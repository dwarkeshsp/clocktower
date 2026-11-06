"""Play against the AI players with friends: `python -m clocktower play`, then open the link it prints.
The same server hosts the public tables at play.clocktowerbench.com (docs/hosting.md).

One server holds many tables. Each table has a lobby and plays one game at a time; anyone with a table's
link can join it, and joining gives that browser a private, unguessable token for its seat (a personal
rejoin link carries it to another device). A person's seat sees exactly what a model in that seat would
see (the same rendered events, the same prompts) and answers the same requests (whispers, speech,
nominations, votes, night choices, Slayer shots) under the same word limits. Each person's allegiance
choice, and which seat they were dealt, stays secret from everyone else until the Grimoire is opened.

What survives a restart: every table, its people and their tokens, and each game, which continues from
its last dusk (the engine's checkpoint.pkl), all kept in one SQLite file (`Store`). AI seats cost money,
so a game is paid either by the house (only the free models, within a daily and a per-game cap) or by
the host's own API keys, which live in this process's memory only and are never written anywhere.

The page lives in clocktower/table/; this module is its JSON API and the game runner (one thread with its
own event loop per game, so the HTTP server stays responsive while games wait on people and models).
"""
from __future__ import annotations
import argparse
import asyncio
import json
import math
import os
import random
import re
import secrets
import shutil
import socket
import sqlite3
import threading
import time
import traceback
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from .agents import HumanSeat
from .characters import ABILITY, DEMONS, MINIONS, OUTSIDERS, SETUPS, TOWNSFOLK, kind
from .game import WORDS
from .llm import OPENAI_PREFIXES, TLS, BudgetExceeded, Ledger, limiter, make_client
from .prompts import player_system
from .render import render, visible

PAGE = Path(__file__).with_name('table')
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml',
         '.woff': 'font/woff', '.woff2': 'font/woff2'}  # the page's self-hosted fonts (table/fonts)
HOME = 'https://clocktowerbench.com'

# What the lobby offers, strongest first: the 2026 rating (docs/plans/f2-ratings.json) and the fitted
# cost of one AI seat for one game (v16-v17 results), so a host can see roughly what a game costs.
MODELS = [
    ('gpt-6-astra', 'GPT-6 Astra', 1858, 1.85),
    ('gpt-6.1-sol', 'GPT-6.1 Sol', 1729, 0.11),
    ('claude-fable-5-1', 'Claude Fable 5.1', 1595, 2.66),
    ('gpt-5.6-sol', 'GPT-5.6 Sol', 1593, 0.74),
    ('claude-fable-5', 'Claude Fable 5', 1561, 10.43),
    ('claude-opus-5-5', 'Claude Opus 5.5', 1538, 0.85),
    ('gpt-5.5', 'GPT-5.5', 1472, 1.91),
    ('claude-opus-4-6', 'Claude Opus 4.6', 1427, 3.30),
    ('gpt-5.4', 'GPT-5.4', 1268, 3.87),
    ('claude-opus-4-7', 'Claude Opus 4.7', 1265, 2.77),
    ('claude-opus-4-8', 'Claude Opus 4.8', 1194, 8.44),
    ('random', 'Practice bots (random moves, free)', None, 0.0),
]
TEAMS = ('good', 'evil', 'any')
SIZES = (10, 11, 12)          # the eval's table sizes (two Minions)
MAX_PEOPLE = 12
TIMERS = (0, 60, 120, 300, 600)  # seconds per turn; 0 = wait as long as it takes
AWAY = 120  # a player whose page hasn't checked in for this long passes their turns
NAME_LEN, TEXT_LEN, KEY_LEN, BODY_LEN = 24, 2000, 300, 32_000


def provider(model):
    if model == 'random':
        return None
    if model.startswith('openrouter:'):
        return 'openrouter'
    return 'openai' if model.startswith(OPENAI_PREFIXES) else 'anthropic'


def server_key(prov):
    """Whether this server holds an API key for the provider (the house's free models need one)."""
    return bool({'anthropic': os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('MY_ANTHROPIC_API_KEY'),
                 'openai': os.environ.get('OPENAI_API_KEY'),
                 'openrouter': os.environ.get('OPENROUTER_API_KEY')}.get(prov))


def available(model):
    """Whether this server could play the model on its own keys."""
    return model == 'random' or server_key(provider(model))


def env_num(env, name, default, cast=float):
    try:
        return cast(env.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    """Limits for a hosted server, from PLAY_* environment variables (docs/hosting.md)."""
    data_dir: Path | None = None              # SQLite file and game logs; None = memory only (tests)
    daily_cap: float = 30.0                   # USD per UTC day the house pays for free games
    budget_timezone: str = 'UTC'              # midnight in this timezone resets the daily cap
    budget_period: str = 'day'                # 'day' or 'month': how often daily_cap resets (the 1st, for a month)
    game_cap: float = 5.0                     # USD one free game may spend
    byo_game_cap: float = 50.0                # USD one game on a player's own key may spend
    free_models: tuple = ('gpt-6.1-sol',)     # models the house pays for; ('all',) = every model with a key
    max_games: int = 20                       # games running at once
    max_tables: int = 300                     # open tables (lobbies and games)
    tables_per_hour: int = 6                  # new tables per IP per hour
    idle_minutes: float = 30.0                # a lobby or game nobody has looked at for this long closes
    keep_days: float = 14.0                   # finished tables (and their logs) are kept this long; 0 = forever
    proxy_hops: int = 0                       # trusted proxies in front (Render: 1) for client IPs
    ip_header: str | None = None              # header the proxy sets to the client IP (Fly: Fly-Client-IP); wins over hops
    public_url: str | None = None             # e.g. https://play.clocktowerbench.com (links, allowed origin)
    allowed_origins: tuple = ()               # extra origins allowed to POST
    probes: bool = True                       # ask AI seats for their beliefs (shown at the reveal)

    def __post_init__(self):
        ZoneInfo(self.budget_timezone)
        if self.budget_period not in ('day', 'month'):
            raise ValueError("budget_period must be 'day' or 'month'")
        for name in ('daily_cap', 'game_cap', 'byo_game_cap'):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) < 0:
                raise ValueError(f'{name} must be a finite nonnegative amount')

    @classmethod
    def from_env(cls, env=None, data_dir=None):
        env = os.environ if env is None else env
        d = env.get('PLAY_DATA_DIR') or data_dir
        url = (env.get('PLAY_PUBLIC_URL') or '').rstrip('/') or None
        return cls(data_dir=Path(d) if d else None,
                   daily_cap=env_num(env, 'PLAY_DAILY_BUDGET', 30.0), game_cap=env_num(env, 'PLAY_GAME_BUDGET', 5.0),
                   budget_timezone=env.get('PLAY_BUDGET_TIMEZONE', 'UTC'),
                   budget_period=env.get('PLAY_BUDGET_PERIOD', 'day').strip().lower(),
                   byo_game_cap=env_num(env, 'PLAY_BYO_GAME_BUDGET', 50.0),
                   free_models=tuple(m.strip() for m in env.get('PLAY_FREE_MODELS', 'gpt-6.1-sol').split(',') if m.strip()),
                   max_games=env_num(env, 'PLAY_MAX_GAMES', 20, int), max_tables=env_num(env, 'PLAY_MAX_TABLES', 300, int),
                   tables_per_hour=env_num(env, 'PLAY_TABLES_PER_HOUR', 6, int),
                   idle_minutes=env_num(env, 'PLAY_IDLE_MINUTES', 30.0), keep_days=env_num(env, 'PLAY_KEEP_DAYS', 14.0),
                   proxy_hops=env_num(env, 'PLAY_PROXY_HOPS', 0, int), public_url=url,
                   ip_header=(env.get('PLAY_IP_HEADER') or '').strip() or None,
                   allowed_origins=tuple(o.strip().rstrip('/') for o in env.get('PLAY_ALLOWED_ORIGINS', '').split(',') if o.strip()),
                   probes=env.get('PLAY_PROBES', '1') not in ('0', 'false', 'no'))

    def free(self, model):
        """Whether the house pays for this model (it must also hold the key)."""
        return model == 'gpt-6.1-sol' and ('all' in self.free_models or model in self.free_models) and available(model)


