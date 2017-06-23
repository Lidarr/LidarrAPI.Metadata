const { Track } = require('./../models');

const trackController = {};

trackController.single = (req, res) => {
  Track.findById(req.cleanData.id)
  .then(track => {
    if (!track) {
      res.status(404);
      return res.json({ Success: false, Message: 'Not found.' });
    }
    res.json({ Success: true, Track: track });
  })
  .catch(err => {
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};
trackController.multiple = (req, res) => {
  Track.findAll({ where: { id: req.cleanData.ids } })
  .then(tracks => {
    res.json({ Success: true, Tracks: tracks, Count: tracks.length });
  })
  .catch(err => {
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};
trackController.fromAlbum = (req, res) => {
  Track.findAll({ where: { album_id: req.cleanData.id } })
  .then(tracks => {
    res.json({ Success: true, Tracks: tracks, Count: tracks.length });
  })
  .catch(err => {
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};

module.exports = trackController;
