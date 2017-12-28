import unittest

import pytest

from lidarrmetadata import util


@pytest.mark.parametrize('dictionary,key,default,expected', [
    ({}, 'a', None, None),  # Default value
    ({}, 'a', 1, 1),  # Pass default value
    ({'a': [1, 2]}, 'a', None, 1),  # Normal usage
    ({'a': 1}, 'a', None, 1),  # Not list
    ({'a': [[1, 2], [3, 4]]}, 'a', None, [1, 2]),  # Nested list
])
def test_first_key_item(dictionary, key, default, expected):
    assert expected == util.first_key_item(dictionary, key, default)


@pytest.mark.parametrize('iterable,func,types,expected', [
    ({'a': 1}, lambda _: 2, object, {'a': 2}),
    ({'a': 1}, lambda _: 2, str, {'a': 1}),
    ({'a': 1, 2: 'b'}, lambda s: s.upper(), str, {'a': 1, 2: 'B'}),
    ([1, 2, 3], lambda i: i + 1, int, [2, 3, 4]),
    ((1, 2, 3), lambda i: i + 1, object, (2, 3, 4)),
    (['a', 1, [1, 2]], lambda _: 2, int, ['a', 2, [2, 2]]),
    ([[1, 2]], lambda i: i + 1, int, [[2, 3]]),
    (['a', 1, 1.1], lambda _: 2, [int, float], ['a', 2, 2])
])
def test_map_iterable_values(iterable, func, types, expected):
    result = util.map_iterable_values(iterable, func, types)
    assert expected == result


@pytest.mark.parametrize('string,table,expected', [
    ('abc', {'a': 'q'}, 'qbc'),
    ('abc', {'a': 'qw'}, 'qwbc'),
    ('abc', {'ab': 'QW'}, 'abc')  # Doesn't support 2-character in source at the moment
])
def test_translate_string(string, table, expected):
    result = util.translate_string(string, table)
    assert expected == result


class BidirectionalDictionaryTest(unittest.TestCase):
    def setUp(self):
        self.d = util.BidirectionalDictionary({'a': 1, 'b': 2})

    def test_regular_access(self):
        assert self.d['a'] == 1
        assert self.d['b'] == 2

    def test_regular_set(self):
        assert self.d['a'] == 1
        self.d['a'] = 2
        assert self.d['a'] == 2

    def test_inverse_access(self):
        assert self.d.inverse[1] == 'a'
        assert self.d.inverse[2] == 'b'

    def test_inverse_set(self):
        assert self.d.inverse[1] == 'a'
        self.d['a'] = 2
        assert self.d.inverse[2] == 'a'
