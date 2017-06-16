const request = require('request-promise-native');
const url = require('url');
const crypto = require('crypto');
const cheerio = require('cheerio');
const xml2json = require('xml2json');

module.exports = class API {
  constructor(name, parsing, baseUri) {
    this.searchDefinitions = new Map();
    this.getDefinitions = new Map();
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
      xml: ((xml) => JSON.parse(xml2json.toJson(xml, { arrayNotation: true })))
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
  encodeId(id) {
    return this.name + '-' + id;
  }
  decodeId(id) {
    return id.split('-').slice(1).join('-');
  }
  // Search should return an array of items from a query
  defineSearchMethod(searchType, method) {
    this.searchDefinitions.set(searchType, method);
  }
  search(searchType, query) {
    let $this = this;
    let method = $this.searchDefinitions.get(searchType);
    return new Promise((fulfil, reject) => {
      method(query, function() {
        let reqObj = (arguments.length > 1) ? { uri: url.resolve($this.baseUri, arguments[0]), qs: arguments[1] } : ((typeof arguments[0] === 'string') ? { uri: url.resolve($this.baseUri, arguments[0]) } : arguments[0]);
        return new Promise((fulfil) => {
          $this.requestWrapper(reqObj)
          .then($this.parsingFunc)
          .then(fulfil)
          .catch(reject);
        });
      }, fulfil);
    });
  }
  // Get should return a single item from an id
  defineGetMethod(searchType, method) {
    this.getDefinitions.set(searchType, method);
  }
  get(searchType, query) {
    let $this = this;
    let method = $this.getDefinitions.get(searchType);
    return new Promise((fulfil, reject) => {
      method(query, function() {
        let reqObj = (arguments.length > 1) ? { uri: url.resolve($this.baseUri, arguments[0]), qs: arguments[1] } : ((typeof arguments[0] === 'string') ? { uri: url.resolve($this.baseUri, arguments[0]) } : arguments[0]);
        return new Promise((fulfil) => {
          $this.requestWrapper(reqObj)
          .then($this.parsingFunc)
          .then(fulfil)
          .catch(reject);
        });
      }, fulfil);
    });
  }
}
