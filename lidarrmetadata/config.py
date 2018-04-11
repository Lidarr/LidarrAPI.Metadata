"""
Lidarr metadata config
"""

import os
import six
import re

from lidarrmetadata import util

# Environment key to use for configuration setting. This environment variable
# may be set to override the default config if no CLI argument is given
ENV_KEY = 'LIDARR_METADATA_CONFIG'

# Dictionary to get a config class based on key. This is automatically
# populated on class creation by ConfigMeta. Keys are the name of the class
# before Config suffix in uppercase
CONFIGS = {}


def split_camel_case(string):
    """
    Splits camel case string into list of strings
    :param string: String to split
    :returns: List of substrings in CamelCase
    """
    return re.sub('([a-z])([A-Z])', r'\1 \2', string).split()


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

                override = self._get_env_override(var)
                print(var, override)

                setattr(self, var, override)

            self.__instance = self

    @classmethod
    def _get_env_override(cls, var):
        """
        Gets the environment variable override value for a variable if it exists or returns the original value
        :param var: Name of variable to check. It will check the environment variable of the same name
        :return: Environment variable of object or original value if environment variable does not exist
        """
        print(var)
        original_value = getattr(cls, var)
        original_type = type(original_value) if original_value is not None else str

        # Parse special types
        env_setting = os.getenv(var, original_value)
        if env_setting != original_value:
            override = cls._parse_env_value(env_setting, original_type, original_value, var)
        elif original_type == dict:
            keys = [key for key in os.environ.keys() if key.startswith(var)]
            override = original_value
            override.update({k.split('__')[1]:
                                 cls._parse_env_value(os.getenv(k),
                                                      type(original_value.get(k, '')),
                                                      original_value.get(k, None),
                                                      k)
                             for k in keys})
        else:
            override = original_value

        return override

    @classmethod
    def _parse_env_value(cls, env_setting, original_type, original_value, variable_name):
        """
        Parses the value of an environment variable according to the type of the original variable
        :param env_setting: Environment setting as string
        :param original_type: Type of original variable
        :param original_value: Value of original variable
        :param variable_name: Name of variable being parsed
        :return:
        """
        # No override if there is no env setting
        if not env_setting:
            return original_value

        if isinstance(original_value, list):
            # Lists are separated with colons such as a:b:c -> ['a', 'b', 'c']
            list_item_type = type(original_value[0]) if original_value else str
            items = util.split_escaped(env_setting, split_char=':')
            override = map(list_item_type, items)
        elif isinstance(original_value, dict):
            # Dicts have each object split into a different variable being the original name plus '__'. For
            # example, DictVar = {'a': 1, 'b': [2,3]} is set in the env as DictVar__a=1 and DictVar__b=2:3.
            override = {k: cls._parse_env_value(env_setting,
                                                type(v),
                                                v,
                                                k)
                        for k, v in original_value.items()}
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
        'FanArtTvProvider': ([FANART_KEY], {}),
        'MusicbrainzDbProvider': ([], {'db_host': 'musicbrainz'}),
        'WikipediaProvider': ([], {})
    }

    # Connection info for sentry
    SENTRY_DSN = ('https://c94975eddcf84d91901ebc1fdba99327:'
                  '605f0689da43434bae633d07c0357c46@sentry.io/215082')

    # Testing mode
    TESTING = False


class TestConfig(DefaultConfig):
    CACHE_CONFIG = {'CACHE_TYPE': 'null'}


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
                print('\t{:24s}{:30s}{}'.format(key, type(value), value))
    return __config


if __name__ == '__main__':
    get_config()
    get_config()
