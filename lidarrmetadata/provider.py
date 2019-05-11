from __future__ import division

import abc
import collections
import contextlib
import datetime
import imp
import logging
import pkg_resources
import re
import six
from urllib3.exceptions import HTTPError

import dateutil.parser
import mediawikiapi
import psycopg2
import psycopg2.extensions
from psycopg2 import sql
import pylast
import requests

from lidarrmetadata.config import get_config
from lidarrmetadata import limit
from lidarrmetadata import stats
from lidarrmetadata import util

if six.PY2:
    from urllib import unquote as url_unquote
else:
    from urllib.parse import unquote as url_unquote

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.info('Have provider logger')

# always get strings from database in unicode
psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)
psycopg2.extensions.register_type(psycopg2.extensions.UNICODEARRAY)

CONFIG = get_config()

# Provider class dictionary
PROVIDER_CLASSES = {}


def get_providers_implementing(cls):
    """
    Gets list of providers implementing mixin
    :param cls: Mixin class for implementation
    :return: List of providers inheriting from cls
    """
    return [p for p in Provider.providers if isinstance(p, cls)]


def _get_rate_limiter(key=None):
    """
    Builds a rate limiter from config values
    :return: RateLimiter appropriate to config
    """
    try:
        limit_class = getattr(limit, CONFIG.EXTERNAL_LIMIT_CLASS)
    except AttributeError:
        logger.error('Limit class "{}" does not exist. Defaulting to NullRateLimiter'.format(
            CONFIG.EXTERNAL_LIMIT_CLASS))
        return limit.NullRateLimiter()

    logger.info('Initializing rate limiter class {} with key {}'.format(limit_class, key))
    if limit_class == limit.NullRateLimiter:
        return limit.NullRateLimiter()
    elif limit_class == limit.RedisRateLimiter:
        return limit.RedisRateLimiter(key=key,
                                      redis_host=CONFIG.EXTERNAL_LIMIT_REDIS_HOST,
                                      redis_port=CONFIG.EXTERNAL_LIMIT_REDIS_PORT,
                                      redis_db=CONFIG.EXTERNAL_LIMIT_REDIS_DB,
                                      queue_size=CONFIG.EXTERNAL_LIMIT_QUEUE_SIZE,
                                      time_delta=CONFIG.EXTERNAL_LIMIT_TIME_DELTA)
    elif limit_class == limit.SimpleRateLimiter:
        return limit.SimpleRateLimiter(queue_size=CONFIG.EXTERNAL_LIMIT_QUEUE_SIZE,
                                       time_delta=CONFIG.EXTERNAL_LIMIT_TIME_DELTA)
    else:
        logger.warning(
            "Don't know how to instantiate {}. Defaulting to NullRateLimiter".format(limit_class))
        return limit.NullRateLimiter()


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
    def search_artist_name(self, name, limit=None, albums=None):
        """
        Searches for artist with name
        :param name: Name to search for
        :param limit: Limit of number of results to return. Defaults to None, indicating no limit
        :return: List of possible matches
        """
        pass


class ReleaseGroupByArtistMixin(MixinBase):
    """
    Gets release groups for artist
    """

    @abc.abstractmethod
    def get_release_groups_by_artist(self, artist_id):
        """
        Gets release groups by artist by ID
        :param artist_id: ID of artist
        :return: List of release groups by artist
        """
        pass


class ReleaseGroupByIdMixin(MixinBase):
    """
    Gets release group by ID
    """

    @abc.abstractmethod
    def get_release_group_by_id(self, rgid):
        """
        Gets release group by ID
        :param rgid: Release group ID
        :return: Release Group corresponding to rgid
        """
        pass


class ReleasesByReleaseGroupIdMixin(MixinBase):
    """
    Gets releases by ReleaseGroup ID
    """

    @abc.abstractmethod
    def get_releases_by_rgid(self, rgid):
        """
        Gets releases by release group ID
        :param rgid: Release group ID
        :return: Releases corresponding to rgid or rid
        """
        pass