# ---- storage ---------------------------------------------------------------------------------------
class Store:
    """Tables and spend in one SQLite file (stdlib). Everything goes through these few methods, so a
    Postgres version is the same class with another connection and placeholder style."""

    def __init__(self, path=':memory:'):
        if path != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        with self.lock:
            if self.path != ':memory:':
                self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('CREATE TABLE IF NOT EXISTS tables (id TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS spend (time REAL NOT NULL, table_id TEXT, game TEXT, '
                            'cost REAL NOT NULL, paid_by TEXT NOT NULL, label TEXT)')
            self.db.execute('CREATE INDEX IF NOT EXISTS spend_time ON spend (time)')
            if 'pending' not in {row[1] for row in self.db.execute('PRAGMA table_info(spend)')}:
                self.db.execute('ALTER TABLE spend ADD COLUMN pending INTEGER NOT NULL DEFAULT 0')

    def save_table(self, tid, data):
        with self.lock:
            self.db.execute('INSERT INTO tables (id, data, updated) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE '
                            'SET data = excluded.data, updated = excluded.updated', (tid, json.dumps(data), time.time()))

    def load_tables(self):
        with self.lock:
            return [json.loads(d) for (d,) in self.db.execute('SELECT data FROM tables ORDER BY updated')]

    def delete_table(self, tid):
        with self.lock:
            self.db.execute('DELETE FROM tables WHERE id = ?', (tid,))

    def add_spend(self, table, game, cost, paid_by, label=None):
        with self.lock:
            self.db.execute('INSERT INTO spend (time, table_id, game, cost, paid_by, label) VALUES (?, ?, ?, ?, ?, ?)',
                            (time.time(), table, game, cost, paid_by, label))

    def spent(self, since=0.0, paid_by=None, game=None):
        q, args = 'SELECT COALESCE(SUM(cost), 0) FROM spend WHERE (time >= ? OR pending = 1)', [since]
        if paid_by:
            q, args = q + ' AND paid_by = ?', args + [paid_by]
        if game:
            q, args = q + ' AND game = ?', args + [game]
        with self.lock:
            return self.db.execute(q, args).fetchone()[0]

    def reserve(self, table, game, amount, daily_cap, game_cap, timezone, label, period='day'):
        """Charge the upper bound durably before sending; SQLite serializes competing games/processes.
        Uncertain requests remain pending across midnight/restarts until explicitly reconciled."""
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError('Invalid request reservation')
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                daily = self.db.execute("SELECT COALESCE(SUM(cost), 0) FROM spend WHERE paid_by = 'house' "
                                        'AND (time >= ? OR pending = 1)', (today(timezone, period),)).fetchone()[0]
                game_spent = self.db.execute('SELECT COALESCE(SUM(cost), 0) FROM spend WHERE game = ?',
                                             (game,)).fetchone()[0]
                if daily + amount > daily_cap:
                    raise BudgetExceeded(f'The {period}ly AI budget has no room for this request and calls in progress.')
                if game_cap is not None and game_spent + amount > game_cap:
                    raise BudgetExceeded('The game AI budget has no room for this request and calls in progress.')
                cur = self.db.execute('INSERT INTO spend (time, table_id, game, cost, paid_by, label, pending) '
                                      "VALUES (?, ?, ?, ?, 'house', ?, 1)",
                                      (time.time(), table, game, amount, label))
                self.db.execute('COMMIT')
                return cur.lastrowid
            except BaseException:
                self.db.execute('ROLLBACK')
                raise

    def settle(self, reservation, amount):
        with self.lock:
            row = self.db.execute('SELECT cost FROM spend WHERE rowid = ? AND pending = 1', (reservation,)).fetchone()
            if not row or not math.isfinite(amount) or not 0 <= amount <= row[0]:
                raise BudgetExceeded('Cannot reconcile API cost safely; the request reservation remains held.')
            self.db.execute('UPDATE spend SET cost = ?, pending = 0, time = ? WHERE rowid = ?',
                            (amount, time.time(), reservation))


def today(timezone='UTC', period='day'):
    """Epoch seconds at the start of the current budget period (today, or the 1st of this month) at midnight
    in the configured budget timezone."""
    start = datetime.fromtimestamp(time.time(), ZoneInfo(timezone)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (start.replace(day=1) if period == 'month' else start).timestamp()


class PlayLedger(Ledger):
    """Per-game accounting, with durable per-request reservations for house-paid OpenAI calls."""

    def __init__(self, table, game, paid_by, cap, store, daily_cap=None, timezone='UTC', period='day'):
        self.table, self.game, self.paid_by, self.cap, self.store = table, game, paid_by, cap, store
        self.path = None
        self.spent = store.spent(game=game) if store else 0.0  # a resumed game counts what it spent before
        self.daily_cap, self.timezone, self.period = daily_cap, timezone, period
        self.hard_budget = paid_by == 'house' and daily_cap is not None
        if self.hard_budget and store is None:
            raise ValueError('A house budget requires persistent accounting')

    def reserve(self, amount, label):
        return self.store.reserve(self.table, self.game, amount, self.daily_cap, self.cap, self.timezone, label, self.period)

    def check(self):
        if self.cap is not None and self.spent >= self.cap:
            raise BudgetExceeded(f'this game has spent ${self.spent:.2f} of its ${self.cap:.2f} cap')

    def add(self, amount, **meta):
        if self.hard_budget:
            if meta.get('reservation') is None:
                raise BudgetExceeded('House API calls must reserve their cost before sending.')
            self.store.settle(meta['reservation'], amount)
            self.spent = self.store.spent(game=self.game)
            return
        self.spent += amount
        if self.store:
            self.store.add_spend(self.table, self.game, amount, self.paid_by, meta.get('label'))


# ---- keys --------------------------------------------------------------------------------------------
KEY_SHAPE = re.compile(r'^[A-Za-z0-9_\-]{20,%d}$' % KEY_LEN)
SECRET = re.compile(r'(sk-[A-Za-z0-9_\-*.]{6,}|sk_[A-Za-z0-9_\-*.]{6,})')


def redact(text, keys=()):
    """Text with API keys (whole or in the masked form providers echo in errors) taken out."""
    text = str(text or '')
    for k in keys:
        if k:
            text = text.replace(k, '[key]')
    return SECRET.sub('[key]', text)


def check_key(prov, key):
    """Ask the provider whether a key works (listing models is free). Raises ValueError if it is refused;
    a network problem lets the key through (the game will fail clearly if it really is bad)."""
    url, headers = ({'anthropic': ('https://api.anthropic.com/v1/models', {'x-api-key': key, 'anthropic-version': '2023-06-01'}),
                     'openai': ('https://api.openai.com/v1/models', {'Authorization': f'Bearer {key}'})}[prov])
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10, context=TLS).close()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ValueError(f'{"Anthropic" if prov == "anthropic" else "OpenAI"} refused that key.') from None
    except (urllib.error.URLError, OSError):
        pass


