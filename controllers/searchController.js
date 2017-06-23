const logger = require('./../logger');
const fetch = require('./../fetch');
const { Artist, Album, Track } = require('./../models');

const searchController = {};

searchController.artist = (req, res) => {
  Artist.findAll({ where: { name: req.cleanData.query } })
  .then(artists => {
    if (!artists.length) {
      logger.info('Fetching artist from apis.');
      return fetch.Artist(req.cleanData.query)
      .then(data => {
        res.json({ Success: true, Artists: data, Count: data.length });
        Artist.bulkCreate(data, { validate: true });
      });
    }
    logger.info('Found artist in the database.');
    res.json({ Success: true, Artists: artists, Count: artists.length });
  })
  .catch(err => {
    logger.error(err);
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};

searchController.album = (req, res) => {
  Album.findAll({ where: { title: req.cleanData.query } })
  .then(albums => {
    if (!albums.length) {
      logger.info('Fetching album from apis.');
      return fetch.Album(req.cleanData.query)
      .then(data => {
        res.json({ Success: true, Albums: data, Count: data.length });
        Album.bulkCreate(data, { validate: true });
      });
    }
    logger.info('Found album in the database.');
    res.json({ Success: true, Albums: albums, Count: albums.length });
  })
  .catch(err => {
    logger.error(err);
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};

searchController.track = (req, res) => {
  fetch.Track(req.cleanData.query)
  .then(data => {
    res.json({ Success: true, Tracks: data, Count: data.length });
    Track.bulkCreate(data, { validate: true });
  });
};

module.exports = searchController;
