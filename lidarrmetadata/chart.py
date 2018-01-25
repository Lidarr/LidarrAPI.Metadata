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
        search_result = search_provider.search_album_name(result['name'], artist_name=result['artistName'], limit=1)
        if search_result:
            search_result = search_result[0]
            search_results.append(_parse_album_search_result(search_result))

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
        search_result = search_provider.search_album_name(result.title, artist_name=result.artist)
        if search_result:
            search_result = search_result[0]
            search_results.append(_parse_album_search_result(search_result))

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
        search_result = search_provider.search_album_name(result['name'], artist_name=result['artistName'], limit=1)
        if search_result:
            search_result = search_result[0]
            search_results.append(_parse_album_search_result(search_result))

            if len(search_results) == count:
                break

    return search_results


def get_lastfm_album_chart(count=10, user=None):
    """
    Gets and parses lastfm chart
    :param count: Number of results to return. Defaults to 10
    :return: Parsed chart
    """
    client = pylast.LastFMNetwork(api_key=config.CONFIG.LASTFM_KEY, api_secret=config.CONFIG.LASTFM_SECRET)

    if user:
        user = client.get_user(user[0])
        lastfm_albums = user.get_top_albums()
    else:
        tag = client.get_tag('all')
        lastfm_albums = tag.get_top_albums()

    album_provider = provider.get_providers_implementing(provider.AlbumByIdMixin)[0]
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
            search_result = album_provider.get_album_by_id(rgid[0]['gid'])
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
    client = pylast.LastFMNetwork(api_key=config.CONFIG.LASTFM_KEY, api_secret=config.CONFIG.LASTFM_SECRET)

    if user:
        user = client.get_user(user[0])
        lastfm_artists = user.get_top_artists()
    else:
        lastfm_artists = client.get_top_artists()


    artists = []
    search_provider = provider.get_providers_implementing(provider.ArtistNameSearchMixin)[0]
    for lastfm_artist in pylast.extract_items(lastfm_artists):
        artist = {'Name': lastfm_artist.name, 'Id': lastfm_artist.get_mbid()}

        if not all(artist.values()):
            print(artist)
            results = search_provider.search_artist_name(artist['Name'], limit=1)
            print(results)
            if results:
                results = results[0]
                artist = {'Name': results['ArtistName'], 'Id': results['Id']}


        if all(artist.values()):
            artists.append(artist)

    if len(artists) > count:
        artists = artists[:count]

    return artists


def _parse_album_search_result(search_result):
    return {
        'AlbumId': search_result['Id'],
        'AlbumTitle': search_result['Title'],
        'ArtistName': search_result['Artist']['Name'],
        'ArtistId': search_result['Artist']['Id'],
        'ReleaseDate': search_result['ReleaseDate']
    }
