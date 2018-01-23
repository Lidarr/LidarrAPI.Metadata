"""
Code for getting and parsing music charts (Billboard, itunes, etc)
"""

import billboard
import pylast
import requests

from lidarrmetadata import config
from lidarrmetadata import provider


def get_apple_music_chart(count=10):
    """
    Gets and parses itunes chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/apple-music/top-albums/all/{count}/explicit.json'.format(count=4 * count)
    response = requests.get(URL)
    results = response.json()['feed']['results']

    search_provider = provider.get_providers_implementing(provider.AlbumNameSearchMixin)[0]

    search_results = []
    for result in results:
        search_result = search_provider.search_album_name(result['name'], result['artistName'])
        if search_result:
            search_result = search_result[0]
            search_results.append(_parse_result(search_result))

            if len(search_results) == count:
                break

    return search_results


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
        search_result = search_provider.search_album_name(result.title, result.artist)
        if search_result:
            search_result = search_result[0]
            search_results.append(_parse_result(search_result))

            if len(search_results) == count:
                break

    return search_results


def get_itunes_chart(count=10):
    """
    Gets and parses itunes chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/itunes-music/top-albums/all/{count}/explicit.json'.format(count=4 * count)
    response = requests.get(URL)
    results = response.json()['feed']['results']

    search_provider = provider.get_providers_implementing(provider.AlbumNameSearchMixin)[0]

    search_results = []
    for result in results:
        search_result = search_provider.search_album_name(result['name'], result['artistName'])
        if search_result:
            search_result = search_result[0]
            search_results.append(_parse_result(search_result))

            if len(search_results) == count:
                break

    return search_results


def get_lastfm_chart(count=10):
    """
    Gets and parses lastfm chart
    :param count: Number of results to return. Defaults to 10
    :return: Parsed chart
    """
    client = pylast.LastFMNetwork(api_key=config.CONFIG.LASTFM_KEY, api_secret=config.CONFIG.LASTFM_SECRET)
    lastfm_artists = client.get_top_artists()

    artists = [{'Name': artist.name,
                'Id': artist.get_mbid()}
               for artist in pylast.extract_items(lastfm_artists)]

    if len(artists) > count:
        artists = artists[:count]

    return artists


def _parse_result(search_result):
    return {
        'AlbumId': search_result['Id'],
        'AlbumTitle': search_result['Title'],
        'ArtistName': search_result['Artist']['Name'],
        'ArtistId': search_result['Artist']['Id'],
        'ReleaseDate': search_result['ReleaseDate']
    }
