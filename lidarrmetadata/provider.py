import abc
import collections
import contextlib
import datetime
import imp
import logging
import pkg_resources
import re
import urllib

import dateutil.parser
import six

import psycopg2
import pylast
import requests
import wikipedia

import lidarrmetadata
from lidarrmetadata import util

logger = logging.getLogger(__name__)


def get_providers_implementing(cls):
    """
    Gets list of providers implementing mixin
    :param cls: Mixin class for implementation
    :return: List of providers inheriting from cls
    """
    return [p for p in Provider.providers if isinstance(p, cls)]


class MixinBase(six.with_metaclass(abc.ABCMeta, object)):
    pass


class ArtistByIdMixin(MixinBase):
    """
    Gets artist by id
    """

    @abc.abstractmethod
    def get_artist_by_id(self, artist_id):
        """
        Gets artist by id
        :param artist_id: ID of artist
        :return: Artist matching ID or None
        """
        pass


class ArtistNameSearchMixin(MixinBase):
    """
    Searches for artist with artist name
    """

    @abc.abstractmethod
    def search_artist_name(self, name, limit=None):
        """
        Searches for artist with name
        :param name: Name to search for
        :param limit: Limit of number of results to return. Defaults to None, indicating no limit
        :return: List of possible matches
        """
        pass


class AlbumByArtistMixin(MixinBase):
    """
    Gets albums for artist
    """

    @abc.abstractmethod
    def get_albums_by_artist(self, artist_id):
        """
        Gets albums by artist by ID
        :param artist_id: ID of artist
        :return: List of albums by artist
        """
        pass


class AlbumByIdMixin(MixinBase):
    """
    Gets album by ID
    """

    @abc.abstractmethod
    def get_album_by_id(self, rgid, rid=None):
        """
        Gets album by ID
        :param rgid: Release group ID
        :param rid: Release ID of individual release. Defaults to None, in which case the first result is chosen
        :return: Album corresponding to rgid or rid
        """
        pass


class MediaByAlbumMixin(MixinBase):
    """
    Gets medium for album
    """

    @abc.abstractmethod
    def get_album_media(self, album_id):
        """
        Gets media for album
        :param album_id: ID of album
        :return: List of media
        """


class TracksByAlbumMixin(MixinBase):
    """
    Gets tracks by album is
    """

    @abc.abstractmethod
    def get_album_tracks(self, album_id):
        """
        Gets tracks in album
        :param album_id: ID of album
        :return: List of tracks in album
        """
        pass


class ArtistOverviewMixin(MixinBase):
    """
    Gets overview for artist
    """

    @abc.abstractmethod
    def get_artist_overview(self, artist_id):
        pass


class ArtistArtworkMixin(MixinBase):
    """
    Gets art for artist
    """

    @abc.abstractmethod
    def get_artist_images(self, artist_id):
        """
        Gets images for artist with ID
        :param artist_id: ID of artist
        :return: List of results
        """
        pass


class AlbumArtworkMixin(MixinBase):
    """
    Gets art for album
    """

    @abc.abstractmethod
    def get_album_images(self, album_id):
        """
        Gets images for album with ID
        :param album_id: ID of album
        :return: List of results
        """
        pass


class ArtistLinkMixin(MixinBase):
    """
    Gets links for artist
    """

    @abc.abstractmethod
    def get_artist_links(self, artist_id):
        """
        Gets links for artist with id
        :param artist_id: ID of artist
        :return: List of links
        """
        pass


class AlbumNameSearchMixin(MixinBase):
    """
    Searches for album by name
    """

    @abc.abstractmethod
    def search_album_name(self, name, limit=None, artist_name=''):
        """
        Searches for album with name
        :param name: Name of album
        :param limit: Limit of number of results to return. Defaults to None, indicating no limit
        :param artist_name: Artist name restriction
        :return: List of albums
        """
        pass


class Provider(object):
    """
    Provider base class
    """

    # List of provider instances
    providers = []

    def __init__(self):
        self.providers.append(self)


