// Clocktower table: lobby, the town circle, the chronicle and the action dock for one human seat.
// Everything a seat sees comes from /api/state (the same events and prompts a model in that seat gets).
// No inline styles in markup: the page's Content-Security-Policy has no 'unsafe-inline' (positions and delays
// are set through element.style, which the policy allows).
'use strict';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* private mode */ } },
};
const svg = (body, cls = 'i') => `<svg class="${cls}" viewBox="0 0 24 24" aria-hidden="true">${body}</svg>`;
const ICON = {
  moon: svg('<path d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a6.8 6.8 0 0 0 10.7 10.7z"/>'),
  sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
  bell: svg('<path d="M18 9a6 6 0 0 0-12 0c0 7-3 8.5-3 8.5h18S18 16 18 9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/>'),
  quill: svg('<path d="M20 4c-6 0-11 4-13 11l-1.5 5"/><path d="M20 4c0 6-4 10-10 11"/><path d="M9 12h5"/>'),
  town: svg('<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="3.5" r="1.6"/><circle cx="20.5" cy="12" r="1.6"/><circle cx="12" cy="20.5" r="1.6"/><circle cx="3.5" cy="12" r="1.6"/>'),
  book: svg('<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/>'),
  scroll: svg('<path d="M7 3h11a2 2 0 0 1 2 2v1H9"/><path d="M7 3a2 2 0 0 0-2 2v14a2 2 0 0 1-2 2h12a2 2 0 0 0 2-2V6"/><path d="M9 9h5M9 13h5"/>'),
  pen: svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>'),
  sound: svg('<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>'),
  mute: svg('<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M22 9l-6 6M16 9l6 6"/>'),
  glass: svg('<path d="M6 2h12M6 22h12"/><path d="M7 2c0 5 10 5 10 10S7 17 7 22"/><path d="M17 2c0 5-10 5-10 10s10 5 10 10"/>'),
  whisper: svg('<path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'),
  lock: svg('<rect x="5" y="11" width="14" height="10" rx="1"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>'),
  eye: svg('<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
  skull: svg('<path d="M12 3a8 8 0 0 0-5 14.2V20h10v-2.8A8 8 0 0 0 12 3z"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/>'),
  arrow: svg('<path d="M12 2 4 22l8-5 8 5z"/>'),
  hand: svg('<path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10.5V4a1.5 1.5 0 0 1 3 0v6.5M14 10.5V5.5a1.5 1.5 0 0 1 3 0V14c0 4-2.5 7-6.5 7-3 0-4.5-1.5-6-4l-1.8-3a1.5 1.5 0 0 1 2.4-1.8L8 14"/>'),
  seal: svg('<circle cx="12" cy="12" r="8"/><path d="M8.5 12.2l2.4 2.3 4.6-4.8"/>'),
  good: '<svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="7" fill="currentColor"/><g stroke="currentColor" stroke-width="2.6" stroke-linecap="square"><path d="M20 4v5M20 31v5M4 20h5M31 20h5M8.7 8.7l3.5 3.5M27.8 27.8l3.5 3.5M8.7 31.3l3.5-3.5M27.8 12.2l3.5-3.5"/></g></svg>',
  evil: '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M9 6c1 6 3 9 6 10M31 6c-1 6-3 9-6 10" stroke="currentColor" stroke-width="2.6" fill="none" stroke-linecap="square"/><path d="M20 13c-6 0-10 4.5-10 10.5S14.5 35 20 35s10-5.5 10-11.5S26 13 20 13z" fill="currentColor"/><path d="M15 23l3.5 1.5M25 23l-3.5 1.5" stroke="#08060a" stroke-width="2.4" stroke-linecap="square"/></svg>',
  any: '<svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="13" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M20 7a13 13 0 0 1 0 26z" fill="currentColor"/><circle cx="20" cy="20" r="3" fill="currentColor"/></svg>',
};
const SETUPS = { 5: [3, 0, 1], 6: [3, 1, 1], 7: [5, 0, 1], 8: [5, 1, 1], 9: [5, 2, 1], 10: [7, 0, 2], 11: [7, 1, 2], 12: [7, 2, 2], 13: [9, 0, 3], 14: [9, 1, 3], 15: [9, 2, 3] };
const TEAM_TEXT = {
  good: ['Good', 'Find the Demon'], evil: ['Evil', 'Deceive the town'], any: ['Either', 'Let fate decide'],
};
const EFFORT_TEXT = {
  low: 'Quick: the fastest turns', medium: 'Balanced: slower turns',
  high: 'Full, as in the benchmark: slow (a day can take an hour)',
};
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)');

const TID = (location.pathname.match(/^\/t\/([\w-]+)/) || [])[1] || null;  // this table (none: the home page)
const TOKEN_KEY = `ct.token.${TID}`;
let token = TID ? store.get(TOKEN_KEY) : null;
const setToken = (t) => { token = t; store.set(TOKEN_KEY, t); };
let hostKey = null;
let sound = store.get('ct.sound') !== 'off';
let models = {};          // id -> display name (from the lobby)

async function api(path, body) {
  const opts = body === undefined ? {} : { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } };
  opts.headers = { ...(opts.headers || {}), 'X-Token': token || '' };
  const r = await fetch(path.startsWith('/') ? path : `/api/t/${TID}/${path}`, opts);
  const ct = r.headers.get('Content-Type') || '';
  const data = ct.includes('json') ? await r.json() : await r.text();
  if (!r.ok) { const e = new Error((data && data.error) || `HTTP ${r.status}`); e.status = r.status; throw e; }
  return data;
}

function show(screen) {
  $('lobby').hidden = screen !== 'lobby';
  $('table').hidden = screen !== 'table';
}

/** A press that does work: the button shows it is busy until the work is done (and can't be pressed twice). */
async function busy(btn, work) {
  if (!btn || btn.dataset.busy) return;
  btn.dataset.busy = '1'; btn.classList.add('busy'); btn.setAttribute('aria-busy', 'true');
  try { await work(); } finally { delete btn.dataset.busy; btn.classList.remove('busy'); btn.removeAttribute('aria-busy'); }
}

// ================================================================== lobby
let configInFlight = 0;  // config saves in flight (table size changes are shown before the server confirms)
let lobbyTimer = null, lobbyState = null, joinTeam = 'good';

function allegiance(box, current, onPick) {
  box.innerHTML = ['good', 'evil', 'any'].map((t) => `<button type="button" class="team-tile ${t}${t === current ? ' on' : ''}" data-team="${t}" aria-pressed="${t === current}">
    ${ICON[t]}<b>${TEAM_TEXT[t][0]}</b><small>${TEAM_TEXT[t][1]}</small></button>`).join('');
  box.querySelectorAll('button').forEach((b) => b.onclick = () => {
    box.querySelectorAll('button').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', x === b); });
    onPick(b.dataset.team);
  });
}

async function pollLobby() {
  clearTimeout(lobbyTimer);
  try {
    const L = await api('lobby');
    if (configInFlight && lobbyState) L.config.players = lobbyState.config.players;  // keep the host's click while its save is in flight
    lobbyState = L;
    L.models.forEach((m) => { models[m.id] = m.name; });
    if (token && !L.me) setToken(null);
    if (L.me && hostKey && !L.me.host) {
      try { await api('host', { key: hostKey }); } catch { /* not valid */ }
      hostKey = null; history.replaceState(null, '', location.pathname);
      return pollLobby();
    }
    if ((L.status === 'playing' || L.status === 'over') && L.me && L.me.seated) return enterTable();
    renderLobby(L);
  } catch (e) {
    if (e.status === 404) { show('lobby'); screen('gone'); return; }
    /* server restarting: keep trying */
  }
  lobbyTimer = setTimeout(pollLobby, 1500);
}

const SCREENS = ['home', 'gone', 'join', 'gather', 'busy', 'paused', 'mine'];
function screen(...on) { SCREENS.forEach((id) => { $(id).hidden = !on.includes(id); }); }

