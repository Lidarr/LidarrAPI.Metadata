const request = require('request-promise-native');
const url = require('url');

module.exports = class API {
  constructor(name, type, baseUri) {
    this.searchDefinitions = new Map();
    this.getDefinitions = new Map();
    this.setRequestDefaults({});

    if (name) this.setName(name);
    if (type) this.setType(type);
    if (baseUri) this.setBaseUri(baseUri);
  }
  setName(name) {
    this.name = name;
  }
  getName() {
    return this.name;
  }
  setType(type) {
    // TODO: html parsing
    if (type != 'rest') throw new Error('Api type must be rest.');
    this.type = type;
  }
  setBaseUri(uri) {
    this.baseUri = uri;
  }
  setRequestDefaults(obj) {
    this.requestWrapper = request.defaults(obj);
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
          .then(fulfil)
          .catch(reject);
        });
      }, fulfil);
    });
  }
}
