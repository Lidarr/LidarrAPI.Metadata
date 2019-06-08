import os
import uuid
import functools
import asyncio

from quart import Quart, abort, make_response, request, jsonify
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
                    before_send=processor.create_event)

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
        abort(400, 'No query provided')

    query = query.strip().strip('\x00')
    return query


@app.errorhandler(404)
def page_not_found_error(e):
    return jsonify(error=str(e)), 404

@app.errorhandler(HTTPStatusException)
def handle_error(e):
    return jsonify(error = e.description), e.status_code

@app.errorhandler(500)
def handle_error(e):
    # TODO Bypass caching instead when caching reworked
    if isinstance(e, redis.ConnectionError):
        return jsonify(error='Could not connect to redis'), 503
    elif isinstance(e, redis.BusyLoadingError):
        return jsonify(error='Redis not ready'), 503
    elif isinstance(e, api.ArtistNotFoundException):
        return jsonify(error='Artist not found'), 404
    elif isinstance(e, api.ReleaseGroupNotFoundException):
        return jsonify(error='Album not found'), 404
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
    
    artist_task = asyncio.create_task(api.get_artist_info(mbid))
    albums_task = asyncio.create_task(api.get_artist_albums(mbid))

    artist, expiry = await artist_task

    albums = await albums_task
    if albums is None:
        return jsonify(error='No release group provider available'), 500
        
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
    basic = request.args.get('basic', False)
    include_tracks = request.args.get('includeTracks', False)

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit

    search_providers = provider.get_providers_implementing(provider.AlbumNameSearchMixin)
    
    if search_providers:
        start = timer()
        album_ids = await search_providers[0].search_album_name(query, artist_name=artist_name, limit=limit)
        logger.debug(f"Got album search results in {(timer() - start) * 1000:.0f}ms ")
        
        if basic:
            albums = album_ids
            validity = 1
        else:
            
            results = await asyncio.gather(*[api.get_release_group_info(item['Id']) for item in album_ids])
            albums = [result[0] for result in results]
            
            # Current versions of lidarr will fail trying to parse the tracks contained in releases
            # because it's not expecting it to be present and passes null for ArtistMetadata dict
            if not include_tracks:
                for album in albums:
                    album['releases'] = []
            
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
        results = await asyncio.gather(*[api.get_artist_info(item['Id']) for item in artist_ids])
        artists = [result[0] for result in results]
        validity = min([result[1] for result in results] or [0])
    
    return add_cache_control_header(jsonify(artists), validity)

@app.route('/search')
async def search_route():
    type = request.args.get('type', None)

    if type == 'artist':
        return await search_artist()
    elif type == 'album':
        return await search_album()
    else:
        error = jsonify(error='Type not provided') if type is None else jsonify(
            error='Unsupported search type {}'.format(type))
        return error, 400
    
@app.route('/invalidate')
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

        ## Get all the artists/albums that need updating
        cache_users = provider.get_providers_implementing(provider.InvalidateCacheMixin)
        for cache_user in cache_users:
            result = await cache_user.invalidate_cache(base_url)

            artists = artists.union(result['artists'])
            albums = albums.union(result['albums'])

        ## Invalidate all the local caches
        await asyncio.gather(
            *(util.CACHE.delete(f"get_artist_info:{artist}") for artist in artists),
            *(util.CACHE.delete(f"get_release_group_info_basic:{album}") for album in albums),
            *(util.ARTIST_CACHE.expire(artist, ttl=-1) for artist in artists),
            *(util.ALBUM_CACHE.expire(album, ttl=-1) for album in albums)
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

@app.before_serving
async def run_async_init():
    async_providers = provider.get_providers_implementing(provider.AsyncInit)
    for prov in async_providers:
        await prov._init()
        
@app.after_serving
async def run_async_del():
    async_providers = provider.get_providers_implementing(provider.AsyncDel)
    for prov in async_providers:
        await prov._del()
        
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=config.get_config().HTTP_PORT, use_reloader=True)
