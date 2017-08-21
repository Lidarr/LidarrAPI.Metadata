import collections
import imp
import itertools
import six
import sys

import pylast

import lidarrmetadata


def provider_by_name(name):
    """
    Gets a provider by string name
    :param name: Name of provider
    :return:
    """
    return getattr(sys.modules[__name__], name)


def qualitied_func_name(func):
    """
    Gets qualitied function name
    :param func:
    :return:
    """
    if six.PY3:
        return func.__qualname__

    func_class = getattr(func, 'im_class', None)

    if func_class:
        return func_class.__name__ + '.' + func.__name__

    return func.__name__


def _perm_length(fields, providers):
    """
    Calculates number of steps for the given providers to get the given fields
    :param fields: Fields to get
    :param providers: Providers to use
    :return: Number of steps to use if providers can provide fields, None if
             they cannot.
    """
    fields = set(fields)

    # Check to make sure all the desired fields can be provided by providers
    provided_fields = {key for provider in providers for key in
                       provider.fields.keys()}
    if provided_fields.intersection(fields) != fields:
        return None

    steps = 0
    remaining_fields = fields
    for provider in providers:
        steps += 1
        remaining_fields = remaining_fields.difference(provider.fields)

        if not remaining_fields:
            return steps


def _provider_route(fields):
    """
    Gets the route of provider to use to obtain the given fields. Results are
    cached to avoid having to redo permutations multiple times.

    :param fields: List of fields to search for
    :return: List of providers to use
    """
    lengths = {}
    for n in range(1, len(Provider.providers) + 1):
        for providers_perm in itertools.permutations(Provider.providers, n):
            steps = _perm_length(fields, providers_perm)
            if steps is not None:
                lengths[providers_perm] = steps

        # If there's a solution with n providers, there won't be a shorter
        # solution with n + 1 providers, so we can stop here
        if any(lengths.values()):
            break

    return min(lengths, key=lengths.get) if lengths else None


def search_fields(fields):
    """
    Searched for the desired fields
    :param fields: Dictionary of fields -> FuncCall to search where the
                   args and kwargs are passed to the search function
    :return: Dict of field -> result
    """
    route = _provider_route(fields.keys())

    results = []
    for provider in route:
        field_names = set(fields.keys()).intersection(provider.fields.keys())
        provider_fields = {field_name: fields[field_name]
                           for field_name in field_names}
        results.extend(provider.search_fields(provider_fields))

    return results


# Resource, field tuple for identifying search functions
ResourceField = collections.namedtuple('ResourceField', ['resource', 'field'])


class FuncCall(object):
    """
    Encapsulates a function call into a class so we don't have to keep passing
    around (func, (args, kwargs)) tuples
    """

    def __init__(self, func, *args, **kwargs):
        """
        Class initialization
        :param func: Encapsulated function
        :param args: Args to provide to function
        :param kwargs: Keyword args to provide to function
        """
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *args, **kwargs):
        """
        Calls FuncCall. Allows calling like a function
        :param args: Additional args to call with
        :param kwargs: Additional kwargs to call with
        :return: Result of function called with args and kwargs class was
                 initialized with along with passed args and kwargs
        """
        args = self.args + args
        kwargs.update(self.kwargs)
        return self.func(*args, **kwargs)

    def __eq__(self, other):
        """
        Tests equality of FuncCalls
        :param other: Other object
        :return: True if function, args, and kwargs are equivalent. False
                 otherwise
        """
        return (self.func == other.func
                and self.args == other.args
                and self.kwargs == other.kwargs)

    def __hash__(self):
        """
        Hashing for function. Just hashes the representation string. Probably
        not the most optimal, but it'll work for our purposes.
        :return:
        """
        return hash(repr(self))

    def __repr__(self):
        """
        Gets string representation of func call
        :return: String representation of func call
        """
        args_str = ', '.join(self.args)
        kwargs_str = ', '.join(['{key}={value}'.format(key=key, value=value)
                                for key, value in self.kwargs.items()])
        return '{name}({args}, {kwargs})'.format(
            name=qualitied_func_name(self.func),
            args=args_str,
            kwargs=kwargs_str)