class FanArtTvProvider(Provider, AlbumArtworkMixin, ArtistArtworkMixin):
    def __init__(self,
                 api_key,
                 base_url='webservice.fanart.tv/v3/music/',
                 use_https=True):
        """
        Class initialization

        :param api_key: fanart.tv API key
        :param base_url: Base URL of API. Defaults to
                         webservice.fanart.tv/v3/music
        :param use_https: Whether or not to use https. Defaults to True.
        """
        super(FanArtTvProvider, self).__init__()

        self.cache = util.Cache()
        self._api_key = api_key
        self._base_url = base_url
        self.use_https = use_https

    def get_artist_images(self, artist_id):
        results = self.cache.get(artist_id)

        if not results:
            results = self.get_by_mbid(artist_id)
            self.cache.put(artist_id, results)
            for id, album_result in results.get('albums', {}).items():
                self.cache.put(id, album_result)

        return self.parse_artist_images(results)

    def get_album_images(self, album_id, cache_only=False):
        results = self.cache.get(album_id, {})

        if not results and not cache_only:
            results = self.get_by_mbid(album_id)
            results = results.get('albums', results).get(album_id, results)
            self.cache.put(album_id, results)

        return self.parse_album_images(results)

    def get_by_mbid(self, mbid):
        # TODO Cache results
        """
        Gets the fanart.tv response for resource with Musicbrainz id mbid
        :param mbid: Musicbrainz ID
        :return: fanart.tv response for mbid
        """
        url = self.build_url(mbid)
        return requests.get(url).json()

    def build_url(self, mbid):
        """
        Builds query url
        :param mbid: Musicbrainz ID of resource
        :return: URL to query
        """
        scheme = 'https://' if self.use_https else 'http://'
        url = scheme + self._base_url
        if url[-1] != '/':
            url += '/'
        url += mbid
        url += '/?api_key={api_key}'.format(api_key=self._api_key)
        return url

    @staticmethod
    def parse_album_images(response):
        """
        Parses album images to our expected format
        :param response: API response
        :return: List of images in our expected format
        """
        images = {'Cover': util.first_key_item(response, 'albumcover'),
                  'Disc': util.first_key_item(response, 'cdart')}
        return [{'CoverType': key, 'Url': value['url'].replace('https', 'http')}
                for key, value in images.items() if value]

    @staticmethod
    def parse_artist_images(response):
        """
        Parses artist images to our expected format
        :param response: API response
        :return: List of images in our expected format
        """
        images = {'Banner': util.first_key_item(response, 'musicbanner'),
                  'Fanart': util.first_key_item(response, 'artistbackground'),
                  'Logo': util.first_key_item(response, 'hdmusiclogo'),
                  'Poster': util.first_key_item(response, 'artistthumb')}
        return [{'CoverType': key, 'Url': value['url'].replace('https', 'http')}
                for key, value in images.items() if value]


class LastFmProvider(Provider,
                     ArtistNameSearchMixin,
                     ArtistOverviewMixin,
                     AlbumArtworkMixin):
    """
    Provider that uses LastFM API
    """

    def __init__(self, api_key, api_secret):
        """
        Class initialization
        :param api_key: LastFM API key
        :param api_secret: LastFM API secret
        """
        super(LastFmProvider, self).__init__()

        self._client = pylast.LastFMNetwork(api_key=api_key,
                                            api_secret=api_secret)

    def search_artist(self, name):
        results = self._client.search_for_artist(name).get_next_page()
        return [{'Id': result.get_mbid(),
                 'Overview': result.get_bio_summary()}
                for result in results]


