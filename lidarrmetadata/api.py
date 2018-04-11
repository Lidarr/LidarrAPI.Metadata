import uuid

from flask import Flask, request, jsonify
import raven.contrib.flask
from werkzeug.exceptions import HTTPException

import lidarrmetadata
from lidarrmetadata import chart
from lidarrmetadata import config
from lidarrmetadata import provider
from lidarrmetadata import util

app = Flask(__name__)
app.config.from_object(config.get_config())

sentry = raven.contrib.flask.Sentry(app, dsn=app.config['SENTRY_DSN'])

if app.config['USE_CACHE']:
    util.CACHE.config = config.get_config().CACHE_CONFIG
    util.CACHE.init_app(app)

if not app.config['PRODUCTION']:
    # Run api doc server if not running in production
    from flasgger import Swagger

    swagger = Swagger(app)

# Set up providers
for provider_name, (args, kwargs) in app.config['PROVIDERS'].items():
    provider.PROVIDER_CLASSES[provider_name](*args, **kwargs)

@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(error=str(e)), code


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

    if mbid in config.get_config().BLACKLISTED_ARTISTS:
        return jsonify(error='Blacklisted artist'), 403


@app.route('/')
def default_route():
    """
    Default route with API information
    :return:
    """
    info = {'version': lidarrmetadata.__version__}
    return jsonify(info)


@app.route('/artist/<mbid>', methods=['GET'])
@util.CACHE.cached(key_prefix=lambda: request.full_path)
def get_artist_info(mbid):
    uuid_validation_response = validate_mbid(mbid)
    if uuid_validation_response:
        return uuid_validation_response

    # TODO A lot of repetitive code here. See if we can refactor
    artist_providers = provider.get_providers_implementing(
        provider.ArtistByIdMixin)
    link_providers = provider.get_providers_implementing(
        provider.ArtistLinkMixin)
    overview_providers = provider.get_providers_implementing(
        provider.ArtistOverviewMixin)
    artist_art_providers = provider.get_providers_implementing(
        provider.ArtistArtworkMixin)
    album_providers = provider.get_providers_implementing(
        provider.AlbumByArtistMixin)

    # TODO Figure out preferred providers
    if artist_providers:
        artist = artist_providers[0].get_artist_by_id(mbid)
        if not artist:
            return jsonify(error='Artist not found'), 404
    else:
        # 500 error if we don't have an artist provider since it's essential
        return jsonify(error='No artist provider available'), 500
    if album_providers:
        artist['Albums'] = album_providers[0].get_albums_by_artist(mbid)
    else:
        # 500 error if we don't have an album provider since it's essential
        return jsonify(error='No album provider available'), 500

    if link_providers and not artist.get('Links', None):
        artist['Links'] = link_providers[0].get_artist_links(mbid)

    if overview_providers:
        wikipedia_links = filter(
            lambda link: 'wikipedia' in link.get('target', ''),
            artist['Links'])
        if wikipedia_links:
            artist['Overview'] = overview_providers[0].get_artist_overview(
                wikipedia_links[0]['target'])

    if 'Overview' not in artist:
        artist['Overview'] = ''

    if artist_art_providers:
        artist['Images'] = artist_art_providers[0].get_artist_images(mbid)
    else:
        artist['Images'] = []

    # Filter album types and statuses
    # TODO Should types be part of album query?
    primary_types = request.args.get('primTypes', None)
    if primary_types:
        primary_types = primary_types.split('|')
        artist['Albums'] = filter(lambda album: album.get('Type') in primary_types, artist['Albums'])
    secondary_types = request.args.get('secTypes', None)
    if secondary_types:
        secondary_types = set(secondary_types.split('|'))
        artist['Albums'] = filter(lambda album: (album['SecondaryTypes'] == [] and 'Studio' in secondary_types)
                                                or secondary_types.intersection(album.get('SecondaryTypes')),
                                  artist['Albums'])
    release_statuses = request.args.get('releaseStatuses', None)
    if release_statuses:
        release_statuses = set(release_statuses.split('|'))
        artist['Albums'] = filter(lambda album: release_statuses.intersection(album.get('ReleaseStatuses')),
                                  artist['Albums'])

    return jsonify(artist)


