const API = require('./api.js');

module.exports = (token) => {
  let api = new API('Discogs', 'rest', 'https://api.discogs.com/');

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

  api.defineSearchMethod('artist', (query, request, cb) => {
    request('database/search', { q: query, type: 'artist' })
    .then(JSON.parse)
    .then(data =>
      cb(data.results.map(data => {
        return {
          Id: api.getName() + '-' + data.id, // Prepend provider name
          ArtistName: data.title,
          ImageUrl: data.thumb,
          Url: data.resource_url
        };
      }))
    );
  });
  api.defineSearchMethod('albumByArtist', (artistId, request, cb) => {
    artistId = artistId.split('-').slice(1).join('-');
    request(`artists/${artistId}/releases`)
    .then(JSON.parse)
    .then(data =>
      cb(data.releases.map(data => {
        return {
          Id: api.getName() + '-' + data.id, // Prepend provider name
          AlbumName: data.title,
          Year: data.year,
          Label: data.label,
          ImageUrl: data.thumb,
          Url: data.resource_url
        };
      }))
    );
  })

  api.defineGetMethod('albums', (id, request, cb) => {
    request(`releases/${id}`)
    .then(JSON.parse)
    .then(data =>
      cb({
        AlbumName: data.title,
        Artist: {
          Id: data.artists[0].id,
          ArtistName: data.artists[0].name,
          ArtistUrl: data.artists[0].resource_url
        },
        Year: data.year,
        Genres: data.genres,
        Overview: data.notes,
        Labels: data.labels.map(item => {
          return {
            Name: item.name,
            CatalogNumber: item.catno,
            ProviderIds: { [api.getName()]: id }
          };
        }),
        Images: data.images.map(item => {
          return {
            Url: item.uri,
            Height: item.height,
            Width: item.width
          };
        }),
        Url: data.uri,
        ProviderIds: { [api.getName()]: id }
      })
    );
  });
  api.defineGetMethod('artists', (id, request, cb) => {
    request(`artists/${id}`)
    .then(JSON.parse)
    .then(data =>
      cb({
        ArtistName: data.name,
        Overview: data.profile,
        Images: data.images.map(item => {
          return {
            Url: item.uri,
            Height: item.height,
            Width: item.width
          };
        }),
        Url: data.uri,
        ProviderIds: { [api.getName()]: id }
      })
    );
  });

  return api;
};
