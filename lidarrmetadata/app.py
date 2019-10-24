import os
import uuid
import functools
import asyncio

from quart import Quart, abort, make_response, request, jsonify, redirect, url_for
from quart.exceptions import HTTPStatusException

import redis
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import datetime
from datetime import timedelta
import time
import logging
import aiohttp
from timeit import default_timer as timer
from spotipy import SpotifyException

import lidarrmetadata
from lidarrmetadata import api
from lidarrmetadata import chart
from lidarrmetadata import config
from lidarrmetadata import provider
from lidarrmetadata import util

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.info('Have app logger')

app = Quart(__name__)
app.config.from_object(config.get_config())

if app.config['SENTRY_DSN']:
    if app.config['SENTRY_REDIS_HOST'] is not None:
        processor = util.SentryRedisTtlProcessor(redis_host=app.config['SENTRY_REDIS_HOST'],
                                                redis_port=app.config['SENTRY_REDIS_PORT'],
                                                ttl=app.config['SENTRY_TTL'])
    else:
        processor = util.SentryTtlProcessor(ttl=app.config['SENTRY_TTL'])

    sentry_sdk.init(dsn=app.config['SENTRY_DSN'],
                    integrations=[FlaskIntegration()],
                    before_send=processor.create_event,
                    send_default_pii=True)

# Allow all endpoints to be cached by default
@app.after_request
def add_cache_control_header(response, expiry = provider.utcnow() + timedelta(seconds=app.config['CACHE_TTL']['cloudflare'])):
    if response.status_code not in set([200, 301, 400, 403, 404]):
        response.cache_control.no_cache = True
    # This is a bodge to figure out if we have already set any cache control headers
    elif not response.cache_control or not response.cache_control._directives:
        if expiry:
            now = provider.utcnow()
            response.cache_control.public = True
            # We want to allow caching on cloudflare (which we can invalidate)
            # but disallow caching for local users (which we cannot invalidate)
            response.cache_control.s_maxage = (expiry - now).total_seconds()
            response.cache_control.max_age = 0
            response.expires = now - timedelta(days=1)
        else:
            response.cache_control.no_cache = True
    return response
    
# Decorator to disable caching by endpoint
def no_cache(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        response = await func(*args, **kwargs)
        response.cache_control.no_cache = True
        return response
    return wrapper

def get_search_query():
    """
    Search for a track
    """
    query = request.args.get('query', '')
    query = query.strip().strip('\x00')
    if not query:
        abort(400, 'No query provided')
    
    logger.info(f"Search query: {query}")
    
    # These are invalid search queries for lucene
    if query in set(['-', '+']):
        abort(400, 'Invalid search query')
    
    return query

@app.errorhandler(HTTPStatusException)
def handle_error(e):
    return jsonify(error = e.description), e.status_code

@app.errorhandler(api.ReleaseGroupNotFoundException)
async def handle_error(e):

    # Look for a redirect
    album_provider = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)[0]
    new_id = await album_provider.redirect_old_release_group_id(e.mbid)
    
    if new_id:
        return redirect(app.config['ROOT_PATH'] + url_for('get_release_group_info_route', mbid=new_id), 301)
    
    return jsonify(error='Album not found'), 404

@app.errorhandler(api.ArtistNotFoundException)
async def handle_error(e):

    # Look for a redirect
    artist_provider = provider.get_providers_implementing(provider.ArtistByIdMixin)[0]
    new_id = await artist_provider.redirect_old_artist_id(e.mbid)
    
    if new_id:
        return redirect(app.config['ROOT_PATH'] + url_for('get_artist_info_route', mbid=new_id), 301)
    
    return jsonify(error='Artist not found'), 404

@app.errorhandler(redis.ConnectionError)
def handle_error(e):
    return jsonify(error='Could not connect to redis'), 503

@app.errorhandler(redis.BusyLoadingError)
def handle_error(e):
    return jsonify(error='Redis not ready'), 503

