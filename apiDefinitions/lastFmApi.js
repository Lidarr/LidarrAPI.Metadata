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
      cb(data.results.artistmatches.artist.filter(item => item.hasOwnProperty('mbid') && item.mbid).map(item => ({
        mbid: item.mbid, // Prepend provider name
        name: item.name
      })))
    );
  });
  api.defineArtistGet((id, request, cb) => {
    Promise.all([
      request('', { method: 'artist.getinfo', mbid: id }),
      request('', { method: 'artist.gettopalbums', mbid: id })
    ])
    .then(([ info, albums ]) => {
      Promise.all(albums.topalbums.album.filter(item => item.hasOwnProperty('mbid') && item.mbid).map(item => request('', { method: 'album.getinfo', mbid: item.mbid })))
      .then(albumsInfo =>
        cb({
          mbid: info.artist.mbid,
          name: info.artist.name,
          overview: info.artist.bio.summary,
          albums: albumsInfo.map(item => ({
            mbid: item.album.mbid,
            title: item.album.name,
            tracks: item.album.tracks.track.map(item => ({
              title: item.name
            }))
          }))
        })
      );
    });
  });

  return api;
}
