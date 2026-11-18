"""Failure paths for the public API monitor; the real-server success path is in test_web."""
import io
import unittest
import urllib.error
from unittest import mock

from clocktower.check_play import CheckFailed, PlayCheck


class PlayCheckTest(unittest.TestCase):
    def setUp(self):
        self.check = PlayCheck('https://play.example', poll_interval=0)
        self.created = [{'table': 'testtable', 'host_key': 'test-host'}, {'token': 'test-token'}, {'ok': True}]
        self.free = {'config': {'good_model': 'random', 'evil_model': 'random'}, 'paid_by': None, 'status': 'lobby'}

    def test_refuses_unconfirmed_practice_config(self):
        for config in ({}, {'config': {'good_model': 'paid', 'evil_model': 'random'}, 'paid_by': 'house'}):
            with self.subTest(config=config):
                self.check.request = mock.Mock(side_effect=self.created + [config, {'status': 'lobby'}])
                with self.assertRaisesRegex(CheckFailed, 'refusing to start'):
                    self.check.run()
                self.assertFalse(any(call.args[0].endswith('/start') for call in self.check.request.call_args_list))

    def test_uncertain_start_is_stopped_and_original_failure_preserved(self):
        self.check.request = mock.Mock(side_effect=self.created + [self.free,
            CheckFailed('start request timed out'), {'status': 'playing'},
            CheckFailed('engine still initializing'), {'status': 'playing'}, {'ok': True}, {'status': 'over'}])
        with self.assertRaisesRegex(CheckFailed, 'start request timed out'):
            self.check.run()
        routes = [call.args[0] for call in self.check.request.call_args_list]
        self.assertEqual(sum(route.endswith('/end') for route in routes), 2)
        self.assertFalse(any(route.endswith('/reset') for route in routes))

    def test_game_that_never_becomes_playable_fails_and_is_stopped(self):
        self.check.start_timeout = 0
        self.check.request = mock.Mock(side_effect=self.created + [self.free, {'ok': True},
            {'status': 'playing'}, {'ok': True}, {'status': 'over'}])
        with self.assertRaisesRegex(CheckFailed, 'Timed out waiting for a playable human turn'):
            self.check.run()
        self.assertIn(mock.call('/api/t/testtable/end', {}), self.check.request.call_args_list)

    def test_game_error_fails_and_cleans_up(self):
        self.check.request = mock.Mock(side_effect=self.created + [self.free, {'ok': True},
            {'status': 'over', 'error': 'internal error'}, {'status': 'over'}])
        with self.assertRaisesRegex(CheckFailed, 'Game failed'):
            self.check.run()

    def test_cleanup_failure_also_fails_an_otherwise_successful_check(self):
        self.check.table, self.check.token = 'testtable', 'test-token'
        self.check.start = mock.Mock()
        self.check.cleanup_timeout = 0
        with self.assertRaisesRegex(CheckFailed, 'Timed out ending'):
            self.check.run()

    def test_http_errors_do_not_print_response_secrets(self):
        error = urllib.error.HTTPError('https://play.example/api/new', 503, 'test-host test-token', {},
                                       io.BytesIO(b'test-host test-token'))
        with mock.patch('urllib.request.urlopen', side_effect=error):
            with self.assertRaisesRegex(CheckFailed, '^POST /api/new: HTTP 503$'):
                self.check.request('/api/new', {})

    def test_invalid_json_fails_the_check(self):
        for payload in (b'not JSON', b'[]'):
            with self.subTest(payload=payload), mock.patch('urllib.request.urlopen', return_value=io.BytesIO(payload)):
                with self.assertRaises(CheckFailed):
                    self.check.request('/api/new', {})
