# coding=utf-8
import pytest


from lidarrmetadata import api # This is imported so the flask app initializes and cache doesn't fail
from lidarrmetadata import provider


class TestMusicbrainzDbProvider:

    @staticmethod
    @pytest.mark.parametrize('s,expected', [
        ('abc', 'abc'),
        # ('blink‐182', 'blink-182'),
        (u'blink‐182', 'blink-182'),
        (u'blink\u2010182', 'blink-182'),
        ('...', '...')
    ])
    def test_mb_decode(s, expected):
        result = provider.MusicbrainzDbProvider().mb_decode(s)
        assert expected == result

    @staticmethod
    @pytest.mark.parametrize('s,expected', [
        ('abc', 'abc'),
        # ('blink-182', 'blink‐182'),
        ('blink-182', u'blink‐182'),
        ('blink-182', u'blink\u2010182'),
        ('...', '...')
    ])
    def test_mb_encode(s, expected):
        result = provider.MusicbrainzDbProvider().mb_encode(s)
        assert expected == result


class TestWikipediaProvider:
    def setup(self):
        self.provider = provider.WikipediaProvider()

    def test_summary_invalid_url_empty(self):
        assert '' == self.provider.get_summary('fakeurl', 'en')

    @pytest.mark.parametrize('url,expected', [
        ('http://en.wikipedia.org/wiki/Blink-182', ('Blink-182', 'en')),
        ('https://en.wikipedia.org/wiki/Blink-182', ('Blink-182', 'en')),
        ('http://af.wikipedia.org/wiki/Blink-182', ('Blink-182', 'af')),
        ('https://en.wikipedia.org/wiki/Avenged_Sevenfold', ('Avenged_Sevenfold', 'en')),
        ('https://en.wikipedia.org/wiki/Mumford_%26_Sons', ('Mumford_%26_Sons', 'en')),
        ('https://ja.wikipedia.org/wiki/%CE%9D_(%E3%83%90%E3%83%B3%E3%83%89)', ('%CE%9D_(%E3%83%90%E3%83%B3%E3%83%89)', 'ja'))
    ])
    def test_title_from_url(self, url, expected):
        assert expected == self.provider.title_from_url(url)
        
    @pytest.mark.parametrize('url', [
         ('http://en.wikipedia.org/wiki/Blink-182'),
         ('https://ja.wikipedia.org/wiki/%CE%9D_(%E3%83%90%E3%83%B3%E3%83%89)'),
         ('https://de.wikipedia.org/wiki/The_Boys#The_Mattless_Boys'),
         ('https://www.wikidata.org/wiki/Q953918'),
     ])
    def test_summary_from_url(self, url):
        assert self.provider.get_artist_overview(url) != ''
        
    @pytest.mark.parametrize('url,expected', [
        ('https://www.wikidata.org/wiki/Q953918', 'Mumford%20%26%20Sons'),
        ('https://www.wikidata.org/wiki/Q19873750', 'B%C3%B8rns'),
        ('https://www.wikidata.org/wiki/Q236762', 'Mari%C3%A9%20Digby'),
        # This one has no english wiki page
        ('https://www.wikidata.org/wiki/Q127939', '')
    ])
    def test_get_wikipedia_title(self, url, expected):
        assert self.provider.get_wikipedia_title(url) == expected

    def test_title_from_url_invalid(self):
        with pytest.raises(ValueError):
            self.provider.title_from_url('fakeurl')
