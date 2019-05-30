import os
import uuid
import functools
import asyncio

from quart import Quart, abort, make_response, request, jsonify
from psycopg2 import OperationalError
import redis
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from werkzeug.exceptions import HTTPException
import datetime
from datetime import timedelta
import time
import requests
import logging

import lidarrmetadata
from lidarrmetadata import chart
from lidarrmetadata import config
from lidarrmetadata import provider
from lidarrmetadata import util

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
logger.info('Have api logger')

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
                    before_send=processor.create_event)

# if not app.config['PRODUCTION']:
#     # Run api doc server if not running in production
#     from flasgger import Swagger

#     swagger = Swagger(app)

# Set up providers
for provider_name, (args, kwargs) in app.config['PROVIDERS'].items():
    provider_key = list(filter(lambda k: k.upper() == provider_name,
                               provider.PROVIDER_CLASSES.keys()))[0]
    lower_kwargs = {k.lower(): v for k, v in kwargs.items()}
    provider.PROVIDER_CLASSES[provider_key](*args, **lower_kwargs)

# Allow all endpoints to be cached by default
@app.after_request
def add_cache_control_header(response, expiry = provider.utcnow() + timedelta(seconds=app.config['CACHE_TTL']['cloudflare'])):
    if response.status_code not in set([200, 400, 403, 404]):
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
    def wrapper(*args, **kwargs):
        response = func(*args, **kwargs)
        response.cache_control.no_cache = True
        return response
    return wrapper

def get_search_query():
    """
    Search for a track
    """
    query = request.args.get('query')
    if not query:
        abort(make_response(jsonify(error='No query provided'), 400))

    query = query.strip().strip('\x00')
    return query


@app.errorhandler(404)
def page_not_found_error(e):
    return jsonify(error=str(e)), 404


@app.errorhandler(500)
def handle_error(e):
    # TODO Could re-queue these requests?
    if isinstance(e, OperationalError):
        return jsonify(error='Musicbrainz not ready'), 503
    # TODO Bypass caching instead when caching reworked
    elif isinstance(e, redis.ConnectionError):
        return jsonify(error='Could not connect to redis'), 503
    elif isinstance(e, redis.BusyLoadingError):
        return jsonify(error='Redis not ready'), 503
    else:
        sentry_sdk.capture_exception(e)
        return jsonify(error='Internal server error'), 500


def validate_mbid(mbid, check_blacklist=True):
    """
    Validates Musicbrainz ID and returns flask response in case of error
    :param mbid: Musicbrainz ID to verify
    :param check_blacklist: Checks blacklist for blacklisted ids. Defaults to True
    :return: Flask response if error, None if valid
    """
    try:
        uuid.UUID(mbid, version=4)
    except ValueError:
        return jsonify(error='Invalid UUID'), 400

    if check_blacklist and mbid in config.get_config().BLACKLISTED_ARTISTS:
        return jsonify(error='Blacklisted artist'), 403


@app.route('/')
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
    uuid_validation_response = validate_mbid(mbid, True)
    if uuid_validation_response:
        return uuid_validation_response
    
    artist_task = asyncio.create_task(get_artist_info(mbid))
    albums_task = asyncio.create_task(get_artist_albums(mbid))

    artist, expiry = await artist_task
    if not isinstance(artist, dict):
        # i.e. we have returned an error response
        return artist

    albums = await albums_task
    if albums is None:
        return jsonify(error='No release group provider available'), 500
        
    # Filter release group types
    # This will soon happen client side but keep around until api version is bumped for older clients
    primary_types = request.args.get('primTypes', None)
    if primary_types:
        primary_types = primary_types.split('|')
        albums = filter(lambda release_group: release_group.get('Type') in primary_types, albums)
    secondary_types = request.args.get('secTypes', None)
    if secondary_types:
        secondary_types = set(secondary_types.split('|'))
        albums = filter(lambda release_group: (release_group['SecondaryTypes'] == [] and 'Studio' in secondary_types)
                        or secondary_types.intersection(release_group.get('SecondaryTypes')),
                        albums)
    release_statuses = request.args.get('releaseStatuses', None)
    if release_statuses:
        release_statuses = set(release_statuses.split('|'))
        albums = filter(lambda album: release_statuses.intersection(album.get('ReleaseStatuses')),
                        albums)

    artist['Albums'] = albums

    return add_cache_control_header(jsonify(artist), expiry)

