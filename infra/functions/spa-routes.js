function handler(event) {
  var request = event.request;
  // Route only the known Vue pages; missing assets still return genuine errors.
  // This serves the public shell. APIs must independently authorize access tokens.
  if (/^\/(tools(?:\/minecraft)?\/?|about\/?|projects(?:\/[a-z0-9-]+)?\/?|login\/?|auth\/callback\/?)$/.test(request.uri)) {
    request.uri = '/index.html';
  }
  return request;
}
