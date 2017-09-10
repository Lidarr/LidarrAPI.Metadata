"""
Lidarr metadata config
"""

import os
import re
import sys

from lidarrmetadata import provider

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


class DefaultConfig(object):
    """
    Base configuration class to define default values. All possible config
    values should be defined in this class to avoid KeyErrors or unexpected
    missing values. Explanation for the functionality of each configuration
    value should be provided above the variable and options should be listed
    in alphabetical order.
    """
    __metaclass__ = ConfigMeta

    APPLICATION_ROOT = None

    # File to use for DB
    DB_FILE = os.path.abspath('./music-metadata.db')

    # Debug mode
    DEBUG = False

    # Fanart.tv API credentials
    FANART_KEY = ''

    # LastFM API connection details
    LASTFM_KEY = ''
    LASTFM_SECRET = ''

    # Whether or not running in production
    PRODUCTION = False

    # List of providers
    PROVIDERS = [provider.FanArtTvProvider(FANART_KEY),
                provider.MusicbrainzApiProvider(),
                 provider.WikipediaProvider()],

    # Testing mode
    TESTING = False


CONFIG = CONFIGS.get(os.getenv(ENV_KEY), DefaultConfig)
