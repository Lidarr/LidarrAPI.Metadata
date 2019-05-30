"""
Utility functionality that isn't specific to a given module
"""

import abc
import time

import functools
import redis

from lidarrmetadata import config
from lidarrmetadata import cache

# Cache for application
CACHE = cache.LidarrCache(config=config.get_config().REDIS_CACHE_CONFIG)
FANART_CACHE = cache.LidarrCache(config=config.get_config().FANART_CACHE_CONFIG)
WIKI_CACHE = cache.LidarrCache(config=config.get_config().WIKI_CACHE_CONFIG)

def cache_or_call(func, *args, **kwargs):
    """
    Gets cache result or calls function with args and kwargs
    :param func: Function to call
    :param args: Args to call func with
    :param kwargs: Kwargs to call func with
    :return: Result of func(*args, **kwargs)
    """
    # This may not work well if args or kwargs contain objects, but we don't need to handle that at the moment
    key = str((function_hash(func), repr(args), repr(kwargs)))
    ret = CACHE.get(key)
    if not ret:
        ret = func(*args, **kwargs)
        CACHE.set(key, ret)

    return ret


def first_key_item(dictionary, key, default=None):
    """
    Gets the first item from a dictionary key that returns a list
    :param dictionary: Dictionary to get item from
    :param key: Key to get
    :param default: Default value to use
    :return: First item or default
    """
    value = dictionary.get(key, default)

    if value and value != default and hasattr(value, '__getitem__'):
        return value[0]

    return value


def function_hash(func):
    """
    Hashes function to determine uniqueness of function. Used for versioning functions in caches
    :param func: Function to hash
    :return: Hash representing function. Unique for bytecode of function
    """
    return hash(func.__code__)


class SentryProcessor(object):
    @abc.abstractmethod
    def _allowed(self):
        raise NotImplementedError()

    def create_event(self, event, hint):
        return event if self._allowed() else None

class SentryTtlProcessor(SentryProcessor):
    def __init__(self, ttl=1):
        """
        :param ttl: TTL in seconds
        """
        self._allowed_time = None
        self.ttl = ttl

    def _allowed(self):
        current_time = time.time()
        if self._allowed_time is None or current_time > self._allowed_time:
            self._allowed_time = current_time + self.ttl
            return True

        return False

class SentryRedisTtlProcessor(SentryProcessor):
    """
    Processor for TTL handled by redis, which should work better for multiple server processes or versions
    """
    _KEY = 'SENTRY_TTL'
    def __init__(self, redis_host='localhost', redis_port=6379, ttl=1):
        self.redis = redis.Redis(host=redis_host, port=redis_port)
        self.ttl = ttl

    def _allowed(self):
        # TODO Check on a per-exception basis
        if self.redis.exists(self._KEY):
            return False
        else:
            self.redis.set(self._KEY, True, ex=self.ttl)

        return True
