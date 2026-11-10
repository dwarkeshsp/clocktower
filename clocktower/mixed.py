"""Mixed-team analysis (pilot B, games/v17/b1-*, and the b2 rating batch, games/v17/b2-*): does a team of two
models play at the average of its members' ratings, and do seats favour their own model (whispers, votes)?

Prediction: team strength = mean of its seats' combined ratings (docs/plans/f2-ratings.json), plus the
good-side edge and setup terms, as in the rating fit. In-group: among whispers from one mixed-team seat
to others on the mixed team, the share going to the same model vs the share expected if recipients were
picked without regard to model; vote agreement of same-model vs cross-model pairs on the mixed team.
Intervals: bootstrap over side-swapped pairs.

Rating (`--rate`): the mixed team (either list order) enters the 2026 Bradley-Terry fit (`clocktower.ratings.fit`)
as a 12th player, over the 2026 games plus every mixed game; ratings re-centred so the 11 models of
experiments/models-2026.json average 1500 (the published scale). Mixing effect = mixed rating - mean of its two
members' ratings, from the same fit, so its bootstrap (over side-swapped pairs) carries the members' uncertainty.
The published 11-model numbers (docs/plans/f2-ratings.json) are not touched.

    python -m clocktower mixed [GAMES_PREFIX]   # default games/v17/b1-; results in docs/findings/mixed-teams/b1-mixed-pilot.json
    python -m clocktower mixed games/v17/b2- --rate [--boot 500] [--out docs/findings/mixed-teams/b2-mixed-rating.json]
"""
import json, glob, sys, random, collections
import numpy as np
from pathlib import Path
from .characters import MINIONS

REPO = Path(__file__).resolve().parent.parent
ROOT = 'games/v17/b1-'
R = json.loads((REPO / 'docs/plans/f2-ratings.json').read_text())
RATING = {m['id']: m['combined'] for m in R['models']}
H, SETUP = R['good_advantage'], R['setup_effects']
SOLO = 'gpt-6.1-sol'  # the pilot's opponent; b2 games take the opponent from config.json
MIX = 'claude-opus-5-5+gpt-5.6-sol'  # the mixed team as one player in the fit (either list order)
MEMBERS = ('claude-opus-5-5', 'gpt-5.6-sol')
MIXED_BATCHES = ['v17/b1-*', 'v17/b2-*']


def p_good(good, evil, inplay, n):
    d = sum(RATING[m] for m in good) / len(good) - sum(RATING[m] for m in evil) / len(evil) + H
    d += sum(SETUP[m] for m in ('Spy', 'Scarlet Woman', 'Baron') if m in inplay)
    d += SETUP.get(f'{n} players', 0)
    return 1 / (1 + 10 ** (-d / 400))


def games(root=ROOT):
    out = []
    for d in sorted(glob.glob(root + '*/game-*')):
        try:
            r = json.load(open(d + '/result.json'))
        except FileNotFoundError:
            continue
        if r.get('winner') not in ('good', 'evil'):
            continue
        evil = {s for s, c in r['starting'].items() if c in MINIONS or c == 'Imp'}
        models = r['models']
        try:
            c = json.load(open(d + '/config.json'))
            mixed_side = 'good' if ',' in c['good_model'] else 'evil'
            solo = c['evil_model'] if mixed_side == 'good' else c['good_model']
        except FileNotFoundError:
            mixed_side = 'evil' if any(models[s] != SOLO for s in evil) else 'good'; solo = SOLO
        team = {s for s in models if (s in evil) == (mixed_side == 'evil')}
        ev = [json.loads(l) for l in open(d + '/events.jsonl')]
        out.append({'dir': d, 'r': r, 'evil': evil, 'models': models, 'solo': solo,
                    'side': mixed_side, 'team': team, 'events': ev})
    return out


