"""Build the public website (clocktowerbench.com) as static files: `python -m clocktower.export`.

Copies the hand-written pages in site/src/ into site/dist/ (wrapping each in site/src/layout.html), and writes
the data the pages read:

    data/ratings.json      the 2026 fit (docs/plans/f2-ratings.json), plus head-to-head game counts
    data/charts.json       small blog-figure series (village belief by day, evil tilt, mixed team)
    data/index.json        one row per game in the library (filters, cards)
    data/highlights.json   site/content/highlights.json with each quote located in its game (day + event)
    data/games/<id>.json.gz  one compact game per file for the replay viewer (gzip; the page inflates it)

Which games: every game in the 2026 rating fit (`ratings.BATCHES` minus `ratings.DROPPED`), the 20 Opus 4.8
v16 games the fit drops (shown, marked unrated), and the mixed-team games (v17/b1-*, v17/b2-*).

    python -m clocktower.export --games /home/user/clocktower/games          # full build into site/dist
    python -m clocktower.export --games ... --limit 20                       # a quick build with 20 games
    python -m clocktower.export --no-games                                   # pages and index data only
"""
from __future__ import annotations
import argparse
import glob
import gzip
import hashlib
import json
import os
import re
import shutil
from collections import defaultdict
from pathlib import Path

from . import characters
from .ratings import BATCHES, DROPPED

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
MIXED_BATCHES = ['v17/b1-*', 'v17/b2-*']
EVIL = {'Imp', 'Poisoner', 'Spy', 'Scarlet Woman', 'Baron'}
MINIONS = ['Poisoner', 'Spy', 'Scarlet Woman', 'Baron']

# Display names and labs for every model in the exported games.
MODELS = {
    'claude-opus-4-6': ('Opus 4.6', 'Anthropic'), 'gpt-5.4': ('GPT-5.4', 'OpenAI'),
    'claude-opus-4-7': ('Opus 4.7', 'Anthropic'), 'gpt-5.5': ('GPT-5.5', 'OpenAI'),
    'claude-opus-4-8': ('Opus 4.8', 'Anthropic'), 'claude-fable-5': ('Fable 5', 'Anthropic'),
    'gpt-5.6-sol': ('GPT-5.6 Sol', 'OpenAI'), 'claude-fable-5-1': ('Fable 5.1', 'Anthropic'),
    'gpt-6-astra': ('GPT-6 Astra', 'OpenAI'), 'claude-opus-5-5': ('Opus 5.5', 'Anthropic'),
    'gpt-6.1-sol': ('GPT-6.1 Sol', 'OpenAI'), 'claude-fable-5-2': ('Fable 5.2', 'Anthropic'),
}
MIXED_ID = 'mixed:claude-opus-5-5+gpt-5.6-sol'

# Game vocabulary beyond the characters, for the hover glossary (data/glossary.json). Characters come from
# characters.ABILITY. Keys are matched as whole words, case-sensitively, with an optional plural s.
TERMS = {
    'Demon': ('Demon', 'evil', 'The lead evil player: kills one player each night. Good wins when the Demon dies. '
                               'In Trouble Brewing the Demon is the Imp.'),
    'Minion': ('Minion', 'evil', "The Demon's helpers. Minions start the game knowing who the Demon is and who each other are. "
                                 'In Trouble Brewing: Poisoner, Spy, Scarlet Woman, Baron.'),
    'Townsfolk': ('Townsfolk', 'good', 'Good characters whose ability helps the town: most of the table.'),
    'Outsider': ('Outsider', 'good', 'Good characters whose ability is a handicap: Butler, Drunk, Recluse, Saint.'),
    'Storyteller': (None, None, 'The referee: deals the characters, runs the nights and decides what ambiguous abilities '
                                'show. In this eval the Storyteller is a fixed script, not a model.'),
    'Grimoire': (None, None, "The Storyteller's record of every player's true character and status. Only the Spy sees it."),
    'poisoned': (None, None, "A poisoned player's ability does not work and any information it gives may be false, "
                             'and they are not told.'),
    'ghost vote': (None, None, 'A dead player keeps one vote for the rest of the game, usable once.'),
    'red herring': (None, None, 'A good player who registers as the Demon to the Fortune Teller for the whole game.'),
    'Demon bluff': (None, None, 'A good character not in play, shown to the Demon at the start, so evil can claim it safely.'),
    'starpass': (None, None, 'The Imp kills itself at night so a Minion becomes the Imp. The town usually reads a night '
                             'death as proof of good, so the Demon moves to someone already trusted.'),
    'bus': (None, None, 'Evil voting to execute one of its own, to look good or to spend a Minion and save the Demon.'),
}
TERMS['star-pass'] = TERMS['star pass'] = TERMS['starpass']   # spellings the models use
TERMS['buss'] = TERMS['bus']                                   # "bussed", "bussing"


