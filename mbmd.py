"""
Simple metadata server using only musicbrainz
"""

import collections
import logging
import logging.handlers


import dateutil.parser
import flask
import musicbrainzngs
import psycopg2
import requests

try:
    from functools import lru_cache
except ImportError:
    from functools32 import lru_cache

# Config stuff
PORT = 5000
MUSICBRAINZ_HOST = 'musicbrainz.org'
AGENT = ('lidarr', '0.0.0')
MODE = 'MB'  # DB for direct DB connection, MB for musicbrainz API
DB_HOST = ''
DB_PORT = 5432
DB_NAME = 'musicbrainz_db'
DB_USER = 'abc'
DB_PASSWORD = 'abc'

if MODE == 'DB':
    db_connection = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    db_cursor = db_connection.cursor()
else:
    db_connection = None
    db_cursor = None


def query_from_file(filename, *args, **kwargs):
    """
    Executes query from sql file
    :param filename: Filename of sql query
    :param args: Positional args to pass to cursor.execute
    :param kwargs: Keyword args to pass to cursor.execute
    :return: List of dict with column: value results
    """
    with open(filename, 'r') as sql:
        return map_query(sql.read(), *args, **kwargs)


def map_query(*args, **kwargs):
    """
    Maps a SQL query to a list of dicts of column name: value
    :param args: Args to pass to cursor.execute
    :param kwargs: Keyword args to pass to cursor.execute
    :return: List of dict with column: value
    """
    db_cursor.execute(*args, **kwargs)
    columns = collections.OrderedDict((column.name, None) for column in db_cursor.description)
    results = db_cursor.fetchall()
    return [{column: result[i] for i, column in enumerate(columns.keys())} for result in results]


class DiscordHandler(logging.handlers.HTTPHandler):
    """
    Logs to discord server
    """
    DISCORD_URL = ''

    def __init__(self):
        super(DiscordHandler, self).__init__(None, None)

    def emit(self, record):
        """
        Sends log message
        :param record: Record of error
        :return:
        """
        requests.post(self.DISCORD_URL, data=self.mapLogRecord(record))

    def mapLogRecord(self, record):
        """
        Maps log record to request dict
        :param record: Record of error
        :return: Representation of data to send to discord
        """
        return {'content': '```\n{}\n```'.format(record.exc_text)}


musicbrainzngs.set_hostname(MUSICBRAINZ_HOST)
musicbrainzngs.set_useragent(*AGENT)

app = flask.Flask(__name__)
discord_handler = DiscordHandler()
discord_handler.setLevel(logging.ERROR)


def _mb_escaped_query(query):
    """
    Escapes a query for musicbrainz
    :param query: Query to escape
    :return: Escapes special characters with \
    """
    escaped_query = ''
    for c in query:
        if not c.isalnum() and c not in ['-', '.', '-', '/']:
            escaped_query += '\\'

        escaped_query += c

    return escaped_query


def _mb_album_type(mb_release_group):
    """
    Gets album type from musicbrainz release group
    :param mb_release_group: Release group from musicbrainz response
    :return: Album type as string
    """
    return mb_release_group.get('secondary-type-list',
                                [mb_release_group.get('primary-type',
                                                      'Unknown')])[0]


def _parse_mb_album(mb_release_group):
    """
    Parses album (release) response from musicbrainz
    :param mb_release: Response from muscbrainz
    :return: Dict of the format wanted by api
    """
    mb_release = musicbrainzngs.get_release_by_id(mb_release_group['release-list'][0]['id'],
                                                  includes=['recordings'])['release']
    artists = [{'Id': artist['artist']['id'], 'ArtistName': artist['artist']['name']}
               for artist in mb_release_group['artist-credit'] if isinstance(artist, dict)]

    try:
        mb_image = musicbrainzngs.get_release_group_image_list(mb_release_group['id'])
    except musicbrainzngs.ResponseError:
        mb_image = {'images': []}

    return {'Id': mb_release_group['id'],
            'Title': mb_release_group['title'],
            'Artists': artists,
            'ReleaseDate': dateutil.parser.parse(mb_release['date']) if 'date' in mb_release else '',
            'Genres': [],
            'Overview': '',
            'Label': '',
            'Images': list(filter(None, [_parse_mb_image(image) for image in
                                         mb_image['images']])),
            'Type': _mb_album_type(mb_release_group),
            'Tracks': [_parse_mb_track(track) for track in
                       mb_release['medium-list'][0]['track-list']]}


