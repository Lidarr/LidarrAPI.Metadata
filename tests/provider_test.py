# coding=utf-8
import pytest

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
        assert '' == self.provider.get_summary('fakeurl')

    @pytest.mark.parametrize('url,expected', [
        ('http://en.wikipedia.org/wiki/Blink-182', 'Blink-182'),
        ('https://en.wikipedia.org/wiki/Blink-182', 'Blink-182'),
        ('http://af.wikipedia.org/wiki/Blink-182', 'Blink-182'),
        ('https://en.wikipedia.org/wiki/Avenged_Sevenfold', 'Avenged_Sevenfold'),
        ('https://en.wikipedia.org/wiki/Mumford_%26_Sons', 'Mumford_&_Sons')
    ])
    def test_title_from_url(self, url, expected):
        assert expected == self.provider.title_from_url(url)

    def test_title_from_url_invalid(self):
        with pytest.raises(ValueError):
            self.provider.title_from_url('fakeurl')
