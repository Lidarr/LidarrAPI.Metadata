from __future__ import division

import abc
import collections
import contextlib
import datetime
import time
import pytz
import imp
import logging
import pkg_resources
import re
import six
from urllib3.exceptions import HTTPError

import asyncio
import aiohttp
import asyncpg
import json

import dateutil.parser
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
    from urllib import quote as url_quote
else:
    from urllib.parse import quote as url_quote

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
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

class InvalidateCacheMixin(MixinBase):
    """
    Invalidates cache for updated items
    """
    
    @abc.abstractmethod
    def invalidate_cache(self, prefix):
        """
        Invalidates any internal cache as appropriate and returns entities that need invalidating at API level
        :param prefix: URL prefix for the instance we are clearing cache for
        :return: Dict {"artists":[ids], "albums":[ids]} of artists/albums that need to be updated
        """
        pass
    
class AsyncInit(MixinBase):
    """
    Hook to initialize async items
    """
    
    @abc.abstractmethod
    async def _init(self, prefix):
        """
        Run at initialization using await
        """
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
        
class ProviderUnavailableException(Exception):
    """ Thown on error for providers we can cope without """
    pass

class HttpProvider(Provider):
    """
    Generic provider which makes external HTTP queries
    """
    
    def __init__(self, name):
        super(HttpProvider, self).__init__()
        
        self._name = name
        self._limiter = _get_rate_limiter(key='wikipedia')
        self._stats = stats.TelegrafStatsClient(CONFIG.STATS_HOST,
                                                CONFIG.STATS_PORT) if CONFIG.ENABLE_STATS else None
        # self._session = aiohttp.ClientSession(timeout = aiohttp.ClientTimeout(total=CONFIG.EXTERNAL_TIMEOUT / 1000))
        
        logger.debug('Initialised aiohttp provider')
        
    def _count_request(self, result_type):
        if self._stats:
            self._stats.metric('external', {result_type: 1}, tags={'provider': 'wikipedia'})

    def _record_response_result(self, response):
        if self._stats:
            self._stats.metric('external',
                               {
                                   'response_time': response.elapsed.microseconds / 1000,
                                   'response_status_code': response.status_code
                               },
                               tags={'provider': 'solr_search'})
            
    async def get_with_limit(self, url):
        try:
            ## TODO make this persistent
            async with aiohttp.ClientSession() as session:
                resp = await session.request(method='GET', url=url)
                resp.raise_for_status()
                logger.info("Got response [%s] for URL: %s", resp.status, url)
                json = await resp.json()
                return json
        except ValueError as error:
            logger.error(f'Response from {self._name} not valid json: {error}')
            raise ProviderUnavailableException(f'{self._name} returned invalid json')
        except (aiohttp.ClientError, aiohttp.http_exceptions.HttpProcessingError) as error:
            logger.error(f'aiohttp exception for {url} [{getattr(error, "status", None)}]: {getattr(error, "message", None)}')
            raise ProviderUnavailableException(f'{self._name} aiohttp exception')
        except Exception as error:
            logger.error(f'Non-aiohttp exceptions occured: {getattr(error, "__dict__", {})}')
            # raise ProviderUnavailableException(f'{self._name} non-aiohttp exception')
            raise

