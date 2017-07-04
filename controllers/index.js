// Load other controllers and combine them in an object

const artistController = require('./artistController');
const searchController = require('./searchController');

module.exports = {
  artistController,
  searchController
};
