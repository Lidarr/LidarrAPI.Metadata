const { Artist } = require('./../models');

const artistController = {};

artistController.single = (req, res) => {
  Artist.findById(req.cleanData.id)
  .then(artist => {
    if (!artist) {
      res.status(404);
      return res.json({ Success: false, Message: 'Not found.' });
    }
    res.json({ Success: true, Artist: artist });
  })
  .catch(err => {
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};
artistController.multiple = (req, res) => {
  Artist.findAll({ where: { id: req.cleanData.ids } })
  .then(artists => {
    res.json({ Success: true, Artists: artists, Count: artists.length });
  })
  .catch(err => {
    res.status(500);
    res.json({ Success: false, Message: 'Database error.' });
  });
};

module.exports = artistController;
