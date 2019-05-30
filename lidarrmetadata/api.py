import os
import uuid
import functools

from flask import Flask, abort, make_response, request, jsonify
from flask_httpauth import HTTPBasicAuth
from psycopg2 import OperationalError
import redis
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from werkzeug.exceptions import HTTPException
import datetime
import requests
import logging

import lidarrmetadata
from lidarrmetadata import chart
from lidarrmetadata import config
from lidarrmetadata import provider
from lidarrmetadata.provider import ProviderUnavailableException
from lidarrmetadata import util

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.info('Have api logger')

app = Flask(__name__)
app.config.from_object(config.get_config())

auth = HTTPBasicAuth()

@auth.get_password
def get_pw(username):
    if username == app.config['INVALIDATE_USERNAME']:
        return app.config['INVALIDATE_PASSWORD']
    return None

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

if app.config['USE_CACHE']:
    util.CACHE.config = config.get_config().REDIS_CACHE_CONFIG
    util.CACHE.init_app(app)
    
    util.FANART_CACHE.config = config.get_config().FANART_CACHE_CONFIG
    util.FANART_CACHE.init_app(app)
    
    util.WIKI_CACHE.config = config.get_config().WIKI_CACHE_CONFIG
    util.WIKI_CACHE.init_app(app)

if not app.config['PRODUCTION']:
    # Run api doc server if not running in production
    from flasgger import Swagger

    swagger = Swagger(app)

# Set up providers
for provider_name, (args, kwargs) in app.config['PROVIDERS'].items():
    provider_key = list(filter(lambda k: k.upper() == provider_name,
                               provider.PROVIDER_CLASSES.keys()))[0]
    lower_kwargs = {k.lower(): v for k, v in kwargs.items()}
    provider.PROVIDER_CLASSES[provider_key](*args, **lower_kwargs)

# Allow all endpoints to be cached by default
@app.after_request
def add_cache_control_header(response, ttl = app.config['CACHE_TTL_GOOD']):
    if response.status_code not in set([200, 400, 403, 404]):
        response.cache_control.no_cache = True
    elif not response.cache_control:
        if ttl > 0:
            response.cache_control.public = True
            # We want to allow caching on cloudflare (which we can invalidate)
            # but disallow caching for local users (which we cannot invalidate)
            response.cache_control.s_maxage = ttl
            response.cache_control.max_age = 0
            response.expires = datetime.datetime.utcnow() - datetime.timedelta(days=1)
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
@no_cache
def default_route():
    """
    Default route with API information
    :return:
    """
    vintage_providers = provider.get_providers_implementing(
        provider.DataVintageMixin)

    info = {
        'branch': os.getenv('GIT_BRANCH'),
        'commit': os.getenv('COMMIT_HASH'),
        'version': lidarrmetadata.__version__,
        'replication_date': vintage_providers[0].data_vintage()
    }
    return jsonify(info)


@app.route('/artist/<mbid>', methods=['GET'])
def get_artist_info_route(mbid):
    uuid_validation_response = validate_mbid(mbid, True)
    if uuid_validation_response:
        return uuid_validation_response

    artist, validity = get_artist_info(mbid)
    if not isinstance(artist, dict):
        # i.e. we have returned an error response
        return artist

    albums = get_artist_albums(mbid)
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

    return add_cache_control_header(jsonify(artist), validity)

@util.CACHE.memoize_variable_timeout()
def get_artist_info(mbid):
    # TODO A lot of repetitive code here. See if we can refactor
    artist_providers = provider.get_providers_implementing(
        provider.ArtistByIdMixin)
    link_providers = provider.get_providers_implementing(
        provider.ArtistLinkMixin)

    artist_art_providers = provider.get_providers_implementing(provider.ArtistArtworkMixin)

    # TODO Figure out preferred providers
    if artist_providers:
        artist = artist_providers[0].get_artist_by_id(mbid)
        if not artist:
            return (jsonify(error='Artist not found'), 404), 0
    else:
        # 500 error if we don't have an artist provider since it's essential
        return (jsonify(error='No artist provider available'), 500), 0
    
    if link_providers and not artist.get('Links', None):
        artist['Links'] = link_providers[0].get_artist_links(mbid)

    validity = app.config['CACHE_TTL_GOOD']
        
    try:
        artist['Overview'] = get_overview(artist['Links'])
    except ProviderUnavailableException:
        artist['Overview'] = ''
        validity = app.config['CACHE_TTL_BAD']
        
    if artist_art_providers:
        try:
            artist['Images'] = artist_art_providers[0].get_artist_images(mbid)
        except ProviderUnavailableException:
            artist['Images'] = []
            validity = app.config['CACHE_TTL_BAD']
    else:
        artist['Images'] = []
        
    return artist, validity

def get_overview(links):
    overview_providers = provider.get_providers_implementing(provider.ArtistOverviewMixin)    

    if overview_providers:
        wikidata_link = next(filter(
            lambda link: 'wikidata' in link.get('type', ''),
            links), None)
        wikipedia_link = next(filter(
            lambda link: 'wikipedia' in link.get('type', ''),
            links), None)

        if wikidata_link:
            return overview_providers[0].get_artist_overview(wikidata_link['target'])
        elif wikipedia_link:
            return overview_providers[0].get_artist_overview(wikipedia_link['target'])
        
    return ''

@util.CACHE.memoize()
def get_artist_albums(mbid):
    release_group_providers = provider.get_providers_implementing(
        provider.ReleaseGroupByArtistMixin)
    if release_group_providers:
        return release_group_providers[0].get_release_groups_by_artist(mbid)
    else:
        return None