function renderLobby(L) {
  show('lobby');
  const joined = !!L.me, inGame = joined && L.me.in_game;
  const busyGame = joined && (L.status === 'playing' || L.status === 'paused') && !inGame;
  const paused = joined && L.status === 'paused' && inGame;
  screen(...(!joined ? ['join'] : busyGame ? ['busy', 'mine'] : paused ? ['paused', 'mine'] : ['gather', 'mine']));
  if (!joined) {
    if (!$('join-team').childElementCount) allegiance($('join-team'), joinTeam, (t) => { joinTeam = t; });
    return;
  }
  const link = L.links && L.links.friends;
  $('share').hidden = !link;
  if (link) $('share-url').textContent = link;
  $('mine-url').textContent = `${link || location.origin + location.pathname}#me=${token}`;
  if (paused) {
    $('paused-text').textContent = L.error || 'The game is paused.';
    $('paused-host').hidden = !L.me.host;
    return;
  }
  $('people').innerHTML = L.people.map((p) => `<li${p.you ? ' class="you"' : ''}><span class="mini-token">${esc(p.name[0] || '?')}</span>
    <span class="who">${esc(p.name)}${p.you ? ' <em>you</em>' : ''}</span>${p.host ? '<span class="plate gold">host</span>' : ''}<i class="online${p.online ? ' on' : ''}" title="${p.online ? 'here' : 'away'}" aria-label="${p.online ? 'here' : 'away'}"></i>
    ${L.me.host && !p.you ? `<button class="kick" data-t="${esc(p.id)}" title="Remove ${esc(p.name)}" aria-label="Remove ${esc(p.name)}">&times;</button>` : ''}</li>`).join('');
  $('people').querySelectorAll('.kick').forEach((b) => b.onclick = () => api('kick', { target: b.dataset.t }).then(pollLobby));
  const box = $('my-team');
  if (box.dataset.team !== L.me.team) {
    box.dataset.team = L.me.team;
    allegiance(box, L.me.team, (t) => { box.dataset.team = t; api('me', { team: t }).then(pollLobby).catch(() => {}); });
  }

  const c = L.config, n = c.players, [tf, os, mn] = SETUPS[n];
  $('settings').classList.toggle('readonly', !L.me.host);
  $('size-n').textContent = n;
  $('size-minus').disabled = !L.me.host || n <= (L.sizes || [10])[0];
  $('size-plus').disabled = !L.me.host || n >= (L.sizes || [12]).slice(-1)[0];
  $('composition').innerHTML = '<i class="tf"></i>'.repeat(tf) + '<i class="os"></i>'.repeat(os) + '<i class="mn"></i>'.repeat(mn) + '<i class="dm"></i>';
  const humans = L.people.length;
  $('comp-text').innerHTML = `<span class="good">${tf} Townsfolk</span> &middot; <span class="good">${os} Outsider${os === 1 ? '' : 's'}</span> &middot; <span class="evil">${mn} Minion${mn === 1 ? '' : 's'}</span> &middot; <span class="evil">1 Demon</span><br>
    <em>${humans} ${humans === 1 ? 'human' : 'humans'}, ${Math.max(0, n - humans)} AI players</em>`;
  for (const [id, key] of [['good-model', 'good_model'], ['evil-model', 'evil_model']]) {
    const sel = $(id);
    sel.disabled = !L.me.host;
    const sig = c[key] + '|' + L.models.map((m) => +m.ready).join('') + L.keys.join();
    if (sel.dataset.v !== sig || !sel.options.length) {
      sel.innerHTML = L.models.map((m) => `<option value="${esc(m.id)}"${m.ready ? '' : ' disabled'}>${esc(m.name)}${m.elo ? ` · ${m.elo}` : ''}${m.id === 'random' ? '' : m.ready ? (m.free && !L.keys.includes(m.provider) ? ' · free' : ' · your key') : ' · needs your key'}</option>`).join('');
      if (!L.models.some((m) => m.id === c[key])) sel.insertAdjacentHTML('beforeend', `<option value="${esc(c[key])}">${esc(c[key])}</option>`);
      sel.value = c[key]; sel.dataset.v = sig;
    }
  }
  const tm = $('timer');
  tm.disabled = !L.me.host;
  if (tm.dataset.v !== String(c.timer) || !tm.options.length) {
    tm.innerHTML = L.timers.map((t) => `<option value="${t}">${t ? (t < 120 ? `${t} seconds` : `${t / 60} minutes`) : 'No limit'}</option>`).join('');
    tm.value = c.timer; tm.dataset.v = String(c.timer);
  }
  const ef = $('effort');
  ef.disabled = !L.me.host;
  const efforts = L.efforts || [];
  if (ef.dataset.v !== c.effort + efforts.join() || !ef.options.length) {
    ef.innerHTML = efforts.map((e) => `<option value="${esc(e)}">${esc(EFFORT_TEXT[e] || e)}</option>`).join('');
    ef.value = c.effort; ef.dataset.v = c.effort + efforts.join();
  }
  const cost = (id) => (L.models.find((m) => m.id === id) || {}).seat_cost;
  const evilSeats = mn + 1, goodSeats = n - evilSeats, ai = Math.max(0, n - humans) / n;
  const cg = cost(c.good_model), ce = cost(c.evil_model);
  const est = cg == null || ce == null ? null : Math.max(0, (goodSeats * cg + evilSeats * ce) * ai);
  $('estimate').innerHTML = est == null ? '' : (L.paid_by === 'house' ? `<b>Free</b>: the AI players are on Clocktower Bench (up to $${L.caps.game} a game). `
    : L.paid_by === 'player' ? `On your key: roughly <b>$${est.toFixed(2)}</b> of API calls per game, from past games. ` : '')
    + 'Ratings are the 2026 study\'s Elo, measured at full thinking.';
  $('byo').hidden = !L.me.host;
  $('byo-cap').textContent = `$${L.caps.byo_game}`;
  $('byo-have').textContent = L.keys.length ? `Using your ${L.keys.map((k) => (k === 'openai' ? 'OpenAI' : 'Anthropic')).join(' and ')} key for this table.` : '';
  $('start').hidden = !L.me.host;
  $('start').disabled = !!L.problem;
  $('start-err').textContent = L.me.host ? (L.problem || L.error || '') : '';
  $('host-note').textContent = L.me.host ? '' : 'The host sets the table and rings the bell.';
  $('claim').hidden = L.me.host;
  if (L.status === 'playing' && L.me.in_game) {
    $('start').hidden = false; $('start').disabled = true; $('start').textContent = 'Dealing the characters…';
  } else $('start').textContent = 'Ring the bell';
}

function wireLobby() {
  $('join-go').onclick = () => busy($('join-go'), async () => {
    $('join-err').textContent = '';
    try {
      const r = await api('join', { name: $('join-name').value, team: joinTeam, host: hostKey });
      setToken(r.token);
      if (hostKey) { hostKey = null; history.replaceState(null, '', location.pathname); }
      await pollLobby();
    } catch (e) { $('join-err').textContent = e.message; $('join-name').focus(); }
  });
  $('join-name').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('join-go').click(); });
  const set = (cfg) => { configInFlight++; return api('config', cfg).then(pollLobby).catch((e) => { $('start-err').textContent = e.message; }).finally(() => { configInFlight--; }); };
  const sizes = () => lobbyState.sizes || [10, 11, 12];
  // The table size updates on screen at once; the server confirms it (or the next poll reverts it).
  const bump = (d) => {
    const s = sizes(), n = Math.max(s[0], Math.min(s[s.length - 1], lobbyState.config.players + d));
    if (n === lobbyState.config.players) return;
    lobbyState.config.players = n; renderLobby(lobbyState); set({ players: n });
  };
  $('size-minus').onclick = () => bump(-1);
  $('size-plus').onclick = () => bump(+1);
  $('good-model').onchange = (e) => set({ good_model: e.target.value });
  $('evil-model').onchange = (e) => set({ evil_model: e.target.value });
  $('timer').onchange = (e) => set({ timer: +e.target.value });
  $('effort').onchange = (e) => set({ effort: e.target.value });
  copyButton('share-copy', 'share-url');
  copyButton('mine-copy', 'mine-url');
  $('claim-go').onclick = () => api('host', {}).then(pollLobby).catch(() => {});
  $('start').onclick = () => busy($('start'), async () => {
    unlockAudio();
    try { await api('start', {}); await pollLobby(); } catch (e) { $('start-err').textContent = e.message; }
  });
  const saveKey = async (prov, input, err) => {
    const key = $(input).value.trim();
    $(err).textContent = '';
    try { await api('key', { provider: $(prov).value, key }); $(input).value = ''; pollLobby(); } catch (e) { $(err).textContent = e.message; }
  };
  $('byo-save').onclick = () => busy($('byo-save'), () => saveKey('byo-provider', 'byo-key', 'start-err'));
  $('resume-key-save').onclick = () => busy($('resume-key-save'), () => saveKey('resume-provider', 'resume-key', 'paused-err'));
  $('resume-go').onclick = () => busy($('resume-go'), async () => {
    try { await api('resume', {}); await pollLobby(); } catch (e) { $('paused-err').textContent = e.message; }
  });
  $('paused-end').onclick = async () => {
    if (!confirm('End the game for everyone?')) return;
    try { await api('end', {}); pollLobby(); } catch (e) { $('paused-err').textContent = e.message; }
  };
}

function copyButton(btn, from) {
  $(btn).onclick = async () => {
    const text = $(from).textContent;
    try { await navigator.clipboard.writeText(text); } catch {
      const r = document.createRange(); r.selectNodeContents($(from));
      const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r);
      try { document.execCommand('copy'); } catch { /* selected for the user at least */ }
    }
    $(btn).textContent = 'Copied'; $(btn).classList.add('done');
    setTimeout(() => { $(btn).textContent = 'Copy'; $(btn).classList.remove('done'); }, 1500);
  };
}

// ================================================================== the home page
async function home() {
  show('lobby'); screen('home');
  $('new-table').onclick = () => busy($('new-table'), async () => {
    $('new-err').textContent = '';
    try {
      const r = await api('/api/new', {});
      location.href = `/t/${encodeURIComponent(r.table)}#host=${encodeURIComponent(r.host_key)}`;
    } catch (e) { $('new-err').textContent = e.message; }
  });
  try {
    const I = await api('/api/info');
    const f = I.free;
    $('free-note').innerHTML = (f.models.length
      ? (f.open ? `Free games use <b>${f.models.map(esc).join(', ')}</b> for the AI players, paid by Clocktower Bench ($${f.left_today.toFixed(0)} of ${f.budget_period === 'month' ? "this month's" : "today's"} $${f.daily_cap} left). `
        : f.budget_period === 'month' ? `This month's free AI budget is used up (it resets on the 1st). `
        : `Today's free AI budget is used up (it resets at midnight ${esc(f.budget_timezone || 'UTC')}). `) : '')
      + 'Practice bots are always free, and a host can bring an Anthropic or OpenAI key to play any model.'
      + (I.games >= I.max_games ? ' <b>Every game slot is busy right now.</b>' : '');
  } catch { /* the note is optional */ }
}

// ================================================================== the table
const T = {};
function resetTable(game) {
  Object.assign(T, {
    game, since: 0, players: [], me: null, pending: null, sent: null, over: false, reveal: null, revealShown: false,
    filter: 'all', who: null, head: '', day: 0, stage: '', nominee: null, yes: new Set(), block: null, tie: false,
    speaking: null, wh: {}, ballot: null, form: null, deadline: null, alertedTurn: null, did: '', needed: null,
    progress: null, townSig: '', whyOpen: false,
  });
  $('feed').innerHTML = '';
  $('reveal').hidden = true;
}

let tableTimer = null;
function enterTable() {
  clearTimeout(lobbyTimer);
  show('table');
  pollState();
}