class MusicbrainzApiProvider(Provider,
                             ArtistByIdMixin,
                             ArtistLinkMixin,
                             ArtistNameSearchMixin,
                             AlbumByArtistMixin,
                             TracksByAlbumMixin):
    """
     Provider that utilizes the musicbrainz API
    """

    def __init__(self, host='musicbrainz.org'):
        super(MusicbrainzApiProvider, self).__init__()

        # Set up client. Since musicbrainzngs has its functions operate on a
        # module namespace, we need to have a module import for each instance
        self.client = imp.load_module('self.client',
                                      *imp.find_module('musicbrainzngs'))
        self.client.set_rate_limit(False)
        self.client.set_useragent('lidarr-metadata', lidarrmetadata.__version__)
        self.client.set_hostname(host)

    def get_artist_by_id(self, artist_id):
        mb_response = self.client.get_artist_by_id(artist_id,
                                                   includes=['url-rels'])
        return self._parse_mb_artist(mb_response['artist'])

    def get_artist_links(self, artist_id):
        return self.get_artist_by_id(artist_id)['Links']

    def get_album_tracks(self, album_id):
        return self.search_album('', rgid=album_id)[0]['Tracks']

    def get_albums_by_artist(self, artist_id):
        return self.search_album('', arid=artist_id)

    def search_artist_name(self, name, limit=None):
        return self.search_artist(name)

    def _search_artist(self, query, **kwargs):
        """
        Searches for an artist
        :param query: Artist query
        :param kwargs: Keyword arguments to send to musicbrainzngs search
        :return:
        """
        query = self._mb_escaped_query(query)
        mb_response = self.client.search_artists(query, **kwargs)['artist-list']
        return [{'Id': artist['id'],
                 'ArtistName': artist['name']}
                for artist in mb_response]

    def artist_by_id(self, mbid, **kwargs):
        """
        Gets artist by ID
        :param mbid: Musicbrainz ID of artist
        :param kwargs: Keyword args to supply to musicbrainz call
        :return: Dictionary of result
        """
        mb_response = self.client.get_artist_by_id(mbid, **kwargs)['artist']
        artist = self._parse_mb_artist(mb_response)
        i = 0
        limit = 100
        artist['Albums'] = []

        while len(artist['Albums']) == i * limit:
            artist['Albums'].extend(self.search_album('',
                                                      limit=limit,
                                                      offset=i * limit,
                                                      arid=artist['Id']))
            i += 1

        return artist

    def search_artist(self, query, **kwargs):
        """
        Searches musicbrainz for artist
        :param query: Artist query
        :param kwargs: Keyword args to supply to search call
        :return: List of dictionaries of result
        """
        query = self._mb_escaped_query(query)
        mb_response = self.client.search_artists(query, **kwargs)['artist-list']
        return [self._parse_mb_artist(artist) for artist in mb_response]

    def search_album(self, query, limit=100, offset=0, **kwargs):
        """
        Searches musicbrainz for album query
        :param query: Search query
        :param limit: Limit of results for a single page
        :param offset: Search offset. Use this if searching multiple times
        :param kwargs: Keyword args passed as fields to muscbrainz search
        :return: Dict of album object
        """
        mb_response = \
            self.client.search_release_groups(self._mb_escaped_query(query),
                                              limit=limit,
                                              offset=offset,
                                              **kwargs)['release-group-list']

        return [self._parse_mb_album(mb_album) for mb_album in mb_response]

    @staticmethod
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

    @staticmethod
    def _mb_album_type(mb_release_group):
        """
        Gets album type from musicbrainz release group
        :param mb_release_group: Release group from musicbrainz response
        :return: Album type as string
        """
        return mb_release_group.get('secondary-type-list',
                                    [mb_release_group.get('primary-type',
                                                          'Unknown')])[0]

    def _parse_mb_album(self, mb_release_group):
        """
        Parses album (release) response from musicbrainz
        :param mb_release_group: Response from muscbrainz
        :return: Dict of the format wanted by api
        """
        try:
            mb_release = \
                self.client.get_release_by_id(
                    mb_release_group['release-list'][0]['id'],
                    includes=['recordings'])['release']
        except self.client.ResponseError:
            mb_release = {}

        artists = [
            {'Id': artist['artist']['id'],
             'ArtistName': artist['artist']['name']}
            for artist in mb_release_group['artist-credit'] if
            isinstance(artist, dict)]

        return {'Id': mb_release_group['id'],
                'Title': mb_release_group['title'],
                'Artists': artists,
                'ReleaseDate': dateutil.parser.parse(
                    mb_release['date']) if 'date' in mb_release else '',
                'Genres': [],
                'Overview': '',
                'Label': '',
                'Type': self._mb_album_type(mb_release_group),
                'Tracks': [self._parse_mb_track(track) for track in
                           mb_release.get('medium-list',
                                          [{}])[0].get('track-list', [])]}

    @staticmethod
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
                'Genres': '',
                'Links': mb_artist.get('url-relation-list', [])}

    @staticmethod
    def _parse_mb_track(mb_track):
        """
        Parses track/recording response from musicbrainz
        :param mb_track: Recording result from musicbrainz
        :return: Dict of format wanted by api
        """
        return {'Id': mb_track['id'],
                'TrackName': mb_track['recording']['title'],
                'TrackNumber': mb_track['position'],
                'DurationMs': int(mb_track.get('length', 0)) or None}