def summarise(gs):
    res = {'games': len(gs), 'by_side': {}}
    for side in ('good', 'evil'):
        sub = [g for g in gs if g['side'] == side]
        won = sum(g['r']['winner'] == side for g in sub)
        pred = {}
        for label, sub_model in (('mixed (average)', None), ('all Opus 5.5', 'claude-opus-5-5'), ('all GPT-5.6 Sol', 'gpt-5.6-sol')):
            tot = 0
            for g in sub:
                inplay = set(g['r']['starting'].values())
                good = [g['models'][s] for s in g['models'] if s not in g['evil']]
                evil = [g['models'][s] for s in g['evil']]
                if sub_model:
                    good = [sub_model if m != g['solo'] else m for m in good]
                    evil = [sub_model if m != g['solo'] else m for m in evil]
                p = p_good(good, evil, inplay, len(g['models']))
                tot += p if side == 'good' else 1 - p
            pred[label] = round(tot, 2)
        res['by_side'][side] = {'games': len(sub), 'mixed_won': won, 'expected_wins': pred}
    # in-group whispers
    same = exp = n = 0; per = collections.defaultdict(lambda: [0, 0.0, 0])
    for g in gs:
        for e in g['events']:
            if e['kind'] != 'whisper':
                continue
            s = e['data']['from']
            if s not in g['team']:
                continue
            pool = [q for q in g['team'] if q != s]
            chance = sum(g['models'][q] == g['models'][s] for q in pool) / len(pool)
            for t in e['data']['to']:
                if t in g['team']:
                    hit = g['models'][t] == g['models'][s]
                    n += 1; same += hit; exp += chance
                    q = per[g['models'][s]]; q[0] += hit; q[1] += chance; q[2] += 1
    res['whispers'] = {'to_teammates': n, 'same_model': same, 'expected_same': round(exp, 1),
                       'by_sender': {m: {'whispers': q[2], 'same_share': round(q[0] / q[2], 3),
                                         'chance_share': round(q[1] / q[2], 3)} for m, q in sorted(per.items())}}
    # vote agreement
    agree = collections.Counter(); pairs = collections.Counter()
    for g in gs:
        votes = collections.defaultdict(dict)
        for e in g['events']:
            if e['kind'] == 'vote' and e['data']['voter'] in g['team']:
                votes[(e['day'], e['data']['nominee'])][e['data']['voter']] = e['data']['yes']
        for vs in votes.values():
            ss = sorted(vs)
            for i in range(len(ss)):
                for j in range(i + 1, len(ss)):
                    k = 'same' if g['models'][ss[i]] == g['models'][ss[j]] else 'cross'
                    pairs[k] += 1; agree[k] += vs[ss[i]] == vs[ss[j]]
    res['votes'] = {k: {'pairs': pairs[k], 'agree': round(agree[k] / pairs[k], 3) if pairs[k] else None} for k in ('same', 'cross')}
    return res


def rating_games(games_root=REPO / 'games', batches=None):
    """ratings.load over the 2026 study plus the mixed batches, with the mixed team (either order) as MIX."""
    from . import ratings
    gs = ratings.load(games_root, ratings.BATCHES + MIXED_BATCHES if batches is None else batches)
    for g in gs:
        for side in ('good', 'evil'):
            if ',' in g[side]:
                assert set(g[side].split(',')) == set(MEMBERS), g[side]
                g[side] = MIX
    return gs


def _rate_once(gs, ids):
    """Combined, detection and deception ratings with MIX as a 12th player, centred on the 11 models."""
    from .ratings import fit
    names = ids + [MIX]
    out = []
    for r in (fit(gs, names)[0], *fit(gs, names, split=True)[:2]):
        shift = sum(r[n] for n in ids) / len(ids) - 1500
        out.append({n: v - shift for n, v in r.items()})
    return out