async def get_artist_links_and_overview(mbid):
    link_providers = provider.get_providers_implementing(provider.ArtistLinkMixin)    
    links = await link_providers[0].get_artist_links(mbid)

    overview, expiry = await get_overview(links)
    
    return {'Links': links, 'Overview': overview}, expiry

async def get_overview(links):
    overview_providers = provider.get_providers_implementing(provider.ArtistOverviewMixin)    

    if overview_providers:
        wikidata_link = next(filter(
            lambda link: 'wikidata' in link.get('type', ''),
            links), None)
        wikipedia_link = next(filter(
            lambda link: 'wikipedia' in link.get('type', ''),
            links), None)

        if wikidata_link:
            return await overview_providers[0].get_artist_overview(wikidata_link['target'])
        elif wikipedia_link:
            return await overview_providers[0].get_artist_overview(wikipedia_link['target'])
        
    return '', provider.utcnow() + timedelta(days=365)

async def get_artist_info(mbid):
    
    cache_key = f"get_artist_info:{mbid}"
    cached = await util.CACHE.get(cache_key)
    if cached:
        return cached

    now = provider.utcnow()
    expiry = now + timedelta(seconds = app.config['CACHE_TTL']['cloudflare'])
    
    # TODO A lot of repetitive code here. See if we can refactor
    artist_providers = provider.get_providers_implementing(provider.ArtistByIdMixin)
    artist_art_providers = provider.get_providers_implementing(provider.ArtistArtworkMixin)
    
    if not artist_providers:
        # 500 error if we don't have an artist provider since it's essential
        return (jsonify(error='No artist provider available'), 500), None

    # overviews are the slowest thing so set those going first, followed by images
    link_overview_task = asyncio.create_task(get_artist_links_and_overview(mbid))
    if artist_art_providers:
        images_task = asyncio.create_task(artist_art_providers[0].get_artist_images(mbid))
        
    logger.debug("All artist tasks created")
    
    # Await the overwiew and let the rest finish in meantime
    overview_data, overview_expiry = await link_overview_task
    
    artist = await artist_providers[0].get_artist_by_id(mbid)
    if not artist:
        return (jsonify(error='Artist not found'), 404), None

    artist.update(overview_data)
    
    if artist_art_providers:
        images, image_expiry = await images_task
        artist['Images'] = images
    else:
        image_expiry = expiry
    
    expiry = min(expiry, overview_expiry, image_expiry)
    ttl = (expiry - now).total_seconds()
    
    await util.CACHE.set(cache_key, (artist, expiry), ttl=ttl)
        
    return artist, expiry

async def get_artist_albums(mbid):
    release_group_providers = provider.get_providers_implementing(
        provider.ReleaseGroupByArtistMixin)
    if release_group_providers:
        return await release_group_providers[0].get_release_groups_by_artist(mbid)
    else:
        return None

@app.route('/album/<mbid>', methods=['GET'])
async def get_release_group_info_route(mbid):
    output, expiry = await get_release_group_info(mbid)
    
    if isinstance(output, dict):
        output = add_cache_control_header(jsonify(output), expiry)

    return output

async def get_release_group_links_and_overview(mbid):
    link_providers = provider.get_providers_implementing(provider.ReleaseGroupLinkMixin)    
    links = await link_providers[0].get_release_group_links(mbid)

    overview, expiry = await get_overview(links)
    
    return {'Links': links, 'Overview': overview}, expiry

async def get_release_group_artists(mbid):
    track_providers = provider.get_providers_implementing(provider.TracksByReleaseGroupMixin)
    # Do artist ids first since we want to get cracking on artist details
    artist_ids = await track_providers[0].get_release_group_artist_ids(mbid)
    results = await asyncio.gather(*[get_artist_info(gid) for gid in artist_ids])
    artists = [result[0] for result in results]
    expiry = min([result[1] for result in results])
    
    return artists, expiry

