"""
Simple metadata server using only musicbrainz
"""

import dateutil.parser
import flask
import musicbrainzngs

# Config stuff
PORT = 5000
MUSICBRAINZ_HOST = 'musicbrainz.org'
AGENT = ('lidarr', '0.0.0')

musicbrainzngs.set_hostname(MUSICBRAINZ_HOST)
musicbrainzngs.set_useragent(*AGENT)

app = flask.Flask(__name__)


def _parse_mb_album(mb_release_group):
    """
    Parses album (release) response from musicbrainz
    :param mb_release: Response from muscbrainz
    :return: Dict of the format wanted by api
    """
    mb_release = musicbrainzngs.get_release_by_id(mb_release_group['release-list'][0]['id'])['release']
    artists = [{'Id': artist['artist']['id'], 'ArtistName': artist['artist']['name']}
               for artist in mb_release_group['artist-credit'] if isinstance(artist, dict)]

    return {'Id': mb_release_group['id'],
            'Title': mb_release_group['title'],
            'Artists': artists,
            'ReleaseDate': dateutil.parser.parse(mb_release['date']) if 'date' in mb_release else '',
            'Genres': [],
            'Overview': '',
            'Label': '',
            'Images': [],
            'Type': mb_release_group.get('type', 'Unknown'),
            'Tracks': []}


def _parse_mb_artist(mb_artist):
    """
    Parses artist response from musicbrainz
    :param mb_artist: Resposne from muscbrainz
    :return: Dict of the format wanted by API
    """
    return {'Id': mb_artist['id'],
            'ArtistName': mb_artist['name'],
            'Overview': '',
            'Images': [],
            'Genres': ''}


def _album_search(query, **kwargs):
    """
    Searches musicbrainz for album query
    :param query: Search query
    :param kwargs: Keyword args passed as fields to muscbrainz search
    :return: Dict of album object
    """
    mb_response = musicbrainzngs.search_release_groups(query, **kwargs)['release-group-list']
    return [_parse_mb_album(mb_album) for mb_album in mb_response]


def _artist_search(query):
    """
    Searches musicbrainz for artist query
    :param query: Search query
    :return: Dict of artist object
    """
    mb_response = musicbrainzngs.search_artists(query)['artist-list']
    return [_parse_mb_artist(mb_artist) for mb_artist in mb_response]


@app.route('/albums/<mbid>/')
def album_route(mbid):
    """
    Gets album by mbid
    :param mbid: Musicbrainz ID of album
    :return:
    """
    mb_response = musicbrainzngs.get_release_group_by_id(mbid)
    return _parse_mb_album(mb_response)


@app.route('/artists/<mbid>/')
def artist_route(mbid):
    """
    Gets artist by mbid
    :param mbid: Musicbrainz ID of artist
    :return:
    """
    mb_response = musicbrainzngs.get_artist_by_id(mbid)['artist']
    artist = _parse_mb_artist(mb_response)
    queried_albums = _album_search('', artistname=artist['ArtistName'])
    albums = []
    for album in queried_albums:
        for album_artist in album['Artists']:
            if artist['ArtistName'] == album_artist['ArtistName']:
                albums.append(album)
                break

    artist['Albums'] = albums
    return flask.jsonify(artist)


@app.route('/search/album')
def search_album_route():
    """
    Searches album with query parameter
    :return:
    """
    query = flask.request.args.get('query', None)

    if not query:
        response = flask.jsonify(error='Query parameter required')
        response.status_code = 400
        return response

    return flask.jsonify(_album_search(query))


@app.route('/search/artist')
def search_artist_route():
    """
    Searches artist with query parameter
    :return:
    """
    query = flask.request.args.get('query', None)

    if not query:
        response = flask.jsonify(error='Query parameter required')
        response.status_code = 400
        return response

    return flask.jsonify(_artist_search(query))


@app.route('/search/')
def search_route():
    """
    Search route to redirect to album/artist search
    :return:
    """
    search_type = flask.request.args.get('type', None)
    if search_type == 'album':
        return search_album_route()
    elif search_type == 'artist':
        return search_artist_route()
    else:
        response = flask.jsonify(error='Search type required')
        response.status_code = 400
        return response


if __name__ == '__main__':
    app.run(debug=True, port=PORT)
