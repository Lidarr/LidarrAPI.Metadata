import pylast

from lidarrmetadata import models


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
    def search_artist(cls, artist, stop_on_result=True, cache_results=False):
        """
        Searches all providers for artists via their ``_search_artist`` method.
        :param artist: Artist to search for
        :param stop_on_result: Whether or not to stop on the first provider to return a result. Defaults to True.
        :param cache_results: Whether or not to cache results. Defaults to False.
        :return: List of artist results
        """
        results = []
        for provider in cls.providers:
            provider_results = provider._search_artist(artist)
            results.extend(provider_results)

            if provider_results and stop_on_result:
                break

        if cache_results:
            [artist.save() for artist in results if artist.mbId]

        return results

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

    def _search_artist(self, artist):
        """

        :param artist:
        :return:
        """
        results = self._client.search_for_artist(artist).get_next_page()
        return [self._parse_artist(result) for result in results]

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

    def __init__(self):
        Provider.__init__()

    def _search_artist(self, artist):
        """

        :param artist:
        :return:
        """
        raise NotImplementedError()


if __name__ == '__main__':
    LASTFM_KEY = ''
    LASTFM_SECRET = ''
    LastFmProvider(api_key=LASTFM_KEY, api_secret=LASTFM_SECRET)
    DatabaseProvider()
    print(Provider.search_artist('afi', cache_results=True))
