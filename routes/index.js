const Router = require('restify-routing');
const routes = new Router();

const Get = require('./get');
const Search = require('./search');

routes.use('/get', Get);
routes.use('/search', Search);

module.exports = routes;
