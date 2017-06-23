const Router = require('restify-routing');
const { trackController } = require('./../../controllers');
const routes = new Router();

routes.get('/:id', trackController.single);
routes.get('/', trackController.multiple);
routes.get('/fromAlbum/:id', trackController.fromAlbum);

module.exports = routes;
