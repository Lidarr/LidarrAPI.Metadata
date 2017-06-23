const { Album } = require('./../models');

const albumController = {};

albumController.single = (req, res) => {
  Album.findById(req.cleanData.id)
  .then(album => {
    if (!album) {
      res.status(404);
      return res.json({ Success: false, Message: 'Not found.' });
    }
    res.json({ Success: true, Album: album });
  })
  .catch(err => {
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};
albumController.multiple = (req, res) => {
  Album.findAll({ where: { id: req.cleanData.ids } })
  .then(albums => {
    res.json({ Success: true, Albums: albums, Count: albums.length });
  })
  .catch(err => {
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};
albumController.byArtist = (req, res) => {
  Album.findAll({ where: { artist_id: req.cleanData.id } })
  .then(albums => {
    res.json({ Success: true, Albums: albums, Count: albums.length });
  })
  .catch(err => {
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};

module.exports = albumController;
