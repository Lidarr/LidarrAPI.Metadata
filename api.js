const request = require('request-promise-native');
const url = require('url');
const cheerio = require('cheerio');
const xml2js = require('xml2js');
const Ajv = require('ajv');

const ajv = Ajv();
const validation = {};
validation.artist = ajv.compile({
  type: 'object',
  properties: {
    name: { type: 'string' }
  },
  required: [ 'name' ],
  additionalProperties: false
});
validation.album = ajv.compile({
  type: 'object',
  properties: {
    title: { type: 'string' },
    year: { type: 'integer' }
  },
  required: [ 'title', 'year' ],
  additionalProperties: false
});
validation.track = ajv.compile({
  type: 'object',
  properties: {
    title: { type: 'string' },
    number: { type: 'integer' }
  },
  required: [ 'title', 'number' ],
  additionalProperties: false
});

module.exports = class API {
  constructor(name, parsing, baseUri) {
    this.searchDefinitions = {};
    // this.getDefinitions = new Map();
    this.setRequestDefaults({});

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

  // Search should return an array of items from a query
  defineArtistSearch(method) {
    this.searchDefinitions.artist = method;
  }
  defineAlbumSearch(method) {
    this.searchDefinitions.album = method;
  }
  defineTrackSearch(method) {
    this.searchDefinitions.track = method;
  }

  executeSearch(method, validationFunc, query) {
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
      }, (parsedData) => {
        //if (!validationFunc(parsedData)) return reject(new Error('The api returned invalid data.'));
        fulfil(parsedData);
      });
    });
  }

  searchArtist(query) {
    return this.executeSearch(this.searchDefinitions.artist, validation.artist, query);
  }
  searchAlbum(query) {
    return this.executeSearch(this.searchDefinitions.album, validation.album, query);
  }
  searchTrack(query) {
    return this.executeSearch(this.searchDefinitions.track, validation.track, query);
  }

  // Not needed, maybe useful for updating data?
  // // Get should return a single item from an id
  // defineGetMethod(searchType, method) {
  //   this.getDefinitions.set(searchType, method);
  // }
  // get(searchType, query) {
  //   let $this = this;
  //   let method = $this.getDefinitions.get(searchType);
  //   return new Promise((fulfil, reject) => {
  //     method(query, function() {
  //       let reqObj = (arguments.length > 1) ? { uri: url.resolve($this.baseUri, arguments[0]), qs: arguments[1] } : ((typeof arguments[0] === 'string') ? { uri: url.resolve($this.baseUri, arguments[0]) } : arguments[0]);
  //       return new Promise((fulfil) => {
  //         $this.requestWrapper(reqObj)
  //         .then($this.parsingFunc)
  //         .then(fulfil)
  //         .catch(reject);
  //       });
  //     }, fulfil);
  //   });
  // }
}
