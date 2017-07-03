const logger = require('./../logger');
const fetch = require('./../fetch');
const { Artist, Album, Track } = require('./../models');

const searchController = {};

searchController.artist = (req, res) => {
  logger.info('Fetching artist from apis.');
  return fetch.searchArtist(req.cleanData.query)
  .then(data => res.json(data));
};

module.exports = searchController;
