"""
Tests api functionality
"""

import pytest
import quart
from werkzeug.exceptions import BadRequest

import lidarrmetadata.app


@pytest.mark.parametrize('s,expected', [
    ('abc  ', 'abc'),
    (' abc', 'abc'),
    ('abc\n', 'abc'),
    ('abc\t', 'abc'),
    ('abc\x00', 'abc')
])
@pytest.mark.asyncio
async def test_get_search_query(s, expected):
    async with lidarrmetadata.app.app.test_request_context('/search?type=album&query=' + s):
        result = lidarrmetadata.app.get_search_query()
    assert expected == result


@pytest.mark.asyncio
async def test_get_search_query_blank():
    async with lidarrmetadata.app.app.test_request_context('/search?type=album&query='):
        with pytest.raises(BadRequest) as e:
            lidarrmetadata.app.get_search_query()
            assert e.code == 400
