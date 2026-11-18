"""The website exporter (clocktower/export.py): compact game records, game selection, quotes, secrets, a full build."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from clocktower import export

SEATS = [('Alex', 'Imp'), ('Blair', 'Empath'), ('Casey', 'Poisoner'), ('Drew', 'Chef'), ('Ellis', 'Saint')]


def ev(seq, day, phase, kind, data, to='public'):
    return {'seq': seq, 'time': 0, 'day': day, 'phase': phase, 'kind': kind, 'data': data, 'to': to, 'dead': []}


def write_game(d, good='claude-opus-5-5', evil='gpt-6.1-sol', winner='good'):
    d.mkdir(parents=True)
    (d / 'config.json').write_text(json.dumps({'good_model': good, 'evil_model': evil, 'protocol': 'v17'}))
    models = {n: (evil if c in export.EVIL else good) for n, c in SEATS}
    (d / 'result.json').write_text(json.dumps({'winner': winner, 'reason': 'The Demon is dead.', 'days': 1, 'seed': 7,
                                               'models': models, 'final': dict(SEATS)}))
    events = [
        ev(0, 0, 'setup', 'setup', {'seats': [{'name': n, 'character': c, 'shown': c} for n, c in SEATS],
                                    'bluffs': ['Monk', 'Mayor', 'Slayer'], 'red_herring': None}, 'audit'),
        ev(1, 0, 'setup', 'intro', {'text': 'You are Alex.'}, ['Alex']),
        ev(2, 1, 'night', 'header', {'text': 'Night 1'}),
        ev(3, 1, 'night', 'thinking', {'player': 'Casey', 'kind': 'night', 'text': 'Poison Blair.'}, 'audit'),
        ev(4, 1, 'night', 'night_choice', {'player': 'Casey', 'role': 'Poisoner', 'targets': ['Blair']}, 'audit'),
        ev(5, 1, 'night', 'info', {'text': 'Night 1 — Empath: 2'}, ['Blair']),
        ev(6, 1, 'day', 'header', {'text': 'Day 1'}),
        ev(7, 1, 'day', 'dawn', {'day': 1, 'deaths': [], 'narration': 'Morning.'}),
        ev(8, 1, 'day', 'header', {'text': 'Day 1 · private time 1'}),
        ev(9, 1, 'day', 'thinking', {'player': 'Alex', 'kind': 'beat', 'text': 'Claim Chef.'}, 'audit'),
        ev(10, 1, 'day', 'thinking', {'player': 'Drew', 'kind': 'beat', 'text': 'I will pass.'}, 'audit'),
        ev(11, 1, 'day', 'whisper', {'from': 'Alex', 'to': ['Casey'], 'text': 'I am the Chef, okay?'}, ['Alex', 'Casey']),
        ev(12, 1, 'day', 'header', {'text': 'Day 1 · town square 1'}),
        ev(13, 1, 'day', 'say', {'speaker': 'Blair', 'text': 'Empath 2 here.'}),
        ev(14, 1, 'nominations', 'nominations_open', {}),
        ev(15, 1, 'nominations', 'notice', {'text': '(Your nomination of Alex was not taken.)'}, ['Drew']),
        ev(16, 1, 'nominations', 'nomination', {'nominator': 'Blair', 'nominee': 'Alex', 'text': 'You lied.'}),
        ev(17, 1, 'nominations', 'defense', {'nominee': 'Alex', 'text': 'No.'}),
        ev(18, 1, 'nominations', 'vote', {'voter': 'Blair', 'nominee': 'Alex', 'yes': True, 'ghost': False, 'text': ''}),
        ev(19, 1, 'nominations', 'vote_result', {'nominee': 'Alex', 'votes': 3, 'needed': 3, 'outcome': 'block', 'voters': []}),
        ev(20, 1, 'nominations', 'execution', {'player': 'Alex', 'died': True}),
        ev(21, 1, 'nominations', 'game_over', {'winner': winner, 'reason': 'The Demon is dead.'}),
    ]
    (d / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events) + '\n')
    probe = lambda who, alex, alive=True: {'day': 1, 'point': 'nominations', 'player': who, 'team': 'good', 'alive': alive,
                                           'players': {'Alex': {'demon': alex}, 'Casey': {'demon': 0.1}}}
    (d / 'probes.jsonl').write_text('\n'.join(json.dumps(p) for p in [
        probe('Blair', 0.6), probe('Drew', 0.2), probe('Ellis', 0.9, alive=False),
        {'day': 1, 'point': 'nominations', 'player': 'Casey', 'team': 'evil', 'players': {'Alex': {'demon': 1.0}}}]) + '\n')


class ExportGame(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_game(self.root / 'v17/f3-a-v-b/game-01')
        self.g = export.export_game(self.root / 'v17/f3-a-v-b/game-01', 'v17/f3-a-v-b/game-01', 'rated')

    def tearDown(self):
        self.tmp.cleanup()

    def items(self, kind=None):
        return [it for d in self.g['days_'] for s in d['secs'] for it in s['it'] if kind is None or it['k'] == kind]

    def test_header_and_seats(self):
        g = self.g
        self.assertEqual((g['good'], g['evil'], g['winner'], g['players']), ('claude-opus-5-5', 'gpt-6.1-sol', 'good', 5))
        self.assertEqual(g['twin'], 'v17/f3-a-v-b/game-01-swap')
        self.assertEqual(g['minions'], ['Poisoner'])
        self.assertEqual([s['e'] for s in g['seats']], [1, 0, 1, 0, 0])
        self.assertEqual(g['models'][g['seats'][0]['m']], 'gpt-6.1-sol')
        self.assertEqual(g['intros'], {'Alex': 'You are Alex.'})

    def test_sections_in_order(self):
        self.assertEqual([(s['t'], s['b']) for s in self.g['days_'][0]['secs']],
                         [('night', 0), ('dawn', 0), ('private', 1), ('square', 1), ('noms', 0)])

    def test_reasoning_travels_with_its_move(self):
        w = self.items('w')[0]
        self.assertEqual((w['p'], w['to'], w['t']), ('Alex', ['Casey'], 'Claim Chef.'))
        self.assertEqual(self.items('nc')[0]['t'], 'Poison Blair.')
        alone = self.items('th')  # Drew passed: his reasoning stays on its own
        self.assertEqual([(t['p'], t['x']) for t in alone], [('Drew', 'I will pass.')])

    def test_secret_items_are_marked_and_noise_dropped(self):
        self.assertTrue(all(it.get('a') for it in self.items() if it['k'] in ('nc', 'info', 'th')))
        self.assertFalse(self.items('note'))  # turn bookkeeping notices are dropped
        self.assertEqual([it['k'] for it in self.items()][-6:], ['nom', 'def', 'v', 'vr', 'ex', 'end'])

    def test_beliefs_average_living_good_players(self):
        b = self.g['belief'][0]
        self.assertEqual((b['d'], b['pt'], b['n']), (1, 'nominations', 2))
        self.assertEqual(b['v']['Alex'], 40)  # (60 + 20) / 2: the dead Ellis and the evil Casey don't count
        self.assertEqual(set(b['by']), {'Blair', 'Drew', 'Ellis'})

    def test_library_uses_the_demon_at_the_last_survey(self):
        self.g['belief'] = [{'d': 2, 'demon': 'Casey', 'v': {'Alex': 0, 'Casey': 87}}]
        self.assertEqual(export.summary(self.g, set())['demonBelief'], 87)

    def test_find_quote(self):
        self.assertEqual(export.find_quote(self.g, 'i AM the  chef'), (1, 11, False))
        self.assertEqual(export.find_quote(self.g, 'Claim Chef'), (1, 11, True))
        self.assertEqual(export.find_quote(self.g, 'never said'), (None, None, False))


class Selection(unittest.TestCase):
    def test_rated_unrated_and_mixed(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            write_game(root / 'v16/f2-opus48-v-x/game-01', good='claude-opus-4-8')
            write_game(root / 'v16/f2-a-v-b/game-01')
            write_game(root / 'v17/b2-mixA-v-astra/game-01', good='claude-opus-5-5,gpt-5.6-sol', evil='gpt-6-astra')
            write_game(root / 'v17/f3-a-v-b/game-01', winner=None)  # unfinished: left out
            got = dict(export.select(root))
            self.assertEqual(got, {'v16/f2-opus48-v-x/game-01': 'unrated', 'v16/f2-a-v-b/game-01': 'rated',
                                   'v17/b2-mixA-v-astra/game-01': 'mixed'})
            g = export.export_game(root / 'v17/b2-mixA-v-astra/game-01', 'v17/b2-mixA-v-astra/game-01')
            self.assertEqual(g['good'], export.MIXED_ID)


class Secrets(unittest.TestCase):
    def test_credentials_are_refused(self):
        for bad in ['sk-ant-api03-abcdefghijklmnop', 'hf_' + 'a' * 30, 'sk-proj-' + 'A' * 30]:
            with self.assertRaises(SystemExit):
                export.check_secrets(f'some text {bad} more', 'x')
        export.check_secrets('a task-oriented sk- discussion', 'x')  # ordinary text passes


class Build(unittest.TestCase):
    def test_build_writes_pages_and_data(self):
        with tempfile.TemporaryDirectory() as t:
            root, out = Path(t) / 'games', Path(t) / 'dist'
            write_game(root / 'v17/f3-a-v-b/game-01')
            write_game(root / 'v17/f3-a-v-b/game-01-swap', winner='evil')
            rows = export.build(root, out)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['twin'], 'v17/f3-a-v-b/game-01-swap')
            for page in ('index', 'leaderboard', 'games', 'game', 'highlights', 'play', 'run', 'about'):
                html = (out / f'{page}.html').read_text()
                self.assertIn('<title>', html)
                self.assertIn('The Pandemonium Institute', html)  # the disclaimer is on every page
                self.assertNotIn('{{', html)
            blob = (out / 'data/games/v17--f3-a-v-b--game-01.json.gz').read_bytes()
            self.assertEqual(json.loads(gzip.decompress(blob))['id'], 'v17/f3-a-v-b/game-01')
            ratings = json.loads((out / 'data/ratings.json').read_text())
            self.assertIn('names', ratings)
            self.assertEqual(ratings['h2h'], {'claude-opus-5-5|gpt-6.1-sol': [1, 2]})
            self.assertTrue((out / 'config.js').read_text().startswith('window.CT_CONFIG'))
            self.assertEqual((out / 'CNAME').read_text().strip(), 'clocktowerbench.com')


if __name__ == '__main__':
    unittest.main()
