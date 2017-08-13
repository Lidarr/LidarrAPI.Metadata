import sys
import warnings

import pylast
import musicbrainzngs

import lidarrmetadata
from lidarrmetadata import config
from lidarrmetadata import models


def provider_by_name(name):
    """
    Gets a provider by string name
    :param name: Name of provider
    :return:
    """
    return getattr(sys.modules[__name__], name)


class Provider(object):
    """
    Base provider class
    """

    # Search priorities to determine which order providers are used in
    PRIORITY_FIRST = -1
    PRIORITY_NORMAL = 0
    PRIORITY_LAST = 1

    # List of provider instances to use for queries
    providers = []

    def __init__(self, priority=PRIORITY_NORMAL):
        self.priority = priority
        self.providers.append(self)
        self.providers.sort(key=lambda p: p.priority)

    @classmethod
    def search_album(cls, album, stop_on_result=True, cache_results=True):
        """
        Searches all providers for album via their ``_search_album`` method.
        :param album: Album to search for
        :param stop_on_result: Whether or not to stop on the first provider to return a result. Defaults to True.
        :param cache_results: Whether or not to cache results. Defaults to True.
        :return: List of artist results
        """
        results = []
        for provider in cls.providers:
            try:
                provider_results = provider._search_album(album)
            except NotImplementedError:
                warnings.warn(
                    'Album search not implemented for {class_name}'.format(class_name=provider.__class__.__name__))
                continue

            results.extend(provider_results)

            if provider_results and stop_on_result:
                break

        if cache_results:
            [album.save() for album in results
             if album.mbId and album.release_date and not album.select().where(models.Album.mbId == album.mbId)]

        return results

    @classmethod
    def search_artist(cls, artist, stop_on_result=True, cache_results=True):
        """
        Searches all providers for artists via their ``_search_artist`` method.
        :param artist: Artist to search for
        :param stop_on_result: Whether or not to stop on the first provider to return a result. Defaults to True.
        :param cache_results: Whether or not to cache results. Defaults to True.
        :return: List of artist results
        """
        results = []
        for provider in cls.providers:
            try:
                provider_results = provider._search_artist(artist)
            except NotImplementedError:
                warnings.warn(
                    'Artist search not implemented for {class_name}'.format(class_name=provider.__class__.__name__))
                continue
            results.extend(provider_results)

            if provider_results and stop_on_result:
                break

        if cache_results:
            [artist.save() for artist in results
             if artist.mbId and not artist.select().where(models.Artist.mbId == artist.mbId)]

        return results

    def _search_album(self, album):
        """
        Function to implement to search album
        :param album: Album to search for
        :return: List of Album objects
        """
        raise NotImplementedError()

    def _search_artist(self, artist):
        """
        Function to implement to search artist
        :param artist: Artist to search for
        :return: List of Artist objects
        """
        raise NotImplementedError()


class DatabaseProvider(Provider):
    """
    Provider to get data from cache/data database
    """

    def __init__(self):
        Provider.__init__(self, priority=self.PRIORITY_FIRST)

    def _search_album(self, album):
        """

        :param album:
        :return:
        """
        return models.Album.select().where(models.Album.title.contains(album))

    def _search_artist(self, artist):
        """

        :param artist:
        :return:
        """
        return models.Artist.select().where(models.Artist.artist_name.contains(artist))


class LastFmProvider(Provider):
    """
    Provider to get LastFM data
    """

    def __init__(self, api_key, api_secret):
        """

        :param api_key: LastFM API key
        :param api_secret: LastFM API access secret
        :return:
        """
        Provider.__init__(self)

        # LastFM client
        self._client = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)

    def _search_album(self, album):
        """

        :param album:
        :return:
        """
        raise NotImplementedError()
        results = self._client.search_for_album(album).get_next_page()
        return [self._parse_album(result) for result in results]

    def _search_artist(self, artist):
        """

        :param artist:
        :return:
        """
        results = self._client.search_for_artist(artist).get_next_page()
        return [self._parse_artist(result) for result in results]

    @staticmethod
    def _parse_album(result):
        """
        Parses LastFM response as our artist class
        :param result: LastFM response
        :return: Album corresponding to resposne
        """
        return models.Album(mbId=result.get_mbid(), title=result.title, release_date=result.get_release_date())

    @staticmethod
    def _parse_artist(result):
        """
        Parses LastFM response as our artist class
        :param result: LastFM response
        :return: List of Artists corresponding to response
        """
        return models.Artist(mbId=result.get_mbid(), artist_name=result.name, overview=result.get_bio_summary())


class MusicbrainzProvider(Provider):
    """
    Provider to get Musicbrainz data
    """

    def __init__(self, musicbrainz_server='musicbrainz.org'):
        Provider.__init__(self)
        musicbrainzngs.set_useragent('lidarrmetadata', lidarrmetadata.__version__)
        musicbrainzngs.set_hostname(musicbrainz_server)

    def _search_album(self, album):
        """

        :param album:
        :return:
        """
        results = musicbrainzngs.search_releases(album)['release-list']
        albums = [self._parse_album(result) for result in results]
        return [album for album in albums if album]

    def _search_artist(self, artist):
        """

        :param artist:
        :return:
        """
        results = musicbrainzngs.search_artists(artist)['artist-list']
        return [self._parse_artist(result) for result in results]

    @staticmethod
    def _parse_album(result):
        """
        Parses musicbrainz release to get Album
        :param result: Musicbrainz release result
        :return: Album object corresponding to release
        """
        if 'id' not in result or 'title' not in result or 'date' not in result:
            warnings.warn('Missing field while parsing {result}'.format(result=result))
            return

        return models.Album(mbId=result['id'], title=result['title'], release_date=result['date'])

    @staticmethod
    def _parse_artist(result):
        """
        Parsing of artists returned by musicbrainz api
        :param result: Artist object corresponding to result
        :return:
        """
        return models.Artist(mbId=result['id'], artist_name=result['name'], overview='')


def search_album(album): return Provider.search_album(album)
def search_artist(artist): return Provider.search_artist(artist)


if __name__ == '__main__':
    LastFmProvider(api_key=config.CONFIG.LASTFM_KEY, api_secret=config.CONFIG.LASTFM_SECRET)
    DatabaseProvider()
    MusicbrainzProvider()
    print(Provider.search_artist('afi', cache_results=True, stop_on_result=True))
    print(Provider.search_album('dark side of the moon', cache_results=True, stop_on_result=False))