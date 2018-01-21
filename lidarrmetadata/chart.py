"""
Code for getting and parsing music charts (Billboard, itunes, etc)
"""

import datetime

import requests

from lidarrmetadata import provider

def get_itunes_chart(count=10):
    """
    Gets and parses itunes chart
    :param count: Number of results to return. Defaults to 10
    :return: Chart response for itunes
    """
    URL = 'https://rss.itunes.apple.com/api/v1/us/apple-music/top-albums/all/{count}/explicit.json'.format(count=count)
    response = requests.get(URL)
    results = response.json()['feed']['results']

    search_provider = provider.get_providers_implementing(provider.AlbumNameSearchMixin)[0]

    search_results = []
    for result in results:
        print('searching')
        search_result = search_provider.search_album_name(result['name'], result['artistName'])
        if search_result:
            search_result = search_result[0]
            print(search_result)
            search_results.append({
                'AlbumId': search_result['Id'],
                'AlbumTitle': search_result['Title'],
                'ArtistName': search_result['Artist']['Name'],
                'ArtistId': search_result['Artist']['Id'],
                'ReleaseDate': datetime.datetime.strptime(result['releaseDate'], '%Y-%m-%d')
            })

    return search_results

if __name__ == '__main__':
    print(get_itunes_chart())