const Router = require('restify-routing');
const { searchController } = require('./../controllers');
const routes = new Router();

// Middleware to clean the query
routes.all('**', (req, res, next) => {
  req.cleanData = {};
  req.cleanData.query = req.params.query.trim();
  if (req.cleanData.query.length) return next();
  res.status(400);
  res.send('Invalid query.');
});

routes.get('/artist/:query', searchController.artist);

module.exports = routes;