async function pollState() {
  clearTimeout(tableTimer);
  let S;
  const asked = T.since || 0;
  try {
    S = await api('state?since=' + asked);
  } catch (e) {
    if (/Unknown player/.test(e.message) || e.status === 404) { if (e.status !== 404) setToken(null); return pollLobby(); }
    tableTimer = setTimeout(pollState, 2000);
    return;
  }
  if (!S.seated) {
    if (S.status === 'playing') { tableTimer = setTimeout(pollState, 1000); return; }
    return pollLobby();
  }
  if (S.game !== T.game || (T.run != null && S.run !== T.run)) {  // a new game, or the server restarted and
    resetTable(S.game);                                            // the game replays from its last dusk
    T.run = S.run;
    if (asked) { tableTimer = setTimeout(pollState, 0); return; }  // fetch it all again from the start
  }
  T.run = S.run;
  T.since = S.next;
  T.players = S.players; T.me = S.me; T.over = S.over; T.reveal = S.reveal; T.spent = S.spent; T.host = S.host;
  T.progress = S.progress || null;
  const feed = $('feed'), stick = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 160;
  const first = !asked;
  S.events.forEach((ev) => addEvent(ev, first));
  const prevTurn = T.pending && T.pending.turn;
  T.pending = S.pending;
  const myTurn = S.pending && S.pending.turn !== prevTurn;
  if (S.events.length || myTurn) {
    if (stick || myTurn) { feed.scrollTop = feed.scrollHeight; $('jump').hidden = true; }
    else if (S.events.length) $('jump').hidden = false;
  }
  if ((S.pending && S.pending.turn) !== prevTurn) { T.form = null; renderDock(); }
  else if (!S.pending && waitSig() !== T.waitSig) renderDock();   // idle: keep the waiting line in step with the phase
  else tickDock();
  paintTally();
  if (S.pending && T.sent !== S.pending.turn && T.alertedTurn !== S.pending.turn) { T.alertedTurn = S.pending.turn; alertTurn(); }
  if (!S.pending || T.sent === S.pending.turn) document.title = 'Clocktower';
  renderBar(); renderPhase(); renderTown(); renderBanner();
  if (S.over && S.reveal && !T.revealShown) { T.revealShown = true; renderReveal(); }
  tableTimer = setTimeout(pollState, S.over ? 3000 : 900);
}

// ---------------------------------------------------------------- derived table state
function processEvent(ev) {
  const d = ev.data;
  switch (ev.kind) {
    case 'header':
      T.head = d.text;
      if (/^Night/.test(d.text)) { T.stage = 'night'; T.nominee = null; T.yes = new Set(); T.block = null; T.tie = false; }
      else if (/^Day \d+$/.test(d.text)) { T.stage = 'dawn'; T.wh = {}; }
      else if (/private time/.test(d.text)) T.stage = 'private';
      else if (/town square/.test(d.text)) T.stage = 'public';
      T.day = ev.day; break;
    case 'nominations_open': T.stage = 'nominations'; T.head = `Day ${ev.day} · nominations`; break;
    case 'nomination': T.nominee = d.nominee; T.yes = new Set(); T.needed = null; break;
    case 'vote': if (d.yes) T.yes.add(d.voter); break;
    case 'vote_result':
      if (d.outcome === 'block') { T.block = { name: d.nominee, votes: d.votes }; T.tie = false; }
      else if (d.outcome === 'tie') { T.block = null; T.tie = true; }
      T.nominee = null; T.yes = new Set(); T.needed = null; break;
    case 'execution': case 'no_execution': T.block = null; break;
    case 'say': case 'defense': T.speaking = { name: d.speaker || d.nominee, at: Date.now() }; break;
    case 'game_over': T.stage = 'over'; break;
    case 'whisper': {
      const me = T.me && T.me.seat;
      const others = [d.from, ...d.to].filter((x) => x !== me);
      others.forEach((x) => { T.wh[x] = (T.wh[x] || 0) + 1; });
      break;
    }
  }
}

// ---------------------------------------------------------------- the phase band: when we are, and whose move it is
const TRACK = [['night', 'Night'], ...[1, 2, 3, 4, 5, 6].map((i) => ['private', `Whispers ${i}`]), ...[1, 2, 3].map((i) => ['public', `Town square ${i}`]), ['noms', 'Nominations']];

function phaseInfo() {
  const h = T.head || '';
  const m = h.match(/private time (\d+)/), q = h.match(/town square (\d+)/), day = T.day || (h.match(/\d+/) || [0])[0];
  if (T.over || T.stage === 'over') return { key: 'over', title: 'Game over', sub: T.reveal && T.reveal.winner ? `${T.reveal.winner === 'good' ? 'Good' : 'Evil'} wins` : '', pos: -1, icon: ICON.bell };
  if (T.stage === 'night') return { key: 'night', title: h || 'Night', sub: 'The town sleeps', pos: 0, icon: ICON.moon };
  if (m) return { key: 'private', title: `Day ${day}`, sub: `Whispers ${m[1]} of 6`, pos: +m[1], icon: ICON.quill };
  if (q) return { key: 'public', title: `Day ${day}`, sub: `Town square ${q[1]} of 3`, pos: 6 + +q[1], icon: ICON.bell };
  if (T.stage === 'nominations') {
    const sub = T.nominee ? `On trial: ${T.nominee}` : T.block ? `${T.block.name} on the block · ${T.block.votes}` : 'Nominations';
    return { key: T.nominee ? 'vote' : 'noms', title: `Day ${day}`, sub, pos: 10, icon: T.nominee ? ICON.hand : ICON.arrow };
  }
  if (T.stage === 'dawn') return { key: 'dawn', title: `Day ${day}`, sub: 'Dawn', pos: 0.5, icon: ICON.sun };
  return { key: 'dawn', title: h || 'The town gathers', sub: '', pos: -1, icon: ICON.sun };
}

function turnState() {
  if (T.over) return 'over';
  if (T.pending && T.sent !== T.pending.turn) return 'yours';
  if (T.pending && T.sent === T.pending.turn) return 'sealed';
  return 'wait';
}

function renderPhase() {
  const P = phaseInfo(), box = $('phase'), ts = turnState();
  document.body.dataset.phase = P.key;
  const track = TRACK.map(([k, label], i) => `<li class="${k}${i < P.pos ? ' done' : ''}${Math.floor(P.pos) === i ? ' now' : ''}" title="${label}"></li>`).join('');
  const turn = ts === 'yours' ? `<span class="turnflag yours"><i class="dot"></i>Your turn${timerHTML()}</span>`
    : ts === 'sealed' ? `<span class="turnflag sealed">${ICON.seal}Sent</span>`
      : ts === 'over' ? '' : `<span class="turnflag wait">${ICON.glass}Waiting</span>`;
  const sig = P.key + P.title + P.sub + ts + P.pos;
  if (box.dataset.sig === sig) { tickDock(); return; }
  box.dataset.sig = sig;
  box.className = 'phase ' + P.key;
  box.innerHTML = `<div class="ph-text">${P.icon}<b class="ph-title">${esc(P.title)}</b><span class="ph-sub">${esc(P.sub)}</span></div>
    ${P.pos >= 0 ? `<ol class="track" aria-hidden="true">${track}</ol>` : ''}${turn}`;
}

// ---------------------------------------------------------------- the circle and the strip
function seatEl(p) {
  const me = T.me, isMe = me && p.name === me.seat;
  const known = me && me.known[p.name];
  const el = document.createElement('button');
  el.type = 'button';
  el.className = 'seat' + (isMe ? ' me' : '') + (p.alive ? '' : ' dead');
  el.dataset.name = p.name;
  let face = `<span class="initial">${esc(p.name[0])}</span>`, ring = '', label = p.name;
  if (isMe) { ring = me.evil ? ' evil' : ' good'; label += `, you, the ${me.character}`; }
  else if (known) { face = `<span class="initial">${esc(p.name[0])}</span><span class="role">${known}</span>`; ring = ' evil'; label += `, your ${known}`; }
  let badges = '';
  if (T.nominee && T.yes.has(p.name)) { badges += `<span class="badge hand" title="Hand raised">${ICON.hand}</span>`; label += ', hand raised'; }
  if (!p.alive && p.ghost) badges += '<span class="badge gv" title="Ghost vote unused"></span>';
  if (T.wh[p.name]) badges += `<span class="badge wh" title="Whispers with you today">${T.wh[p.name]}</span>`;
  if (T.block && T.block.name === p.name) { badges += `<span class="badge blk" title="On the block">${T.block.votes}</span>`; label += `, on the block with ${T.block.votes}`; }
  if (!p.alive) label += ', dead';
  el.innerHTML = `<span class="token${ring}">${face}${p.alive ? '' : '<span class="shroud"></span>'}${badges}</span><span class="name">${esc(isMe ? 'You' : p.name)}</span>`;
  if (T.speaking && T.speaking.name === p.name && Date.now() - T.speaking.at < 4000) el.classList.add('speaking');
  if (T.nominee === p.name) el.classList.add('nominee');
  // A seat is always the chronicle's filter, your turn or not (who to whisper to, nominate or choose is picked
  // in the dock). The seats you have picked there are ringed in gold here, so the choice shows on the circle.
  const on = T.who === p.name;
  if (on) el.classList.add('filtered');
  el.setAttribute('aria-pressed', on);
  const f = T.pending && T.sent !== T.pending.turn ? T.form : null;
  if (f && (f.picks.includes(p.name) || f.shot === p.name)) { el.classList.add('picked'); label += ', chosen for your move'; }
  const what = on ? 'Showing only what involves them: press to show everything' : isMe ? 'Show only what involves you' : `Show only what involves ${p.name}`;
  el.setAttribute('aria-label', `${label}. ${what}`);
  el.title = on ? 'Show everything again' : isMe ? 'Show only what involves you' : `Show only what involves ${p.name}`;
  el.onclick = () => seatClicked(p.name);
  return el;
}

function seatClicked(name) {
  T.who = T.who === name ? null : name;
  renderFilters(); applyFilter(); renderTown();
  const feed = $('feed');
  feed.scrollTop = feed.scrollHeight; $('jump').hidden = true;   // the latest of what is now shown
}

