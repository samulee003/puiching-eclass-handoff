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
    db: null
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
  function writePending() { writeJson(PENDING_STORE_KEY, state.pending); }

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

  function updatePanel(label, message, connected) {
    var panel = document.getElementById('sync-panel');
    if (!panel) return;
    var s = panel.querySelector('[data-sync-state]');
    var m = panel.querySelector('[data-sync-message]');
    if (s) { s.textContent = label; s.classList.toggle('connected', Boolean(connected)); }
    if (m) m.textContent = message;
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

  function digestCode(code) {
    if (!window.crypto || !window.crypto.subtle || !window.TextEncoder) {
      return Promise.reject(new Error('此瀏覽器不支援安全同步碼'));
    }
    var bytes = new TextEncoder().encode('puiching-eclass-room-v1:' + code);
    return window.crypto.subtle.digest('SHA-256', bytes).then(function (d) {
      return Array.from(new Uint8Array(d), function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    });
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
      if (isObject(r.data)) out[r.key] = sanitizePointsChild(r.data);
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
    else record.data = sanitizePointsChild(value);
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
      updatePanel('已離線', '本機變更已保留；重新連線後會再嘗試同步。', false);
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
      // Both sides changed since baseline and disagree: remote wins (last snapshot), local change already in pending if important.
      if (!equalValue(kind, current, before) && !equalValue(kind, incomingValue, before) && !equalValue(kind, current, incomingValue)) {
        writes.push([key, current]);
      }
      if (equalValue(kind, current, incomingValue)) return;
      // Local has unsent change that matches pending: keep local, re-push.
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
    state.listeners = [[todosRef, 'value', todosHandler], [pointsRef, 'value', pointsHandler]];
  }

  function stopConnection(showStatus) {
    state.listeners.forEach(function (l) { try { l[0].off(l[1], l[2]); } catch (e) {} });
    state.listeners = [];
    state.roomRef = null;
    state.roomId = '';
    state.connected = false;
    state.remote = { todos: {}, points: {} };
    if (showStatus) updatePanel('本機模式', '目前只保留在這台裝置。', false);
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
      if (!state.auth.currentUser) return state.auth.signInAnonymously();
    });
  }

  function connect(rawCode, silent) {
    var code = normalizeCode(rawCode);
    if (!CODE_PATTERN.test(code)) {
      updatePanel('需要同步碼', '同步碼是 20 個英數字元，請檢查輸入。', false);
      return Promise.resolve(false);
    }
    if (!isConfigured()) {
      updatePanel('尚未設定雲端', '請先依 SYNC_SETUP.md 設定 Firebase；目前仍可離線使用。', false);
      return Promise.resolve(false);
    }
    updatePanel('連接中…', '正在安全連接同步空間。', false);
    stopConnection(false);
    return ensureFirebase().then(function () {
      state.code = code;
      return digestCode(code);
    }).then(function (roomId) {
      state.roomId = roomId;
      state.roomRef = state.db.ref('rooms/' + state.roomId);
      return state.roomRef.once('value');
    }).then(function (snap) {
      var root = snap.val() || {};
      reconcileInitial(parseTodoRecords(root.todos), parsePointRecords(root.points));
      state.connected = true;
      attachListeners();
      saveCode(code);
      var input = panelInput();
      if (input) input.value = formatCode(code);
      updatePanel('已同步 ☁️', '勾選＋積分會即時同步。換裝置輸入同一組碼即可。', true);
      return true;
    }).catch(function (err) {
      stopConnection(false);
      updatePanel('連接失敗', silent ? '上次同步未能連線；本機資料仍安全保留。' : (err && err.message) || '請檢查設定與網路。', false);
      return false;
    });
  }

  function disconnect() {
    stopConnection(true);
    clearSavedCode();
    state.code = '';
    var input = panelInput();
    if (input) input.value = '';
  }

  function setupPanel() {
    var panel = document.getElementById('sync-panel');
    if (!panel || panel.dataset.ready === 'true') return;
    panel.dataset.ready = 'true';
    var isParent = panel.dataset.syncRole === 'parent';
    var role = isParent ? '家長在這台產生同步碼，再輸入到小孩平板' : '向家長取得同步碼，輸入後連接';
    panel.innerHTML =
      '<div class="sync-header"><strong>☁️ 跨裝置同步</strong><span class="sync-state" data-sync-state>本機模式</span></div>' +
      '<div class="sync-copy">' + role + '。只同步勾選＋積分，不含 eClass 密碼。</div>' +
      '<div class="sync-controls">' +
      '<label for="sync-code">家庭同步碼</label>' +
      '<input id="sync-code" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="24" placeholder="XXXX-XXXX-XXXX-XXXX-XXXX" />' +
      '<button type="button" data-sync-action="generate">產生同步碼</button>' +
      '<button type="button" data-sync-action="connect">連接雲端</button>' +
      '<button type="button" data-sync-action="copy">複製同步碼</button>' +
      '<button type="button" data-sync-action="disconnect">停止同步</button>' +
      '</div><div class="sync-message" data-sync-message>尚未設定雲端時，仍會照常使用本機模式。</div>';
    var input = panel.querySelector('#sync-code');
    var saved = readSavedCode();
    if (CODE_PATTERN.test(saved)) input.value = formatCode(saved);
    panel.querySelector('[data-sync-action="generate"]').addEventListener('click', function () {
      var code = generateCode();
      input.value = formatCode(code);
      connect(code, false);
    });
    panel.querySelector('[data-sync-action="connect"]').addEventListener('click', function () { connect(input.value, false); });
    panel.querySelector('[data-sync-action="copy"]').addEventListener('click', function () {
      var code = normalizeCode(input.value);
      if (!CODE_PATTERN.test(code)) { updatePanel('需要同步碼', '先產生或輸入同步碼。', false); return; }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(formatCode(code)).then(function () {
          updatePanel(state.connected ? '已同步 ☁️' : '同步碼已複製', '請把同步碼交給另一台裝置。', state.connected);
        }).catch(function () { input.focus(); input.select(); });
      } else { input.focus(); input.select(); }
    });
    panel.querySelector('[data-sync-action="disconnect"]').addEventListener('click', disconnect);
    input.addEventListener('input', function () {
      input.value = input.value.toUpperCase().replace(/[^A-Z2-9-]/g, '');
    });
    if (!isConfigured()) updatePanel('本機模式', '要跨裝置同步，請依 SYNC_SETUP.md 設定 Firebase。', false);
  }

  function register(handlers) {
    state.handlers = handlers || {};
    state.local.todos = sanitizeTodos(readJson(TODO_STORE_KEY));
    state.local.points = sanitizePoints(readJson(POINTS_STORE_KEY));
    state.pending = readPending();
    setupPanel();
    var saved = readSavedCode();
    if (isConfigured() && CODE_PATTERN.test(saved)) {
      window.setTimeout(function () { connect(saved, true); }, 0);
    } else if (!isConfigured()) {
      updatePanel('本機模式', '要跨裝置同步，請依 SYNC_SETUP.md 設定 Firebase。', false);
    }
  }

  window.addEventListener('online', function () {
    if (state.connected) { flushPending(); return; }
    var saved = readSavedCode();
    if (isConfigured() && CODE_PATTERN.test(saved)) connect(saved, true);
  });

  window.PuichingSync = {
    register: register,
    replaceTodos: function (v) { publishChanges('todos', v); },
    replacePoints: function (v) { publishChanges('points', v); },
    connect: connect,
    disconnect: disconnect,
    isConfigured: isConfigured
  };
})();
