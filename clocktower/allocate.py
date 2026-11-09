"""Where extra games go: a fixed rule, decided before any results and never by which way they lean.

1. Floor: every pair of models in the list plays at least `floor` side-swapped pairs.
2. Style clashes: a matchup whose observed result is more than `z` standard errors from what the ratings
   predict gets one extra pair (once).
3. Precision: then add, one at a time, the pair that most reduces the uncertainty of the models still above
   the target, per dollar, until every model's 90% half-width is within `target` Elo (or the money runs out). Never add to
   a matchup that already has `cap` pairs, or whose opponent is already `share` of either model's games.

`--only MODEL` rates a model added later: only matchups that include it are considered, and only its own
half-width counts toward the target (the floor then applies to none: pass `--floor 0`).

Each new pair's guaranteed Minion is the one its two models have been dealt least (written as the matchup's
`minions`, which `tournament` uses). Half-widths are the
analytic (Fisher) ones for the combined rating, scaled per model to match the bootstrap in the ratings file.

    python -m clocktower allocate experiments/models-2026.json docs/plans/f2-ratings.json 'games/v16/f2-*' 'games/v17/f3*' \\
        --exclude 'v16/f2-*opus48*' --target 100 --seed 170000 --out games/v17/f4 --budget 23000 > experiments/f4.json
"""
import argparse, fnmatch, glob, itertools, json, math, sys, collections
import numpy as np
from .characters import MINIONS

K = 400 / math.log(10)
GOOD_SEATS, EVIL_SEATS = 8, 3  # a 10-12 player table: 7-9 good, always three evil


def load(patterns, exclude=()):
    games = []
    for pat in patterns:
        for d in sorted(glob.glob(pat + '/game-*')):
            if any(fnmatch.fnmatch(d, '*' + x) for x in exclude):
                continue
            try:
                r = json.load(open(d + '/result.json')); c = json.load(open(d + '/config.json'))
            except FileNotFoundError:
                continue
            if r.get('winner') not in ('good', 'evil'):
                continue
            n_evil = sum(1 for ch in r['starting'].values() if ch in MINIONS or ch == 'Imp')
            games.append({'good': c['good_model'], 'evil': c['evil_model'], 'won': r['winner'] == 'good',
                          'minion': c.get('minion'), 'cost': r.get('cost', 0), 'n_good': len(r['starting']) - n_evil,
                          'n_evil': n_evil})
    return games


def seat_costs(games, names):
    """Per-model cost of one seat-game: least squares over game costs (cost ~ n_good*c[good] + n_evil*c[evil])."""
    idx = {n: i for i, n in enumerate(names)}
    X = np.zeros((len(games), len(names))); y = np.array([g['cost'] for g in games])
    for k, g in enumerate(games):
        X[k, idx[g['good']]] += g['n_good']; X[k, idx[g['evil']]] += g['n_evil']
    c, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {n: max(float(c[i]), 0.05) for n, i in idx.items()}


