from flask import Flask, request, jsonify, send_file
from werkzeug.exceptions import HTTPException

from lidarrmetadata import config
from lidarrmetadata import models
from lidarrmetadata import provider

app = Flask(__name__)
app.config.from_object(config.CONFIG)

if not app.config['PRODUCTION']:
    # Run api doc server if not running in production
    from flasgger import Swagger

    swagger = Swagger(app)


@app.before_request
def before_request():
    models.database.connect()


@app.teardown_request
def teardown_request(response):
    if not models.database.is_closed():
        models.database.close()


@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(error=str(e)), code


@app.route('/artists/<mbid>/', methods=['GET'])
def get_artist_info(mbid):
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
    album_art_providers = provider.get_providers_implementing(
        provider.AlbumArtworkMixin)
    track_providers = provider.get_providers_implementing(
        provider.TracksByAlbumMixin)

    # TODO Figure out preferred providers
    if artist_providers:
        artist = artist_providers[0].get_artist_by_id(mbid)
    else:
        # 500 error if we don't have an artist provider since it's essential
        return jsonify(error='No artist provider available'), 500
    if album_providers:
        artist['Albums'] = album_providers[0].get_albums_by_artist(mbid)
    else:
        # 500 error if we don't have an album provider since it's essential
        return jsonify(error='No album provider available'), 500

    if track_providers:
        for album in artist['Albums']:
            album['Tracks'] = track_providers[0].get_album_tracks(album['Id'])
    else:
        # 500 error if we don't have a track provider since it's essential
        return jsonify(error='No track provider available'), 500

    if link_providers and not artist['Links']:
        artist['Links'] = link_providers[0].get_artist_links(mbid)

    if overview_providers:
        wikipedia_links = filter(lambda link: 'wikipedia' in link.values(),
                                 artist['Links'])
        if wikipedia_links:
            artist['Overview'] = overview_providers[0].get_artist_overview(
                wikipedia_links[0]['target'])

    if artist_art_providers:
        artist['Images'] = artist_art_providers[0].get_artist_images(mbid)

    if album_art_providers:
        for album in artist['Albums']:
            album['Images'] = album_art_providers[0].get_album_images(
                album['Id'])
    else:
        for album in artist['Albums']:
            album['Images'] = []

    return jsonify(artist)

@app.route('/search/album/')
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
    query = request.args.get('query', '')
    albums = provider.search_album(query)
    return jsonify(albums)


@app.route('/search/artist/', methods=['GET'])
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

    search_providers = provider.get_providers_implementing(
        provider.ArtistNameSearchMixin)
    overview_providers = provider.get_providers_implementing(
        provider.ArtistOverviewMixin)
    link_providers = provider.get_providers_implementing(
        provider.ArtistLinkMixin)

    if not search_providers:
        response = jsonify(error='No search providers available')
        response.status_code = 500
        return response

    # TODO Prefer certain providers?
    artists = search_providers[0].search_artist_name(query)

    for artist in artists:
        if link_providers:
            artist['Links'] = link_providers[0].get_artist_links(artist['Id'])

            # FIXME Repeated above
            wikipedia_links = filter(lambda link: 'wikipedia' in link.values(),
                                     artist['Links'])
            if wikipedia_links:
                try:
                    artist['Overview'] = overview_providers[0].get_artist_overview(
                        wikipedia_links[0]['target'])
                except ValueError:
                    pass

    return jsonify(artists)


@app.route('/search/')
def search_route():
    type = request.args.get('type', None)

    if type == 'artist':
        return search_artist()
    else:
        error = jsonify(error='Type not provided') if type is None else jsonify(
            error='Unsupported search type {}'.format(type))
        return error, 400


if __name__ == '__main__':
    app.run(port=5000)