function dial() {
  // 12 ticks: six private beats, three town-square beats, nominations, and two for the night.
  let pos = 0;
  const m = T.head.match(/private time (\d+)/), q = T.head.match(/town square (\d+)/);
  if (T.stage === 'night') pos = 10.5;
  else if (m) pos = +m[1] - 1;
  else if (q) pos = 5 + +q[1];
  else if (T.stage === 'nominations') pos = 9;
  else pos = -0.5;
  let ticks = '';
  for (let i = 0; i < 12; i++) {
    const a = (i * 30 - 90) * Math.PI / 180, r1 = 39, r2 = i % 3 === 0 ? 31 : 34;
    const k = i < 6 ? 'private' : i < 9 ? 'public' : i < 10 ? 'noms' : 'night';
    ticks += `<line class="tick ${k}${i <= pos && T.stage !== 'night' ? ' done' : ''}" x1="${50 + r1 * Math.cos(a)}" y1="${50 + r1 * Math.sin(a)}" x2="${50 + r2 * Math.cos(a)}" y2="${50 + r2 * Math.sin(a)}"/>`;
  }
  return `<svg class="dial" viewBox="0 0 100 100" aria-hidden="true"><circle class="rim" cx="50" cy="50" r="47"/><circle class="face" cx="50" cy="50" r="44"/>
    <path class="night-arc" d="M ${50 + 44 * Math.cos(-150 * Math.PI / 180)} ${50 + 44 * Math.sin(-150 * Math.PI / 180)} A 44 44 0 0 1 50 6"/>
    ${ticks}<line class="hand" x1="50" y1="50" x2="50" y2="20" transform="rotate(${pos * 30} 50 50)"/><circle class="hub" cx="50" cy="50" r="3.5"/></svg>`;
}

function renderCircle(box) {
  const ps = T.players, n = ps.length || 1;
  box.innerHTML = '<div class="ring"></div>';
  const size = box.clientWidth || 600;
  // the token size follows the space between neighbours, so names never collide
  const r0 = size * 0.40, t = Math.max(30, Math.min(84, (2 * Math.PI * r0 / n) * 0.54, size * 0.15));
  box.style.setProperty('--t', t + 'px');
  const R = 50 - (t * 0.75 / size) * 100 - 2;
  ps.forEach((p, i) => {
    const a = (i / n) * 2 * Math.PI - Math.PI / 2;
    const el = seatEl(p);
    el.style.left = `${50 + R * Math.cos(a)}%`;
    el.style.top = `${50 + R * Math.sin(a)}%`;
    box.appendChild(el);
  });
  const P = phaseInfo();
  const centre = document.createElement('div');
  centre.className = 'centre';
  const blk = T.nominee ? `<b>${esc(T.nominee)}</b> is nominated · ${T.yes.size} hand${T.yes.size === 1 ? '' : 's'}` : T.block ? `<b>${esc(T.block.name)}</b> is on the block (${T.block.votes})` : T.tie ? 'A tie: nobody on the block' : '';
  centre.innerHTML = `${dial()}<div class="ph">${esc(P.title)}</div><div class="ph-sub">${esc(P.sub)}</div><div class="block">${blk}</div>`;
  box.appendChild(centre);
}

function renderTown() {
  const wide = getComputedStyle($('town')).display !== 'none', strip = $('strip');
  const narrow = getComputedStyle(strip).display !== 'none', sheet = !$('sheet').hidden && $('sheet').dataset.kind === 'town';
  const f = T.pending && T.sent !== T.pending.turn ? T.form : null;
  const sig = JSON.stringify([T.players, T.me, T.who, f && [f.picks, f.shot], T.nominee, [...T.yes], T.block, T.tie, T.wh, T.head, T.stage, T.over,
    T.speaking && Date.now() - T.speaking.at < 4000 && T.speaking.name, wide, narrow, sheet, wide && $('circle').clientWidth]);
  if (sig === T.townSig) return;
  T.townSig = sig;
  // keep the keyboard's place: the seats are rebuilt, so focus goes back to the same player's seat
  const at = document.activeElement, name = at && at.classList.contains('seat') ? at.dataset.name : null, home = name && at.parentElement;
  if (wide) renderCircle($('circle'));
  if (narrow) {
    const n = T.players.length;
    strip.style.setProperty('--cols', n <= 6 ? n : Math.ceil(n / 2));
    strip.innerHTML = ''; T.players.forEach((p) => strip.appendChild(seatEl(p)));
  }
  if (sheet) renderCircle($('sheet-body').querySelector('.circle'));
  if (name && home && document.contains(home)) home.querySelector(`.seat[data-name="${CSS.escape(name)}"]`)?.focus({ preventScroll: true });
}

function renderBar() {
  const me = T.me;
  if (!me) return;
  $('me-token').textContent = me.seat[0];
  $('me-token').className = 'mini-token ' + (me.evil ? 'evil' : 'good') + (me.alive ? '' : ' dead');
  $('me-name').textContent = me.seat;
  $('me-char').textContent = me.character + (me.alive ? '' : ' · dead');
  $('me-char').className = me.evil ? 'evil' : 'good';
  $('me-chip').setAttribute('aria-label', `You are ${me.seat}, the ${me.character}, ${me.evil ? 'evil' : 'good'}${me.alive ? '' : ', dead'}. Show your character.`);
}

function renderBanner() {
  const me = T.me, b = $('role-banner');
  if (!me || T.over || store.get(`ct.seen.${T.game}`)) { b.hidden = true; return; }
  if (!b.hidden && b.dataset.k === me.character) return;
  b.dataset.k = me.character;
  const team = me.evil ? 'evil' : 'good';
  b.className = 'rcard ' + team;
  b.innerHTML = `<span class="token big ${team}"><span class="initial">${esc(me.character[0])}</span></span>
    <div class="rc-body"><p class="eyebrow">You are ${esc(me.seat)}</p><h3>The ${esc(me.character)}</h3><span class="plate ${team}">${team} team</span>
    <p>${esc(me.ability)}</p><p class="fine">${me.evil ? 'Evil wins when only two players are left alive. Keep your team hidden.' : 'Good wins by executing the Demon. Find it.'}
    Tap your name at the top any time to see this again.</p></div><button class="ghost small" id="banner-ok">Got it</button>`;
  b.hidden = false;
  $('banner-ok').onclick = () => { store.set(`ct.seen.${T.game}`, '1'); b.hidden = true; };
}

// ---------------------------------------------------------------- the chronicle
const CATS = [['all', 'All'], ['town', 'Town square'], ['whisper', 'Whispers'], ['st', 'Storyteller']];

function renderFilters() {
  const f = $('filters');
  // the player filter comes first, so on a phone it is never scrolled out of sight
  f.innerHTML = (T.who ? `<button class="chip who" data-who="1" aria-label="Showing only what involves ${esc(T.who)}. Show everyone again">Only ${esc(T.who === (T.me && T.me.seat) ? 'you' : T.who)} &times;</button>` : '')
    + CATS.map(([k, label]) => `<button class="chip${T.filter === k ? ' on' : ''}" data-f="${k}" aria-pressed="${T.filter === k}">${label}</button>`).join('')
    + (T.who ? '' : '<span class="chip-hint">Tap a player to see only them</span>');
  f.querySelectorAll('[data-f]').forEach((b) => b.onclick = () => { T.filter = b.dataset.f; renderFilters(); applyFilter(); });
  const w = f.querySelector('[data-who]');
  if (w) w.onclick = () => { T.who = null; renderFilters(); applyFilter(); renderTown(); };
  f.scrollLeft = 0;
}

function matches(el) {
  const cat = el.dataset.cat;
  if (cat === 'divider') return !T.who;
  if (T.filter !== 'all' && cat !== T.filter) return false;
  if (T.who && !(el.dataset.who || '').split(' ').includes(T.who)) return false;
  return true;
}
function applyFilter() { for (const el of $('feed').children) el.hidden = !matches(el); }

function tokenHTML(name, extra = '') {
  const me = T.me, known = me && me.known[name];
  const cls = me && name === me.seat ? (me.evil ? ' evil' : ' good') : known ? ' evil' : '';
  const dead = T.players.find((p) => p.name === name && !p.alive) ? ' dead' : '';
  return `<span class="mini-token${cls}${dead}${extra}" aria-hidden="true">${esc(name[0])}</span>`;
}

