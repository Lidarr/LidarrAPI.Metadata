import pytest

from lidarrmetadata import util


@pytest.mark.parametrize('dictionary,key,default,expected', [
    ({}, 'a', None, None),                          # Default value
    ({}, 'a', 1, 1),                                # Pass default value
    ({'a': [1, 2]}, 'a', None, 1),                  # Normal usage
    ({'a': 1}, 'a', None, 1),                       # Not list
    ({'a': [[1, 2], [3, 4]]}, 'a', None, [1, 2]),   # Nested list
])
def test_first_key_item(dictionary, key, default, expected):
    assert expected == util.first_key_item(dictionary, key, default)
