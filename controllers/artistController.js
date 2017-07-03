const logger = require('./../logger');
const fetch = require('./../fetch');
const { Artist, Album, Track } = require('./../models');

const artistController = {};

artistController.artist = (req, res) =>
  Artist.findOne({
    where: { Id: req.cleanData.id },
    attributes: [ 'Id', 'ArtistName', 'Overview' ],
    include: [{ model: Album, attributes: [ 'Id', 'Title', 'ReleaseDate' ], include: [{ model: Track, attributes: [ 'Id', 'Title', 'Explicit' ] }] }]
  })
  .then(artist => {
    if (!artist) {
      fetch.getArtist(req.cleanData.id)
      .then(data => {
        logger.info('Saved new artist in the database');
        res.json(data);
      })
      .catch(err => {
        logger.error('Database error', err);
        res.status(500);
        res.send('Database error.');
      });
    } else res.json(artist);
  })
  .catch(err => {
    logger.error('Database error', err);
    res.status(500);
    res.send('Database error.');
  });

// artistController.albums = (req, res) =>
//   Artist.findOne({ where: { mbid: req.cleanData.id } })
//   .then(artist => {
//     if (!artist) {
//       fetch.getArtist(req.cleanData.id)
//       .then(data => {
//         logger.info('Saved new artist in the database');
//         res.json(data.albums);
//       })
//       .catch(err => {
//         logger.error('Database error', err);
//         res.status(500);
//         res.send('Database error.');
//       });
//     } else {
//       Album.findAll({
//         where: { artist_id: artist.id },
//         attributes: [ 'mbid', 'title', 'date' ],
//         include: [{ model: Track, attributes: [ 'mbid', 'title', 'explicit' ] }]
//       })
//       .then(albums => {
//         res.json({ Success: true, Albums: albums });
//       })
//       .catch(err => {
//         logger.error('Database error', err);
//         res.status(500);
//         res.send('Database error.');
//       });
//     }
//   })
//   .catch(err => {
//     logger.error('Database error', err);
//     res.status(500);
//     res.send('Database error.');
//   });

module.exports = artistController;
