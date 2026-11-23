/**
 * core/fetch-rewrite.js - file:// WebView -> core origin fetch rewrite.
 *
 * The WebView loads from file:///android_asset/web/, so main.js builds its
 * transport from window.location.origin ("file://") and the Connect/grpc-web
 * transport then fetches e.g.
 *   file://exa.language_server_pb.languageserverservice/Method
 * which the WebView rejects: URL scheme "file" is not supported.
 *
 * Rewrite file:// or relative ConnectRPC URLs onto the core origin, preserving
 * method/headers/body and attaching the CSRF token. Idempotent and a no-op for
 * non-RPC / already-absolute http(s) URLs.
 *
 * The original periodic HEAD ping is not ported (it referenced an undefined
 * helper; see docs/DEADCODE.md).
 */
var RPC_MARKERS = ['exa.language_server_pb.', 'exa.host_bridge_pb.', '/exa.'];

// RPC path (no leading slash) when `url` is a file:// or relative ConnectRPC
// URL; null for anything else (http(s), blob, data, static assets).
function rpcPathFrom(url) {
  if (!url) return null;
  var s = String(url);
  if (typeof window !== 'undefined' && window.location && window.location.origin && window.location.origin !== 'null' && s.startsWith(window.location.origin)) {
    s = s.slice(window.location.origin.length);
  } else if (/^(https?|blob|data|wss?|chrome-extension):/i.test(s)) {
    return null;
  }
  var best = -1;
  for (var i = 0; i < RPC_MARKERS.length; i++) {
    var at = s.indexOf(RPC_MARKERS[i]);
    if (at >= 0 && (best === -1 || at < best)) best = at;
  }
  if (best === -1) return null;
  return s.slice(best).replace(/^\/+/, '') || null;
}

function installFetchRewrite() {
  if (global.__AG_FETCH_REWRITE__ || typeof global.fetch !== 'function') return;
  var origFetch = global.fetch.bind(global);

  function fetchWithStartupRetry(u, opts, retries) {
    return origFetch(u, opts).catch(function (err) {
      if (retries > 0) {
        return new Promise(function (resolve) {
          setTimeout(function () {
            resolve(fetchWithStartupRetry(u, opts, retries - 1));
          }, 120);
        });
      }
      throw err;
    });
  }

  global.fetch = function (resource, init) {
    try {
      // Request object: rebuild against the core origin, keep method/body.
      if (resource && typeof resource === 'object' && typeof resource.url === 'string') {
        var rpath = rpcPathFrom(resource.url);
        if (rpath) {
          try {
            var targetUrl = appendCsrfQuery(coreBase() + '/' + rpath);
            var reqMethod = resource.method || (init && init.method) || 'POST';
            var reqHeaders = new Headers(resource.headers || (init && init.headers) || {});
            ensureCsrf(reqHeaders);

            var bodyPromise;
            if (init && init.body !== undefined) {
              bodyPromise = Promise.resolve(init.body);
            } else {
              try {
                bodyPromise = resource.clone().arrayBuffer().then(function (buf) {
                  return buf.byteLength > 0 ? buf : undefined;
                }).catch(function () { return undefined; });
              } catch (e) {
                bodyPromise = Promise.resolve(undefined);
              }
            }

            return bodyPromise.then(function (bodyData) {
              var nextOpts = {
                method: reqMethod,
                headers: reqHeaders,
                body: bodyData,
                credentials: 'omit'
              };
              return fetchWithStartupRetry(targetUrl, nextOpts, 30);
            });
          } catch (e) { warn('fetch rewrite (Request)', e); }
        }
        return origFetch(resource, init);
      }

      // String URL: the Connect/grpc-web transport's common path.
      if (typeof resource === 'string') {
        var path = rpcPathFrom(resource);
        if (path) {
          var url = appendCsrfQuery(coreBase() + '/' + path);
          var headers = new Headers((init && init.headers) || {});
          ensureCsrf(headers);
          var next = {};
          if (init) {
            for (var k in init) {
              if (Object.prototype.hasOwnProperty.call(init, k)) next[k] = init[k];
            }
          }
          next.headers = headers;

          return fetchWithStartupRetry(url, next, 30);
        }
      }
    } catch (e) { warn('fetch rewrite', e); }
    return origFetch(resource, init);
  };
  global.__AG_FETCH_REWRITE__ = true;
function configureModelGateway() {
    // The WebView origin is https://127.0.0.1:<enginePort>, so an HTTP probe
    // to the proxy port is blocked by CORS. Skip the probe: send SetCloudCodeURL
    // straight to the local core RPC (same origin). The core then talks to the
    // proxy itself; retries cover the case where node is still installing.
    var targetUrl = 'http://127.0.0.1:50996';
    var attempts = 0;
    function apply() {
      setRpcUrl(targetUrl, function () {
        warn('model-gateway', 'Cloud Code routed to ' + targetUrl);
      });
      attempts++;
      if (attempts < 20) {
        setTimeout(apply, 3000);
      }
    }
    apply();

    function setRpcUrl(url, onSuccess) {
      try {
        var rpcUrl = appendCsrfQuery(coreBase() + '/exa.language_server_pb.LanguageServerService/SetCloudCodeURL');
        var reqHeaders = new Headers({
          'Content-Type': 'application/json',
          'Connect-Protocol-Version': '1'
        });
        ensureCsrf(reqHeaders);
        fetchWithStartupRetry(rpcUrl, {
          method: 'POST',
          headers: reqHeaders,
          body: JSON.stringify({ url: url })
        }, 5).then(function (rpcRes) {
          if (rpcRes && rpcRes.ok && typeof onSuccess === 'function') onSuccess();
        }).catch(function (err) {
          warn('model-gateway', 'SetCloudCodeURL error', err);
        });
      } catch (e) {
        warn('model-gateway', 'SetCloudCodeURL failure', e);
      }
    }
  }

  setTimeout(configureModelGateway, 1000);
}

