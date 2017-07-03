const fs = require('fs');
const logger = require('./logger');
const { Artist, Album, Track } = require('./models');
const config = require('./config.json');

// // Load all apis
// const apis = fs.readdirSync(__dirname + '/apiDefinitions')
// .filter(filename => filename.endsWith('Api.js'))
// .map(filename => require('./apiDefinitions/' + filename))
// .map(api => api(config.tokens[api.name]));

// Load all apis in preference order: the first api is going to be called, if it returns an error or empty results, the next api is going to be called. If all the apis return an error or empty results, it's going to assume all the results are empty and return an empty array.
const apis = [
  require('./apiDefinitions/lastFmApi.js')(config.lastfm_api.token),
  //require('./apiDefinitions/musicbrainzApi.js')(config.discogs_api.token)
];

const tryForEachApi = func =>
  new Promise(fulfil => {
    const tryNext = n => {
      if (n >= apis.length) return fulfil([]);
      func(apis[n])
      .then(data => {
        if (!data) return tryNext(n+1);
        fulfil(data);
      })
      .catch(err => {
        logger.error(err);
        tryNext(n+1);
      });
    }
    tryNext(0);
  });

const fetch = {};

fetch.searchArtist = query =>
  tryForEachApi(api => api.searchArtist(query));

fetch.getArtist = id =>
  new Promise((fulfil, reject) =>
    tryForEachApi(api => api.getArtist(id))
    .then(data => {
      if (!data) return reject(new Error('Artist not found'));
      Artist.create({
        Id: data.Id,
        ArtistName: data.ArtistName,
        Overview: data.Overview
      })
      .then(artist =>
        Promise.all(data.Albums.map(album => artist.createAlbum({
          Id: album.Id,
          Title: album.Title,
          ReleaseDate: album.ReleaseDate
        })))
        .then(albums =>
          albums.forEach((album, i) => {
            (album.images ? album.images.forEach(image => album.createImage({
              url: image.url,
              media_type: image.type
            })) : Promise.resolve())
            .then(Promise.all(data.Albums[i].Tracks.map(track => album.createTrack({
              Id: track.Id,
              Title: track.Title,
              Explicit: track.Explicit,
              artist_id: artist.id
            }))))
            .then(() => fulfil(data))
            .catch(reject);
          })
        )
        .catch(reject)
      )
      .catch(reject);
    })
  );




// fetch.Album = query =>
//   tryForEachApi(api => api.searchAlbum(query));
//
// fetch.Track = query =>
//   tryForEachApi(api => api.searchTrack(query));

module.exports = fetch;
