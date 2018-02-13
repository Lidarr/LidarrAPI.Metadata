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


def split_camel_case(string):
    """
    Splits camel case string into list of strings
    :param string: String to split
    :returns: List of substrings in CamelCase
    """
    return re.sub('([a-z])([A-Z])', r'\1 \2', string).split()


class EnvironmentOverride(type):
    """
    Metaclass to override variables with environment variables if they exist
    """

    def __init__(cls, name, bases, attr):
        type.__init__(cls, name, bases, attr)

        for var in dir(cls):
            # Make sure it isn't a python special attribute
            if var.split('__')[0] == var.split('__')[-1] == '':
                continue

            override = os.getenv(var, getattr(cls, var))
            setattr(cls, var, override)


class ConfigMeta(EnvironmentOverride):
    """
    Config metaclass to register config classes
    """

    def __init__(cls, name, bases, attr):
        """
        Called upon the creation of a new class
        """
        # Parent initialization
        EnvironmentOverride.__init__(cls, name, bases, attr)

        # Get key for name
        substrings = split_camel_case(name)
        substrings = substrings[
                     :-1] if substrings[-1].lower() == 'config' else substrings
        key = '_'.join([s.upper() for s in substrings])

        # Register class
        CONFIGS[key] = cls


class DefaultConfig(six.with_metaclass(ConfigMeta, object)):
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
        'CACHE_REDIS_HOST': 'localhost'
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
        'MusicbrainzDbProvider': ([], {}),
        'WikipediaProvider': ([], {})
    }

    # Connection info for sentry
    SENTRY_DSN = ('https://c94975eddcf84d91901ebc1fdba99327:'
                  '605f0689da43434bae633d07c0357c46@sentry.io/215082')

    # Testing mode
    TESTING = False

class TestConfig(DefaultConfig):
    CACHE_CONFIG = {'CACHE_TYPE': 'null'}

CONFIG = CONFIGS.get(os.getenv(ENV_KEY), DefaultConfig)