class FanArtTvProvider(HttpProvider, 
                       AlbumArtworkMixin, 
                       ArtistArtworkMixin,
                       InvalidateCacheMixin):
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
        super(FanArtTvProvider, self).__init__('fanart')

        self._api_key = api_key
        self._base_url = base_url
        self.use_https = use_https
        
        ## dummy value for initialization, will be picked up from redis later on
        self._last_cache_invalidation = time.time() - 60 * 60 * 24

    async def get_artist_images(self, artist_id, ignore_cache = False):
        
        cached, expired = util.FANART_CACHE.get(artist_id) or (None, True)

        if cached and not expired and not ignore_cache:
            return self.parse_artist_images(cached)
        
        try:
            results = await self.get_by_mbid(artist_id)

            util.FANART_CACHE.set(artist_id, results)
            for id, album_result in results.get('albums', {}).items():
                util.FANART_CACHE.set(id, album_result)
                    
            return self.parse_artist_images(results)

        except ProviderUnavailableException:
            if cached:
                return self.parse_artist_images(cached)
            else:
                raise

    async def get_album_images(self, album_id):
        cached, expired = util.FANART_CACHE.get(album_id) or (None, True)

        if cached and not expired:
            return self.parse_album_images(cached)
        
        try:
            results = await self.get_by_mbid(album_id)
            results = results.get('albums', results).get(album_id, results)            
            util.FANART_CACHE.set(album_id, results)

        except ProviderUnavailableException:
            if cached:
                return self.parse_album_images(cached)
            else:
                raise

    async def get_by_mbid(self, mbid):
        """
        Gets the fanart.tv response for resource with Musicbrainz id mbid
        :param mbid: Musicbrainz ID
        :return: fanart.tv response for mbid
        """
        url = self.build_url(mbid)
        return await self.get_with_limit(url)
        
    def invalidate_cache(self, prefix):
        logger.debug('Invalidating fanart cache')
        
        result = {'artists': [], 'albums': []}
        
        last_invalidation_key = prefix + 'FanartProviderLastCacheInvalidation'
        self._last_cache_invalidation = util.CACHE.get(last_invalidation_key) or self._last_cache_invalidation
        current_cache_invalidation = int(time.time())
        
        # Since we don't have a fanart personal key we can only see things with a lag
        all_updates = self.get_fanart_updates(self._last_cache_invalidation - CONFIG.FANART_API_DELAY_SECONDS)
        invisible_updates = self.get_fanart_updates(current_cache_invalidation - CONFIG.FANART_API_DELAY_SECONDS)
        
        # Remove the updates we can't see
        artist_ids = self.diff_fanart_updates(all_updates, invisible_updates)
        logger.info('Invalidating artists given fanart updates:\n{}'.format('\n'.join(artist_ids)))

        # Mark artists as expired
        for id in artist_ids:
            cached, expired = util.FANART_CACHE.get(id) or (None, True)
            if cached:
                # bodge - set timeout to one second from now
                util.FANART_CACHE.set(id, cached, timeout=1)
                
        # If there's only a few fanart updates then grab them now
        if len(artist_ids) <= 20:
            for id in artist_ids:
                self.get_artist_images(id, ignore_cache = True)
        else:
            logger.info('Too many fanart updates, only marking expired')

        util.CACHE.set(last_invalidation_key, current_cache_invalidation, timeout=0)
        
        result['artists'] = artist_ids
        return result
    
    def get_fanart_updates(self, time):
        url = self.build_url('latest') + '&date={}'.format(int(time))
        logger.debug(url)
        
        try:
            response = requests.get(url, timeout=CONFIG.EXTERNAL_TIMEOUT / 1000 * 5)
            try:
                if len(response.content):
                    return response.json()
                else:
                    return []
            except Exception as e:
                logger.error('Error decoding {}'.format(response))
                return []
        except ConnectionError as error:
            logger.error('ConnectionError: {e}'.format(e=error))
            return []
        except HTTPError as error:
            logger.error('HTTPError: {e}'.format(e=error))
            return []
        except requests.exceptions.Timeout as error:
            logger.error('Timeout: {e}'.format(e=error))
            return []
        except requests.exceptions.ConnectionError as error:
            logger.error('ConnectionError: {e}'.format(e=error))
            return []

        
    def diff_fanart_updates(self, long, short):
        """
        Unpicks the fanart api lag so we can see which have been updated
        """
        
        long_ids = collections.Counter([x['id'] for x in long])
        short_ids = collections.Counter([x['id'] for x in short])

        long_ids.subtract(short_ids)
        return set(long_ids.elements())

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
                    logger.error(u'Non-200 response code for {url}: {code}\n\t{details}'.format(
                        url=url,
                        code=response.status_code,
                        details=response.text
                    ))
                    return {}

        except HTTPError as error:
            logger.error('HTTPError: {e}'.format(e=error))
            return {}
        except requests.exceptions.Timeout as error:
            logger.error('Timeout: {e}'.format(e=error))
            self._count_request('timeout')
            return {}
        except limit.RateLimitedError:
            logger.debug('Musicbrainz search request rate limited')
            self._count_request('ratelimit')
            return {}
        
    def search_artist_name(self, name, limit=None, albums=None):
        
        if albums:
            return self.search_artist_name_with_albums(name, albums, self.parse_artist_search_with_albums, limit)

        # Note that when using a dismax query we shouldn't apply lucene escaping
        # See https://github.com/metabrainz/musicbrainz-server/blob/master/lib/MusicBrainz/Server/Data/WebService.pm
        url = u'{server}/artist/select?wt=mbjson&q={query}'.format(
            server=self._search_server,
            query=url_quote(name.encode('utf-8'))
        )
        
        if limit:
            url += u'&rows={}'.format(limit)
        
        response = self.get_with_limit(url)
        
        if not response:
            return {}
        
        logger.debug(u'Search for {query} completed in {time}ms'.format(query=name, time=response.elapsed.microseconds / 1000))
        
        return self.parse_artist_search(response.json())
    
    def search_artist_name_with_albums(self, artist, albums, handler, limit=None):
        
        album_query = u" ".join(albums)
        query = u"({album_query}) AND (artist:{artist} OR artistname:{artist} OR creditname:{artist})".format(
            album_query=url_quote(self.escape_lucene_query(album_query).encode('utf-8')),
            artist=url_quote(self.escape_lucene_query(artist).encode('utf-8'))
        )
        
        url = u'{server}/release-group/advanced?wt=mbjson&q={query}'.format(
            server=self._search_server,
            query=query
        )
        
        if limit:
            url += u'&rows={}'.format(limit)
            
        response = self.get_with_limit(url)
        
        if not response:
            return {}

        logger.debug(u'Search for {query} completed in {time}ms'.format(query=query, time=response.elapsed.microseconds / 1000))
        
        return handler(response.json())
    
    def search_album_name(self, name, limit=None, artist_name=''):
        
        if artist_name:
            return self.search_artist_name_with_albums(artist_name, [name], self.parse_album_search, limit)

        # Note that when using a dismax query we shouldn't apply lucene escaping
        # See https://github.com/metabrainz/musicbrainz-server/blob/master/lib/MusicBrainz/Server/Data/WebService.pm
        url = u'{server}/release-group/select?wt=mbjson&q={query}'.format(
            server=self._search_server,
            query=url_quote(name.encode('utf-8'))
        )
        
        if limit:
            url += u'&rows={}'.format(limit)
        
        response = self.get_with_limit(url)
        
        if not response:
            return {}
        
        logger.debug(u'Search for {query} completed in {time}ms'.format(query=name, time=response.elapsed.microseconds / 1000))
        
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
                            AsyncInit,
                            DataVintageMixin,
                            InvalidateCacheMixin,
                            AlbumArtworkMixin,
                            ArtistByIdMixin,
                            ArtistLinkMixin,
                            ReleaseGroupByArtistMixin,
                            ReleaseGroupByIdMixin,
                            ReleasesByReleaseGroupIdMixin,
                            ReleaseGroupLinkMixin,
                            TracksByReleaseGroupMixin):
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
        self._pool = None
        
        ## dummy value for initialization, will be picked up from redis later on
        self._last_cache_invalidation = datetime.datetime.now(pytz.utc) - datetime.timedelta(hours = 2)
        
    async def uuid_as_str(self, con):
        await con.set_type_codec(
            'uuid', encoder=str, decoder=str,
            schema='pg_catalog', format='text'
        )
        
    async def _init(self):
        logger.debug("Initializing MB DB pool")
        self._pool = await asyncpg.create_pool(host = self._db_host,
                                               port = self._db_port,
                                               user = self._db_user,
                                               password = self._db_password,
                                               database = self._db_name,
                                               init = self.uuid_as_str)
        logger.debug("Done")
        
    async def data_vintage(self):
        data = await self.query_from_file('../sql/data_vintage.sql')
        return data[0]['vintage']
    
    async def invalidate_cache(self, prefix):

        last_invalidation_key = prefix + 'MBProviderLastCacheInvalidation'
        self._last_cache_invalidation = util.CACHE.get(last_invalidation_key) or self._last_cache_invalidation

        result = {'artists': [], 'albums': []}
        
        vintage = self.data_vintage()
        if vintage > self._last_cache_invalidation:
            logger.debug('Invalidating musicbrainz cache')

            result['artists'] = await self._invalidate_queries_by_entity_id('updated_artists.sql')
            result['albums'] = await self._invalidate_queries_by_entity_id('updated_albums.sql')
            
            logger.info('Invalidating these artists given musicbrainz updates:\n{}'.format('\n'.join(result['artists'])))
            logger.info('Invalidating these albums given musicbrainz updates:\n{}'.format('\n'.join(result['albums'])))

            util.CACHE.set(last_invalidation_key, vintage, timeout=0)
        else:
            logger.debug('Musicbrainz invalidation not required')
            
        return result
    
    async def _invalidate_queries_by_entity_id(self, changed_query):
        entities = await self.query_from_file(changed_query, {'date': self._last_cache_invalidation})
        return [entity['gid'] for entity in entities]
        
    async def get_artist_by_id(self, artist_id):
        results = await self.query_from_file('../sql/artist_search_mbid.sql', [artist_id])
        
        logger.debug("got artist")
        
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

    async def get_album_images(self, album_id):
        filename = '../sql/caa_by_mbid.sql'
        results = await self.query_from_file(filename, [album_id])
        
        logger.debug("got album images")

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

    async def get_release_group_by_id(self, rgid):
        release_groups = await self.query_from_file('release_group_by_id.sql', [rgid])
        
        logger.debug("got release group")
        
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
        
        date_json = [json.loads(dt) for dt in date_json]
        defined = [datetime.datetime(dt['year'], dt['month'], dt['day']) for dt in date_json if dt['year'] and dt['month'] and dt['day']]
        if defined:
            return min(defined)

        return min([datetime.datetime(dt['year'] or 1, dt['month'] or 1, dt['day'] or 1) for dt in date_json])

    async def get_releases_by_rgid(self, rgid):

        releases = await self.query_from_file('release_by_release_group_id.sql', [rgid])
        
        logger.debug("got releases")
                
        if not releases:
            return []

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

    async def get_release_group_artist_ids(self, rgid):
        result = await self.query_from_file('artist_by_release_group.sql', [rgid])
        logger.debug("got track artist ids")
        return [x['gid'] for x in result]

    async def get_release_group_tracks(self, rgid):
        results = await self.query_from_file('track_release_group.sql', [rgid])
        
        logger.debug("got rg tracks")

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

    async def get_release_groups_by_artist(self, artist_id):
        results = await self.query_from_file('release_group_search_artist_mbid.sql',
                                       [artist_id])
        
        logger.debug("got artist release groups")

        return [{'Id': result['gid'],
                 'Title': result['album'],
                 'Type': result['primary_type'],
                 'SecondaryTypes': result['secondary_types'],
                 'ReleaseStatuses': result['release_statuses']}
                for result in results]

    async def get_artist_links(self, artist_id):
        results = await self.query_from_file('links_artist_mbid.sql',
                                       [artist_id])
        logger.debug("got artist links")
        return [{'target': result['url'],
                 'type': self.parse_url_source(result['url'])}
                for result in results]

    async def get_release_group_links(self, release_group_id):
        results = await self.query_from_file('links_release_group_mbid.sql',
                                       [release_group_id])
        logger.debug("got release group links")
        return [{'target': result['url'],
                 'type': self.parse_url_source(result['url'])}
                for result in results]

    async def query_from_file(self, sql_file, *args, **kwargs):
        """
        Executes query from sql file
        :param sql_file: Filename of sql file
        :param args: Positional args to pass to cursor.execute
        :param kwargs: Keyword args to pass to cursor.execute
        :return: List of dict with column: value results
        """
        filename = pkg_resources.resource_filename('lidarrmetadata.sql', sql_file)

        with open(filename, 'r') as sql:
            return await self.map_query(sql.read(), *args, **kwargs)

    async def map_query(self, sql, *args, **kwargs):
        """
        Maps a SQL query to a list of dicts of column name: value
        :param args: Args to pass to cursor.execute
        :param kwargs: Keyword args to pass to cursor.execute
        :return: List of dict with column: value
        """
        
        # logger.debug(f"running query:\n{sql}")
        cursor_args = args[0] if args else kwargs
        # logger.debug(f"args:\n:{cursor_args}")
        
        async with self._pool.acquire() as connection:
            data = await connection.fetch(sql, *cursor_args)
            
        # logger.debug(data)
            
        results = [dict(row.items()) for row in data]

        # Decode strings
        # results = util.map_iterable_values(results, self.mb_decode, str)

        return results

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