@app.errorhandler(500)
def handle_error(e):
    sentry_sdk.capture_exception(e)
    return jsonify(error='Internal server error'), 500

def validate_mbid(mbid):
    """
    Validates Musicbrainz ID and returns flask response in case of error
    :param mbid: Musicbrainz ID to verify
    :return: Flask response if error, None if valid
    """
    try:
        uuid.UUID(mbid, version=4)
    except ValueError:
        return jsonify(error='Invalid UUID'), 400

@app.route('/')
@no_cache
async def default_route():
    """
    Default route with API information
    :return:
    """
    vintage_providers = provider.get_providers_implementing(
        provider.DataVintageMixin)
    
    data = await vintage_providers[0].data_vintage()

    info = {
        'branch': os.getenv('GIT_BRANCH'),
        'commit': os.getenv('COMMIT_HASH'),
        'version': lidarrmetadata.__version__,
        'replication_date': data
    }
    return jsonify(info)


@app.route('/artist/<mbid>', methods=['GET'])
async def get_artist_info_route(mbid):
    uuid_validation_response = validate_mbid(mbid)
    if uuid_validation_response:
        return uuid_validation_response
    
    artist_task = asyncio.create_task(api.get_artist_info(mbid))
    albums_task = asyncio.create_task(api.get_artist_albums(mbid))

    artist, expiry = await artist_task

    albums = await albums_task
        
    # Filter release group types
    # This will soon happen client side but keep around until api version is bumped for older clients
    primary_types = request.args.get('primTypes', None)
    if primary_types:
        primary_types = primary_types.split('|')
        albums = list(filter(lambda release_group: release_group.get('Type') in primary_types, albums))
    secondary_types = request.args.get('secTypes', None)
    if secondary_types:
        secondary_types = set(secondary_types.split('|'))
        albums = list(filter(lambda release_group: (release_group['SecondaryTypes'] == [] and 'Studio' in secondary_types)
                             or secondary_types.intersection(release_group.get('SecondaryTypes')),
                             albums))
    release_statuses = request.args.get('releaseStatuses', None)
    if release_statuses:
        release_statuses = set(release_statuses.split('|'))
        albums = list(filter(lambda album: release_statuses.intersection(album.get('ReleaseStatuses')),
                             albums))

    artist['Albums'] = albums

    return add_cache_control_header(jsonify(artist), expiry)

@app.route('/album/<mbid>', methods=['GET'])
async def get_release_group_info_route(mbid):
    
    uuid_validation_response = validate_mbid(mbid)
    if uuid_validation_response:
        return uuid_validation_response
    
    output, expiry = await api.get_release_group_info(mbid)
    
    return add_cache_control_header(jsonify(output), expiry)

@app.route('/chart/<name>/<type_>/<selection>')
async def chart_route(name, type_, selection):
    """
    Gets chart
    :param name: Name of chart. 404 if name invalid
    """
    name = name.lower()
    count = request.args.get('count', 10, type=int)

    # Get remaining chart-dependent args
    chart_kwargs = request.args.to_dict()
    if 'count' in chart_kwargs:
        del chart_kwargs['count']

    key = (name, type_, selection)

    # Function to get each chart. Use lower case for keys
    charts = {
        ('apple-music', 'album', 'top'): chart.get_apple_music_top_albums_chart,
        ('apple-music', 'album', 'new'): chart.get_apple_music_new_albums_chart,
        ('billboard', 'album', 'top'): chart.get_billboard_200_albums_chart,
        ('billboard', 'artist', 'top'): chart.get_billboard_100_artists_chart,
        ('itunes', 'album', 'top'): chart.get_itunes_top_albums_chart,
        ('itunes', 'album', 'new'): chart.get_itunes_new_albums_chart,
        ('lastfm', 'album', 'top'): chart.get_lastfm_album_chart,
        ('lastfm', 'artist', 'top'): chart.get_lastfm_artist_chart
    }

    if key not in charts.keys():
        return jsonify(error='Chart {}/{}/{} not found'.format(*key)), 404
    else:
        result = await charts[key](count, **chart_kwargs)
        expiry = provider.utcnow() + timedelta(seconds=app.config['CACHE_TTL']['chart'])
        return add_cache_control_header(jsonify(result), expiry)

