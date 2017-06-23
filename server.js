const restify = require('restify');
const bunyan = require('bunyan');

const config = require('./config.json');
const logger = require('./logger');

const _PORT = (process.env.PORT || 3000);

// SETUP DB
const db = require('./models');
db.sequelize.authenticate()
.then(() => db.sequelize.sync({}))
.catch(err => logger.error('Unable to connect to the database: ', err))
.then(() => {

  // Setup Restify
  const server = restify.createServer();

  server.use(restify.queryParser());

  // Dump all requests
  server.on('after', restify.auditLogger({ log: bunyan.createLogger({
      name: 'audit',
      stream: process.stdout
    }), body: true }));

  const routes = require('./routes');

  // Handle API requests
  routes.applyRoutes(server);

  server.listen(_PORT, (err, port) => {
    if (err) return logger.error(`App listening error`, { err: err });
    console.log(`Restify app listening at port ${_PORT}...`);
    logger.info(`Restify app listening at port ${_PORT}...`);
  });

});