class WikipediaProvider(HttpProvider, ArtistOverviewMixin):
    """
    Provider for querying wikipedia
    """

    WIKIPEDIA_REGEX = re.compile(r'https?://(?P<language>\w+)\.wikipedia\.org/wiki/(?P<title>.+)')
    WIKIDATA_REGEX = re.compile(r'https?://www.wikidata.org/(wiki|entity)/(?P<entity>.+)')

    def __init__(self):
        """
        Class initialization
        """
        super(WikipediaProvider, self).__init__('wikipedia')

        # https://github.com/metabrainz/musicbrainz-server/blob/v-2019-05-13-schema-change/lib/MusicBrainz/Server/Data/WikipediaExtract.pm#L61
        self.language_preference = (
            'en', 'ja', 'de', 'fr', 'fi', 'it', 'sv', 'es', 'ru', 'pl',
            'nl', 'pt', 'et', 'da', 'ko', 'ca', 'cs', 'cy', 'el', 'he',
            'hu', 'id', 'lt', 'lv', 'no', 'ro', 'sk', 'sl', 'tr', 'uk',
            'vi', 'zh'
        )
        
    async def get_artist_overview(self, url):
        cached, expired = util.WIKI_CACHE.get(url) or (None, True)
        
        if cached and not expired:
            return cached
        
        logger.debug("getting overview")
        
        try:
            summary = await self.wikidata_get_summary_from_url(url) if 'wikidata' in url else await self.wikipedia_get_summary_from_url(url)
            util.WIKI_CACHE.set(url, summary)
            return summary
        
        except ProviderUnavailableException:
            if cached:
                return cached
            else:
                raise
        except ValueError:
            logger.error('Could not get summary from {}'.format(url))
            return ''
            
    async def wikidata_get_summary_from_url(self, url):
        data = await self.wikidata_get_entity_data_from_url(url)
        return await self.wikidata_get_summary_from_entity_data(data)
            
    async def wikidata_get_summary_from_entity_data(self, data):
        
        sites = { item['site']: url_quote(item['title'].encode('utf-8')) for item in data.get('sitelinks', {}).values() }

        # return english wiki if possible
        if 'enwiki' in sites:
            return await self.wikipedia_get_summary_from_title(sites['enwiki'], 'en')
        
        # if not, return english entity description
        description = data.get('descriptions', {}).get('en', {}).get('value', '')
        if description:
            return description
        
        # otherwise fall back to most common language available
        language = next((x for x in self.language_preference if sites.get('{}wiki'.format(x), '')), None)
        
        if language:
            title = sites['{}wiki'.format(language)]
            return await self.wikipedia_get_summary_from_title(title, language)
        return ''
    
    async def wikidata_get_entity_data_from_url(self, url):
        entity = self.wikidata_entity_from_url(url)
        wikidata_url = (
            'https://www.wikidata.org/w/api.php'
            '?action=wbgetentities'
            '&ids={}'
            '&props=sitelinks|descriptions'
            '&format=json'
        ).format(entity)
        
        data = await self.get_with_limit(wikidata_url)
        return (
            data
            .get('entities', {})
            .get(entity, {})
        )
    
    async def wikidata_get_entity_data_from_language_title(self, title, language):
        title = title.split("#", 1)[0]
        wikidata_url = (
            'https://www.wikidata.org/w/api.php'
            '?action=wbgetentities'
            '&sites={language}wiki'
            '&titles={title}'
            '&props=sitelinks|descriptions'
            '&format=json'
        ).format(language=language, title=title)
        data = await self.get_with_limit(wikidata_url)
        entities = data.get('entities', {})
        return entities[next(iter(entities))]
    
    async def wikipedia_get_summary_from_url(self, url):
        url_title, url_language = self.wikipedia_title_from_url(url)
        
        # if English link, just use that
        if url_language == 'en':
            return self.wikipedia_get_summary_from_title(url_title, url_language)
        
        # Otherwise go via wikidata to try to get something in English or best other language
        data = await self.wikidata_get_entity_data_from_language_title(url_title, url_language)
        return self.wikidata_get_summary_from_entity_data(data)
        
    async def wikipedia_get_summary_from_title(self, title, language):
        """
        Gets summary of a wikipedia page
        :param url: URL of wikipedia page
        :return: Summary String
        """
        
        wiki_url = (
            'https://{language}.wikipedia.org/w/api.php'
            '?action=query'
            '&prop=extracts'
            '&exintro'
            '&explaintext'
            '&format=json'
            '&formatversion=2'
            '&titles={title}'
        ).format(language = language, title = title)
        
        data = await self.get_with_limit(wiki_url)
        return data.get('query', {}).get('pages', [{}])[0].get('extract', '')

    @classmethod
    def wikipedia_title_from_url(cls, url):
        """
        Gets the wikipedia page title from url. This may not work for URLs with
        certain special characters
        :param url: URL of wikipedia page
        :return: Title of page at URL
        """
        match = cls.WIKIPEDIA_REGEX.match(url)

        if not match:
            raise ValueError(u'URL {} does not match regex `{}`'.format(url, cls.WIKIPEDIA_REGEX.pattern))

        title = match.group('title')
        language = match.group('language')
        return title, language

    @classmethod
    def wikidata_entity_from_url(cls, url):
        """
        Gets the wikidata entity id from the url. This may not work for URLs with
        certain special characters
        :param url: URL of wikidata page
        :return: Entity referred to
        """
        match = cls.WIKIDATA_REGEX.match(url)

        if not match:
            raise ValueError(u'URL {} does not match regex `{}`'.format(url, cls.WIKIDATA_REGEX.pattern))

        id = match.group('entity')
        return id