class MusicbrainzDbProvider(Provider,
                            ArtistByIdMixin,
                            ArtistLinkMixin,
                            ArtistNameSearchMixin,
                            AlbumByArtistMixin,
                            AlbumByIdMixin,
                            AlbumNameSearchMixin,
                            MediaByAlbumMixin,
                            TracksByAlbumMixin):
    """
    Provider for directly querying musicbrainz database
    """

    TRANSLATION_TABLE = util.BidirectionalDictionary({
        u'\u2026': '...',  # HORIZONTAL ELLIPSIS (U+2026)
        u'\u0027': "'",  # APOSTROPHE (U+0027)
        u'\u2010': '-',  # HYPHEN (U+2010)
        u'\u8243': u'\u2033',  # DOUBLE PRIME (U+8243)
    })

    def __init__(self,
                 db_host='localhost',
                 db_port=5432,
                 db_name='musicbrainz_db',
                 db_user='abc',
                 db_password='abc'):
        """
        Class initialization

        Note that these defaults are reasonable if the linuxserverio/musicbrainz
        docker image is running locally with port 5432 exposed.

        :param db_host: Host of musicbrainz db. Defaults to localhost
        :param db_port: Port of musicbrainz db. Defaults to 5432
        :param db_name: Name of musicbrainz db. Defaults to musicbrainz_db
        :param db_user: User for musicbrainz db. Defaults to abc
        :param db_password: Password for musicbrainz db. Defaults to abc
        """
        super(MusicbrainzDbProvider, self).__init__()

        self._db_host = db_host
        self._db_port = db_port
        self._db_name = db_name
        self._db_user = db_user
        self._db_password = db_password

    def get_artist_by_id(self, artist_id):
        results = self.query_from_file('../sql/artist_search_mbid.sql', [artist_id])
        if results:
            results = results[0]
        else:
            return {}
        return {'Id': results['gid'],
                'ArtistName': results['name'],
                'SortName': results['sort_name'],
                'Status': 'ended' if results['ended'] else 'active',
                'Type': results['type'] or 'Artist',
                'Disambiguation': results['comment']}

    def search_artist_name(self, name, limit=None):
        name = self.mb_encode(name)

        filename = pkg_resources.resource_filename('lidarrmetadata.sql', 'artist_search_name.sql')
        with open(filename, 'r') as infile:
            query = infile.read()

        if limit:
            with self._cursor() as cursor:
                if limit:
                    query += cursor.mogrify(' LIMIT %s', [limit])

        results = self.map_query(query, [name])

        return [{'Id': result['gid'],
                 'ArtistName': result['name'],
                 'Type': result['type'] or 'Artist',
                 'Disambiguation': result['comment']}
                for result in results]

    def search_album_name(self, name, limit=None, artist_name=''):
        name = self.mb_encode(name)

        filename = pkg_resources.resource_filename('lidarrmetadata.sql', 'album_search_name.sql')
        with open(filename, 'r') as infile:
            query = infile.read()

        if artist_name or limit:
            with self._cursor() as cursor:

                if artist_name:
                    query += cursor.mogrify(' AND UPPER(artist.name) LIKE UPPER(%s)', [artist_name])

                if limit:
                    query += cursor.mogrify(' LIMIT %s', [limit])

        results = self.map_query(query, [name])

        return [{'Id': result['gid'],
                 'Disambiguation': result['comment'],
                 'Title': result['album'],
                 'Type': result['primary_type'],
                 'SecondaryTypes': result['secondary_types'],
                 'ReleaseDate': datetime.datetime(result['year'] or 1,
                                                  result['month'] or 1,
                                                  result['day'] or 1),
                 'Artist': {'Id': result['artist_id'], 'Name': result['artist_name']}}
                for result in results]

    def get_album_by_id(self, rgid, rid=None):
        release_groups = self.query_from_file('release_group_by_id.sql', [rgid])

        if not release_groups:
            return {}

        rid = rid or release_groups[0]['release_id']

        releases = filter(lambda rg: rg['release_id'] == rid, release_groups)
        release = releases[0] if releases else None

        if not release:
            return {}

        album = {'Id': release_groups[0]['gid'],
                 'Disambiguation': release_groups[0]['comment'],
                 'Title': release_groups[0]['album'],
                 'Type': release_groups[0]['primary_type'],
                 'SecondaryTypes': release_groups[0]['secondary_types'],
                 'ReleaseDate': datetime.datetime(release_groups[0]['year'] or 1,
                                                  release_groups[0]['month'] or 1,
                                                  release_groups[0]['day'] or 1),
                 'Label': release['label'],
                 'Artist': {'Id': release_groups[0]['artist_id'], 'Name': release_groups[0]['artist_name']},
                 'SelectedRelease': rid}

        releases = [{'Id': release_group['release_id'],
                     'Disambiguation': release_group['release_comment'],
                     'Country': release_group['country'],
                     'Label': release_group['label'],
                     'ReleaseDate': datetime.datetime(release_group['release_year'] or 1,
                                                      release_group['release_month'] or 1,
                                                      release_group['release_day'] or 1),
                     'MediaCount': release_group['media_count'],
                     'TrackCount': release_group['track_count'],
                     'Format': [release_group['format']]}
                    for release_group in release_groups]

        # Combine formats
        # TODO Rework data code and find a better solution for this
        combined_releases = {}
        for release in releases:
            id_ = release['Id']
            if id_ in combined_releases:
                combined_releases[id_]['Format'].extend(release['Format'])
            else:
                combined_releases[id_] = release

        for release in combined_releases.values():
            format_counter = collections.Counter(release['Format'])
            formats = []
            for medium, count in format_counter.items():
                if medium:
                    format_ = '' if count == 1 else '{}x'.format(count)
                    formats.append(format_ + medium)

            release['Format'] = ' + '.join(formats)

        album['Releases'] = combined_releases.values()

        return album

    def get_album_media(self, album_id):
        results = self.query_from_file('media_album_mbid.sql',
                                       [album_id])
        return [{'Format': result['medium_format'] or '',
                 'Name': result['medium_name'],
                 'Position': result['medium_position']}
                for result in results]

    def get_album_tracks(self, album_id):
        results = self.query_from_file('track_album_mbid.sql',
                                       [album_id])

        return [{'Id': result['gid'],
                 'TrackName': result['name'],
                 'DurationMs': result['length'],
                 'MediumNumber': result['medium_position'],
                 'TrackNumber': result['number'],
                 'TrackPosition': result['position']}
                for result in results]

    def get_albums_by_artist(self, artist_id):
        results = self.query_from_file('album_search_artist_mbid.sql',
                                       [artist_id])

        return [{'Id': result['gid'],
                 'Disambiguation': result['comment'],
                 'Title': result['album'],
                 'Type': result['primary_type'],
                 'SecondaryTypes': result['secondary_types'],
                 'ReleaseDate': datetime.datetime(result['year'] or 1,
                                                  result['month'] or 1,
                                                  result['day'] or 1)}
                for result in results]

    def get_artist_links(self, artist_id):
        results = self.query_from_file('links_artist_mbid.sql',
                                       [artist_id])
        return [{'target': result['url'],
                 'type': self.parse_url_source(result['url'])}
                for result in results]

    def query_from_file(self, sql_file, *args, **kwargs):
        """
        Executes query from sql file
        :param sql_file: Filename of sql file
        :param args: Positional args to pass to cursor.execute
        :param kwargs: Keyword args to pass to cursor.execute
        :return: List of dict with column: value results
        """
        filename = pkg_resources.resource_filename('lidarrmetadata.sql', sql_file)

        with open(filename, 'r') as sql:
            return self.map_query(sql.read(), *args, **kwargs)

    def map_query(self, *args, **kwargs):
        """
        Maps a SQL query to a list of dicts of column name: value
        :param args: Args to pass to cursor.execute
        :param kwargs: Keyword args to pass to cursor.execute
        :return: List of dict with column: value
        """

        with self._cursor() as cursor:
            cursor.execute(*args, **kwargs)
            columns = collections.OrderedDict(
                (column.name, None) for column in cursor.description)
            results = cursor.fetchall()

        results = [{column: result[i] for i, column in enumerate(columns.keys())}
                   for
                   result in results]

        # Decode strings
        results = util.map_iterable_values(results, self.mb_decode, str)

        return results

    @contextlib.contextmanager
    def _cursor(self):
        connection = psycopg2.connect(host=self._db_host,
                                      port=self._db_port,
                                      dbname=self._db_name,
                                      user=self._db_user,
                                      password=self._db_password)
        cursor = connection.cursor()
        yield cursor
        cursor.close()
        connection.close()

    @classmethod
    def mb_decode(cls, s):
        """
        Decodes a string from musicbrainz
        :param s: String to decode
        :return: Decoded string
        """
        return util.translate_string(s, cls.TRANSLATION_TABLE)

    @classmethod
    def mb_encode(cls, s):
        """
        Encodes a string for musicbrainz
        :param s: String to encode
        :return: Musicbrainz encoded string
        """
        return util.translate_string(s, cls.TRANSLATION_TABLE.inverse)

    @staticmethod
    def parse_url_source(url):
        """
        Parses URL for name
        :param url: URL to parse
        :return: Website name of url
        """
        domain = url.split('/')[2]
        split_domain = domain.split('.')
        try:
            return split_domain[-2] if split_domain[-2] != 'co' else split_domain[-3]
        except IndexError:
            return domain


