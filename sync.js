(function () {
  'use strict';

  const TODO_STORE_KEY = 'puiching-eclass-todos-v1';
  const PROJECT_STORE_KEY = 'puiching-eclass-project-v1';
  const SYNC_CODE_KEY = 'puiching-eclass-sync-code-v1';
  const PENDING_STORE_KEY = 'puiching-eclass-sync-pending-v1';
  const CODE_LENGTH = 20;
  const CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
  const CODE_PATTERN = /^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{20}$/;
  const FIREBASE_VERSION = '10.14.1';
  const state = {
    handlers: {},
    local: { todos: Object.create(null), project: Object.create(null) },
    remote: { todos: Object.create(null), project: Object.create(null) },
    pending: { todos: Object.create(null), project: Object.create(null) },
    listeners: [],
    connected: false,
    applyingRemote: false,
    code: '',
    roomId: '',
    roomRef: null,
    auth: null,
    db: null
  };

  function hasOwn(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
  }

  function isObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value);
  }

  function readJson(key) {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || '{}');
      return isObject(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }

  function writeJson(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {}
  }

  function cloneStore(value) {
    return Object.assign(Object.create(null), isObject(value) ? value : {});
  }

  function sanitizeTodos(value) {
    const result = Object.create(null);
    if (!isObject(value)) return result;
    for (const key of Object.keys(value)) {
      if (value[key] === true) result[key] = true;
    }
    return result;
  }

  function sanitizeProject(value) {
    const result = Object.create(null);
    if (!isObject(value)) return result;
    for (const key of Object.keys(value)) {
      if (value[key] === 'doing' || value[key] === 'done') result[key] = value[key];
    }
    return result;
  }

  function sanitizePending(kind, value) {
    const result = Object.create(null);
    if (!isObject(value)) return result;
    for (const key of Object.keys(value)) {
      if (kind === 'todos' && typeof value[key] === 'boolean') result[key] = value[key];
      if (kind === 'project' &&
          (value[key] === 'todo' || value[key] === 'doing' || value[key] === 'done')) {
        result[key] = value[key];
      }
    }
    return result;
  }

  function readPending() {
    const value = readJson(PENDING_STORE_KEY);
    return {
      todos: sanitizePending('todos', value.todos),
      project: sanitizePending('project', value.project)
    };
  }

  function writePending() {
    writeJson(PENDING_STORE_KEY, state.pending);
  }

  function getConfig() {
    return window.PUICHING_SYNC_CONFIG || {};
  }

  function isConfigured() {
    const config = getConfig();
    return config.enabled !== false &&
      ['apiKey', 'authDomain', 'databaseURL', 'projectId', 'appId'].every(key => Boolean(config[key]));
  }

  function normalizeCode(value) {
    return String(value || '').toUpperCase().replace(/[\s-]/g, '');
  }

  function formatCode(value) {
    const code = normalizeCode(value);
    return code.match(/.{1,4}/g)?.join('-') || code;
  }

  function readSavedCode() {
    try { return normalizeCode(localStorage.getItem(SYNC_CODE_KEY) || ''); } catch { return ''; }
  }

  function saveCode(code) {
    try { localStorage.setItem(SYNC_CODE_KEY, code); } catch {}
  }

  function clearSavedCode() {
    try { localStorage.removeItem(SYNC_CODE_KEY); } catch {}
  }

  function updatePanel(label, message, connected) {
    const panel = document.getElementById('sync-panel');
    if (!panel) return;
    const stateLabel = panel.querySelector('[data-sync-state]');
    const messageLabel = panel.querySelector('[data-sync-message]');
    if (stateLabel) {
      stateLabel.textContent = label;
      stateLabel.classList.toggle('connected', Boolean(connected));
    }
    if (messageLabel) messageLabel.textContent = message;
  }

  function panelInput() {
    return document.querySelector('#sync-code');
  }

  function generateCode() {
    const values = new Uint32Array(CODE_LENGTH);
    if (window.crypto?.getRandomValues) {
      window.crypto.getRandomValues(values);
      return Array.from(values, value => CODE_ALPHABET[value % CODE_ALPHABET.length]).join('');
    }
    return Array.from({ length: CODE_LENGTH }, () =>
      CODE_ALPHABET[Math.floor(Math.random() * CODE_ALPHABET.length)]).join('');
  }

  async function digestCode(code) {
    if (!window.crypto?.subtle || !window.TextEncoder) {
      throw new Error('此瀏覽器不支援安全同步碼');
    }
    const bytes = new TextEncoder().encode('puiching-eclass-room-v1:' + code);
    const digest = await window.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
  }

  function encodePath(value) {
    const bytes = new TextEncoder().encode(value);
    let binary = '';
    for (const byte of bytes) binary += String.fromCharCode(byte);
    return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function equalValue(kind, a, b) {
    if (kind === 'todos') return Boolean(a) === Boolean(b);
    return (a || 'todo') === (b || 'todo');
  }

  function defaultValue(kind) {
    return kind === 'todos' ? false : 'todo';
  }

  function localValue(kind, store, key) {
    return hasOwn(store, key) ? store[key] : defaultValue(kind);
  }

  function parseRecords(value, kind) {
    const records = Object.create(null);
    if (!isObject(value)) return records;
    for (const record of Object.values(value)) {
      if (!isObject(record) || typeof record.key !== 'string') continue;
      if (kind === 'todos' && typeof record.done === 'boolean') {
        records[record.key] = record.done;
      }
      if (kind === 'project' &&
          (record.status === 'todo' || record.status === 'doing' || record.status === 'done')) {
        records[record.key] = record.status;
      }
    }
    return records;
  }

  function notify(kind, value) {
    const callback = kind === 'todos'
      ? state.handlers.onTodosChanged
      : state.handlers.onProjectChanged;
    if (typeof callback === 'function') {
      try { callback(value); } catch {}
    }
  }

  function setLocal(kind, value, notifyChange) {
    const store = kind === 'todos' ? sanitizeTodos(value) : sanitizeProject(value);
    state.local[kind] = store;
    writeJson(kind === 'todos' ? TODO_STORE_KEY : PROJECT_STORE_KEY, store);
    if (notifyChange) notify(kind, store);
    return store;
  }

  function writeRemote(kind, key, value) {
    if (!state.roomRef || !state.auth?.currentUser) {
      return Promise.reject(new Error('同步尚未連接'));
    }
    const record = {
      key,
      updatedAt: window.firebase.database.ServerValue.TIMESTAMP,
      deviceId: state.auth.currentUser.uid
    };
    if (kind === 'todos') record.done = Boolean(value);
    else record.status = value || 'todo';
    return state.roomRef.child(kind).child(encodePath(key)).set(record);
  }

  function sendPending(kind, key, value) {
    return writeRemote(kind, key, value).then(() => {
      if (hasOwn(state.pending[kind], key) &&
          equalValue(kind, state.pending[kind][key], value)) {
        delete state.pending[kind][key];
        writePending();
      }
    }).catch(() => {
      updatePanel('已離線', '本機變更已保留；重新連線後會再嘗試同步。', false);
    });
  }

  function queueWrite(kind, key, value) {
    state.pending[kind][key] = value;
    writePending();
    return sendPending(kind, key, value);
  }

  function flushPending() {
    for (const kind of ['todos', 'project']) {
      for (const [key, value] of Object.entries(state.pending[kind])) {
        sendPending(kind, key, value);
      }
    }
  }

  function publishChanges(kind, nextValue) {
    const next = kind === 'todos' ? sanitizeTodos(nextValue) : sanitizeProject(nextValue);
    const previous = state.local[kind] || Object.create(null);
    state.local[kind] = next;
    if (!state.connected || state.applyingRemote) return;

    const keys = new Set([...Object.keys(previous), ...Object.keys(next)]);
    for (const key of keys) {
      const before = localValue(kind, previous, key);
      const after = localValue(kind, next, key);
      if (!equalValue(kind, before, after)) {
        queueWrite(kind, key, after);
      }
    }
  }

  function applyRemote(kind, incoming) {
    if (!state.connected) return;
    const remote = kind === 'todos' ? sanitizeTodos(incoming) : sanitizeProject(incoming);
    const previousRemote = state.remote[kind] || Object.create(null);
    const baseline = state.local[kind] || Object.create(null);
    const local = kind === 'todos'
      ? sanitizeTodos(readJson(TODO_STORE_KEY))
      : sanitizeProject(readJson(PROJECT_STORE_KEY));
    const writes = [];
    let changed = false;
    const keys = new Set([...Object.keys(previousRemote), ...Object.keys(remote)]);

    for (const key of keys) {
      const before = localValue(kind, baseline, key);
      const current = localValue(kind, local, key);
      const incomingValue = localValue(kind, remote, key);
      if (!equalValue(kind, current, before) && !equalValue(kind, incomingValue, before)) {
        writes.push([key, current]);
        continue;
      }
      if (equalValue(kind, current, incomingValue)) continue;
      changed = true;
      if (kind === 'todos') {
        if (incomingValue) local[key] = true;
        else delete local[key];
      } else if (incomingValue === 'todo') {
        delete local[key];
      } else {
        local[key] = incomingValue;
      }
    }

    for (const [key, value] of Object.entries(state.pending[kind])) {
      const current = localValue(kind, local, key);
      if (!equalValue(kind, current, value)) {
        changed = true;
        if (kind === 'todos') {
          if (value) local[key] = true;
          else delete local[key];
        } else if (value === 'todo') {
          delete local[key];
        } else {
          local[key] = value;
        }
      }
      writes.push([key, value]);
    }

    state.remote[kind] = remote;
    state.applyingRemote = true;
    setLocal(kind, local, changed);
    state.applyingRemote = false;
    for (const [key, value] of writes) queueWrite(kind, key, value);
  }

  function reconcileInitial(remoteTodos, remoteProject) {
    const localTodos = sanitizeTodos(readJson(TODO_STORE_KEY));
    const localProject = sanitizeProject(readJson(PROJECT_STORE_KEY));
    const nextTodos = cloneStore(localTodos);
    const nextProject = cloneStore(localProject);
    const writes = [];

    for (const [key, value] of Object.entries(remoteTodos)) {
      if (value) nextTodos[key] = true;
      else delete nextTodos[key];
    }
    for (const [key, value] of Object.entries(remoteProject)) {
      if (value === 'todo') delete nextProject[key];
      else nextProject[key] = value;
    }
    for (const [key, value] of Object.entries(state.pending.todos)) {
      if (value) nextTodos[key] = true;
      else delete nextTodos[key];
      writes.push(['todos', key, value]);
    }
    for (const [key, value] of Object.entries(state.pending.project)) {
      if (value === 'todo') delete nextProject[key];
      else nextProject[key] = value;
      writes.push(['project', key, value]);
    }
    for (const [key, value] of Object.entries(localTodos)) {
      if (!hasOwn(remoteTodos, key) && !hasOwn(state.pending.todos, key)) {
        writes.push(['todos', key, value]);
      }
    }
    for (const [key, value] of Object.entries(localProject)) {
      if (!hasOwn(remoteProject, key) && !hasOwn(state.pending.project, key)) {
        writes.push(['project', key, value]);
      }
    }

    state.remote = {
      todos: sanitizeTodos(remoteTodos),
      project: sanitizeProject(remoteProject)
    };
    state.applyingRemote = true;
    setLocal('todos', nextTodos, true);
    setLocal('project', nextProject, true);
    state.applyingRemote = false;
    for (const [kind, key, value] of writes) queueWrite(kind, key, value);
  }

  function attachListeners() {
    const todosRef = state.roomRef.child('todos');
    const projectRef = state.roomRef.child('project');
    const todosHandler = snapshot => applyRemote('todos', parseRecords(snapshot.val(), 'todos'));
    const projectHandler = snapshot => applyRemote('project', parseRecords(snapshot.val(), 'project'));
    todosRef.on('value', todosHandler);
    projectRef.on('value', projectHandler);
    state.listeners = [
      [todosRef, 'value', todosHandler],
      [projectRef, 'value', projectHandler]
    ];
  }

  function stopConnection(showStatus) {
    for (const [ref, event, handler] of state.listeners) ref.off(event, handler);
    state.listeners = [];
    state.roomRef = null;
    state.roomId = '';
    state.connected = false;
    state.remote = { todos: Object.create(null), project: Object.create(null) };
    if (showStatus) updatePanel('本機模式', '目前只保留在這台裝置。', false);
  }

  function loadScript(url) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-puiching-firebase="${url}"]`);
      if (existing) {
        if (existing.dataset.loaded === 'true') resolve();
        else {
          existing.addEventListener('load', resolve, { once: true });
          existing.addEventListener('error', reject, { once: true });
        }
        return;
      }
      const script = document.createElement('script');
      script.src = url;
      script.dataset.puichingFirebase = url;
      script.addEventListener('load', () => {
        script.dataset.loaded = 'true';
        resolve();
      }, { once: true });
      script.addEventListener('error', reject, { once: true });
      document.head.appendChild(script);
    });
  }

  async function ensureFirebase() {
    const base = `https://www.gstatic.com/firebasejs/${FIREBASE_VERSION}`;
    if (!window.firebase?.initializeApp) {
      await loadScript(`${base}/firebase-app-compat.js`);
      await loadScript(`${base}/firebase-auth-compat.js`);
      await loadScript(`${base}/firebase-database-compat.js`);
    }
    if (!window.firebase?.auth || !window.firebase?.database) {
      throw new Error('雲端同步元件載入失敗');
    }
    const config = getConfig();
    if (!window.firebase.apps.length) window.firebase.initializeApp(config);
    state.auth = window.firebase.auth();
    state.db = window.firebase.database();
    if (!state.auth.currentUser) await state.auth.signInAnonymously();
  }

  async function connect(rawCode, silent) {
    const code = normalizeCode(rawCode);
    if (!CODE_PATTERN.test(code)) {
      updatePanel('需要同步碼', '同步碼是 20 個英數字元，請檢查輸入。', false);
      return false;
    }
    if (!isConfigured()) {
      updatePanel('尚未設定雲端', '請先依 SYNC_SETUP.md 設定 Firebase；目前仍可離線使用。', false);
      return false;
    }
    updatePanel('連接中…', '正在安全連接同步空間。', false);
    stopConnection(false);
    try {
      await ensureFirebase();
      state.code = code;
      state.roomId = await digestCode(code);
      state.roomRef = state.db.ref(`rooms/${state.roomId}`);
      const snapshot = await state.roomRef.once('value');
      const root = snapshot.val() || {};
      reconcileInitial(parseRecords(root.todos, 'todos'), parseRecords(root.project, 'project'));
      state.connected = true;
      attachListeners();
      saveCode(code);
      const input = panelInput();
      if (input) input.value = formatCode(code);
      updatePanel('已同步 ☁️', '筆電與平板使用同一組同步碼，就會看到最新進度。', true);
      return true;
    } catch (error) {
      stopConnection(false);
      updatePanel('連接失敗', silent ? '上次同步未能連線；本機資料仍安全保留。' : (error.message || '請檢查設定與網路。'), false);
      return false;
    }
  }

  function disconnect() {
    stopConnection(true);
    clearSavedCode();
    state.code = '';
    const input = panelInput();
    if (input) input.value = '';
  }

  function setupPanel() {
    const panel = document.getElementById('sync-panel');
    if (!panel || panel.dataset.ready === 'true') return;
    panel.dataset.ready = 'true';
    const role = panel.dataset.syncRole === 'parent' ? '筆電先產生同步碼，再把碼給平板' : '請向家長取得同步碼，輸入後連接';
    panel.innerHTML = `
      <div class="sync-header">
        <strong>☁️ 跨裝置同步</strong>
        <span class="sync-state" data-sync-state>本機模式</span>
      </div>
      <div class="sync-copy">${role}</div>
      <div class="sync-controls">
        <label for="sync-code">家庭同步碼</label>
        <input id="sync-code" type="text" inputmode="text" autocomplete="off"
          autocapitalize="characters" spellcheck="false" maxlength="24" placeholder="XXXX-XXXX-XXXX-XXXX-XXXX" />
        <button type="button" data-sync-action="generate">產生同步碼</button>
        <button type="button" data-sync-action="connect">連接雲端</button>
        <button type="button" data-sync-action="copy">複製同步碼</button>
        <button type="button" data-sync-action="disconnect">停止同步</button>
      </div>
      <div class="sync-message" data-sync-message>尚未設定雲端時，仍會照常使用本機模式。</div>`;

    const input = panel.querySelector('#sync-code');
    const saved = readSavedCode();
    if (CODE_PATTERN.test(saved)) input.value = formatCode(saved);
    panel.querySelector('[data-sync-action="generate"]').addEventListener('click', () => {
      const code = generateCode();
      input.value = formatCode(code);
      connect(code, false);
    });
    panel.querySelector('[data-sync-action="connect"]').addEventListener('click', () => {
      connect(input.value, false);
    });
    panel.querySelector('[data-sync-action="copy"]').addEventListener('click', async () => {
      const code = normalizeCode(input.value);
      if (!CODE_PATTERN.test(code)) {
        updatePanel('需要同步碼', '先產生或輸入同步碼。', false);
        return;
      }
      try {
        await navigator.clipboard.writeText(formatCode(code));
        updatePanel(state.connected ? '已同步 ☁️' : '同步碼已複製', '請把同步碼交給另一台裝置。', state.connected);
      } catch {
        input.focus();
        input.select();
        updatePanel('同步碼已選取', '請手動複製後貼到另一台裝置。', state.connected);
      }
    });
    panel.querySelector('[data-sync-action="disconnect"]').addEventListener('click', disconnect);
    input.addEventListener('input', () => {
      input.value = input.value.toUpperCase().replace(/[^A-Z2-9-]/g, '');
    });
    if (!isConfigured()) {
      updatePanel('本機模式', '要跨裝置同步，請依 SYNC_SETUP.md 設定 Firebase。', false);
    }
  }

  function register(handlers) {
    state.handlers = handlers || {};
    state.local.todos = sanitizeTodos(readJson(TODO_STORE_KEY));
    state.local.project = sanitizeProject(readJson(PROJECT_STORE_KEY));
    state.pending = readPending();
    setupPanel();
    const saved = readSavedCode();
    if (isConfigured() && CODE_PATTERN.test(saved)) {
      window.setTimeout(() => connect(saved, true), 0);
    }
  }

  window.addEventListener('online', () => {
    if (state.connected) {
      flushPending();
      return;
    }
    const saved = readSavedCode();
    if (isConfigured() && CODE_PATTERN.test(saved)) connect(saved, true);
  });

  window.PuichingSync = {
    register,
    replaceTodos: value => publishChanges('todos', value),
    replaceProject: value => publishChanges('project', value),
    connect,
    disconnect,
    isConfigured
  };
})();
