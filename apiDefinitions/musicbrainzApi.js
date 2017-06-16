const API = require('./api.js');

module.exports = (token) => {
  let api = new API('musicbrainz', 'xml', 'https://musicbrainz.org/ws/2/');

  api.setRequestDefaults({
    method: 'GET',
    headers: {
      'User-Agent': 'nodejs-request-library'
    }
  });

  api.defineSearchMethod('artist', (query, request, cb) => {
    request('artist', { query })
    .then(data =>
      cb(data.metadata[0]['artist-list'][0].artist.map(item => ({
        Id: api.encodeId(item.id), // Prepend provider name
        ArtistName: item.name[0],
        Url: 'https://musicbrainz.org/artist/' + item.id,
        Genres: item['tag-list'] ? item['tag-list'][0].tag.map(tag => tag.name[0]) : []
      })))
    );
  });
  api.defineSearchMethod('albumByArtist', (artistId, request, cb) => {
    request('release', { artist: api.decodeId(artistId) }) // TODO: FIX
    .then(data =>
      cb(data.metadata['release-list'].release.map(data => ({
          Id: api.encodeId(data.id), // Prepend provider name
          AlbumName: data.title[0],
          Year: data.date[0].split('-')[0],
          Url: 'https://musicbrainz.org/release/' + data.id
      })))
    );
  });

  api.defineGetMethod('albums', (id, request, cb) => {
    request(`release/${id}`)
    .then(data => {
      data = data.metadata[0].release[0];
      cb({
        Id: api.getName() + '-' + data.id, // Prepend provider name
        AlbumName: data.title[0],
        Year: data.date[0].split('-')[0],
        Url: 'https://musicbrainz.org/release/' + data.id,
        ProviderIds: { [api.getName()]: id }
      })
    });
  });
  api.defineGetMethod('artists', (id, request, cb) => {
    request(`artist/${id}`, { inc: 'url-rels+tags' })
    .then(data => {
      data = data.metadata[0].artist[0];
      cb({
        ArtistName: data.name[0],
        Url: 'https://musicbrainz.org/artist/' + id,
        Genres: data['tag-list'].map(item => item.tag[0].name[0]),
        ProviderIds: { [api.getName()]: id }
      });
    });
  });

  return api;
};
