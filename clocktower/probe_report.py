"""Reproduce the historical six-model belief chart from saved surveys, before and after fixes.

python -m clocktower.probe_report --games games --out docs/charts/demon-belief.json
The original f2-f5 chart includes the 20 unrated v16 games. Keep that cohort fixed for the correction.
"""
import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from . import probe

GROUPS = {
    'OpenAI': ['gpt-5.6-sol', 'gpt-6-astra', 'gpt-6.1-sol'],
    'Anthropic': ['claude-fable-5', 'claude-fable-5-1', 'claude-opus-5-5'],
}
LABELS = {'OpenAI': 'GPT-5.6 Sol, GPT-6 Astra, GPT-6.1 Sol',
          'Anthropic': 'Fable 5, Fable 5.1, Opus 5.5'}
BATCHES = ['v16/f2-*', 'v17/f3*-*', 'v17/f4-*', 'v17/f5-*']


def build(games):
    games = Path(games)
    pool = defaultdict(list)
    selected = []
    for batch in BATCHES:
        for config in sorted(games.glob(batch + '/game-*/config.json')):
            cfg = json.loads(config.read_text())
            lab = next((lab for lab, models in GROUPS.items() if cfg['good_model'] in models), None)
            if not lab:
                continue
            path = config.parent
            if json.loads((path / 'result.json').read_text()).get('winner') not in ('good', 'evil'):
                continue
            selected.append(path.relative_to(games).as_posix())
            events = [json.loads(line) for line in (path / 'events.jsonl').read_text().splitlines() if line.strip()]
            original = [json.loads(line) for line in (path / 'probes.jsonl').read_text().splitlines() if line.strip()]
            corrected = probe.load(path / 'probes.jsonl', events=events)
            for version, rows in [('original', original), ('corrected', corrected)]:
                by_day = defaultdict(list)
                for r in rows:
                    if r['point'] != 'nominations' or r['team'] != 'good' or not r['alive'] or r['day'] > 4:
                        continue
                    demon = r['demon'] if version == 'corrected' else next(
                        (n for n, t in r['truth'].items() if t['character'] == 'Imp'), None)
                    value = r.get('players', {}).get(demon, {}).get('demon')
                    if value is not None:
                        by_day[r['day']].append(value)
                for day, values in by_day.items():
                    pool[version, lab, day].append(statistics.mean(values))
    series = {}
    for version in ('original', 'corrected'):
        series[version] = []
        for lab in GROUPS:
            values = [pool[version, lab, day] for day in range(1, 5)]
            if any(not v for v in values):
                raise ValueError(f'Missing days for {lab}; fetch all f2-f5 event and probe logs first')
            series[version].append({'lab': lab, 'models': LABELS[lab],
                                    'by_day': [statistics.mean(v) for v in values],
                                    'games_by_day': [len(v) for v in values]})
    return {'method': 'Living good players averaged within each game at nominations, then equal weight per game. '
                      'Days 1-4 separately; original six-model f2-f5 comparison, retaining unrated v16 games.',
            'games': selected, **series}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--games', type=Path, default=Path('games'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--site-charts', type=Path)
    args = parser.parse_args()
    report = build(args.games)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    if args.site_charts:
        charts = json.loads(args.site_charts.read_text())
        charts['demon_belief'] = {'note': report['method'], 'series': report['corrected']}
        args.site_charts.write_text(json.dumps(charts, indent=2) + '\n')
    print(f'Reprocessed {len(report["games"])} games for the six-model chart.')


if __name__ == '__main__':
    main()
