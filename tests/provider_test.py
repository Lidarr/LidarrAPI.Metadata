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
