/* Puiching eClass cross-device sync (todos + points).
   Static GitHub Pages friendly: Firebase Realtime Database + Anonymous Auth.
   - todos:  puiching-eclass-todos-v1  (key -> true), per-key last-write-wins
   - points: puiching-eclass-points-v1 (childId -> {earned,spent,awarded,bonusDates,redemptions}), per-child last-write-wins
   Offline-first: localStorage always works; pending writes replay on reconnect.
   Pages must include a <div id="sync-panel"> and call window.PuichingSync.register().
*/
(function () {
  'use strict';

  var TODO_STORE_KEY = 'puiching-eclass-todos-v1';
  var POINTS_STORE_KEY = 'puiching-eclass-points-v1';
  var SYNC_CODE_KEY = 'puiching-eclass-sync-code-v1';
  var PENDING_STORE_KEY = 'puiching-eclass-sync-pending-v1';
  var CODE_LENGTH = 20;
  var CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
  var CODE_PATTERN = /^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{20}$/;
  var FIREBASE_VERSION = '10.14.1';

  var state = {
    handlers: {},
    local: { todos: {}, points: {} },
    remote: { todos: {}, points: {} },
    pending: { todos: {}, points: {} },
    listeners: [],
    connected: false,
    applyingRemote: false,
    code: '',
    roomId: '',
    roomRef: null,
    auth: null,
    db: null,
    disconnectTimer: null,
    retryTimer: null
  };

  function isObject(v) { return v && typeof v === 'object' && !Array.isArray(v); }
  function hasOwn(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

  function readJson(key) {
    try {
      var p = JSON.parse(localStorage.getItem(key) || '{}');
      return isObject(p) ? p : {};
    } catch (e) { return {}; }
  }
  function writeJson(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }
  function clone(o) { return Object.assign({}, isObject(o) ? o : {}); }

  function sanitizeTodos(value) {
    var out = {};
    if (!isObject(value)) return out;
    Object.keys(value).forEach(function (k) { if (value[k] === true) out[k] = true; });
    return out;
  }

  function sanitizePointsChild(v) {
    var out = { earned: 0, spent: 0, awarded: {}, bonusDates: {}, redemptions: [] };
    if (!isObject(v)) return out;
    if (typeof v.earned === 'number' && v.earned >= 0) out.earned = Math.floor(v.earned);
    if (typeof v.spent === 'number' && v.spent >= 0) out.spent = Math.floor(v.spent);
    if (isObject(v.awarded)) {
      Object.keys(v.awarded).forEach(function (k) { if (v.awarded[k] === true) out.awarded[k] = true; });
    }
    if (isObject(v.bonusDates)) {
      Object.keys(v.bonusDates).forEach(function (k) { if (v.bonusDates[k] === true) out.bonusDates[k] = true; });
    }
    if (Array.isArray(v.redemptions)) {
      out.redemptions = v.redemptions.filter(function (r) {
        return isObject(r) && typeof r.id === 'string' && typeof r.cost === 'number';
      }).slice(-50).map(function (r) {
        return { id: r.id, name: String(r.name || r.id), cost: r.cost, at: String(r.at || '') };
      });
    }
    return out;
  }

  function sanitizePoints(value) {
    var out = {};
    if (!isObject(value)) return out;
    Object.keys(value).forEach(function (childId) {
      if (/^[a-z0-9-]+$/.test(childId)) out[childId] = sanitizePointsChild(value[childId]);
    });
    return out;
  }

  function sanitizePending(kind, value) {
    var out = {};
    if (!isObject(value)) return out;
    Object.keys(value).forEach(function (k) {
      if (kind === 'todos' && typeof value[k] === 'boolean') out[k] = value[k];
      if (kind === 'points' && isObject(value[k])) out[k] = sanitizePointsChild(value[k]);
    });
    return out;
  }

  function readPending() {
    var v = readJson(PENDING_STORE_KEY);
    return { todos: sanitizePending('todos', v.todos), points: sanitizePending('points', v.points) };
  }
  function writePending() {
    var todosCount = Object.keys(state.pending.todos || {}).length;
    var pointsCount = Object.keys(state.pending.points || {}).length;
    if (todosCount === 0 && pointsCount === 0) {
      try { localStorage.removeItem(PENDING_STORE_KEY); } catch (e) {}
    } else {
      writeJson(PENDING_STORE_KEY, state.pending);
    }
  }

  function getConfig() { return window.PUICHING_SYNC_CONFIG || {}; }
  function isConfigured() {
    var c = getConfig();
    return c.enabled !== false &&
      ['apiKey', 'authDomain', 'databaseURL', 'projectId', 'appId'].every(function (k) { return Boolean(c[k]); });
  }

  function normalizeCode(v) { return String(v || '').toUpperCase().replace(/[\s-]/g, ''); }
  function formatCode(v) {
    var c = normalizeCode(v);
    return (c.match(/.{1,4}/g) || []).join('-') || c;
  }
  function readSavedCode() {
    try { return normalizeCode(localStorage.getItem(SYNC_CODE_KEY) || ''); } catch (e) { return ''; }
  }
  function saveCode(c) { try { localStorage.setItem(SYNC_CODE_KEY, c); } catch (e) {} }
  function clearSavedCode() { try { localStorage.removeItem(SYNC_CODE_KEY); } catch (e) {} }

  /**
   * Updates sync panel indicator state with exact 4 state badges:
   * - 已同步 ☁️
   * - 本機模式 💻
   * - 連接中…
   * - 已離線 ⚠️
   */
  function updatePanel(label, message, connected) {
    var panel = document.getElementById('sync-panel');
    if (panel) {
      var s = panel.querySelector('[data-sync-state]');
      var m = panel.querySelector('[data-sync-message]');
      if (s) {
        s.textContent = label;
        s.classList.remove('connected', 'local', 'connecting', 'offline');
        if (label.indexOf('已同步') !== -1 || connected) {
          s.classList.add('connected');
          s.setAttribute('data-sync-state', 'connected');
        } else if (label.indexOf('本機模式') !== -1) {
          s.classList.add('local');
          s.setAttribute('data-sync-state', 'local');
        } else if (label.indexOf('連接中') !== -1) {
          s.classList.add('connecting');
          s.setAttribute('data-sync-state', 'connecting');
        } else if (label.indexOf('已離線') !== -1) {
          s.classList.add('offline');
          s.setAttribute('data-sync-state', 'offline');
        }
      }
      if (m && message !== undefined) m.textContent = message;
    }

    document.querySelectorAll('[data-sync-state-badge]').forEach(function (b) {
      b.textContent = label;
      b.classList.remove('connected', 'local', 'connecting', 'offline');
      if (label.indexOf('已同步') !== -1 || connected) {
        b.classList.add('connected');
      } else if (label.indexOf('本機模式') !== -1) {
        b.classList.add('local');
      } else if (label.indexOf('連接中') !== -1) {
        b.classList.add('connecting');
      } else if (label.indexOf('已離線') !== -1) {
        b.classList.add('offline');
      }
    });
  }
  function panelInput() { return document.querySelector('#sync-code'); }

  function generateCode() {
    var vals = new Uint32Array(CODE_LENGTH);
    if (window.crypto && window.crypto.getRandomValues) {
      window.crypto.getRandomValues(vals);
      return Array.from(vals, function (v) { return CODE_ALPHABET[v % CODE_ALPHABET.length]; }).join('');
    }
    return Array.from({ length: CODE_LENGTH }, function () {
      return CODE_ALPHABET[Math.floor(Math.random() * CODE_ALPHABET.length)];
    }).join('');
  }

  function pureJsSha256(ascii) {
    function rightRotate(value, amount) { return (value >>> amount) | (value << (32 - amount)); }
    var mathPow = Math.pow;
    var maxWord = mathPow(2, 32);
    var lengthProperty = 'length';
    var i, j;
    var result = '';
    var words = [];
    var asciiBitLength = ascii[lengthProperty] * 8;
    var hash = [];
    var k = [];
    var primeCounter = 0;
    var isComposite = {};
    for (var candidate = 2; primeCounter < 64; candidate++) {
      if (!isComposite[candidate]) {
        for (i = 0; i < 313; i += candidate) { isComposite[i] = candidate; }
        hash[primeCounter] = (mathPow(candidate, 0.5) * maxWord) | 0;
        k[primeCounter++] = (mathPow(candidate, 1 / 3) * maxWord) | 0;
      }
    }
    hash = hash.slice(0, 8);
    ascii += '\x80';
    while (ascii[lengthProperty] % 64 - 56) ascii += '\x00';
    for (i = 0; i < ascii[lengthProperty]; i++) {
      j = ascii.charCodeAt(i);
      if (j >> 8) return '';
      words[i >> 2] |= j << ((3 - i) % 4) * 8;
    }
    words[words[lengthProperty]] = ((asciiBitLength / maxWord) | 0);
    words[words[lengthProperty]] = (asciiBitLength) | 0;
    for (j = 0; j < words[lengthProperty];) {
      var w = words.slice(j, j += 16);
      var oldHash = hash;
      hash = hash.slice(0, 8);
      for (i = 0; i < 64; i++) {
        var w15 = w[i - 15], w2 = w[i - 2];
        var a = hash[0], e = hash[4];
        var temp1 = hash[7]
          + (rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25))
          + ((e & hash[5]) ^ ((~e) & hash[6]))
          + k[i]
          + (w[i] = (i < 16) ? w[i] : (
              w[i - 16]
              + (rightRotate(w15, 7) ^ rightRotate(w15, 18) ^ (w15 >>> 3))
              + w[i - 7]
              + (rightRotate(w2, 17) ^ rightRotate(w2, 19) ^ (w2 >>> 10))
            ) | 0
          );
        var temp2 = (rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22))
          + ((a & hash[1]) ^ (a & hash[2]) ^ (hash[1] & hash[2]));
        hash = [(temp1 + temp2) | 0].concat(hash);
        hash[4] = (hash[4] + temp1) | 0;
      }
      for (i = 0; i < 8; i++) { hash[i] = (hash[i] + oldHash[i]) | 0; }
    }
    for (i = 0; i < 8; i++) {
      for (var i2 = 3; i2 >= 0; i2--) {
        var b = (hash[i] >> (i2 * 8)) & 255;
        result += ((b < 16) ? '0' : '') + b.toString(16);
      }
    }
    return result;
  }

  function digestCode(code) {
    var raw = 'puiching-eclass-room-v1:' + code;
    if (window.crypto && window.crypto.subtle && typeof window.crypto.subtle.digest === 'function' && window.TextEncoder) {
      try {
        var bytes = new TextEncoder().encode(raw);
        return window.crypto.subtle.digest('SHA-256', bytes).then(function (d) {
          return Array.from(new Uint8Array(d), function (b) { return b.toString(16).padStart(2, '0'); }).join('');
        }).catch(function () {
          return pureJsSha256(raw);
        });
      } catch (e) {
        return Promise.resolve(pureJsSha256(raw));
      }
    }
    return Promise.resolve(pureJsSha256(raw));
  }

  function encodePath(value) {
    var bytes = new TextEncoder().encode(value);
    var bin = '';
    bytes.forEach(function (b) { bin += String.fromCharCode(b); });
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function samePoints(a, b) {
    try { return JSON.stringify(a || null) === JSON.stringify(b || null); } catch (e) { return false; }
  }
  function equalValue(kind, a, b) {
    if (kind === 'todos') return Boolean(a) === Boolean(b);
    return samePoints(a, b);
  }
  function defaultValue(kind) { return kind === 'todos' ? false : null; }
  function localValue(kind, store, key) {
    if (hasOwn(store, key)) return store[key];
    return defaultValue(kind);
  }

  function safeFirebaseKey(k) {
    return encodeURIComponent(String(k || '')).replace(/\./g, '%2E');
  }

  function unsafeFirebaseKey(k) {
    try {
      return decodeURIComponent(String(k || ''));
    } catch (e) {
      return String(k || '');
    }
  }

  function serializePointsForFirebase(v) {
    var clean = sanitizePointsChild(v);
    var out = {
      earned: clean.earned,
      spent: clean.spent,
      awarded: {},
      bonusDates: {},
      redemptions: clean.redemptions
    };
    Object.keys(clean.awarded || {}).forEach(function (k) {
      if (clean.awarded[k] === true) {
        out.awarded[safeFirebaseKey(k)] = true;
      }
    });
    Object.keys(clean.bonusDates || {}).forEach(function (k) {
      if (clean.bonusDates[k] === true) {
        out.bonusDates[safeFirebaseKey(k)] = true;
      }
    });
    return out;
  }

  function deserializePointsFromFirebase(v) {
    var clean = sanitizePointsChild(v);
    var out = {
      earned: clean.earned,
      spent: clean.spent,
      awarded: {},
      bonusDates: {},
      redemptions: clean.redemptions
    };
    Object.keys(clean.awarded || {}).forEach(function (k) {
      if (clean.awarded[k] === true) {
        out.awarded[unsafeFirebaseKey(k)] = true;
      }
    });
    Object.keys(clean.bonusDates || {}).forEach(function (k) {
      if (clean.bonusDates[k] === true) {
        out.bonusDates[unsafeFirebaseKey(k)] = true;
      }
    });
    return out;
  }

  function parseTodoRecords(value) {
    var out = {};
    if (!isObject(value)) return out;
    Object.values(value).forEach(function (r) {
      if (!isObject(r) || typeof r.key !== 'string') return;
      if (typeof r.done === 'boolean') out[r.key] = r.done;
    });
    return out;
  }
  function parsePointRecords(value) {
    var out = {};
    if (!isObject(value)) return out;
    Object.values(value).forEach(function (r) {
      if (!isObject(r) || typeof r.key !== 'string') return;
      if (!/^[a-z0-9-]+$/.test(r.key)) return;
      if (isObject(r.data)) out[r.key] = deserializePointsFromFirebase(r.data);
    });
    return out;
  }

  function notify(kind, value) {
    var cb = kind === 'todos' ? state.handlers.onTodosChanged : state.handlers.onPointsChanged;
    if (typeof cb === 'function') { try { cb(value); } catch (e) {} }
  }

  function setLocal(kind, value, notifyChange) {
    var store = kind === 'todos' ? sanitizeTodos(value) : sanitizePoints(value);
    state.local[kind] = store;
    writeJson(kind === 'todos' ? TODO_STORE_KEY : POINTS_STORE_KEY, store);
    if (notifyChange) notify(kind, store);
    return store;
  }

  function writeRemote(kind, key, value) {
    if (!state.roomRef || !state.auth || !state.auth.currentUser) {
      return Promise.reject(new Error('同步尚未連接'));
    }
    var record = {
      key: key,
      updatedAt: window.firebase.database.ServerValue.TIMESTAMP,
      deviceId: state.auth.currentUser.uid
    };
    if (kind === 'todos') record.done = Boolean(value);
    else record.data = serializePointsForFirebase(value);
    var path = kind === 'todos' ? 'todos' : 'points';
    return state.roomRef.child(path).child(encodePath(key)).set(record);
  }

  function sendPending(kind, key, value) {
    return writeRemote(kind, key, value).then(function () {
      if (hasOwn(state.pending[kind], key) && equalValue(kind, state.pending[kind][key], value)) {
        delete state.pending[kind][key];
        writePending();
      }
    }).catch(function () {
      updatePanel('已離線 ⚠️', '網路暫時中斷；本機變更已保留，重新連線後自動補送。', false);
    });
  }

  function queueWrite(kind, key, value) {
    state.pending[kind][key] = value;
    writePending();
    return sendPending(kind, key, value);
  }

  function flushPending() {
    ['todos', 'points'].forEach(function (kind) {
      Object.entries(state.pending[kind]).forEach(function (pair) { sendPending(kind, pair[0], pair[1]); });
    });
  }

  function publishChanges(kind, nextValue) {
    var next = kind === 'todos' ? sanitizeTodos(nextValue) : sanitizePoints(nextValue);
    var prev = state.local[kind] || {};
    state.local[kind] = next;
    if (!state.connected || state.applyingRemote) return;
    var keys = new Set([].concat(Object.keys(prev), Object.keys(next)));
    keys.forEach(function (key) {
      var before = localValue(kind, prev, key);
      var after = localValue(kind, next, key);
      if (!equalValue(kind, before, after)) queueWrite(kind, key, after);
    });
  }

  function applyRemote(kind, incoming) {
    if (!state.connected) return;
    var remote = kind === 'todos' ? sanitizeTodos(incoming) : sanitizePoints(incoming);
    var prevRemote = state.remote[kind] || {};
    var baseline = state.local[kind] || {};
    var localRaw = kind === 'todos' ? readJson(TODO_STORE_KEY) : readJson(POINTS_STORE_KEY);
    var local = kind === 'todos' ? sanitizeTodos(localRaw) : sanitizePoints(localRaw);
    var writes = [];
    var changed = false;
    var keys = new Set([].concat(Object.keys(prevRemote), Object.keys(remote)));
    keys.forEach(function (key) {
      var before = localValue(kind, baseline, key);
      var current = localValue(kind, local, key);
      var incomingValue = localValue(kind, remote, key);
      if (!equalValue(kind, current, before) && !equalValue(kind, incomingValue, before) && !equalValue(kind, current, incomingValue)) {
        writes.push([key, current]);
      }
      if (equalValue(kind, current, incomingValue)) return;
      changed = true;
      if (kind === 'todos') {
        if (incomingValue) local[key] = true; else delete local[key];
      } else {
        if (incomingValue === null || incomingValue === undefined) delete local[key];
        else local[key] = incomingValue;
      }
    });
    Object.entries(state.pending[kind]).forEach(function (pair) {
      var key = pair[0], value = pair[1];
      var current = localValue(kind, local, key);
      if (!equalValue(kind, current, value)) {
        changed = true;
        if (kind === 'todos') { if (value) local[key] = true; else delete local[key]; }
        else local[key] = value;
      }
      writes.push([key, value]);
    });
    state.remote[kind] = remote;
    state.applyingRemote = true;
    setLocal(kind, local, changed);
    state.applyingRemote = false;
    writes.forEach(function (w) { queueWrite(kind, w[0], w[1]); });
  }

  function reconcileInitial(remoteTodos, remotePoints) {
    var localTodos = sanitizeTodos(readJson(TODO_STORE_KEY));
    var localPoints = sanitizePoints(readJson(POINTS_STORE_KEY));
    var nextTodos = clone(localTodos);
    var nextPoints = clone(localPoints);
    var writes = [];
    Object.entries(remoteTodos).forEach(function (pair) {
      if (pair[1]) nextTodos[pair[0]] = true; else delete nextTodos[pair[0]];
    });
    Object.entries(remotePoints).forEach(function (pair) { nextPoints[pair[0]] = pair[1]; });
    Object.entries(state.pending.todos).forEach(function (pair) {
      if (pair[1]) nextTodos[pair[0]] = true; else delete nextTodos[pair[0]];
      writes.push(['todos', pair[0], pair[1]]);
    });
    Object.entries(state.pending.points).forEach(function (pair) {
      nextPoints[pair[0]] = pair[1];
      writes.push(['points', pair[0], pair[1]]);
    });
    Object.entries(localTodos).forEach(function (pair) {
      if (!hasOwn(remoteTodos, pair[0]) && !hasOwn(state.pending.todos, pair[0])) writes.push(['todos', pair[0], pair[1]]);
    });
    Object.entries(localPoints).forEach(function (pair) {
      if (!hasOwn(remotePoints, pair[0]) && !hasOwn(state.pending.points, pair[0])) writes.push(['points', pair[0], pair[1]]);
    });
    state.remote = { todos: sanitizeTodos(remoteTodos), points: sanitizePoints(remotePoints) };
    state.applyingRemote = true;
    setLocal('todos', nextTodos, true);
    setLocal('points', nextPoints, true);
    state.applyingRemote = false;
    writes.forEach(function (w) { queueWrite(w[0], w[1], w[2]); });
  }

  function attachListeners() {
    var todosRef = state.roomRef.child('todos');
    var pointsRef = state.roomRef.child('points');
    var todosHandler = function (snap) { applyRemote('todos', parseTodoRecords(snap.val())); };
    var pointsHandler = function (snap) { applyRemote('points', parsePointRecords(snap.val())); };
    todosRef.on('value', todosHandler);
    pointsRef.on('value', pointsHandler);

    // RTDB real-time connection status listener (.info/connected)
    var connectedRef = state.db.ref('.info/connected');
    var connectedHandler = function (snap) {
      var isOnline = Boolean(snap.val());
      if (isOnline) {
        if (state.disconnectTimer) {
          clearTimeout(state.disconnectTimer);
          state.disconnectTimer = null;
        }
        if (state.connected) {
          updatePanel('已同步 ☁️', '勾選＋積分會即時同步。換裝置輸入同一組碼即可。', true);
          flushPending();
        }
      } else {
        if (state.connected && !state.disconnectTimer) {
          // Debounce temporary handshakes or network drops for 5s before declaring offline
          state.disconnectTimer = setTimeout(function () {
            state.disconnectTimer = null;
            if (state.connected) {
              updatePanel('已離線 ⚠️', '網路暫時中斷；本機變更已保留，重新連線後自動補送。', false);
            }
          }, 5000);
        }
      }
    };
    connectedRef.on('value', connectedHandler);

    state.listeners = [
      [todosRef, 'value', todosHandler],
      [pointsRef, 'value', pointsHandler],
      [connectedRef, 'value', connectedHandler]
    ];
  }

  function stopConnection(showStatus) {
    if (state.disconnectTimer) {
      clearTimeout(state.disconnectTimer);
      state.disconnectTimer = null;
    }
    if (state.retryTimer) {
      clearTimeout(state.retryTimer);
      state.retryTimer = null;
    }
    state.listeners.forEach(function (l) { try { l[0].off(l[1], l[2]); } catch (e) {} });
    state.listeners = [];
    state.roomRef = null;
    state.roomId = '';
    state.connected = false;
    state.remote = { todos: {}, points: {} };
    if (showStatus) updatePanel('本機模式 💻', '目前只保留在這台裝置；離線使用完全正常。', false);
  }

  function loadScript(url) {
    return new Promise(function (resolve, reject) {
      var existing = document.querySelector('script[data-puiching-firebase="' + url + '"]');
      if (existing) {
        if (existing.dataset.loaded === 'true') resolve();
        else {
          existing.addEventListener('load', resolve, { once: true });
          existing.addEventListener('error', reject, { once: true });
        }
        return;
      }
      var s = document.createElement('script');
      s.src = url;
      s.dataset.puichingFirebase = url;
      s.addEventListener('load', function () { s.dataset.loaded = 'true'; resolve(); }, { once: true });
      s.addEventListener('error', reject, { once: true });
      document.head.appendChild(s);
    });
  }

  function ensureFirebase() {
    var base = 'https://www.gstatic.com/firebasejs/' + FIREBASE_VERSION;
    var need = !(window.firebase && window.firebase.initializeApp);
    var p = need
      ? loadScript(base + '/firebase-app-compat.js')
          .then(function () { return loadScript(base + '/firebase-auth-compat.js'); })
          .then(function () { return loadScript(base + '/firebase-database-compat.js'); })
      : Promise.resolve();
    return p.then(function () {
      if (!window.firebase || !window.firebase.auth || !window.firebase.database) {
        throw new Error('雲端同步元件載入失敗');
      }
      var config = getConfig();
      if (!window.firebase.apps.length) window.firebase.initializeApp(config);
      state.auth = window.firebase.auth();
      state.db = window.firebase.database();

      var persistP = Promise.resolve();
      if (state.auth && typeof state.auth.setPersistence === 'function' && window.firebase && window.firebase.auth && window.firebase.auth.Auth) {
        var Auth = window.firebase.auth.Auth;
        persistP = state.auth.setPersistence(Auth.Persistence.LOCAL)
          .catch(function () {
            return state.auth.setPersistence(Auth.Persistence.SESSION);
          })
          .catch(function () {
            return state.auth.setPersistence(Auth.Persistence.NONE);
          })
          .catch(function () {});
      }

      return persistP.then(function () {
        if (!state.auth.currentUser) {
          return state.auth.signInAnonymously().catch(function (authErr) {
            console.warn('[PuichingSync] signInAnonymously warning:', authErr);
            throw authErr;
          });
        }
      });
    });
  }

  function connect(rawCode, silent) {
    var code = normalizeCode(rawCode);
    if (!CODE_PATTERN.test(code)) {
      updatePanel('本機模式 💻', '同步碼格式不正確，請檢查（20 位英數字元）。', false);
      return Promise.resolve(false);
    }
    if (!isConfigured()) {
      updatePanel('本機模式 💻', '請先依 SYNC_SETUP.md 設定 Firebase；目前仍可離線使用。', false);
      return Promise.resolve(false);
    }
    updatePanel('連接中…', '正在安全連接同步空間…', false);
    stopConnection(false);
    return ensureFirebase().then(function () {
      state.code = code;
      return digestCode(code);
    }).then(function (roomId) {
      state.roomId = roomId;
      state.roomRef = state.db.ref('rooms/' + state.roomId);
      return new Promise(function (res) {
        var t = setTimeout(function () {
          res({ val: function () { return {}; } });
        }, 6000);
        state.roomRef.once('value').then(function (s) {
          clearTimeout(t);
          res(s);
        }).catch(function (e) {
          clearTimeout(t);
          console.warn('[PuichingSync] once(value) warning:', e);
          res({ val: function () { return {}; } });
        });
      });
    }).then(function (snap) {
      var root = snap.val() || {};
      reconcileInitial(parseTodoRecords(root.todos), parsePointRecords(root.points));
      state.connected = true;
      attachListeners();
      saveCode(code);
      var input = panelInput();
      if (input) input.value = formatCode(code);
      updatePairingCards(code);
      updatePanel('已同步 ☁️', '勾選＋積分會即時同步。換裝置輸入同一組碼即可。', true);
      return true;
    }).catch(function (err) {
      console.warn('[PuichingSync] 連線失敗:', err);
      stopConnection(false);
      updatePanel('已離線 ⚠️', silent ? '上次同步未能連線；本機資料仍安全保留。' : ((err && err.message) || '連線失敗，目前已進入本機模式。'), false);

      // 行動裝置自動背景重試排程（若瀏覽器連線正常）
      if (typeof navigator !== 'undefined' && navigator.onLine !== false && !state.retryTimer) {
        state.retryTimer = setTimeout(function () {
          state.retryTimer = null;
          var saved = readSavedCode();
          if (saved === code && !state.connected) {
            connect(code, true);
          }
        }, 10000);
      }
      return false;
    });
  }

  function disconnect() {
    stopConnection(true);
    clearSavedCode();
    state.code = '';
    var input = panelInput();
    if (input) input.value = '';
    updatePairingCards('');
  }

  // Pure client-side SVG QR code generator (ISO/IEC 18004 Model 2)
  var internalQr = (function () {
    var EXP = new Uint8Array(512), LOG = new Uint8Array(256), x = 1;
    for (var i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 0x100) x ^= 0x11d; }
    for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255];
    function gm(a, b) { return (a === 0 || b === 0) ? 0 : EXP[LOG[a] + LOG[b]]; }
    var RS = {};
    function getPoly(deg) {
      if (RS[deg]) return RS[deg];
      var p = new Uint8Array([1]);
      for (var k = 0; k < deg; k++) {
        var n = new Uint8Array(p.length + 1), f = EXP[k];
        for (var l = 0; l < p.length; l++) { n[l] ^= gm(p[l], f); n[l + 1] ^= p[l]; }
        p = n;
      }
      return (RS[deg] = p);
    }
    function calcEC(d, ec) {
      var g = getPoly(ec), r = new Uint8Array(ec);
      for (var i = 0; i < d.length; i++) {
        var f = d[i] ^ r[0];
        for (var c = 0; c < ec - 1; c++) r[c] = r[c + 1] ^ gm(g[c], f);
        r[ec - 1] = gm(g[ec - 1], f);
      }
      return r;
    }
    var SPECS = {
      1: { c: 26, ec: 10, g: [[1, 16]] }, 2: { c: 44, ec: 16, g: [[1, 28]] },
      3: { c: 70, ec: 26, g: [[1, 44]] }, 4: { c: 100, ec: 18, g: [[2, 32]] },
      5: { c: 134, ec: 24, g: [[2, 43]] }, 6: { c: 172, ec: 16, g: [[4, 27]] },
      7: { c: 196, ec: 18, g: [[4, 31]] }, 8: { c: 242, ec: 22, g: [[2, 38], [2, 39]] },
      9: { c: 292, ec: 22, g: [[3, 36], [2, 37]] }, 10: { c: 346, ec: 26, g: [[4, 43], [1, 44]] }
    };
    var ALIGN = { 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50] };
    function toUtf8(s) {
      if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(s);
      var u = [];
      for (var i = 0; i < s.length; i++) {
        var c = s.charCodeAt(i);
        if (c < 128) u.push(c);
        else if (c < 2048) u.push(192 | (c >> 6), 128 | (c & 63));
        else u.push(224 | (c >> 12), 128 | ((c >> 6) & 63), 128 | (c & 63));
      }
      return new Uint8Array(u);
    }
    function encode(bytes) {
      var v = 1;
      for (var ver = 1; ver <= 10; ver++) {
        var sp = SPECS[ver], dc = 0;
        for (var gi = 0; gi < sp.g.length; gi++) dc += sp.g[gi][0] * sp.g[gi][1];
        if (4 + (ver <= 9 ? 8 : 16) + (bytes.length * 8) <= dc * 8) { v = ver; break; }
      }
      var spec = SPECS[v], totalCW = 0;
      for (var gj = 0; gj < spec.g.length; gj++) totalCW += spec.g[gj][0] * spec.g[gj][1];
      var bits = [];
      function pb(num, len) { for (var b = len - 1; b >= 0; b--) bits.push((num >>> b) & 1); }
      pb(4, 4); pb(bytes.length, v <= 9 ? 8 : 16);
      for (var bi = 0; bi < bytes.length; bi++) pb(bytes[bi], 8);
      var term = Math.min(4, totalCW * 8 - bits.length);
      for (var t = 0; t < term; t++) bits.push(0);
      while (bits.length % 8 !== 0) bits.push(0);
      var cw = [];
      for (var i = 0; i < bits.length; i += 8) {
        var byte = 0; for (var b = 0; b < 8; b++) byte = (byte << 1) | bits[i + b];
        cw.push(byte);
      }
      var pad = [236, 17], pi = 0;
      while (cw.length < totalCW) { cw.push(pad[pi % 2]); pi++; }
      var blks = [], ecBlks = [], off = 0;
      for (var gk = 0; gk < spec.g.length; gk++) {
        var nb = spec.g[gk][0], sz = spec.g[gk][1];
        for (var bk = 0; bk < nb; bk++) {
          var blk = new Uint8Array(cw.slice(off, off + sz)); off += sz;
          blks.push(blk); ecBlks.push(calcEC(blk, spec.ec));
        }
      }
      var finalCW = [], maxD = 0;
      for (var m = 0; m < blks.length; m++) if (blks[m].length > maxD) maxD = blks[m].length;
      for (var ci = 0; ci < maxD; ci++) {
        for (var bj = 0; bj < blks.length; bj++) if (ci < blks[bj].length) finalCW.push(blks[bj][ci]);
      }
      for (var ei = 0; ei < spec.ec; ei++) {
        for (var eb = 0; eb < ecBlks.length; eb++) finalCW.push(ecBlks[eb][ei]);
      }
      return { v: v, cw: finalCW };
    }
    function makeMatrix(res) {
      var v = res.v, cw = res.cw, sz = (v - 1) * 4 + 21;
      var mat = [], isFn = [];
      for (var r = 0; r < sz; r++) { mat.push(new Uint8Array(sz)); isFn.push(new Uint8Array(sz)); }
      function set(row, col, val) { mat[row][col] = val ? 1 : 0; isFn[row][col] = 1; }
      function finder(fr, fc) {
        for (var r = -1; r <= 7; r++) {
          for (var c = -1; c <= 7; c++) {
            var cr = fr + r, cc = fc + c;
            if (cr < 0 || cr >= sz || cc < 0 || cc >= sz) continue;
            if (r === -1 || r === 7 || c === -1 || c === 7) set(cr, cc, 0);
            else if (r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4)) set(cr, cc, 1);
            else set(cr, cc, 0);
          }
        }
      }
      finder(0, 0); finder(0, sz - 7); finder(sz - 7, 0);
      var coords = ALIGN[v] || [];
      for (var ai = 0; ai < coords.length; ai++) {
        for (var aj = 0; aj < coords.length; aj++) {
          var ar = coords[ai], ac = coords[aj];
          if (isFn[ar][ac]) continue;
          for (var dr = -2; dr <= 2; dr++) {
            for (var dc = -2; dc <= 2; dc++) {
              set(ar + dr, ac + dc, Math.abs(dr) === 2 || Math.abs(dc) === 2 || (dr === 0 && dc === 0) ? 1 : 0);
            }
          }
        }
      }
      for (var t = 8; t < sz - 8; t++) {
        if (!isFn[6][t]) set(6, t, t % 2 === 0 ? 1 : 0);
        if (!isFn[t][6]) set(t, 6, t % 2 === 0 ? 1 : 0);
      }
      set(sz - 8, 8, 1);
      for (var f = 0; f < 9; f++) { isFn[8][f] = 1; isFn[f][8] = 1; }
      for (var f2 = sz - 8; f2 < sz; f2++) { isFn[8][f2] = 1; isFn[f2][8] = 1; }
      var bits = [];
      for (var cwi = 0; cwi < cw.length; cwi++) {
        for (var bit = 7; bit >= 0; bit--) bits.push((cw[cwi] >>> bit) & 1);
      }
      var bIdx = 0, up = true;
      for (var col = sz - 1; col > 0; col -= 2) {
        if (col === 6) col--;
        var rows = [];
        for (var ri = 0; ri < sz; ri++) rows.push(up ? sz - 1 - ri : ri);
        for (var rk = 0; rk < rows.length; rk++) {
          var row = rows[rk];
          for (var c2 = 0; c2 < 2; c2++) {
            var cCur = col - c2;
            if (!isFn[row][cCur]) mat[row][cCur] = bIdx < bits.length ? bits[bIdx++] : 0;
          }
        }
        up = !up;
      }
      var FMT = [0x1472, 0x1167, 0x1E50, 0x1B45, 0x0538, 0x002D, 0x0F1A, 0x0A0F];
      var bestM = 0, bestP = Infinity;
      function maskCond(m, ro, co) {
        if (m === 0) return (ro + co) % 2 === 0;
        if (m === 1) return ro % 2 === 0;
        if (m === 2) return co % 3 === 0;
        if (m === 3) return (ro + co) % 3 === 0;
        if (m === 4) return (Math.floor(ro / 2) + Math.floor(co / 3)) % 2 === 0;
        if (m === 5) return ((ro * co) % 2) + ((ro * co) % 3) === 0;
        if (m === 6) return (((ro * co) % 2) + ((ro * co) % 3)) % 2 === 0;
        return ((ro + co) % 2) + ((ro * co) % 3) === 0;
      }
      for (var mk = 0; mk < 8; mk++) {
        var pen = 0;
        for (var pr = 0; pr < sz; pr++) {
          var count = 1;
          for (var pc = 1; pc < sz; pc++) {
            var v1 = isFn[pr][pc] ? mat[pr][pc] : mat[pr][pc] ^ (maskCond(mk, pr, pc) ? 1 : 0);
            var v0 = isFn[pr][pc - 1] ? mat[pr][pc - 1] : mat[pr][pc - 1] ^ (maskCond(mk, pr, pc - 1) ? 1 : 0);
            if (v1 === v0) count++; else { if (count >= 5) pen += 3 + (count - 5); count = 1; }
          }
          if (count >= 5) pen += 3 + (count - 5);
        }
        if (pen < bestP) { bestP = pen; bestM = mk; }
      }
      for (var fr = 0; fr < sz; fr++) {
        for (var fc = 0; fc < sz; fc++) {
          if (!isFn[fr][fc] && maskCond(bestM, fr, fc)) mat[fr][fc] ^= 1;
        }
      }
      var fmtVal = FMT[bestM];
      var tll = [[8,0],[8,1],[8,2],[8,3],[8,4],[8,5],[8,7],[8,8],[7,8],[5,8],[4,8],[3,8],[2,8],[1,8],[0,8]];
      for (var fIdx = 0; fIdx < 15; fIdx++) {
        var bVal = (fmtVal >>> (14 - fIdx)) & 1;
        mat[tll[fIdx][0]][tll[fIdx][1]] = bVal;
        if (fIdx < 7) mat[sz - 1 - fIdx][8] = bVal;
        else mat[8][sz - 15 + fIdx] = bVal;
      }
      return mat;
    }
    return {
      generateSvg: function (text, opts) {
        opts = opts || {};
        var sz = opts.size || 180, pad = typeof opts.margin === 'number' ? opts.margin : 2;
        var mat = makeMatrix(encode(toUtf8(String(text || ''))));
        var dim = mat.length, total = dim + (pad * 2);
        var p = '';
        for (var r = 0; r < dim; r++) {
          for (var c = 0; c < dim; c++) {
            if (mat[r][c]) p += 'M' + (c + pad) + ' ' + (r + pad) + 'h1v1h-1z ';
          }
        }
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + total + ' ' + total + '" width="' + sz + '" height="' + sz + '" shape-rendering="crispEdges"><rect width="' + total + '" height="' + total + '" fill="#ffffff"/><path d="' + p + '" fill="#000000"/></svg>';
      }
    };
  })();

  if (!window.QRCode) window.QRCode = internalQr;
  if (!window.generateQrSvg) window.generateQrSvg = internalQr.generateSvg;

  /**
   * Generates pure client-side SVG QR Code string without external network.
   */
  function generateQrSvgString(text, options) {
    if (window.QRCode && typeof window.QRCode.generateSvg === 'function') {
      return window.QRCode.generateSvg(text, options);
    }
    if (typeof window.generateQrSvg === 'function') {
      return window.generateQrSvg(text, options);
    }
    return internalQr.generateSvg(text, options);
  }

  /**
   * Computes child pairing URL: ${origin}${pathname}abigail.html?sync=${code}
   */
  function getChildPairingUrl(childPage, code) {
    var base = 'https://samulee003.github.io/puiching-eclass-handoff/';
    try {
      var protocol = window.location.protocol;
      var host = window.location.host;
      var hostname = window.location.hostname;
      // Only use current host if it is a real public remote host (not local / file)
      if (protocol === 'https:' && hostname && hostname !== 'localhost' && hostname !== '127.0.0.1' && !hostname.endsWith('.local')) {
        var origin = window.location.origin || (protocol + '//' + host);
        var pathname = window.location.pathname || '/';
        if (pathname.endsWith('index.html')) {
          pathname = pathname.slice(0, -10);
        }
        if (!pathname.endsWith('/')) {
          pathname += '/';
        }
        base = origin + pathname;
      }
    } catch (e) {}
    return base + childPage + '?sync=' + code;
  }

  /**
   * Updates or hides the Quick-Pairing cards for Abigail & Gloria on the parent page.
   */
  function updatePairingCards(code) {
    var cardsSection = document.getElementById('sync-pairing-section');
    if (!cardsSection) return;
    var norm = normalizeCode(code);
    if (!CODE_PATTERN.test(norm)) {
      cardsSection.style.display = 'none';
      return;
    }
    cardsSection.style.display = 'block';

    var abigailUrl = getChildPairingUrl('abigail.html', norm);
    var gloriaUrl = getChildPairingUrl('gloria.html', norm);

    var urlAbigailEl = document.getElementById('sync-url-abigail');
    var urlGloriaEl = document.getElementById('sync-url-gloria');
    if (urlAbigailEl) urlAbigailEl.textContent = abigailUrl;
    if (urlGloriaEl) urlGloriaEl.textContent = gloriaUrl;

    var qrAbigailEl = document.getElementById('sync-qr-abigail');
    var qrGloriaEl = document.getElementById('sync-qr-gloria');
    if (qrAbigailEl) {
      qrAbigailEl.innerHTML = generateQrSvgString(abigailUrl, { size: 160, margin: 2 });
    }
    if (qrGloriaEl) {
      qrGloriaEl.innerHTML = generateQrSvgString(gloriaUrl, { size: 160, margin: 2 });
    }
  }

  /**
   * Auto-extracts ?sync=... or ?familyCode=... or #sync=... from URL,
   * immediately sanitizes the browser address bar, and returns the normalized code.
   */
  function extractSyncCodeFromUrl() {
    try {
      var search = window.location.search || '';
      var hash = window.location.hash || '';
      var match = search.match(/[?&](?:sync|familyCode|familyId|code)=([A-Za-z0-9-]+)/i) ||
                  hash.match(/[#&](?:sync|familyCode|familyId|code)=([A-Za-z0-9-]+)/i);
      if (!match) return null;
      var raw = match[1];
      var normalized = normalizeCode(raw);
      if (!CODE_PATTERN.test(normalized)) return null;

      // Address bar sanitization: immediately strip sensitive sync code from browser history and URL bar
      if (window.history && window.history.replaceState) {
        var cleanSearch = search.replace(/([?&])(?:sync|familyCode|familyId|code)=[^&]*(&|$)/i, function (m, p1, p2) {
          return p2 ? p1 : '';
        }).replace(/[?&]$/, '');
        var cleanHash = hash.replace(/([#&])(?:sync|familyCode|familyId|code)=[^&]*(&|$)/i, function (m, p1, p2) {
          return p2 ? p1 : '';
        }).replace(/[#&]$/, '');
        var cleanUrl = window.location.pathname + cleanSearch + cleanHash;
        window.history.replaceState(null, document.title, cleanUrl || window.location.pathname);
      }
      return normalized;
    } catch (e) {
      return null;
    }
  }

  function setupPanel() {
    var panel = document.getElementById('sync-panel');
    if (!panel || panel.dataset.ready === 'true') return;
    panel.dataset.ready = 'true';
    var isParent = panel.dataset.syncRole === 'parent';
    var role = isParent ? '家長在這台產生同步碼，再配對至小孩平板' : '向家長取得同步碼，輸入後連接';

    var parentPairingHtml = '';
    if (isParent) {
      parentPairingHtml =
        '<div class="sync-pairing-section" id="sync-pairing-section" style="display:none; margin-top: 14px; border-top: 1px dashed var(--border, #334155); padding-top: 12px;">' +
        '  <div style="font-weight:700; margin-bottom: 8px; color: var(--text, #e2e8f0); font-size: 0.85rem;">📱 小孩平板極簡配對（免手動輸入代碼）</div>' +
        '  <div class="sync-cards-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px;">' +
        '    <div class="sync-card" data-child="abigail" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border, #334155); border-radius: 10px; padding: 10px;">' +
        '      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">' +
        '        <strong>🦊 李悅（Abigail · P3）</strong>' +
        '      </div>' +
        '      <div class="sync-card-actions" style="display:flex; gap:6px; margin-bottom:8px;">' +
        '        <button type="button" data-action="toggle-qr" data-target="abigail" style="cursor:pointer;">隱藏 QR Code</button>' +
        '        <button type="button" data-action="copy-url" data-target="abigail" style="cursor:pointer;">複製配對連結</button>' +
        '      </div>' +
        '      <div class="sync-qr-container" id="sync-qr-abigail" style="display:block; text-align:center; padding:10px; background:#fff; border-radius:10px; margin-bottom:8px; box-shadow:0 4px 12px rgba(0,0,0,0.15);"></div>' +
        '      <div class="sync-card-url" id="sync-url-abigail" style="font-size:0.72rem; color:var(--muted, #94a3b8); word-break:break-all;"></div>' +
        '    </div>' +
        '    <div class="sync-card" data-child="gloria" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border, #334155); border-radius: 10px; padding: 10px;">' +
        '      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">' +
        '        <strong>🐰 李昕（Gloria · P1）</strong>' +
        '      </div>' +
        '      <div class="sync-card-actions" style="display:flex; gap:6px; margin-bottom:8px;">' +
        '        <button type="button" data-action="toggle-qr" data-target="gloria" style="cursor:pointer;">隱藏 QR Code</button>' +
        '        <button type="button" data-action="copy-url" data-target="gloria" style="cursor:pointer;">複製配對連結</button>' +
        '      </div>' +
        '      <div class="sync-qr-container" id="sync-qr-gloria" style="display:block; text-align:center; padding:10px; background:#fff; border-radius:10px; margin-bottom:8px; box-shadow:0 4px 12px rgba(0,0,0,0.15);"></div>' +
        '      <div class="sync-card-url" id="sync-url-gloria" style="font-size:0.72rem; color:var(--muted, #94a3b8); word-break:break-all;"></div>' +
        '    </div>' +
        '  </div>' +
        '</div>';
    }

    panel.innerHTML =
      '<div class="sync-header"><strong>☁️ 跨裝置同步</strong><span class="sync-state local" data-sync-state>本機模式 💻</span></div>' +
      '<div class="sync-copy">' + role + '。只同步勾選＋積分，不含 eClass 密碼。</div>' +
      '<div class="sync-controls">' +
      '<label for="sync-code">家庭同步碼</label>' +
      '<input id="sync-code" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="24" placeholder="XXXX-XXXX-XXXX-XXXX-XXXX" />' +
      '<button type="button" data-sync-action="generate">產生同步碼</button>' +
      '<button type="button" data-sync-action="connect">連接雲端</button>' +
      '<button type="button" data-sync-action="copy">複製同步碼</button>' +
      '<button type="button" data-sync-action="disconnect">停止同步</button>' +
      '</div>' +
      '<div class="sync-message" data-sync-message>目前只保留在這台裝置；離線使用完全正常。</div>' +
      parentPairingHtml;

    var input = panel.querySelector('#sync-code');
    var saved = readSavedCode();
    if (CODE_PATTERN.test(saved)) {
      input.value = formatCode(saved);
      if (isParent) updatePairingCards(saved);
    }

    panel.querySelector('[data-sync-action="generate"]').addEventListener('click', function () {
      var code = generateCode();
      input.value = formatCode(code);
      if (isParent) updatePairingCards(code);
      connect(code, false);
    });

    panel.querySelector('[data-sync-action="connect"]').addEventListener('click', function () {
      var code = normalizeCode(input.value);
      if (isParent) updatePairingCards(code);
      connect(code, false);
    });

    panel.querySelector('[data-sync-action="copy"]').addEventListener('click', function () {
      var code = normalizeCode(input.value);
      if (!CODE_PATTERN.test(code)) {
        updatePanel('本機模式 💻', '先產生或輸入同步碼。', false);
        return;
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(formatCode(code)).then(function () {
          updatePanel(state.connected ? '已同步 ☁️' : '本機模式 💻', '同步碼已複製，請交給另一台裝置。', state.connected);
        }).catch(function () { input.focus(); input.select(); });
      } else { input.focus(); input.select(); }
    });

    panel.querySelector('[data-sync-action="disconnect"]').addEventListener('click', disconnect);

    input.addEventListener('input', function () {
      input.value = input.value.toUpperCase().replace(/[^A-Z2-9-]/g, '');
      var norm = normalizeCode(input.value);
      if (isParent && CODE_PATTERN.test(norm)) {
        updatePairingCards(norm);
      }
    });

    if (isParent) {
      // Toggle QR code display
      panel.querySelectorAll('[data-action="toggle-qr"]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var target = btn.getAttribute('data-target');
          var qrBox = document.getElementById('sync-qr-' + target);
          if (!qrBox) return;
          var isHidden = qrBox.style.display === 'none';
          if (isHidden) {
            var childPage = (target === 'gloria') ? 'gloria.html' : 'abigail.html';
            var code = normalizeCode(panelInput() ? panelInput().value : readSavedCode());
            var url = getChildPairingUrl(childPage, code);
            qrBox.innerHTML = generateQrSvgString(url, { size: 180, margin: 2 });
            qrBox.style.display = 'block';
            btn.textContent = '隱藏 QR Code';
            try { qrBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (e) {}
          } else {
            qrBox.style.display = 'none';
            btn.textContent = '顯示 QR Code';
          }
        });
      });

      // Copy pairing URL
      panel.querySelectorAll('[data-action="copy-url"]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var target = btn.getAttribute('data-target');
          var urlEl = document.getElementById('sync-url-' + target);
          var childPage = (target === 'gloria') ? 'gloria.html' : 'abigail.html';
          var code = normalizeCode(panelInput() ? panelInput().value : readSavedCode());
          var url = (urlEl && urlEl.textContent.trim()) ? urlEl.textContent.trim() : getChildPairingUrl(childPage, code);
          if (!url) return;
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url).then(function () {
              var origText = btn.textContent;
              btn.textContent = '已複製連結！✓';
              setTimeout(function () { btn.textContent = origText; }, 2000);
            }).catch(function () { prompt('請手動複製配對連結：', url); });
          } else {
            prompt('請手動複製配對連結：', url);
          }
        });
      });
    }

    if (!isConfigured()) {
      updatePanel('本機模式 💻', '要跨裝置同步，請先設定 Firebase。目前已啟用本機模式。', false);
    }
  }

  function register(handlers) {
    state.handlers = handlers || {};
    state.local.todos = sanitizeTodos(readJson(TODO_STORE_KEY));
    state.local.points = sanitizePoints(readJson(POINTS_STORE_KEY));
    state.pending = readPending();
    setupPanel();

    // Check for auto-pairing query parameter or hash on child tablets
    var urlCode = extractSyncCodeFromUrl();
    if (urlCode && CODE_PATTERN.test(urlCode)) {
      saveCode(urlCode);
      var input = panelInput();
      if (input) input.value = formatCode(urlCode);
      updatePanel('連接中…', '已自動載入家庭同步碼，正在連線… ☁️', false);
      window.setTimeout(function () {
        connect(urlCode, false).then(function (ok) {
          if (ok) {
            var toast = document.getElementById('toast');
            if (toast) {
              toast.textContent = '已自動連線家庭同步空間！☁️';
              toast.classList.add('show');
              setTimeout(function () { toast.classList.remove('show'); }, 3000);
            }
          }
        });
      }, 0);
      return;
    }

    var saved = readSavedCode();
    if (isConfigured() && CODE_PATTERN.test(saved)) {
      window.setTimeout(function () { connect(saved, true); }, 0);
    } else if (!isConfigured()) {
      updatePanel('本機模式 💻', '要跨裝置同步，請先設定 Firebase。目前已啟用本機模式。', false);
    }
  }

  window.addEventListener('online', function () {
    if (state.connected) {
      updatePanel('已同步 ☁️', '勾選＋積分會即時同步。換裝置輸入同一組碼即可。', true);
      flushPending();
      return;
    }
    var saved = readSavedCode();
    if (isConfigured() && CODE_PATTERN.test(saved)) connect(saved, true);
  });

  window.addEventListener('offline', function () {
    if (state.connected) {
      updatePanel('已離線 ⚠️', '網路暫時中斷；本機變更已保留，重新連線後自動補送。', false);
    }
  });

  function handleResume() {
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      var saved = readSavedCode();
      if (saved && CODE_PATTERN.test(saved)) {
        if (state.db && typeof state.db.goOnline === 'function') {
          try { state.db.goOnline(); } catch (e) {}
        }
        if (!state.connected || !state.roomRef) {
          connect(saved, true);
        } else {
          flushPending();
        }
      }
    }
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', handleResume);
    document.addEventListener('click', function (e) {
      var target = e.target;
      if (!target) return;
      var badge = target.closest('[data-sync-state-badge], [data-sync-state]');
      if (badge && (badge.classList.contains('offline') || (badge.textContent && badge.textContent.indexOf('已離線') !== -1))) {
        var saved = readSavedCode();
        if (saved && CODE_PATTERN.test(saved)) {
          updatePanel('連接中…', '正在嘗試重新連線… ☁️', false);
          connect(saved, false);
        }
      }
    });
  }
  if (typeof window !== 'undefined') {
    window.addEventListener('pageshow', handleResume);
  }

  function getOrCreateCode() {
    var saved = readSavedCode();
    if (CODE_PATTERN.test(saved)) {
      return saved;
    }
    var code = generateCode();
    saveCode(code);
    var input = panelInput();
    if (input) input.value = formatCode(code);
    connect(code, false);
    return code;
  }

  window.PuichingSync = {
    register: register,
    replaceTodos: function (v) { publishChanges('todos', v); },
    replacePoints: function (v) { publishChanges('points', v); },
    connect: connect,
    disconnect: disconnect,
    isConfigured: isConfigured,
    generateQrSvg: generateQrSvgString,
    getChildPairingUrl: getChildPairingUrl,
    extractSyncCodeFromUrl: extractSyncCodeFromUrl,
    updatePairingCards: updatePairingCards,
    flushPending: flushPending,
    getOrCreateCode: getOrCreateCode
  };
})();
