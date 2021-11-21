import pytest

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

@pytest.fixture(scope='function')
def patch_search_provider(monkeypatch):
    monkeypatch.setattr(provider, 'get_providers_implementing', lambda x: [NullSearchProvider()])

@pytest.mark.asyncio
async def test_billboard_200_albums_chart(patch_search_provider):
    await chart.get_billboard_200_albums_chart()

@pytest.mark.asyncio
async def test_billboard_100_artists_chart(patch_search_provider):
    await chart.get_billboard_100_artists_chart()