def rate(gs, ids, boot=500, seed=0):
    """Mixed-team rating, mixing effect (MIX - mean of MEMBERS) and records, 90% intervals by pair bootstrap."""
    from .ratings import by_pair, q90
    def summary(rs):
        return {k: {'mixed': r[MIX], 'members_mean': (r[MEMBERS[0]] + r[MEMBERS[1]]) / 2,
                    'effect': r[MIX] - (r[MEMBERS[0]] + r[MEMBERS[1]]) / 2, **{m: r[m] for m in MEMBERS}}
                for k, r in zip(('combined', 'detection', 'deception'), rs)}
    point = summary(_rate_once(gs, ids)); allr = _rate_once(gs, ids)[0]
    pairs = by_pair(gs); keys = sorted(pairs); rng = random.Random(seed); B = collections.defaultdict(list)
    for _ in range(boot):
        s = summary(_rate_once([g for k in (rng.choice(keys) for _ in keys) for g in pairs[k]], ids))
        for k, v in s.items():
            for q, x in v.items():
                B[(k, q)].append(x)
    res = {'games': len(gs), 'mixed_games': sum(MIX in (g['good'], g['evil']) for g in gs), 'boot': boot,
           'ratings_all': {n: round(v) for n, v in sorted(allr.items(), key=lambda kv: -kv[1])}}
    for k, v in point.items():
        res[k] = {q: [round(x), q90(B[(k, q)])] for q, x in v.items()}
    res['p_effect_negative'] = round(float(np.mean(np.array(B[('combined', 'effect')]) < 0)), 3)
    rec = collections.defaultdict(lambda: {'good_games': 0, 'good_wins': 0, 'evil_games': 0, 'evil_wins': 0})
    for g in gs:
        if g['good'] == MIX:
            r = rec[g['evil']]; r['good_games'] += 1; r['good_wins'] += g['won']
        elif g['evil'] == MIX:
            r = rec[g['good']]; r['evil_games'] += 1; r['evil_wins'] += not g['won']
    res['record_by_opponent'] = dict(rec)
    return res


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '-h' in argv or '--help' in argv:
        print(__doc__)
        return None
    if '--rate' in argv:
        boot = int(argv[argv.index('--boot') + 1]) if '--boot' in argv else 500
        out = argv[argv.index('--out') + 1] if '--out' in argv else None
        ids = [m['id'] for m in json.loads((REPO / 'experiments/models-2026.json').read_text()) if m.get('centre', True)]
        ok = set(ids) | {MIX}  # the 2026 study's models and the mixed team (later models' games are left out)
        res = rate([g for g in rating_games() if g['good'] in ok and g['evil'] in ok], ids, boot)
        text = json.dumps(res, indent=1); print(text)
        if out:
            Path(out).write_text(text + '\n')
        return res
    gs = games(argv[0] if argv else ROOT)
    res = summarise(gs)
    # bootstrap over side-swapped pairs: whisper excess (overall and per sending model) and vote gap
    by = collections.defaultdict(list)
    for g in gs:
        by[g['dir'].replace('-swap', '')].append(g)
    keys = list(by); rng = random.Random(0); W, V = [], []; WM = collections.defaultdict(list)
    for _ in range(1000):
        s = summarise([g for k in (rng.choice(keys) for _ in keys) for g in by[k]])
        w = s['whispers']
        if w['to_teammates']:
            W.append((w['same_model'] - w['expected_same']) / w['to_teammates'])
        for m, q in w['by_sender'].items():
            WM[m].append(q['same_share'] - q['chance_share'])
        v = s['votes']
        if v['same']['agree'] is not None and v['cross']['agree'] is not None:
            V.append(v['same']['agree'] - v['cross']['agree'])
    q = lambda xs: [round(sorted(xs)[int(.05 * len(xs))], 3), round(sorted(xs)[int(.95 * len(xs))], 3)]
    res['whispers']['excess_share_90'] = q(W); res['votes']['gap_90'] = q(V)
    for m, xs in WM.items():
        res['whispers']['by_sender'][m]['excess_90'] = q(xs)
    out = argv[argv.index('--out') + 1] if '--out' in argv else None
    text = json.dumps(res, indent=1); print(text)
    if out:
        Path(out).write_text(text + '\n')
    return res


if __name__ == '__main__':
    main()
