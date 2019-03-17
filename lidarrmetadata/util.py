"""
Utility functionality that isn't specific to a given module
"""

import abc
import time

import flask_caching
import functools
import redis

from lidarrmetadata import config

# Cache for application
CACHE = flask_caching.Cache(config=config.get_config().CACHE_CONFIG)



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


def map_iterable_values(iterable, func, types=object):
    """
    Maps all strings in iterable

    !!!
    This function was a fun one to write. Don't modify until tests are added unless there's an issue.
    !!!

    :param iterable: Iterable to find strings in
    :param func: String mapping function
    :param types: Type restriction as single type or iterable of types. Defaults to object (no type restriction)
    :return: Iterable with mapped strings
    """
    types = (types,) if isinstance(types, type) else tuple(types)

    original_type = type(iterable)
    if original_type not in [dict, list]:
        iterable = list(iterable)

    mapped = type(iterable)()
    assign_func = mapped.setdefault if isinstance(mapped, dict) else mapped.insert
    enumerate_func = iterable.items if isinstance(iterable, dict) else functools.partial(enumerate, iterable)

    for i, v in enumerate_func():
        if isinstance(v, types):
            assign_func(i, func(v))
        elif hasattr(v, '__iter__') and not isinstance(v, str):
            assign_func(i, map_iterable_values(v, func, types))
        else:
            assign_func(i, v)

    if original_type not in [dict, list]:
        mapped = original_type(mapped)

    return mapped


def translate_string(s, table):
    """
    Translated a string based on translation table
    :param s: String to translate
    :param table: Tranalation table as dictionary
    :return: Translated string
    """
    return ''.join([table.get(c, c) for c in s])


class BidirectionalDictionary(dict):
    """
    Bidirectional dictionary. Thanks to https://stackoverflow.com/a/21894086/2383721. Modified to only have unique
    values
    """

    def __init__(self, *args, **kwargs):
        super(BidirectionalDictionary, self).__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in self.items():
            self.inverse.setdefault(value, key)

    def __setitem__(self, key, value):
        if key in self:
            del self.inverse[value]
        super(BidirectionalDictionary, self).__setitem__(key, value)
        self.inverse.setdefault(value, key)

    def __delitem__(self, key):
        del self.inverse[self[key]]
        super(BidirectionalDictionary, self).__delitem__(key)


class Cache(object):
    """
    Cache to store info
    """

    def __init__(self):
        """
        Initialization
        """
        self._backend = {}

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        return self.put(key, value)

    def get(self, key, default=None):
        """
        Gets item with key
        :param key: Key of item to get
        :param default: Default value to return if no item at key
        :return: Item at key
        """
        return self._backend.get(key, default)

    def put(self, key, item):
        """
        Puts item at key
        :param key: Key to put item at
        :param item: Value to put
        """
        self._backend[key] = item

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
