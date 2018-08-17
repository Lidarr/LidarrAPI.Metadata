"""
Tests api functionality
"""

import pytest
import werkzeug.exceptions

import lidarrmetadata.api


@pytest.mark.parametrize('s,expected', [
    ('abc  ', 'abc'),
    (' abc', 'abc'),
    ('abc\n', 'abc'),
    ('abc\t', 'abc'),
    ('abc\x00', 'abc')
])
def test_get_search_query(s, expected):
    with lidarrmetadata.api.app.test_request_context('/search?type=album&query=' + s):
        result = lidarrmetadata.api.get_search_query()
    assert expected == result


def test_get_search_query_blank():
    with lidarrmetadata.api.app.test_request_context('/search?type=album&query='):
        with pytest.raises(werkzeug.exceptions.HTTPException) as e:
            lidarrmetadata.api.get_search_query()
            assert e.code == 400