@app.route('/search/album')
async def search_album():
    """Search for a human-readable album
    ---
    parameters:
     - name: query
       in: path
       type: string
       required: true
    responses:
      200:
            description: Returns a set of albums
            schema:
              $ref: /search/album/dark%20side%20%of%20the%20moon
            examples:
              {
                "mbId": "a1ad30cb-b8c4-4d68-9253-15b18fcde1d1",
                "release_date": "Mon, 14 Nov 2005 00:00:00 GMT",
                "title": "Dark Side of the Moon"
              }
    """
    query = get_search_query()

    artist_name = request.args.get('artist', '')
    include_tracks = request.args.get('includeTracks', False)

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit

    albums, scores, validity = await get_album_search_results(query, limit, include_tracks, artist_name)

    return add_cache_control_header(jsonify(albums), validity)

async def get_album_search_results(query, limit, include_tracks, artist_name):
    search_providers = provider.get_providers_implementing(provider.AlbumNameSearchMixin)
    
    if search_providers:
        start = timer()
        search_results = await search_providers[0].search_album_name(query, artist_name=artist_name, limit=limit)
        logger.debug(f"Got album search results in {(timer() - start) * 1000:.0f}ms ")

        async def get_search_result(item):
            result, validity = await api.get_release_group_info(item['Id'])
            return result, item['Score'], validity
        
        results = await asyncio.gather(*[get_search_result(item) for item in search_results])
        albums = [result[0] for result in results]

        # Current versions of lidarr will fail trying to parse the tracks contained in releases
        # because it's not expecting it to be present and passes null for ArtistMetadata dict
        if not include_tracks:
            for album in albums:
                album['releases'] = []

        scores = [result[1] for result in results]
        validity = min([result[2] for result in results] or [provider.utcnow()])

        return albums, scores, validity
        
    else:
        abort(500, "No album search providers")

@app.route('/search/artist', methods=['GET'])
async def search_artist():
    """Search for a human-readable artist
    ---
    parameters:
     - name: query
       in: path
       type: string
       required: true
    responses:
      200:
            description: Returns a set of artists limited to the first 5
            schema:
              $ref: /search/artist/afi
            examples:
              {
                    "Albums": [],
            "AristUrl": "http://www.last.fm/music/afi",
            "ArtistName": "AFI",
            "Genres": [],
            "Id": "4fc58550-637f-496f-b6bc-3a62ba7f2f7e",
            "Images": [
                {
                    "Url": "https://lastfm-img2.akamaized.net/i/u/80cd9530f9ef4c783873b1a39951ff98.png",
                    "media_type": "cover"
                }
            ],
            "Overview": "AFI (A Fire Inside) is an American punk rock/alternative rock band 
                                    from Ukiah, CA that formed in 1991."
                }
    """
    query = get_search_query()

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit

    artists, scores, validity = await get_artist_search_results(query, limit)
    
    return add_cache_control_header(jsonify(artists), validity)

async def get_artist_search_results(query, limit):
    search_providers = provider.get_providers_implementing(
        provider.ArtistNameSearchMixin)

    if not search_providers:
        return abort(500, 'No search providers available')

    # TODO Prefer certain providers?
    artist_ids = await search_providers[0].search_artist_name(query, limit=limit)

    async def get_search_result(id, score):
        result, validity = await api.get_artist_info(id)
        return result, score, validity

    results = await asyncio.gather(*[get_search_result(item['Id'], item['Score']) for item in artist_ids])

    artists = [result[0] for result in results]
    scores = [result[1] for result in results]
    validity = min([result[2] for result in results] or [provider.utcnow()])

    return artists, scores, validity

