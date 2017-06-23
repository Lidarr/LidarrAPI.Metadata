const API = require('../api.js');

module.exports = (token) => {
  const api = new API('musicbrainz', 'json', 'https://musicbrainz.org/ws/2/');

  api.setRequestDefaults({
    method: 'GET',
    headers: {
      'User-Agent': 'nodejs-request-library'
    },
    qs: {
      fmt: 'json'
    }
  });

  api.defineArtistSearch((query, request, cb) => {
    request('artist', { query })
    .then(data =>
      cb(data.artists.map(item => ({
        //Id: api.encodeId(item.id), // Prepend provider name
        name: item.name
      })))
    );
  });
  api.defineAlbumSearch((query, request, cb) => {
    request('master', { query })
    .then(data =>
      cb(data.releases.map(item => ({
        //Id: api.encodeId(item.id), // Prepend provider name
        title: item.title,
        year: item.date.split('-')[0]
      })))
    );
  });

  return api;
};
