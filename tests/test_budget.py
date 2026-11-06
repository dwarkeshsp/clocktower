"""House spending caps: concurrent calls, uncertain outcomes and midnight/restarts. No paid API calls."""
import asyncio
import io
import json
import tempfile
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from clocktower.llm import BudgetExceeded, NO_LIMIT, OpenAIConversation
from clocktower.web import PlayLedger, Settings, Store, today


class BudgetTest(unittest.TestCase):
    def ledger(self, store, game='game', daily=30, cap=5):
        return PlayLedger('table', game, 'house', cap, store, daily, 'Asia/Singapore')

    def conversation(self, ledger):
        return OpenAIConversation('system', {'type': 'object', 'properties': {}, 'additionalProperties': False},
                                  model='gpt-6.1-sol', api_key='fake', label='Alex', ledger=ledger,
                                  semaphore=NO_LIMIT, max_tokens=100)

    def count_response(self, tokens=1000):
        return io.BytesIO(json.dumps({'input_tokens': tokens}).encode())

    def response(self):
        return {'status': 'completed', 'service_tier': 'default',
                'usage': {'input_tokens': 1000, 'output_tokens': 10},
                'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{}'}]}]}

    def test_competing_connections_cannot_exceed_daily_cap(self):
        with tempfile.TemporaryDirectory() as d:
            stores = [Store(Path(d) / 'spend.db') for _ in range(16)]
            ledgers = [self.ledger(s, game=str(i), daily=3, cap=10) for i, s in enumerate(stores)]
            def reserve(ledger):
                try:
                    return ledger.reserve(1, 'seat')
                except BudgetExceeded:
                    return None
            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(reserve, ledgers))
            self.assertEqual(sum(r is not None for r in results), 3)
            self.assertEqual(stores[0].spent(paid_by='house'), 3)
            for s in stores:
                s.db.close()

    def test_competing_seats_share_game_cap(self):
        store = Store()
        ledgers = [self.ledger(store, cap=2) for _ in range(3)]
        ledgers[0].reserve(1, 'a')
        ledgers[1].reserve(1, 'b')
        with self.assertRaises(BudgetExceeded):
            ledgers[2].reserve(1, 'c')

    def test_restart_and_midnight_keep_uncertain_requests(self):
        before = datetime(2026, 11, 5, 15, 59, 59, tzinfo=timezone.utc).timestamp()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'spend.db'
            with mock.patch('clocktower.web.time.time', return_value=before):
                store = Store(path)
                reservation = self.ledger(store, daily=1).reserve(1, 'seat')
                store.db.close()
            with mock.patch('clocktower.web.time.time', return_value=before + 2):
                store = Store(path)
                with self.assertRaises(BudgetExceeded):
                    self.ledger(store, game='new', daily=1).reserve(.1, 'seat')
                store.settle(reservation, .25)
                self.ledger(store, game='new', daily=1).reserve(.75, 'seat')
                self.assertEqual(store.spent(today('Asia/Singapore'), 'house'), 1)
                store.db.close()

    def test_singapore_boundary_and_previous_spend(self):
        midnight = datetime(2026, 11, 5, 16, tzinfo=timezone.utc).timestamp()
        store = Store()
        with mock.patch('clocktower.web.time.time', return_value=midnight - .01):
            store.add_spend('old', 'old', 30, 'house')
        with mock.patch('clocktower.web.time.time', return_value=midnight + .01):
            self.assertEqual(today('Asia/Singapore'), midnight)
            self.ledger(store).reserve(.1, 'seat')
            self.assertAlmostEqual(store.spent(today('Asia/Singapore'), 'house'), .1)

    def test_monthly_period_counts_since_the_first(self):
        first = datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()
        store = Store()
        with mock.patch('clocktower.web.time.time', return_value=first - 1):
            store.add_spend('oct', 'oct', 50, 'house')
        with mock.patch('clocktower.web.time.time', return_value=first + 4 * 86400):
            store.add_spend('nov', 'nov', 7, 'house')
        with mock.patch('clocktower.web.time.time', return_value=first + 9 * 86400):
            self.assertEqual(today('UTC', 'month'), first)
            self.assertEqual(store.spent(today('UTC', 'month'), 'house'), 7)
            self.assertEqual(store.spent(today('UTC'), 'house'), 0)
            with self.assertRaises(BudgetExceeded):
                store.reserve('t', 'g', 4, 10, None, 'UTC', 'seat', 'month')
            store.reserve('t', 'g', 3, 10, None, 'UTC', 'seat', 'month')
        self.assertEqual(Settings.from_env({'PLAY_BUDGET_PERIOD': 'Month'}).budget_period, 'month')
        with self.assertRaises(ValueError):
            Settings(budget_period='week')

    def test_send_reconciles_to_actual_cost_once(self):
        store = Store()
        conv = self.conversation(self.ledger(store))
        def post(body):
            self.assertGreater(store.spent(), .0021)
            self.assertEqual(body['service_tier'], 'default')
            return self.response()
        with mock.patch('urllib.request.urlopen', return_value=self.count_response()) as count, \
                mock.patch.object(conv, '_post', side_effect=post):
            reply = asyncio.run(conv.send('hello'))
        self.assertEqual(reply.action, {})
        self.assertAlmostEqual(store.spent(), .0021)
        self.assertEqual(store.db.execute('SELECT COUNT(*) FROM spend').fetchone()[0], 1)
        payload = json.loads(count.call_args.args[0].data)
        self.assertIn('text', payload)  # count the structured-output schema, too
        self.assertIn('reasoning', payload)

    def test_retry_reserves_again_after_unknown_outcome(self):
        store = Store()
        conv = self.conversation(self.ledger(store))
        with mock.patch('urllib.request.urlopen', side_effect=lambda *a, **kw: self.count_response()), \
                mock.patch.object(conv, '_post', side_effect=[ConnectionError('lost response'), self.response()]), \
                mock.patch('clocktower.llm.asyncio.sleep', new_callable=mock.AsyncMock):
            asyncio.run(conv.send('hello'))
        rows = store.db.execute('SELECT cost, pending FROM spend ORDER BY rowid').fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], 1)
        self.assertGreater(rows[0][0], .0035)
        self.assertAlmostEqual(rows[1][0], .0021)
        self.assertEqual(rows[1][1], 0)

    def test_rejected_request_releases_reservation(self):
        store = Store()
        conv = self.conversation(self.ledger(store))
        error = urllib.error.HTTPError(conv.URL, 401, 'bad key', {}, io.BytesIO(b'bad key'))
        with mock.patch('urllib.request.urlopen', return_value=self.count_response()), \
                mock.patch.object(conv, '_post', side_effect=error), self.assertRaises(RuntimeError):
            asyncio.run(conv.send('hello'))
        self.assertEqual(store.spent(), 0)

    def test_no_generation_without_a_reservation(self):
        store = Store()
        conv = self.conversation(self.ledger(store, daily=.001))
        with mock.patch('urllib.request.urlopen', return_value=self.count_response()), \
                mock.patch.object(conv, '_post') as post, self.assertRaises(BudgetExceeded):
            asyncio.run(conv.send('hello'))
        post.assert_not_called()

    def test_missing_usage_fails_closed(self):
        store = Store()
        conv = self.conversation(self.ledger(store))
        with mock.patch('urllib.request.urlopen', return_value=self.count_response()), \
                mock.patch.object(conv, '_post', return_value={'status': 'failed'}), self.assertRaises(BudgetExceeded):
            asyncio.run(conv.send('hello'))
        self.assertGreater(store.spent(), 0)
        self.assertEqual(store.db.execute('SELECT pending FROM spend').fetchone()[0], 1)

    def test_long_context_reserves_cache_and_output_surcharges(self):
        store = Store()
        conv = self.conversation(self.ledger(store))
        def post(body):
            self.assertAlmostEqual(store.spent(), 1.516515)  # (300K*$5/M + 100*$15/M) + 1%
            return self.response()
        with mock.patch('urllib.request.urlopen', return_value=self.count_response(300_000)), \
                mock.patch.object(conv, '_post', side_effect=post):
            asyncio.run(conv.send('hello'))

    def test_invalid_limits_fail_closed(self):
        for value in (float('nan'), float('inf'), -1):
            with self.assertRaises(ValueError):
                Settings(daily_cap=value)

    def test_legacy_database_migrates_without_losing_spend(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'old.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE spend (time REAL, table_id TEXT, game TEXT, cost REAL, paid_by TEXT, label TEXT)')
                db.execute("INSERT INTO spend VALUES (0, 't', 'g', 2, 'house', 'a')")
            store = Store(path)
            self.assertEqual(store.spent(), 2)
            store.add_spend('t', 'g', 1, 'house')
            self.assertEqual(store.spent(), 3)
            store.db.close()
