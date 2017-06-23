const Router = require('restify-routing');
const { albumController } = require('./../../controllers');
const routes = new Router();

routes.get('/:id', albumController.single);
routes.get('/', albumController.multiple);
routes.get('/byArtist/:id', albumController.byArtist);

module.exports = routes;