@app.route('/search/all', methods=['GET'])
async def search_all():
    query = get_search_query()

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit

    results = await asyncio.gather(
        get_artist_search_results(query, limit),
        get_album_search_results(query, limit, True, None)
    )
    artists, artist_scores, artist_validity = results[0]
    albums, album_scores, album_validity = results[1]
    validity = min(artist_validity, album_validity)

    artist_items = [{'score': artist_scores[i],
                     'artist': x,
                     'album': None}
                    for i, x in enumerate(artists)]
    album_items = [{'score': album_scores[i],
                    'artist': None,
                    'album': x}
                   for i, x in enumerate(albums)]
    results = artist_items + album_items
    results.sort(key = lambda i: i['score'], reverse = True)

    return add_cache_control_header(jsonify(results), validity)

@app.route('/search/fingerprint', methods=['POST'])
async def search_fingerprint():
    ids = await request.json

    if ids is None:
        return jsonify(error='Bad Request - expected JSON list of recording IDs as post body'), 400
    
    logger.info(ids)

    album_provider = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)[0]
    album_ids = await album_provider.get_release_groups_by_recording_ids(ids)

    logger.info('got albums')
    logger.info(album_ids)

    results = await asyncio.gather(*[api.get_release_group_info(id) for id in album_ids])
    albums = [result[0] for result in results]
    validity = min([result[1] for result in results] or [provider.utcnow()])

    return add_cache_control_header(jsonify(albums), validity)

@app.route('/search')
async def search_route():
    type = request.args.get('type', None)

    if type == 'artist':
        return await search_artist()
    elif type == 'album':
        return await search_album()
    elif type == 'all':
        return await search_all()
    else:
        error = jsonify(error='Type not provided') if type is None else jsonify(
            error='Unsupported search type {}'.format(type))
        return error, 400

@app.route('/spotify/artist/<spotify_id>', methods=['GET'])
async def spotify_lookup_artist(spotify_id):
    mbid, expires = await util.SPOTIFY_CACHE.get(spotify_id)

    if mbid == 0 and expires > provider.utcnow():
        return jsonify(error='Not found'), 404
    if mbid is not None:
        return redirect(app.config['ROOT_PATH'] + url_for('get_artist_info_route', mbid=mbid), 301)

    # Search on links in musicbrainz db
    link_provider = provider.get_providers_implementing(provider.ArtistByIdMixin)[0]
    artistid = await link_provider.get_artist_id_from_spotify_id(spotify_id)
    logger.debug(f"Got match from musicbrainz db: {artistid}")
    if artistid:
        await util.SPOTIFY_CACHE.set(spotify_id, artistid, ttl=None)
        return redirect(app.config['ROOT_PATH'] + url_for('get_artist_info_route', mbid=artistid), 301)

    # Fall back to a text search for a popular album
    try:
        spotify_provider = provider.get_providers_implementing(provider.SpotifyIdMixin)[0]
        spotifyalbum = spotify_provider.album_from_artist(spotify_id)
    except SpotifyException:
        await util.SPOTIFY_CACHE.set(spotify_id, 0, ttl=app.config['CACHE_TTL']['cloudflare'])
        return jsonify(error='Not found'), 404
    
    spotifyalbum = await spotify_lookup_by_text_search(spotifyalbum)
    if spotifyalbum is None:
        return jsonify(error='Not found'), 404

    await util.SPOTIFY_CACHE.set(spotifyalbum['AlbumSpotifyId'], spotifyalbum['AlbumMusicBrainzId'], ttl=None)
    await util.SPOTIFY_CACHE.set(spotifyalbum['ArtistSpotifyId'], spotifyalbum['ArtistMusicBrainzId'], ttl=None)

    return redirect(app.config['ROOT_PATH'] + url_for('get_artist_info_route', mbid=spotifyalbum['ArtistMusicBrainzId']), 301)