class Provider(object):
    """
    Base provider class
    """

    # Search priorities to determine which order providers are used in
    PRIORITY_FIRST = -1
    PRIORITY_NORMAL = 0
    PRIORITY_LAST = 1

    # List of provider instances to use for queries
    providers = []

    def __init__(self, priority=PRIORITY_NORMAL):
        self.priority = priority
        self.providers.append(self)
        self.providers.sort(key=lambda p: p.priority)

        self.fields = {}

    def search_fields(self, fields):
        """
        Searches for the given fields, minimizing the number of function calls
        in case on function provides multiple fields
        :param fields: Dictionary of field -> FuncCall
        :return: Dictionary of ResourceField -> result
        """
        search_funcs = collections.defaultdict(list)
        for field, call in fields.items():
            # Update the call's function since we start it with None
            call.func = self.fields[field]
            search_funcs[call].append(field)

        print('sf', search_funcs)

        results = []
        for func, _fields in search_funcs.items():
            print('func call', func)
            # TODO Handle merging results. Should probably find a way to always
            # have an ID and join on that
            result = func()
            results.extend(result)

        # Remove fields that weren't wanted
        for result in results:
            [result.pop(extra_field)
             for extra_field in set(result.keys()).difference(fields.keys())]

        return results


class MusicbrainzApiProvider(Provider):
    """
    Provider that utilizes the musicbrainz API
    """

    def __init__(self, host='musicbrainz.org'):
        super(MusicbrainzApiProvider, self).__init__()

        # Set up client. Since musicbrainzngs has its functions operate on a
        # module namespace, we need to have a module import for each instance
        self.client = imp.load_module('self.client',
                                      *imp.find_module('musicbrainzngs'))
        self.client.set_useragent('lidarr-metadata', lidarrmetadata.__version__)
        self.client.set_hostname(host)

        # Set up provider fields
        self.fields[ResourceField('Artist', 'Id')] = self._search_artist
        self.fields[ResourceField('Artist', 'ArtistName')] = self._search_artist

    def _search_artist(self, query, **kwargs):
        """
        Searches for an artist
        :param query: Artist query
        :param kwargs: Keyword arguments to send to musicbrainzngs search
        :return:
        """
        mb_response = self.client.search_artists(query, **kwargs)['artist-list']
        return [{ResourceField('Artist', 'Id'): artist['id'],
                 ResourceField('Artist', 'ArtistName'): artist['name']}
                for artist in mb_response]


class LastFmProvider(Provider):
    """
    Provider that uses LastFM API
    """
    def __init__(self, api_key, api_secret):
        """
        Class initialization
        :param api_key: LastFM API key
        :param api_secret: LastFM API secret
        """
        super(LastFmProvider, self).__init__()

        self._client = pylast.LastFMNetwork(api_key=api_key,
                                            api_secret=api_secret)

        # Set up supported fields
        self.fields = {ResourceField('Artist', 'Id'): self.search_artist,
                       ResourceField('Artist', 'Overview'): self.search_artist}

    def search_artist(self, name):
        results = self._client.search_for_artist(name).get_next_page()
        return [{ResourceField('Artist', 'Id'): result.get_mbid(),
                ResourceField('Artist', 'Overview'): result.get_bio_summary()}
                for result in results]

if __name__ == '__main__':
    provider = MusicbrainzApiProvider()
    LastFmProvider('',
                   '')
    results = search_fields(
        {ResourceField('Artist', 'ArtistName'): FuncCall(None, '3oh3'),
         ResourceField('Artist', 'Id'): FuncCall(None, '3oh3'),
         ResourceField('Artist', 'Overview'): FuncCall(None, '3oh3')})
    print(results)