def glossary():
    """{term: {k: kind, team: 'good'|'evil', x: text}} for every character and general term."""
    out = {}
    for c, text in characters.ABILITY.items():
        out[c] = {'k': characters.kind(c), 'team': 'evil' if characters.is_evil_character(c) else 'good', 'x': text}
    for t, (k, team, text) in TERMS.items():
        out[t] = {'k': k, 'team': team, 'x': text}
    return out


# Anything that looks like a credential must never reach the published data.
SECRET = re.compile(r'sk-ant-[A-Za-z0-9_-]{8,}|sk-(?:proj-)?[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|'
                    r'AKIA[0-9A-Z]{16}|xox[bp]-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{20,}|sk_[a-f0-9]{32,}')


def _json(path):
    return json.loads(Path(path).read_text())


def team_id(models):
    """One id per team: a model id, or MIXED_ID for the Opus 5.5 + GPT-5.6 Sol mixed team."""
    if not models:
        return 'unknown'
    ms = sorted(set(models.split(',')))
    return ms[0] if len(ms) == 1 else 'mixed:' + '+'.join(ms)


def safe_name(gid):
    return gid.replace('/', '--')


def twin_of(gid):
    return gid[:-5] if gid.endswith('-swap') else gid + '-swap'


def select(games_root):
    """[(game id, group)] with group 'rated', 'unrated' (Opus 4.8's v16 games) or 'mixed'."""
    out = []
    for pattern, group in [(b, 'rated') for b in BATCHES] + [(b, 'mixed') for b in MIXED_BATCHES]:
        for d in sorted(glob.glob(f'{games_root}/{pattern}/game-*')):
            if not os.path.exists(d + '/result.json') or not os.path.exists(d + '/events.jsonl'):
                continue
            if _json(d + '/result.json').get('winner') not in ('good', 'evil'):
                continue
            g = group
            if group == 'rated' and DROPPED[0] in d + '/':
                c = _json(d + '/config.json')
                if DROPPED[1] in (c['good_model'], c['evil_model']):
                    g = 'unrated'
            out.append((os.path.relpath(d, games_root), g))
    return out


ACTOR = {'say': 'speaker', 'whisper': 'from', 'vote': 'voter', 'nomination': 'nominator', 'defense': 'nominee',
         'night_choice': 'player', 'slayer': 'shooter'}
SECTION = re.compile(r'Day (\d+) · (private time|town square|beat) (\d+)')  # v1-v2 had one kind of round: 'beat'


