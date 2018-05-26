"""
Lidarr metadata config
"""

import os
import six
import re

# Environment key to use for configuration setting. This environment variable
# may be set to override the default config if no CLI argument is given
ENV_KEY = 'LIDARR_METADATA_CONFIG'

# Dictionary to get a config class based on key. This is automatically
# populated on class creation by ConfigMeta. Keys are the name of the class
# before Config suffix in uppercase
CONFIGS = {}


# TODO Move these functions to util once circular dependency is resolved

def first_key(d):
    """
    Gets the first key of a dictionary
    :param d: Dictionary
    :return: First key in dictionary
    """
    return list(d.keys())[0]


def get_index_type(iterable):
    """
    Gets the index type of an iterable. Note that iterables with multiple
    index types are not supported

    :param iterable: Iterable to get index type of
    :return: Type of index of iterable
    """
    if isinstance(iterable, (tuple, list)):
        return int
    elif isinstance(iterable, dict):
        return type(first_key(iterable)) if iterable else None
    else:
        raise ValueError()


def get_value_type(iterable):
    """
    Gets the value type of an iterable. Note that iterables with multiple
    value types are not supported

    :param iterable: Iterable to get value type of
    :return: Value type of iterable
    """
    if isinstance(iterable, (tuple, list)):
        return type(iterable[0])
    elif isinstance(iterable, dict):
        return type(iterable.get(first_key(iterable)))
    else:
        raise ValueError()


def get_nested(iterable, indices, fail_return_first=False):
    """
    Gets a nested value of a series of indices

    :param iterable: Iterable to get value from
    :param indices: Sequence of indices to follow
    :param fail_return_first: Returns first key if an index doesn't exist.
            This is a somewhat dirty way of getting what we need for config.
            Defaults to False
    :return: Value at sequence of indices
    """
    index = get_index_type(iterable)(indices[0])
    if len(indices) > 1:
        return get_nested(iterable[index], indices[1:])
    else:
        if fail_return_first:
            try:
                return iterable[index]
            except IndexError:
                return iterable[0]
            except KeyError:
                return iterable[first_key(iterable)]
        else:
            return iterable[index]


def set_nested(iterable, indices, value):
    """
    Sets a nested value of a series of indices. Note that this will
    edit the iterable in-place since all iterables should be references

    :param iterable: Iterable to set value in
    :param indices: Indices to follow
    :param value: Value to set
    :return:
    """
    index = get_index_type(iterable)(indices[0])
    if len(indices) > 1:
        set_nested(iterable[index], indices[1:], value)
    else:
        if isinstance(iterable, dict):
            iterable.update({index: value})
        elif isinstance(iterable, list):
            if index < len(iterable):
                iterable[index] = value
            else:
                # Add Nones if we have a list. Note that we can't do
                # this for tuples since they're immutable
                set_nested(iterable.append(None), indices, value)
        else:
            iterable[index] = value


def split_camel_case(string):
    """
    Splits camel case string into list of strings
    :param string: String to split
    :returns: List of substrings in CamelCase
    """
    return re.sub('([a-z])([A-Z])', r'\1 \2', string).split()


def split_escaped(string, split_char=' ', escape_char='\\'):
    """
    Splits escaped string

    :param string: String to split
    :param split_char: Character to split on. Defaults to single space
    :param escape_char: Character to escape with. Defaults to \
    """
    ret = []
    current = ''
    skip = False
    for char in string:
        if skip:
            skip = False
            continue
        elif char == escape_char:
            current += split_char
            skip = True
        elif char == split_char:
            if current:
                ret.append(current)

            current = ''
        else:
            current += char

    if current:
        ret.append(current)

    return ret


class ConfigMeta(type):
    """
    Config metaclass to register config classes
    """

    def __init__(cls, name, bases, attr):
        """
        Called upon the creation of a new class
        """
        # Parent initialization
        type.__init__(cls, name, bases, attr)

        # Get key for name
        substrings = split_camel_case(name)
        substrings = substrings[
                     :-1] if substrings[-1].lower() == 'config' else substrings
        key = '_'.join([s.upper() for s in substrings])

        # Register class
        CONFIGS[key] = cls


