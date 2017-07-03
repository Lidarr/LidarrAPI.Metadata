const bunyan = require('bunyan');

// Moved to a separate module so it can be required by any other module
module.exports = bunyan.createLogger({
  name: 'LidarrAPI.Metadata',
  streams: [
    {
      level: 'info',
      stream: process.stdout,
    },
    {
      level: 'info',
      path: './logfile.log'
    }
  ]
});