@app.route('/spotify/album/<spotify_id>', methods=['GET'])
async def spotify_lookup_album(spotify_id):
    mbid, expires = await util.SPOTIFY_CACHE.get(spotify_id)

    if mbid == 0 and expires > provider.utcnow():
        return jsonify(error='Not found'), 404
    if mbid is not None:
        return redirect(app.config['ROOT_PATH'] + url_for('get_release_group_info_route', mbid=mbid), 301)

    # Search on links in musicbrainz db
    link_provider = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)[0]
    albumid = await link_provider.get_release_group_id_from_spotify_id(spotify_id)
    logger.debug(f"Got match from musicbrainz db: {albumid}")
    if albumid:
        await util.SPOTIFY_CACHE.set(spotify_id, 0, ttl=app.config['CACHE_TTL']['cloudflare'])
        return redirect(app.config['ROOT_PATH'] + url_for('get_release_group_info_route', mbid=albumid), 301)

    # Fall back to a text search
    try:
        spotify_provider = provider.get_providers_implementing(provider.SpotifyIdMixin)[0]
        spotifyalbum = spotify_provider.album(spotify_id)
    except SpotifyException:
        await util.SPOTIFY_CACHE.set(spotify_id, 0, ttl=None)
        return jsonify(error='Not found'), 404

    spotifyalbum = await spotify_lookup_by_text_search(spotifyalbum)
    if spotifyalbum is None:
        return jsonify(error='Not found'), 404

    await util.SPOTIFY_CACHE.set(spotifyalbum['AlbumSpotifyId'], spotifyalbum['AlbumMusicBrainzId'], ttl=None)

    return redirect(app.config['ROOT_PATH'] + url_for('get_release_group_info_route', mbid=spotifyalbum['AlbumMusicBrainzId']), 301)

async def spotify_lookup_by_text_search(spotifyalbum):
    logger.debug(f"Artist: {spotifyalbum['Artist']} Album: {spotifyalbum['Album']}")    
    
    # do search
    search_provider = provider.get_providers_implementing(provider.AlbumNameSearchMixin)[0]
    result = await search_provider.search_album_name(spotifyalbum['Album'], artist_name=spotifyalbum['Artist'], limit=1)

    if not result:
        ttl = app.config['CACHE_TTL']['cloudflare']
        await util.SPOTIFY_CACHE.set(spotifyalbum['AlbumSpotifyId'], 0, ttl=ttl)
        await util.SPOTIFY_CACHE.set(spotifyalbum['ArtistSpotifyId'], 0, ttl=ttl)
        return None

    # Map back to an artist
    albumid = result[0]['Id']
    album, validity = await api.get_release_group_info(result[0]['Id'])
    artistid = album['artistid']

    spotifyalbum['AlbumMusicBrainzId'] = albumid
    spotifyalbum['ArtistMusicBrainzId'] = artistid

    return spotifyalbum

@app.route('/spotify/lookup', methods=['POST'])
async def spotify_lookup():
    ids = await request.json

    if ids is None:
        return jsonify(error='Bad Request - expected JSON list of spotify IDs as post body'), 400
    
    logger.info(ids)

    results = await util.SPOTIFY_CACHE.multi_get(ids)
    output = [{'spotifyid': ids[x], 'musicbrainzid': results[x][0]} for x in range(len(ids))]

    return jsonify(output)
    