class WikipediaProvider(Provider, ArtistOverviewMixin):
    """
    Provider for querying wikipedia
    """

    URL_REGEX = re.compile(r'https?://\w+\.wikipedia\.org/wiki/(?P<title>.+)')

    def __init__(self):
        """
        Class initialization
        """
        super(WikipediaProvider, self).__init__()

    def get_artist_overview(self, url):
        return self.get_summary(url)

    @classmethod
    def get_summary(cls, url):
        """
        Gets summary of a wikipedia page
        :param url: URL of wikipedia page
        :return: Summary String
        """
        try:
            title = cls.title_from_url(url)
            return wikipedia.summary(title, auto_suggest=False)
        # FIXME Both of these may be recoverable
        except wikipedia.PageError as error:
            logger.error('Wikipedia PageError from {url}: {e}'.format(e=error, url=url))
            return ''
        except wikipedia.DisambiguationError as error:
            logger.error('Wikipedia DisambiguationError from {url}: {e}'.format(e=error, url=url))
            return ''
        except ValueError as error:
            logger.error('Page parse error: {e}'.format(e=error))
            return ''

    @classmethod
    def title_from_url(cls, url):
        """
        Gets the wikipedia page title from url. This may not work for URLs with
        certain special characters
        :param url: URL of wikipedia page
        :return: Title of page at URL
        """
        match = cls.URL_REGEX.match(url)

        if not match:
            raise ValueError('URL {} does not match regex `{}`'.format(url, cls.URL_REGEX.pattern))

        title = match.group('title')
        return urllib.unquote(title)
