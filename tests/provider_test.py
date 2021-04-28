# coding=utf-8
import pytest

from lidarrmetadata import provider


class TestWikipediaProvider:
    def setup(self):
        self.provider = provider.WikipediaProvider()

    @pytest.mark.asyncio
    async def test_summary_invalid_url_empty(self):
        assert '' == await self.provider.wikipedia_get_summary_from_title('fakeurl', 'en')
        
    def test_title_from_url_invalid(self):
        with pytest.raises(ValueError):
            self.provider.wikipedia_title_from_url('fakeurl')

    @pytest.mark.parametrize('url,expected', [
        ('http://en.wikipedia.org/wiki/Blink-182', ('Blink-182', 'en')),
        ('https://en.wikipedia.org/wiki/Blink-182', ('Blink-182', 'en')),
        ('http://af.wikipedia.org/wiki/Blink-182', ('Blink-182', 'af')),
        ('https://en.wikipedia.org/wiki/Avenged_Sevenfold', ('Avenged_Sevenfold', 'en')),
        ('https://en.wikipedia.org/wiki/Mumford_%26_Sons', ('Mumford_%26_Sons', 'en')),
        ('https://ja.wikipedia.org/wiki/%CE%9D_(%E3%83%90%E3%83%B3%E3%83%89)', ('%CE%9D_(%E3%83%90%E3%83%B3%E3%83%89)', 'ja')),
        ('https://wikipedia.org/wiki/Toni_Baldwin', ('Toni_Baldwin', 'en')),
        ('https://www.wikipedia.org/wiki/Toni_Baldwin', ('Toni_Baldwin', 'en'))
    ])
    def test_title_from_url(self, url, expected):
        assert expected == self.provider.wikipedia_title_from_url(url)
        
    @pytest.mark.parametrize('url,expected', [
        ('http://en.wikipedia.org/wiki/Blink-182', u'Blink-182 (sometimes written as Blink 182;'),
        ('https://ja.wikipedia.org/wiki/%CE%9D_(%E3%83%90%E3%83%B3%E3%83%89)', u'\u03bd'),
        ('https://de.wikipedia.org/wiki/The_Boys#The_Mattless_Boys', 'The Boys are an English punk rock'),
        ('https://www.wikidata.org/wiki/Q953918', 'Mumford & Sons are an English folk rock band'),
        ('https://www.wikidata.org/wiki/Q127939', 'Russian folk rock band'),
     ])
    @pytest.mark.asyncio
    async def test_summary_from_url(self, url, expected):
        result, expiry = await self.provider.get_artist_overview(url)
        assert result.startswith(expected)