def item(ev):
    """The compact viewer item for one engine event, or None to drop it."""
    k, d, s = ev['kind'], ev['data'], ev['seq']
    if k == 'say':
        return {'k': 'say', 's': s, 'p': d['speaker'], 'x': d['text']}
    if k == 'whisper':
        return {'k': 'w', 's': s, 'p': d['from'], 'to': d['to'], 'x': d['text']}
    if k == 'nomination':
        return {'k': 'nom', 's': s, 'p': d['nominator'], 'n': d['nominee'], 'x': d.get('text') or ''}
    if k == 'defense':
        return {'k': 'def', 's': s, 'p': d['nominee'], 'x': d.get('text') or ''}
    if k == 'vote':
        it = {'k': 'v', 's': s, 'p': d['voter'], 'y': 1 if d['yes'] else 0}
        if d.get('ghost'): it['g'] = 1
        if d.get('text'): it['x'] = d['text']
        return it
    if k == 'vote_result':
        return {'k': 'vr', 's': s, 'n': d['nominee'], 'c': d['votes'], 'need': d['needed'], 'o': d['outcome']}
    if k == 'execution':
        return {'k': 'ex', 's': s, 'p': d['player'], 'died': 1 if d['died'] else 0}
    if k == 'no_execution':
        return {'k': 'noex', 's': s}
    if k == 'slayer':
        return {'k': 'sl', 's': s, 'p': d['shooter'], 'n': d['target'], 'died': 1 if d['died'] else 0}
    if k == 'virgin':
        return {'k': 'vg', 's': s, 'p': d['nominator'], 'n': d.get('nominee')}
    if k == 'dawn':
        return {'k': 'dawn', 's': s, 'x': d.get('narration') or '', 'dd': d['deaths']}
    if k == 'game_over':
        return {'k': 'end', 's': s, 'w': d['winner'], 'x': d['reason']}
    if k == 'night_choice':
        return {'k': 'nc', 's': s, 'p': d['player'], 'r': d['role'], 'n': d['targets'], 'a': 1}
    if k == 'info':
        return {'k': 'info', 's': s, 'to': ev['to'], 'x': d['text'], 'a': 1}
    if k == 'death':
        return {'k': 'death', 's': s, 'p': d['player'], 'x': d.get('cause', ''), 'a': 1}
    if k == 'becomes':
        return {'k': 'bec', 's': s, 'p': d['player'], 'c': d['character'], 'a': 1}
    if k == 'notice':
        if d['text'].startswith('('):  # turn bookkeeping ("your nomination was not taken"): noise for a reader
            return None
        it = {'k': 'note', 's': s, 'x': d['text']}
        if ev['to'] != 'public':
            it['to'], it['a'] = ev['to'], 1
        return it
    return None  # header, intro, setup, st_choice, nominations_open, thinking: handled by the caller or dropped


def beliefs(path, seats):
    """Per day: the good players' average P(Demon) for each player (the probe before nominations, else dawn),
    and each good prober's own numbers. Probabilities in whole percent."""
    if not os.path.exists(path):
        return []
    names = [s['n'] for s in seats]
    by = defaultdict(lambda: defaultdict(dict))  # (day, point) -> prober -> target -> pct
    alive = {}
    for line in Path(path).read_text().splitlines():
        try:
            p = json.loads(line)
        except ValueError:
            continue
        if p.get('team') != 'good' or not isinstance(p.get('players'), dict):
            continue
        key = (p['day'], p['point'])
        for t, v in p['players'].items():
            if t in names and isinstance(v, dict) and isinstance(v.get('demon'), (int, float)):
                by[key][p['player']][t] = round(100 * max(0.0, min(1.0, v['demon'])))
        alive[(key, p['player'])] = bool(p.get('alive', True))
    out = []
    for day in sorted({k[0] for k in by}):
        key = (day, 'nominations') if (day, 'nominations') in by else (day, 'dawn')
        probers = by[key]
        living = [p for p in probers if alive.get((key, p))] or list(probers)
        avg = {}
        for t in names:
            vals = [probers[p][t] for p in living if t in probers[p]]
            if vals:
                avg[t] = round(sum(vals) / len(vals))
        out.append({'d': day, 'pt': key[1], 'n': len(living), 'v': avg, 'by': {p: dict(v) for p, v in probers.items()}})
    return out