function stripPrompt(p) {
  return String(p || '')
    .replace(/ Put your choice in `targets`\./, '').replace(/ \(`targets`\)/, '')
    .replace(/Set `vote` to true or false; `say` may hold a very short remark \(optional; don't just restate your vote\)\./, 'You may add a very short remark.')
    .replace(/Set `vote` to true \(yes\) or false \(no\)/, 'Vote yes or no')
    .replace(/ \(set `nominate`; your `say` is the accusation\)/, ' (your words are the accusation)')
    .replace(/ in `say`/, '').replace(/`/g, '');
}

const SECTION = { night: 'night', private: 'private', town: 'public', nominations: 'noms' };

function addEvent(ev, quiet) {
  processEvent(ev);
  const d = ev.data, me = T.me ? T.me.seat : '';
  const feed = $('feed');
  let el = document.createElement('div'), cat = 'town', who = [];
  el.className = 'ev';
  const nameTag = (n) => esc(n === me ? 'You' : n);
  switch (ev.kind) {
    case 'header': {
      cat = 'divider';
      const big = /^(Night|Day) \d+$/.test(d.text), night = /^Night/.test(d.text);
      const kind = night ? 'night' : /private/.test(d.text) ? 'private' : /town square/.test(d.text) ? 'public' : 'day';
      const icon = { night: ICON.moon, private: ICON.quill, public: ICON.bell, day: ICON.sun }[kind];
      const label = d.text.replace(/^Day \d+ · /, '').replace(/^private time (\d+)$/, 'Whispers $1 of 6').replace(/^town square (\d+)$/, 'Town square $1 of 3');
      el.className += ` divider ${kind}${big ? ' big' : ''}`;
      el.innerHTML = `<span class="rule"></span>${icon}<span class="lbl">${esc(label)}</span><span class="rule"></span>`;
      break;
    }
    case 'intro': {
      cat = 'st';
      const m = T.me || {};
      el.innerHTML = `<div class="rcard intro ${m.evil ? 'evil' : 'good'}"><span class="token ${m.evil ? 'evil' : 'good'}"><span class="initial">${esc((m.character || '?')[0])}</span></span>
        <div class="rc-body"><div class="h">${ICON.eye} The Storyteller shows you your character</div><p>${esc(d.text)}</p></div></div>`;
      break;
    }
    case 'info': {
      cat = 'st';
      const night = /^Night/.test(d.text);
      el.innerHTML = `<div class="st-note${night ? ' night' : ''}"><div class="h">${night ? ICON.moon : ICON.eye} The Storyteller, to you alone</div><p>${esc(d.text)}</p></div>`;
      break;
    }
    case 'notice': case 'text':
      cat = 'st'; el.innerHTML = `<div class="notice">${esc(d.text)}</div>`; break;
    case 'dawn':
      who = d.deaths;
      el.innerHTML = `<div class="dawn${d.deaths.length ? ' deaths' : ''}">${d.narration ? `<p class="narr">${esc(d.narration)}</p>` : ''}
        ${d.deaths.length ? `<p class="died">${ICON.skull}<span>Died in the night: <b>${d.deaths.map(esc).join(', ')}</b></span></p>` : '<p class="none">Nobody died in the night</p>'}</div>`;
      break;
    case 'say': {
      who = [d.speaker];
      const dead = T.players.find((p) => p.name === d.speaker && !p.alive);
      el.innerHTML = `<div class="say${d.speaker === me ? ' mine' : ''}${dead ? ' dead' : ''}">${tokenHTML(d.speaker)}
        <div class="body"><div class="who">${nameTag(d.speaker)}${dead ? ' <span class="tag">dead</span>' : ''}</div><div class="bubble">${esc(d.text)}</div></div></div>`;
      break;
    }
    case 'whisper': {
      cat = 'whisper'; who = [d.from, ...d.to];
      const to = d.to.map((x) => (x === me ? 'you' : esc(x))).join(' &amp; ');
      el.innerHTML = `<div class="say whisper${d.from === me ? ' mine' : ''}">${tokenHTML(d.from)}
        <div class="body"><div class="who">${ICON.lock}${d.from === me ? 'You' : esc(d.from)} <span class="to">whisper${d.from === me ? '' : 's'} to ${to}</span></div><div class="bubble">${esc(d.text)}</div></div></div>`;
      break;
    }
    case 'nominations_open':
      cat = 'divider'; el.className += ' divider noms'; el.innerHTML = `<span class="rule"></span>${ICON.arrow}<span class="lbl">Nominations open</span><span class="rule"></span>`; break;
    case 'nomination':
      who = [d.nominator, d.nominee]; T.ballot = null;
      el.innerHTML = `<div class="nomcard"><div class="h">${ICON.arrow}<span><b>${esc(d.nominator === me ? 'You' : d.nominator)}</b> nominate${d.nominator === me ? '' : 's'} <b>${esc(d.nominee === me ? 'you' : d.nominee)}</b></span></div>${d.text ? `<p>${esc(d.text)}</p>` : ''}</div>`;
      break;
    case 'defense':
      who = [d.nominee];
      el.innerHTML = `<div class="say defense${d.nominee === me ? ' mine' : ''}">${tokenHTML(d.nominee)}<div class="body"><div class="who">${nameTag(d.nominee)} <span class="tag">defense</span></div>
        <div class="bubble">${d.text ? esc(d.text) : '<em>says nothing in their defense</em>'}</div></div></div>`;
      break;
    case 'vote': {
      if (!T.ballot) {
        T.ballot = document.createElement('div');
        T.ballot.className = 'ev'; T.ballot.dataset.cat = 'town'; T.ballot.dataset.who = d.nominee;
        T.ballot.innerHTML = `<div class="ballot"><div class="h">${ICON.hand}<span>The vote on <b>${esc(d.nominee === me ? 'you' : d.nominee)}</b></span><span class="n">0</span></div><div class="votes"></div><div class="remarks"></div></div>`;
        feed.appendChild(T.ballot); T.ballot.hidden = !matches(T.ballot);
      }
      const b = T.ballot;
      b.dataset.who += ' ' + d.voter;
      b.querySelector('.votes').insertAdjacentHTML('beforeend', `<span class="v${d.yes ? ' yes' : ''}${d.ghost ? ' gv' : ''}" title="${esc(d.voter)}: ${d.yes ? 'yes' : 'no'}${d.ghost ? ' (ghost vote)' : ''}">${d.yes ? ICON.hand : ''}${esc(d.voter === me ? 'you' : d.voter)}</span>`);
      if (d.yes) { const n = b.querySelector('.h .n'); n.textContent = +n.textContent + 1; }
      if (d.text) b.querySelector('.remarks').insertAdjacentHTML('beforeend', `<div><b>${esc(d.voter)}</b> ${esc(d.text)}</div>`);
      b.hidden = !matches(b);
      return;
    }
    case 'vote_result': {
      const line = `<div class="res${d.outcome === 'block' ? ' block' : ''}"><b>${d.votes}</b> of ${d.needed} needed${d.outcome === 'block' ? ` · ${esc(d.nominee)} is about to be executed` : d.outcome === 'tie' ? ' · a tie: nobody is about to die' : ' · not enough'}</div>`;
      if (T.ballot) { T.ballot.querySelector('.ballot').insertAdjacentHTML('beforeend', line); T.ballot.querySelector('.ballot').classList.add('done', d.outcome); T.ballot = null; return; }
      who = [d.nominee]; el.innerHTML = `<div class="ballot done ${d.outcome}">${line}</div>`;
      break;
    }
    case 'execution':
      who = [d.player]; el.innerHTML = `<div class="doom">${ICON.skull}<span><b>${esc(d.player === me ? 'You are' : d.player + ' is')} executed</b>${d.died ? '' : ' (they were already dead)'}</span></div>`; break;
    case 'no_execution':
      el.innerHTML = '<div class="doom quiet"><span>Nobody is executed today</span></div>'; break;
    case 'virgin':
      who = [d.nominator, d.nominee]; el.innerHTML = `<div class="doom">${ICON.skull}<span><b>${esc(d.nominator)} is executed immediately!</b> The day ends.</span></div>`; break;
    case 'slayer':
      who = [d.shooter, d.target];
      el.innerHTML = `<div class="nomcard slay"><div class="h">${ICON.arrow}<span>The Slayer's shot</span></div><p>${esc(d.shooter)} claims the Slayer's power and shoots at ${esc(d.target)}. ${d.died ? `<b>${esc(d.target)} dies!</b>` : 'Nothing happens.'}</p></div>`;
      break;
    case 'game_over':
      el.innerHTML = `<div class="over-ev ${esc(d.winner)}"><span class="eyebrow">Game over</span><b>${d.winner === 'good' ? 'Good' : d.winner === 'evil' ? 'Evil' : esc(d.winner)} wins</b><em>${esc(d.reason)}</em></div>`; break;
    default:
      cat = 'st'; el.innerHTML = `<div class="notice">${esc(ev.text)}</div>`;
  }
  if (!quiet && !REDUCED.matches) el.classList.add('fresh');
  el.dataset.cat = cat;
  el.dataset.who = who.join(' ');
  el.hidden = !matches(el);
  feed.appendChild(el);
}

// ---------------------------------------------------------------- the dock
const words = (s) => (s.trim().match(/\S+/g) || []).length;

function newForm(p) {
  const others = T.players.map((x) => x.name).filter((x) => x !== T.me.seat);
  const f = { picks: [], text: '', shot: null, showShot: false, remark: false, err: '' };
  if (p.kind === 'night' || p.kind === 'ravenkeeper') Object.assign(f, { mode: 'night', pickable: p.options, max: p.n_targets });
  else if (p.kind === 'beat' && p.mode === 'private') Object.assign(f, { mode: 'whisper', pickable: others, max: 2 });
  else if (p.kind === 'nominate') Object.assign(f, { mode: 'nominate', pickable: p.options, max: 1 });
  else if (p.kind === 'vote') Object.assign(f, { mode: 'vote', pickable: null });
  else if (p.kind === 'defense') Object.assign(f, { mode: 'defense', pickable: null });
  else Object.assign(f, { mode: 'speak', pickable: null });
  return f;
}

function togglePick(name) {
  const f = T.form;
  if (!f) return;
  const i = f.picks.indexOf(name);
  if (i >= 0) f.picks.splice(i, 1);
  else { f.picks.push(name); if (f.picks.length > f.max) f.picks.shift(); }
  renderDock(); renderTown();
}

function timerHTML() {
  const p = T.pending;
  if (!p || !p.deadline || T.sent === p.turn) return '';
  const left = Math.max(0, Math.round(p.deadline - Date.now() / 1000));
  return `<span class="timer${left < 20 ? ' low' : ''}" data-timer>${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}</span>`;
}
function tickDock() { document.querySelectorAll('[data-timer]').forEach((t) => { t.outerHTML = timerHTML(); }); }
setInterval(tickDock, 1000);

const KIND = {
  night: 'Night · your ability', ravenkeeper: 'Ravenkeeper', whisper: 'Whisper', speak: 'Town square',
  comment: 'Before the vote', nominate: 'Nominations', defense: 'You stand accused', vote: 'The vote',
};

function headline(p, f) {
  const nominee = (p.options && p.options[0]) || T.nominee || '';
  const need = (p.prompt.match(/It takes (\d+) yes votes/) || [])[1];
  if (need) T.needed = +need;
  switch (p.kind === 'comment' ? 'comment' : f.mode) {
    case 'night': return p.kind === 'ravenkeeper' ? 'You died tonight. Choose a player to learn their character.' : `Choose ${f.max === 2 ? 'two players' : 'a player'}.`;
    case 'whisper': return 'Send a private whisper, or stay silent.';  // to whom: the "Whisper to" buttons in the dock
    case 'speak': return 'Speak to the whole town, or stay quiet.';
    case 'comment': return `Say something before the vote on ${esc(nominee)}, or stay quiet.`;
    case 'nominate': return 'Nominate a player for execution, or pass.';
    case 'defense': return 'Defend yourself to the whole town.';
    case 'vote': return `Execute <b>${esc(nominee)}</b>?${need ? ` <span class="need">${T.yes.size} of ${need} hands</span>` : ''}`;
    default: return '';
  }
}

function waitingText() {
  const dead = T.me && !T.me.alive;
  const base = { night: 'Night has fallen. The town sleeps…', private: 'Whispers pass between the others…', public: 'The town square is talking…',
    nominations: T.nominee ? `The town votes on ${esc(T.nominee)}…` : 'The town deliberates…', dawn: 'Dawn breaks…' }[T.stage] || 'The town deliberates…';
  return base + (dead ? ' <em>You are dead: you can still talk and whisper, and you have one ghost vote.</em>' : '');
}

function announce(text) { const a = $('announce'); if (a) { a.textContent = ''; setTimeout(() => { a.textContent = text; }, 30); } }

const waitSig = () => [T.stage, T.nominee, T.over, T.me && T.me.alive].join('|');

// ---------------------------------------------------------------- who the table is waiting on
// Turns are simultaneous within a group: the engine asks a few seats at once and shows what they said only
// when all of them have answered, then asks the next group. So while it is your turn nothing new can arrive,
// which looks like a frozen chat unless the page says so. The server sends counts only (never which seats).
const people = (n) => `${n} ${n === 1 ? 'player' : 'players'}`;

function tallyHTML() {
  const g = T.progress, ts = turnState();
  if (ts === 'over') return '';
  const mine = ts === 'yours', priv = T.pending ? T.pending.mode === 'private' : T.stage === 'private';
  if (!g) return mine ? '<p class="tally-line"><b>The table is waiting for you.</b></p>' : '';
  // right after you send, the server may still count you for one poll
  const others = Math.max(0, g.waiting - (g.you ? 1 : 0));
  const done = g.kind === 'nominate' ? 'have answered' : 'have had their turn';
  const count = g.of > 1 ? `<span class="tally-n" title="${g.done} of ${g.of} ${done} this round"><span class="pips" aria-hidden="true">${Array.from({ length: g.of }, (_, i) => `<i class="${i < g.done ? 'done' : i < g.done + g.waiting ? 'now' : ''}"></i>`).join('')}</span><span>${g.done} of ${g.of}<span class="sr-only"> ${done} this round</span></span></span>` : '';
  let who, then, why = '';
  if (mine) {
    who = `Waiting on you${others ? ` and ${others} other${others === 1 ? '' : 's'}` : ''}.`;
    then = 'Nothing new will arrive until you act.';
    if (g.groups) why = `Each round, players take their turns a few at a time. What your group ${priv ? 'whispers is delivered' : 'says is shown'} only once all of you have acted, and then the next group goes. So the chat is not stuck: it is waiting for you${others ? ` and ${others === 1 ? 'one other player' : `${others} others`}` : ''}. ${g.done} of ${g.of} players have had their turn this round.`;
    else if (g.kind === 'nominate') why = `Every living player who has not nominated today is asked at once, and the answers are shown together. ${g.done} of ${g.of} have answered.`;
    else if (g.kind === 'vote') { then = 'The vote goes on when you have voted.'; why = 'Votes are cast one at a time, clockwise from the nominee, each player seeing the hands already raised.'; }
  } else {
    if (!others) return '';
    who = `Waiting on ${people(others)}.`;
    then = g.kind === 'vote' ? 'Votes go one at a time, clockwise.' : g.kind === 'defense' ? '' : `${others === 1 ? 'Their' : 'Their'} ${g.groups ? (priv ? 'whispers' : 'words') : 'answers'} arrive together.`;
    if (g.groups) why = `Each round, players take their turns a few at a time. What a group ${priv ? 'whispers is delivered' : 'says is shown'} only once all of it has acted, so messages come in bursts. ${g.done} of ${g.of} players have had their turn this round.`;
    else if (g.kind === 'nominate') why = `Every living player who has not nominated today is asked at once, and the answers are shown together. ${g.done} of ${g.of} have answered.`;
  }
  return `<p class="tally-line"><span class="tally-who"><b>${who}</b> ${then}${why ? ` <button type="button" class="why" id="why" aria-expanded="${!!T.whyOpen}" aria-controls="tally-why">Why?</button>` : ''}</span>${count}</p>`
    + (why ? `<p class="tally-why" id="tally-why"${T.whyOpen ? '' : ' hidden'}>${why}</p>` : '');
}

function paintTally() {
  const el = $('tally');
  if (!el) return;
  const h = tallyHTML();
  if (el.dataset.h === h) return;
  const focused = document.activeElement && document.activeElement.id === 'why';
  el.dataset.h = h; el.innerHTML = h; el.hidden = !h;
  if (focused) $('why')?.focus();
  setDockHeight();
}
// "Why?" opens the longer explanation (one handler for the whole dock: the line is repainted every poll)
document.addEventListener('click', (e) => {
  if (!e.target.closest || !e.target.closest('#why')) return;
  T.whyOpen = !T.whyOpen; paintTally(); $('why')?.focus();
});
const tally = () => { const h = tallyHTML(); return `<div class="tally" id="tally" role="status" data-h="${esc(h)}"${h ? '' : ' hidden'}>${h}</div>`; };

function renderDock() {
  const dock = $('dock'), p = T.pending;
  dock.className = '';
  T.waitSig = waitSig();
  if (T.over) {
    dock.className = 'over';
    dock.innerHTML = `<div class="wait">${ICON.bell}<span>The game is over.</span><button class="primary small" id="see-reveal">Open the Grimoire</button></div>`;
    $('see-reveal').onclick = renderReveal;
    return setDockHeight();
  }
  if (!p) { dock.className = 'idle'; dock.innerHTML = `<div class="wait">${ICON.glass}<span>${waitingText()}</span></div>${tally()}`; return setDockHeight(); }
  if (T.sent === p.turn) {
    dock.className = 'idle sealed';
    dock.innerHTML = `<div class="wait">${ICON.seal}<span><b>${esc(T.did || 'Sent')}.</b> Waiting for the others…</span></div>${tally()}`;
    return setDockHeight();
  }
  const f = T.form || (T.form = newForm(p));
  const kindLabel = p.kind === 'comment' ? KIND.comment : p.kind === 'ravenkeeper' ? KIND.ravenkeeper : KIND[f.mode];
  dock.className = 'turn ' + (f.mode === 'whisper' ? 'private' : f.mode === 'night' ? 'night' : f.mode === 'vote' || f.mode === 'nominate' || f.mode === 'defense' ? 'blood' : 'public');
  const fold = (open) => `<button type="button" class="fold" id="fold" aria-expanded="${open}" aria-controls="dock-body" title="${open ? 'Fold your move away to read the chronicle' : 'Back to your move'}">${open ? 'Read first' : 'Your move'}<span aria-hidden="true">${open ? ' ▾' : ' ▴'}</span></button>`;
  if (f.min) {  // folded away, to read the chronicle (filtered by player or not) with the whole screen
    dock.className += ' min';
    dock.dataset.turn = p.turn;
    dock.innerHTML = `<div class="dock-body" id="dock-body"><div class="ask"><div class="what"><div class="kind"><span class="yt">Your turn</span>${kindLabel}</div></div>${timerHTML()}${fold(false)}</div>${tally()}</div>`;
    $('fold').onclick = () => { f.min = false; renderDock(); $('fold')?.focus(); };
    return setDockHeight();
  }
  let h = `<div class="ask"><div class="what"><div class="kind"><span class="yt">Your turn</span>${kindLabel}${fold(true)}</div>
    <div class="head">${headline(p, f)}</div><div class="prompt" role="button" tabindex="0" aria-expanded="${!!f.promptOpen}">${esc(stripPrompt(p.prompt))}</div></div>${timerHTML()}</div>${tally()}`;
  let foot = '';  // the action buttons: rendered outside the scrolling body so they are always in view
  const picks = (list, label, note = '') => `<div class="pick-label" id="pick-label">${label}${note ? ` <em>${note}</em>` : ''}</div><div class="picks" role="group" aria-labelledby="pick-label">${list.map((n) => {
    const dead = !T.players.find((x) => x.name === n)?.alive;
    const on = f.picks.includes(n);
    return `<button type="button" class="pick${on ? ' on' : ''}${dead ? ' dead' : ''}" data-pick="${esc(n)}" aria-pressed="${on}">${esc(n === T.me.seat ? 'yourself' : n)}</button>`;
  }).join('')}</div>`;
  const textarea = (ph, limit, rows = 3) => `<div class="compose"><textarea id="say" rows="${rows}" placeholder="${ph}" aria-label="${ph}">${esc(f.text)}</textarea><span class="count" id="count">${words(f.text)}/${limit}</span></div>`;
  const slayer = () => {
    if (!f.showShot) return `<div class="slayer-row"><button class="linkish" id="shot-open">Claim the Slayer's shot…</button></div>`;
    const others = T.players.map((x) => x.name).filter((x) => x !== T.me.seat);
    return `<div class="slayer-box"><div class="fine">Shoot publicly at a player. If you are the real Slayer and hit the Demon, they die; otherwise nothing happens (anyone may claim).</div>
      <div class="picks">${others.map((n) => `<button type="button" class="pick${f.shot === n ? ' on' : ''}" data-shot="${esc(n)}" aria-pressed="${f.shot === n}">${esc(n)}</button>`).join('')}</div>
      <button class="linkish" id="shot-close">Never mind</button></div>`;
  };
  if (f.mode === 'night') {
    h += picks(p.options, f.max === 2 ? 'Choose two' : 'Choose');
    foot = `<div class="actions"><button class="primary" id="go" ${f.picks.length === f.max ? '' : 'disabled'}>Choose ${f.max === 2 ? (f.picks.length === 2 ? esc(f.picks.join(' and ')) : 'two') : f.picks[0] ? esc(f.picks[0] === T.me.seat ? 'yourself' : f.picks[0]) : ''}</button></div>`;
  } else if (f.mode === 'whisper') {
    h += picks(f.pickable, 'Whisper to', 'one or two players');
    h += textarea(f.picks.length ? `Only ${f.picks.join(' and ')} will see this` : 'Pick one or two players, then whisper…', p.whisper_words, 2);
    foot = `<div class="actions"><button class="primary violet" id="go" ${f.picks.length && words(f.text) ? '' : 'disabled'}>${f.picks.length ? `Whisper to ${esc(f.picks.join(' & '))}` : 'Whisper'}</button><button class="ghost" id="pass">Stay silent</button></div>`;
  } else if (f.mode === 'nominate') {
    h += picks(p.options, 'Nominate');
    h += textarea(f.picks[0] ? `Why ${f.picks[0]}? (your accusation)` : 'Pick a player to nominate, or pass', p.words, 2);
    foot = `<div class="actions"><button class="primary blood" id="go" ${f.picks.length ? '' : 'disabled'}>${f.picks[0] ? 'Nominate ' + esc(f.picks[0] === T.me.seat ? 'yourself' : f.picks[0]) : 'Nominate'}</button><button class="ghost" id="pass">Pass</button></div>`;
    h += slayer();
  } else if (f.mode === 'vote') {
    h += f.remark ? textarea('A short remark (optional)', p.words, 1) : '<div class="slayer-row"><button class="linkish" id="remark">Add a remark…</button></div>';
    foot = `<div class="vote-btns"><button class="primary blood" id="yes">${ICON.hand}Raise hand</button><button class="ghost" id="no">Keep it down</button></div>`;
  } else if (f.mode === 'defense') {
    h += textarea('Your defense, to the whole town', p.words, 3);
    foot = `<div class="actions"><button class="primary" id="go">Defend</button><button class="ghost" id="pass">Say nothing</button></div>`;
  } else {
    h += textarea(p.kind === 'comment' ? 'Speak before the vote (or stay quiet)' : 'Speak to the whole town…', p.words, 2);
    foot = `<div class="actions"><button class="primary" id="go" ${words(f.text) || f.shot ? '' : 'disabled'}>${f.shot && !words(f.text) ? 'Shoot' : 'Speak'}</button><button class="ghost" id="pass">Stay quiet</button></div>`;
    h += slayer();
  }
  if (f.err) foot = `<p class="err" role="alert">${esc(f.err)}</p>` + foot;
  const fresh = dock.dataset.turn !== String(p.turn);
  dock.dataset.turn = p.turn;
  dock.innerHTML = `<div class="dock-body" id="dock-body">${h}</div><div class="dock-foot">${foot}</div>`;  // the body scrolls, the buttons stay
  if (fresh && !REDUCED.matches) { dock.classList.add('arrive'); setTimeout(() => dock.classList.remove('arrive'), 400); }

  const pr = dock.querySelector('.ask .prompt');
  if (pr) {
    if (f.promptOpen) pr.classList.add('open');
    const flip = () => { f.promptOpen = !f.promptOpen; pr.classList.toggle('open'); pr.setAttribute('aria-expanded', f.promptOpen); setDockHeight(); };
    pr.onclick = flip; pr.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flip(); } };
  }
  dock.querySelectorAll('[data-pick]').forEach((b) => b.onclick = () => { togglePick(b.dataset.pick); $('dock').querySelector(`[data-pick="${CSS.escape(b.dataset.pick)}"]`)?.focus(); });
  dock.querySelectorAll('[data-shot]').forEach((b) => b.onclick = () => { f.shot = f.shot === b.dataset.shot ? null : b.dataset.shot; renderDock(); renderTown(); });
  const ta = $('say');
  if (ta) {
    const limit = f.mode === 'whisper' ? p.whisper_words : p.words;
    ta.oninput = () => {
      f.text = ta.value;
      const c = $('count'), n = words(f.text);
      c.textContent = n > limit ? `${n}/${limit} · cut at ${limit}` : `${n}/${limit}`;
      c.classList.toggle('over', n > limit);
      const go = $('go');
      if (go && f.mode === 'whisper') go.disabled = !(f.picks.length && n);
      if (go && f.mode === 'speak') { go.disabled = !(n || f.shot); go.textContent = f.shot && !n ? 'Shoot' : 'Speak'; }
    };
    ta.onkeydown = (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); ($('go') || $('yes'))?.click(); } };
  }
  const on = (id, fn) => { const b = $(id); if (b) b.onclick = fn; };
  on('shot-open', () => { f.showShot = true; renderDock(); });
  on('shot-close', () => { f.showShot = false; f.shot = null; renderDock(); renderTown(); });
  on('remark', () => { f.remark = true; renderDock(); $('say')?.focus(); });
  on('fold', () => { f.min = true; renderDock(); $('fold')?.focus(); const fd = $('feed'); fd.scrollTop = fd.scrollHeight; });
  on('go', () => submit(false));
  on('pass', () => submit(true));
  on('yes', () => submit(false, true));
  on('no', () => submit(false, false));
  if (fresh) announce(`Your turn: ${kindLabel}.`);
  setDockHeight();
}

