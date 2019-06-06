"""
Code for getting and parsing music charts (Billboard, itunes, etc)
"""

import billboard
import pylast
import aiohttp
from aiocache import cached

from lidarrmetadata import config
from lidarrmetadata import provider
from lidarrmetadata import util
from lidarrmetadata.api import get_release_group_info_basic

async def _parse_itunes_chart(URL, count):
    async with aiohttp.ClientSession() as session:
        async with session.get(URL, timeout=aiohttp.ClientTimeout(total=5)) as response:
            json = await response.json()
            results = filter(lambda r: r.get('kind', '') == 'album', json['feed']['results'])
            search_provider = provider.get_providers_implementing(provider.AlbumNameSearchMixin)[0]
            search_results = []
            for result in results:
                search_result = await search_provider.search_album_name(result['name'], artist_name=result['artistName'], limit=1)
                if search_result:
                    search_result = search_result[0]
                    search_results.append(await _parse_album_search_result(search_result))

                    if len(search_results) == count:
                        break
            return search_results

@cached(ttl = 60 * 60 * 24, alias='default')
async def get_apple_music_top_albums_chart(count=10):
    """
    Gets and parses itunes chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/apple-music/top-albums/all/{count}/explicit.json'.format(
        count=4 * count)
    return await _parse_itunes_chart(URL, count)

@cached(ttl = 60 * 60 * 24, alias='default')
async def get_apple_music_new_albums_chart(count=10):
    URL = 'https://rss.itunes.apple.com/api/v1/us/apple-music/new-releases/all/{count}/explicit.json'.format(
        count=4 * count)
    return await _parse_itunes_chart(URL, count)

@cached(ttl = 60 * 60 * 24, alias='default')
async def get_billboard_200_albums_chart(count=10):
    """
    Gets billboard top 200 albums
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for billboard-200
    """
    results = billboard.ChartData('billboard-200')

    search_provider = provider.get_providers_implementing(provider.AlbumNameSearchMixin)[0]

    search_results = []
    for result in results:
        search_result = await search_provider.search_album_name(result.title, artist_name=result.artist)
        if search_result:
            search_result = search_result[0]
            search_results.append(await _parse_album_search_result(search_result))

            if len(search_results) == count:
                break

    return search_results

@cached(ttl = 60 * 60 * 24, alias='default')
async def get_billboard_100_artists_chart(count=10):
    """
    Gets billboard top 100 albums
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for artist-100
    """
    results = billboard.ChartData('artist-100')

    search_provider = provider.get_providers_implementing(provider.ArtistNameSearchMixin)[0]

    search_results = []
    for result in results:
        artist_search = await search_provider.search_artist_name(result.artist, limit=1)
        if artist_search:
            search_results.append({'ArtistName': result.artist, 'ArtistId': artist_search[0]['Id']})

        if len(search_results) == count:
            break

    return search_results

@cached(ttl = 60 * 60 * 24, alias='default')
async def get_itunes_top_albums_chart(count=10):
    """
    Gets and parses itunes chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/itunes-music/top-albums/all/{count}/explicit.json'.format(
        count=4 * count)
    return await _parse_itunes_chart(URL, count)


@cached(ttl = 60 * 60 * 24, alias='default')
async def get_itunes_new_albums_chart(count=10):
    """
    Gets and parses itunes new chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/itunes-music/new-music/all/{count}/explicit.json'.format(
        count=4 * count)
    return await _parse_itunes_chart(URL, count)

@cached(ttl = 60 * 60 * 24, alias='default')
async def get_lastfm_album_chart(count=10, user=None):
    """
    Gets and parses lastfm chart
    :param count: Number of results to return. Defaults to 10
    :return: Parsed chart
    """
    client = pylast.LastFMNetwork(api_key=config.get_config().LASTFM_KEY, api_secret=config.get_config().LASTFM_SECRET)

    if user:
        user = client.get_user(user[0])
        lastfm_albums = user.get_top_albums(limit = count * 2)
    else:
        tag = client.get_tag('all')
        lastfm_albums = tag.get_top_albums(limit = count * 2)

    album_provider = provider.get_providers_implementing(provider.ReleaseGroupByIdMixin)[0]
    albums = []
    for lastfm_album in lastfm_albums:
        # TODO Figure out a cleaner way to do this
        rgid = await album_provider.map_query(
            'SELECT release_group.gid '
            'FROM release '
            'JOIN release_group ON release_group.id = release.release_group '
            'WHERE release.gid = $1 '
            'LIMIT 1',
            lastfm_album.item.get_mbid()
        )

        if rgid:
            search_result = await _parse_album_search_result({'Id': rgid[0]['gid']})
            if search_result:
                albums.append(search_result)

                if len(albums) == count:
                    break

    if len(albums) > count:
        albums = albums[:count]

    return albums

@cached(ttl = 60 * 60 * 24, alias='default')
async def get_lastfm_artist_chart(count=10, user=None):
    """
    Gets and parses lastfm chart
    :param count: Number of results to return. Defaults to 10
    :return: Parsed chart
    """
    client = pylast.LastFMNetwork(api_key=config.get_config().LASTFM_KEY, api_secret=config.get_config().LASTFM_SECRET)

    if user:
        user = client.get_user(user[0])
        lastfm_artists = user.get_top_artists(limit = count * 2)
    else:
        lastfm_artists = client.get_top_artists(limit = count * 2)

    artists = []
    search_provider = provider.get_providers_implementing(provider.ArtistNameSearchMixin)[0]
    for lastfm_artist in lastfm_artists:
        artist = {'ArtistName': lastfm_artist.item.name, 'ArtistId': lastfm_artist.item.get_mbid()}

        if not all(artist.values()):
            results = await search_provider.search_artist_name(artist['ArtistName'], limit=1)
            if results:
                results = results[0]
                artist = {'ArtistName': results['ArtistName'], 'ArtistId': results['Id']}

        if all(artist.values()):
            artists.append(artist)

    if len(artists) > count:
        artists = artists[:count]

    return artists


async def _parse_album_search_result(search_result):
    album = await get_release_group_info_basic(search_result['Id'])
    album = album[0]
    return {
        'AlbumId': album['id'],
        'AlbumTitle': album['title'],
        'ArtistId': album['artistid'],
        'ReleaseDate': album['releasedate']
    }