@app.route('/album/<mbid>', methods=['GET'])
@util.CACHE.cached(key_prefix=lambda: request.full_path)
def get_album_info(mbid):
    uuid_validation_response = validate_mbid(mbid)
    if uuid_validation_response:
        return uuid_validation_response

    # Determine which release we want
    release = request.args.get('release', None)

    album_providers = provider.get_providers_implementing(provider.AlbumByIdMixin)
    album_art_providers = provider.get_providers_implementing(
        provider.AlbumArtworkMixin)
    media_providers = provider.get_providers_implementing(provider.MediaByAlbumMixin)
    track_providers = provider.get_providers_implementing(
        provider.TracksByAlbumMixin)

    if album_providers:
        album = album_providers[0].get_album_by_id(mbid, release)
    else:
        return jsonify(error='No album provider available'), 500

    if not album:
        return jsonify(error='Album not found'), 404

    if track_providers:
        if 'Releases' in album and album['Releases'][0]:
            album['Media'] = media_providers[0].get_album_media(album['SelectedRelease'])
            album['Tracks'] = track_providers[0].get_album_tracks(album['SelectedRelease'])
    else:
        # 500 error if we don't have a track provider since it's essential
        return jsonify(error='No track provider available'), 500

    if album_art_providers:
        album['Images'] = album_art_providers[0].get_album_images(
            album['Id'], cache_only=True)
    else:
        album['Images'] = []

    return jsonify(album)


@app.route('/chart/<name>/<type_>/<selection>')
@util.CACHE.cached(key_prefix=lambda: request.full_path)
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
        ('apple-music', 'album', 'top'): chart.get_apple_music_chart,
        ('billboard', 'album', 'top'): chart.get_billboard_200_albums_chart,
        ('billboard', 'artist', 'top'): chart.get_billboard_100_artists_chart,
        ('itunes', 'album', 'top'): chart.get_itunes_chart,
        ('lastfm', 'album', 'top'): chart.get_lastfm_album_chart,
        ('lastfm', 'artist', 'top'): chart.get_lastfm_artist_chart
    }

    if key not in charts.keys():
        return jsonify(error='Chart {}/{}/{} not found'.format(*key)), 404
    else:
        return jsonify(charts[key](count, **chart_kwargs))


@app.route('/search/album')
@util.CACHE.cached(key_prefix=lambda: request.full_path)
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
    query = request.args.get('query')
    if not query:
        return jsonify(error="No query provided"), 400
    query = query.strip()

    artist_name = request.args.get('artist', '')

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit

    search_providers = provider.get_providers_implementing(provider.AlbumNameSearchMixin)
    album_art_providers = provider.get_providers_implementing(provider.AlbumArtworkMixin)

    if search_providers:
        albums = search_providers[0].search_album_name(query, artist_name=artist_name, limit=limit)
    else:
        response = jsonify(error="No album search providers")
        response.status_code = 500
        return response

    if album_art_providers:
        for album in albums:
            album['Images'] = album_art_providers[0].get_album_images(album['Id'])

    return jsonify(albums)


@app.route('/search/artist', methods=['GET'])
@util.CACHE.cached(key_prefix=lambda: request.full_path)
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
    query = request.args.get('query')
    if not query:
        return jsonify(error='No query provided'), 400
    query = query.strip()

    limit = request.args.get('limit', default=10, type=int)
    limit = None if limit < 1 else limit

    search_providers = provider.get_providers_implementing(
        provider.ArtistNameSearchMixin)
    artist_providers = provider.get_providers_implementing(
        provider.ArtistByIdMixin)
    overview_providers = provider.get_providers_implementing(
        provider.ArtistOverviewMixin)
    link_providers = provider.get_providers_implementing(
        provider.ArtistLinkMixin)
    artist_art_providers = provider.get_providers_implementing(
        provider.ArtistArtworkMixin)

    if not search_providers:
        response = jsonify(error='No search providers available')
        response.status_code = 500
        return response

    # TODO Prefer certain providers?
    artists = search_providers[0].search_artist_name(query, limit=limit)

    for artist in artists:
        artist.update(artist_providers[0].get_artist_by_id(artist['Id']))
        if link_providers:
            artist['Links'] = link_providers[0].get_artist_links(artist['Id'])

            # FIXME Repeated above
            wikipedia_links = filter(
                lambda link: 'wikipedia' in link.get('target', ''),
                artist['Links'])
            if wikipedia_links:
                try:
                    artist['Overview'] = overview_providers[
                        0].get_artist_overview(
                        wikipedia_links[0]['target'])
                except ValueError:
                    pass

        if 'Overview' not in artist:
            artist['Overview'] = ''

        if artist_art_providers and request.args.get('images', 'True').lower() == 'true':
            artist['Images'] = artist_art_providers[0].get_artist_images(artist['Id'])
        else:
            artist['Images'] = []

    return jsonify(artists)


@app.route('/search')
def search_route():
    type = request.args.get('type', None)

    if type == 'artist':
        return search_artist()
    elif type == 'album':
        return search_album()
    else:
        error = jsonify(error='Type not provided') if type is None else jsonify(
            error='Unsupported search type {}'.format(type))
        return error, 400


if __name__ == '__main__':
    app.run(port=config.get_config().HTTP_PORT)