function setDockHeight() { document.documentElement.style.setProperty('--dock-h', $('dock').offsetHeight + 'px'); }

/** A one-line echo of what this seat just did, shown while it waits (so every tap has visible feedback). */
function describe(a, f, pass) {
  const shot = a.slayer_shot ? ` and shot at ${a.slayer_shot}` : '';
  if (pass && !a.slayer_shot) return { whisper: 'You stayed silent', nominate: 'You passed', defense: 'You said nothing', speak: 'You stayed quiet' }[f.mode] || 'You passed';
  if (f.mode === 'night') return `You chose ${a.targets.map((t) => (t === T.me.seat ? 'yourself' : t)).join(' and ')}`;
  if (f.mode === 'whisper') return `You whispered to ${a.whispers[0].to.join(' and ')}`;
  if (f.mode === 'nominate') return (a.nominate ? `You nominated ${a.nominate === T.me.seat ? 'yourself' : a.nominate}` : 'You passed') + shot;
  if (f.mode === 'vote') return a.vote ? 'You raised your hand' : 'You kept your hand down';
  if (f.mode === 'defense') return 'You made your defense';
  return (a.say ? 'You spoke to the town' : 'You stayed quiet') + shot;
}

async function submit(pass, vote) {
  const p = T.pending, f = T.form;
  const a = { say: '', whispers: [], nominate: null, vote: null, targets: [], slayer_shot: null };
  if (!pass) {
    if (f.mode === 'night') a.targets = f.picks.slice();
    else if (f.mode === 'whisper') a.whispers = [{ to: f.picks.slice(), text: f.text.trim() }];
    else if (f.mode === 'nominate') { a.nominate = f.picks[0]; a.say = f.text.trim(); }
    else if (f.mode === 'vote') { a.vote = vote; a.say = f.text.trim(); }
    else a.say = f.text.trim();
    if (f.shot && (f.mode === 'speak' || f.mode === 'nominate')) a.slayer_shot = f.shot;
  } else if (f.shot && (f.mode === 'speak' || f.mode === 'nominate')) a.slayer_shot = f.shot;
  if (T.sent === p.turn) return;  // already sent: a double tap must not answer twice
  T.sent = p.turn;                // seal the dock at once, before the server replies
  T.did = describe(a, f, pass);
  document.title = 'Clocktower';
  renderDock(); renderTown(); renderPhase();
  try {
    await api('act', { turn: p.turn, action: a });
    pollState();  // what the move set in motion, without waiting out the poll interval
  } catch (e) {
    if (T.pending && T.pending.turn === p.turn) { T.sent = null; f.err = e.message; renderDock(); renderPhase(); }
  }
}

