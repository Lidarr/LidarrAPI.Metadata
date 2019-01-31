"""
Code for getting and parsing music charts (Billboard, itunes, etc)
"""

import billboard
import pylast
import requests

from lidarrmetadata import config
from lidarrmetadata import provider
from lidarrmetadata import util


def _parse_itunes_chart(URL, count):
    response = requests.get(URL)
    results = filter(lambda r: r.get('kind', '') == 'album', response.json()['feed']['results'])
    search_provider = provider.get_providers_implementing(provider.AlbumNameSearchMixin)[0]
    search_results = []
    for result in results:
        search_result = search_provider.search_album_name(result['name'], artist_name=result['artistName'], limit=1)
        if search_result:
            search_result = search_result[0]
            search_results.append(_parse_album_search_result(search_result))

            if len(search_results) == count:
                break
    return search_results


@util.CACHE.memoize(timeout=60 * 60 * 24 * 7)
def get_apple_music_top_albums_chart(count=10):
    """
    Gets and parses itunes chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/apple-music/top-albums/all/{count}/explicit.json'.format(
        count=4 * count)
    return _parse_itunes_chart(URL, count)


@util.CACHE.memoize(timeout=60 * 60 * 24 * 7)
def get_apple_music_new_albums_chart(count=10):
    URL = 'https://rss.itunes.apple.com/api/v1/us/apple-music/new-releases/all/{count}/explicit.json'.format(
        count=4 * count)
    return _parse_itunes_chart(URL, count)


def get_billboard_200_albums_chart(count=10):
    """
    Gets billboard top 200 albums
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for billboard-200
    """
    results = billboard.ChartData('billboard-200')

    search_provider = provider.get_providers_implementing(provider.AlbumNameSearchMixin)[0]

    search_results = []
    for result in results:
        search_result = search_provider.search_album_name(result.title, artist_name=result.artist)
        if search_result:
            search_result = search_result[0]
            search_results.append(_parse_album_search_result(search_result))

            if len(search_results) == count:
                break

    return search_results


def get_billboard_100_artists_chart(count=10):
    """
    Gets billboard top 100 albums
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for artist-100
    """
    results = billboard.ChartData('artist-100')

    search_provider = provider.get_providers_implementing(provider.ArtistNameSearchMixin)[0]

    search_results = []
    for result in results:
        artist_search = search_provider.search_artist_name(result.artist, limit=1)
        if artist_search:
            search_results.append({'ArtistName': result.artist, 'ArtistId': artist_search[0]['Id']})

        if len(search_results) == count:
            break

    return search_results


@util.CACHE.memoize(timeout=60 * 60 * 24 * 7)
def get_itunes_top_albums_chart(count=10):
    """
    Gets and parses itunes chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/itunes-music/top-albums/all/{count}/explicit.json'.format(
        count=4 * count)
    return _parse_itunes_chart(URL, count)


@util.CACHE.memoize(timeout=60 * 60 * 24 * 7)
def get_itunes_new_albums_chart(count=10):
    """
    Gets and parses itunes new chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/itunes-music/new-music/all/{count}/explicit.json'.format(
        count=4 * count)
    return _parse_itunes_chart(URL, count)


def get_lastfm_album_chart(count=10, user=None):
    """
    Gets and parses lastfm chart
    :param count: Number of results to return. Defaults to 10
    :return: Parsed chart
    """
    client = pylast.LastFMNetwork(api_key=config.get_config().LASTFM_KEY, api_secret=config.get_config().LASTFM_SECRET)

    if user:
        user = util.cache_or_call(client.get_user, user[0])
        lastfm_albums = util.cache_or_call(user.get_top_albums)
    else:
        tag = util.cache_or_call(client.get_tag, 'all')
        lastfm_albums = util.cache_or_call(tag.get_top_albums)

    album_provider = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)[0]
    albums = []
    for result in pylast.extract_items(lastfm_albums):
        # TODO Figure out a cleaner way to do this
        rgid = album_provider.map_query(
            ('SELECT release_group.gid '
             'FROM release '
             'JOIN release_group ON release_group.id = release.release_group '
             'WHERE release.gid = %s '
             'LIMIT 1'),
            [result.get_mbid()])

        if rgid:
            search_result = album_provider.get_release_group_by_id(rgid[0]['gid'])
            if search_result:
                albums.append(_parse_album_search_result(search_result))

                if len(albums) == count:
                    break

    if len(albums) > count:
        albums = albums[:count]

    return albums


def get_lastfm_artist_chart(count=10, user=None):
    """
    Gets and parses lastfm chart
    :param count: Number of results to return. Defaults to 10
    :return: Parsed chart
    """
    client = pylast.LastFMNetwork(api_key=config.get_config().LASTFM_KEY, api_secret=config.get_config().LASTFM_SECRET)

    if user:
        user = util.cache_or_call(client.get_user, user[0])
        lastfm_artists = util.cache_or_call(user.get_top_artists)
    else:
        lastfm_artists = util.cache_or_call(client.get_top_artists)

    artists = []
    search_provider = provider.get_providers_implementing(provider.ArtistNameSearchMixin)[0]
    for lastfm_artist in pylast.extract_items(lastfm_artists):
        artist = {'ArtistName': lastfm_artist.name, 'ArtistId': lastfm_artist.get_mbid()}

        if not all(artist.values()):
            print(artist)
            results = search_provider.search_artist_name(artist['ArtistName'], limit=1)
            print(results)
            if results:
                results = results[0]
                artist = {'ArtistName': results['ArtistName'], 'ArtistId': results['Id']}

        if all(artist.values()):
            artists.append(artist)

    if len(artists) > count:
        artists = artists[:count]

    return artists


def _parse_album_search_result(search_result):
    return {
        'AlbumId': search_result['Id'],
        'AlbumTitle': search_result['Title'],
        'ArtistId': search_result['ArtistId'],
        'ReleaseDate': search_result['ReleaseDate']
    }
