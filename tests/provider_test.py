# coding=utf-8
import pytest


from lidarrmetadata import config
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

    @staticmethod
    @pytest.mark.parametrize('query,mbid', [
        ('blink-182', '0743b15a-3c32-48c8-ad58-cb325350befa'),
        ("Snail’s House", 'cfd45526-701e-457a-b3bd-013506a890a6'),
        ("Snail's House", 'cfd45526-701e-457a-b3bd-013506a890a6'),
        ('Yukihiro Fukotomi', '5ae575a5-3c2d-4cbb-9fe5-be806d5946ae'),
        ('福富幸宏', '5ae575a5-3c2d-4cbb-9fe5-be806d5946ae'),
        ('Yasuyuki Okamura', 'da3d15ea-4011-4cc7-bd73-b4192891c1d4'),
        ('岡村靖幸', 'da3d15ea-4011-4cc7-bd73-b4192891c1d4'),
        ('Кипелов', '76f95aaa-9be1-47a1-8db8-731cb77cf938'),
    ])
    def test_search_artist(query, mbid):
        args, kwargs = config.TestConfig.PROVIDERS['MUSICBRAINZDBPROVIDER']
        kwargs = {k.lower(): v for k, v in kwargs.items()}
        db_provider = provider.MusicbrainzDbProvider(*args, **kwargs)
        results = db_provider.search_artist_name(query)
        print(results)
        assert mbid in map(lambda r: r['Id'], results)

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
