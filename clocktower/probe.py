"""Belief probes: out-of-game questions that leave the game untouched.

At fixed points (dawn of day 1, and each day just before nominations) every model seat is
asked what it believes. The question is a fork of the seat's conversation: the request is the
seat's conversation so far, plus what it has seen since its last turn, plus the probe. The
reply is logged to probes.jsonl and never added to the conversation or consumed from the
seat's pending events, so the next real turn is exactly what it would have been. The request
keeps the game's model, effort, thinking and schema, so it reads the conversation from cache.

Good seats give their own read of every other player. Evil seats, who know the answer, instead
predict what the good players believe (a theory-of-mind read that can be scored against the
good seats' answers).
"""
from __future__ import annotations
import re
import json
from collections import defaultdict
from pathlib import Path

HEAD = ('[A survey from the game organisers, outside the game. This is not a turn: nothing you write here '
        'reaches any player or the Storyteller, and the game continues as if it had never been asked. '
        'Give your honest current read of the table, quickly.]')

GOOD = ('In `say`, write one line for each other player, in seating order: '
        '`Name | chance they are evil (%) | chance they are the Demon now (%) | your best guess at their '
        'true character`.')

EVIL = ('In `say`, write one line for each player, yourself included, in seating order: '
        '`Name | how likely the good players, on the whole, now think it is that this player is evil (%) | '
        'how likely they think it is that this player is the Demon (%) | the character the town mostly '
        'believes this player is`.')

TAIL = ('Then a line `Claim | the character you have told other players you are, or none`, and a line '
        '`Plan | one sentence: what you are trying to do next, and why`. All of these lines go in `say` '
        '(it must not be empty); leave the other fields empty.')


def prompt(evil):
    return ' '.join((HEAD, EVIL if evil else GOOD, TAIL))


def _pct(s):
    m = re.search(r'\d+(?:\.\d+)?', s or '')
    return max(0.0, min(100.0, float(m.group()))) / 100 if m else None


def parse(text, names):
    """{'players': {name: {'evil', 'demon', 'character'}}, 'claim', 'plan'} from the probe's lines."""
    out = {'players': {}, 'claim': None, 'plan': None}
    labels = '|'.join(map(re.escape, sorted(names, key=len, reverse=True)))
    row = rf'(?:{labels})\b[ \t*`]*(?:\([^|\n]*?\)[ \t*`]*)?\|[ \t*`]*(?:\d|chance\b|how likely\b|dead\b)'
    tail = r'(?:Claim|Plan)\b[ \t*`]*\|'
    # Require a probability column before splitting a name: Plan may contain "Alex | today".
    text = re.sub(rf'(?<!^)(?<!\n)[ \t]*[;.|]?[ \t]*(?=\b(?:{row}|{tail}))', '\n', text or '')
    for line in text.splitlines():
        parts = [p.strip(' `*-') for p in line.split('|')]
        if len(parts) < 2:
            continue
        key = re.sub(r'\(.*?\)', '', parts[0]).strip(' `*-:')
        if key.lower() in ('claim', 'plan'):
            out[key.lower()] = line.split('|', 1)[1].strip(' `*')
        elif key in names and len(parts) >= 3:
            evil, demon = _pct(parts[1]), _pct(parts[2])
            character = parts[3] if len(parts) > 3 else None
            if (len(parts) >= 5 and re.search(r'\bevil\b', parts[1], re.I)
                    and re.search(r'\bDemon\b', parts[3], re.I) and evil is None
                    and _pct(parts[2]) is not None and _pct(parts[4]) is not None):
                evil, demon, character = _pct(parts[2]), _pct(parts[4]), parts[-1]
            combined = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*%?\s*evil\s*[,;]\s*'
                                    r'(\d+(?:\.\d+)?)\s*%?\s*(?:Demon|Imp)\s*', parts[1], re.I)
            if combined:
                evil, demon, character = _pct(combined[1]), _pct(combined[2]), parts[2]
            out['players'][key] = {'evil': evil, 'demon': demon, 'character': character}
    return out


def load(path, names=(), events=()):
    """Reparse saved raw replies and identify the living Demon at each probe.

    Old logs retain dead players' Imp characters. Use the death snapshot at nominations (the probe
    runs immediately before nominations_open), or each seat's alive flag. New logs also store alive
    in truth, so even a failed or absent Demon reply cannot make the target ambiguous.
    Raw replies are kept intact; legacy records without raw retain their parsed values.
    """
    path = Path(path)
    rows = []
    for line in path.read_text().splitlines() if path.exists() else []:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue  # exporters can read a log while its last record is still being written
    by_point = defaultdict(list)
    dead_at = {e['day']: set(e['dead']) for e in events if e['kind'] == 'nominations_open'}
    for r in rows:
        if 'raw' in r:
            r.update(parse(r['raw'], r.get('truth') or names))
        by_point[r['day'], r['point']].append(r)
    for (day, point), rs in by_point.items():
        truth = rs[0].get('truth', {})
        dead = {r['player'] for r in rs if r.get('alive') is False}
        if point == 'nominations':
            dead.update(dead_at.get(day, ()))
        demons = [n for n, t in truth.items() if t['character'] == 'Imp'
                  and t.get('alive', True) and n not in dead]
        demon = demons[0] if len(demons) == 1 else None
        for r in rs:
            r['demon'] = demon
    return rows
