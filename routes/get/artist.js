const Router = require('restify-routing');
const { artistController } = require('./../../controllers');
const routes = new Router();


routes.get('/:ids', artistController.single);
routes.get('/', artistController.multiple);

module.exports = routes;
