const Router = require('restify-routing');
const routes = new Router();

const Artist = require('./artist');
const Album = require('./album');
const Track = require('./track');

routes.all('**', (req, res, next) => {
  req.cleanData = {};
  if (req.params.id) {
    req.cleanData.id = req.params.id.trim();
    if (!req.cleanData.id.length) { // Should check for id format (hex or dec maybe?)
      logger.silly(`cleanSingleId: id is invalid`);
      return res.status(400).json({ err: 'Invalid id.' });
    }
  } else if (req.query.ids) {
    req.cleanData.ids = req.query.ids.split(',')
    .map(function(item) {
      return item.trim(); // Remove spaces
    }).filter(function(item) {
      return item.length; // Remove empty ids, should check for id format (hex or dec maybe?)
    }).filter(function(item, index, arr) {
      return arr.indexOf(item) == index; // Make the array unique
    });
    if (!req.cleanData.ids.length) {
      logger.silly(`cleanMultipleIds: no valid ids`);
      return res.status(400).json({ err: 'No valid ids found.' });
    }
  }
  next();
});

routes.use('/artist', Artist);
routes.use('/album', Album);
routes.use('/track', Track);

module.exports = routes;
