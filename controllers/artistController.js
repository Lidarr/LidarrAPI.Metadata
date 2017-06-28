const logger = require('./../logger');
const fetch = require('./../fetch');
const { Artist, Album, Track } = require('./../models');

const artistController = {};

artistController.artist = (req, res) =>
  Artist.findOne({
    where: { mbid: req.cleanData.id },
    attributes: [ 'mbid', 'name', 'overview' ]
  })
  .then(artist => {
    if (!artist) {
      fetch.getArtist(req.cleanData.id)
      .then(data => {
        logger.info('Saved new artist in the database');
        res.json({ Success: true, Artist: (i => {delete i.albums; return i;})(data) });
      })
      .catch(err => {
        logger.error('Database error', err);
        res.status(500);
        res.json({ Success: false, Message: 'Database error.' });
      });
    } else res.json({ Success: true, Artist: artist });
  })
  .catch(err => {
    logger.error('Database error', err);
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });

artistController.albums = (req, res) =>
  Artist.findOne({ where: { mbid: req.cleanData.id } })
  .then(artist => {
    if (!artist) {
      fetch.getArtist(req.cleanData.id)
      .then(data => {
        logger.info('Saved new artist in the database');
        res.json({ Success: true, Albums: data.albums });
      })
      .catch(err => {
        logger.error('Database error', err);
        res.status(500);
        res.json({ Success: false, Message: 'Database error.' });
      });
    } else {
      Album.findAll({
        where: { artist_id: artist.id },
        attributes: [ 'mbid', 'title', 'date' ],
        include: [{ model: Track, attributes: [ 'mbid', 'title', 'explicit' ] }]
      })
      .then(albums => {
        res.json({ Success: true, Albums: albums });
      })
      .catch(err => {
        logger.error('Database error', err);
        res.status(500);
        res.json({ Success: false, Message: 'Database error.' });
      });
    }
  })
  .catch(err => {
    logger.error('Database error', err);
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });

module.exports = artistController;