class TracksByReleaseGroupMixin(MixinBase):
    """
    Gets tracks by release group
    """

    @abc.abstractmethod
    def get_release_group_tracks(self, rgid):
        """
        Gets tracks in album
        :rgid album_id: ID of release group
        :return: List of tracks in all releases of a release group
        """
        pass

    @abc.abstractmethod
    def get_release_group_artist_ids(self, rgid):
        """
        Gets all the artists associated with a release group ID
        :param rgid: Release group ID
        :return: All artists credited as lead credit on tracks on releases
        """
        pass


class TrackSearchMixin(MixinBase):
    """
    Search for tracks by name
    """

    @abc.abstractmethod
    def search_track(self, query, artist_name=None, album_name=None, limit=10):
        """
        Searches for tracks matching query
        :param query: Search query
        :param artist_name: Artist name. Defaults to None, in which case tracks from all artists are returned
        :param album_name: Album name. Defaults to None, in which case tracks from all albums are returned
        :param limit: Maximum number of results to return. Defaults to 10. Returns all results if negative
        :return: List of track results
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


class ReleaseGroupLinkMixin(MixinBase):
    """
    Gets links for release group
    """

    @abc.abstractmethod
    def get_release_group_links(self, release_group_id):
        """
        Gets links for release_group with id
        :param release_group_id: ID of release_group
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

class DataVintageMixin(MixinBase):
    """
    Returns vintage of data in use
    """
    
    @abc.abstractmethod
    def data_vintage(self):
        pass

class ProviderMeta(abc.ABCMeta):
    def __new__(mcls, name, bases, namespace):
        """
        Creates class and registers it to PROVIDER_CLASSES
        :param mcls: Parent metaclass
        :param name: Name of class
        :param bases: Base classes
        :param namespace: Class dictionary
        :return: Newly created class
        """
        cls = super(ProviderMeta, mcls).__new__(mcls, name, bases, namespace)
        PROVIDER_CLASSES[name] = cls
        return cls


class Provider(six.with_metaclass(ProviderMeta, object)):
    """
    Provider base class
    """

    # List of provider instances
    providers = []

    def __init__(self):
        logger.info('Initializing provider {}'.format(self.__class__))
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

        self._api_key = api_key
        self._base_url = base_url
        self._limiter = _get_rate_limiter(key='fanart')
        self._stats = stats.TelegrafStatsClient(CONFIG.STATS_HOST,
                                                CONFIG.STATS_PORT) if CONFIG.ENABLE_STATS else None
        self.use_https = use_https
        
    def _redis_key(self, id):
        return u'fanart{}'.format(id)

    def get_artist_images(self, artist_id):
        results = util.CACHE.get(self._redis_key(artist_id))

        if not results:
            results = self.get_by_mbid(artist_id)

            # TODO Improve this during refactor to models
            if results is None:
                return self.parse_artist_images({})

            util.CACHE.set(self._redis_key(artist_id), results)
            for id, album_result in results.get('albums', {}).items():
                util.CACHE.set(self._redis_key(id), album_result)

        return self.parse_artist_images(results)

    def get_album_images(self, album_id):
        results = util.CACHE.get(self._redis_key(album_id))

        if not results:
            results = self.get_by_mbid(album_id)

            # TODO Improve this during refactor to models
            if results is None:
                return self.parse_album_images({})

            results = results.get('albums', results).get(album_id, results)
            util.CACHE.set(self._redis_key(album_id), results)

        return self.parse_album_images(results)

    @util.CACHE.memoize()
    def get_by_mbid(self, mbid):
        """
        Gets the fanart.tv response for resource with Musicbrainz id mbid
        :param mbid: Musicbrainz ID
        :return: fanart.tv response for mbid
        """
        url = self.build_url(mbid)
        try:
            with self._limiter.limited():
                self._count_request('request')
                response = requests.get(url, timeout=CONFIG.EXTERNAL_TIMEOUT / 1000)
                try:
                    return response.json()
                except Exception as e:
                    logger.error('Error decoding {}'.format(response))
                    return None
        except HTTPError as error:
            logger.error('HTTPError: {e}'.format(e=error))
            return None
        except requests.exceptions.Timeout as error:
            logger.error('Timeout: {e}'.format(e=error))
            self._count_request('timeout')
            return None
        except limit.RateLimitedError:
            logger.error('Fanart request to {} rate limited'.format(mbid))
            self._count_request('ratelimit')
            return None

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

    def _count_request(self, result_type):
        if self._stats:
            self._stats.metric('external', {result_type: 1}, tags={'provider': 'fanart'})

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
    
