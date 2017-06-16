const API = require('./api.js');

module.exports = (token) => {
  let api = new API('lastfm', 'json', 'http://ws.audioscrobbler.com/2.0/');

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

  api.defineSearchMethod('artist', (query, request, cb) => {
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
  api.defineSearchMethod('albumByArtist', (artistId, request, cb) => {
    request('', { method: 'artist.getTopAlbums', mbid: api.decodeId(artistId) })
    .then(data =>
      cb(
        data.topalbums.album
        .filter(item => item.mbid !== null)
        .map(item => ({
          Id: api.encodeId(item.mbid), // Prepend provider name
          AlbumName: item.name,
          ImageUrl: ((obj) => ({ Url: obj['#text'], Size: obj.size }))(item.image.find(item => item.size == 'medium') || item.image[0]),
          Url: item.url
        }))
      )
    );
  });

  api.defineGetMethod('albums', (id, request, cb) => {
    request('', { method: 'album.getInfo', mbid: id })
    .then(data =>
      cb({
        AlbumName: data.album.name,
        Artist: {
          ArtistName: data.album.artist,
        },
        Genres: data.album.tags.tag.map(item => item.name),
        Overview: data.album.wiki.summary,
        Images: data.album.image.map(item => ({
          Url: item['#text'],
          Size: item.size
        })),
        Url: data.album.url,
        ProviderIds: { [api.getName()]: id }
      })
    );
  });
  api.defineGetMethod('artists', (id, request, cb) => {
    request('', { method: 'artist.getInfo', mbid: id })
    .then(data =>
      cb({
        ArtistName: data.artist.name,
        Overview: data.artist.bio.summary,
        Images: data.artist.image.map(item => ({
          Url: item['#text'],
          Size: item.size
        })),
        Genres: data.artist.tags.tag.map(item => item.name),
        Url: data.artist.url,
        ProviderIds: { [api.getName()]: id }
      })
    );
  });

  return api;
}
