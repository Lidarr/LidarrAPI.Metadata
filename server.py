from flask import Flask # Used for web API
from flask import jsonify, request, Response

artist = {}
artist['Id'] = 'aaaaa_aaaaa_aaaa' #This will be a unique id or perhaps Musicbrainz id
artist['ArtistName'] = 'Alien Ant Farm'
artist['Overview'] = ''
artist['Images'] = [{
	'Url': '',
	'Height': 128,
	'Width': 128
}]
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
album1['Id'] = 'aaaaa_aaaaa_bbbb'
album1['AlbumName'] = 'ANThology'
album1['Artists'] = [{
	'Id': 'aaaaa_aaaaa_aaaa',
	'ArtistName': 'Alien Ant Farm',
	'ArtistUrl': '' # This should be the full artist object
}]
album1['Year'] = '2001'
album1['Genres'] = [
	'alternative rock'
]
album1['Overview'] = ("Anthology (styled as ANThology) is the second album by Alien Ant Farm released on March 6, 2001 "
					"in the USA and March 19, 2001 in Australia and the UK. It is the first major label album of the band. "
					"Similarly to how their debut album was entitled Greatest Hits, the album is in fact not a compilation album."
					"\"Smooth Criminal\" was released as downloadable content for the Rock Band series of video games on May 5, 2009."
					" The rest of the album has been licensed for release on the Rock Band Network over the course of 2011–12, starting "
					"with \"Movies\" and \"Courage\" and continuing with three songs per quarter until the full album is released.")
album1['Label'] = ''		
album1['Images'] = [{
	'Url': '',
	'Height': 128,
	'Width': 128
}]	
album1['Url'] = ''		
albums.append(album1)

tracks = [
	{'TrackNumber': 1, 'TrackName': 'Courage', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb01', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 2, 'TrackName': 'Movies', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb02', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 3, 'TrackName': 'Flesh and Bone', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb03', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 4, 'TrackName': 'Whisper', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb04', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 5, 'TrackName': 'Summer', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb05', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 6, 'TrackName': 'Sticks and Stones', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb06', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 7, 'TrackName': 'Attitude', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb07', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 8, 'TrackName': 'Stranded', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb08', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 9, 'TrackName': 'Wish', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb09', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 10, 'TrackName': 'Calico', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb10', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 11, 'TrackName': '(Happy) Death Day', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb11', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 12, 'TrackName': 'Smooth Criminal', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb12', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},
	{'TrackNumber': 13, 'TrackName': 'Universe / Orange Appeal', 'DurationMs': 210000, 'Id': 'aaaaa_aaaaa_bb13', 'DiscNumber': 1, 'Explicit': 'false', 'Href': '', 'Artists':[artist]},

]


app = Flask(__name__)

####### ARTISTS 
# For all API calls, ID can range between id (our metadata id), mid( musicbrainz id ), theopendb id, etc.
@app.route('/artists/<id>/', methods=['GET'])
def get_artist(id=None):
	''' Get an artist. '''
	result = {
		"Items": [],
		"Count": 0
	}

	result["Items"].append(artist)
	result["Count"] = len(result["Items"])
	return jsonify({"Artists": result})


@app.route('/artists', methods=['GET'])
def get_artists():
	''' Gets several artists '''
	ids = request.args.get('ids', [])
	result = {}
	result['Items'] = []
	result['Items'].append(artist)
	result['Count'] = len(result['Items'])
	return jsonify({"Artists": result})

@app.route('/artists/<id>/albums/', methods=['GET'])
def get_artist_albums(id=None):
	''' Get an artist's albums '''
	result = {
		"Items": [],
		"Count": 0
	}
	result["Items"] = albums
	result["Count"] = len(result["Items"])
	return jsonify(result)


####### ALBUMS 
@app.route('/albums/<id>/', methods=['GET'])
def get_album(id=None):
	''' Get an album '''
	result = {
		"Items": [],
		"Count": 0
	}
	result["Items"].append(album1)
	result["Count"] = len(result["Items"])
	return jsonify(result)


@app.route('/albums', methods=['GET'])
def get_albums():
	''' Gets several albums '''
	ids = request.args.get('ids', [])
	result = {
		"Items": [],
		"Count": 0
	}
	result["Items"] = albums
	result["Count"] = len(result["Items"])
	return jsonify({"Albums": result})

####### TRACKS
@app.route('/tracks/<id>/', methods=['GET'])
def get_track(id=None):
	''' Get a track '''
	return jsonify(album1)

@app.route('/tracks', methods=['GET'])
def get_tracks():
	''' Get several tracks '''
	# TODO: Implement Resource map
	ids = request.args.get('ids', [])
	result = {}
	result['Tracks'] = tracks
	result['Count'] = 13
	return jsonify(result)

@app.route('/albums/<id>/tracks/', methods=['GET'])
def get_tracks_by_album(id=None):
	''' Gets all tracks for a given album '''
	result = {
		"Items": [],
		"Count": 0
	}
	result["Items"] = tracks
	result["Count"] = len(result["Items"])
	return jsonify(result)

####### OTHER  

@app.route('/search/', methods=['GET'])
def search():
	''' Perform a search on database and returns the most likely results in a list ''' 
	search_query = request.args.get("query", "")
	query_type = request.args.get("type", "artist") #valid types are artist, album, track

	result = {
		"Items": [],
		"Count": 0
	}
	result["Items"].append(artist)
	result["Count"] = len(result["Items"])

	return jsonify({"Artists": result})





print ("Starting server")
app.run(debug=True)