class SolrSearchProvider(Provider,
                         ArtistNameSearchMixin,
                         AlbumNameSearchMixin):
    
    """
    Provider that uses a solr indexed search
    """
    def __init__(self,
                 search_server='http://solr:8983/solr'):
        """
        Class initialization

        Defaults to the offical musicbrainz webservice but in principle we could
        host our own mirror using https://github.com/metabrainz/musicbrainz-docker

        :param search_server: URL for the search server.  Note that using HTTPS adds around 100ms to search time.
        """
        super(SolrSearchProvider, self).__init__()

        self._search_server = search_server
        self._limiter = _get_rate_limiter(key='solr_search')
        
        self._stats = stats.TelegrafStatsClient(CONFIG.STATS_HOST,
                                                CONFIG.STATS_PORT) if CONFIG.ENABLE_STATS else None

            
    def _count_request(self, result_type):
        if self._stats:
            self._stats.metric('external', {result_type: 1}, tags={'provider': 'solr_search'})

    def _record_response_result(self, response):
        if self._stats:
            self._stats.metric('external',
                               {
                                   'response_time': response.elapsed.microseconds / 1000,
                                   'response_status_code': response.status_code
                               },
                               tags={'provider': 'solr_search'})
        
    def get_with_limit(self, url):
        
        try:
            with self._limiter.limited():
                self._count_request('request')
                response = requests.get(url, timeout=CONFIG.EXTERNAL_TIMEOUT)
                self._record_response_result(response)

                if response.status_code == 200:
                    return response
                else:
                    logger.error('Non-200 response code for search: {}\n\t{}'.format(response.status_code,
                                                                                     response))
                    return {}

        except HTTPError as error:
            logger.error('HTTPError: {e}'.format(e=error))
            return {}
        except requests.exceptions.Timeout as error:
            logger.error('Timeout: {e}'.format(e=error))
            self._count_request('timeout')
            return {}
        except limit.RateLimitedError:
            logger.error('Musicbrainz search request rate limited')
            self._count_request('ratelimit')
            return {}
        
    def search_artist_name(self, name, limit=None, albums=None):
        
        if albums:
            return self.search_artist_name_with_albums(name, albums, self.parse_artist_search_with_albums, limit)

        # Note that when using a dismax query we shouldn't apply lucene escaping
        # See https://github.com/metabrainz/musicbrainz-server/blob/master/lib/MusicBrainz/Server/Data/WebService.pm
        url = u'{server}/artist/select?wt=mbjson&q={query}'.format(server=self._search_server, query=name)
        
        if limit:
            url += u'&rows={}'.format(limit)
        
        response = self.get_with_limit(url)
        
        if not response:
            return {}
        
        logger.debug("Search for {query} completed in {time}ms".format(query=name, time=response.elapsed.microseconds / 1000))
        
        return self.parse_artist_search(response.json())
    
    def search_artist_name_with_albums(self, artist, albums, handler, limit=None):
        
        album_query = u" ".join(albums)
        query = u"({album_query}) AND (artist:{artist} OR artistname:{artist} OR creditname:{artist})".format(album_query=album_query, artist=artist)
        
        url = u'{server}/release-group/advanced?wt=mbjson&q={query}'.format(server=self._search_server,
                                                                            query=self.escape_lucene_query(query))
        
        if limit:
            url += u'&rows={}'.format(limit)
            
        response = self.get_with_limit(url)
        
        if not response:
            return {}

        logger.debug("Search for {query} completed in {time}ms".format(query=query, time=response.elapsed.microseconds / 1000))
        
        return handler(response.json())
    
    def search_album_name(self, name, limit=None, artist_name=''):
        
        if artist_name:
            return self.search_artist_name_with_albums(artist_name, [name], self.parse_album_search, limit)

        # Note that when using a dismax query we shouldn't apply lucene escaping
        # See https://github.com/metabrainz/musicbrainz-server/blob/master/lib/MusicBrainz/Server/Data/WebService.pm
        url = u'{server}/release-group/select?wt=mbjson&q={query}'.format(server=self._search_server, query=name)
        
        if limit:
            url += u'&rows={}'.format(limit)
        
        response = self.get_with_limit(url)
        
        if not response:
            return {}
        
        logger.debug("Search for {query} completed in {time}ms".format(query=name, time=response.elapsed.microseconds / 1000))
        
        return self.parse_album_search(response.json())

    
    @staticmethod
    def escape_lucene_query(text):
        return re.sub(r'([+\-&|!(){}\[\]\^"~*?:\\/])', r'\\\1', text)
        
    @staticmethod
    def parse_artist_search(response):
        
        if not 'count' in response or response['count'] == 0:
            return []
        
        return [{'Id': x['id'],
                 'ArtistName': x['name'],
                 'Type': x['type'] if 'type' in x else '',
                 'Disambiguation': x['disambiguation'] if 'disambiguation' in x else ''}
                for x in response['artists']];
    
    @staticmethod
    def parse_artist_search_with_albums(response):
        
        if not 'count' in response or response['count'] == 0:
            return []
        
        artists = []
        seen_artists = set()
        
        for rg in response['release-groups']:
            for credit in rg['artist-credit']:
                if not credit['artist']['id'] in seen_artists:
                    seen_artists.add(credit['artist']['id'])
                    artists.append(credit['artist'])
                
        result = [{'Id': artist['id'],
                    'ArtistName': artist['name'],
                    'Disambiguation': artist['disambiguation'] if 'disambiguation' in artist else ''}
                  for artist in artists]
        
        return result
    
    @staticmethod
    def parse_album_search(response):
        
        if not 'count' in response or response['count'] == 0:
            return []
        
        result = [{'Id': result['id'],
                 'Title': result['title'],
                 'Type': result['primary-type'] if 'primary-type' in result else 'Unknown'}
                for result in response['release-groups']]

        return result
    
