import requests
import pylast

# class APIProvider():
# 	def __init__(self, api_url, api_key, response_type):
# 		self.api_url = api_url
# 		self.api_key = api_key
# 		self.response_type = response_type

# 	def search(self, )

headers = {'user-agent': 'nodejs-request-library'}

API_KEY = 'XXXXXXXXXXXXXXXXX'
API_SECRET = 'XXXXXXXXXXXXXXXXXXXXXXX'

network = pylast.LastFMNetwork(api_key=API_KEY, api_secret=API_SECRET)


def convert_artist(artist_obj):
    return {'ArtistName': artist_obj.name, 'Id': artist_obj.get_mbid(), 'Overview': artist_obj.get_bio_summary(),
            'AristUrl': artist_obj.get_url(), 'Genres': [], 'Images': [{'Url': artist_obj.get_cover_image(), 'media_type': 'cover'}],
            'Albums': []}


def convert_album(album_obj):
    return {'Title': album_obj.title, 'Id': album_obj.get_mbid(), 'ReleaseDate': album_obj.get_release_date(), 'Artist': album_obj.artist,
            'Images': [{'Url': album_obj.get_cover_image(), 'media_type': 'cover'}], 'Tracks': [], 'Url': album_obj.get_url()}


def search_artist(artist, limit_to=5):
    result = network.search_for_artist(artist)
    # Get all sequences of results
    artist_search_page = result.get_next_page()[:limit_to]
    artists = []
    for item in artist_search_page:
        images = [{'Url': item.get_cover_image(), 'media_type': 'cover'}]
        # TODO: Search for albums and populate
        artists.append(convert_artist(item))

    return artists


def get_artist_info(mbid):
    ''' Returns information about an Artist via artist name or mbid '''
    result = network.get_artist_by_mbid(mbid)
    artist = convert_artist(result)
    albums_result = result.get_top_albums()

    for album in albums_result:
        # TODO: Get all tracks for each
        print 'Converting %s' % album.item.title
        artist['Albums'].append(convert_album(album.item))

    return artist