async def get_release_group_info_basic(mbid):
    
    cache_key = f"get_release_group_info:{mbid}"
    cached = await util.CACHE.get(cache_key)
    if cached:
        return cached
    
    uuid_validation_response = validate_mbid(mbid)
    if uuid_validation_response:
        return (uuid_validation_response, None)
    
    release_group_providers = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)
    release_providers = provider.get_providers_implementing(provider.ReleasesByReleaseGroupIdMixin)
    album_art_providers = provider.get_providers_implementing(provider.AlbumArtworkMixin)[::-1]
    track_providers = provider.get_providers_implementing(provider.TracksByReleaseGroupMixin)
    
    if not release_group_providers:
        return (jsonify(error='No album provider available'), 500), None

    if not release_providers:
        return(jsonify(error='No release provider available'), 500), None        
    
    if not track_providers:
        return (jsonify(error='No track provider available'), 500), None

    now = provider.utcnow()
    expiry = now + timedelta(seconds = app.config['CACHE_TTL']['cloudflare'])

    # Overviews and art are next slowest so set these going
    links_overview_task = asyncio.create_task(get_release_group_links_and_overview(mbid))
    art_task_1 = asyncio.create_task(album_art_providers[0].get_album_images(mbid))
    art_task_2 = asyncio.create_task(album_art_providers[1].get_album_images(mbid))
    
    # These just query database and are fast
    release_group_task = asyncio.create_task(release_group_providers[0].get_release_group_by_id(mbid))
    releases_task = asyncio.create_task(release_providers[0].get_releases_by_rgid(mbid))
    tracks_task = asyncio.create_task(track_providers[0].get_release_group_tracks(mbid))
    
    logger.debug("All release group tasks created")

    # Wait on this since it's slowest and the rest will get finished in the meantime
    overview_data, overview_expiry = await links_overview_task

    release_group = await release_group_task
    if not release_group:
        return (jsonify(error='Album not found'), 404), None

    release_group.update(overview_data)
    
    release_group['Releases'] = await releases_task

    tracks = await tracks_task
    for release in release_group['Releases']:
        release['Tracks'] = [t for t in tracks if t['ReleaseId'] == release['Id']]

    if album_art_providers:
        images1 = await art_task_1
        if images1:
            release_group['Images'] = images1
            images_expiry = expiry
            art_task_2.cancel()
        else:
            release_group['Images'], images_expiry = await art_task_2
    else:
        release_group['Images'] = []
        
    expiry = min(expiry, overview_expiry, images_expiry)
    ttl = (expiry - now).total_seconds()
        
    await util.CACHE.set(cache_key, (release_group, expiry), ttl=ttl)

    return release_group, expiry

async def get_release_group_info(mbid):

    artists_task = asyncio.create_task(get_release_group_artists(mbid))
    release_group_task = asyncio.create_task(get_release_group_info_basic(mbid))
    
    release_group, rg_expiry = await release_group_task
    artists, artist_expiry = await artists_task
    
    release_group['Artists'] = artists
    return release_group, min(rg_expiry, artist_expiry)

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
        return jsonify(result)


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
    basic = request.args.get('basic', False)

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit

    search_providers = provider.get_providers_implementing(provider.AlbumNameSearchMixin)
    
    if search_providers:
        album_ids = await search_providers[0].search_album_name(query, artist_name=artist_name, limit=limit)
        
        if basic:
            albums = album_ids
            validity = 1
        else:
            
            results = await asyncio.gather(*[get_release_group_info(item['Id']) for item in album_ids])
            albums = [result[0] for result in results]
            
            # Current versions of lidarr will fail trying to parse the tracks contained in releases
            # because it's not expecting it to be present and passes null for ArtistMetadata dict
            for album in albums:
                album['Releases'] = []
            
            validity = min([result[1] for result in results] or [0])
        
    else:
        return jsonify(error="No album search providers"), 500

    return add_cache_control_header(jsonify(albums), validity)

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
    albums = request.args.getlist('album')

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit
    
    basic = request.args.get('basic', False)

    search_providers = provider.get_providers_implementing(
        provider.ArtistNameSearchMixin)

    if not search_providers:
        return jsonify(error='No search providers available'), 500

    # TODO Prefer certain providers?
    artist_ids = filter(lambda a: a['Id'] not in config.get_config().BLACKLISTED_ARTISTS,
                        await search_providers[0].search_artist_name(query, limit=limit, albums=albums))

    if basic:
        artists = artist_ids
        validity = 1
    else:
        results = await asyncio.gather(*[get_artist_info(item['Id']) for item in artist_ids])
        artists = [result[0] for result in results]
        validity = min([result[1] for result in results] or [0])
    
    return add_cache_control_header(jsonify(artists), validity)

@app.route('/search')
async def search_route():
    type = request.args.get('type', None)

    if type == 'artist':
        return search_artist()
    elif type == 'album':
        return search_album()
    else:
        error = jsonify(error='Type not provided') if type is None else jsonify(
            error='Unsupported search type {}'.format(type))
        return error, 400
    
# @app.route('/fanart_updates')
# def get_fanart_updates():
#     fanart_provider = provider.get_providers_implementing(provider.ArtistArtworkMixin)[0]
    
