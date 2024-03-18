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

    ROOT_PATH = ''

    BLACKLISTED_ARTISTS = [
        'f731ccc4-e22a-43af-a747-64213329e088',  # [anonymous]
        '33cf029c-63b0-41a0-9855-be2a3665fb3b',  # [data]
        '314e1c25-dde7-4e4d-b2f4-0a7b9f7c56dc',  # [dialogue]
        'eec63d3c-3b81-4ad4-b1e4-7c147d4d2b61',  # [no artist]
        '9be7f096-97ec-4615-8957-8d40b5dcbc41',  # [traditional]
        '125ec42a-7229-4250-afc5-e057484327fe',  # [unknown]
        '89ad4ac3-39f7-470e-963a-56509c546377',  # Various Artists
    ]
    
    # Host definitions used elsewhere
    REDIS_HOST = 'redis'
    REDIS_PORT = 6379
    POSTGRES_CACHE_HOST = 'db'
    POSTGRES_CACHE_PORT = 5432

    # TTL set in Cache-Control headers.  Use 0 to disable caching.
    # The GOOD value is used if we got info from all providers
    # The BAD value is used if some providers were unavailable but
    # there was enough information to return a useful response
    # (e.g. we are missing overviews or images)
    DAYS = 60 * 60 * 24
    
    USE_CACHE = True
    CACHE_TTL = {
        'cloudflare': DAYS * 30,
        'changes': 60,
        'chart': DAYS * 1,
        'provider_error': 60 * 30,
        'redis': DAYS * 7,
        'fanart': DAYS * 30,
        'tadb': DAYS * 30,
        'wikipedia': DAYS * 7
    }
    
    CACHE_CONFIG = {
        'default': {
            'cache': 'aiocache.RedisCache',
            'endpoint': REDIS_HOST,
            'port': REDIS_PORT,
            'namespace': 'lm3.7',
            'serializer': {
                'class': 'lidarrmetadata.cache.CompressionSerializer'
            },
        },
        'fanart': {
            'cache': 'lidarrmetadata.cache.PostgresCache',
            'endpoint': POSTGRES_CACHE_HOST,
            'port': POSTGRES_CACHE_PORT,
            'db_table': 'fanart',
            'timeout': 0,
        },
        'tadb': {
            'cache': 'lidarrmetadata.cache.PostgresCache',
            'endpoint': POSTGRES_CACHE_HOST,
            'port': POSTGRES_CACHE_PORT,
            'db_table': 'tadb',
            'timeout': 0,
        },
        'wikipedia': {
            'cache': 'lidarrmetadata.cache.PostgresCache',
            'endpoint': POSTGRES_CACHE_HOST,
            'port': POSTGRES_CACHE_PORT,
            'db_table': 'wikipedia',
            'timeout': 0,
        },
        'artist': {
            'cache': 'lidarrmetadata.cache.PostgresCache',
            'endpoint': POSTGRES_CACHE_HOST,
            'port': POSTGRES_CACHE_PORT,
            'db_table': 'artist',
            'timeout': 0,
        },
        'album': {
            'cache': 'lidarrmetadata.cache.PostgresCache',
            'endpoint': POSTGRES_CACHE_HOST,
            'port': POSTGRES_CACHE_PORT,
            'db_table': 'album',
            'timeout': 0,
        },
        'spotify': {
            'cache': 'lidarrmetadata.cache.PostgresCache',
            'endpoint': POSTGRES_CACHE_HOST,
            'port': POSTGRES_CACHE_PORT,
            'db_table': 'spotify',
            'timeout': 0,
        }
    }

    CRAWLER_BATCH_SIZE = {
        'wikipedia': 50,
        'fanart': 500,
        'tadb': 500,
        'artist': 100,
        'album': 100
    }
    
    NULL_CACHE_CONFIG = {
        'default': {
            'cache': 'lidarrmetadata.cache.NullCache',
        },
        'fanart': {
            'cache': 'lidarrmetadata.cache.NullCache',
            'serializer': {
                'class': 'lidarrmetadata.cache.ExpirySerializer'
            },
        },
        'tadb': {
            'cache': 'lidarrmetadata.cache.NullCache',
            'serializer': {
                'class': 'lidarrmetadata.cache.ExpirySerializer'
            },
        },
        'wikipedia': {
            'cache': 'lidarrmetadata.cache.NullCache',
            'serializer': {
                'class': 'lidarrmetadata.cache.ExpirySerializer'
            }
        },
        'artist': {
            'cache': 'lidarrmetadata.cache.NullCache',
            'serializer': {
                'class': 'lidarrmetadata.cache.ExpirySerializer'
            }

        },
        'album': {
            'cache': 'lidarrmetadata.cache.NullCache',
            'serializer': {
                'class': 'lidarrmetadata.cache.ExpirySerializer'
            }
        },
        'spotify': {
            'cache': 'lidarrmetadata.cache.NullCache',
            'serializer': {
                'class': 'lidarrmetadata.cache.ExpirySerializer'
            }
        }
    }
    
    # Debug mode
    DEBUG = False

    # Enable sending stats
    ENABLE_STATS = True

    # External request parameters
    # Class of limiter
    EXTERNAL_LIMIT_CLASS = 'NullRateLimiter'
    # Size of rate limit queue
    EXTERNAL_LIMIT_QUEUE_SIZE = 60
    # Rate limit time delta in ms
    EXTERNAL_LIMIT_TIME_DELTA = 1000
    # Request timeout in ms
    EXTERNAL_TIMEOUT = 250

    # Redis db if using RedisRateLimiter
    EXTERNAL_LIMIT_REDIS_DB = 10
    # Redis host if using RedisRateLimiter
    EXTERNAL_LIMIT_REDIS_HOST = REDIS_HOST
    # Redis port if using RedisRateLimiter
    EXTERNAL_LIMIT_REDIS_PORT = REDIS_PORT

    # Fanart.tv API credentials
    FANART_KEY = ''
    # The API for standard keys is supposed to be delayed by 7 days but
    # in practise it appears the lag is slightly more
    FANART_API_DELAY_SECONDS = 8 * 24 * 60 * 60

    # TADB API credentials
    TADB_KEY = '1'

    # Port to use
    HTTP_PORT = 5001

    # LastFM API connection details
    LASTFM_KEY = ''
    LASTFM_SECRET = ''

    # Spotify app details
    SPOTIFY_REDIRECT_URL = ''
    SPOTIFY_ID = 'replaceme'
    SPOTIFY_SECRET = 'replaceme'
    SPOTIFY_MATCH_MIN_RATIO = 0.8

    # Whether or not running in production
    PRODUCTION = False

    # Provider -> (args, kwargs) dictionaries
    PROVIDERS = {
        'MUSICBRAINZDBPROVIDER': ([], {'DB_HOST': 'db', 'DB_PORT': 5432}),
        'SOLRSEARCHPROVIDER': ([], {'SEARCH_SERVER': 'http://solr:8983/solr'}),
        'FANARTTVPROVIDER': ([FANART_KEY], {}),
        'WIKIPEDIAPROVIDER': ([], {}),
        'THEAUDIODBPROVIDER': ([TADB_KEY], {}),
        'SPOTIFYAUTHPROVIDER': ([], {'CLIENT_ID': SPOTIFY_ID, 'CLIENT_SECRET': SPOTIFY_SECRET, 'REDIRECT_URI': SPOTIFY_REDIRECT_URL}),
        'SPOTIFYPROVIDER': ([], {'CLIENT_ID': SPOTIFY_ID, 'CLIENT_SECRET': SPOTIFY_SECRET})
    }

    # Connection info for sentry. Defaults to None, in which case Sentry won't be used
    SENTRY_DSN = None

    # Redis connection info for sentry event processor. No redis connection info will fall back to a local processor
    SENTRY_REDIS_HOST = REDIS_HOST
    SENTRY_REDIS_PORT = REDIS_PORT

    # Sentry rate limit TTL in seconds
    SENTRY_TTL = 1

    # Stats server
    STATS_HOST = 'telegraf'
    STATS_PORT = 8092
    
    # Cloudflare details for invalidating cache on update
    CLOUDFLARE_ZONE_ID = ''
    CLOUDFLARE_AUTH_EMAIL = ''
    CLOUDFLARE_AUTH_KEY = ''
    CLOUDFLARE_URL_BASE = ''
    INVALIDATE_APIKEY = 'replaceme'

    # Testing mode
    TESTING = False

    # Hosted cache for third-party images
    IMAGE_CACHE_HOST = "imagecache.lidarr.audio"

    # Number of concurrent TADB connections for crawler
    TADB_CONNECTIONS = 5


class TestConfig(DefaultConfig):
    USE_CACHE = False
    ENABLE_STATS = False
    EXTERNAL_LIMIT_CLASS = 'NullRateLimiter'
    SENTRY_REDIS_HOST = None
    SENTRY_REDIS_PORT = None
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