def export_game(d, gid, group=None):
    """The compact game record the viewer reads (see site/src/assets/viewer.js)."""
    d = Path(d)
    config = json.loads((d / 'config.json').read_text())
    result = json.loads((d / 'result.json').read_text())
    events = [json.loads(l) for l in (d / 'events.jsonl').read_text().splitlines() if l.strip()]
    setup = next((e['data'] for e in events if e['kind'] == 'setup'), None)
    if setup is None:  # the first games (v1-v2) logged the Grimoire only in result.json; seats are in seating order
        setup = {'seats': [{'name': n, 'character': c, 'shown': result.get('drunk_as') or c if c == 'Drunk' else c}
                           for n, c in (result.get('starting') or {}).items()],
                 'bluffs': result.get('bluffs') or [], 'red_herring': result.get('red_herring')}
    models = result.get('models') or {}
    final = result.get('final') or {}
    mids = sorted(set(models.values()))
    seats = []
    for s in setup['seats']:
        seat = {'n': s['name'], 'c': s['character'], 'e': 1 if s['character'] in EVIL else 0,
                'm': mids.index(models[s['name']]) if s['name'] in models else -1}
        if s['shown'] != s['character']:
            seat['s'] = s['shown']
        if final.get(s['name']) and final[s['name']] != s['character']:
            seat['f'] = final[s['name']]
        seats.append(seat)
    inplay = {s['c'] for s in seats}
    intros = {e['to'][0]: e['data']['text'] for e in events if e['kind'] == 'intro' and isinstance(e['to'], list)}

    days, sec, wsec, pending = {}, None, None, {}  # wsec: where whispers go when a v1-v2 'beat' mixes both

    def day_of(n):
        if n not in days:
            days[n] = {'d': n, 'secs': [], 'dead': []}
        return days[n]

    def open_section(n, t, b=0):
        nonlocal sec, wsec
        sec = {'t': t, 'b': b, 'it': []}
        day_of(n)['secs'].append(sec)
        wsec = None
        pending.clear()
        return sec

    for ev in events:
        k, n = ev['kind'], ev['day']
        if n >= 1:
            day_of(n)['dead'] = ev.get('dead') or []
        if k == 'header':
            text = ev['data']['text']
            m = SECTION.match(text)
            if text.startswith('Night'):
                open_section(n, 'night')
            elif m and m.group(2) == 'beat':  # whispers and public speech shared one round: split them
                w = open_section(n, 'private', int(m.group(3)))
                open_section(n, 'square', int(m.group(3)))
                wsec = w
            elif m:
                open_section(n, 'private' if m.group(2) == 'private time' else 'square', int(m.group(3)))
            continue
        if k == 'nominations_open':
            open_section(n, 'noms')
            continue
        if k == 'dawn':
            open_section(n, 'dawn')
        if sec is None or n < 1:
            continue
        if k == 'thinking':
            p = ev['data']['player']
            th = {'k': 'th', 's': ev['seq'], 'p': p, 'x': ev['data']['text'], 'why': ev['data'].get('kind', ''), 'a': 1}
            sec['it'].append(th)
            pending[p] = (th, sec)
            continue
        it = item(ev)
        if it is None:
            continue
        actor = ev['data'].get(ACTOR.get(k, ''), None)
        if actor and actor in pending:  # this turn's private reasoning travels with the move it led to
            th, where = pending.pop(actor)
            it['t'] = th['x']
            where['it'].remove(th)
        (wsec if wsec is not None and it['k'] == 'w' else sec)['it'].append(it)

    # v1-v3 configs name one model for both sides (`model`); later ones name each side.
    good = config.get('good_model') or config.get('model')
    evil = config.get('evil_model') or config.get('model')
    return {
        'id': gid, 'batch': gid.rsplit('/', 1)[0], 'group': group,
        'good': team_id(good), 'evil': team_id(evil), 'models': mids,
        'winner': result['winner'], 'reason': result.get('reason', ''), 'days': result.get('days'),
        'players': len(seats), 'minions': [m for m in MINIONS if m in inplay], 'seed': result.get('seed'),
        'twin': twin_of(gid), 'protocol': config.get('protocol'),
        'seats': seats, 'bluffs': setup.get('bluffs', []), 'rh': setup.get('red_herring'),
        'intros': intros,
        'days_': [days[k] for k in sorted(days)],
        'belief': beliefs(d / 'probes.jsonl', seats),
    }


def summary(g, available):
    """The library row for one game."""
    demon = next((s['n'] for s in g['seats'] if s['c'] == 'Imp'), None)
    b_last = g['belief'][-1]['v'].get(demon) if g['belief'] and demon else None
    whispers = sum(1 for day in g['days_'] for sec in day['secs'] for it in sec['it'] if it['k'] == 'w')
    return {'id': g['id'], 'batch': g['batch'], 'group': g['group'], 'good': g['good'], 'evil': g['evil'],
            'winner': g['winner'], 'reason': g['reason'], 'days': g['days'], 'players': g['players'],
            'minions': g['minions'], 'twin': g['twin'] if g['twin'] in available else None, 'protocol': g['protocol'],
            'whispers': whispers, 'demonBelief': b_last}


def find_quote(g, quote):
    """(day, seq, in_reasoning) of the first item whose text, or else whose attached reasoning, contains the quote
    (ignoring case and spacing); (None, None, False) when it is nowhere."""
    norm = lambda s: re.sub(r'\s+', ' ', s or '').lower().replace('’', "'")
    q = norm(quote)
    for field in ('x', 't'):
        for day in g['days_']:
            for sec in day['secs']:
                for it in sec['it']:
                    if q in norm(it.get(field)):
                        return day['d'], it['s'], field == 't' or it['k'] == 'th'
    return None, None, False