#     # long_date = (datetime.datetime(2019, 5, 20, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()
#     # short_date = (datetime.datetime(2019, 5, 20, 23, 59, 59) - datetime.datetime(1970, 1, 1)).total_seconds()

#     # Gives updates that happened on the 19th
#     long_date = (datetime.datetime(2019, 5, 19, 23, 59, 59) - datetime.datetime(1970, 1, 1)).total_seconds()
#     short_date = (datetime.datetime(2019, 5, 20, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()
    
#     # Gives updates that happened on the 19th
#     long_date = (datetime.datetime(2019, 5, 12, 23, 59, 59) - datetime.datetime(1970, 1, 1)).total_seconds()
#     short_date = (datetime.datetime(2019, 5, 13, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()
    
#     # long_date = (datetime.datetime(2019, 5, 19, 23, 59, 59) - datetime.datetime(1970, 1, 1)).total_seconds()
#     # short_date = (datetime.datetime(2019, 5, 14, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()

#     # long_date = (datetime.datetime(2019, 5, 11, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()
#     # short_date = (datetime.datetime(2019, 5, 12, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()
    
#     # long_date = (datetime.datetime(2019, 5, 12, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()
#     # short_date = (datetime.datetime(2019, 5, 13, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()
    
#     # long_date = (datetime.datetime(2019, 5, 13, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()
#     # short_date = (datetime.datetime(2019, 5, 14, 0, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds()

    
#     # long_date = (datetime.datetime(2019, 5, 20, 11, 5, 0) - datetime.datetime(1970, 1, 1)).total_seconds() - 7 * 24 * 60 * 60
#     # short_date = (datetime.datetime(2019, 5, 20, 11, 0, 0) - datetime.datetime(1970, 1, 1)).total_seconds() - 7 * 24 * 60 * 60
    
#     long = fanart_provider.get_fanart_updates(long_date)
#     short = fanart_provider.get_fanart_updates(short_date)
    
#     ids = fanart_provider.diff_fanart_updates(long, short)
    
#     return jsonify(sorted(ids))

async def invalidate_cache():
    
    ## this is used as a prefix in various places to make sure
    ## we keep cache for different metadata versions separate
    base_url = app.config['CLOUDFLARE_URL_BASE'] + '/' +  app.config['APPLICATION_ROOT'].lstrip('/').rstrip('/')
    
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
        invalidated = []

        cache_users = provider.get_providers_implementing(provider.InvalidateCacheMixin)
        for cache_user in cache_users:
            result = cache_user.invalidate_cache(base_url)

            artists = artists.union(result['artists'])
            albums = albums.union(result['albums'])

        for artist in artists:
            # util.CACHE.delete_memoized(get_artist_info, artist)
            # util.CACHE.delete_memoized(get_artist_albums, artist)

            key = '{url}/artist/{artist}'.format(url=base_url, artist=artist)
            invalidated.append(key)

        for album in albums:
            # util.CACHE.delete_memoized(get_release_group_info, album)

            key = '{url}/album/{album}'.format(url=base_url, album=album)
            invalidated.append(key)

        # cloudflare only accepts 500 files at a time
        for i in xrange(0, len(invalidated), 500):
            invalidate_cloudflare(invalidated[i:i+500], retries = 2)
    
    finally:
        util.CACHE.delete(invalidation_in_progress_key)
        # make sure any exceptions are not swallowed
        pass
        
    logger.info('Invalidation complete')
    
    return jsonify(invalidated)

def invalidate_cloudflare(files, retries = 2):

    zoneid = app.config['CLOUDFLARE_ZONE_ID']
    if not zoneid:
        return
    
    url = 'https://api.cloudflare.com/client/v4/zones/{}/purge_cache'.format(zoneid)
    headers = {'X-Auth-Email': app.config['CLOUDFLARE_AUTH_EMAIL'],
               'X-Auth-Key': app.config['CLOUDFLARE_AUTH_KEY'],
               'Content-Type': 'application/json'}
    data = {'files': files}
    
    r = requests.post(url, headers=headers, json=data)
    logger.info(r.text)
    
    if not r.json()['success'] and retries > 0:
        invalidate_cloudflare(files, retries - 1)
        
@app.before_serving
async def run_async_init():
    async_providers = provider.get_providers_implementing(provider.AsyncInit)
    for prov in async_providers:
        await prov._init()
        
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=config.get_config().HTTP_PORT, use_reloader=True)
