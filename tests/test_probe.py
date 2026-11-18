import json
import tempfile
import unittest
from pathlib import Path

from clocktower import probe, analyze, export


class ProbeRegression(unittest.TestCase):
    def test_one_line_players_and_tail(self):
        text = 'Alex | 45% | 15% | Undertaker ; Blair | 5% | 2% | Chef. Claim | Butler. Plan | Wait.'
        p = probe.parse(text, ['Alex', 'Blair'])
        self.assertEqual(p['players']['Alex'], {'evil': .45, 'demon': .15, 'character': 'Undertaker'})
        self.assertEqual(p['players']['Blair']['demon'], .02)
        self.assertEqual(p['claim'], 'Butler')
        self.assertEqual(p['plan'], 'Wait.')

    def test_dead_player_rows_on_one_line(self):
        p = probe.parse('Alex | 55 | 38 | Imp ; Blair (dead) | dead | 0 | Chef ; Jules | 30 | 12 | Monk',
                        ['Alex', 'Blair', 'Jules'])
        self.assertEqual(p['players']['Blair'], {'evil': None, 'demon': 0., 'character': 'Chef'})
        self.assertEqual(p['players']['Jules']['demon'], .12)

    def test_inline_headers(self):
        p = probe.parse('Alex | chance they are evil (%) | 18 | chance they are the Demon now (%) | 4 | best guess | Empath', ['Alex'])
        self.assertEqual(p['players']['Alex'], {'evil': .18, 'demon': .04, 'character': 'Empath'})

    def test_both_probabilities_in_one_column(self):
        p = probe.parse('Alex | 55% evil, 25% Demon | one of 3 possible roles', ['Alex'])
        self.assertEqual(p['players']['Alex'], {'evil': .55, 'demon': .25, 'character': 'one of 3 possible roles'})

    def test_transfer_and_historical_reparse_reach_analysis_and_site(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            truth = {'Alex': {'character': 'Imp', 'evil': True}, 'Jules': {'character': 'Imp', 'evil': True},
                     'Blair': {'character': 'Chef', 'evil': False}}
            rows = [{'day': 3, 'point': 'nominations', 'player': 'Blair', 'team': 'good', 'alive': True,
                     'truth': truth, 'raw': 'Alex | 100 | 0 | Imp ; Jules | 90 | 86 | Imp',
                     'players': {'Alex': {'evil': 1., 'demon': 0., 'character': 'Imp ; Jules'}}}]
            (path / 'probes.jsonl').write_text(json.dumps(rows[0]) + '\n')
            events = [{'day': 3, 'kind': 'nominations_open', 'dead': ['Alex']}]
            (path / 'events.jsonl').write_text(json.dumps(events[0]) + '\n')
            (path / 'result.json').write_text(json.dumps({'winner': 'good', 'starting': {}}))
            (path / 'config.json').write_text(json.dumps({'good_model': 'random', 'evil_model': 'random'}))
            self.assertEqual(analyze.game_metrics(path)['demon'], .86)
            b = export.beliefs(path / 'probes.jsonl', [{'n': n} for n in truth], events)
            self.assertEqual(b[0]['demon'], 'Jules')
            self.assertEqual(b[0]['v']['Jules'], 86)
            self.assertEqual(json.loads((path / 'probes.jsonl').read_text())['players'], rows[0]['players'])

    def test_alive_flags_work_without_events_and_ignore_failed_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'probes.jsonl'
            truth = {'Alex': {'character': 'Imp'}, 'Jules': {'character': 'Imp'}}
            rows = [{'day': 2, 'point': 'nominations', 'player': p, 'alive': alive, 'truth': truth, 'error': 'failed'}
                    for p, alive in [('Alex', False), ('Jules', True)]]
            path.write_text('\n'.join(map(json.dumps, rows)))
            self.assertTrue(all(r['demon'] == 'Jules' for r in probe.load(path)))
            rows = [{'day': 2, 'point': 'nominations', 'player': 'Blair', 'alive': True,
                     'truth': {'Alex': {'character': 'Imp', 'alive': False}, 'Jules': {'character': 'Imp', 'alive': True}}}]
            path.write_text(json.dumps(rows[0]))
            self.assertEqual(probe.load(path)[0]['demon'], 'Jules')

    def test_dawn_is_not_scored_using_later_same_day_deaths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'probes.jsonl'
            path.write_text(json.dumps({'day': 1, 'point': 'dawn', 'player': 'Alex', 'alive': True,
                                        'truth': {'Alex': {'character': 'Imp'}}}))
            events = [{'day': 1, 'kind': 'nominations_open', 'dead': ['Alex']}]
            self.assertEqual(probe.load(path, events=events)[0]['demon'], 'Alex')

    def test_incomplete_log_record_does_not_break_export(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'probes.jsonl'
            row = {'day': 1, 'point': 'nominations', 'player': 'Blair', 'team': 'good',
                   'truth': {'Alex': {'character': 'Imp', 'alive': True}},
                   'raw': 'Alex | 40 | 20 | Imp'}
            path.write_text(json.dumps(row) + '\n{"day":')
            self.assertEqual(probe.load(path)[0]['players']['Alex']['demon'], .2)
