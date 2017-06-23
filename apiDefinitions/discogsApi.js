const API = require('../api.js');

module.exports = (token) => {
  const api = new API('discogs', 'json', 'https://api.discogs.com/');

  api.setRequestDefaults({
    method: 'GET',
    headers: {
      'User-Agent': 'nodejs-request-library',
      'Authorization': 'Discogs token=' + token
    },
    qs: {
      page: 1,
      per_page: 50
    }
  });

  api.defineArtistSearch((query, request, cb) => {
    request('database/search', { q: query, type: 'artist' })
    .then(data =>
      cb(data.results.map(data => ({
        //Id: api.encodeId(data.id), // Prepend provider name
        name: data.title
      })))
    );
  });
  api.defineAlbumSearch((query, request, cb) => {
    request('database/search', { q: query, type: 'master' })
    .then(data =>
      cb(data.results.map(data => ({
        //Id: api.encodeId(data.id), // Prepend provider name
        title: data.title,
        year: data.year
      })))
    );
  });

  return api;
};