def head_to_head(games_root):
    """{'good|evil': [good wins, games]} over the rated games, for the leaderboard's grid tooltips."""
    h = defaultdict(lambda: [0, 0])
    for gid, group in select(games_root):
        if group != 'rated':
            continue
        c = _json(f'{games_root}/{gid}/config.json')
        r = _json(f'{games_root}/{gid}/result.json')
        key = c['good_model'] + '|' + c['evil_model']
        h[key][0] += r['winner'] == 'good'
        h[key][1] += 1
    return dict(h)


def check_secrets(text, where):
    m = SECRET.search(text)
    if m:
        raise SystemExit(f'refusing to publish {where}: it contains something that looks like a credential '
                         f'({m.group(0)[:6]}...)')


def render_pages(src, out, config):
    """Wrap each page fragment in the layout. A fragment starts with <!-- title: ... | description: ... | nav: ... -->."""
    layout = (src / 'layout.html').read_text()
    for page in sorted((src / 'pages').glob('*.html')):
        body = page.read_text()
        meta = {}
        m = re.match(r'\s*<!--(.*?)-->', body, re.S)
        if m:
            for part in m.group(1).split('|'):
                if ':' in part:
                    k, v = part.split(':', 1)
                    meta[k.strip()] = v.strip()
            body = body[m.end():]
        html = (layout.replace('{{title}}', meta.get('title', 'Clocktower Bench'))
                .replace('{{description}}', meta.get('description', ''))
                .replace('{{page}}', meta.get('nav', page.stem))
                .replace('{{canonical}}', f"https://{config.get('domain', '')}/{'' if page.stem == 'index' else page.name}")
                .replace('{{body}}', body.strip()))
        (out / page.name).write_text(stamp_assets(html, out))


def stamp_assets(html, out):
    """Append ?v=<content hash> to each local script and stylesheet link, so browsers fetch changed assets after a
    deploy instead of serving a cached copy (the hosts send no cache headers)."""
    def tag(m):
        path = out / m.group(2)
        if not path.exists():
            return m.group(0)
        return f'{m.group(1)}="{m.group(2)}?v={hashlib.sha1(path.read_bytes()).hexdigest()[:8]}"'
    return re.sub(r'(src|href)="((?:assets/[^"?]+\.(?:css|js))|config\.js)"', tag, html)


