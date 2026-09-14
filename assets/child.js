/* Shared logic for a single child's tablet self-management page.
   Each page sets window.CHILD_ID ('li-yue' | 'li-xin') before loading this file.
   Data source is the same status.json as the parent overview; checkbox state is
   stored per-device in localStorage using the same key/scheme as index.html so a
   child's page and the parent overview stay consistent when opened on one device. */
(function () {
  'use strict';

  var STORE_KEY = 'puiching-eclass-todos-v1';
  var POINTS_KEY = 'puiching-eclass-points-v1';
  var TZ = 'Asia/Macau';
  var CHILD_ID = window.CHILD_ID;

  // Reward config comes from status.json (parent-editable); these are fallbacks.
  var DEFAULT_REWARDS = {
    points_per_task: 10,
    all_done_bonus: 20,
    catalog: [
      { id: 'gummy', name: '小熊軟糖', emoji: '🐻', cost: 50 },
      { id: 'choco', name: '巧克力', emoji: '🍫', cost: 80 }
    ]
  };

  var SUBJECT_EMOJI = {
    '英文': '🔤', '中文': '📖', '常識': '🌍', '數學': '➗',
    '導師': '📢', '通知': '📢', '體育': '⚽', '音樂': '🎵', '視藝': '🎨'
  };

  // section key -> kid-friendly label + emoji
  var SECTIONS = [
    ['due_today', '今天要做', '📌'],
    ['due_soon', '快到期', '⏰'],
    ['tests_this_week', '小測驗', '📝'],
    ['other', '其他', '📚']
  ];

  function loadStore() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || '{}'); }
    catch (e) { return {}; }
  }
  function saveStore(s) { localStorage.setItem(STORE_KEY, JSON.stringify(s)); }

  // Points state is per-child and per-device (localStorage). Points are awarded the
  // first time a task is checked and are NOT removed on uncheck, so children cannot
  // farm points by toggling. `spent` tracks redemptions.
  function loadPoints() {
    try { return JSON.parse(localStorage.getItem(POINTS_KEY) || '{}'); }
    catch (e) { return {}; }
  }
  function savePoints(p) { localStorage.setItem(POINTS_KEY, JSON.stringify(p)); }

  function pointsState() {
    var all = loadPoints();
    var s = all[CHILD_ID] || {};
    return {
      earned: s.earned || 0,
      spent: s.spent || 0,
      awarded: s.awarded || {},
      bonusDates: s.bonusDates || {},
      redemptions: s.redemptions || []
    };
  }
  function writePointsState(s) {
    var all = loadPoints();
    all[CHILD_ID] = s;
    savePoints(all);
  }
  function balanceOf(s) { return Math.max(0, s.earned - s.spent); }

  function rewardsConfig() {
    var r = (DATA && DATA.rewards) || {};
    return {
      perTask: typeof r.points_per_task === 'number' ? r.points_per_task : DEFAULT_REWARDS.points_per_task,
      bonus: typeof r.all_done_bonus === 'number' ? r.all_done_bonus : DEFAULT_REWARDS.all_done_bonus,
      catalog: (r.catalog && r.catalog.length) ? r.catalog : DEFAULT_REWARDS.catalog
    };
  }

  function itemKey(childId, section, it) {
    return [childId, section, it.due || '', it.subject || '', it.title || ''].join('|');
  }

  function todayMacau() {
    return new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(new Date());
  }
  function parseYmd(s) {
    if (!s) return null;
    var p = s.split('-').map(Number);
    if (!p[0] || !p[1] || !p[2]) return null;
    return { y: p[0], m: p[1], d: p[2], iso: s };
  }
  function daysBetween(a, b) {
    if (!a || !b) return null;
    var t0 = Date.UTC(a.y, a.m - 1, a.d);
    var t1 = Date.UTC(b.y, b.m - 1, b.d);
    return Math.round((t1 - t0) / 86400000);
  }

  function subjectEmoji(sub) { return SUBJECT_EMOJI[sub] || '📚'; }

  function shortTitle(it) {
    var t = it.title || '';
    return t.length > 18 ? t.slice(0, 16) + '…' : t;
  }

  function addDays(ymd, n) {
    var dt = new Date(Date.UTC(ymd.y, ymd.m - 1, ymd.d + n));
    var iso = dt.toISOString().slice(0, 10);
    var p = iso.split('-').map(Number);
    return { y: p[0], m: p[1], d: p[2], iso: iso };
  }

  function dueChip(dueIso, today) {
    var due = parseYmd(dueIso);
    if (!due) return { cls: 'due-later', text: '無限期' };
    var diff = daysBetween(today, due);
    if (diff < 0) return { cls: 'overdue', text: '逾期 ' + (-diff) + ' 天' };
    if (diff === 0) return { cls: 'due-today', text: '今天要交' };
    if (diff === 1) return { cls: 'due-soon', text: '明天' };
    if (diff <= 3) return { cls: 'due-soon', text: '還有 ' + diff + ' 天' };
    return { cls: 'due-later', text: (due.m) + '/' + (due.d) + ' 交' };
  }

  function sectionItems(child) {
    return [
      ['due_today', child.due_today || []],
      ['due_soon', child.due_soon || []],
      ['tests_this_week', child.tests_this_week || []],
      ['other', child.other || []]
    ];
  }

  function progressOf(child, store) {
    var total = 0, done = 0;
    sectionItems(child).forEach(function (pair) {
      pair[1].forEach(function (it) {
        total++;
        if (store[itemKey(child.id, pair[0], it)]) done++;
      });
    });
    return { total: total, done: done };
  }

  // "cleared" = all today + soon items checked (tests count when nothing else is due)
  function isCleared(child, store) {
    var must = (child.due_today || []).concat(child.due_soon || []);
    if (!must.length) {
      var tests = child.tests_this_week || [];
      return tests.every(function (it) { return store[itemKey(child.id, 'tests_this_week', it)]; });
    }
    return must.every(function (it) {
      var sec = (child.due_today || []).indexOf(it) >= 0 ? 'due_today' : 'due_soon';
      return store[itemKey(child.id, sec, it)];
    });
  }

  function encourageText(done, total) {
    if (total === 0) return '今天沒有功課，好好休息！😄';
    if (done >= total) return '全部做完了，太棒了！🎉';
    var left = total - done;
    if (done === 0) return '一起開始吧，加油！💪';
    return '做得好！還有 ' + left + ' 樣就完成 👍';
  }

  function toast(msg) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.style.display = 'block';
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.style.display = 'none'; }, 2600);
  }

  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  var DATA = null;

  // A kid-friendly Gantt: each near-term homework item is a bar running up to its
  // due date, with a "today" line, so children can see how much time they have.
  function renderTimeline(child) {
    var tl = document.getElementById('tl');
    if (!tl) return;
    var store = loadStore();
    var today = parseYmd(todayMacau());

    var rows = [];
    sectionItems(child).forEach(function (pair) {
      pair[1].forEach(function (it) {
        var due = parseYmd(it.due);
        if (!due) return;
        var diff = daysBetween(today, due);
        if (diff < -14 || diff > 35) return; // focus on the next few weeks
        rows.push({ it: it, due: due, diff: diff, key: itemKey(child.id, pair[0], it) });
      });
    });
    rows.sort(function (a, b) { return a.due.iso < b.due.iso ? -1 : (a.due.iso > b.due.iso ? 1 : 0); });

    var head = '<h2>🗓️ 時間表 <span class="badge">今天 → 交</span></h2>';
    if (!rows.length) {
      tl.innerHTML = head + '<div class="empty">這陣子沒有要交的功課 🎉</div>';
      return;
    }

    var rangeStart = today, rangeEnd = addDays(today, 7);
    rows.forEach(function (r) {
      if (r.due.iso < rangeStart.iso) rangeStart = r.due;
      if (r.due.iso > rangeEnd.iso) rangeEnd = r.due;
    });
    var span = Math.max(daysBetween(rangeStart, rangeEnd), 7);
    function pct(d) {
      var o = daysBetween(rangeStart, d) / span * 100;
      return Math.max(0, Math.min(100, o));
    }
    var todayPct = pct(today);

    var lanes = '';
    rows.forEach(function (r) {
      var done = !!store[r.key];
      var overdue = r.diff < 0;
      var barStart, barEnd;
      if (overdue) {
        barEnd = r.due;
        barStart = addDays(r.due, -2);
        if (barStart.iso < rangeStart.iso) barStart = rangeStart;
      } else {
        barStart = today;
        barEnd = r.due;
      }
      var left = pct(barStart);
      var width = Math.max(pct(barEnd) - left, 3);
      var cls = done ? 'done' : (overdue ? 'overdue' : (r.diff <= 1 ? 'soon' : ''));
      var chip = dueChip(r.it.due, today);
      lanes +=
        '<div class="tl-lane">' +
          '<div class="tl-lanelabel">' +
            '<span>' + subjectEmoji(r.it.subject) + ' ' + shortTitle(r.it) + '</span>' +
            '<span class="tl-when">' + chip.text + '</span>' +
          '</div>' +
          '<div class="tl-track"><div class="tl-bar ' + cls + '" style="left:' + left + '%;width:' + width + '%"></div></div>' +
        '</div>';
    });

    // Avoid the "今天" label colliding with the start/end date labels.
    var startLabel = rangeStart.iso === today.iso
      ? '' : '<span class="tl-start">' + rangeStart.m + '/' + rangeStart.d + '</span>';
    var endLabel = rangeEnd.iso === today.iso
      ? '' : '<span class="tl-end">' + rangeEnd.m + '/' + rangeEnd.d + '</span>';
    var todayXform = todayPct <= 2 ? 'translateX(0)'
      : (todayPct >= 98 ? 'translateX(-100%)' : 'translateX(-50%)');

    tl.innerHTML = head +
      '<div class="tl-wrap">' +
        '<div class="tl-axis">' +
          startLabel +
          '<span class="tl-today-label" style="left:' + todayPct + '%;transform:' + todayXform + '">今天</span>' +
          endLabel +
        '</div>' +
        '<div class="tl-lanes">' +
          '<div class="tl-today-line" style="left:' + todayPct + '%"></div>' +
          lanes +
        '</div>' +
      '</div>';
  }

  // Award points the first time a task becomes done. Returns points gained (0 if none).
  function awardForTask(child, key) {
    var cfg = rewardsConfig();
    var s = pointsState();
    var gained = 0;
    if (!s.awarded[key]) {
      s.awarded[key] = true;
      s.earned += cfg.perTask;
      gained += cfg.perTask;
    }
    // Daily bonus when everything due today is done (once per Macau day).
    var todayIso = todayMacau();
    if (!s.bonusDates[todayIso]) {
      var store = loadStore();
      var todayItems = child.due_today || [];
      var allTodayDone = todayItems.length > 0 && todayItems.every(function (it) {
        return store[itemKey(child.id, 'due_today', it)];
      });
      if (allTodayDone) {
        s.bonusDates[todayIso] = true;
        s.earned += cfg.bonus;
        gained += cfg.bonus;
      }
    }
    writePointsState(s);
    return gained;
  }

  function renderShop(child) {
    var shop = document.getElementById('shop');
    if (!shop) return;
    var cfg = rewardsConfig();
    var s = pointsState();
    var bal = balanceOf(s);

    var cards = cfg.catalog.map(function (item) {
      var affordable = bal >= item.cost;
      var owned = s.redemptions.filter(function (r) { return r.id === item.id; }).length;
      return '' +
        '<div class="shop-item' + (affordable ? '' : ' locked') + '">' +
          '<div class="shop-emoji">' + (item.emoji || '🎁') + '</div>' +
          '<div class="shop-name">' + item.name + '</div>' +
          '<div class="shop-cost">⭐ ' + item.cost + ' 分' + (owned ? ' · 已換 ' + owned : '') + '</div>' +
          '<button type="button" class="shop-btn" data-reward="' + item.id + '"' +
            (affordable ? '' : ' disabled') + '>' +
            (affordable ? '兌換' : '還差 ' + (item.cost - bal)) +
          '</button>' +
        '</div>';
    }).join('');

    shop.innerHTML =
      '<h2>🎁 獎勵商店 <span class="badge">⭐ ' + bal + ' 分</span></h2>' +
      '<div class="shop-hint">做完功課賺積分，換實體小零食！兌換後把訊息拿給爸媽 😋</div>' +
      '<div class="shop-grid">' + cards + '</div>';

    shop.querySelectorAll('.shop-btn').forEach(function (btn) {
      if (btn.disabled) return;
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        redeem(child, btn.dataset.reward);
      });
    });
  }

  function redeem(child, rewardId) {
    var cfg = rewardsConfig();
    var item = cfg.catalog.filter(function (i) { return i.id === rewardId; })[0];
    if (!item) return;
    var s = pointsState();
    if (balanceOf(s) < item.cost) {
      toast('積分還不夠喔，再加油！💪');
      return;
    }
    s.spent += item.cost;
    s.redemptions.push({ id: item.id, name: item.name, cost: item.cost, at: new Date().toISOString() });
    writePointsState(s);
    var msg = '🎁 ' + child.zh + '想用 ' + item.cost + ' 分換 ' + (item.emoji || '') + item.name +
      '（剩 ' + balanceOf(s) + ' 分）— 請爸媽兌現小零食';
    copy(msg);
    toast('🎉 已換 ' + (item.emoji || '') + item.name + '！訊息已複製，拿給爸媽');
    renderShop(child);
    updatePointsBadge();
  }

  function updatePointsBadge() {
    var el = document.getElementById('points');
    if (el) el.textContent = balanceOf(pointsState());
  }

  function render(child) {
    var store = loadStore();
    var today = parseYmd(todayMacau());
    var root = document.getElementById('sections');
    root.innerHTML = '';

    SECTIONS.forEach(function (secDef) {
      var secKey = secDef[0], label = secDef[1], emoji = secDef[2];
      var items = child[secKey] || [];
      if (!items.length) return;

      var sec = el('div', 'section');
      var h = el('h2', null, emoji + ' ' + label);
      h.appendChild(el('span', 'badge', String(items.length)));
      sec.appendChild(h);

      var ul = el('ul', 'tasks');
      items.forEach(function (it) {
        var key = itemKey(child.id, secKey, it);
        var done = !!store[key];
        var li = el('li', 'task' + (done ? ' done' : ''));
        li.setAttribute('role', 'button');
        li.setAttribute('tabindex', '0');
        li.dataset.key = key;

        var chip = dueChip(it.due, today);
        var submit = it.submit_required === false
          ? '<span class="chip nosubmit">不用交</span>'
          : (it.submit_required ? '<span class="chip submit">要交給老師</span>' : '');
        var detail = it.detail ? '<div class="t-detail">' + it.detail + '</div>' : '';
        var note = it.note ? '<span class="chip due-later">' + it.note + '</span>' : '';
        var progress = it.progress ? '<span class="chip due-later">進度 ' + it.progress + '</span>' : '';

        li.innerHTML =
          '<span class="check" aria-hidden="true">✓</span>' +
          '<div>' +
            '<div class="t-title">' + subjectEmoji(it.subject) + ' ' + (it.title || '') + '</div>' +
            '<div class="t-meta">' +
              '<span class="t-sub">' + (it.subject || '') + '</span>' +
              '<span class="chip ' + chip.cls + '">' + chip.text + '</span>' +
              submit + note + progress +
            '</div>' + detail +
          '</div>';

        function toggle() {
          var s = loadStore();
          var nowDone = !s[key];
          if (nowDone) s[key] = true; else delete s[key];
          saveStore(s);
          li.classList.toggle('done', nowDone);
          if (nowDone) {
            var gained = awardForTask(child, key);
            if (gained > 0) toast('+' + gained + ' ⭐ 積分！');
            updatePointsBadge();
            renderShop(child);
          }
          renderTimeline(child);
          updateProgress(child);
        }
        li.addEventListener('click', toggle);
        li.addEventListener('keydown', function (e) {
          if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggle(); }
        });
        ul.appendChild(li);
      });
      sec.appendChild(ul);
      root.appendChild(sec);
    });

    if (!root.children.length) {
      root.appendChild(el('div', 'empty', '🎈 今天沒有功課項目，好好玩吧！'));
    }
    renderTimeline(child);
    renderShop(child);
    updatePointsBadge();
    updateProgress(child);
  }

  function updateProgress(child) {
    var store = loadStore();
    var p = progressOf(child, store);
    var pct = p.total ? Math.round(p.done * 100 / p.total) : 100;
    document.getElementById('bar-fill').style.width = pct + '%';
    document.getElementById('progress-count').textContent = p.done + ' / ' + p.total + ' 完成';
    document.getElementById('encourage').textContent = encourageText(p.done, p.total);
  }

  function onDoneClick(child) {
    var store = loadStore();
    if (isCleared(child, store)) {
      var text = child.zh + '清了';
      copy(text);
      toast('🎉 太棒了！已複製「' + text + '」，拿給爸媽貼給 Grok');
    } else {
      var open = [];
      (child.due_today || []).forEach(function (it) {
        if (!store[itemKey(child.id, 'due_today', it)]) open.push(it.title);
      });
      (child.due_soon || []).forEach(function (it) {
        if (!store[itemKey(child.id, 'due_soon', it)]) open.push(it.title);
      });
      toast('還差 ' + open.length + ' 樣：' + open.slice(0, 3).join('、') + (open.length > 3 ? '…' : ''));
    }
  }

  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () { fallbackCopy(text); });
    } else { fallbackCopy(text); }
  }
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
  }

  function load() {
    fetch('status.json?ts=' + Date.now())
      .then(function (r) { return r.json(); })
      .then(function (data) {
        DATA = data;
        var child = (data.children || []).filter(function (c) { return c.id === CHILD_ID; })[0];
        if (!child) {
          document.getElementById('sections').innerHTML =
            '<div class="empty">找不到這位小朋友的資料（' + CHILD_ID + '）</div>';
          return;
        }
        document.title = child.zh + '的功課';
        document.getElementById('child-name').textContent = child.zh;
        document.getElementById('child-who').textContent =
          child.en + ' · ' + child.grade;
        document.getElementById('avatar').textContent =
          CHILD_ID === 'li-xin' ? '🐰' : '🦊';
        document.getElementById('updated').textContent =
          '更新：' + (data.updated_at || '—');
        render(child);

        document.getElementById('btn-done').addEventListener('click', function () {
          onDoneClick(child);
        });
      })
      .catch(function (e) {
        document.getElementById('sections').innerHTML =
          '<div class="empty">讀不到功課資料 😢（' + e.message + '）</div>';
      });
  }

  document.addEventListener('DOMContentLoaded', load);
})();