# ---- seats -------------------------------------------------------------------------------------------
class RateLimited(Exception):
    pass


class NotFound(Exception):
    pass


def evil_seats(n):
    return SETUPS[n][2] + 1


def assign(people, players, rng):
    """Seats for people, given the dealt players: those who asked for evil get evil seats, good get
    good, the rest fill what is left. `people` is [(token, team)]; returns {token: seat name}."""
    evil = [p.name for p in players if p.evil]
    good = [p.name for p in players if not p.evil]
    rng.shuffle(evil)
    rng.shuffle(good)
    out = {}
    for want in ('evil', 'good', 'any'):
        for token, team in people:
            if team != want:
                continue
            pool = {'evil': evil, 'good': good}.get(team) or rng.choice([x for x in (evil, good) if x])
            out[token] = pool.pop()
    return out


def lan_address():
    """This machine's address on the local network (for friends' phones), or None."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('10.255.255.255', 1))
            return s.getsockname()[0]
    except OSError:
        return None


def clean_name(name):
    name = ''.join(c for c in str(name or '') if c.isprintable())
    return ' '.join(name.split())[:NAME_LEN]


def clean_text(v):
    if not isinstance(v, str):
        return ''
    return ''.join(c for c in v[:TEXT_LEN] if c.isprintable() or c in '\n\t')


def clean(a):
    """An action from the page, coerced to the schema's shape (the engine validates names and limits)."""
    a = a if isinstance(a, dict) else {}
    names = lambda v: [x[:NAME_LEN] for x in v if isinstance(x, str)][:3] if isinstance(v, list) else []
    one = lambda v: v[:NAME_LEN] if isinstance(v, str) else None
    whispers = [{'to': names(w.get('to')), 'text': clean_text(w.get('text'))}
                for w in (a.get('whispers') or [])[:1] if isinstance(w, dict)] if isinstance(a.get('whispers'), list) else []
    return {'say': clean_text(a.get('say')), 'whispers': whispers, 'nominate': one(a.get('nominate')),
            'vote': a.get('vote') if isinstance(a.get('vote'), bool) else None,
            'targets': names(a.get('targets')), 'slayer_shot': one(a.get('slayer_shot'))}


def public_view(evs, start=0, dead=None, ghosts=None):
    """Deaths as the town knows them (the engine's own record runs ahead at night) and used ghost votes,
    scanning events from `start` (callers keep the sets and scan only new events)."""
    dead, ghosts = set() if dead is None else dead, set() if ghosts is None else ghosts
    for ev in evs[start:]:
        k, d = ev['kind'], ev['data']
        if ev['to'] != 'public':
            continue
        if k == 'dawn':
            dead.update(d['deaths'])
        elif k == 'execution' and d.get('died'):
            dead.add(d['player'])
        elif k == 'slayer' and d.get('died'):
            dead.add(d['target'])
        elif k == 'vote' and d.get('ghost'):
            ghosts.add(d['voter'])
    return dead, ghosts


def reads(out, humans):
    """What the good AI seats believed about each human seat at their last belief probe (probe.py):
    {seat: {'evil': mean chance evil, 'by': [{'seat', 'evil', 'demon', 'character'}]}}."""
    path = Path(out) / 'probes.jsonl' if out else None
    if not humans or not path or not path.exists():
        return {}
    latest = {}
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('team') == 'good' and r.get('players') and r.get('player') not in humans:
            if r['player'] not in latest or r.get('day', 0) >= latest[r['player']].get('day', 0):
                latest[r['player']] = r
    out_ = {}
    for h in sorted(humans):
        by = [{'seat': p, 'day': r.get('day'), **{k: r['players'][h].get(k) for k in ('evil', 'demon', 'character')}}
              for p, r in sorted(latest.items()) if h in r['players']]
        vals = [b['evil'] for b in by if b['evil'] is not None]
        if by:
            out_[h] = {'evil': round(sum(vals) / len(vals), 3) if vals else None, 'by': by}
    return out_