def build(games_root=ROOT / 'games', out=SITE / 'dist', src=SITE / 'src', content=SITE / 'content',
          limit=None, with_games=True, media=None, pages_only=False):
    games_root, out, src, content = Path(games_root), Path(out), Path(src), Path(content)
    config = json.loads((src / 'config.json').read_text()) if (src / 'config.json').exists() else {}
    if pages_only:  # re-render pages, assets and config over an existing build, keeping its data
        shutil.rmtree(out / 'assets', ignore_errors=True)
        shutil.copytree(src / 'assets', out / 'assets')
        (out / 'config.js').write_text('window.CT_CONFIG = ' + json.dumps(config, indent=2) + ';\n')
        (out / 'data').mkdir(exist_ok=True)
        (out / 'data' / 'glossary.json').write_text(json.dumps(glossary(), separators=(',', ':'), ensure_ascii=False))
        render_pages(src, out, config)
        print(f'Rendered pages into {out}')
        return None
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src / 'assets', out / 'assets')
    (out / 'data' / 'games').mkdir(parents=True)
    (out / 'config.js').write_text('window.CT_CONFIG = ' + json.dumps(config, indent=2) + ';\n')
    if config.get('domain'):
        (out / 'CNAME').write_text(config['domain'] + '\n')
    (out / '.nojekyll').write_text('')
    shutil.copy(src / '404.html', out / '404.html') if (src / '404.html').exists() else None
    render_pages(src, out, config)

    # Ratings, model names, head-to-head counts, blog-figure series.
    ratings = json.loads((ROOT / 'docs/plans/f2-ratings.json').read_text())
    ratings['names'] = {k: v[0] for k, v in MODELS.items()}
    ratings['names'][MIXED_ID] = 'Opus 5.5 + GPT-5.6 Sol'
    ratings['labs'] = {k: v[1] for k, v in MODELS.items()}
    ratings['h2h'] = head_to_head(games_root)
    (out / 'data' / 'ratings.json').write_text(json.dumps(ratings, separators=(',', ':')))
    charts = json.loads((content / 'charts.json').read_text())
    tilt = ROOT / 'docs/charts/evil-tilt.json'
    if tilt.exists():
        charts['evil_tilt'] = json.loads(tilt.read_text())
    mixed = ROOT / 'docs/analysis/b2-mixed-rating.json'
    if mixed.exists():
        m = json.loads(mixed.read_text())
        charts['mixed'] = {k: m[k] for k in ('combined', 'detection', 'deception', 'record_by_opponent', 'p_effect_negative')}
    (out / 'data' / 'charts.json').write_text(json.dumps(charts, separators=(',', ':')))
    (out / 'data' / 'glossary.json').write_text(json.dumps(glossary(), separators=(',', ':'), ensure_ascii=False))

    # Media: the explainer video and its poster, when a local copy is given.
    (out / 'media').mkdir()
    for name in ('poster.jpg',):
        if (content / name).exists():
            shutil.copy(content / name, out / 'media' / name)
    if media and Path(media).exists():
        shutil.copy(media, out / 'media' / Path(media).name)

    # Games.
    chosen = select(games_root)
    if limit:
        keep = {h['id'] for h in json.loads((content / 'highlights.json').read_text())}
        chosen = [c for c in chosen if c[0] in keep] + [c for c in chosen if c[0] not in keep][:limit]
    available = {gid for gid, _ in chosen}
    rows, exported, total = [], {}, 0
    for gid, group in chosen:
        g = export_game(games_root / gid, gid, group)
        text = json.dumps(g, separators=(',', ':'), ensure_ascii=False)
        check_secrets(text, gid)
        rows.append(summary(g, available))
        if with_games or gid in {h['id'] for h in json.loads((content / 'highlights.json').read_text())}:
            exported[gid] = g
            blob = gzip.compress(text.encode(), compresslevel=9, mtime=0)
            (out / 'data' / 'games' / (safe_name(gid) + '.json.gz')).write_bytes(blob)
            total += len(blob)
    (out / 'data' / 'index.json').write_text(json.dumps(rows, separators=(',', ':')))

    # Highlights, each quote located in its game.
    hl = json.loads((content / 'highlights.json').read_text())
    for h in hl:
        g = exported.get(h['id'])
        if g is None:
            continue
        row = next(r for r in rows if r['id'] == h['id'])
        h.update({k: row[k] for k in ('good', 'evil', 'winner', 'days', 'players')})
        if h.get('quote'):
            h['day'], h['seq'], h['think'] = find_quote(g, h['quote'])
            if h['seq'] is None:
                print(f"warning: highlight quote not found in {h['id']}: {h['quote']!r}")
    (out / 'data' / 'highlights.json').write_text(json.dumps(hl, separators=(',', ':'), ensure_ascii=False))

    for p in out.rglob('*'):
        if p.is_file() and p.suffix in ('.json', '.js', '.html'):
            check_secrets(p.read_text(), str(p.relative_to(out)))
    size = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    print(f'Built {out}: {len(rows)} games ({len(exported)} exported, {total / 1e6:.1f} MB gzipped), '
          f'site {size / 1e6:.1f} MB')
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description='Build the public website into site/dist.')
    ap.add_argument('--games', default=str(ROOT / 'games'), help='games root holding v16/ and v17/ logs')
    ap.add_argument('--out', default=str(SITE / 'dist'))
    ap.add_argument('--limit', type=int, help='export only the highlight games plus this many others (a quick build)')
    ap.add_argument('--no-games', action='store_true', help='skip per-game files (except highlights)')
    ap.add_argument('--media', help='a local copy of explainer-three-tricks.mp4 to publish with the site')
    ap.add_argument('--pages-only', action='store_true', help='re-render pages and assets over an existing build (fast)')
    a = ap.parse_args(argv)
    build(a.games, a.out, limit=a.limit, with_games=not a.no_games, media=a.media, pages_only=a.pages_only)


if __name__ == '__main__':
    main()
