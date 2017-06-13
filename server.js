import express from 'express';
import low from 'lowdb';
import uuid from 'uuid';
import winston from 'winston';
import config from './config.json';

const _PORT = (process.env.PORT || 3000);

// Setup Winston Logging
const logger = new (winston.logger)({
  transports: [
    new (winston.transports.Console)(),
    new (winston.transports.File)({ filename: 'somefile.log' })
  ]
});

// Setup LowDB
const db = low('db.json');

const discogsApi = require('./discogsApi')(db, config.discogs_api.token);

db.defaults({
  artists: [],
  albums: [],
  tracks: []
}).write();

// Setup Express
const app = express();

// Express middlewares
function cleanSingleId(req, res, next) {
  req.cleanData = {};
  req.cleanData.id = req.params.id.trim();
  if (req.cleanData.id.length == 0) { // Should check for id format (hex or dec maybe?)
    logger.silly(`cleanSingleId: id is invalid`);
    return res.json({ err: 'Invalid id.' });
  }
  next();
}
function cleanMultipleIds(req, res, next) {
  req.cleanData = {};
  req.cleanData.ids = req.query.ids.split(',').map(function(item) {
    return item.trim(); // Remove spaces
  }).filter(function(item) {
    return item.length // Remove empty ids, should check for id format (hex or dec maybe?)
  }).filter(function(item, index, arr) {
    return arr.indexOf(item) == index; // Make the array unique
  });
  if (req.cleanData.ids.length == 0) {
    logger.silly(`cleanMultipleIds: no valid ids`);
    return res.json({ err: 'No valid ids found.' });
  }
  next();
}

function getDB(type, id) {
  return new Promise(function(resolve, reject) {
    // Split ID
    id = id.split('-');
    const provider = id.splice(0, 1)[0];
    id = id.join('-');

    logger.debug(`getDB: Getting ${type} with id ${id} from DB`);

    // Search in DB
    const result = db.get(type)
    .find({ ProviderIds: { [provider]: id } })
    .value();

    // Check result exists and is valid, otherwhise add it or update id
    if (result && (Date.now() - result.LastUpdate) < config.db_record_expiration_days*24*3600*1000) {
      // Return the DB record
      logger.debug(`getDB: ${type} with id ${id} found in the DB and is up to date`);
      resolve(result);
    } else {
      // Add or update the DB record
      discogsApi.get[type](id)
      .then(function(data) {
        data.LastUpdate = Date.now();
        if (result) {
          // Update
          data.Id = db.get(type)
          .find({ ProviderIds: { [provider]: id } })
          .assign(data)
          .write().Id;
        } else {
          // Add
          data.Id = uuid();
          db.get(type)
          .push(data)
          .write();
        }
        logger.debug(`getDB: ${type} with id ${id} ${ result ? 'updated' : 'created' } DB record`);
        resolve(data);
      })
      .catch(function(err) {
        logger.debug(`getDB: received error fetching ${type} with id ${id} from the api`, { err: err });
        reject(err);
      });
    }
  });
}
function getDBMultiple(type, ids) {
  return Promise.all(ids.map(function(id) {
    return getDB(type, id);
  }));
}

// Handle API requests

// Artists
app.get('/artist/:id', cleanSingleId, function(req, res) {
  getDB('artists', req.cleanData.id)
  .then(function(data) {
    res.json(data);
  }, function(err) {
    res.json({ err: err });
  });
});
app.get('/artists', cleanMultipleIds, function(req, res) {
  getDBMultiple('artists', req.cleanData.ids)
  .then(function(data) {
    res.json({
      Artists: data,
      Count: data.length
    });
  }, function(err) {
    res.json({ err: err });
  });
});
app.get('/artist/:id/albums', cleanSingleId, function(req, res) {
  discogsApi.search.albumByArtist(req.cleanData.id)
  .then(function(data) {
    res.json({
      Items: data,
      Count: data.length
    });
  }, function(err) {
    logger.error(`app.get /artist/id/albums: api error`, { err: err });
    res.json({ err: err });
  });
});

// Albums
app.get('/album/:id', cleanSingleId, function(req, res) {
  getDB('albums', req.cleanData.id)
  .then(function(data) {
    res.json(data);
  }, function(err) {
    res.json({ err: err });
  });
});
app.get('/albums', cleanMultipleIds, function(req, res) {
  getDBMultiple('albums', req.cleanData.ids)
  .then(function(data) {
    res.json({
      Albums: data,
      Count: data.length
    });
  }, function(err) {
    res.json({ err: err });
  });
});

// Tracks
app.get('/track/:id', cleanSingleId, function(req, res) {
  getDB('track', req.cleanData.id)
  .then(function(data) {
    res.json(data);
  }, function(err) {
    res.json({ err: err });
  });
});
app.get('/tracks', cleanMultipleIds, function(req, res) {
  getDBMultiple('tracks', req.cleanData.ids)
  .then(function(data) {
    res.json({
      Tracks: data,
      Count: data.length
    });
  }, function(err) {
    res.json({ err: err });
  });
});

// Other
app.get('/search', function(req, res) {
  const queryType = req.query.queryType;
  const query = req.query.query;

  if (['artist'].indexOf(queryType) == -1) {
    logger.silly(`app.get /search: invalid query type`);
    return res.json({ err: 'Invalid query type. Must choose artist.' });
  }

  discogsApi.search[queryType](query)
  .then(function(data) {
    res.json({
      Items: data,
      Count: data.length
    });
  })
  .catch(function(err) {
    logger.error(`app.get /search: api error`, { err: err });
    res.json({ err: 'API error.' });
  });
});

app.listen(_PORT, function(err, port) {
  if (err) return logger.error(`App listening error`, { err: err });
  console.log(`Express app listening at port ${_PORT}...`);
});
