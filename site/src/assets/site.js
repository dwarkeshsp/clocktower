/* Shared code for every page: config, header, data loading and the SVG charts. No dependencies. */
(function () {
  const C = window.CT_CONFIG || {};
  const CT = (window.CT = { config: C });
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  CT.$ = $; CT.$$ = $$;
  CT.esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ---------- header: mark the current page; config links ---------- */
  const page = document.body.dataset.page;
  $$('.nav a').forEach((a) => { if (a.dataset.nav === page) a.setAttribute('aria-current', 'page'); });
  // Links whose target lives in config.js: hidden-ish when unset, so a placeholder never 404s.
  const wireLinks = () => $$('[data-config-href]').forEach((a) => {
    const url = C[a.dataset.configHref];
    if (url) { a.href = url; if (/^https?:/.test(url)) { a.target = '_blank'; a.rel = 'noopener'; } }
    else if (a.classList.contains('btn')) { a.setAttribute('aria-disabled', 'true'); a.removeAttribute('href'); a.title = 'Coming soon'; const s = document.createElement('span'); s.className = 'small muted'; s.textContent = ' (soon)'; a.append(s); }
    else if (a.classList.contains('feature-card')) { a.removeAttribute('href'); a.setAttribute('aria-disabled', 'true'); a.title = 'Coming soon'; const b = a.querySelector('b'); if (b) b.textContent += ' (soon)'; }
    else a.remove();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wireLinks); else wireLinks();

  /* ---------- data ---------- */
  const cache = {};
  CT.json = (url) => (cache[url] = cache[url] || fetch(url).then((r) => { if (!r.ok) throw new Error(url + ': ' + r.status); return r.json(); }));
  CT.ratings = () => CT.json('data/ratings.json');
  CT.safe = (id) => id.replaceAll('/', '--');
  /** One game: a gzip file inflated in the browser (or plain JSON if the host already decoded it). */
  CT.game = async (id) => {
    const base = C.gameDataBase || 'data/games/';
    const r = await fetch(base + CT.safe(id) + '.json.gz');
    if (!r.ok) throw new Error('Game not found: ' + id);
    const buf = new Uint8Array(await r.arrayBuffer());
    let text;
    if (buf[0] === 0x1f && buf[1] === 0x8b) {
      const ds = new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'));
      text = await new Response(ds).text();
    } else text = new TextDecoder().decode(buf);
    return JSON.parse(text);
  };

  /* ---------- names ---------- */
  CT.name = (R, id) => (R.names && R.names[id]) || id;
  CT.lab = (R, id) => (id.startsWith('mixed:') ? 'Mixed' : (R.labs && R.labs[id]) || '');
  /** A BotC-style token: ink outline, wooden rim, parchment face, the lab's mark (both marks for a mixed team). */
  CT.token = (R, id, cls = '') => {
    const lab = CT.lab(R, id);
    const inner = lab === 'Mixed' ? '<svg class="a"><use href="#lab-Anthropic"/></svg><svg class="o"><use href="#lab-OpenAI"/></svg>'
      : lab ? `<svg><use href="#lab-${lab}"/></svg>` : '';
    return `<span class="tok ${lab} ${cls}" title="${CT.esc(lab === 'Mixed' ? 'Mixed team' : lab)}">${inner}</span>`;
  };
  CT.labMark = (R, id) => CT.token(R, id, 'xs');
  CT.css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  CT.labColor = (lab) => CT.css(lab === 'Anthropic' ? '--anth-lt' : lab === 'OpenAI' ? '--oai-lt' : '--mixed-lt');   // lines and bars on the page
  CT.labInk = (lab) => CT.css(lab === 'Anthropic' ? '--anth' : lab === 'OpenAI' ? '--oai' : '--mixed');            // the mark on a token's face
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  CT.fmtDate = (s) => `${MON[+s.slice(5, 7) - 1]} ${+s.slice(8, 10)}, ${s.slice(0, 4)}`;
  CT.pct = (p) => Math.round(p * 100) + '%';

  /* ---------- tooltip ---------- */
  let tip;
  CT.tip = (html, ev) => {
    if (!tip) { tip = document.createElement('div'); tip.className = 'tip'; tip.setAttribute('role', 'status'); document.body.append(tip); }
    if (!html) { tip.hidden = true; return; }
    tip.innerHTML = html; tip.hidden = false;
    const x = ev.clientX ?? 0, y = ev.clientY ?? 0, w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.max(8, Math.min(x + 14, innerWidth - w - 8)) + 'px';
    tip.style.top = (y + 16 + h > innerHeight ? y - h - 12 : y + 16) + 'px';
  };
  document.addEventListener('scroll', () => CT.tip(null), { passive: true });
  /** Hover and tap both show the tooltip; tapping elsewhere hides it. */
  CT.hover = (node, html) => {
    node.addEventListener('pointerenter', (e) => CT.tip(html(), e));
    node.addEventListener('pointermove', (e) => CT.tip(html(), e));
    node.addEventListener('pointerleave', () => CT.tip(null));
    node.addEventListener('click', (e) => { e.stopPropagation(); CT.tip(html(), e); });
  };
  document.addEventListener('click', () => CT.tip(null));

  /* ---------- game vocabulary: hover (or tap) a character or term for what it means (data/glossary.json) ---------- */
  let terms = null, termRe = null, termsLoading = null;
  const loadTerms = () => termsLoading || (termsLoading = CT.json('data/glossary.json').catch(() => ({})).then((g) => {
    terms = g;
    const keys = Object.keys(g).sort((a, b) => b.length - a.length);
    termRe = keys.length ? new RegExp('\\b(' + keys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')(s|es|ed|ing)?\\b', 'g') : null;  // "Minions", "starpassed", "bussing"
  }));
  const termTip = (t) => { const g = terms[t]; return `<b>${CT.esc(t)}</b>${g.k ? ` · ${CT.esc(g.k)}${g.team ? ', ' + g.team : ''}` : ''}<br>${CT.esc(g.x)}`; };
  /** Wrap every glossary term in root's text in <span class="term">, leaving attributes and existing marks alone. */
  CT.markTerms = async (root) => {
    if (!root) return;
    await loadTerms();
    if (!termRe || !root.isConnected) return;
    const skip = (n) => n.parentNode && n.parentNode.closest && n.parentNode.closest('.term, script, style, option, textarea');
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    for (let n; (n = walker.nextNode());) { termRe.lastIndex = 0; if (!skip(n) && termRe.test(n.nodeValue)) nodes.push(n); }
    for (const n of nodes) {
      const s = n.nodeValue, frag = document.createDocumentFragment();
      let last = 0, m; termRe.lastIndex = 0;
      while ((m = termRe.exec(s))) {
        frag.append(s.slice(last, m.index));
        const el = document.createElement('span'); el.className = 'term'; el.dataset.t = m[1]; el.textContent = m[0];
        frag.append(el); last = m.index + m[0].length;
      }
      frag.append(s.slice(last));
      n.replaceWith(frag);
    }
  };
  const termAt = (e) => { const t = e.target && e.target.closest && e.target.closest('.term'); return t && terms && terms[t.dataset.t] ? t.dataset.t : null; };
  document.addEventListener('pointerover', (e) => { const t = termAt(e); if (t) CT.tip(termTip(t), e); });
  document.addEventListener('pointermove', (e) => { const t = termAt(e); if (t) CT.tip(termTip(t), e); });
  document.addEventListener('pointerout', (e) => { if (termAt(e)) CT.tip(null); });
  document.addEventListener('click', (e) => { const t = termAt(e); if (t) CT.tip(termTip(t), e); });  // after the hide-on-click above, so a tap shows it

  /* ---------- SVG helpers ---------- */
  const NS = 'http://www.w3.org/2000/svg';
  function svgIn(host, W, H, label) {
    host.innerHTML = '';
    const s = document.createElementNS(NS, 'svg');
    s.setAttribute('viewBox', `0 0 ${W} ${H}`); s.setAttribute('width', W); s.setAttribute('height', H);
    s.setAttribute('role', 'img'); if (label) s.setAttribute('aria-label', label);
    host.append(s);
    const el = (t, a, txt, parent = s) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; parent.append(e); return e; };
    return { s, el };
  }
  /** Re-draw a chart when its container changes width or the theme flips. */
  CT.responsive = (host, draw) => {
    let w = 0;
    const go = () => { const nw = Math.round(host.clientWidth); if (nw && nw !== w) { w = nw; draw(nw); } };
    new ResizeObserver(go).observe(host);
    window.addEventListener('ct-theme', () => { w = 0; go(); });
    go();
  };
  /** A chart marker drawn as a little token (wood rim, parchment face, the lab's mark); a diamond for a mixed team. */
  function marker(el, lab, cx, cy, r, attrs = {}, parent) {
    const g = el('g', {}, null, parent), ink = CT.css('--outline');
    if (lab === 'Mixed') { el('rect', { x: cx - r * .78, y: cy - r * .78, width: r * 1.56, height: r * 1.56, fill: CT.labColor(lab), stroke: ink, 'stroke-width': 1.5, transform: `rotate(45 ${cx} ${cy})` }, null, g); return g; }
    el('circle', { cx, cy, r: r + 1.2, fill: ink }, null, g);
    el('circle', { cx, cy, r, fill: CT.css('--wood') }, null, g);
    el('circle', { cx, cy, r: r * .7, fill: CT.css('--parch-hi'), stroke: ink, 'stroke-width': .8 }, null, g);
    const s = r * .95;
    el('use', { href: `#lab-${lab}`, x: cx - s / 2, y: cy - s / 2, width: s, height: s, style: `color:${CT.labInk(lab)}` }, null, g);
    return g;
  }
  /** Greedy label placement: right, left, above, below; skip a label that fits nowhere (the tooltip has it). */
  function placeLabels(el, items, bounds, avoid) {
    const boxes = avoid.slice();
    const hit = (b) => b.x < bounds.x0 || b.x + b.w > bounds.x1 || b.y < bounds.y0 || b.y + b.h > bounds.y1 ||
      boxes.some((o) => b.x < o.x + o.w && b.x + b.w > o.x && b.y < o.y + o.h && b.y + b.h > o.y);
    for (const it of items) {
      const w = it.text.length * 7.2 + 4, h = 16, r = it.r + 5;
      const cands = [[it.x + r, it.y - h / 2, 'start'], [it.x - r - w, it.y - h / 2, 'end'], [it.x - w / 2, it.y - r - h, 'middle'], [it.x - w / 2, it.y + r, 'middle']];
      for (const [x, y, anchor] of cands) {
        const b = { x, y, w, h };
        if (hit(b)) continue;
        boxes.push(b);
        const tx = anchor === 'start' ? x + 2 : anchor === 'end' ? x + w - 2 : x + w / 2;
        el('text', { x: tx, y: y + 12.5, 'text-anchor': anchor, class: 'lbl' }, it.text);
        break;
      }
    }
  }

  /* ---------- chart: rating by release date ---------- */
  CT.chartByDate = (host, R, metric = 'combined') => CT.responsive(host, (W) => {
    const key = { combined: ['combined', 'c90'], detection: ['detection', 'd90'], deception: ['deception', 'v90'] }[metric];
    const ms = R.models;
    const small = W < 560, H = small ? 400 : 440, L = small ? 40 : 52, Rm = small ? 12 : 24, T = 14, B = 30;
    const vals = ms.flatMap((m) => m[key[1]]);
    const lo = Math.floor((Math.min(...vals) - 30) / 100) * 100, hi = Math.ceil((Math.max(...vals) + 30) / 100) * 100;
    const day = (s) => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
    const t0 = Date.UTC(2026, 0, 15), t1 = Date.UTC(2026, 9, 15);
    const x = (s) => L + (day(s) - t0) / (t1 - t0) * (W - L - Rm), y = (v) => T + (hi - v) / (hi - lo) * (H - T - B);
    const { s, el } = svgIn(host, W, H, `${metric} rating of each model by release date`);
    const step = small ? 200 : 100;
    for (let v = lo; v <= hi; v += step) {
      el('line', { x1: L, x2: W - Rm, y1: y(v), y2: y(v), class: v === lo ? 'axis-line' : 'grid-line' });
      el('text', { x: L - 8, y: y(v) + 4, 'text-anchor': 'end' }, v.toLocaleString('en-US'));
    }
    for (let m = 1; m <= 9; m += small ? 2 : 1) {
      const sd = `2026-${String(m + 1).padStart(2, '0')}-01`;
      el('text', { x: x(sd), y: H - 8, 'text-anchor': 'middle' }, MON[m]);
    }
    // the year's trend: least squares through the points (as in the fit's trend_per_year)
    const tr = R.trend_per_year && R.trend_per_year[{ combined: 'c', detection: 'd', deception: 'v' }[metric]];
    if (tr) {
      const xs = ms.map((m) => day(m.date)), ys = ms.map((m) => m[key[0]]);
      const mx = xs.reduce((a, b) => a + b) / xs.length, my = ys.reduce((a, b) => a + b) / ys.length;
      const slope = tr[0] / (365.25 * 864e5);
      const a = Date.UTC(2026, 0, 20), b = Date.UTC(2026, 9, 5);
      const p = (t) => my + slope * (t - mx);
      el('line', { x1: L + (a - t0) / (t1 - t0) * (W - L - Rm), x2: L + (b - t0) / (t1 - t0) * (W - L - Rm), y1: y(p(a)), y2: y(p(b)), stroke: CT.css('--p-mute'), 'stroke-dasharray': '6 5', 'stroke-width': 1.6, opacity: .9 });
    }
    const pts = [];
    for (const m of ms) {
      const lab = CT.lab(R, m.id), c = CT.labColor(lab), bx = x(m.date), [a, b] = m[key[1]];
      el('line', { x1: bx, x2: bx, y1: y(a), y2: y(b), stroke: c, 'stroke-width': 4, opacity: .45 });
      pts.push({ m, lab, x: bx, y: y(m[key[0]]) });
    }
    const g = el('g', {});
    for (const p of pts) {
      const node = marker(el, p.lab, p.x, p.y, small ? 8.5 : 10, {}, g);
      const hitArea = el('circle', { cx: p.x, cy: p.y, r: 16, fill: 'transparent', style: 'cursor:pointer' }, null, g);
      const m = p.m;
      CT.hover(hitArea, () => `<b>${CT.esc(CT.name(R, m.id))}</b> · ${m.lab}<br>${CT.fmtDate(m.date)}<br>${metric[0].toUpperCase() + metric.slice(1)}: <b>${m[key[0]]}</b> (90%: ${m[key[1]][0]}–${m[key[1]][1]})<br>As good ${m.good_wins}/${m.good_games} · as evil ${m.evil_wins}/${m.evil_games}`);
      node.style.pointerEvents = 'none';
    }
    placeLabels(el, pts.slice().sort((a, b) => b.m[key[0]] - a.m[key[0]]).map((p) => ({ x: p.x, y: p.y, r: 10, text: CT.name(R, p.m.id) })),
      { x0: L, x1: W - 2, y0: 0, y1: H - B }, pts.map((p) => ({ x: p.x - 11, y: p.y - 11, w: 22, h: 22 })));
  });

  /* ---------- chart: detection vs deception scatter ---------- */
  CT.chartSplit = (host, R) => CT.responsive(host, (W) => {
    const small = W < 560, H = Math.min(W, small ? 380 : 470), L = 48, Rm = 16, T = 12, B = 42;
    const ms = R.models, lo = 1100, hi = 2000;
    const x = (v) => L + (v - lo) / (hi - lo) * (W - L - Rm), y = (v) => T + (hi - v) / (hi - lo) * (H - T - B);
    const { el } = svgIn(host, W, H, 'Detection rating against deception rating');
    for (let v = lo + 100; v <= hi; v += 100) {
      if (small && v % 200) continue;
      el('line', { x1: x(v), x2: x(v), y1: T, y2: H - B, class: 'grid-line' });
      el('line', { x1: L, x2: W - Rm, y1: y(v), y2: y(v), class: 'grid-line' });
      el('text', { x: x(v), y: H - B + 16, 'text-anchor': 'middle' }, v);
      el('text', { x: L - 7, y: y(v) + 4, 'text-anchor': 'end' }, v);
    }
    el('line', { x1: x(lo), y1: y(lo), x2: x(hi), y2: y(hi), stroke: CT.css('--p-mute'), 'stroke-dasharray': '6 5', 'stroke-width': 1.4 });
    el('text', { x: x(1880), y: y(1950) - 4, 'text-anchor': 'end', 'font-size': 11 }, 'equal at both');
    el('text', { x: (L + W - Rm) / 2, y: H - 6, 'text-anchor': 'middle', class: 'lbl', style: `fill:${CT.css('--good')}` }, 'Detection (playing good) →');
    el('text', { x: 12, y: (T + H - B) / 2, 'text-anchor': 'middle', class: 'lbl', style: `fill:${CT.css('--evil')}`, transform: `rotate(-90 12 ${(T + H - B) / 2})` }, 'Deception (playing evil) →');
    const pts = ms.map((m) => ({ m, lab: CT.lab(R, m.id), x: x(m.detection), y: y(m.deception) }));
    for (const p of pts) {
      marker(el, p.lab, p.x, p.y, 10);
      const h = el('circle', { cx: p.x, cy: p.y, r: 16, fill: 'transparent', style: 'cursor:pointer' });
      const m = p.m;
      CT.hover(h, () => `<b>${CT.esc(CT.name(R, m.id))}</b><br>Detection ${m.detection} (${m.d90[0]}–${m.d90[1]})<br>Deception ${m.deception} (${m.v90[0]}–${m.v90[1]})<br>Won ${m.good_wins}/${m.good_games} as good, ${m.evil_wins}/${m.evil_games} as evil`);
    }
    const ticks = [];
    for (let v = lo + 100; v <= hi; v += 100) if (!(small && v % 200)) ticks.push({ x: 0, y: y(v) - 8, w: L - 4, h: 16 });
    placeLabels(el, pts.map((p) => ({ x: p.x, y: p.y, r: 10, text: CT.name(R, p.m.id) })), { x0: 20, x1: W, y0: 0, y1: H - B }, pts.map((p) => ({ x: p.x - 11, y: p.y - 11, w: 22, h: 22 })).concat(ticks));
  });

  /* ---------- head-to-head expected win rate ---------- */
  CT.winProb = (R, a, b, mode) => {
    const se = R.setup_effects, h = R.good_advantage + 0.5 * (se['Spy'] + se['Scarlet Woman'] + se['Baron']) + (se['11 players'] + se['12 players']) / 3;
    const P = (d) => 1 / (1 + Math.pow(10, -d / 400));
    const g = P(a.detection - b.deception + h), e = 1 - P(b.detection - a.deception + h);
    return mode === 'good' ? g : mode === 'evil' ? e : (g + e) / 2;
  };
  CT.h2h = (host, R, mode = 'both') => {
    const rows = R.models.slice().sort((a, b) => b.combined - a.combined);
    const win = CT.css('--oai-lt'), lose = CT.css('--evil');
    let html = '<table class="h2h"><tr><th></th>' + rows.map((m) => `<th class="col" scope="col"><span>${CT.esc(CT.name(R, m.id))}</span></th>`).join('') + '</tr>';
    rows.forEach((a, i) => {
      html += `<tr><th class="row" scope="row">${CT.esc(CT.name(R, a.id))}</th>`;
      rows.forEach((b, j) => {
        if (a === b) { html += '<td class="self">·</td>'; return; }
        const p = CT.winProb(R, a, b, mode), k = Math.min(Math.abs(p - 0.5) * 2, 1), pct = Math.round(14 + k * 38);  // at most 52%: light text stays above 4.5:1
        const bg = `color-mix(in oklab, ${p >= 0.5 ? win : lose} ${pct}%, ${CT.css('--surface')})`;
        html += `<td data-i="${i}" data-j="${j}" style="background:${bg};color:var(--text)">${Math.round(p * 100)}</td>`;
      });
      html += '</tr>';
    });
    host.innerHTML = html + '</table>';
    CT.$$('td[data-i]', host).forEach((td) => {
      const a = rows[+td.dataset.i], b = rows[+td.dataset.j];
      const ag = (R.h2h || {})[a.id + '|' + b.id] || [0, 0], bg = (R.h2h || {})[b.id + '|' + a.id] || [0, 0];
      const won = ag[0] + (bg[1] - bg[0]), n = ag[1] + bg[1];
      const side = mode === 'good' ? ` as good against ${CT.esc(CT.name(R, b.id))} as evil` : mode === 'evil' ? ` as evil against ${CT.esc(CT.name(R, b.id))} as good` : '';
      CT.hover(td, () => `<b>${CT.esc(CT.name(R, a.id))}</b> vs <b>${CT.esc(CT.name(R, b.id))}</b><br>Expected: ${CT.esc(CT.name(R, a.id))} wins ${Math.round(CT.winProb(R, a, b, mode) * 100)}%${side}<br>Played: ${n ? `won ${won} of ${n}` : 'no games yet'}`);
    });
  };

  /* ---------- line chart over days or skill (village belief, evil tilt) ---------- */
  CT.chartBelief = (host, D) => CT.responsive(host, (W) => {
    const small = W < 560, H = small ? 280 : 320, L = 44, Rm = small ? 16 : 90, T = 26, B = 30, n = D.series[0].by_day.length;
    const x = (d) => L + 30 + (d - 1) / (n - 1) * (W - L - Rm - 30), y = (v) => T + (0.6 - v) / 0.6 * (H - T - B);
    const { el } = svgIn(host, W, H, 'Village belief in the real Demon by day');
    for (let v = 0; v <= 0.6001; v += 0.1) {
      el('line', { x1: L, x2: W - Rm, y1: y(v), y2: y(v), class: v === 0 ? 'axis-line' : 'grid-line' });
      el('text', { x: L - 8, y: y(v) + 4, 'text-anchor': 'end' }, Math.round(v * 100) + '%');
    }
    for (let d = 1; d <= n; d++) el('text', { x: x(d), y: H - 8, 'text-anchor': 'middle' }, 'Day ' + d);
    D.series.forEach((s) => {
      const c = CT.labColor(s.lab), up = s.lab === 'OpenAI';
      el('polyline', { points: s.by_day.map((v, i) => `${x(i + 1)},${y(v)}`).join(' '), fill: 'none', stroke: c, 'stroke-width': 3 });
      s.by_day.forEach((v, i) => {
        marker(el, s.lab, x(i + 1), y(v), 9);
        el('text', { x: x(i + 1), y: up ? y(v) - 15 : y(v) + 25, 'text-anchor': 'middle', class: 'lbl' }, Math.round(v * 100) + '%');
        const h = el('circle', { cx: x(i + 1), cy: y(v), r: 15, fill: 'transparent' });
        CT.hover(h, () => `<b>${s.lab}</b> towns (${CT.esc(s.models)})<br>Day ${i + 1}: ${Math.round(v * 100)}% on the real Demon`);
      });
      if (!small) el('text', { x: x(n) + 12, y: y(s.by_day[n - 1]) + 4, class: 'lbl' }, s.lab);
    });
  });

  CT.chartTilt = (host, D) => CT.responsive(host, (W) => {
    const small = W < 560, H = small ? 280 : 320, L = 44, Rm = 16, T = 24, B = 44, x0 = 1200, x1 = 1900;
    const x = (v) => L + (v - x0) / (x1 - x0) * (W - L - Rm), y = (v) => T + (0.6 - v) / 0.6 * (H - T - B);
    const { el } = svgIn(host, W, H, 'Evil win rate in evenly matched games, by skill');
    for (let v = 0; v <= 0.6001; v += 0.1) {
      el('line', { x1: L, x2: W - Rm, y1: y(v), y2: y(v), class: v === 0 ? 'axis-line' : 'grid-line' });
      el('text', { x: L - 8, y: y(v) + 4, 'text-anchor': 'end' }, Math.round(v * 100) + '%');
    }
    for (let v = x0; v <= x1; v += small ? 200 : 100) el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle' }, v.toLocaleString('en-US'));
    el('text', { x: (L + W - Rm) / 2, y: H - 6, 'text-anchor': 'middle', class: 'lbl' }, 'Skill of both teams (average Elo)');
    const c = CT.css('--evil'), Cv = D.curve;
    el('polygon', { points: Cv.map((p) => `${x(p[0])},${y(p[3])}`).concat(Cv.slice().reverse().map((p) => `${x(p[0])},${y(p[2])}`)).join(' '), fill: c, opacity: .16 });
    el('polyline', { points: Cv.map((p) => `${x(p[0])},${y(p[1])}`).join(' '), fill: 'none', stroke: c, 'stroke-width': 2.2 });
    for (const p of D.points) {
      el('circle', { cx: x(p.x), cy: y(p.p), r: 5.5, fill: CT.css('--text'), stroke: CT.css('--bg'), 'stroke-width': 2 });
      const h = el('circle', { cx: x(p.x), cy: y(p.p), r: 15, fill: 'transparent' });
      CT.hover(h, () => `Teams averaging ~${Math.round(p.x)} Elo, within 200 of each other<br>Evil won <b>${p.e} of ${p.n}</b> (${Math.round(p.p * 100)}%)`);
      if (!small) el('text', { x: x(p.x), y: y(p.p) - 11, 'text-anchor': 'middle', class: 'lbl' }, `${Math.round(p.p * 100)}%`);
    }
  });

  CT.chartMixed = (host, M, R, key = 'combined') => CT.responsive(host, (W) => {
    const H = 300, T = 30, B = 46, L = 46, lo = 1100, hi = 1800, y = (v) => T + (hi - v) / (hi - lo) * (H - T - B);
    const { el } = svgIn(host, W, H, 'Mixed team rating against each model alone');
    for (let v = lo; v <= hi; v += 100) {
      el('line', { x1: L, x2: W - 8, y1: y(v), y2: y(v), class: v === lo ? 'axis-line' : 'grid-line' });
      el('text', { x: L - 8, y: y(v) + 4, 'text-anchor': 'end' }, v.toLocaleString('en-US'));
    }
    const r = M[key], cols = [['claude-opus-5-5', 'Opus 5.5 alone', 'Anthropic'], ['gpt-5.6-sol', 'GPT-5.6 Sol alone', 'OpenAI'], ['mixed', 'Half and half', 'Mixed']];
    const avg = r.members_mean[0];
    el('line', { x1: L + 6, x2: W - 14, y1: y(avg), y2: y(avg), stroke: CT.css('--p-mute'), 'stroke-dasharray': '6 5' });
    el('text', { x: L + 8, y: y(avg) - 6, 'font-size': 11 }, `members' average ${avg}`);
    cols.forEach(([k, label, lab], j) => {
      const cx = L + (W - L) * (j + 0.5) / 3, [v, [a, b]] = r[k], c = CT.labColor(lab);
      el('line', { x1: cx, x2: cx, y1: y(a), y2: y(b), stroke: c, 'stroke-width': 3, 'stroke-linecap': 'round', opacity: .45 });
      marker(el, lab, cx, y(v), 10);
      el('text', { x: cx + 13, y: y(v) + 4, class: 'lbl' }, v);
      el('text', { x: cx, y: H - 22, 'text-anchor': 'middle', class: 'lbl' }, label);
      const h = el('circle', { cx, cy: y(v), r: 18, fill: 'transparent' });
      CT.hover(h, () => `<b>${label}</b><br>${v} Elo (90%: ${a}–${b})`);
    });
    const e = r.effect;
    el('text', { x: (L + W) / 2, y: 16, 'text-anchor': 'middle', class: 'lbl' }, `Mixing effect: ${e[0] > 0 ? '+' : '−'}${Math.abs(e[0])} Elo (90%: ${e[1][0]} to ${e[1][1] > 0 ? '+' : ''}${e[1][1]})`);
  });
  /* ---------- the leaderboard as a script sheet: token, name, release month, bar with its 90% interval, Elo ---------- */
  CT.board = (host, R, compact = false) => {
    const ms = R.models.slice().sort((a, b) => b.combined - a.combined);
    const lo = Math.floor((Math.min(...ms.map((m) => m.c90[0])) - 120) / 100) * 100, hi = Math.ceil((Math.max(...ms.map((m) => m.c90[1])) + 10) / 100) * 100;
    const pos = (v) => ((v - lo) / (hi - lo) * 100).toFixed(2) + '%';
    const n = (v) => v.toLocaleString('en-US');
    const head = `<thead><tr><th class="num">#</th><th>Model</th><th class="hide-xs">Released</th><th class="barcell">Rating <span class="hide-sm">· 90% interval</span></th><th class="num">Elo</th>` +
      (compact ? '' : '<th class="num hide-sm">Detection</th><th class="num hide-sm">Deception</th><th class="num hide-sm">Won as good</th><th class="num hide-sm">Won as evil</th>') + '</tr></thead>';
    host.innerHTML = head + '<tbody>' + ms.map((m, i) => {
      const lab = CT.lab(R, m.id), [a, b] = m.c90;
      return `<tr>
        <td class="num rank">${i + 1}</td>
        <td><div class="model">${CT.token(R, m.id, 'sm')}<div><a href="games.html?model=${encodeURIComponent(m.id)}">${CT.esc(CT.name(R, m.id))}</a>${compact ? '' : `<span class="labname hide-xs">${lab}</span>`}</div></div></td>
        <td class="hide-xs dim">${MON[+m.date.slice(5, 7) - 1]}</td>
        <td class="barcell"><div class="bar" title="${n(m.combined)} (90%: ${n(a)}–${n(b)})"><span class="fill ${lab}" style="width:${pos(m.combined)}"></span><span class="ci" style="left:${pos(a)};width:calc(${pos(b)} - ${pos(a)});--k:${((m.combined - a) / (b - a) * 100).toFixed(1)}%"></span></div></td>
        <td class="num elo">${n(m.combined)}</td>` +
        (compact ? '' : `<td class="num hide-sm">${n(m.detection)}</td><td class="num hide-sm">${n(m.deception)}</td><td class="num hide-sm dim">${m.good_wins}/${m.good_games}</td><td class="num hide-sm dim">${m.evil_wins}/${m.evil_games}</td>`) + '</tr>';
    }).join('') + '</tbody>';
    CT.$$('tbody tr', host).forEach((tr, i) => {
      const m = ms[i];
      CT.hover(tr.querySelector('.bar'), () => `<b>${CT.esc(CT.name(R, m.id))}</b> · ${CT.lab(R, m.id)}<br>Rating ${n(m.combined)} (90%: ${n(m.c90[0])}–${n(m.c90[1])})<br>Detection ${n(m.detection)} · deception ${n(m.deception)}<br>Won ${m.good_wins}/${m.good_games} as good, ${m.evil_wins}/${m.evil_games} as evil`);
    });
  };

  /* ---------- a game's two teams as a small vs card ---------- */
  CT.vsTeams = (R, g, size = 'md') => {
    const side = (t, team) => `<div class="team ${g.winner === team ? 'won' : 'lost'}"><span class="plate ${team}">${team}</span>${CT.token(R, t, size + ' ' + team)}<span class="nm">${CT.esc(CT.name(R, t))}</span>${g.winner === team ? '<span class="wins">wins</span>' : ''}</div>`;
    return `<div class="vsrow">${side(g.good, 'good')}<span class="vs" aria-label="versus">vs</span>${side(g.evil, 'evil')}</div>`;
  };
})();