# ---- one table ---------------------------------------------------------------------------------------
class Table:
    """A lobby, the people at it, and its current game."""

    def __init__(self, args, runner=None, hub=None, tid=None):
        self.args, self.hub = args, hub
        self.settings = hub.settings if hub else Settings()
        self.id = tid or secrets.token_urlsafe(9)
        self.lock = threading.RLock()
        self.people = {}       # token -> {id, name, team, host, seat}
        self.host_key = os.environ.get('CLOCKTOWER_HOST_KEY') if not hub else None
        self.host_key = self.host_key or secrets.token_urlsafe(12)
        free = [m[0] for m in MODELS if self.settings.free(m[0])]
        pick = lambda m: m if m == 'random' or (m and self.settings.free(m)) else (free[0] if free else 'random')
        model = getattr(args, 'model', None)
        self.config = {'players': 10, 'good_model': pick(getattr(args, 'good_model', None) or model),
                       'evil_model': pick(getattr(args, 'evil_model', None) or model), 'timer': 300 if hub else 0}
        self.status, self.error, self.game, self.result = 'lobby', None, None, None
        self.seats = {}        # seat name -> HumanSeat (current game)
        self.seat_map = {}     # seat name -> token (current game; kept, so a resumed game seats people again)
        self.game_id, self.run, self.seed, self.out, self.paid_by = None, 0, None, None, None
        self.runner = runner or run_game
        self.links = {}
        self.dealt = set()     # tokens of the people in the current game
        self.seen = {}         # token -> when that player's page last checked in
        self.ended = None      # why the game was ended early: 'host' or 'idle'
        self.keys = {}         # provider -> a player's own API key: memory only, never saved or shown
        self.final = None      # the reveal and each human seat's last view, kept once a game is over
        self.games = []        # every log folder this table has made (deleted with it)
        self.created = self.active = time.time()
        self.finished = None
        self.keep = False      # never closed for idleness (the table a local server opens at start)
        self._scan = (None, 0, set(), set())

    # ---- persistence ---------------------------------------------------------------------------------
    FIELDS = ('id', 'host_key', 'people', 'config', 'status', 'error', 'game_id', 'run', 'seed', 'out', 'paid_by',
              'seat_map', 'ended', 'final', 'games', 'created', 'finished', 'result')

    def snapshot(self):
        with self.lock:
            return {**{k: getattr(self, k) for k in self.FIELDS}, 'dealt': sorted(self.dealt)}

    def save(self):
        if self.hub:
            self.hub.store.save_table(self.id, self.snapshot())

    @classmethod
    def from_snapshot(cls, args, data, hub, runner=None):
        t = cls(args, runner, hub, data['id'])
        for k in cls.FIELDS:
            if k in data:
                setattr(t, k, data[k])
        t.dealt = set(data.get('dealt') or [])
        now = time.time()
        t.seen = {tok: now for tok in t.people}  # everyone gets the usual grace to come back
        return t

    # ---- lobby ---------------------------------------------------------------------------------------
    def join(self, name, team, host_key=None):
        name = clean_name(name)
        if not name:
            raise ValueError('Enter a name.')
        if team not in TEAMS:
            raise ValueError('Choose good, evil or either.')
        with self.lock:
            if len(self.people) >= MAX_PEOPLE:
                raise ValueError(f'The table is full ({MAX_PEOPLE} people).')
            token = secrets.token_urlsafe(18)
            first = not any(p['host'] for p in self.people.values())  # the first to join hosts
            self.people[token] = {'id': secrets.token_hex(4), 'name': name, 'team': team,
                                  'host': first or host_key == self.host_key, 'seat': None}
            self.seen[token] = self.active = time.time()
        self.save()
        return token

    def person(self, token):
        p = self.people.get(token or '') if isinstance(token, str) else None
        if not p:
            raise PermissionError('Unknown player: join the table first.')
        return p

    def update_me(self, token, name=None, team=None):
        with self.lock:
            p = self.person(token)
            if name is not None:
                name = clean_name(name)
                if name:
                    p['name'] = name
            if team is not None and self.status in ('lobby', 'over'):
                if team not in TEAMS:
                    raise ValueError('Choose good, evil or either.')
                p['team'] = team
        self.save()

    def claim_host(self, token, key=None):
        """Anyone at the table may become a host (friends trust each other); hosts set up and start games."""
        with self.lock:
            self.person(token)['host'] = True
        self.save()

    def host(self, token, what='do that'):
        p = self.person(token)
        if not p['host']:
            raise PermissionError(f'Only the host can {what}.')
        return p

    def ready(self, model):
        """Whether the table can play this model now: free, or a host gave a key for its provider."""
        return model == 'random' or self.settings.free(model) or provider(model) in self.keys

    def set_config(self, token, cfg):
        with self.lock:
            self.host(token, 'change the table')
            if self.status in ('playing', 'paused'):
                raise ValueError('A game is under way.')
            ids = {m[0] for m in MODELS} | {self.config['good_model'], self.config['evil_model']}
            if 'players' in cfg:
                n = int(cfg['players'])
                if n not in SIZES:
                    raise ValueError(f'Tables seat {SIZES[0]} to {SIZES[-1]} players.')
                self.config['players'] = n
            for k in ('good_model', 'evil_model'):
                if k in cfg:
                    if cfg[k] not in ids:
                        raise ValueError(f'Unknown model {cfg[k]}.')
                    if not self.ready(cfg[k]):
                        raise ValueError(f'{cfg[k]} needs your own {provider(cfg[k]).title()} API key.')
                    self.config[k] = cfg[k]
            if 'timer' in cfg:
                t = int(cfg['timer'])
                if t not in TIMERS:
                    raise ValueError('Unknown timer.')
                self.config['timer'] = t
        self.save()

    def set_key(self, token, prov, key):
        """A host's own API key for this table's games: kept in memory only. An empty key removes it."""
        if prov not in ('anthropic', 'openai'):
            raise ValueError('Keys are for Anthropic or OpenAI.')
        key = (key or '').strip() if isinstance(key, str) else ''
        with self.lock:
            self.host(token, 'add an API key')
            if self.status == 'playing':
                raise ValueError('A game is under way.')
        if not key:
            with self.lock:
                self.keys.pop(prov, None)
                for k in ('good_model', 'evil_model'):  # back to a model the table can still play
                    if not self.ready(self.config[k]):
                        self.config[k] = next((m[0] for m in MODELS if self.ready(m[0])), 'random')
            self.save()
            return {'keys': sorted(self.keys)}
        if not KEY_SHAPE.match(key):
            raise ValueError("That doesn't look like an API key.")
        (self.hub.check_key if self.hub else check_key)(prov, key)
        with self.lock:
            self.keys[prov] = key
        return {'keys': sorted(self.keys)}

    def kick(self, token, target):
        with self.lock:
            self.host(token)
            if self.status in ('playing', 'paused'):
                raise ValueError('A game is under way.')
            gone = [t for t, p in self.people.items() if p['id'] == target and t != token]
            for t in gone:
                del self.people[t]
        self.save()

    def problem(self):
        """Why the game can't start yet, or None. Counts only: never who chose what."""
        n, people = self.config['players'], list(self.people.values())
        if not people:
            return 'Nobody has joined.'
        if len(people) > n:
            return f'{len(people)} people have joined a {n}-player table: add seats.'
        evil = sum(p['team'] == 'evil' for p in people)
        good = sum(p['team'] == 'good' for p in people)
        if evil > evil_seats(n):
            return f'Too many people chose evil: a {n}-player table has {evil_seats(n)} evil seats.'
        if good > n - evil_seats(n):
            return f'Too many people chose good: a {n}-player table has {n - evil_seats(n)} good seats.'
        return self.payer()[1]

    def payer(self):
        """Who pays for this game's AI seats: (None | 'house' | 'player', problem or None)."""
        c = self.config
        if len(self.people) >= c['players']:
            return None, None
        models = {c['good_model'], c['evil_model']} - {'random'}
        if not models:
            return None, None
        provs = {provider(m) for m in models}
        if provs <= set(self.keys):
            return 'player', None
        if all(self.settings.free(m) for m in models) and not provs & set(self.keys):
            return 'house', None
        names = dict((m[0], m[1]) for m in MODELS)
        return None, ('A game is paid either by the free allowance or by your own keys: add a key for '
                      + ' and '.join(sorted(p.title() for p in provs - set(self.keys)))
                      + ', or pick ' + ' / '.join(names.get(m, m) for m in self.settings.free_models if m in names)
                      + ' or practice bots for both teams.')

    def start(self, token):
        with self.lock:
            self.host(token, 'begin')
            if self.status in ('playing', 'paused'):
                raise ValueError('A game is already under way.')
            why = self.problem()
            if why:
                raise ValueError(why)
            paid_by = self.payer()[0]
            if self.hub:
                self.hub.admit(self, paid_by)
            for p in self.people.values():
                p['seat'] = None
            self.status, self.error, self.result, self.game, self.seats, self.final = 'playing', None, None, None, {}, None
            self.ended, self.seat_map, self.paid_by, self.run = None, {}, paid_by, 1
            now = time.time()
            self.seen.update({t: now for t in self.people})
            self.game_id = secrets.token_hex(4)
            self.seed = getattr(self.args, 'seed', None)
            self.seed = self.seed if self.seed is not None else random.randrange(2 ** 32)
            root = Path(self.hub.settings.data_dir / 'games') if self.hub and self.hub.settings.data_dir else \
                Path(getattr(self.args, 'out', None) or Path(__file__).resolve().parent.parent / 'games' / 'play')
            self.out = str(root / f'{time.strftime("%Y%m%d-%H%M%S")}-{self.id}-{self.game_id}')
            self.games.append(self.out)
            self.dealt = set(self.people)
        self.save()
        self.launch()

    def launch(self):
        cfg = {**self.config, 'seed': self.seed, 'out': self.out, 'game_id': self.game_id,
               'probes': self.settings.probes and self.paid_by is not None}
        threading.Thread(target=self._run, args=(cfg,), daemon=True, name=f'game-{self.id}').start()

    def resume(self, token):
        """Continue a game that a server restart paused (it was paid by keys the restart forgot)."""
        with self.lock:
            self.host(token, 'resume the game')
            if self.status != 'paused':
                raise ValueError('No game is paused.')
            if self.payer()[0] != 'player':
                raise ValueError('Add your API key again first: the server forgot it when it restarted.')
            if self.hub:
                self.hub.admit(self, 'player')
            self.status, self.run = 'playing', self.run + 1
        self.save()
        self.launch()

    def humans(self, g):
        """Called by the engine once the characters are dealt (or a game resumes): the people's seats."""
        with self.lock:
            if not self.seat_map:
                tokens = [(t, p['team']) for t, p in self.people.items() if t in self.dealt]
                self.seat_map = {seat: tok for tok, seat in assign(tokens, g.players, random.Random()).items()}
            timeout = self.config['timer'] or None
            self.seats = {}
            for seat, token in self.seat_map.items():
                if token in self.people:
                    self.people[token]['seat'] = seat
                self.seats[seat] = HumanSeat(seat, timeout, away=lambda t=token: time.time() - self.seen.get(t, 0) > AWAY)
            seats = dict(self.seats)
        self.save()
        return seats

    def client(self):
        """The API client for this game: the house's keys, or the host's own (never the house's then)."""
        import anthropic
        own = self.paid_by == 'player'
        if own and self.keys.get('anthropic'):
            c = anthropic.AsyncAnthropic(api_key=self.keys['anthropic'], max_retries=8, timeout=900)
        else:
            c = make_client()
        c.openai_api_key = self.keys.get('openai') if own else None
        return c

    def ledger_spent(self):
        """What the current game has spent so far (from the store, so it counts every call)."""
        if self.hub and self.game_id:
            return self.hub.store.spent(game=self.game_id)
        return 0.0

    def ledger(self):
        cap = {'house': self.settings.game_cap, 'player': self.settings.byo_game_cap}.get(self.paid_by)
        if not self.hub:
            cap = getattr(self.args, 'cap', None)
        return PlayLedger(self.id, self.game_id, self.paid_by or 'none', cap, self.hub.store if self.hub else None,
                          self.settings.daily_cap if self.hub else None, self.settings.budget_timezone,
                          self.settings.budget_period)

    def _run(self, cfg):
        try:
            result = self.runner(self, cfg)
            with self.lock:
                self.result = result
                if self.ended is None and (result or {}).get('stopped', '') and str(result['stopped']).startswith('halted'):
                    self.ended = 'host'
        except Exception as e:
            print(redact(traceback.format_exc(), self.keys.values()), flush=True)
            with self.lock:
                self.error = redact(f'{type(e).__name__}: {e}', self.keys.values())
        with self.lock:
            if self.status == 'shutdown':  # the server is stopping: the game resumes when it starts again
                return
            self.status, self.finished = 'over', time.time()
            try:
                self.final = self.finish()
            except Exception:
                traceback.print_exc()
            if self.paid_by == 'player':
                self.scrub()
        self.save()

    def scrub(self):
        """Take any trace of the host's key out of the game's logs (providers echo masked keys in errors)."""
        out = Path(self.out) if self.out else None
        keys = list(self.keys.values())
        for name in ('events.jsonl', 'transcript.md', 'result.json', 'calls.jsonl'):
            f = out / name if out else None
            if f and f.exists():
                text = f.read_text()
                clean_ = redact(text, keys)
                if clean_ != text:
                    f.write_text(clean_)
        if self.result:
            self.result = json.loads(redact(json.dumps(self.result), keys))

    def reset(self, token):
        with self.lock:
            self.host(token, 'do that')
            if self.status in ('playing', 'paused'):
                raise ValueError('A game is under way.')
            self.status, self.game, self.result, self.error, self.seats, self.final = 'lobby', None, None, None, {}, None
            self.seat_map, self.dealt = {}, set()
            for p in self.people.values():
                p['seat'] = None
        self.save()

    def end(self, token=None, why='host'):
        """End the game for everyone (the host, or nobody left watching): it halts at its next turn and
        the Grimoire is shown."""
        with self.lock:
            if token is not None:
                self.host(token, 'end the game')
            game = self.game
            if self.status == 'paused':
                self.status, self.ended, self.finished = 'over', why, time.time()
                self.error = self.error or 'The game was paused and has been closed.'
                self.save()
                return
            if self.status != 'playing' or not game or not game.out:
                raise ValueError('No game is under way.')
            self.ended = why
            (game.out / game.STOP).touch()
            seats = list(self.seats.values())
        for seat in seats:  # anyone being waited on passes, so the game reaches its next turn now
            seat.submit({})

    # ---- views -----------------------------------------------------------------------------------
    def touch(self, token):
        if token in self.people:
            self.seen[token] = self.active = time.time()

    def lobby(self, token, base=None):
        with self.lock:
            self.touch(token)
            me = self.people.get(token) if isinstance(token, str) else None
            n = self.config['players']
            tf, os_, mn = SETUPS[n]
            now = time.time()
            base = base or (self.links.get('friends') if self.links else None)
            invite = f'{base}/t/{self.id}' if base and self.hub else base
            names = {m[0]: m[1] for m in MODELS}
            return {
                'table': self.id, 'status': self.status, 'error': self.error, 'game': self.game_id,
                'me': None if not me else {'name': me['name'], 'team': me['team'], 'host': me['host'], 'id': me['id'],
                                           'seated': bool(me['seat']) and token in self.dealt, 'in_game': token in self.dealt},
                'people': [{'id': p['id'], 'name': p['name'], 'host': p['host'], 'you': t == token,
                            'online': now - self.seen.get(t, 0) < 15} for t, p in self.people.items()],
                'config': self.config, 'setup': {'townsfolk': tf, 'outsiders': os_, 'minions': mn, 'demons': 1},
                'sizes': SIZES, 'evil_seats': evil_seats(n), 'problem': self.problem(),
                'models': [{'id': i, 'name': nm, 'elo': elo, 'seat_cost': c, 'provider': provider(i),
                            'free': self.settings.free(i) or i == 'random', 'ready': self.ready(i)}
                           for i, nm, elo, c in MODELS if i == 'random' or provider(i) in ('anthropic', 'openai')],
                'free_models': [names.get(m, m) for m in self.settings.free_models if self.settings.free(m)],
                'keys': sorted(self.keys) if me and me['host'] else [], 'paid_by': self.payer()[0],
                'caps': {'game': self.settings.game_cap, 'byo_game': self.settings.byo_game_cap},
                'timers': TIMERS, 'max_people': MAX_PEOPLE,
                'links': {} if not me else {'friends': invite, 'host': f'{invite}#host={self.host_key}' if invite and me['host'] else None},
                'home': HOME,
            }

    def view(self, game):
        """(events, town-known dead, used ghost votes) for the current game, scanning only new events."""
        evs = list(game.events)
        with self.lock:
            src, n, dead, ghosts = self._scan
            if src is not game or n > len(evs):
                n, dead, ghosts = 0, set(), set()
            public_view(evs, n, dead, ghosts)
            self._scan = (game, len(evs), dead, ghosts)
            return evs, set(dead), set(ghosts)

    @staticmethod
    def seat_view(g, starting, seat, dead, ghosts):
        """What the seat knows about itself and the town."""
        me, start = g[seat], starting or {}
        known = {}
        if start.get(seat) in MINIONS + DEMONS:  # what the evil team was told at the start
            for name, c in start.items():
                if name != seat and c in DEMONS:
                    known[name] = 'Demon'
                elif name != seat and c in MINIONS:
                    known[name] = 'Minion'
        return ({'seat': seat, 'character': me.shown, 'kind': kind(me.shown), 'evil': me.shown in MINIONS + DEMONS,
                 'ability': ABILITY[me.shown], 'known': known, 'bluffs': g.bluffs if start.get(seat) == 'Imp' else [],
                 'alive': seat not in dead},
                [{'name': q.name, 'alive': q.name not in dead, 'ghost': q.name not in ghosts} for q in g.players])

    def finish(self):
        """At the end of a game: the reveal, and each human seat's last view (so a restarted server can
        still show a finished game)."""
        game = self.game
        if not game or not game.g:
            return None
        evs, dead, ghosts = self.view(game)
        me = {seat: self.seat_view(game.g, game.starting, seat, dead, ghosts)[0] for seat in self.seat_map}
        players = self.seat_view(game.g, game.starting, game.g.players[0].name, dead, ghosts)[1]
        return {'reveal': self.reveal(game), 'me': me, 'players': players, 'day': game.day, 'phase': game.phase,
                'spent': round(sum(c.get('cost', 0) for c in game.calls), 2)}

    def reason(self, g):
        stopped = str((self.result or {}).get('stopped') or '')
        if g and g.reason and g.winner:
            return g.reason
        if self.ended == 'host':
            return 'The host ended the game.'
        if self.ended == 'idle':
            return 'Nobody was at the table any more, so the game was closed.'
        if stopped.startswith('budget'):
            cap = self.settings.game_cap if self.paid_by == 'house' else self.settings.byo_game_cap
            return f'The AI budget for this game (${cap:g}) ran out.'
        if stopped.startswith('seat failed'):
            return 'An AI player could not answer, so the game stopped: ' + redact(stopped[len('seat failed: '):], self.keys.values())[:300]
        return redact(stopped or self.error or '', self.keys.values()) or None

    def reveal(self, game):
        g, start = game.g, game.starting or {}
        models = game.meta.get('models', {})
        seat_of = {seat: self.people[t]['name'] for seat, t in self.seat_map.items() if t in self.people}
        return {
            'winner': g.winner, 'reason': self.reason(g),
            'seats': [{'name': q.name, 'character': q.character, 'started': start.get(q.name),
                       'shown': q.shown if q.shown != q.character else None, 'evil': q.evil,
                       'alive': q.alive, 'player': seat_of.get(q.name), 'model': models.get(q.name)}
                      for q in g.players],
            'bluffs': g.bluffs, 'red_herring': g.red_herring,
            'reads': reads(game.out, set(self.seat_map)),
        }

    def state(self, token, since):
        with self.lock:
            p = self.person(token)
            self.touch(token)
            seat, game = (p['seat'] if token in self.dealt else None), self.game
            final = self.final
        if game and game.g and seat:
            evs, dead, ghosts = self.view(game)
            g = game.g
            me, players = self.seat_view(g, game.starting, seat, dead, ghosts)
            day, phase = game.day, game.phase
            spent = round(sum(c.get('cost', 0) for c in game.calls), 2)
        elif seat and final and seat in final['me'] and self.out:
            evs = self.logged_events()
            me, players, day, phase, spent = final['me'][seat], final['players'], final['day'], final['phase'], final['spent']
        else:
            return {'status': self.status, 'seated': False, 'error': self.error, 'table': self.id}
        events = []
        for ev in evs[since:]:
            if ev['kind'] == 'thinking' or not visible(ev, seat):
                continue
            text = render(ev, seat, set(ev['dead']))
            if text is None:
                continue
            events.append({'seq': ev['seq'], 'kind': ev['kind'], 'day': ev['day'], 'phase': ev['phase'],
                           'text': text.strip(), 'data': ev['data'], 'private': ev['to'] != 'public'})
        human = self.seats.get(seat) if game else None
        req = human.pending if human else None
        over = self.status == 'over' or bool(game and game.g and game.g.winner)
        out = {
            'status': self.status, 'seated': True, 'table': self.id, 'game': self.game_id, 'run': self.run,
            'next': len(evs), 'events': events, 'me': me, 'players': players, 'day': day, 'phase': phase,
            'pending': None if req is None else {
                'turn': human.turn, 'kind': req.kind, 'prompt': req.prompt, 'n_targets': req.n_targets,
                'options': req.options, 'alive': req.alive, 'mode': req.mode, 'beat': req.beat,
                'deadline': human.deadline, 'words': WORDS['vote' if req.kind == 'vote' else
                                                           'defense' if req.kind == 'defense' else 'beat'],
                'whisper_words': WORDS['whisper']},
            'waiting': req is None and not over, 'timer': self.config['timer'],
            'spent': spent, 'paid_by': self.paid_by, 'over': over, 'error': self.error, 'host': p['host'], 'home': HOME,
        }
        if over:
            out['reveal'] = (final or {}).get('reveal') or (self.reveal(game) if game and game.g else None)
        return out

    def logged_events(self):
        f = Path(self.out) / 'events.jsonl'
        if not f.exists():
            return []
        evs = []
        for line in f.read_text().splitlines():
            try:
                evs.append(json.loads(line))
            except ValueError:
                pass
        return evs

    def act(self, token, body):
        with self.lock:
            p = self.person(token)
            self.touch(token)
            human = self.seats.get(p['seat']) if token in self.dealt and self.status == 'playing' else None
        if not human or not human.pending:
            raise ValueError('It is not your turn.')
        if not human.submit(clean(body.get('action') or {}), body.get('turn')):
            raise ValueError('That turn has passed.')

    def rules(self):
        return {'text': player_system(self.config['players']),
                'characters': [{'name': c, 'kind': kind(c), 'ability': ABILITY[c]}
                               for c in TOWNSFOLK + OUTSIDERS + MINIONS + DEMONS]}

    def transcript(self, token):
        """The whole game with every seat's reasoning, once it is over."""
        self.person(token)
        out = Path(self.out) if self.out else None
        if self.status != 'over' or not out or not (out / 'transcript.md').exists():
            raise ValueError('The chronicle opens when the game is over.')
        return (out / 'transcript.md').read_text()


