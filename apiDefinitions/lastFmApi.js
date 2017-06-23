const API = require('../api.js');

module.exports = (token) => {
  const api = new API('lastfm', 'json', 'http://ws.audioscrobbler.com/2.0/');

  api.setRequestDefaults({
    method: 'GET',
    headers: {
      'User-Agent': 'nodejs-request-library'
    },
    qs: {
      api_key: token,
      format: 'json'
    }
  });

  api.defineArtistSearch((query, request, cb) => {
    request('', { method: 'artist.search', artist: query })
    .then(data =>
      cb(data.results.artistmatches.artist.map(item => ({
        Id: api.encodeId(item.mbid), // Prepend provider name
        ArtistName: item.name,
        ImageUrl: ((obj) => ({ Url: obj['#text'], Size: obj.size }))(item.image.find(item => item.size == 'medium') || item.image[0]),
        Url: data.url
      })))
    );
  });
  api.defineAlbumSearch((query, request, cb) => {
    request('', { method: 'album.search', album: query })
    .then(data =>
      cb(data.results.albummatches.album.map(item => ({
        //Id: api.encodeId(item.mbid), // Prepend provider name
        title: item.name,
        year: null,
      })))
    );
  });
  api.defineTrackSearch((query, request, cb) => {
    request('', { method: 'track.search', track: query })
    .then(data =>
      cb(data.results.trackmatches.track.map(item => ({
        //Id: api.encodeId(item.mbid), // Prepend provider name
        title: item.name,
        number: null,
      })))
    );
  });

  return api;
}
