/* The replay viewer: one game, one day at a time. Data format: clocktower/export.py (export_game). */
(async function () {
  const { $, $$, esc } = CT;
  const params = new URLSearchParams(location.search);
  const id = params.get('g');
  const S = { day: params.has('day') ? +params.get('day') || 0 : 1, secrets: params.get('secrets') === '1', follow: params.get('follow') || '', target: +params.get('e') || 0 };
  if (!id) { $('#day').innerHTML = 'No game chosen. <a href="games.html">Pick one from the library.</a>'; return; }

  let G, R, index;
  try { [G, R, index] = await Promise.all([CT.game(id), CT.ratings(), CT.json('data/index.json').catch(() => [])]); }
  catch (e) { $('#day').innerHTML = `Couldn't load this game (${esc(e.message)}). <a href="games.html">Back to the library.</a>`; return; }

  const seat = Object.fromEntries(G.seats.map((s) => [s.n, s]));
  // Every player gets a colour by seat (style.css .p0 … .p11); names are underlined in it wherever they appear.
  const seatIdx = Object.fromEntries(G.seats.map((s, i) => [s.n, i]));
  const pn = (n) => (n in seatIdx ? `<span class="pnm p${seatIdx[n]}">${esc(n)}</span>` : esc(n));
  const nameRe = G.seats.length ? new RegExp('\\b(' + G.seats.map((s) => s.n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')\\b', 'g') : null;
  const rich = (text) => (nameRe ? esc(text).replace(nameRe, (m) => pn(m)) : esc(text));  // escaped text, names marked
  const modelOf = (n) => (seat[n] && seat[n].m >= 0 ? G.models[seat[n].m] : null);
  const isOpenAI = (n) => /^gpt|^o\d/.test(modelOf(n) || '');
  const teamName = (t) => CT.name(R, t);
  const days = G.days_;
  const lastDay = days.length ? days[days.length - 1].d : 1;
  if (S.day > lastDay) S.day = lastDay;

  // Who is what on a given day: becomes-events up to and including that day's night.
  const changes = [];
  for (const d of days) for (const sec of d.secs) for (const it of sec.it) if (it.k === 'bec') changes.push({ d: d.d, night: sec.t === 'night', p: it.p, c: it.c });
  const roleOn = (n, day) => { let c = seat[n] ? seat[n].c : '?'; for (const x of changes) if (x.p === n && (x.d < day || (x.d === day && x.night))) c = x.c; return c; };
  // Public deaths: dead at the end of the previous day, plus this dawn's deaths.
  const deadAtDawn = (day) => {
    const prev = days.find((x) => x.d === day - 1), cur = days.find((x) => x.d === day);
    const set = new Set(prev ? prev.dead : []);
    if (cur) for (const sec of cur.secs) if (sec.t === 'dawn') for (const it of sec.it) (it.dd || []).forEach((p) => set.add(p));
    return set;
  };

  /* ---------- header: one line, good vs evil and the result ---------- */
  document.title = `${teamName(G.good)} (good) vs ${teamName(G.evil)} (evil): Clocktower Bench`;
  const team = (t, side) => `<span class="team"><span class="who ${side}">${side}</span>${CT.token(R, t, 'md')}<span>${esc(teamName(t))}</span></span>`;
  $('#g-title').innerHTML = `<h1 class="sr-only">${esc(teamName(G.good))} (good) vs ${esc(teamName(G.evil))} (evil)</h1><p class="matchup">${team(G.good, 'good')}<span class="vs">vs</span>${team(G.evil, 'evil')}<span class="result ${G.winner}">${G.winner === 'good' ? 'Good' : 'Evil'} wins on day ${G.days}</span></p>`;
  const twin = index.find((g) => g.id === G.twin);
  $('#g-meta').innerHTML = [
    `${G.players} players`, G.minions.length ? `Minions: ${G.minions.map(esc).join(', ')}` : '',
    G.group === 'mixed' ? 'Mixed-team game' : G.group === 'unrated' ? '<span title="Opus 4.8\'s first games hit a retry bug and were replayed under v17">Not rated</span>' : '',
    twin ? `<a href="game.html?g=${encodeURIComponent(twin.id)}">Twin game</a> (sides swapped: ${twin.winner} won)` : '',
    `<span class="muted">${esc(G.id)} · seed ${G.seed}</span>`,
  ].filter(Boolean).join(' · ');
  CT.markTerms($('#g-meta'));

  /* ---------- controls ---------- */
  $('#toolbar').hidden = false;
  const tabs = $('#daytabs');
  tabs.innerHTML = `<button role="tab" data-d="0">Setup</button>` + days.map((d) => `<button role="tab" data-d="${d.d}">Day ${d.d}</button>`).join('');
  tabs.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { S.day = +b.dataset.d; S.target = 0; render(true); } });
  const sec = $('#secrets'); sec.checked = S.secrets;
  sec.addEventListener('change', () => { S.secrets = sec.checked; if (!S.secrets) S.follow = ''; render(false); });
  const fol = $('#follow');
  fol.insertAdjacentHTML('beforeend', G.seats.map((s) => `<option value="${esc(s.n)}">See as ${esc(s.n)}</option>`).join(''));
  fol.addEventListener('change', () => { S.follow = fol.value; if (S.follow) S.secrets = true; render(false); });

  /* ---------- text helpers ---------- */
  const md = (s) => rich(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  const roleTag = (n, day) => {
    if (!S.secrets || !seat[n]) return '';
    const c = roleOn(n, day), evil = seat[n].e;
    return `<span class="rtag ${evil ? 'evil' : 'good'}">${esc(c)}${seat[n].s && c === seat[n].c ? ` (thinks ${esc(seat[n].s)})` : ''}</span>`;
  };
  const modelTag = (n) => (S.secrets && G.models.length > 2 && modelOf(n) ? `<span class="small muted">${esc(CT.name(R, modelOf(n)))}</span>` : '');
  const who = (n, day, dead) => `<span>${pn(n)}</span>${roleTag(n, day)}${modelTag(n)}${dead && dead.has(n) ? '<span class="dead">(dead)</span>' : ''}`;
  const reasoning = (n, text, open) => {
    if (!S.secrets || !text) return '';
    if (S.follow && S.follow !== n) return '';
    const label = isOpenAI(n) ? 'Reasoning summary <span class="muted" style="font-weight:500">(OpenAI encrypts the full reasoning)</span>' : 'Private reasoning';
    return `<details class="think"${open ? ' open' : ''}><summary>${label}</summary><div class="body">${md(text)}</div></details>`;
  };
  const secretItem = (it) => it.a || it.k === 'w';
  const visible = (it) => {
    if (!secretItem(it)) return true;
    if (!S.secrets) return false;
    if (!S.follow) return true;
    const f = S.follow;
    if (it.k === 'w') return it.p === f || it.to.includes(f);
    if (it.k === 'info' || it.k === 'note') return (it.to || []).includes(f);
    if (it.k === 'th' || it.k === 'nc') return it.p === f;
    return false;
  };

  /* ---------- items ---------- */
  function msg(it, day, dead) {
    const id = `e${it.s}`;
    switch (it.k) {
      case 'say': return `<div class="msg" id="${id}"><div class="who">${who(it.p, day, dead)}</div><div class="txt">${rich(it.x)}</div>${reasoning(it.p, it.t)}</div>`;
      case 'w': {
        const evilChat = S.secrets && seat[it.p] && seat[it.p].e && it.to.every((t) => seat[t] && seat[t].e);
        return `<div class="msg whisper${evilChat ? ' evilchat' : ''}" id="${id}"><div class="who">${who(it.p, day, dead)}<span class="to">→ ${it.to.map((t) => pn(t)).join(' & ')}</span>${evilChat ? '<span class="small evil">evil team</span>' : ''}</div><div class="txt">${rich(it.x)}</div>${reasoning(it.p, it.t)}</div>`;
      }
      case 'th': return `<div class="think-only" id="${id}">${pn(it.p)} ${it.why === 'nominate' ? 'chose not to nominate' : it.why === 'vote' ? 'thought before voting' : 'passed this turn'}.${reasoning(it.p, it.x)}</div>`;
      case 'nc': return `<div class="msg secret" id="${id}"><b>${pn(it.p)}</b> (${esc(it.r)}) chose ${it.n.length ? it.n.map(pn).join(' and ') : 'nobody'}.${reasoning(it.p, it.t)}</div>`;
      case 'info': return `<div class="msg secret" id="${id}"><b>${(it.to || []).map(pn).join(', ')}</b> learns: ${rich(it.x.replace(/^Night \d+ — /, ''))}</div>`;
      case 'death': return `<div class="msg secret" id="${id}">${pn(it.p)} dies (${rich(it.x)}).</div>`;
      case 'bec': return `<div class="msg secret" id="${id}"><b>${pn(it.p)}</b> becomes the <b>${esc(it.c)}</b>.</div>`;
      case 'note': return `<div class="msg ${it.to ? 'secret' : 'sys'}" id="${id}">${it.to ? `<b>${it.to.map(pn).join(', ')}</b> is told: ` : ''}${rich(it.x)}</div>`;
      case 'sl': return `<div class="verdict" id="${id}">${pn(it.p)} claims the Slayer's power and shoots ${pn(it.n)}. ${it.died ? `<b>${pn(it.n)} dies!</b>` : 'Nothing happens.'}${reasoning(it.p, it.t)}</div>`;
      case 'vg': return `<div class="verdict exec" id="${id}">${pn(it.p)} nominated the Virgin and is executed on the spot. The day ends.</div>`;
      case 'ex': return `<div class="verdict exec" id="${id}">${pn(it.p)} is executed.${it.died ? '' : ' (They were already dead.)'}${S.secrets && seat[it.p] ? ` They were the <b>${esc(roleOn(it.p, day + 1))}</b>.` : ''}</div>`;
      case 'noex': return `<div class="verdict" id="${id}">Nobody is executed today.</div>`;
      case 'end': return `<div class="gameover" id="${id}"><p class="eyebrow">Game over</p><h3 class="${it.w}">${it.w === 'good' ? 'Good' : 'Evil'} wins</h3><p class="muted sans" style="margin:0">${rich(it.x)}</p></div>`;
      case 'dawn': return '';
      default: return '';
    }
  }

  function nominations(items, day, dead) {
    // Group: nomination, defense, comments and votes, result; anything else stands alone.
    const out = []; let cur = null;
    for (const it of items) {
      if (it.k === 'nom') { cur = { nom: it, rest: [], votes: [], res: null }; out.push(cur); continue; }
      if (cur && !cur.res && ['def', 'say', 'v', 'th'].includes(it.k)) { (it.k === 'v' ? cur.votes : cur.rest).push(it); continue; }
      if (cur && it.k === 'vr') { cur.res = it; continue; }
      out.push(it);
    }
    return out.map((g) => {
      if (!g.nom) return visible(g) ? msg(g, day, dead) : '';
      const n = g.nom;
      const rest = g.rest.filter(visible).map((it) => it.k === 'def'
        ? `<div class="msg" id="e${it.s}"><div class="who">${who(it.p, day, dead)}<span class="small muted">defends</span></div><div class="txt">${it.x ? rich(it.x) : '<i class="muted">says nothing</i>'}</div>${reasoning(it.p, it.t)}</div>`
        : msg(it, day, dead)).join('');
      const votes = g.votes.map((v) => `<span class="vote${v.y ? ' yes' : ''}${v.g ? ' ghost' : ''}" id="e${v.s}" title="${esc(v.p)}: ${v.y ? 'yes' : 'no'}${v.g ? ' (ghost vote)' : ''}${v.x ? ' — ' + esc(v.x) : ''}">${pn(v.p)} ${v.y ? '✓' : '·'}</span>`).join('');
      const remarks = g.votes.filter((v) => v.x || (S.secrets && v.t && (!S.follow || S.follow === v.p)));
      const remarkHtml = remarks.length ? `<details class="think"><summary>Vote remarks${S.secrets ? ' and reasoning' : ''} (${remarks.length})</summary><div style="margin-top:6px">${remarks.map((v) =>
        `<div class="msg" style="margin-bottom:4px"><div class="who">${who(v.p, day, dead)}<span class="small muted">votes ${v.y ? 'yes' : 'no'}</span></div>${v.x ? `<div class="txt">${rich(v.x)}</div>` : ''}${reasoning(v.p, v.t)}</div>`).join('')}</div></details>` : '';
      const r = g.res;
      const tally = r ? `<div class="tally ${r.o === 'block' ? 'block' : ''}">${r.c} vote${r.c === 1 ? '' : 's'}, ${r.need} needed. ${{ block: `${pn(r.n)} is about to be executed.`, tie: 'A tie with the leader: nobody is about to be executed.', short: 'Not enough.' }[r.o] || ''}</div>` : '';
      return `<div class="nom" id="e${n.s}"><div class="head">${pn(n.p)}${roleTag(n.p, day)} <span class="arrow">nominates</span> ${pn(n.n)}${roleTag(n.n, day)}</div>
        ${n.x ? `<div class="txt" style="margin-bottom:8px">${rich(n.x)}</div>` : ''}${reasoning(n.p, n.t)}${rest}
        ${votes ? `<div class="votes" aria-label="Votes in order">${votes}</div>` : ''}${tally}${remarkHtml}</div>`;
    }).join('');
  }

  const ICON = {
    night: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>',
    private: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 6h16v10H9l-5 4z" stroke-linejoin="round"/></svg>',
    square: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="8" r="3"/><circle cx="5" cy="11" r="2"/><circle cx="19" cy="11" r="2"/><path d="M6 20c0-3 3-5 6-5s6 2 6 5"/></svg>',
    noms: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v18M5 7h14M7 7l-3 7h6zM17 7l-3 7h6z" stroke-linejoin="round"/></svg>',
  };

  function renderDay(d) {
    const D = days.find((x) => x.d === d);
    if (!D) return '<p>No such day.</p>';
    const dead = deadAtDawn(d);
    let html = '', privCount = 0, privShown = 0;
    const priv = D.secs.filter((s) => s.t === 'private');
    for (const s of priv) for (const it of s.it) if (it.k === 'w') privCount++;
    const night = D.secs.find((s) => s.t === 'night'), dawn = D.secs.find((s) => s.t === 'dawn');
    // Night
    const nightItems = night ? night.it.filter(visible) : [];
    html += `<div class="section"><h2>${ICON.night}Night ${d}</h2>`;
    if (nightItems.length) html += nightItems.map((it) => msg(it, d, dead)).join('');
    else if (!S.secrets) html += `<div class="collapsed">The town sleeps. ${d === 1 ? 'Information roles learn their first clues.' : 'The Demon chooses a victim.'} <button type="button" data-reveal>Reveal secrets</button> to see every night action and what each player learned.</div>`;
    const dw = dawn && dawn.it.find((x) => x.k === 'dawn');
    if (dw) html += `<div class="dawn" style="margin-top:12px" id="e${dw.s}">${dw.x ? `<div class="narr">${rich(dw.x)}</div>` : ''}<div class="deaths">${dw.dd.length ? `Died in the night: ${dw.dd.map(pn).join(', ')}${S.secrets ? ` (${dw.dd.map((p) => esc(roleOn(p, d))).join(', ')})` : ''}.` : 'Nobody died in the night.'}</div></div>`;
    if (dawn) html += dawn.it.filter((x) => x.k !== 'dawn' && visible(x)).map((it) => msg(it, d, dead)).join('');
    html += '</div>';
    // Private time
    html += `<div class="section"><h2>${ICON.private}Private time<span class="kicker">${privCount} whispers in ${priv.length} rounds</span></h2>`;
    if (!S.secrets) html += `<div class="collapsed">Each player holds ${priv.length} one-to-one conversations. Whispers are private. <button type="button" data-reveal>Reveal secrets</button> to read all ${privCount}.</div>`;
    else for (const s of priv) {
      const items = s.it.filter(visible);
      privShown += items.filter((x) => x.k === 'w').length;
      if (!items.length) continue;
      html += `<div class="beat"><div class="beat-h">Round ${s.b}</div>${items.map((it) => msg(it, d, dead)).join('')}</div>`;
    }
    if (S.secrets && S.follow && !privShown) html += `<div class="collapsed">${pn(S.follow)} sent and received no whispers today.</div>`;
    html += '</div>';
    // Town square
    const sq = D.secs.filter((s) => s.t === 'square');
    html += `<div class="section"><h2>${ICON.square}Town square</h2>`;
    for (const s of sq) {
      const items = s.it.filter(visible);
      html += `<div class="beat"><div class="beat-h">Round ${s.b}</div>${items.map((it) => msg(it, d, dead)).join('') || '<p class="muted small sans">Nobody spoke.</p>'}</div>`;
    }
    html += '</div>';
    // Nominations
    const noms = D.secs.find((s) => s.t === 'noms');
    if (noms) {
      const items = noms.it.filter(visible), n = items.filter((x) => x.k === 'nom').length;
      html += `<div class="section"><h2>${ICON.noms}Nominations<span class="kicker">${n} nomination${n === 1 ? '' : 's'}</span></h2>${nominations(noms.it, d, dead) || '<p class="muted">Nobody nominated.</p>'}</div>`;
    }
    // Pager
    html += `<div class="daypager">${d > 0 ? `<button class="btn" data-go="${d - 1}">← ${d === 1 ? 'Setup' : 'Day ' + (d - 1)}</button>` : '<span></span>'}${d < lastDay ? `<button class="btn primary" data-go="${d + 1}">Day ${d + 1} →</button>` : '<a class="btn" href="games.html">Back to the library</a>'}</div>`;
    return html;
  }

  function renderSetup() {
    let html = `<div class="section"><h2>${ICON.square}The table</h2><p class="lede" style="font-size:1.08rem">${G.players} players sit in a circle. ${G.seats.filter((s) => !s.e).length} are good and ${G.seats.filter((s) => s.e).length} are evil: one Demon (the Imp) and ${G.seats.filter((s) => s.e).length - 1} Minions. One model, ${esc(teamName(G.good))}, plays every good seat; ${esc(teamName(G.evil))} plays every evil seat.</p>`;
    if (!S.secrets) html += `<div class="collapsed">Roles are hidden, just as the players see it. <button type="button" data-reveal>Reveal secrets</button> to see the Grimoire: every character, the Demon's bluffs and what each player was told.</div>`;
    else {
      html += `<div class="setup-list">${G.seats.map((s) => `<div><b>${pn(s.n)}</b>: <span class="${s.e ? 'evil' : 'good'}">${esc(s.c)}</span>${s.s ? ` (thinks they are the ${esc(s.s)})` : ''}${s.f ? ` → later the ${esc(s.f)}` : ''}${s.n === G.rh ? ' · the Fortune Teller\'s red herring' : ''}${modelOf(s.n) ? ` <span class="small muted">${esc(CT.name(R, modelOf(s.n)))}</span>` : ''}</div>`).join('')}</div>
        <p class="sans small" style="margin-top:10px">Demon bluffs (three good characters not in play, shown to the Demon): <b>${G.bluffs.map(esc).join(', ')}</b></p>`;
      if (Object.keys(G.intros || {}).length) html += `<h3 style="margin-top:22px">What each player was told</h3>` + G.seats.filter((s) => !S.follow || s.n === S.follow).map((s) => `<div class="sans small"><b>${pn(s.n)}</b></div><div class="intro-text">${rich((G.intros || {})[s.n] || '')}</div>`).join('');
    }
    html += `</div><div class="daypager"><span></span><button class="btn primary" data-go="1">Night 1 →</button></div>`;
    return html;
  }

  /* ---------- aside: seats and the village's suspicion ---------- */
  function renderAside(d) {
    const dead = d ? deadAtDawn(d) : new Set();
    const multi = G.models.length > 2;
    const rows = G.seats.map((s) => {
      const c = d ? roleOn(s.n, d) : s.c;
      const cls = [dead.has(s.n) ? 'dead' : '', S.follow === s.n ? 'on' : ''].join(' ');
      const role = S.secrets ? `<span class="pc ${s.e ? 'evil' : 'good'}">${esc(c)}${multi && modelOf(s.n) ? ` <span class="muted">· ${esc(CT.name(R, modelOf(s.n)))}</span>` : ''}</span>` : '<span class="pc"></span>';
      return `<tr class="${cls}"><td><button type="button" data-seat="${esc(s.n)}" aria-pressed="${S.follow === s.n}" title="See the game as ${esc(s.n)}"><span class="pn pnm p${seatIdx[s.n]}">${esc(s.n)}</span>${role}<span class="ps">${dead.has(s.n) ? 'dead' : ''}</span></button></td></tr>`;
    }).join('');
    const seats = `<table class="players"><tbody>${rows}</tbody></table><p class="small muted" style="margin:8px 0 0">Tap a player to see the game as they saw it${S.secrets ? '' : ' (reveals secrets)'}.</p>`;
    let belief = '';
    if (G.belief && G.belief.length) {
      const cols = G.belief;
      const names = G.seats.map((s) => s.n);
      const cur = cols.find((b) => b.d === d) || cols[cols.length - 1];
      const sorted = names.slice().sort((a, b) => (cur.v[b] ?? -1) - (cur.v[a] ?? -1));
      const accent = CT.css('--accent'), evil = CT.css('--evil');
      const cell = (b, n) => {
        const v = b.v[n]; if (v == null) return '<td class="num muted">–</td>';
        const isDemon = S.secrets && b.demon === n;
        const bg = `color-mix(in oklab, ${isDemon ? evil : accent} ${Math.round(8 + v * 0.8)}%, transparent)`;
        return `<td class="num" data-b="${b.d}" data-n="${esc(n)}" style="background:${bg};${b.d === cur.d ? 'outline:1px solid var(--line-2);' : ''}${isDemon ? 'font-weight:700;' : ''}">${v}</td>`;
      };
      belief = `<details class="panel" id="p-belief"${S.beliefOpen ? ' open' : ''}><summary><h3>Who does the town suspect?</h3>${S.beliefOpen ? '' : ` <span class="small muted sans">top on day ${cur.d}: ${esc(sorted[0])} ${cur.v[sorted[0]]}%</span>`}</summary>
        <p class="small muted sans" style="margin:0 0 10px">Before each day's votes, every good player privately estimates the chance that each player is the Demon (out of game; nobody sees the answers). Average of the living good players, in %.${S.secrets ? ' <span style="color:var(--evil-ink)">Red: the living Demon at the survey.</span>' : ''}</p>
        <div class="scroll-x"><table class="data" style="font-size:.78rem"><thead><tr><th></th>${cols.map((b) => `<th class="num" style="${b.d === cur.d ? 'color:var(--accent-2)' : ''}">D${b.d}</th>`).join('')}</tr></thead>
        <tbody>${sorted.map((n) => `<tr><td style="white-space:nowrap;padding:5px 6px${dead.has(n) ? ';color:var(--faint)' : ''}">${pn(n)}</td>${cols.map((b) => cell(b, n)).join('')}</tr>`).join('')}</tbody></table></div>
        <p class="small muted sans" style="margin:8px 0 0">Sorted by Day ${cur.d}. Tap a number for who believed it most.</p></details>`;
    }
    $('#aside').innerHTML = `<details class="panel" id="p-seats"${S.seatsOpen ? ' open' : ''}><summary><h3>Players</h3><span class="small muted">${G.players}${S.secrets ? '' : ' · roles hidden'}${d ? ` · as of day ${d}` : ''}</span></summary>${seats}</details>${belief}`;
    $('#p-seats').addEventListener('toggle', (e) => { S.seatsOpen = e.target.open; });
    if ($('#p-belief')) $('#p-belief').addEventListener('toggle', (e) => { S.beliefOpen = e.target.open; });
    $$('#aside [data-seat]').forEach((b) => b.addEventListener('click', () => {
      S.follow = S.follow === b.dataset.seat ? '' : b.dataset.seat;
      if (S.follow) S.secrets = true;
      render(false);
    }));
    $$('#aside td[data-b]').forEach((td) => CT.hover(td, () => {
      const b = G.belief.find((x) => x.d === +td.dataset.b), n = td.dataset.n;
      const by = Object.entries(b.by || {}).filter(([p]) => p !== n && b.by[p][n] != null).sort((x, y) => y[1][n] - x[1][n]).slice(0, 3);
      return `<b>${pn(n)}</b>, day ${b.d}: village average ${b.v[n]}% (${b.n} good players)${by.length ? '<br>Most suspicious: ' + by.map(([p, v]) => `${pn(p)} ${v[n]}%`).join(', ') : ''}`;
    }));
  }

  /* ---------- render ---------- */
  function syncUrl() {
    const q = new URLSearchParams({ g: id });
    q.set('day', S.day);
    if (S.secrets) q.set('secrets', '1');
    if (S.follow) q.set('follow', S.follow);
    history.replaceState(null, '', '?' + q);
  }
  function render(scrollTop) {
    $$('#daytabs button').forEach((b) => b.setAttribute('aria-selected', +b.dataset.d === S.day));
    const active = $(`#daytabs button[data-d="${S.day}"]`), strip = $('#daytabs');  // centre the day without scrollIntoView (it moves the keyboard's starting point)
    if (active) strip.scrollLeft = active.offsetLeft - strip.offsetLeft - (strip.clientWidth - active.offsetWidth) / 2;
    $('#secrets').checked = S.secrets;
    $('#follow').value = S.follow;
    const box = $('#day'); box.className = '';
    box.innerHTML = S.day === 0 ? renderSetup() : renderDay(S.day);
    renderAside(S.day);
    CT.markTerms(box); CT.markTerms($('#aside'));
    $$('#day [data-go]').forEach((b) => b.addEventListener('click', () => { S.day = +b.dataset.go; S.target = 0; render(true); }));
    $$('#day [data-reveal]').forEach((b) => b.addEventListener('click', () => { S.secrets = true; render(false); }));
    syncUrl();
    if (S.target) {
      const el = document.getElementById('e' + S.target);
      if (el) {
        el.classList.add('hit'); const det = el.querySelector('details.think'); if (det && el.dataset.open !== '0') det.open = true;
        setTimeout(() => el.scrollIntoView({ block: 'center' }), 60);
      }
      S.target = 0;
    } else if (scrollTop) window.scrollTo({ top: Math.max(0, $('#viewer').offsetTop - 140), behavior: 'instant' in window ? 'instant' : 'auto' });
  }
  // A deep link to a secret moment (a whisper or reasoning) turns secrets on, so the moment is visible.
  if (S.target) {
    for (const d of days) for (const s of d.secs) for (const it of s.it) if (it.s === S.target) { S.day = d.d; if (secretItem(it) || params.get('think') === '1') S.secrets = true; }
  }
  S.seatsOpen = S.beliefOpen = !matchMedia('(max-width: 999px)').matches;
  render(false);
})();
