const request = require('request-promise-native');
const url = require('url');
const cheerio = require('cheerio');
const xml2js = require('xml2js');
const Ajv = require('ajv');

const ajv = Ajv();
const validation = {};
validation.search = {};
validation.get = {};
validation.search.artist = ajv.compile({
  type: 'array',
  items: {
    type: 'object',
    properties: {
      mbid: { type: 'string' },
      name: { type: 'string' },
      overview: { type: 'string' }
    },
    required: [ 'mbid', 'name' ]
  },
  additionalProperties: false
});
validation.get.artist = ajv.compile({
  type: 'object',
  properties: {
    mbid: { type: 'string' },
    name: { type: 'string' },
    overview: { type: 'string' },
    images: {
      type: 'array',
      items: { type: 'string' }
    },
    albums: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          mbid: { type: 'string' },
          title: { type: 'string' },
          date: { type: 'string' },
          images: {
            type: 'array',
            items: { type: 'string' }
          },
          tracks: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                mbid: { type: 'string' },
                title: { type: 'string' },
                explicit: { type: 'boolean' }
              },
              required: [ 'title' ],
            }
          }
        },
        required: [ 'mbid', 'title', 'tracks' ]
      }
    }
  },
  required: [ 'mbid', 'name', 'albums' ],
  additionalProperties: false
});

module.exports = class API {
  constructor(name, parsing, baseUri) {
    this.searchDefinitions = {};
    this.getDefinitions = {};

    if (name) this.setName(name);
    if (parsing) this.setParsing(parsing);
    if (baseUri) this.setBaseUri(baseUri);
  }
  setName(name) {
    this.name = name;
  }
  getName() {
    return this.name;
  }
  setParsing(parsing) {
    const parsingOptions = {
      none: ((data) => data),
      json: JSON.parse,
      html: cheerio.load,
      xml: ((xml) => new Promise((fulfil, reject) => {
        xml2js.parseString(xml, (err, obj) => {
          if (err) return reject(err);
          fulfil(obj);
        });
      }))
    };
    if (typeof parsing === 'function') return this.parsingFunc = parsing;
    if (parsingOptions[parsing]) return this.parsingFunc = parsingOptions[parsing];
    throw new Error('Invalid parsing option.');
  }
  setBaseUri(uri) {
    this.baseUri = uri;
  }
  setRequestDefaults(obj) {
    this.requestWrapper = request.defaults(obj);
  }

  executeRequest(method, validationFunc, query) {
    let $this = this;
    return new Promise((fulfil, reject) => {
      if (!method) reject(new Error('This search is not supported by this api.'));
      method(query, function() {
        let reqObj = (arguments.length > 1) ? { uri: url.resolve($this.baseUri, arguments[0]), qs: arguments[1] } : ((typeof arguments[0] === 'string') ? { uri: url.resolve($this.baseUri, arguments[0]) } : arguments[0]);
        return new Promise((fulfil) => {
          $this.requestWrapper(reqObj)
          .then($this.parsingFunc)
          .then(fulfil)
          .catch(reject);
        });
      }, parsedData => {
        if (!validationFunc(parsedData)) return reject(new Error('The api returned invalid data.'));
        fulfil(parsedData);
      });
    });
  }

  // Search should return an array of items from a query
  defineArtistSearch(method) {
    this.searchDefinitions.artist = method;
  }
  searchArtist(query) {
    return this.executeRequest(this.searchDefinitions.artist, validation.search.artist, query);
  }

  // Get should return a single item from an id
  defineArtistGet(method) {
    this.getDefinitions.artist = method;
  }
  getArtist(query) {
    return this.executeRequest(this.getDefinitions.artist, validation.get.artist, query);
  }
}