class ConfigBase(object):
    # Instance so we don't create a new config every time (singleton)
    __instance = None

    def __init__(self):
        """
        Initialization. Uses instance if there is one, otherwise replaces class variables with environment variables
        """
        if self.__instance:
            self = self.__instance
        else:
            for var in dir(self):
                # Make sure it isn't a python special attribute
                if var.upper() != var:
                    continue

                self._set_env_override(var, getattr(self, var))

            self.__instance = self

    @staticmethod
    def _search_env(name):
        """
        Searches env variables for variables matching name and returns a list of indices
        :param name: Name to match
        :return: List of (var, value, [indices]) tuples
        """
        envs = filter(lambda k: k.split('__')[0] == name, os.environ.keys())
        return [{'config_var': var.split('__')[0],
                 'env_var': var,
                 'env_setting': os.getenv(var),
                 'indices': var.split('__')[1:]}
                for var in envs]

    def _set_env_override(self, var, original):
        """
        Gets the environment variable override value for a variable if it exists or returns the original value
        :param var: Name of variable to check. It will check the environment variable of the same name
        :return: Environment variable of object or original value if environment variable does not exist
        """
        original_type = type(original) if original is not None else str

        envs = self._search_env(var)
        override = None
        for env in envs:
            if env['indices']:
                original_value = get_nested(original, env['indices'], True)
                set_nested(original, env['indices'],
                           self._parse_env_value(env['env_setting'], type(original_value), original_value))
            else:
                setting = self._parse_env_value(env['env_setting'], original_type, original)
                setattr(self, var, setting)

        return override

    @classmethod
    def _parse_env_value(cls, env_setting, original_type, original_value):
        """
        Parses the value of an environment variable according to the type of the original variable
        :param env_setting: Environment setting as string
        :param original_type: Type of original variable
        :param original_value: Value of original variable
        :return:
        """
        # No override if there is no env setting
        if not env_setting:
            return original_value

        if isinstance(original_value, (list, tuple)):
            # Lists are separated with colons such as a:b:c -> ['a', 'b', 'c']
            list_item_type = type(original_value[0]) if original_value else str
            items = split_escaped(env_setting, split_char=':')
            override = original_type(map(list_item_type, items))
        elif isinstance(original_value, bool):
            return env_setting.lower() == 'true'
        else:
            override = original_type(env_setting)
        return override


class DefaultConfig(six.with_metaclass(ConfigMeta, ConfigBase)):
    """
    Base configuration class to define default values. All possible config
    values should be defined in this class to avoid KeyErrors or unexpected
    missing values. Explanation for the functionality of each configuration
    value should be provided above the variable and options should be listed
    in alphabetical order.

    Note that for the environmental override system to work correctly, keys
    in dictionary config variables should be capitalized.
    """

    APPLICATION_ROOT = None

    BLACKLISTED_ARTISTS = [
        'f731ccc4-e22a-43af-a747-64213329e088',  # [anonymous]
        '33cf029c-63b0-41a0-9855-be2a3665fb3b',  # [data]
        '314e1c25-dde7-4e4d-b2f4-0a7b9f7c56dc',  # [dialogue]
        'eec63d3c-3b81-4ad4-b1e4-7c147d4d2b61',  # [no artist]
        '9be7f096-97ec-4615-8957-8d40b5dcbc41',  # [traditional]
        '125ec42a-7229-4250-afc5-e057484327fe',  # [unknown]
        '89ad4ac3-39f7-470e-963a-56509c546377',  # Various Artists
    ]

    # Cache options
    USE_CACHE = True
    CACHE_CONFIG = {
        'CACHE_TYPE': 'redis',
        'CACHE_DEFAULT_TIMEOUT': 60 * 60 * 24,
        'CACHE_KEY_PREFIX': 'lidarrmetadata',
        'CACHE_REDIS_HOST': 'redis'
    }

    # File to use for DB
    DB_FILE = os.path.abspath('./music-metadata.db')

    # Debug mode
    DEBUG = False

    # Fanart.tv API credentials
    FANART_KEY = ''

    # Port to use
    HTTP_PORT = 5001

    # LastFM API connection details
    LASTFM_KEY = ''
    LASTFM_SECRET = ''

    # Whether or not running in production
    PRODUCTION = False

    # Provider -> (args, kwargs) dictionaries
    PROVIDERS = {
        'FANARTTVPROVIDER': ([FANART_KEY], {}),
        'MUSICBRAINZDBPROVIDER': ([], {'DB_HOST': 'musicbrainz'}),
        'WIKIPEDIAPROVIDER': ([], {})
    }

    # Connection info for sentry
    SENTRY_DSN = ('https://c94975eddcf84d91901ebc1fdba99327:'
                  '605f0689da43434bae633d07c0357c46@sentry.io/215082')
    SENTRY_ENABLE = True

    # Testing mode
    TESTING = False


class TestConfig(DefaultConfig):
    CACHE_CONFIG = {'CACHE_TYPE': 'null'}
    SENTRY_ENABLE = False
    Testing = True


__config = None


def get_config():
    global __config
    if not __config:
        config_key = os.environ.get(ENV_KEY, 'DEFAULT').upper()
        __config = CONFIGS[config_key]()

        # TODO Replace with logging functions when we improve logging
        print('Initializing config {} from environment {}={}'.format(__config.__class__.__name__, ENV_KEY, config_key))
        for key in dir(__config):
            if key == key.upper():
                value = getattr(__config, key)
                print('\t{:24s}{:30s}{}'.format(key, str(type(value)), value))
    return __config


if __name__ == '__main__':
    get_config()
    get_config()
