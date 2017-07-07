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

  api.setErrorCheck(json => {
    if (json.error) throw json.error;
  })

  api.defineArtistSearch((query, request, cb) => {
    request('', { method: 'artist.search', artist: query })
    .then(data =>
      cb(data.results.artistmatches.artist.filter(item => item.hasOwnProperty('mbid') && item.mbid).map(item => ({
        Id: item.mbid, // Prepend provider name
        ArtistName: item.name
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
          Id: info.artist.mbid,
          ArtistName: info.artist.name,
          Overview: info.artist.bio.summary,
          Albums: albumsInfo.map(item => ({
            Id: item.album.mbid,
            Title: item.album.name,
            Tracks: item.album.tracks.track.map(item => ({
              Title: item.name
            }))
          }))
        })
      );
    });
  });

  return api;
}
