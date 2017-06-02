from flask import Flask # Used for web API
from flask import request
from flask import jsonify

artist = {}
artist['ArtistId'] = 'aaaaa_aaaaa_aaaa' #This will be a unique id or perhaps Musicbrainz id
artist['ArtistName'] = 'Alien Ant Farm'
artist['Overview'] = ''
artist['Path'] = 'O:\Lidarr Test\Alien Ant Farm'
artist['ImageUrl'] = ''
artist['Genres'] = [
  'alternative metal',
  'alternative rock',
  'funk metal',
  'industrial metal',
  'nu metal',
  'pop punk',
  'pop rock',
  'post-grunge',
  'rap metal',
  'rap rock',
  'rock'
]

albums = []
album1 = {}
album1['AlbumName'] = 'ANThology'
album1['Artist'] = {
	'ArtistId': 'aaaaa_aaaaa_aaaa',
	'ArtistName': 'Alien Ant Farm'
}
album1['Year'] = '2001'
album1['Genres'] = [
	'alternative rock'
]
album1['Overview'] = 'Anthology (styled as ANThology) is the second album by Alien Ant Farm released on March 6, 2001 in the USA and March 19, 2001 in Australia and the UK. It is the first major label album of the band. Similarly to how their debut album was entitled Greatest Hits, the album is in fact not a compilation album. ' + 
					'"Smooth Criminal" was released as downloadable content for the Rock Band series of video games on May 5, 2009. The rest of the album has been licensed for release on the Rock Band Network over the course of 2011–12, starting with "Movies" and "Courage" and continuing with three songs per quarter until the full album is released.'
album1['Label'] = ''					
albums.append(album1)

tracks = [
	{'TrackNumber': 1, 'TrackName': 'Courage', 'RuntimeSecs': 210},
	{'TrackNumber': 2, 'TrackName': 'Movies', 'RuntimeSecs': 210},
	{'TrackNumber': 3, 'TrackName': 'Flesh and Bone', 'RuntimeSecs': 210},
	{'TrackNumber': 4, 'TrackName': 'Whisper', 'RuntimeSecs': 210},
	{'TrackNumber': 5, 'TrackName': 'Summer', 'RuntimeSecs': 210},
	{'TrackNumber': 6, 'TrackName': 'Sticks and Stones', 'RuntimeSecs': 210},
	{'TrackNumber': 7, 'TrackName': 'Attitude', 'RuntimeSecs': 210},
	{'TrackNumber': 8, 'TrackName': 'Stranded', 'RuntimeSecs': 210},
	{'TrackNumber': 9, 'TrackName': 'Wish', 'RuntimeSecs': 210},
	{'TrackNumber': 10, 'TrackName': 'Calico', 'RuntimeSecs': 210},
	{'TrackNumber': 11, 'TrackName': '(Happy) Death Day', 'RuntimeSecs': 210},
	{'TrackNumber': 12, 'TrackName': 'Smooth Criminal', 'RuntimeSecs': 210},
	{'TrackNumber': 13, 'TrackName': 'Universe / Orange Appeal', 'RuntimeSecs': 210},

]


app = Flask(__name__)

####### ARTISTS 
# For all API calls, ID can range between id (our metadata id), mid( musicbrainz id ), theopendb id, etc.
@app.route('/artists/<id>/', methods=['GET'])
def get_artist(id=None):
    ''' Get an artist. '''
    return jsonify(artist)

@app.route('/artists', methods=['GET'])
def get_artists():
    ''' Gets several artists '''
    ids = request.args.get('ids', [])
    result = {}
    result['Artists'] = []
    results['Artists'].append(artist)
    results['Count'] = 1
    print('get_artists:' + json(results))
    return jsonify(results)

@app.route('/artists/<id>/albums', methods=['GET'])
def get_artist_albums(id=None):
	''' Get an artist's albums '''
	return jsonify(albums)


####### ALBUMS 
@app.route('/albums/<id>/', methods=['GET'])
def get_album(id=None):
    ''' Get an album '''
    return jsonify(album1)

@app.route('/albums', methods=['GET'])
def get_albums():
    ''' Gets several albums '''
    ids = request.args.get('ids', [])
    result = {}
    result['Albums'] = albums
    results['Count'] = 1
    return jsonify(results)

####### TRACKS
@app.route('/tracks/<id>/', methods=['GET'])
def get_album(id=None):
    ''' Get a track '''
    return jsonify(album1)

@app.route('/tracks', methods=['GET'])
def get_albums():
    ''' Get several tracks '''
    ids = request.args.get('ids', [])
    result = {}
    result['Tracks'] = tracks
    results['Count'] = 13
    return jsonify(results)


####### OTHER  

@app.route('/search', methods=['GET'])
def search():
    ''' Perform a search on database and returns the most likely results in a list ''' 
    search_query = request.args.get('query', '')
    query_type = request.args.get('type', 'artist') #valid types are artist, album, track

    result = {}
    result['results'] = []
    results['results'].append(artist)
    results['count'] = 1

    return jsonify(result)






app.run()