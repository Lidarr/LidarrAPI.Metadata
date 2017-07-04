const Router = require('restify-routing');
const routes = new Router();

// Load other routers and dispatch request to them

const Artist = require('./artist');
const Search = require('./search');

routes.use('/artist', Artist);
routes.use('/search', Search);

module.exports = routes;
