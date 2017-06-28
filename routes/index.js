const Router = require('restify-routing');
const routes = new Router();

const Artist = require('./artist');
const Search = require('./search');

routes.use('/artist', Artist);
routes.use('/search', Search);

module.exports = routes;