def _parse_mb_artist(mb_artist):
    """
    Parses artist response from musicbrainz
    :param mb_artist: Resposne from muscbrainz
    :return: Dict of the format wanted by API
    """
    return {'Id': mb_artist['id'],
            'ArtistName': mb_artist['name'],
            'Overview': mb_artist.get('disambiguation', ''),
            'Images': [],
            'Genres': ''}


def _parse_mb_track(mb_track):
    """
    Parses track/recording response from musicbrainz
    :param mb_track: Recording result from musicbrainz
    :return: Dict of format wanted by api
    """
    return {'Id': mb_track['id'],
            'TrackName': mb_track['recording']['title'],
            'TrackNumber': mb_track['position'],
            'DurationMs': int(mb_track.get('length', -1))}


def _parse_mb_image(mb_image):
    """
    Parses image response from musicbrainz cover art archive
    :param mb_image: Recording result from musicbrainz cover art archive
    :return: Dict of format wanted by api
    """
    if mb_image['front']:
        return {'CoverType': 'Cover',
                'Url': mb_image['image']}
    else:
        return None


def _parse_db_artist(db_artist):
    """
    Parses a db artist from SQL query
    :param db_artist: SQL query return
    :return: Parsed artist JSON
    """
    print(db_artist['gid'])
    return {
        'Id': db_artist['gid'],
        'ArtistName': db_artist['name'],
        'Overview': '',
        'Genres': '',
        'Images': [],
        'Albums': []
    }


def _parse_db_album(db_album):
    """
    Parses a db artist from SQL query
    :param db_album: SQL query return
    :return: Parsed album JSON
    """
    print(db_album.keys())
    return {
        'Id': db_album['gid'],
        'Title': db_album['name'],
        'Artists': [],
        'ReleaseDate': db_album.get('last_updated', ''),
        'Genres': [],
        'Overview': '',
        'Label': '',
        'Images': [],
        'Type': '',
        'Tracks': []
    }


def _parse_db_track(db_track):
    """
    Parses a db track from SQL query
    :param db_track: SQL query return
    :return: Parsed track JSON
    """
    return {
        'Id': db_track['gid'],
        'TrackName': db_track['name'],
        'TrackNumber': db_track['position'],
        'Duration': db_track['length']
    }


@lru_cache()
def _album_search(query, limit=100, offset=0, **kwargs):
    """
    Searches musicbrainz for album query
    :param query: Search query
    :param limit: Limit of results for a single page
    :param offset: Search offset. Use this if searching multiple times
    :param kwargs: Keyword args passed as fields to muscbrainz search
    :return: Dict of album object
    """
    if MODE == 'MB':
        mb_response = \
            musicbrainzngs.search_release_groups(_mb_escaped_query(query),
                                                 limit=limit,
                                                 offset=offset,
                                                 **kwargs)[
                'release-group-list']

        return [_parse_mb_album(mb_album) for mb_album in mb_response]


@lru_cache()
def _artist_search(query):
    """
    Searches musicbrainz for artist query
    :param query: Search query
    :return: Dict of artist object
    """
    if MODE == 'MB':
        mb_response = musicbrainzngs.search_artists(_mb_escaped_query(query))[
            'artist-list']
        return [_parse_mb_artist(mb_artist) for mb_artist in mb_response]
    elif MODE == 'DB':
        artists = query_from_file('./sql/artist_search_name.sql', [query])
        print(artists)
        return [_parse_db_artist(artist) for artist in artists]


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
    if MODE == 'MB':
        mb_response = musicbrainzngs.get_artist_by_id(mbid)['artist']
        artist = _parse_mb_artist(mb_response)
        i = 0
        limit = 100
        artist['Albums'] = []

        while len(artist['Albums']) == i * limit:
            artist['Albums'].extend(_album_search('',
                                                  limit=limit,
                                                  offset=i * limit,
                                                  arid=artist['Id']))
            i += 1

    elif MODE == 'DB':
        artist = query_from_file('./sql/artist_search_mbid.sql', [mbid])[0]
        artist = _parse_db_artist(artist)
        albums = query_from_file('./sql/album_search_artist_mbid.sql', [mbid])
        artist['Albums'] = [_parse_db_album(album) for album in albums]

        for album in artist['Albums']:
            tracks = query_from_file('./sql/track_album_mbid.sql', (album['Id'],))
            album['Tracks'] = [_parse_db_track(track) for track in tracks]
    else:
        raise ValueError('Invalid mode')

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
    app.run(debug=False, port=PORT)