// ---------------------------------------------------------------- turn alerts
let audio = null;
function unlockAudio() { try { audio = audio || new (window.AudioContext || window.webkitAudioContext)(); audio.resume(); } catch { /* no audio */ } }
function chime() {
  if (!sound || !audio) return;
  const t = audio.currentTime;
  [[523.25, 0], [783.99, 0.14], [1046.5, 0.28]].forEach(([fq, dt]) => {
    const o = audio.createOscillator(), g = audio.createGain();
    o.type = 'sine'; o.frequency.value = fq;
    g.gain.setValueAtTime(0.0001, t + dt);
    g.gain.exponentialRampToValueAtTime(0.12, t + dt + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dt + 1.6);
    o.connect(g).connect(audio.destination); o.start(t + dt); o.stop(t + dt + 1.7);
  });
}
function alertTurn() {
  chime();
  try { navigator.vibrate && navigator.vibrate([60, 40, 60]); } catch { /* ignore */ }
  document.title = '● Your turn · Clocktower';
}
document.addEventListener('pointerdown', unlockAudio, { once: true });

// ---------------------------------------------------------------- sheets
let rules = null, sheetFrom = null;
async function openSheet(kind) {
  const body = $('sheet-body'), me = T.me;
  if ($('sheet').hidden) sheetFrom = document.activeElement;
  $('sheet').dataset.kind = kind;
  $('sheet').hidden = false; $('scrim').hidden = false;
  document.querySelectorAll('.tools .icon').forEach((b) => b.classList.toggle('on', b.dataset.sheet === kind));
  if (kind === 'town') {
    $('sheet-title').textContent = 'The town';
    body.innerHTML = '<div class="circle"></div><p class="fine center">Clockwise from the top. Tap a player to see only what involves them, at any time, your turn included; tap them again to see everything.</p>';
    T.townSig = ''; renderTown();
  } else if (kind === 'me') {
    $('sheet-title').textContent = 'Your character';
    const names = T.players.map((p) => p.name), i = names.indexOf(me.seat), n = names.length;
    const known = Object.entries(me.known);
    const team = me.evil ? 'evil' : 'good';
    body.innerHTML = `<div class="rcard ${team}"><span class="token big ${team}"><span class="initial">${esc(me.character[0])}</span></span>
      <div class="rc-body"><p class="eyebrow">${esc(me.seat)} · ${esc(me.kind)}</p><h3>The ${esc(me.character)}</h3><span class="plate ${team}">${team} team</span><p>${esc(me.ability)}</p></div></div>
      <p class="fine">You are on the <b>${team}</b> team${me.alive ? '' : ', and dead: you still talk and whisper, and have one ghost vote'}.</p>
      <h4>Your neighbours</h4><div class="kv"><span>${esc(names[(i - 1 + n) % n])}</span><span>${esc(names[(i + 1) % n])}</span></div>
      ${known.length ? `<h4>Your evil team</h4><div class="kv">${known.map(([nm, r]) => `<span class="evil">${esc(nm)} · ${r}</span>`).join('')}</div>` : ''}
      ${me.bluffs.length ? `<h4>Not in play (safe bluffs)</h4><div class="kv">${me.bluffs.map((b) => `<span>${esc(b)}</span>`).join('')}</div>` : ''}
      <h4>What the Storyteller has told you</h4>${[...$('feed').querySelectorAll('[data-cat="st"] .st-note p')].map((p) => `<p class="told">${esc(p.textContent)}</p>`).join('') || '<p class="fine">Nothing yet.</p>'}`
      + (T.host && !T.over ? `<h4>Host</h4><button class="ghost" id="end-game">End this game for everyone</button>
        <p class="fine">Ends it now and opens the Grimoire. A player whose page is closed for two minutes passes their turns automatically.</p>` : '');
    const eg = $('end-game');
    if (eg) eg.onclick = async () => {
      if (!confirm('End the game for everyone?')) return;
      try { await api('end', {}); closeSheet(); } catch (e) { alert(e.message); }
    };
  } else if (kind === 'script') {
    $('sheet-title').textContent = 'Trouble Brewing';
    rules = rules || await api('rules');
    const n = T.players.length || 10, [tf, os, mn] = SETUPS[n] || SETUPS[10];
    const group = (k, title, team) => `<h4 class="${team}">${title}</h4>` + rules.characters.filter((c) => c.kind === k).map((c) => `<div class="char ${team}${me && c.name === me.character ? ' mine' : ''}">
      <span class="mini-token ${team}" aria-hidden="true">${esc(c.name[0])}</span><div><b>${esc(c.name)}</b><span>${esc(c.ability)}</span></div></div>`).join('');
    body.innerHTML = `<p class="fine">This table of ${n}: ${tf} Townsfolk, ${os} Outsider${os === 1 ? '' : 's'}, ${mn} Minion${mn === 1 ? '' : 's'} and the Imp (a Baron adds two Outsiders in place of two Townsfolk). * = not on the first night.</p>`
      + group('Townsfolk', 'Townsfolk · good', 'good') + group('Outsider', 'Outsiders · good', 'good') + group('Minion', 'Minions · evil', 'evil') + group('Demon', 'Demon · evil', 'evil');
  } else if (kind === 'rules') {
    $('sheet-title').textContent = 'How this table works';
    rules = rules || await api('rules');
    const parts = rules.text.split(/\n(?=[A-Z][A-Z ]+\n)/);
    const keep = parts.filter((s) => !/^(CHARACTERS|YOUR RESPONSE)\n/.test(s));
    body.innerHTML = `<div class="rules"><p class="note">This is, word for word, what every AI player at this table was told (its system prompt), minus the characters (see the book) and the reply format. You have the same moves: one whisper per private-time turn, speech in the town square, nominations, votes and night choices, under the same word limits. Turns are taken a few players at a time, and a group's words are shown together once all of it has acted. The page tells you how many players the table is waiting on, never which ones.</p>`
      + keep.map((s) => { const [hd, ...rest] = s.split('\n'); return /^[A-Z ]+$/.test(hd) ? `<h4>${esc(hd.toLowerCase())}</h4><p>${esc(rest.join('\n'))}</p>` : `<p>${esc(s)}</p>`; }).join('')
      + '<p class="fine">How the AI models rank, and their games against each other: <a href="https://clocktowerbench.com" target="_blank" rel="noopener">clocktowerbench.com</a>.</p></div>';
  } else if (kind === 'notes') {
    $('sheet-title').textContent = 'Your notes';
    const key = `ct.notes.${T.game}.${me.seat}`;
    body.innerHTML = `<p class="fine">Private to this device. The AI players keep their own private reasoning from turn to turn; this is yours.</p><textarea id="notes-pad" aria-label="Your notes" placeholder="Claims, alibis, who whispered what…">${esc(store.get(key) || '')}</textarea>`;
    $('notes-pad').oninput = (e) => store.set(key, e.target.value);
  }
  $('sheet-close').focus();
}
function closeSheet() {
  if ($('sheet').hidden) return;
  $('sheet').hidden = true; $('scrim').hidden = true;
  document.querySelectorAll('.tools .icon').forEach((b) => b.classList.remove('on'));
  if (sheetFrom && document.contains(sheetFrom)) sheetFrom.focus();
}

