/* Marin KB knowledge-base view, bilingual (English / 简体中文). One renderer for both languages, so the two editions have
   the same pages and features and differ only in language. Used by kb.html (standalone, e.g. GitHub Pages) and by the
   research-kb app (its site-wide EN / 中文 switch).
   Data per language: kb/data.json (English master) and kb/data_zh.json (checked translation), chapters kb/ch/*.md and
   kb/ch_zh/*.md. Chinese chapters are paired with the English ones block by block: headings take the English anchors and
   each quote carries its English original as a tooltip. Card text is inserted with textContent; chapter Markdown is
   sanitised with DOMPurify; links are rewritten to in-page routes, GitHub, or pages of the book. */
(function () {
  'use strict';
  var GH = 'https://github.com/marin-community/marin/';
  var VORDER = ['positive', 'negative', 'mixed', 'inconclusive', 'unfinished', 'record', 'in progress'];
  var VCLS = { positive: 'v-yes', negative: 'v-no', mixed: 'v-mix', inconclusive: 'v-unk', unfinished: 'v-drop', record: 'v-log', 'in progress': 'v-open' };
  var VZH = { positive: '有效', negative: '无效', mixed: '有好有坏', inconclusive: '没定论', unfinished: '没跑完', record: '记录', 'in progress': '进行中' };
  var VHELP = {
    positive: ['The change helped and was kept or recommended', '改动有用，被保留或推荐'], negative: ['The change did not help', '改动没有用'],
    mixed: ['Helped on some measures or scales, not others', '在部分指标或规模上有用，其他没有'], inconclusive: ['The results did not settle the question', '结果没能回答这个问题'],
    unfinished: ['Stopped before a result', '没跑出结果就停了'], record: ['A log or a run with no comparison', '只是记录或单次运行，没有对照'], 'in progress': ['Still running at the snapshot', '快照时还在进行']
  };
  // the public sites of the guides that link to each other (a host may override with CFG.relatedUrl)
  var RELATED_SITES = { marin: 'https://marin-kb.vercel.app/#/kb/', vllm: 'https://vllm-kb.vercel.app/#/kb/', sglang: 'https://sglang-kb.vercel.app/#/kb/' };
  var CFG = {
    lang: 'en', assets: '', home: '#/', hooks: {},
    topic: function (id, tab, part) { return '#/t/' + id + (tab ? '/' + tab : '') + (part != null ? '/' + part : ''); },
    doc: function (id) { return '#/doc/' + id; }, card: function (n) { return '#/card/' + n; }
  };
  var DATA = {}, MDS = { en: {}, zh: {} }, BYNS = {}, LOADING = {};
  var D = null, MD = MDS.en, BYN = {}, UI = { q: '', v: {}, imp: false, shown: 60, anchor: null };
  function zh() { return CFG.lang === 'zh'; }
  function S() { return (D && D.site) || null; }          // per-guide texts (code guides); Marin KB has none and keeps its own
  function SL(o) { return o ? (zh() ? (o.zh || o.en) : o.en) : ''; }
  function L(en, cn) { return zh() ? cn : en; }
  function vl(v) { return zh() ? (VZH[v] || v) : v; }
  function vh(v) { return VHELP[v] ? VHELP[v][zh() ? 1 : 0] : ''; }
  function useLang() { D = DATA[CFG.lang] || null; MD = MDS[CFG.lang]; BYN = BYNS[CFG.lang] || {}; }
  function T(id, tab, part) { return CFG.topic(id, tab, part); }

  // ---------- DOM helpers
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) { c.forEach(function (x) { add(el, x); }); return; }
    el.appendChild(typeof c === 'object' ? c : document.createTextNode(String(c)));
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function ext(href, text, cls) { return h('a', { href: href, target: '_blank', rel: 'noopener noreferrer', text: text, class: cls }); }
  function issue(n) { return GH + 'issues/' + (n | 0); }
  function cardRef(n) {
    return h('a', { class: 'ref', href: issue(n), text: '#' + (n | 0), title: L('Show this experiment', '查看这个实验'),
      onclick: function (e) { if (BYN[n] && !e.metaKey && !e.ctrlKey) { e.preventDefault(); drawer(n); } } });
  }
  function refList(ns) { var out = []; (ns || []).forEach(function (n, i) { if (i) out.push(' '); out.push(cardRef(n)); }); return out; }
  function topicById(id) { return D.topics.find(function (t) { return t.id === id; }); }
  function docById(id) { return D.docs.find(function (d) { return d.id === id; }); }
  function mins(words) { var m = Math.max(1, Math.round((words || 0) / 230)); return L(m + ' min', m + ' 分钟'); }
  function plural(n, one, many, cn) { return zh() ? n + ' ' + cn : n + ' ' + (n === 1 ? one : many); }
  function vbar(vc) {
    return h('div', { class: 'vbar', 'aria-hidden': 'true' }, VORDER.filter(function (v) { return vc && vc[v]; }).map(function (v) {
      return h('span', { class: 'seg ' + VCLS[v], style: 'flex:' + vc[v], title: vl(v) + ' ' + vc[v] });
    }));
  }
  function tex(s, display) {
    var el = h('div', { class: 'tex' });
    if (window.katex) { try { window.katex.render(s, el, { displayMode: display, throwOnError: false }); return el; } catch (e) { /* fall through */ } }
    el.textContent = s;
    return el;
  }
  function lightbox(src, alt) {
    var box = h('div', { class: 'lightbox', role: 'dialog', 'aria-label': alt || 'figure', onclick: function () { box.remove(); } }, h('img', { src: src, alt: alt || '' }));
    document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') { box.remove(); document.removeEventListener('keydown', esc); } });
    document.body.appendChild(box);
  }
  function figure(f) {
    var src = CFG.assets + '_images/' + encodeURIComponent(f.file);
    var label = f.src || L('the original thread', '原帖');
    var where = f.link && /^https:\/\/(github\.com\/marin-community\/marin|huggingface\.co)\//.test(f.link) ? ext(f.link, label) : label;
    var who = f.by ? '@' + f.by : S() ? L('a contributor', '一位贡献者') : L('a Marin contributor', '一位 Marin 贡献者');
    return h('figure', { class: 'fig' },
      h('img', { src: src, alt: f.cap, loading: 'lazy', onclick: function () { lightbox(src, f.cap); } }),
      h('figcaption', null, f.cap, h('br'), zh() ? h('span', null, who, f.date ? ' 于 ' + f.date : '', ' 发在 ', where, '。')
        : h('span', null, 'Posted by ', who, f.date ? ' on ' + f.date : '', ' in ', where, '.')));
  }

  // ---------- chapter Markdown -> page (the same files the book is built from)
  function slug(s) { return s.trim().toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/\s/g, '-'); }
  function stripCode(md) { return String(md).replace(/```[\s\S]*?```|~~~[\s\S]*?~~~/g, ''); }
  function headsOf(md) { var out = []; stripCode(md).replace(/^(#{2,3})\s+(.*)$/gm, function (m, l, t) { out.push(t.trim()); }); return out; }
  function quotesOf(md) { var out = []; stripCode(md).replace(/^\s*>\s*"(.*)"\s*$/gm, function (m, q) { out.push(q); }); return out; }
  function docRoute(file) {          // a .md link inside a chapter -> an in-page route (or a page of the book)
    var m = file.match(/(?:^|\/)([A-Za-z0-9_-]+)\.md$/);
    if (!m) return null;
    var id = m[1];
    if (/catalog\//.test(file)) return topicById(id) ? T(id, 'cards') : CFG.home;
    if (id === 'explorer') return CFG.home;
    var d = docById(id);
    if (!d) return CFG.assets + file.replace(/\.md$/, '.html').replace(/^(\.\.\/)+/, '');
    return d.topic ? T(d.topic, 'doc', d.part != null ? d.part : null) : CFG.doc(id);
  }
  function fetchText(path) {
    return fetch(CFG.assets + path, { credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); });
  }
  function loadDoc(id) {             // -> {md, en}: the chapter in the current language, and the English master for pairing
    var d = docById(id), key = CFG.lang;
    if (MDS[key][id]) return Promise.resolve(MDS[key][id]);
    var jobs = [fetchText(d.file)];
    if (d.file_en) jobs.push(fetchText(d.file_en));
    return Promise.all(jobs).then(function (x) { MDS[key][id] = { md: x[0], en: x[1] || x[0] }; return MDS[key][id]; });
  }
  var SRC_RE = /(—\s*(?:Table |Figure )?[Ss]ource:|—\s*Code:|—\s*(?:表格|图片)?来源：)/;
  function renderMd(md, el, en) {
    var maths = [];
    function keep(t, d) { maths.push([t, d]); return 'MATHTOKEN' + (maths.length - 1) + 'END'; }
    var parts = String(md || '').split(/(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]+`)/);
    for (var i = 0; i < parts.length; i += 2) {
      parts[i] = parts[i].replace(/\$\$([\s\S]+?)\$\$/g, function (m, t) { return keep(t, true); })
        .replace(/\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)/g, function (m, t) { return keep(t, false); });
    }
    var html;
    if (window.marked && window.DOMPurify) {
      html = window.DOMPurify.sanitize(window.marked.parse(parts.join(''), { gfm: true }), {
        FORBID_TAGS: ['style', 'form', 'input', 'button', 'textarea', 'select', 'iframe', 'object', 'embed', 'svg', 'math', 'video', 'audio', 'script'],
        FORBID_ATTR: ['style', 'srcset']
      });
    } else { var pre = document.createElement('pre'); pre.textContent = md; html = pre.outerHTML; }
    html = html.replace(/MATHTOKEN(\d+)END/g, function (m, n) {
      var x = maths[+n]; if (!x) return '';
      if (window.katex) { try { return window.katex.renderToString(x[0], { displayMode: x[1], throwOnError: false, trust: false, strict: 'ignore' }); } catch (e) { /* fall through */ } }
      var c = document.createElement('code'); c.textContent = x[0]; return c.outerHTML;
    });
    el.innerHTML = html;
    el.querySelectorAll('img').forEach(function (img) {      // only the book's own figure files, as captioned figures
      var m = (img.getAttribute('src') || '').match(/(?:^|\/)figures\/([A-Za-z0-9._-]+)$/);
      if (!m) { img.remove(); return; }
      var src = CFG.assets + '_images/' + m[1], alt = img.getAttribute('alt') || '';
      var p = img.parentNode, fig = h('figure', { class: 'fig wide' });
      var im = h('img', { src: src, alt: alt, loading: 'lazy', onclick: function () { lightbox(src, alt); } });
      var cap = h('figcaption', null, h('b', { text: alt }));
      if (p && p.tagName === 'P') {
        img.remove();
        var rest = Array.prototype.slice.call(p.childNodes);
        if (rest.length) { cap.appendChild(h('br')); rest.forEach(function (n) { cap.appendChild(n); }); }
        fig.appendChild(im); fig.appendChild(cap); p.replaceWith(fig);
      } else { fig.appendChild(im); fig.appendChild(cap); img.replaceWith(fig); }
    });
    var originals = en && en !== md ? quotesOf(en) : null, qi = 0;
    el.querySelectorAll('blockquote').forEach(function (bq) {
      bq.querySelectorAll('p').forEach(function (p) {
        p.innerHTML = p.innerHTML.replace(new RegExp('(?:<br>)?\\s*(' + SRC_RE.source + '[\\s\\S]*)$'), '<span class="srcline">$1</span>');
      });
      if (bq.querySelector('.srcline')) {
        bq.classList.add('evq');
        if (originals && /^\s*["“]/.test(bq.textContent)) { var o = originals[qi++]; if (o) bq.title = '原文：' + o; }
      }
    });
    el.querySelectorAll('p').forEach(function (p) {
      if (new RegExp('^\\s*' + SRC_RE.source).test(p.textContent) || /^\s*(Compiled from|根据)/.test(p.textContent) && p.querySelector('em, a')) p.classList.add('srcline');
    });
    el.querySelectorAll('table').forEach(function (t) { var w = h('div', { class: 'tablebox' }); t.replaceWith(w); w.appendChild(t); });
    var mm = el.querySelectorAll('pre > code.language-mermaid');
    if (mm.length) {
      mm.forEach(function (c) { var d = h('div', { class: 'mermaid-box' }); d.dataset.src = c.textContent; d.textContent = c.textContent; c.parentNode.replaceWith(d); });
      mermaidLoad().then(function (mermaid) {
        el.querySelectorAll('.mermaid-box').forEach(function (d, i) {
          d.classList.add('ok'); d.textContent = '';              // switch to the page font before measuring
          mermaid.render('mm' + Date.now() + i, d.dataset.src, d).then(function (r) { d.innerHTML = r.svg; }).catch(function () { d.classList.remove('ok'); d.classList.add('bad'); d.textContent = d.dataset.src; });
        });
      }).catch(function () { /* diagrams stay as text */ });
    }
    var enHeads = en ? headsOf(en) : null;
    el.querySelectorAll('h2, h3').forEach(function (hd, k) { hd.id = enHeads && enHeads[k] ? slug(enHeads[k]) : slug(hd.textContent); });
    el.querySelectorAll('a').forEach(function (a) {
      var href = a.getAttribute('href') || '';
      var im = href.match(/^https:\/\/github\.com\/marin-community\/marin\/issues\/(\d+)/);
      if (im && BYN[+im[1]]) {
        a.classList.add('iref'); a.title = L('Show this experiment', '查看这个实验');
        a.addEventListener('click', function (e) { if (!e.metaKey && !e.ctrlKey) { e.preventDefault(); drawer(+im[1]); } });
      }
      if (/^https?:\/\//i.test(href)) { a.target = '_blank'; a.rel = 'noopener noreferrer'; return; }
      if (href.charAt(0) === '#') {
        a.addEventListener('click', function (e) { var t = document.getElementById(href.slice(1)); if (t) { e.preventDefault(); t.scrollIntoView({ behavior: 'smooth', block: 'start' }); } });
        return;
      }
      var m = href.match(/^([^#]+\.md)(?:#(.*))?$/);
      if (m) {
        var r = docRoute(m[1]);
        if (r && r.charAt(0) === '#') { a.setAttribute('href', r); if (m[2]) a.addEventListener('click', function () { UI.anchor = m[2]; }); }
        else if (r) a.setAttribute('href', r + (m[2] ? '#' + m[2] : ''));
        return;
      }
      if (!/\.html(#.*)?$/.test(href)) a.removeAttribute('href');
    });
    return el;
  }
  var mermaidP = null;
  function mermaidLoad() {
    if (!mermaidP) mermaidP = import('https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.4.0/mermaid.esm.min.mjs').then(function (m) {
      var mermaid = m.default;
      var dark = document.documentElement.getAttribute('data-theme') === 'dark' || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
      var font = getComputedStyle(document.body).fontFamily;        // measure labels with the font they are drawn in
      mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: dark ? 'dark' : 'neutral', fontFamily: font,
        themeVariables: { fontFamily: font }, flowchart: { useMaxWidth: true, htmlLabels: true, wrappingWidth: 420 } });
      return mermaid;
    });
    return mermaidP;
  }
  function sections(md) {          // split a chapter at its ## headings
    var out = [], cur = { title: '', body: [] }, inCode = false;
    String(md).split('\n').forEach(function (l) {
      if (/^\s*(```|~~~)/.test(l)) inCode = !inCode;
      var m = !inCode && l.match(/^##\s+(.*)$/);
      if (m) { out.push(cur); cur = { title: m[1].trim(), body: [] }; } else cur.body.push(l);
    });
    out.push(cur);
    return out.map(function (s) { return { title: s.title, body: s.body.join('\n') }; });
  }
  function pairedSections(doc) {   // [{title (current language), en (English title), body}]
    var a = sections(doc.md), b = sections(doc.en);
    return a.map(function (s, i) { return { title: s.title, en: (b[i] || s).title, body: s.body }; });
  }
  function teaser(body) {
    var t = body.replace(/```[\s\S]*?```/g, ' ').split('\n').filter(function (l) { return l.trim() && !/^\s*([>|#!*-]|\d+\.|\$\$)/.test(l); })[0] || '';
    t = t.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/[*_`]/g, '').replace(/\$[^$]*\$/g, '…');
    var max = zh() ? 90 : 190;
    return t.length > max ? t.slice(0, max - 2).replace(zh() ? /$/ : /\s+\S*$/, '') + '…' : t;
  }

  // ---------- reading view: article, sticky contents with scrollspy, progress bar
  var spy = null;
  function readingView(id) {
    var d = docById(id);
    var art = h('article', { class: 'md doc-article' }, h('p', { class: 'muted', text: L('Loading the chapter…', '正在载入章节……') }));
    var toc = h('nav', { class: 'toc', 'aria-label': L('Contents', '目录') }, h('div', { class: 'toc-h', text: L('Contents', '目录') }));
    var bar = h('div', { class: 'progress' }, h('span'));
    var wrap = h('div', null, bar, h('div', { class: 'doc' }, art, toc));
    loadDoc(id).then(function (doc) {
      clear(art);
      art.appendChild(h('div', { class: 'docmeta' },
        h('span', { text: L('Every quote, table and figure is checked against the source', '引文、表格和图都和原始记录逐字核对过') + (zh() ? '（鼠标停在引文上可看原文）' : '') })));
      var body = h('div');
      renderMd(doc.md, body, doc.en);
      art.appendChild(body);
      var heads = Array.prototype.slice.call(body.querySelectorAll('h2, h3'));
      heads.forEach(function (hd) {
        toc.appendChild(h('a', { class: hd.tagName.toLowerCase(), href: '#' + hd.id, text: hd.textContent,
          onclick: function (e) { e.preventDefault(); hd.scrollIntoView({ behavior: 'smooth', block: 'start' }); } }));
      });
      if (spy) spy.disconnect();
      if ('IntersectionObserver' in window) {
        spy = new IntersectionObserver(function (es) {
          es.forEach(function (e) {
            if (!e.isIntersecting) return;
            toc.querySelectorAll('a').forEach(function (a) { a.classList.toggle('on', a.getAttribute('href') === '#' + e.target.id); });
          });
        }, { rootMargin: '-80px 0px -70% 0px' });
        heads.forEach(function (hd) { spy.observe(hd); });
      }
      var target = UI.anchor && document.getElementById(UI.anchor);
      UI.anchor = null;
      if (target) setTimeout(function () { target.scrollIntoView({ block: 'start' }); }, 30);
    }).catch(function (e) { clear(art); art.appendChild(h('p', { class: 'note err', text: L('Could not load the chapter (', '章节载入失败（') + e.message + L(').', '）。') })); });
    function onScroll() {
      if (!document.body.contains(wrap)) { window.removeEventListener('scroll', onScroll); return; }
      var r = art.getBoundingClientRect(), total = r.height - window.innerHeight;
      bar.firstChild.style.width = Math.min(100, Math.max(0, total > 0 ? -r.top / total * 100 : 0)) + '%';
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    return wrap;
  }

  // ---------- process and pitfalls, pulled out of the chapter (sections found by their English titles)
  function pitfallCards(body) {
    var items = [], cur = null, intro = [];
    body.split('\n').forEach(function (l) {
      var m = l.match(/^(\d+)\.\s+(.*)$/);
      if (m) { cur = { n: m[1], lines: [m[2]] }; items.push(cur); } else if (cur) cur.lines.push(l); else intro.push(l);
    });
    var out = [];
    if (intro.join('').trim()) out.push(renderMd(intro.join('\n'), h('div', { class: 'md-inline' })));
    items.forEach(function (it) {
      var txt = it.lines.join('\n'), m = txt.match(/^\*\*(.+?)\*\*\s*/), title, rest;
      if (m) { title = m[1].replace(/[.:。：]$/, ''); rest = txt.slice(m[0].length); }
      else { var s = txt.split(/(?<=[.!?。！？])\s*/); title = s[0]; rest = txt.slice(title.length); }
      var det = h('details', { class: 'pit' }, h('summary', null, h('span', { class: 'pitn', text: it.n }), h('span', { class: 'pitt' }, renderMd(title, h('span', { class: 'md-inline' })))));
      det.addEventListener('toggle', function () { if (det.open && !det._f) { det._f = true; det.appendChild(renderMd(rest, h('div', { class: 'md pit-body' }))); } });
      out.push(det);
    });
    return out;
  }
  var PROC = [[/timeline/i, 'Timeline', '时间线', 'tl'], [/how .*(work|was done)|how marin ran|process/i, 'How the work was done', '工作是怎么做的', 'how'],
    [/pitfall|lesson/i, 'Pitfalls and lessons', '踩过的坑和教训', 'pits'], [/open question/i, 'Open questions', '还没回答的问题', 'open']];
  function processView(t) {
    var box = h('div', null, h('p', { class: 'muted', text: L('Loading…', '载入中……') }));
    Promise.all(t.chapters.map(function (c) { return loadDoc(c.id); })).then(function (docs) {
      clear(box);
      docs.forEach(function (doc, k) {
        var secs = pairedSections(doc), c = t.chapters[k];
        if (t.chapters.length > 1) box.appendChild(h('h2', { class: 'chap-h', text: c.title }));
        (S() && S().process ? S().process.map(function (x) { return [new RegExp(x[0], 'i'), x[1], x[2], x[3] || 'how']; }) : PROC).forEach(function (spec) {
          var s = secs.find(function (x) { return spec[0].test(x.en); });
          if (!s) return;
          var card = h('section', { class: 'card pcard-' + spec[3] }, h('h3', { class: 'sec-h' }, L(spec[1], spec[2]),
            h('a', { class: 'small muted jump', href: T(t.id, 'doc', t.chapters.length > 1 ? k : null), text: L('in the chapter →', '在章节里看 →'),
              onclick: function () { UI.anchor = slug(s.en); } })));
          if (spec[3] === 'pits') add(card, pitfallCards(s.body));
          else card.appendChild(renderMd(s.body, h('div', { class: 'md' + (spec[3] === 'tl' ? ' timeline' : '') })));
          box.appendChild(card);
        });
      });
    }).catch(function (e) { clear(box); box.appendChild(h('p', { class: 'note err', text: L('Could not load (', '载入失败（') + e.message + L(').', '）。') })); });
    return box;
  }

  // ---------- cards
  function prList(prs) {
    if (!prs || !prs.length) return null;
    var ST = { merged: L('merged', '已合并'), open: L('open', '还开着'), closed: L('closed', '没合并') };
    var REL = { 'mentioned in the issue': L('mentioned in the issue', 'issue 提到'), 'cites the issue': L('cites the issue', 'PR 引用了这个 issue') };
    return h('div', { class: 'prs' }, h('div', { class: 'muted small', text: L('Code (pull requests):', '代码（PR）：') }),
      h('ul', null, prs.map(function (p) {
        var k = Number(p.k);
        return h('li', null, ext(GH + 'pull/' + k, '#' + k), ' ',
          h('span', { class: 'chip' + (p.s === 'merged' ? ' good' : ''), text: (ST[p.s] || p.s) + ' ' + (p.d || '').slice(2) }), ' ',
          h('span', { text: p.ti || '' }), p.rel ? h('span', { class: 'muted', text: ' · ' + (REL[p.rel] || p.rel) }) : null,
          h('div', { class: 'muted small mono', text: '+' + (p.a || 0) + '/−' + (p.x || 0) + L(', ', '，') + (p.f || 0) + (p.fm ? '+' : '') + L(' files', ' 个文件') + ((p.p || []).length ? L(': ', '：') + p.p.join('  ') : '') }));
      })));
  }
  function card(r, open) {
    var safe = /^https:\/\/github\.com\/marin-community\/marin\//.test(r.qurl || '') ? r.qurl : issue(r.n);
    var t = topicById(r.t);
    var det = h('details', null, h('summary', { text: L('Setup, quote, pull requests' + (r.fig.length ? ' and figures' : ''), '做法、原文、PR' + (r.fig.length ? '和图' : '')) }));
    function fill() {
      if (det._filled) return;
      det._filled = true;
      add(det, [
        h('dl', { class: 'kv' }, h('dt', { text: L('Setup', '做法') }), h('dd', { text: r.s }), r.sc ? [h('dt', { text: L('Scale', '规模') }), h('dd', { text: r.sc })] : null),
        r.qu ? h('blockquote', { class: 'quote', text: r.qu, title: r.qo ? '原文：' + r.qo : null }) : null,
        r.fig.length ? h('div', { class: 'cardfigs' }, r.fig.map(figure)) : null,
        prList(r.pr),
        h('div', { class: 'small' }, ext(safe, r.qu ? L('Source of the quote', '引文出处') : L('Open the issue', '打开 issue')),
          r.nimg ? [' · ', ext(issue(r.n), L(r.nimg + (r.nimg === 1 ? ' more image' : ' more images') + ' in the issue', 'issue 里还有 ' + r.nimg + ' 张图'))] : null,
          r.l && r.l.length ? [L(' · Related: ', ' · 相关：'), refList(r.l)] : null),
        CFG.hooks.cardActions ? CFG.hooks.cardActions(r) : null]);
    }
    det.addEventListener('toggle', function () { if (det.open) fill(); });
    if (open) { det.open = true; fill(); }
    return h('div', { class: 'card mcard', id: 'c' + r.n },
      h('div', { class: 'mhead' }, h('span', { class: 'vpill ' + (VCLS[r.v] || 'v-unk'), text: vl(r.v), title: vh(r.v) }), h('h3', { text: r.ti })),
      h('div', { class: 'meta' }, t ? h('a', { class: 'chip', href: T(t.id), text: t.name }) : null, ext(issue(r.n), '#' + r.n, 'ref'), h('span', { text: r.d }),
        r.sc ? h('span', { text: r.sc }) : null,
        r.w === 3 ? h('span', { class: 'chip warn', text: L('Important', '重要'), title: L('Went into the recipe, was checked at several scales, or is cited by other experiments', '进了配方、在多个规模上验证过，或被别的实验引用') }) : null,
        r.a ? h('span', { class: 'chip', text: L('written up by an agent', 'agent 撰写') }) : null,
        r.st === 'open' ? h('span', { class: 'chip', text: L('issue still open', 'issue 还开着') }) : null,
        r.pr.length ? h('span', { class: 'chip', text: r.pr.length + (zh() ? ' 个 PR' : r.pr.length === 1 ? ' PR' : ' PRs') }) : null,
        r.fig.length ? h('span', { class: 'chip acc', text: plural(r.fig.length, 'figure', 'figures', '张图') }) : null,
        r.new ? h('span', { class: 'chip good', text: L('new since the chapter', '章节之后新增') }) : null,
        CFG.hooks.cardChips ? CFG.hooks.cardChips(r) : null),
      !zh() && r.en && r.en !== r.ti ? h('div', { class: 'muted small en', text: r.en }) : null,
      h('dl', { class: 'kv' }, h('dt', { text: L('Question', '问题') }), h('dd', { text: r.q }), h('dt', { text: L('Result', '结果') }), h('dd', { text: r.r })),
      det);
  }
  function drawer(n) {
    var r = BYN[n]; if (!r) return;
    var old = document.querySelector('.drawer-wrap'); if (old) old.remove();
    function close() { wrap.remove(); document.removeEventListener('keydown', esc); }
    function esc(e) { if (e.key === 'Escape') close(); }
    var t = topicById(r.t);
    var wrap = h('div', { class: 'drawer-wrap mkb' }, h('div', { class: 'drawer-bg', onclick: close }),
      h('aside', { class: 'drawer', role: 'dialog', 'aria-label': L('Experiment #', '实验 #') + n, tabindex: '-1' },
        h('div', { class: 'drawer-top' }, h('span', { class: 'muted small', text: L('Experiment #', '实验 #') + n }), h('button', { class: 'btn sm', text: L('Close', '关闭'), onclick: close })),
        card(r, true),
        h('div', { class: 'actions' }, t ? h('a', { class: 'btn sm', href: T(t.id), text: L('Topic: ', '主题：') + t.name, onclick: close }) : null,
          ext(issue(n), L('Open the issue on GitHub', '在 GitHub 上打开 issue'), 'btn sm'))));
    document.addEventListener('keydown', esc);
    document.body.appendChild(wrap);
    wrap.querySelector('.drawer').focus();
  }
  function hay(r) {
    if (!r._h) r._h = [r.ti, r.en, r.q, r.s, r.sc, r.r, r.qu, r.qo].concat(r.pr.map(function (p) { return p.ti; })).join(' \u0001 ').toLowerCase();
    return r._h;
  }
  function filter(topic) {
    var terms = UI.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    var vs = VORDER.filter(function (v) { return UI.v[v]; });
    return D.cards.filter(function (r) {
      if (topic && r.t !== topic) return false;
      if (vs.length && vs.indexOf(r.v) < 0) return false;
      if (UI.imp && r.w !== 3) return false;
      for (var i = 0; i < terms.length; i++) {
        var x = terms[i].replace(/^#/, '');
        if (/^\d+$/.test(x) && (r.n === +x || r.pr.some(function (p) { return Number(p.k) === +x; }))) continue;
        if (hay(r).indexOf(terms[i]) < 0) return false;
      }
      return true;
    });
  }
  function cardList(topic) {
    var box = h('div'), list = h('div', { class: 'mlist' }), count = h('div', { class: 'muted small' });
    var mine = D.cards.filter(function (r) { return !topic || r.t === topic; });
    function draw() {
      clear(list);
      var rows = filter(topic);
      rows.slice(0, UI.shown).forEach(function (r) { list.appendChild(card(r)); });
      if (!rows.length) list.appendChild(h('p', { class: 'empty', text: L('No card matches. Try another word, or clear the filters.', '没有符合条件的卡片。换个关键词，或者清掉筛选。') }));
      if (rows.length > UI.shown) list.appendChild(h('button', { class: 'btn', text: L('Show 60 more (' + rows.length + ' in all)', '再显示 60 张（共 ' + rows.length + ' 张）'), onclick: function () { UI.shown += 60; draw(); } }));
      count.textContent = L('Showing ' + Math.min(rows.length, UI.shown) + ' / ' + rows.length + ' matching / ' + mine.length + ' in all',
        '显示 ' + Math.min(rows.length, UI.shown) + ' / 符合条件 ' + rows.length + ' / 共 ' + mine.length);
    }
    var input = h('input', { type: 'search', placeholder: L('Search the cards and PR titles, or type an issue or PR number', '搜索卡片和 PR 标题，或者输入 issue / PR 编号'), value: UI.q, 'aria-label': L('Search the cards', '搜索卡片') });
    var timer;
    input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { UI.q = input.value; UI.shown = 60; draw(); }, 150); });
    var imp = h('input', { type: 'checkbox', checked: UI.imp ? true : null });
    imp.addEventListener('change', function () { UI.imp = imp.checked; UI.shown = 60; draw(); });
    var chips = h('div', { class: 'tabs', style: 'margin:8px 0' }, VORDER.map(function (v) {
      var n = mine.filter(function (r) { return r.v === v; }).length;
      var b = h('button', { class: 'tab' + (UI.v[v] ? ' on' : ''), text: vl(v) + ' ' + n, title: vh(v), onclick: function () { UI.v[v] = !UI.v[v]; b.className = 'tab' + (UI.v[v] ? ' on' : ''); UI.shown = 60; draw(); } });
      return b;
    }));
    add(box, [input, chips, h('label', { class: 'small muted', style: 'display:inline-flex;gap:6px;align-items:center' }, imp,
      L('Important only (went into the recipe, checked at several scales, or cited by other experiments)', '只看重要的（进了配方、多规模验证过，或被别的实验引用的）')), h('div', { style: 'height:6px' }), count, list]);
    draw();
    return box;
  }

  // ---------- pages
  function pageHome() {
    var root = h('div');
    if (S()) return pageHomeSite(root);
    root.appendChild(h('h2', null, L('Knowledge base', '知识库'), h('span', { class: 'n', text: L(D.n + ' Marin experiments · ' + D.topics.length + ' topics · ' + D.npr + ' experiments with linked PRs (' + D.prs + ' PRs)',
      D.n + ' 个 Marin 实验 · ' + D.topics.length + ' 个主题 · ' + D.npr + ' 个实验关联了 PR（共 ' + D.prs + ' 个）') })));
    root.appendChild(h('div', { class: 'card' },
      h('div', { class: 'lead' }, zh() ? ['每个 ', ext(GH, 'Marin', 'marin-link'), ' 实验一张卡：'] : ['One card per ', ext(GH, 'Marin', 'marin-link'), ' experiment: '], L('what was asked, how it was compared, at what scale, the result, whether the conclusion holds, and the original source. ' +
        'Marin (github.com/marin-community/marin) is an open lab that trains language models in public and records every experiment as a GitHub issue. ' +
        'Every topic opens into a full chapter: the timeline, each line of experiments with Marin’s own tables, figures and formulas, how the work was done, the pitfalls, and the open questions. ' +
        'Cards and summaries were drafted by agents from the issue threads; every quote, copied table and figure is checked word for word against the source by a script.',
        '问的什么、怎么比的、多大规模、结果、结论站不站得住、原文出处。Marin（github.com/marin-community/marin）是公开训练大模型、把每个实验都记成 GitHub issue 的开源实验室。' +
        '每个主题都能展开成一章完整的文档：时间线、每一条实验线（附 Marin 自己的表格、图和公式）、工作是怎么做的、踩过的坑、还没回答的问题。卡片和总结由 agent 根据 issue 原文撰写；引文、表格和图都由脚本和原文逐字核对。')),
      h('div', { class: 'meta', style: 'margin-top:8px' }, h('span', { text: L('Experiments opened ' + D.first + ' to ' + D.last, '实验时间 ' + D.first + ' 到 ' + D.last) }), h('span', { text: L('snapshot ', '快照 ') + D.snapshot })),
      CFG.hooks.homeExtras ? CFG.hooks.homeExtras() : null));
    if (D.headline.length) root.appendChild(h('div', { class: 'card' }, h('h3', { text: L('Start with these (Marin’s main findings)', '先看这些（Marin 的主要结论）') }),
      h('ol', { class: 'find' }, D.headline.map(function (x) { return h('li', null, x.text, ' ', refList(x.refs)); }))));
    var guides = D.docs.filter(function (d) { return !d.topic; });
    root.appendChild(h('h2', { text: L('Guides', '导读') }));
    root.appendChild(h('div', { class: 'tiles guides' }, guides.map(function (d) {
      return h('a', { class: 'tile', href: CFG.doc(d.id) }, h('span', { class: 'tg', text: d.kind || '' }), h('span', { class: 'tn', text: d.title }),
        d.blurb ? h('span', { class: 'ts', text: d.blurb }) : null);
    })));
    root.appendChild(h('h2', { text: L('By topic', '按主题') }));
    root.appendChild(h('div', { class: 'tiles' }, D.topics.map(function (t) {
      var stale = (t.fresh || []).length || (CFG.hooks.staleCount ? CFG.hooks.staleCount(t.id) : 0);
      return h('a', { class: 'tile', href: T(t.id) }, h('span', { class: 'tg', text: t.group }), h('span', { class: 'tn', text: t.name }),
        h('span', { class: 'tc', text: L(t.count + ' experiments', t.count + ' 个实验') +
          (t.formulas.length ? L(' · ' + plural(t.formulas.length, 'formula', 'formulas', ''), ' · ' + t.formulas.length + ' 个公式') : '') + (stale ? L(' · ' + stale + ' new since the chapter', ' · ' + stale + ' 个新实验未写进章节') : '') }),
        vbar(t.verdicts), h('span', { class: 'ts', text: t.summary }));
    })));
    root.appendChild(h('h2', { text: L('Search all cards', '搜全部卡片') }));
    root.appendChild(cardList(null));
    return root;
  }
  function pageHomeSite(root) {     // a guide with its own site config (code guides): chapters as topics, no experiment cards
    var st = S();
    root.appendChild(h('h2', null, SL(st.name), h('span', { class: 'n', text: SL(st.stats) })));
    root.appendChild(h('div', { class: 'card' },
      h('div', { class: 'lead' }, ext(st.project.url, (zh() && st.project.name_zh) || st.project.name, 'marin-link'), ' ', SL(st.lead)),
      st.meta ? h('div', { class: 'meta', style: 'margin-top:8px' }, h('span', { text: SL(st.meta) })) : null,
      CFG.hooks.homeExtras ? CFG.hooks.homeExtras() : null));
    if (D.headline.length) root.appendChild(h('div', { class: 'card' }, h('h3', { text: SL(st.headline_title) }),
      h('ol', { class: 'find' }, D.headline.map(function (x) { return h('li', null, x.text); }))));
    var guides = D.docs.filter(function (d) { return !d.topic; });
    if (guides.length) {
      root.appendChild(h('h2', { text: SL(st.guides_title) || L('Start here', '从这里开始') }));
      root.appendChild(h('div', { class: 'tiles guides' }, guides.map(function (d) {
        return h('a', { class: 'tile', href: CFG.doc(d.id) }, h('span', { class: 'tg', text: d.kind || '' }), h('span', { class: 'tn', text: d.title }),
          d.blurb ? h('span', { class: 'ts', text: d.blurb }) : null);
      })));
    }
    var groups = [];
    D.topics.forEach(function (t) { if (groups.indexOf(t.group) < 0) groups.push(t.group); });
    groups.forEach(function (g) {
      root.appendChild(h('h2', { text: g }));
      root.appendChild(h('div', { class: 'tiles' }, D.topics.filter(function (t) { return t.group === g; }).map(function (t) {
        return h('a', { class: 'tile', href: T(t.id) }, h('span', { class: 'tg', text: t.group }), h('span', { class: 'tn', text: t.name }),
          t.formulas.length ? h('span', { class: 'tc', text: L(t.formulas.length + (t.formulas.length === 1 ? ' formula' : ' formulas'), t.formulas.length + ' 个公式') }) : null,
          h('span', { class: 'ts', text: t.summary }));
      })));
    });
    return root;
  }
  function topicTabs(t, cur) {
    var tabs = [['', L('Overview', '概览')], ['doc', L('Full chapter', '章节全文')], ['process', S() ? SL(S().process_tab) : L('Process and pitfalls', '流程和踩坑')]];
    if (t.count) tabs.push(['cards', L('Experiments (' + t.count + ')', '全部卡片（' + t.count + '）')]);
    return h('div', { class: 'tabs topic-tabs', role: 'tablist' }, tabs.map(function (x) {
      return h('a', { class: 'tab' + (cur === x[0] ? ' on' : ''), role: 'tab', 'aria-selected': cur === x[0] ? 'true' : 'false', href: T(t.id, x[0] || null), text: x[1] });
    }));
  }
  function overview(t) {
    var box = h('div');
    var syn = h('div', { class: 'card' }, h('div', { class: 'lead', text: t.summary }));
    if (t.findings.length) add(syn, [h('h3', { class: 'sec', text: L('Current findings', '目前的结论') }), h('ol', { class: 'find' }, t.findings.map(function (f) { return h('li', null, f.text, ' ', refList(f.refs)); }))]);
    if (t.open.length) add(syn, [h('h3', { class: 'sec', text: L('Open questions', '还没回答的') }), h('ul', { class: 'find muted' }, t.open.map(function (f) { return h('li', null, f.text, ' ', refList(f.refs)); }))]);
    if (t.key.length) syn.appendChild(h('p', { class: 'small', style: 'margin:10px 0 0' }, h('b', { text: L('Read first: ', '建议先读：') }), refList(t.key)));
    if (t.date) syn.appendChild(h('p', { class: 'small muted', style: 'margin:8px 0 0', text: L('Summary written ' + t.date + ' from the experiment cards.', '总结写于 ' + t.date + '，依据这个主题的实验卡。') }));
    if (CFG.hooks.topicSummaryExtras) add(syn, CFG.hooks.topicSummaryExtras(t));
    box.appendChild(syn);
    if ((t.fresh || []).length) box.appendChild(h('div', { class: 'card fresh' }, h('b', { text: L(t.fresh.length + (t.fresh.length === 1 ? ' experiment' : ' experiments') + ' added after this chapter was written (' + t.chapter_date + ')',
      '章节写完（' + t.chapter_date + '）之后新增了 ' + t.fresh.length + ' 个实验') }), h('div', { class: 'small muted', style: 'margin:4px 0' },
      L('Their cards are below and in the Experiments tab; the chapter will take them in at its next review.', '它们的卡片在下面和"全部卡片"里；章节下次审稿改写时会并入。')), h('div', null, refList(t.fresh))));
    if ((t.related || []).length) box.appendChild(h('div', { class: 'card related' }, h('h3', { text: L('Related in the other guides', '在其他导读里') }),
      h('ul', { class: 'find' }, t.related.map(function (r) {
        var url = CFG.relatedUrl ? CFG.relatedUrl(r.kb, r.id) : RELATED_SITES[r.kb] ? RELATED_SITES[r.kb] + r.id : null;
        return h('li', null, url ? h('a', { href: url, text: r.title, target: /^https?:/.test(url) ? '_blank' : null, rel: 'noopener' }) : r.title, h('div', { class: 'muted small', text: r.why }));
      }))));
    if (t.formulas.length) box.appendChild(h('div', { class: 'card' }, h('h3', { text: L('Key formulas', '关键公式') }),
      t.formulas.map(function (f) { return h('div', { class: 'formula' }, tex(f.tex, true), h('div', { class: 'what', text: f.what })); }),
      h('p', { class: 'small muted', style: 'margin:8px 0 0', text: L('Copied from the chapter, where each formula is given with its source.', '公式抄自章节全文，出处在章节里。') })));
    if (t.figures.length) box.appendChild(h('div', { class: 'card' }, h('h3', { text: L('Key figures', '关键图') }), h('div', { class: 'figs' }, t.figures.map(figure))));
    var inside = h('div', { class: 'card' }, h('h3', { text: L('Inside the chapter', '章节里有什么') }), h('p', { class: 'muted small', text: L('Loading…', '载入中……') }));
    box.appendChild(inside);
    Promise.all(t.chapters.map(function (c) { return loadDoc(c.id); })).then(function (docs) {
      inside.removeChild(inside.lastChild);
      docs.forEach(function (doc, k) {
        var secs = pairedSections(doc).filter(function (s) { return s.title && !/^sources$/i.test(s.en); });
        if (t.chapters.length > 1) inside.appendChild(h('div', { class: 'tg', style: 'margin-top:10px', text: t.chapters[k].title }));
        var glance = secs.find(function (s) { return /at a glance/i.test(s.en); });
        if (glance && k === 0) inside.appendChild(h('details', { class: 'glance' }, h('summary', { text: L('At a glance: every line of experiments in one table', '一表看全：所有实验线') }), renderMd(glance.body, h('div', { class: 'md' }))));
        inside.appendChild(h('div', { class: 'outline' }, secs.filter(function (s) { return !/at a glance/i.test(s.en); }).map(function (s) {
          return h('a', { class: 'osec', href: T(t.id, 'doc', t.chapters.length > 1 ? k : null), onclick: function () { UI.anchor = slug(s.en); } },
            h('span', { class: 'ot', text: s.title }), h('span', { class: 'od', text: teaser(s.body) }));
        })));
      });
    });
    if (CFG.hooks.topicExtras) add(box, CFG.hooks.topicExtras(t));
    return box;
  }
  function pageTopic(t, sub, part) {
    var root = h('div');
    root.appendChild(h('p', { style: 'margin:16px 0 0' }, h('a', { href: CFG.home, text: L('← All topics', '← 知识库') })));
    root.appendChild(h('div', { class: 'topic-hero' }, h('div', { class: 'tg', text: t.group }), h('h1', { text: t.name }),
      h('div', { class: 'meta' }, t.count ? h('span', { text: L(t.count + ' Marin experiments', t.count + ' 个 Marin 实验') }) : null,
        t.formulas.length ? h('span', { text: L(plural(t.formulas.length, 'key formula', 'key formulas', ''), t.formulas.length + ' 个关键公式') }) : null),
      vbar(t.verdicts)));
    root.appendChild(topicTabs(t, sub || ''));
    if (sub === 'doc') {
      var k = Math.min(t.chapters.length - 1, Math.max(0, +part || 0));
      if (t.chapters.length > 1) root.appendChild(h('div', { class: 'tabs' }, t.chapters.map(function (c, i) {
        return h('a', { class: 'tab' + (i === k ? ' on' : ''), href: T(t.id, 'doc', i), text: c.title });
      })));
      root.appendChild(readingView(t.chapters[k].id));
    } else if (sub === 'process') root.appendChild(processView(t));
    else if (sub === 'cards') root.appendChild(cardList(t.id));
    else root.appendChild(overview(t));
    return root;
  }
  function pageDoc(id) {
    var d = docById(id), root = h('div');
    root.appendChild(h('p', { style: 'margin:16px 0 0' }, h('a', { href: CFG.home, text: L('← Knowledge base', '← 知识库') })));
    if (!d) { root.appendChild(h('p', { class: 'empty', text: L('No such page.', '没有这个页面。') })); return root; }
    root.appendChild(h('div', { class: 'topic-hero' }, h('div', { class: 'tg', text: d.kind || '' }), h('h1', { text: d.title })));
    root.appendChild(readingView(id));
    return root;
  }
  function pageCard(n) {
    var r = BYN[n], root = h('div');
    root.appendChild(h('p', { style: 'margin:16px 0 8px' }, h('a', { href: CFG.home, text: L('← All topics', '← 知识库') }),
      r && topicById(r.t) ? [' · ', h('a', { href: T(r.t), text: topicById(r.t).name })] : null));
    if (!r) { root.appendChild(h('p', { class: 'empty' }, L('#' + n + ' is not an experiment issue in this snapshot. ', '#' + n + ' 不是这次快照里的实验 issue。'), ext(issue(n), L('Open it on GitHub', '在 GitHub 上打开')))); return root; }
    root.appendChild(card(r, true));
    return root;
  }
  function footer() {
    if (S()) return h('footer', { class: 'foot' }, SL(S().footer), ' ', ext(S().project.url, S().project.url.replace(/^https:\/\//, '')), ' · ',
      h('a', { href: CFG.assets + 'intro.html', text: L('Book edition', '书籍版') }));
    return h('footer', { class: 'foot' }, L('Snapshot of Marin’s public experiment record (', 'Marin 公开实验记录的快照（'), ext(GH, 'github.com/marin-community/marin'),
      L('), ' + D.snapshot + '. Text CC BY 4.0; figures belong to their authors and are credited on each figure. An independent reading aid, not an official Marin publication. ',
        '），' + D.snapshot + '。文字以 CC BY 4.0 发布；图归原作者所有，每张图都注明了出处。这是独立的阅读辅助，不是 Marin 官方出版物。'),
      h('a', { href: CFG.assets + 'figure-credits.html', text: L('Figure credits', '图片出处') }), ' · ', h('a', { href: CFG.assets + 'sources.html', text: L('Sources and method', '资料和方法') }));
  }

  // ---------- public interface (kb-standalone.js and the research-kb app)
  function page(route) {          // route: {page: 'home'|'topic'|'doc'|'card', id, tab, part}
    var el;
    if (route.page === 'topic' && topicById(route.id)) { if (route.tab !== 'cards') UI.shown = 60; el = pageTopic(topicById(route.id), route.tab, route.part); }
    else if (route.page === 'doc' && docById(route.id)) el = pageDoc(route.id);
    else if (route.page === 'card' && /^\d+$/.test(String(route.id || ''))) el = pageCard(+route.id);
    else el = pageHome();
    return h('div', { class: 'mkb', lang: zh() ? 'zh-CN' : 'en' }, el, footer());
  }
  window.MarinKB = {
    configure: function (c) {
      if (c.assets != null && c.assets !== CFG.assets) {     // another knowledge base (e.g. Marin -> vLLM): forget the old one's data
        DATA = {}; MDS = { en: {}, zh: {} }; BYNS = {}; LOADING = {}; UI.q = ''; UI.v = {};
      }
      for (var k in c) CFG[k] = c[k];
      useLang();
    },
    assets: function () { return CFG.assets; },
    lang: function () { return CFG.lang; },
    ready: function () {
      var lang = CFG.lang;
      if (DATA[lang]) { useLang(); return Promise.resolve(DATA[lang]); }
      if (!LOADING[lang]) LOADING[lang] = fetch(CFG.assets + (lang === 'zh' ? 'kb/data_zh.json' : 'kb/data.json'), { credentials: 'same-origin' })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (d) { DATA[lang] = d; BYNS[lang] = {}; d.cards.forEach(function (c) { BYNS[lang][c.n] = c; }); useLang(); return d; })
        .catch(function (e) { LOADING[lang] = null; throw e; });
      return LOADING[lang];
    },
    data: function () { return DATA[CFG.lang] || null; },
    page: page,
    title: function (route) { var t = route.page === 'topic' && topicById(route.id), d = route.page === 'doc' && docById(route.id); return t ? t.name : d ? d.title : ''; },
    hasTopic: function (id) { return !!(DATA[CFG.lang] && topicById(id)); },
    topics: function () { return D ? D.topics.map(function (t) { return { id: t.id, name: t.name }; }) : []; },
    cardTitle: function (n) { return BYN[n] ? BYN[n].ti : ''; },
    drawer: drawer,
    answer: function (md) {          // an AI answer: Markdown, with every #N that is an experiment linked to its card
      var el = renderMd(md, h('div', { class: 'md answer' }));
      var walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), nodes = [], n;
      while ((n = walk.nextNode())) if (/#\d{2,6}/.test(n.nodeValue) && !(n.parentNode.closest && n.parentNode.closest('a, code, pre'))) nodes.push(n);
      nodes.forEach(function (node) {
        var frag = document.createDocumentFragment(), last = 0, t = node.nodeValue, m, re = /#(\d{2,6})/g;
        while ((m = re.exec(t))) {
          if (!BYN[+m[1]]) continue;
          frag.appendChild(document.createTextNode(t.slice(last, m.index)));
          frag.appendChild(cardRef(+m[1]));
          last = m.index + m[0].length;
        }
        frag.appendChild(document.createTextNode(t.slice(last)));
        node.replaceWith(frag);
      });
      return el;
    },
    pendingAnchor: function () { return !!UI.anchor; }
  };
})();
