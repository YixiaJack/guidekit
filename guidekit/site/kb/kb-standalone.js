/* Marin KB on your own machine (kb.html, served by serve.py) or on a static host (GitHub Pages).
   The same pages as the research-kb site's knowledge base: routes #/kb, #/kb/<topic>[/doc|process|cards[/<part>]],
   #/kb/doc/<id>, #/kb/card/<n>, and #/chat (Ask & ideas). An EN / 中文 switch (English by default, kept for the session).
   With serve.py and an AI configured (your Claude or Codex subscription, or an API key), "Ask about this experiment",
   "Compare my idea" and "Brainstorm" work as on the site; on a static host they are hidden. */
(function () {
  'use strict';
  var view = document.getElementById('view');
  var UI = { lang: 'en', ai: null, mode: 'ask', card: null, topic: '', draft: '', threads: null, busy: false, err: '' };
  try { UI.lang = sessionStorage.getItem('siteLang') === 'zh' ? 'zh' : 'en'; } catch (e) { /* default */ }
  function L(en, zh) { return UI.lang === 'zh' ? zh : en; }
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v; else if (k === 'text') el.textContent = v;
      else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v); else el.setAttribute(k, v === true ? '' : v);
    }
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) { if (c == null || c === false) return; if (Array.isArray(c)) { c.forEach(function (x) { add(el, x); }); return; } el.appendChild(typeof c === 'object' ? c : document.createTextNode(String(c))); }
  var M = window.MarinKB;
  function site() { var d = M.data(); return d && d.site; }
  function localGuide() {   // the repository's "run it on your computer" section, in the reader's language
    var st = site();
    if (st && st.repo_readme) return UI.lang === 'zh' ? st.repo_readme.zh : st.repo_readme.en;
    return UI.lang === 'zh' ? 'https://github.com/YixiaJack/marin-kb/blob/main/README.zh.md#在自己电脑上运行5-分钟'
      : 'https://github.com/YixiaJack/marin-kb#run-it-on-your-computer-5-minutes';
  }

  // ---------- AI (serve.py)
  function aiOn() { return !!(UI.ai && UI.ai.ai); }
  var PROVIDER = { 'claude-code': 'Claude (your subscription, via Claude Code)', codex: 'Codex (your ChatGPT subscription)', anthropic: 'Anthropic API', openai: 'OpenAI-compatible API' };
  function status() {
    return fetch('api/status', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })
      .then(function (s) { UI.ai = s; });
  }
  function loadThreads() {
    return fetch('api/threads', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; })
      .then(function (t) { UI.threads = t; });
  }
  function ask(payload) {
    UI.busy = true; UI.err = ''; render();
    payload.lang = UI.lang;
    return fetch('api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      .then(function (r) { return r.json(); })
      .then(function (t) { if (t.status !== 'done') UI.err = t.error || L('The AI did not answer.', 'AI 没有回答。'); UI.draft = ''; return loadThreads(); })
      .catch(function (e) { UI.err = e.message; })
      .then(function () { UI.busy = false; render(); });
  }
  function goAsk(mode, card, topic, text) {
    UI.mode = mode; UI.card = card || null; UI.topic = topic || ''; if (text) UI.draft = text;
    location.hash = '#/chat';
  }
  var hooks = {
    cardActions: function (r) {
      if (!aiOn()) return null;
      return h('div', { class: 'actions' },
        h('button', { class: 'btn sm', text: L('Ask about this experiment', '就这个实验提问'), onclick: function () { goAsk('ask', r.n, r.t); } }),
        h('button', { class: 'btn sm', text: L('Compare my idea with it', '拿我的想法和它比'), onclick: function () { goAsk('idea', r.n, r.t); } }));
    },
    homeExtras: function () {
      if (!UI.ai && site() && !site().repo_readme) return null;   // a guide without a local app yet: reading only
      if (!UI.ai) return h('div', { class: 'actions' },     // the public read-only site: to ask, run it on your own computer
        h('a', { class: 'btn sm primary', href: localGuide(), target: '_blank', rel: 'noopener', text: L('Ask with your own AI: run it on your computer ↗', '用自己的 AI 提问：在自己电脑上部署 ↗') }),
        h('span', { class: 'muted small', text: L('Clone the repository and run python3 serve.py; your Claude or ChatGPT subscription answers from this knowledge base.', '克隆仓库，运行 python3 serve.py；用你自己的 Claude 或 ChatGPT 订阅，依据这个知识库回答。') }));
      return h('div', { class: 'meta', style: 'margin-top:6px' }, aiOn()
        ? [h('span', { text: L('AI: ', 'AI：') + (PROVIDER[UI.ai.provider] || UI.ai.provider) + (UI.ai.model ? ' · ' + UI.ai.model : '') }), h('a', { href: '#/chat', text: L('Ask the knowledge base →', '向知识库提问 →') })]
        : UI.ai ? h('span', { text: L('AI is off: ', 'AI 未启用：') + (UI.ai.hint || '') }) : null);
    },
    topicExtras: function (t) {
      if (!aiOn()) return null;
      var ta = h('textarea', { rows: 3, placeholder: L('(Optional) Say which direction to think in. Leave empty to start from this topic’s open questions and contradictory results', '（可选）写下你想往哪个方向想。不写就围绕这个主题还没回答的问题和互相矛盾的结果') });
      return h('div', { class: 'composer' }, h('b', { text: L('Brainstorm from this topic', '从这个主题出发头脑风暴') }),
        h('p', { class: 'hint', style: 'margin:2px 0 8px', text: L('Your AI reads this topic’s summary, cards and chapter, then proposes 3–6 concrete experiments, each saying whether Marin tried it, the smallest test, and the expected signal.',
          '你的 AI 会先读这个主题的总结、卡片和章节，再提 3–6 条具体实验，每条写清 Marin 试过没有、最小验证实验和预期信号。') }),
        ta, h('div', { class: 'actions' }, h('button', { class: 'btn primary', text: L('Start brainstorming', '开始头脑风暴'), onclick: function () {
          var q = ta.value.trim() || L('Propose experiments worth running on the open questions and contradictory results of the topic "' + t.name + '"', '围绕「' + t.name + '」这个主题还没回答的问题和互相矛盾的结果，提出值得做的实验');
          goAsk('brainstorm', null, t.id); ask({ mode: 'brainstorm', question: q, topic: t.id });
        } })));
    }
  };

  // ---------- Ask & ideas (same modes as the site)
  function pageChat() {
    var root = h('div');
    root.appendChild(h('h2', { text: L('Ask & ideas', '提问和想法') }));
    if (!aiOn()) {
      root.appendChild(h('div', { class: 'card' }, h('p', { text: L('No AI is connected. Run Marin KB with serve.py and sign in to Claude Code or Codex (your subscription), or set an API key; see the README.',
        '还没有连接 AI。用 serve.py 运行 Marin KB，并登录 Claude Code 或 Codex（用你的订阅），或者设置 API key；见 README。') }), UI.ai && UI.ai.hint ? h('p', { class: 'muted small', text: UI.ai.hint }) : null));
      return root;
    }
    var modes = [['ask', L('Ask', '提问讨论')], ['idea', L('Check an idea', '检验想法')], ['brainstorm', L('Brainstorm', '头脑风暴')]];
    var box = h('div', { class: 'composer' });
    box.appendChild(h('div', { class: 'modes' }, modes.map(function (m) {
      return h('button', { class: 'mode' + (UI.mode === m[0] ? ' on' : ''), text: m[1], onclick: function () { UI.mode = m[0]; render(); } });
    })));
    var sel = h('select', { 'aria-label': L('Topic', '主题') }, h('option', { value: '', text: L('Any topic', '不限主题') }),
      M.topics().map(function (t) { var o = h('option', { value: t.id, text: t.name }); if (t.id === UI.topic) o.selected = true; return o; }));
    sel.addEventListener('change', function () { UI.topic = sel.value; });
    var ta = h('textarea', { rows: 5, placeholder: UI.mode === 'idea' ? L('Describe your idea: what you would change and what you expect.', '写下你的想法：想改什么、预期会怎样。')
      : UI.mode === 'brainstorm' ? L('(Optional) a direction to think in', '（可选）想往哪个方向想') : L('Ask anything about Marin’s experiments', '关于 Marin 的实验，问什么都可以') });
    ta.value = UI.draft;
    ta.addEventListener('input', function () { UI.draft = ta.value; });
    add(box, [UI.card ? h('div', { class: 'meta', style: 'margin-bottom:6px' }, h('span', { class: 'chip acc', text: L('About experiment #', '关于实验 #') + UI.card + ' ' + M.cardTitle(UI.card) }),
      h('button', { class: 'btn sm', text: L('Remove', '去掉'), onclick: function () { UI.card = null; render(); } })) : null,
      h('div', { class: 'row', style: 'margin-bottom:8px' }, sel), ta,
      h('div', { class: 'actions' }, h('button', { class: 'btn primary', text: UI.busy ? L('Thinking…', '思考中……') : L('Send', '发送'), disabled: UI.busy || null, onclick: function () {
        var q = ta.value.trim();
        if (!q && UI.mode !== 'brainstorm') return;
        ask({ mode: UI.mode, question: q || L('Propose experiments worth running on the open questions of this topic', '针对这个主题还没回答的问题，提出值得做的实验'), card: UI.card, topic: UI.topic || null });
      } }), h('span', { class: 'muted small', text: L('Answered by ', '回答来自 ') + (PROVIDER[UI.ai.provider] || UI.ai.provider) + L(', from Marin KB’s own text', '，依据 Marin KB 的原文') })),
      UI.err ? h('p', { class: 'note err', text: UI.err }) : null]);
    root.appendChild(box);
    if (UI.busy) root.appendChild(h('p', { class: 'thinking', text: L('Your AI is reading the cards and chapters', '你的 AI 正在读卡片和章节') }));
    if (UI.threads === null) { loadThreads().then(render); return root; }
    var ML = { ask: L('Ask', '提问'), idea: L('Idea', '想法'), brainstorm: L('Brainstorm', '头脑风暴') };
    UI.threads.forEach(function (t) {
      root.appendChild(h('div', { class: 'turn' }, h('div', { class: 'q', text: t.question }),
        h('div', { class: 'qmeta', text: (ML[t.mode] || t.mode) + ' · ' + t.at + (t.card ? ' · #' + t.card : '') + ' · ' + (PROVIDER[t.provider] || t.provider || '') }),
        t.status === 'done' ? h('div', { class: 'a' }, M.answer(t.answer)) : h('p', { class: 'note err', text: t.error || '' })));
    });
    if (!UI.threads.length) root.appendChild(h('p', { class: 'empty', text: L('No questions yet.', '还没有提问。') }));
    return root;
  }

  // ---------- shell
  function route() {
    var p = (location.hash || '#/kb').slice(2).split('/');
    if (p[0] === 'chat') return { page: 'chat' };
    if (p[0] === 't') return { page: 'topic', id: p[1], tab: p[2] || '', part: p[3] };          // older addresses
    if (p[0] !== 'kb') return { page: 'home' };
    if (p[1] === 'doc' || p[1] === 'card') return { page: p[1], id: p[2] };
    if (p[1] && M.hasTopic(p[1])) return { page: 'topic', id: p[1], tab: p[2] || '', part: p[3] };
    return { page: 'home' };
  }
  function shortName() {          // the guide's short name in the current language ([site] short, short_zh)
    var st = site();
    if (!st) return 'Marin KB';
    return (UI.lang === 'zh' && st.short_zh) || st.short;
  }
  function chrome() {
    document.documentElement.lang = UI.lang === 'zh' ? 'zh-CN' : 'en';
    var st = site();
    if (st) {                 // a guide's own name and start pages in the header
      var brand = document.querySelector('header .brand');
      if (brand) brand.textContent = shortName();
      var nav = document.getElementById('nav');
      if (nav && st.nav && !nav.dataset.siteNav) {
        nav.dataset.siteNav = '1';
        var after = nav.querySelector('a[data-r="kb"]');
        st.nav.slice().reverse().forEach(function (x) {
          var a = h('a', { href: '#/kb/doc/' + x.doc, 'data-en': x.en, 'data-zh': x.zh, text: x.en });
          after.insertAdjacentElement('afterend', a);
        });
      }
    }
    document.querySelectorAll('[data-en]').forEach(function (el) { el.textContent = el.getAttribute(UI.lang === 'zh' ? 'data-zh' : 'data-en'); });
    document.querySelectorAll('#langsw button').forEach(function (b) { var on = b.getAttribute('data-lang') === UI.lang; b.className = on ? 'on' : ''; b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
    var chat = document.querySelector('#nav a[data-r="chat"]');
    if (chat) chat.hidden = !aiOn();
    var askx = document.getElementById('askext');
    if (askx) { askx.hidden = !!UI.ai || !!(site() && !site().repo_readme); askx.href = localGuide(); }
    var ag = document.getElementById('agent');
    if (ag) { ag.textContent = ''; add(ag, [h('span', { class: 'dot ' + (aiOn() ? 'on' : 'off') }), aiOn() ? L('AI: ', 'AI：') + (PROVIDER[UI.ai.provider] || UI.ai.provider) : UI.ai ? L('AI off', 'AI 未启用') : L('Read-only (no server)', '只读（没有本地服务）')]); }
  }
  function render() {
    var r = route();
    chrome();
    document.querySelectorAll('#nav a[data-r]').forEach(function (a) { a.classList.toggle('on', a.getAttribute('data-r') === (r.page === 'chat' ? 'chat' : 'kb')); });
    view.textContent = '';
    if (r.page === 'chat') { view.appendChild(pageChat()); document.title = L('Ask & ideas', '提问和想法') + ' · ' + shortName(); return; }
    view.appendChild(M.page(r));
    var t = M.title(r);
    document.title = (t ? t + ' · ' : '') + shortName();
  }
  function load() {
    M.configure({ lang: UI.lang, hooks: hooks, home: '#/kb', doc: function (id) { return '#/kb/doc/' + id; }, card: function (n) { return '#/kb/card/' + n; },
      topic: function (id, tab, part) { return '#/kb/' + id + (tab ? '/' + tab : '') + (part != null ? '/' + part : ''); } });
    chrome();
    return M.ready().then(render).catch(function (e) {
      if (UI.lang === 'zh' && /404/.test(e.message)) { view.textContent = '中文版正在翻译，完成后会在这里上线。可以先切到 EN 看英文版。'; return; }
      view.textContent = (UI.lang === 'zh' ? '载入失败（' : 'Could not load (') + e.message + (UI.lang === 'zh' ? '）。' : ').');
    });
  }
  document.querySelectorAll('#langsw button').forEach(function (b) {
    b.addEventListener('click', function () {
      UI.lang = b.getAttribute('data-lang') === 'zh' ? 'zh' : 'en';
      try { sessionStorage.setItem('siteLang', UI.lang); } catch (e) { /* ignore */ }
      var y = window.scrollY; load().then(function () { window.scrollTo(0, y); });
    });
  });
  // a newer version (auto-update pulled it): offer to reload
  var seen = null;
  setInterval(function () { status().then(function () { if (UI.ai && UI.ai.version) { if (seen && seen !== UI.ai.version) showUpdate(); seen = UI.ai.version; } }); }, 10 * 60 * 1000);
  function showUpdate() {
    if (document.getElementById('upd')) return;
    var nm = shortName();
    document.body.appendChild(h('div', { id: 'upd', class: 'update-bar' }, L(nm + ' was updated. ', nm + ' 已更新。'), h('a', { href: location.href, text: L('Reload', '刷新'), onclick: function () { location.reload(); } })));
  }
  status().then(function () { seen = UI.ai && UI.ai.version; return load(); }).then(function () {
    window.addEventListener('hashchange', function () { render(); if (!M.pendingAnchor()) window.scrollTo(0, 0); });
  });
})();