class MusicbrainzDbProvider(Provider,
                            DataVintageMixin,
                            AlbumArtworkMixin,
                            ArtistByIdMixin,
                            ArtistLinkMixin,
                            ArtistNameSearchMixin,
                            ReleaseGroupByArtistMixin,
                            ReleaseGroupByIdMixin,
                            ReleasesByReleaseGroupIdMixin,
                            ReleaseGroupLinkMixin,
                            AlbumNameSearchMixin,
                            TracksByReleaseGroupMixin,
                            TrackSearchMixin):
    """
    Provider for directly querying musicbrainz database
    """

    TRANSLATION_TABLE = util.BidirectionalDictionary({
        u'\u2026': u'...',  # HORIZONTAL ELLIPSIS (U+2026)
        u'\u0027': u"'",  # APOSTROPHE (U+0027)
        u'\u2010': u'-',  # HYPHEN (U+2010)
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
        
    def data_vintage(self):
        return self.query_from_file('../sql/data_vintage.sql')[0]['vintage']

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
                'Disambiguation': results['comment'],
                'Rating': {'Count': results['rating_count'] or 0,
                           'Value': results['rating'] / 10 if results[
                                                                  'rating'] is not None else None}}

    def get_album_images(self, album_id):
        filename = '../sql/caa_by_mbid.sql'
        results = self.query_from_file(filename, [album_id])

        type_mapping = {'Front': 'Cover', 'Medium': 'Disc'}

        art = {}
        for result in results:
            cover_type = type_mapping.get(result['type'], None)
            if cover_type is not None and cover_type not in art:
                art[cover_type] = self._build_caa_url(result['release_gid'], result['image_id'])
        return [{'CoverType': art_type, 'Url': url} for art_type, url in art.items()]

    @staticmethod
    def _build_caa_url(release_id, image_id):
        return 'https://coverartarchive.org/release/{}/{}.jpg'.format(release_id, image_id)

    def search_artist_name(self, name, limit=None, albums=None):
        name = self.mb_encode(name)
        
        filename = 'artist_search_name_with_album.sql' if albums else 'artist_search_name.sql'

        args = {'artist': name}
        if albums:
            with self._cursor() as cursor:
                args['album_query'] = sql.SQL(' | ').join([sql.Literal(album) for album in albums]).as_string(cursor)

        filename = pkg_resources.resource_filename('lidarrmetadata.sql', filename)
        with open(filename, 'r') as infile:
            query = infile.read()

        if limit:
            with self._cursor() as cursor:
                if limit:
                    query += cursor.mogrify(' LIMIT %s', [limit])

        results = self.map_query(query, **args)

        return [{'Id': result['gid'],
                 'ArtistName': result['name'],
                 'Type': result['type'] or 'Artist',
                 'Disambiguation': result['comment'],
                 'Rating': {'Count': result['rating_count'] or 0, 'Value': result['rating'] / 10 if result['rating'] is not None else None}}
                for result in results]

    def search_album_name(self, name, limit=None, artist_name=''):
        name = self.mb_encode(name)

        filename = pkg_resources.resource_filename('lidarrmetadata.sql', 'album_search_name.sql')
        with open(filename, 'r') as infile:
            query = infile.read()

        if artist_name or limit:
            with self._cursor() as cursor:

                if artist_name:
                    query_parts = query.split()

                    # Add artist name clause to where
                    new_parts = []
                    for part in query_parts:
                        if part.startswith('WHERE'):
                            part += cursor.mogrify(
                                ' to_tsvector(\'mb_simple\', artist.name) @@ plainto_tsquery(\'mb_simple\', %s) AND ',
                                [artist_name])

                        new_parts.append(part)
                    query_parts = new_parts or query_parts

                    query = '\n'.join(query_parts)

                if limit:
                    query += cursor.mogrify(' LIMIT %s', [limit])

        results = self.map_query(query, [name, name, name])

        return [{'Id': result['gid'],
                 'Disambiguation': result['comment'],
                 'Title': result['album'],
                 'Type': result['primary_type'],
                 'SecondaryTypes': result['secondary_types'],
                 'ReleaseDate': datetime.datetime(result['year'] or 1,
                                                  result['month'] or 1,
                                                  result['day'] or 1),
                 'ArtistId': result['artist_id'],
                 'Rating': {'Count': result['rating_count'] or 0,
                       'Value': result['rating'] / 10 if result['rating'] is not None else None}
                 }
                for result in results]

    def get_release_group_by_id(self, rgid):
        release_groups = self.query_from_file('release_group_by_id.sql', [rgid])
        if release_groups:
            release_group = release_groups[0]
        else:
            return {}

        return {
            'Id': release_group['gid'],
            'Disambiguation': release_group['comment'],
            'Title': release_group['name'],
            'Type': release_group['primary_type'],
            'SecondaryTypes': release_group['secondary_types'],
            'ReleaseDate': datetime.datetime(release_group['year'] or 1,
                                             release_group['month'] or 1,
                                             release_group['day'] or 1),
            'ArtistId': release_group['artist_id'],
            'Rating': {'Count': release_group['rating_count'] or 0,
                       'Value': release_group['rating'] / 10 if release_group['rating'] is not None else None}
        }

    def get_earliest_good_date(self, date_json):
        if not date_json:
            return None
        
        defined = [datetime.datetime(dt['year'], dt['month'], dt['day']) for dt in date_json if dt['year'] and dt['month'] and dt['day']]
        if defined:
            return min(defined)

        return min([datetime.datetime(dt['year'] or 1, dt['month'] or 1, dt['day'] or 1) for dt in date_json])

    def get_releases_by_rgid(self, rgid):

        releases = self.query_from_file('release_by_release_group_id.sql', [rgid])
        if not releases:
            return {}

        return [{'Id': release['gid'],
                 'Title': release['name'],
                 'Disambiguation': release['comment'],
                 'Status': release['status'],
                 'Label': release['label'],
                 'Country': release['country'],
                 'ReleaseDate': self.get_earliest_good_date(release['release_dates']),
                 'Media': release['media'],
                 'TrackCount': release['track_count']}
                for release in releases]

    def get_release_group_artist_ids(self, rgid):
        return [x['gid'] for x in self.query_from_file('artist_by_release_group.sql', [rgid])]

    def get_release_group_tracks(self, rgid):
        results = self.query_from_file('track_release_group.sql', [rgid])

        return [{'Id': result['gid'],
                 'RecordingId': result['recording_id'],
                 'ReleaseId': result['release_id'],
                 'ArtistId': result['artist_id'],
                 'TrackName': result['name'],
                 'DurationMs': result['length'],
                 'MediumNumber': result['medium_position'],
                 'TrackNumber': result['number'],
                 'TrackPosition': result['position']}
                for result in results]

    def get_release_groups_by_artist(self, artist_id):
        results = self.query_from_file('release_group_search_artist_mbid.sql',
                                       [artist_id])

        return [{'Id': result['gid'],
                 'Title': result['album'],
                 'Type': result['primary_type'],
                 'SecondaryTypes': result['secondary_types'],
                 'ReleaseStatuses': result['release_statuses']}
                for result in results]

    def get_artist_links(self, artist_id):
        results = self.query_from_file('links_artist_mbid.sql',
                                       [artist_id])
        return [{'target': result['url'],
                 'type': self.parse_url_source(result['url'])}
                for result in results]

    def get_release_group_links(self, release_group_id):
        results = self.query_from_file('links_release_group_mbid.sql',
                                       [release_group_id])
        return [{'target': result['url'],
                 'type': self.parse_url_source(result['url'])}
                for result in results]

    def search_track(self, query, artist_name=None, album_name=None, limit=10):
        filename = pkg_resources.resource_filename('lidarrmetadata.sql', 'track_search.sql')
        with open(filename, 'r') as infile:
            sql_query = infile.read()

        with self._cursor() as cursor:

            query_parts = sql_query.split()

            # Add artist name clause to where
            if artist_name or album_name:
                new_query = []
                for part in query_parts:
                    if part.startswith('WHERE'):
                        # This makes no sense, but extra queries are added after WHERE instead of at end of line
                        if artist_name:
                            part += cursor.mogrify(
                                ' to_tsvector(\'mb_simple\', artist.name) @@ plainto_tsquery(\'mb_simple\', %s) AND ',
                                [artist_name])
                        if album_name:
                            part += cursor.mogrify(
                                ' to_tsvector(\'mb_simple\', release_group.name) @@ plainto_tsquery(\'mb_simple\', %s)) AND ',
                                [album_name])
                    new_query.append(part)

                query_parts = new_query

            sql_query = '\n'.join(query_parts)

            if limit:
                sql_query += cursor.mogrify(' LIMIT %s', [limit])

        results = self.map_query(sql_query, [query, query, query])

        return [{'TrackName': result['track_name'],
                 'DurationMs': result['track_duration'],
                 'ArtistName': result['artist_name'],
                 'ArtistId': result['artist_gid'],
                 'AlbumTitle': result['rg_title'],
                 'AlbumId': result['rg_gid'],
                 'Rating': {
                     'Count': result['rating_count'] or 0,
                     'Value': result['rating'] / 10 if result['rating'] is not None else None
                 }}
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
            return util.cache_or_call(self.map_query, sql.read(), *args, **kwargs)

    def map_query(self, sql, *args, **kwargs):
        """
        Maps a SQL query to a list of dicts of column name: value
        :param args: Args to pass to cursor.execute
        :param kwargs: Keyword args to pass to cursor.execute
        :return: List of dict with column: value
        """
        
        cursor_args = args[0] if args else kwargs

        with self._cursor() as cursor:
            cursor.execute(sql, cursor_args)
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
                                      password=self._db_password,
                                      connect_timeout=5)
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
        s = re.sub(' +', ' ', s)
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

    WIKIPEDIA_REGEX = re.compile(r'https?://\w+\.wikipedia\.org/wiki/(?P<title>.+)')
    WIKIDATA_REGEX = re.compile(r'https?://www.wikidata.org/(wiki|entity)/(?P<entity>.+)')

    def __init__(self):
        """
        Class initialization
        """
        super(WikipediaProvider, self).__init__()
        self._client = mediawikiapi.MediaWikiAPI()
        self._limiter = _get_rate_limiter(key='wikipedia')

        self._stats = stats.TelegrafStatsClient(CONFIG.STATS_HOST,
                                                CONFIG.STATS_PORT) if CONFIG.ENABLE_STATS else None

    @util.CACHE.memoize()
    def get_artist_overview(self, url):
        if 'wikidata' in url:
            title = self.get_wikipedia_title(url)
        else:
            title = self.title_from_url(url)
        return self.get_summary(title)

    def get_wikipedia_title(self, url):
        entity = self.entity_from_url(url)
        wikidata_url = 'https://www.wikidata.org/w/api.php?action=wbgetentities&ids=' + entity + '&props=sitelinks&sitefilter=enwiki&format=json'
        data = requests.get(wikidata_url).json()
        return data.get('entities', {}).get(entity, {}).get('sitelinks', {}).get('enwiki', {}).get(
            'title', '')

    def get_summary(self, title):
        """
        Gets summary of a wikipedia page
        :param url: URL of wikipedia page
        :return: Summary String
        """
        try:
            with self._limiter.limited():
                self._count_request('request')
                return self._client.summary(title, auto_suggest=False)
        # FIXME Both of these may be recoverable
        except mediawikiapi.PageError as error:
            logger.error(u'Wikipedia PageError from {title}: {e}'.format(e=error, title=title))
            return ''
        except ValueError as error:
            logger.error(u'Page parse error: {e}'.format(e=error))
            return ''
        except KeyError as error:
            logger.error(u'KeyError {e}'.format(e=error))
            return ''
        except HTTPError as error:
            logger.error(u'HTTPError {e}'.format(e=error))
            return ''
        except limit.RateLimitedError as error:
            self._count_request('ratelimit')
            logger.error(u'Wikipedia Request for {title} rate limited'.format(title=title))
            return ''

    def _count_request(self, result_type):
        if self._stats:
            self._stats.metric('external', {result_type: 1}, tags={'provider': 'wikipedia'})

    @classmethod
    def title_from_url(cls, url):
        """
        Gets the wikipedia page title from url. This may not work for URLs with
        certain special characters
        :param url: URL of wikipedia page
        :return: Title of page at URL
        """
        match = cls.WIKIPEDIA_REGEX.match(url)

        if not match:
            raise ValueError('URL {} does not match regex `{}`'.format(url, cls.WIKIPEDIA_REGEX.pattern))

        title = match.group('title')
        return url_unquote(title)

    @classmethod
    def entity_from_url(cls, url):
        """
        Gets the wikidata entity id from the url. This may not work for URLs with
        certain special characters
        :param url: URL of wikidata page
        :return: Entity referred to
        """
        match = cls.WIKIDATA_REGEX.match(url)

        if not match:
            raise ValueError('URL {} does not match regex `{}`'.format(url, cls.WIKIDATA_REGEX.pattern))

        id = match.group('entity')
        return url_unquote(id)
