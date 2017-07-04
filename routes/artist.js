const Router = require('restify-routing');
const { artistController } = require('./../controllers');
const routes = new Router();

// Middleware to clean the id
routes.all('**', (req, res, next) => {
  req.cleanData = {};
  req.cleanData.id = req.params.id.trim();
  if (req.cleanData.id) return next();
  logger.silly(`cleanSingleId: id is invalid`);
  res.status(400);
  res.send('Invalid id.');
});

routes.get('/:id', artistController.artist);
// routes.get('/:id/albums', artistController.albums);

module.exports = routes;