@app.route('/album/<mbid>', methods=['GET'])
def get_release_group_info_route(mbid):
    output, validity = get_release_group_info(mbid)
    
    if isinstance(output, dict):
        output = add_cache_control_header(jsonify(output), validity)

    return output

@util.CACHE.memoize_variable_timeout()
def get_release_group_info(mbid):
    uuid_validation_response = validate_mbid(mbid)
    if uuid_validation_response:
        return (uuid_validation_response, 0)

    release_group_providers = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)
    release_providers = provider.get_providers_implementing(provider.ReleasesByReleaseGroupIdMixin)
    album_art_providers = provider.get_providers_implementing(provider.AlbumArtworkMixin)[::-1]
    track_providers = provider.get_providers_implementing(provider.TracksByReleaseGroupMixin)
    link_providers = provider.get_providers_implementing(provider.ReleaseGroupLinkMixin)

    if release_group_providers:
        release_group = release_group_providers[0].get_release_group_by_id(mbid)
    else:
        return (jsonify(error='No album provider available'), 500), 0

    if not release_group:
        return (jsonify(error='Album not found'), 404), 0

    if release_providers:
        release_group['Releases'] = release_providers[0].get_releases_by_rgid(mbid)

    else:
        # 500 error if we don't have a release provider since it's essential
        return(jsonify(error='No release provider available'), 500), 0

    if track_providers:
        tracks = track_providers[0].get_release_group_tracks(mbid)
        for release in release_group['Releases']:
            release['Tracks'] = [t for t in tracks if t['ReleaseId'] == release['Id']]

        artist_ids = track_providers[0].get_release_group_artist_ids(mbid)
        artists = [get_artist_info(gid)[0] for gid in set(artist_ids).union([release_group['ArtistId']])]
        release_group['Artists'] = artists
    else:
        # 500 error if we don't have a track provider since it's essential
        return (jsonify(error='No track provider available'), 500), 0

    if link_providers and not release_group.get('Links', None):
        release_group['Links'] = link_providers[0].get_release_group_links(mbid)
        
    validity = app.config['CACHE_TTL_GOOD']
        
    try:
        release_group['Overview'] = get_overview(release_group['Links'])
    except ProviderUnavailableException:
        release_group['Overview'] = ''
        validity = app.config['CACHE_TTL_BAD']

    if album_art_providers:
        try:
            release_group['Images'] = album_art_providers[0].get_album_images(
                release_group['Id'])
            if not release_group['Images'] and len(album_art_providers) > 1:
                release_group['Images'] = album_art_providers[1].get_album_images(release_group['Id'])
        except ProviderUnavailableException:
            release_group['Images'] = []
            validity = app.config['CACHE_TTL_BAD']
    else:
        release_group['Images'] = []

    return release_group, validity

@app.route('/chart/<name>/<type_>/<selection>')
def chart_route(name, type_, selection):
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
        return jsonify(charts[key](count, **chart_kwargs))


@app.route('/search/album')
def search_album():
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
        album_ids = search_providers[0].search_album_name(query, artist_name=artist_name, limit=limit)
        
        if basic:
            albums = album_ids
            validity = 1
        else:
            results = [get_release_group_info(item['Id']) for item in album_ids]
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
def search_artist():
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
                        search_providers[0].search_artist_name(query, limit=limit, albums=albums))

    if basic:
        artists = artist_ids
        validity = 1
    else:
        results = [get_artist_info(item['Id']) for item in artist_ids]
        artists = [result[0] for result in results]
        validity = min([result[1] for result in results] or [0])
    
    return add_cache_control_header(jsonify(artists), validity)

@app.route('/search/track')
def search_track():
    query = get_search_query()

    artist_name = request.args.get('artist', None)
    album_name = request.args.get('album', None)

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit

    search_providers = provider.get_providers_implementing(provider.TrackSearchMixin)
    if not search_providers:
        return jsonify(error='No search providers available'), 500

    tracks = search_providers[0].search_track(query, artist_name, album_name, limit)

    return jsonify(tracks)


@app.route('/search')
def search_route():
    type = request.args.get('type', None)

    if type == 'artist':
        return search_artist()
    elif type == 'album':
        return search_album()
    elif type == 'track':
        return search_track()
    else:
        error = jsonify(error='Type not provided') if type is None else jsonify(
            error='Unsupported search type {}'.format(type))
        return error, 400

@app.route('/invalidate')
@auth.login_required
@no_cache
def invalidate_cache():
    
    ## this is used as a prefix in various places to make sure
    ## we keep cache for different metadata versions separate
    base_url = app.config['CLOUDFLARE_URL_BASE'] + '/' +  app.config['APPLICATION_ROOT'].lstrip('/').rstrip('/')
    
    ## Use a cache key to make sure we don't trigger this in parallel
    invalidation_in_progress_key = base_url + 'CacheInvalidationInProgress'
    in_progress = util.CACHE.get(invalidation_in_progress_key)
    if in_progress:
        return jsonify('Invalidation already in progress'), 500
    
    try:
        util.CACHE.set(invalidation_in_progress_key, True, timeout=60*5)
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
            util.CACHE.delete_memoized(get_artist_info, artist)
            util.CACHE.delete_memoized(get_artist_albums, artist)

            key = '{url}/artist/{artist}'.format(url=base_url, artist=artist)
            invalidated.append(key)

        for album in albums:
            util.CACHE.delete_memoized(get_release_group_info, album)

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
    
if __name__ == '__main__':
    app.run(debug=True, port=config.get_config().HTTP_PORT)
