const fs = require('fs');
const logger = require('./logger');
const config = require('./config.json');

// // Load all apis
// const apis = fs.readdirSync(__dirname + '/apiDefinitions')
// .filter(filename => filename.endsWith('Api.js'))
// .map(filename => require('./apiDefinitions/' + filename))
// .map(api => api(config.tokens[api.name]));

// Load all apis in preference order: the first api is going to be called, if it returns an error or empty results, the next api is going to be called. If all the apis return an error or empty results, it's going to assume all the results are empty and return an empty array.
const apis = [
  require('./apiDefinitions/discogsApi.js')(config.discogs_api.token),
  require('./apiDefinitions/lastFmApi.js')(config.discogs_api.token),
  require('./apiDefinitions/musicbrainzApi.js')(config.discogs_api.token),
];

const tryForEachApi = func =>
  new Promise(fulfil => {
    const tryNext = n => {
      if (n >= apis.length) return fulfil([]);
      func(apis[n])
      .then(data => {
        if (!data.length) return tryNext(n+1);
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

fetch.Artist = query =>
  tryForEachApi(api => api.searchArtist(query));

fetch.Album = query =>
  tryForEachApi(api => api.searchAlbum(query));

fetch.Track = query =>
  tryForEachApi(api => api.searchTrack(query));

module.exports = fetch;