// ---------------------------------------------------------------- reveal
function renderReveal() {
  const R = T.reveal, me = T.me;
  if (!R) return;
  const box = $('reveal');
  box.className = R.winner === 'evil' ? 'evil' : R.winner === 'good' ? 'good' : '';
  const title = R.winner ? `${R.winner === 'good' ? 'Good' : 'Evil'} wins` : 'The game stopped';
  box.innerHTML = `<div class="rv"><p class="crest">The Grimoire is opened</p><h2>${title}</h2><p class="why">${esc(R.reason || '')}</p>
    <div class="rv-grid">${R.seats.map((s) => {
      const was = s.started && s.started !== s.character ? `<small>was the ${esc(s.started)}</small>` : '';
      const thought = s.shown ? `<small>thought they were the ${esc(s.shown)}</small>` : '';
      const model = (models[(s.model || '').split('@')[0]] || s.model || '').replace(/ \(.*\)$/, '');
      const by = s.player ? `<small class="human">${esc(s.player)}</small>` : `<small class="model">${esc((s.model || '').startsWith('random') ? 'Practice bot' : model)}</small>`;
      const rd = R.reads && R.reads[s.name] && R.reads[s.name].evil != null ? `<small class="read">AIs: ${Math.round(R.reads[s.name].evil * 100)}% evil</small>` : '';
      return `<div class="rv-seat${s.evil ? ' evil' : ' good'}${s.alive ? '' : ' dead'}${s.name === me.seat ? ' you' : ''}">
        <span class="token ${s.evil ? 'evil' : 'good'}"><span class="initial">${esc(s.character[0])}</span>${s.alive ? '' : '<span class="shroud"></span>'}</span><b>${esc(s.name)}${s.name === me.seat ? ' <em>you</em>' : ''}</b><small class="rv-char ${s.evil ? 'evil' : 'good'}">${esc(s.character)}${s.alive ? '' : ' · dead'}</small>${was}${thought}${by}${rd}</div>`;
    }).join('')}</div>
    <p class="fine">Demon bluffs: ${(R.bluffs || []).map(esc).join(', ')}${R.red_herring ? ` · Fortune Teller's red herring: ${esc(R.red_herring)}` : ''}</p>
    ${readsHTML(R)}
    <div class="rv-actions"><button class="primary" id="rv-read">Read every AI's reasoning</button><button class="ghost" id="rv-close">Back to the table</button>
    <button class="ghost" id="rv-lobby">Back to the lobby</button></div>
    <p class="fine center"><a href="https://clocktowerbench.com" target="_blank" rel="noopener">How the models rank: clocktowerbench.com</a></p></div>`;
  box.querySelectorAll('.rv-seat').forEach((el, i) => { el.style.animationDelay = `${i * 60}ms`; });
  box.hidden = false;
  box.scrollTop = 0;
  $('rv-read').onclick = () => window.open(`/api/t/${TID}/transcript?token=${encodeURIComponent(token)}`, '_blank', 'noopener');
  $('rv-close').onclick = () => { box.hidden = true; $('see-reveal')?.focus(); };
  $('rv-lobby').onclick = async () => {
    try { await api('reset', {}); } catch { /* not the host: just go back */ }
    box.hidden = true; clearTimeout(tableTimer); T.game = null; pollLobby();
  };
  $('rv-close').focus({ preventScroll: true });
}

function readsHTML(R) {
  const reads = R.reads || {}, me = T.me && T.me.seat;
  const mine = reads[me];
  if (!Object.keys(reads).length) return '';
  const pct = (x) => (x == null ? '?' : `${Math.round(x * 100)}%`);
  let h = '<div class="reads"><h3>What the AIs believed</h3><p class="fine">From each good AI player\'s last private survey (asked outside the game; nobody saw it).</p>';
  if (mine) {
    h += `<div class="scroll-x"><table><tr><th>AI player</th><th>You evil</th><th>You the Demon</th><th>Their guess at your character</th></tr>${mine.by.map((b) => {
      const s = R.seats.find((x) => x.name === b.seat) || {};
      const model = (models[(s.model || '').split('@')[0]] || s.model || '').replace(/ \(.*\)$/, '');
      return `<tr><td>${esc(b.seat)} <small>${esc(model)}</small></td><td>${pct(b.evil)}</td><td>${pct(b.demon)}</td><td>${esc(b.character || '')}</td></tr>`;
    }).join('')}</table></div>`;
  }
  const others = Object.entries(reads).filter(([k]) => k !== me);
  if (others.length) h += `<p class="fine">${others.map(([k, v]) => `${esc(k)}: ${pct(v.evil)} evil on average`).join(' · ')}</p>`;
  return h + '</div>';
}

// ---------------------------------------------------------------- boot
function boot() {
  const m = location.hash.match(/host=([\w-]+)/);
  if (m) hostKey = m[1];
  const mine = location.hash.match(/me=([\w-]+)/);
  if (mine && TID) { setToken(mine[1]); history.replaceState(null, '', location.pathname); }
  wireLobby();
  $('town-btn').innerHTML = ICON.town;
  document.querySelector('[data-sheet="script"]').innerHTML = ICON.book;
  document.querySelector('[data-sheet="rules"]').innerHTML = ICON.scroll;
  document.querySelector('[data-sheet="notes"]').innerHTML = ICON.pen;
  const sb = $('sound-btn');
  const paintSound = () => { sb.innerHTML = sound ? ICON.sound : ICON.mute; sb.title = sound ? 'Turn chime on' : 'Turn chime off'; sb.setAttribute('aria-pressed', sound); };
  paintSound();
  sb.onclick = () => { sound = !sound; store.set('ct.sound', sound ? 'on' : 'off'); unlockAudio(); paintSound(); };
  document.querySelectorAll('[data-sheet]').forEach((b) => b.onclick = () => openSheet(b.dataset.sheet));
  $('me-chip').onclick = () => openSheet('me');
  $('sheet-close').onclick = closeSheet;
  $('scrim').onclick = closeSheet;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { if (!$('sheet').hidden) closeSheet(); else if (!$('reveal').hidden) $('rv-close')?.click(); } });
  $('jump').onclick = () => { const f = $('feed'); f.scrollTop = f.scrollHeight; $('jump').hidden = true; };
  $('feed').addEventListener('scroll', () => { const f = $('feed'); if (f.scrollHeight - f.scrollTop - f.clientHeight < 60) $('jump').hidden = true; });
  window.addEventListener('resize', () => { if (!$('table').hidden) { T.townSig = ''; renderTown(); } setDockHeight(); });
  resetTable(null);
  renderFilters();
  if (!TID) return home();
  pollLobby();
}
boot();
