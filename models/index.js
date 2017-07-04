const Sequelize = require('sequelize');

const logger = require('./../logger');
const config = require('./../config.json');

// Setup DB, load models and setup relationships

const sequelize = new Sequelize(config.db.database, config.db.username, config.db.password, {
  host: config.db.host,
  dialect: 'postgres',
  //logging: logger.info.bind(logger)
  logging: false
});

const Artist = sequelize.import('./artist');
const Album = sequelize.import('./album');
const Track = sequelize.import('./track');
const Image = sequelize.import('./image');

Album.belongsTo(Artist);
Artist.hasMany(Album);
Track.belongsTo(Artist);
Artist.hasMany(Track);
Track.belongsTo(Album);
Album.hasMany(Track);

Artist.hasMany(Image);
Image.belongsTo(Artist);
Album.hasMany(Image);
Image.belongsTo(Album);

module.exports = {
  Sequelize,
  sequelize,
  Artist,
  Album,
  Track,
  Image
};