def plan(models, ratings, games, target=100, floor=1, cap=4, share=0.25, z=2.5, max_spend=None, only=None):
    names = [m['id'] for m in models]; N = len(names); idx = {n: i for i, n in enumerate(names)}
    R = {m['id']: m for m in ratings['models']}
    r = np.array([(R[n]['combined'] - 1500) / K for n in names]); h = ratings['good_advantage'] / K
    boot = np.array([(R[n]['c90'][1] - R[n]['c90'][0]) / 2 for n in names])
    seat = seat_costs(games, names)
    pairs = [p for p in itertools.combinations(names, 2) if not only or only in p]
    focus = np.array([not only or n == only for n in names])  # the models whose half-width the target is about
    pair_cost = {p: (GOOD_SEATS + EVIL_SEATS) * (seat[p[0]] + seat[p[1]]) for p in pairs}

    def game_info(g, e):
        x = np.zeros(N); x[idx[g]] = 1; x[idx[e]] = -1
        p = 1 / (1 + math.exp(-(r[idx[g]] - r[idx[e]] + h)))
        return p * (1 - p) * np.outer(x, x), p
    PI = {p: game_info(*p)[0] + game_info(p[1], p[0])[0] for p in pairs}
    prior = np.eye(N) / 1.5 ** 2; C = np.eye(N) - 1 / N

    def halfwidth(I):
        return 1.645 * K * np.sqrt(np.diag(C @ np.linalg.inv(I + prior) @ C))

    played = collections.Counter(); per_model = collections.Counter(); minions = collections.defaultdict(collections.Counter)
    obs = collections.Counter(); exp = collections.Counter(); var = collections.Counter()
    I = np.zeros((N, N))
    for g in games:
        if g['good'] not in idx or g['evil'] not in idx:
            continue
        key = tuple(sorted((g['good'], g['evil']), key=idx.get))
        dI, p = game_info(g['good'], g['evil']); I += dI
        played[key] += 0.5; per_model[g['good']] += 1; per_model[g['evil']] += 1
        if g['minion']:
            minions[g['good']][g['minion']] += 1; minions[g['evil']][g['minion']] += 1
        a_won = g['won'] == (g['good'] == key[0])
        obs[key] += a_won; exp[key] += p if g['good'] == key[0] else 1 - p; var[key] += p * (1 - p)
    scale = boot / halfwidth(I)  # analytic -> bootstrap, per model
    hw = lambda J: scale * halfwidth(J)
    add = collections.Counter(); why = collections.defaultdict(collections.Counter); spent = 0.0
    log = [f'now: worst ±{hw(I).max():.0f} ({names[int(hw(I).argmax())]}), mean ±{hw(I).mean():.0f}']

    def take(p, reason):
        nonlocal I, spent
        I = I + PI[p]; add[p] += 1; spent += pair_cost[p]; why[p][reason.split(' (')[0]] += 1
        per_model[p[0]] += 2; per_model[p[1]] += 2

    for p in pairs:  # 1. floor
        while played[p] + add[p] < floor:
            take(p, 'floor')
    for p in pairs:  # 2. style clashes
        if var[p] and abs(obs[p] - exp[p]) / math.sqrt(var[p]) > z:
            take(p, f'clash (observed {obs[p]} vs {exp[p]:.1f} expected)')
    log.append(f'after floor and clashes: {sum(add.values())} pairs, ${spent:.0f}, worst ±{hw(I).max():.0f}')
    while hw(I)[focus].max() > target:  # 3. precision per dollar
        over = lambda J: (np.maximum(hw(J)[focus] - target, 0) ** 2).sum()  # only models still above the target count
        cur = over(I); best = None
        for p in pairs:
            if played[p] + add[p] >= cap or (max_spend and spent + pair_cost[p] > max_spend):
                continue
            n = 2 * (played[p] + add[p])  # games in this matchup
            if any(n >= share * per_model[m] for m in p):
                continue
            gain = (cur - over(I + PI[p])) / pair_cost[p]
            if gain > 0 and (best is None or gain > best[0]):
                best = (gain, p)
        if not best:
            log.append('no eligible matchup left (caps or budget)')
            break
        take(best[1], 'precision')
    log.append(f'final: {sum(add.values())} pairs ({2 * sum(add.values())} games), ${spent:.0f}, worst ±{hw(I).max():.0f}, mean ±{hw(I).mean():.0f}')
    log.append('per model: ' + ', '.join(f'{n} ±{v:.0f}' for n, v in zip(names, hw(I))))

    out = []
    for p, n in add.items():  # guaranteed Minions: least dealt to these two models so far
        ms = []
        for _ in range(n):
            m = min(MINIONS, key=lambda x: (minions[p[0]][x] + minions[p[1]][x], MINIONS.index(x)))
            ms.append(m); minions[p[0]][m] += 2; minions[p[1]][m] += 2
        out.append({'pair': p, 'pairs': n, 'minions': ms, 'why': ', '.join(f'{k} {v}' for k, v in why[p].items()), 'cost': round(n * pair_cost[p])})
    return out, log


def main(argv=None):
    ap = argparse.ArgumentParser(prog='clocktower allocate', description=__doc__.split('\n')[0])
    ap.add_argument('models'); ap.add_argument('ratings'); ap.add_argument('games', nargs='+')
    ap.add_argument('--exclude', action='append', default=[])
    ap.add_argument('--target', type=float, default=100); ap.add_argument('--floor', type=int, default=1)
    ap.add_argument('--cap', type=int, default=4); ap.add_argument('--share', type=float, default=0.25)
    ap.add_argument('--z', type=float, default=2.5); ap.add_argument('--max-spend', type=float)
    ap.add_argument('--only', help='a model id: add games only to its matchups, until its own rating meets the target')
    ap.add_argument('--seed', type=int, required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--budget', type=float, required=True, help='cap on the all-time ledger for the plan')
    a = ap.parse_args(argv)
    models = json.load(open(a.models)); short = {m['id']: m.get('short', m['id']) for m in models}
    alloc, log = plan(models, json.load(open(a.ratings)), load(a.games, a.exclude), a.target, a.floor, a.cap,
                      a.share, a.z, a.max_spend, a.only)
    for line in log:
        print(line, file=sys.stderr)
    matchups = []
    for i, x in enumerate(sorted(alloc, key=lambda x: x['pair'])):
        g, e = x['pair']
        matchups.append({'name': f'{short[g]}-v-{short[e]}', 'good': g, 'evil': e, 'pairs': x['pairs'],
                         'seed': a.seed + 100 * i, 'minions': x['minions'], 'why': x['why'],
                         'est_cost': x['cost']})
        print(f"  {matchups[-1]['name']:24} {x['pairs']} pair(s)  ${x['cost']:>4}  {x['why']}", file=sys.stderr)
    rule = {k: getattr(a, k) for k in ('target', 'floor', 'cap', 'share', 'z')}
    print(json.dumps({'note': f'Allocated by clocktower.allocate {rule}', 'out': a.out, 'seed': a.seed,
                      'players': '10-12', 'budget': a.budget, 'matchups': matchups}, indent=1))


if __name__ == '__main__':
    main()
