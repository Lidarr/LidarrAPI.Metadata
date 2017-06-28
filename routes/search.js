const Router = require('restify-routing');
const { searchController } = require('./../controllers');
const routes = new Router();

routes.all('**', (req, res, next) => {
  req.cleanData = {};
  req.cleanData.query = req.params.query.trim();
  if (!req.cleanData.query.length) {
    res.status(400);
    return res.json({ Success: false, Message: 'Invalid query.' });
  }
  next();
});

routes.get('/artist/:query', searchController.artist);

module.exports = routes;
