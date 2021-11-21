import pytest

from lidarrmetadata import config
from lidarrmetadata import chart
from lidarrmetadata import provider

class NullSearchProvider(provider.SolrSearchProvider):
    """
    This is a pretty sketchy way to test these charts, but some of them have a habit of changing. This will at
    least allow us to ensure that they work without the complexity of end to end testing.
    """
    async def search_album_name(self, *args, **kwargs):
        return []
    async def search_artist_name(self, *args, **kwargs):
            return []

class NullRGProvider(provider.ReleaseGroupByIdMixin):
    async def map_query(self, *args, **kwargs):
        return []

    async def get_release_group_id_from_spotify_id(self, spotify_id):
        return None

    async def get_release_groups_by_id(self, rgids):
        return []

    async def redirect_old_release_group_id(self, artist_id):
        return None

@pytest.fixture(scope='function')
def patch_search_provider(monkeypatch):
    before_patch = provider.get_providers_implementing
    def patched_providers(x):
        if x in NullSearchProvider.__mro__:
            return [NullSearchProvider()]
        elif x in NullRGProvider.__mro__:
            return [NullRGProvider()]

        return before_patch(x)

    monkeypatch.setattr(provider, 'get_providers_implementing', patched_providers)

@pytest.mark.asyncio
async def test_billboard_200_albums_chart(patch_search_provider):
    await chart.get_billboard_200_albums_chart()

@pytest.mark.asyncio
async def test_billboard_100_artists_chart(patch_search_provider):
    await chart.get_billboard_100_artists_chart()

@pytest.mark.asyncio
async def test_apple_music_top_albums_chart(patch_search_provider):
    await chart.get_apple_music_top_albums_chart()

@pytest.mark.skipif(config.get_config().LASTFM_KEY == '', reason='No LastFM key available')
@pytest.mark.asyncio
async def test_lastfm_albums_chart(patch_search_provider):
    await chart.get_lastfm_album_chart()

@pytest.mark.skipif(config.get_config().LASTFM_KEY == '', reason='No LastFM key available')
@pytest.mark.asyncio
async def test_lastfm_artists_chart(patch_search_provider):
    await chart.get_lastfm_artist_chart()
