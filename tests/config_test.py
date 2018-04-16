"""
Testing for config module
"""

import os

import pytest

import lidarrmetadata.config


@pytest.mark.parametrize('iterable,expected', [
    ([], int),
    (tuple(), int),
    ({'A': 0}, str),
    ({'A': 'A'}, str)
])
def test_get_index_type(iterable, expected):
    result = lidarrmetadata.config.get_index_type(iterable)
    assert expected == result


@pytest.mark.parametrize('iterable,expected', [
    ([0], int),
    ((0,), int),
    ({'A': 0}, int),
    ({'A': 'A'}, str)
])
def test_get_value_type(iterable, expected):
    result = lidarrmetadata.config.get_value_type(iterable)
    assert expected == result


@pytest.mark.parametrize('iterable,indices,expected', [
    ([0], ['0'], 0),
    ([[0]], ['0', '0'], 0),
    ({'A': [1, 2]}, ['A', '1'], 2),
    (({'A': 0}, [1, 2]), [1, 1], 2)
])
def test_get_nested(iterable, indices, expected):
    result = lidarrmetadata.config.get_nested(iterable, indices)
    assert expected == result


@pytest.mark.parametrize('iterable,indices,value,expected', [
    ([0], ['0'], 1, [1]),
    ([[0]], ['0', '0'], 1, [[1]]),
    ({'A': [1, 2]}, ['A', '1'], 3, {'A': [1, 3]}),
    (({'A': 0}, [1, 2]), [1, 1], 3, ({'A': 0}, [1, 3])),
    ({'A': 0}, ['B'], 1, {'A': 0, 'B': 1})
])
def test_set_nested(iterable, indices, value, expected):
    lidarrmetadata.config.set_nested(iterable, indices, value)
    assert expected == iterable


@pytest.mark.parametrize('name,string,split_char,expected', [
    ('No escape', 'a:b', ':', ['a', 'b']),
    ('No escape multiple chars', 'ab:cd', ':', ['ab', 'cd']),
    ('Multiple no escape', 'a:b:c', ':', ['a', 'b', 'c']),
    ('Single escape', 'a\:b', ':', ['a:b']),
    ('Single escape multiple chars', 'ab\:cd', ':', ['ab:cd']),
    ('Multiple escape', 'a\:b\:c', ':', ['a:b:c']),
    ('Mixed escaped', 'a\\:b:c', ':', ['a:b', 'c']),
    ('Beginning no escape', ':a', ':', ['a']),
    ('Beginning escape', '\:a', ':', [':a']),
    ('Ending no escape', 'a:', ':', ['a']),
    ('Ending escape', 'a\:', ':', ['a:'])
])
def test_split_escaped(name, string, split_char, expected):
    result = lidarrmetadata.config.split_escaped(string, split_char=split_char)
    assert expected == result


@pytest.mark.parametrize('envs,values,expected', [
    (['A'], ['value'], [{'config_var': 'A', 'env_var': 'A', 'env_setting': 'value', 'indices': []}]),
    (['A__B'], ['value'], [{'config_var': 'A', 'env_var': 'A__B', 'env_setting': 'value', 'indices': ['B']}]),
    (
            ['A__B__0'], ['value'],
            [{'config_var': 'A', 'env_var': 'A__B__0', 'env_setting': 'value', 'indices': ['B', '0']}]),
    (['A__B', 'A__C'], ['value1', 'value2'],
     [{'config_var': 'A', 'env_var': 'A__B', 'env_setting': 'value1', 'indices': ['B']},
      {'config_var': 'A', 'env_var': 'A__C', 'env_setting': 'value2', 'indices': ['C']}])
])
def test_search_env(envs, values, expected):
    # Patch environment
    old_environ = os.environ
    os.environ = {var: value for var, value in zip(envs, values)}

    result = lidarrmetadata.config.ConfigBase._search_env(envs[0].split('__')[0])

    # Restore original env
    os.environ = old_environ

    assert sorted(expected, key=lambda i: i['env_var']) == sorted(result, key=lambda i: i['env_var'])

def test_config_override():
    class TestConfig(lidarrmetadata.config.ConfigBase):
        INT = 0
        STR = 'A'
        EMPTY_LIST = []
        STR_LIST = ['a']
        INT_LIST = [0]
        DICT = {'A': 'b'}
        TUPLE = ('a', 'b')

    os.environ.setdefault('INT', '1')
    os.environ.setdefault('STR', 'B')
    os.environ.setdefault('EMPTY_LIST', 'a')
    os.environ.setdefault('STR_LIST', 'a:b')
    os.environ.setdefault('INT_LIST', '0:1')
    os.environ.setdefault('DICT__A', 'c')
    os.environ.setdefault('DICT__B', 'd')
    os.environ.setdefault('TUPLE', 'c:d')

    config = TestConfig()

    assert 1 == config.INT
    assert 'B' == config.STR
    assert ['a'] == config.EMPTY_LIST
    assert ['a', 'b'] == config.STR_LIST
    assert [0, 1] == config.INT_LIST
    assert {'A': 'c', 'B': 'd'} == config.DICT
    assert ('c', 'd') == config.TUPLE


@pytest.mark.parametrize('name,env_setting,original_type,original_value,variable_name,expected', [
    ('No override', '', str, 'ABC', 'var', 'ABC'),
    ('None', '1', str, None, 'var', '1'),
    ('Bool True', 'True', bool, False, 'var', True),
    ('Bool', 'False', bool, True, 'var', False),
    ('String', 'DEF', str, 'ABC', 'var', 'DEF'),
    ('Integer', '1', int, 0, 'var', 1),
    ('Float', '1.2', float, 1.0, 'var', 1.2),
    ('Empty List', 'a:b:c', list, [], 'var', ['a', 'b', 'c']),
    ('List single', 'a', list, ['b'], 'var', ['a']),
    ('List with colon', r'a\:b', list, ['a'], 'var', ['a:b']),
    ('Integer list', '1:2', list, [0], 'var', [1, 2]),
    ('Tuple', '1:2', tuple, (0, 1), 'var', (1, 2)),
    ('Empty tuple', 'a', tuple, (), 'var', ('a',)),
])
def test_parse_env_value(name, env_setting, original_type, original_value, variable_name, expected):
    """
    Tests ``DefaultConfig._parse_env_value``
    """
    result = lidarrmetadata.config.ConfigBase._parse_env_value(env_setting,
                                                               original_type,
                                                               original_value)
    assert expected == result