@app.route('/invalidate')
@no_cache
async def invalidate_cache():
    
    ## this is used as a prefix in various places to make sure
    ## we keep cache for different metadata versions separate
    base_url = app.config['CLOUDFLARE_URL_BASE'] + '/' +  app.config['ROOT_PATH'].lstrip('/').rstrip('/')
    
    ## Use a cache key to make sure we don't trigger this in parallel
    invalidation_in_progress_key = base_url + 'CacheInvalidationInProgress'
    in_progress = await util.CACHE.get(invalidation_in_progress_key)
    if in_progress:
        return jsonify('Invalidation already in progress'), 500
    
    try:
        await util.CACHE.set(invalidation_in_progress_key, True, timeout=60*5)
        logger.info('Invalidating cache')

        ## clear cache for all providers, aggregating a list of artists/albums
        ## that we need to invalidate the final responses for
        artists = set()
        albums = set()

        ## Get all the artists/albums that need updating
        cache_users = provider.get_providers_implementing(provider.InvalidateCacheMixin)
        for cache_user in cache_users:
            result = await cache_user.invalidate_cache(base_url)

            artists = artists.union(result['artists'])
            albums = albums.union(result['albums'])

        ## Invalidate all the local caches
        ## Use set rather than expires so that we add entries for new items also
        await asyncio.gather(
            util.ARTIST_CACHE.multi_set([(artist, None) for artist in artists], ttl=0, timeout=None),
            util.ALBUM_CACHE.multi_set([(album, None) for album in albums], ttl=0, timeout=None)
        )

        ## Invalidate cloudflare cache
        invalidated = [f'{base_url}/artist/{artist}' for artist in artists] + [f'{base_url}/album/{album}' for album in albums]
        await invalidate_cloudflare(invalidated)
    
    finally:
        await util.CACHE.delete(invalidation_in_progress_key)
        # make sure any exceptions are not swallowed
        pass
        
    logger.info('Invalidation complete')
    
    return jsonify(invalidated)

async def invalidate_cloudflare(files):
    
    zoneid = app.config['CLOUDFLARE_ZONE_ID']
    if not zoneid:
        return
    
    url = f'https://api.cloudflare.com/client/v4/zones/{zoneid}/purge_cache'
    headers = {'X-Auth-Email': app.config['CLOUDFLARE_AUTH_EMAIL'],
               'X-Auth-Key': app.config['CLOUDFLARE_AUTH_KEY'],
               'Content-Type': 'application/json'}
    
    async with aiohttp.ClientSession() as session:
        # cloudflare only accepts 500 files at a time
        for i in range(0, len(files), 500):
            data = {'files': files[i:i+500]}
            retries = 2
            
            while retries > 0:
                async with session.post(url, headers=headers, json=data) as r:
                    logger.info(await r.text())
                    json = await r.json()

                    if json.get('success', False):
                        break
                    
                    retries -= 1

@app.route('/spotify/auth')
@no_cache
async def handle_spotify_auth_redirect():
    code = request.args.get('code', '')
    state = request.args.get('state', '')

    if not code:
        abort(400, 'No auth code provided')

    if not state:
        abort(400, 'No state provided')

    if not state.endswith('/oauth.html'):
        abort(400, 'Illegal state value')

    spotify_provider = provider.get_providers_implementing(provider.SpotifyAuthMixin)[0]

    try:
        access_token, expires_in, refresh_token = await spotify_provider.get_token(code)
        newurl = f"{state}?access_token={access_token}&expires_in={expires_in}&refresh_token={refresh_token}";

        return redirect(newurl, 302)
    except aiohttp.ClientResponseError as error:
        abort(error.status, f"spotify: {error.message}")

@app.route('/spotify/renew')
@no_cache
async def handle_spotify_token_renew():
    refresh_token = request.args.get('refresh_token', '')

    if not refresh_token:
        abort(400, 'No refresh token provided')

    spotify_provider = provider.get_providers_implementing(provider.SpotifyAuthMixin)[0]

    try:
        json = await spotify_provider.refresh_token(refresh_token)
        return jsonify(json)
    except aiohttp.ClientResponseError as error:
        abort(error.status, error.message)

@app.after_serving
async def run_async_del():
    async_providers = provider.get_providers_implementing(provider.AsyncDel)
    for prov in async_providers:
        await prov._del()
        
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=config.get_config().HTTP_PORT, use_reloader=True)