def run_game(table, cfg):
    """Play one game for the table (in its game thread); a game with a checkpoint continues from it."""
    from .cli import Shared, play_one
    args = argparse.Namespace(**{**vars(table.args), 'players': str(cfg['players']), 'model': cfg['good_model'],
                                 'good_model': cfg['good_model'], 'evil_model': cfg['evil_model'],
                                 'characters': None, 'probes': cfg.get('probes', False), 'seat_model': None})
    out = Path(cfg['out'])
    if out.exists() and not (out / 'checkpoint.pkl').exists():
        shutil.rmtree(out)  # it never reached its first dusk: start it again
    out.parent.mkdir(parents=True, exist_ok=True)

    def serve_(game):
        with table.lock:
            table.game = game

    async def go():
        os.environ.setdefault('ANTHROPIC_WORKSPACE_ID', args.workspace)
        env = Shared(table.client(), table.ledger(), limiter(args.concurrency))
        return await play_one(args, cfg['seed'], out, env, humans=table.humans, serve=serve_)
    return asyncio.run(go())


# ---- the hub: every table, limits and spend -----------------------------------------------------------
class Bucket:
    """A token bucket per key (an IP): `rate` per second, bursts up to `burst`."""

    def __init__(self, rate, burst):
        self.rate, self.burst, self.state, self.lock = rate, burst, {}, threading.Lock()

    def allow(self, key, now=None):
        now = now or time.monotonic()
        with self.lock:
            tokens, last = self.state.get(key, (self.burst, now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            if len(self.state) > 50_000:
                self.state.clear()
            if tokens < 1:
                self.state[key] = (tokens, now)
                return False
            self.state[key] = (tokens - 1, now)
            return True


class Hub:
    """Every table on this server, the limits on making them, and what the house has spent."""

    def __init__(self, args, settings=None, store=None, runner=None, check_key=check_key):
        self.args = args
        self.settings = settings or Settings()
        d = self.settings.data_dir
        self.store = store or Store(d / 'play.db' if d else ':memory:')
        self.runner, self.check_key = runner, check_key
        self.tables = {}
        self.lock = threading.RLock()
        self.made = {}                       # ip -> deque of table creation times
        self.gets, self.posts = Bucket(40, 80), Bucket(15, 30)
        self.links = {}

    # ---- tables ---------------------------------------------------------------------------------------
    def create(self, ip='local'):
        with self.lock:
            now = time.time()
            times = self.made.setdefault(ip, deque())
            while times and now - times[0] > 3600:
                times.popleft()
            if len(times) >= self.settings.tables_per_hour:
                raise RateLimited('You have opened several tables in the last hour: use one of those, or try later.')
            if len(self.tables) >= self.settings.max_tables:
                raise ValueError('The server is full right now; try again later.')
            times.append(now)
            t = Table(self.args, self.runner, self)
            t.links = self.links
            self.tables[t.id] = t
        t.save()
        return t

    def get(self, tid):
        t = self.tables.get(tid or '')
        if not t:
            raise NotFound('This table does not exist or has closed.')
        return t

    def running(self):
        return [t for t in self.tables.values() if t.status in ('playing',)]

    def spent_today(self):
        return self.store.spent(today(self.settings.budget_timezone, self.settings.budget_period), 'house')

    def admit(self, table, paid_by):
        """Whether one more game can start: the cap on games at once, and for free games the daily budget,
        reserving each running free game's whole per-game cap so the day's spend can't pass the cap."""
        s = self.settings
        with self.lock:
            others = [t for t in self.running() if t is not table]
            if len(others) >= s.max_games:
                raise ValueError(f'All {s.max_games} game slots on this server are in use. Try again in a few minutes.')
            if paid_by != 'house':
                return
            spent = self.spent_today()
            if spent >= s.daily_cap:
                when = 'on the 1st of next month' if s.budget_period == 'month' else 'at midnight'
                period = 'This month' if s.budget_period == 'month' else 'Today'
                raise ValueError(f"{period}'s free AI budget (${s.daily_cap:g}) is used up; it resets {when} {s.budget_timezone}. "
                                 'You can still play against practice bots, or with your own API key.')
            reserved = sum(max(0.0, s.game_cap - t.ledger_spent()) for t in others if t.paid_by == 'house')
            if spent + reserved + s.game_cap > s.daily_cap:
                raise ValueError('The free AI budget is fully booked by games in progress. Try again in a little '
                                 'while, play against practice bots, or use your own API key.')

    def info(self):
        s = self.settings
        names = {m[0]: m[1] for m in MODELS}
        spent = self.spent_today()
        return {'games': len(self.running()), 'max_games': s.max_games, 'home': HOME,
                'free': {'models': [names.get(m, m) for m in s.free_models if s.free(m)], 'daily_cap': s.daily_cap,
                         'budget_timezone': s.budget_timezone, 'budget_period': s.budget_period,
                         'game_cap': s.game_cap, 'left_today': round(max(0.0, s.daily_cap - spent), 2),
                         'open': spent < s.daily_cap and any(s.free(m) for m in s.free_models)}}

    # ---- restart and upkeep --------------------------------------------------------------------------
    def restore(self):
        """Load every saved table; games that were running continue from their last dusk (a game on a
        player's own key waits for the host to paste it again)."""
        for data in self.store.load_tables():
            try:
                t = Table.from_snapshot(self.args, data, self, self.runner)
            except Exception:
                traceback.print_exc()
                continue
            t.links = self.links
            self.tables[t.id] = t
            if t.status == 'playing':
                if t.paid_by == 'player':
                    t.status, t.error = 'paused', 'The server restarted. The host needs to paste their API key again to continue.'
                    t.save()
                else:
                    t.run += 1
                    t.save()
                    t.launch()
        return self

    def sweep(self, now=None):
        """Close what nobody is using: idle lobbies go, idle games end (so they stop spending), and
        finished tables are deleted with their logs after `keep_days`."""
        now = now or time.time()
        idle = self.settings.idle_minutes * 60
        for t in list(self.tables.values()):
            last = max([t.active, *[t.seen.get(tok, 0) for tok in (t.dealt or t.people)]])
            try:
                if t.keep:
                    continue
                if t.status == 'lobby' and now - last > idle:
                    self.drop(t)
                elif t.status in ('playing', 'paused') and now - last > idle:
                    t.end(why='idle')
                elif t.status == 'over':
                    if self.settings.keep_days and now - (t.finished or t.created) > self.settings.keep_days * 86400:
                        self.drop(t, logs=True)
                    elif now - last > max(idle, 6 * 3600):  # nobody came back to the reveal
                        t.keys.clear()
            except ValueError:
                pass

    def drop(self, t, logs=False):
        with self.lock:
            self.tables.pop(t.id, None)
        t.keys.clear()
        self.store.delete_table(t.id)
        if logs:
            for d in t.games:
                shutil.rmtree(d, ignore_errors=True)

    def shutdown(self):
        """The process is stopping (a redeploy): running games resume from their checkpoints next time."""
        for t in list(self.tables.values()):
            if t.status == 'playing':
                with t.lock:
                    t.status = 'shutdown'
                data = t.snapshot()
                data['status'] = 'playing'
                self.store.save_table(t.id, data)


# ---- HTTP ---------------------------------------------------------------------------------------------
# The page's fonts are served from table/fonts, so nothing loads from another host; no inline styles either.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
API = re.compile(r'^/api/t/([A-Za-z0-9_\-]{6,32})/([a-z]+)$')


def serve(hub: Hub, host='0.0.0.0', port=8765, sweep_every=60):
    s = hub.settings

    class Handler(BaseHTTPRequestHandler):
        server_version = 'clocktower'
        sys_version = ''

        def log_message(self, *a):
            pass

        def ip(self):
            # Fly's edge can append its own address to X-Forwarded-For, so counting hops there lumps
            # everyone behind one edge together; Fly-Client-IP is set (and overwritten) by Fly itself.
            if s.ip_header and (h := (self.headers.get(s.ip_header) or '').strip()):
                return h
            fwd = [x.strip() for x in (self.headers.get('X-Forwarded-For') or '').split(',') if x.strip()]
            if s.proxy_hops and len(fwd) >= s.proxy_hops:
                return fwd[-s.proxy_hops]
            return self.client_address[0]

        def send(self, code, body, ctype='application/json', extra=None):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            if ctype.startswith('text/html'):
                self.send_header('Content-Security-Policy', CSP)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        def reply(self, fn):
            try:
                out = fn()
            except PermissionError as e:
                return self.send(403, json.dumps({'error': str(e)}))
            except NotFound as e:
                return self.send(404, json.dumps({'error': str(e)}))
            except RateLimited as e:
                return self.send(429, json.dumps({'error': str(e)}))
            except (ValueError, KeyError, TypeError) as e:
                return self.send(400, json.dumps({'error': str(e)}))
            if isinstance(out, str):
                return self.send(200, out, 'text/plain; charset=utf-8')
            self.send(200, json.dumps(out if out is not None else {'ok': True}))

        def base(self):
            if s.public_url:
                return s.public_url
            host = self.headers.get('X-Forwarded-Host') or self.headers.get('Host') or ''
            proto = self.headers.get('X-Forwarded-Proto') or 'http'
            if not host or host.split(':')[0] in ('localhost', '127.0.0.1'):
                return hub.links.get('friends')
            return f'{proto}://{host}'

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not hub.gets.allow(self.ip()):
                return self.send(429, '{"error": "Too many requests: slow down."}', extra={'Retry-After': '2'})
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            token = self.headers.get('X-Token') or q.get('token')
            if url.path == '/healthz':
                return self.send(200, json.dumps({'ok': True, 'games': len(hub.running()), 'tables': len(hub.tables)}))
            if url.path == '/api/info':
                return self.reply(hub.info)
            m = API.match(url.path)
            if m:
                tid, what = m.groups()
                routes = {
                    'lobby': lambda t: t.lobby(token, self.base()),
                    'state': lambda t: t.state(token, max(0, int(q.get('since', 0)))),
                    'rules': lambda t: t.rules(),
                    'transcript': lambda t: t.transcript(token),
                }
                if what not in routes:
                    return self.send(404, '{}')
                return self.reply(lambda: routes[what](hub.get(tid)))
            name = 'index.html' if url.path in ('/', '/index.html') or re.match(r'^/t/[A-Za-z0-9_\-]+/?$', url.path) \
                else url.path.lstrip('/')
            f = (PAGE / name).resolve()
            if PAGE.resolve() in f.parents and f.is_file() and f.suffix in TYPES:
                return self.send(200, f.read_bytes(), TYPES[f.suffix])
            self.send(404, '{}')

        def origin_ok(self):
            origin = (self.headers.get('Origin') or '').rstrip('/')
            if not origin:
                return True  # not a browser's cross-site request
            allowed = set(s.allowed_origins) | ({s.public_url} if s.public_url else set())
            if origin in allowed:
                return True
            host = self.headers.get('X-Forwarded-Host') or self.headers.get('Host') or ''
            return urlparse(origin).netloc == host

        def do_POST(self):
            ip = self.ip()
            if not hub.posts.allow(ip):
                return self.send(429, '{"error": "Too many requests: slow down."}', extra={'Retry-After': '2'})
            if not self.origin_ok():
                return self.send(403, '{"error": "Cross-site request refused."}')
            try:
                n = int(self.headers.get('Content-Length', 0))
            except ValueError:
                return self.send(400, '{"error": "bad length"}')
            if n > BODY_LEN:
                return self.send(413, '{"error": "Too long."}')
            try:
                body = json.loads(self.rfile.read(n) or b'{}')
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self.send(400, '{"error": "bad JSON"}')
            url = urlparse(self.path)
            token = self.headers.get('X-Token') or body.get('token')
            if url.path == '/api/new':
                return self.reply(lambda: {'table': (t := hub.create(ip)).id, 'host_key': t.host_key})
            m = API.match(url.path)
            if not m:
                return self.send(404, '{}')
            tid, what = m.groups()
            routes = {
                'join': lambda t: {'token': t.join(body.get('name'), body.get('team'), body.get('host'))},
                'me': lambda t: t.update_me(token, body.get('name'), body.get('team')),
                'host': lambda t: t.claim_host(token, body.get('key')),
                'config': lambda t: t.set_config(token, body),
                'key': lambda t: t.set_key(token, body.get('provider'), body.get('key')),
                'kick': lambda t: t.kick(token, body.get('target')),
                'start': lambda t: t.start(token),
                'resume': lambda t: t.resume(token),
                'reset': lambda t: t.reset(token),
                'act': lambda t: t.act(token, body),
                'end': lambda t: t.end(token),
            }
            if what not in routes:
                return self.send(404, '{}')
            self.reply(lambda: routes[what](hub.get(tid)))

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    lan = lan_address()
    local = f'http://localhost:{port}'
    hub.links.update({'friends': s.public_url or (f'http://{lan}:{port}' if lan and host in ('0.0.0.0', '') else local)})

    def upkeep():
        while True:
            time.sleep(sweep_every)
            try:
                hub.sweep()
            except Exception:
                traceback.print_exc()
    threading.Thread(target=upkeep, daemon=True, name='sweep').start()
    return server


def main(args):
    """`python -m clocktower play`: a server for many tables. Run on a laptop, it also opens one table
    and prints its links; hosted (PLAY_PUBLIC_URL set), people open tables from the home page."""
    import signal
    settings = Settings.from_env(data_dir=getattr(args, 'data', None) or Path(__file__).resolve().parent.parent / 'games' / 'play')
    hub = Hub(args, settings).restore()
    server = serve(hub, args.host, args.port)

    def stop(*_):  # everything is already saved; exit at once (in-flight API calls would hold the exit)
        hub.shutdown()
        os._exit(0)
    signal.signal(signal.SIGTERM, stop)
    if settings.public_url:
        print(f'\n  Clocktower tables at {settings.public_url} (port {args.port}); data in {settings.data_dir}\n', flush=True)
    else:
        t = hub.create('local')
        t.keep = True
        local = f'http://localhost:{args.port}/t/{t.id}'
        print(f'\n  Clocktower table is open.\n'
              f'  You (the host):  {local}#host={t.host_key}\n'
              f'  Friends:         {hub.links["friends"]}/t/{t.id}   (same Wi-Fi; or share a tunnel URL, see README)\n'
              f'  Free AI models:  {", ".join(m for m in settings.free_models)} (PLAY_FREE_MODELS=all for every model with a key)\n',
              flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        hub.shutdown()
