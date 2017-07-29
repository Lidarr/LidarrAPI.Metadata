from flask import Flask, request, jsonify, send_file
from werkzeug.exceptions import HTTPException

from lidarrmetadata import config
from lidarrmetadata import models
from lidarrmetadata import provider


app = Flask(__name__)
app.config.from_object(config.CONFIG)

# Set up providers
for provider_name, (args, kwargs) in config.CONFIG.PROVIDERS.items():
    provider_class = provider.provider_by_name(provider_name)
    provider_class(*args, **kwargs)

if not app.config['PRODUCTION']:
    # Run api doc server if not running in production
    from flasgger import Swagger
    swagger = Swagger(app)


@app.before_request
def before_request():
    models.database.connect()


@app.teardown_request
def teardown_request(response):
    if not models.database.is_closed():
        models.database.close()


@app.errorhandler(404)
@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(error=str(e)), code


@app.route("/")
def index():
    ''' This returns our web-app, if we have one '''
    return send_file('static/index.html')


@app.route('/artist/<mbid>', methods=['GET'])
def get_artist_info(mbid):
    print(mbid)
    artist_info = provider.get_artist_info(mbid)
    return jsonify(artist_info)


@app.route('/search/artist/', methods=['GET'])
def search_artist():
    """Search for a human-readable artist
    ---
    parameters:
     - name: query
       in: path
       type: string
       required: true
    responses:
      200:
            description: Returns a set of artists limited to the first 5
            schema:
              $ref: /search/artist/afi
            examples:
              {
                    "Albums": [],
            "AristUrl": "http://www.last.fm/music/afi",
            "ArtistName": "AFI",
            "Genres": [],
            "Id": "4fc58550-637f-496f-b6bc-3a62ba7f2f7e",
            "Images": [
                {
                    "Url": "https://lastfm-img2.akamaized.net/i/u/80cd9530f9ef4c783873b1a39951ff98.png",
                    "media_type": "cover"
                }
            ],
            "Overview": "AFI (A Fire Inside) is an American punk rock/alternative rock band 
                                    from Ukiah, CA that formed in 1991."
                }
    """
    query = request.args.get('query')

    artists = provider.search_artist(query)
    print("Found %s results" % str(len(artists)))

    return jsonify([artist.to_dict() for artist in artists])