function installMediaPolyfills() {
  try {
    if (typeof navigator !== 'undefined' && navigator.permissions && navigator.permissions.query) {
      var origQ = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = function(d) {
        if (d && d.name === 'microphone') {
          return Promise.resolve({ name: 'microphone', state: 'granted', onchange: null });
        }
        return origQ(d);
      };
    }
    if (typeof navigator !== 'undefined' && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      var origG = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = function(c) {
        var cl = c;
        if (c && typeof c === 'object') {
          cl = Object.assign({}, c);
          if (cl.audio && typeof cl.audio === 'object') {
            cl.audio = Object.assign({}, cl.audio);
            delete cl.audio.voiceIsolation;
          }
        }
        return origG(cl).catch(function(err) {
          if (err && (err.name === 'NotReadableError' || err.name === 'OverconstrainedError' || err.name === 'AbortError')) {
            return new Promise(function(res) { setTimeout(res, 180); }).then(function() {
              return origG({ audio: true });
            });
          }
          throw err;
        });
      };
    }
  } catch (e) {
    if (typeof console !== 'undefined' && console.warn) console.warn('[AGY_AUDIO] media polyfill init error', e);
  }
}

installFetchRewrite();
installMediaPolyfills();

function installResumeHandler() {
  try {
    if (global.__AG_RESUME_HANDLER__) return;
    global.__AG_RESUME_HANDLER__ = true;
    global.addEventListener('agy:host-resume', function () {
      try {
        global.dispatchEvent(new Event('focus'));
        global.dispatchEvent(new Event('online'));
        if (typeof document !== 'undefined') {
          document.dispatchEvent(new Event('visibilitychange'));
        }
      } catch (err) {
        if (typeof console !== 'undefined' && console.warn) {
          console.warn('[AGY] host-resume dispatch error', err);
        }
      }
    });
  } catch (e) {
    if (typeof console !== 'undefined' && console.warn) {
      console.warn('[AGY] resume handler install error', e);
    }
  }
}

installResumeHandler();
