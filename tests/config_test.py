"""
Testing for config module
"""

import os

import pytest

import lidarrmetadata.config


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


def test_config_override():
    class TestConfig(lidarrmetadata.config.ConfigBase):
        INT = 0
        STR = 'A'
        EMPTY_LIST = []
        STR_LIST = ['a']
        INT_LIST = [0]
        DICT = {'A': 'b'}

    os.environ.setdefault('INT', '1')
    os.environ.setdefault('STR', 'B')
    os.environ.setdefault('EMPTY_LIST', 'a')
    os.environ.setdefault('STR_LIST', 'a:b')
    os.environ.setdefault('INT_LIST', '0:1')
    os.environ.setdefault('DICT__A', 'c')
    os.environ.setdefault('DICT__B', 'd')

    config = TestConfig()

    assert 1 == config.INT
    assert 'B' == config.STR
    assert ['a'] == config.EMPTY_LIST
    assert ['a', 'b'] == config.STR_LIST
    assert [0, 1] == config.INT_LIST
    assert {'A': 'c', 'B': 'd'} == config.DICT


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
    ('Dictionary', 'c', dict, {'A': 'b'}, 'var__A', {'A': 'c'}),
    ('Dictionary integer', '1', dict, {'A': 0}, 'var__A', {'A': 1})
])
def test_parse_env_value(name, env_setting, original_type, original_value, variable_name, expected):
    """
    Tests ``DefaultConfig._parse_env_value``
    """
    result = lidarrmetadata.config.ConfigBase._parse_env_value(env_setting,
                                                               original_type,
                                                               original_value,
                                                               variable_name)
    assert expected == result
