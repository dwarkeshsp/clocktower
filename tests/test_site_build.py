"""Production builds must not silently omit games or publish stale cached games."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clocktower import export, site_build
from test_export import write_game


class ProductionBuild(unittest.TestCase):
    def test_manifest_selection_includes_new_and_mixed_batches_without_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wanted = ['v17/f6-new/game-01', 'v17/f7-new/game-01', 'v17/b2-mixed/game-01']
            for game in wanted + ['v17/f7-new/game-02']:
                path = root / game
                path.mkdir(parents=True)
                (path / 'config.json').write_text('{}')
                (path / 'result.json').write_text(json.dumps({'winner': 'good' if game in wanted else None}))
            self.assertEqual(set(site_build.manifest_games(root)), set(wanted))

    def test_missing_logs_stop_build_before_exporting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = 'v17/f7-new/game-01'
            write_game(root / 'manifests' / game)
            write_game(root / 'snapshot' / game)
            (root / 'snapshot' / game / 'probes.jsonl').unlink()
            with mock.patch('huggingface_hub.snapshot_download', return_value=str(root / 'snapshot')), \
                    mock.patch.object(site_build, 'dataset_revision', return_value='fixed-commit'), \
                    mock.patch.object(export, 'build') as exporter:
                with self.assertRaisesRegex(ValueError, 'Missing 1 required game logs'):
                    site_build.build(root / 'dist', manifests=root / 'manifests')
                exporter.assert_not_called()

    def test_build_uses_committed_manifests_and_excludes_extra_cached_games(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            games = ['v17/f6-new/game-01', 'v17/f7-new/game-01']
            for game in games:
                write_game(root / 'manifests' / game)
                write_game(root / 'snapshot' / game)
                # A stale dataset result must not replace the committed result.
                (root / 'snapshot' / game / 'result.json').write_text('{}')
            write_game(root / 'snapshot/v17/f7-extra/game-99')
            with mock.patch('huggingface_hub.snapshot_download', return_value=str(root / 'snapshot')) as download, \
                    mock.patch.object(site_build, 'dataset_revision', return_value='fixed-commit'):
                rows = site_build.build(root / 'dist', manifests=root / 'manifests')
            self.assertEqual({row['id'] for row in rows}, set(games))
            self.assertTrue(all(row['winner'] == 'good' for row in rows))
            self.assertEqual(len(download.call_args_list), 2)
            for call in download.call_args_list:
                self.assertEqual(call.kwargs['revision'], 'fixed-commit')
                self.assertIs(call.kwargs['token'], False)

    def test_empty_manifests_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'empty library'):
                site_build.manifest_games(directory)


if __name__ == '__main__':
    unittest.main()
