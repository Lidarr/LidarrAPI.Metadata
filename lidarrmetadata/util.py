"""
Utility functionality that isn't specific to a given module
"""


def first_key_item(dictionary, key, default=None):
    """
    Gets the first item from a dictionary key that returns a list
    :param dictionary: Dictionary to get item from
    :param key: Key to get
    :param default: Default value to use
    :return: First item or default
    """
    value = dictionary.get(key, default)

    if value and value != default:
        return value[0]

    return value


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
