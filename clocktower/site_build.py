"""Build a complete deployable site from committed manifests and public Hugging Face logs.

    python -m clocktower.site_build

Unlike the development exporter, fail if any committed finished game is missing its logs.
No credentials are needed: downloads are anonymous and pinned to one dataset commit per build.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import tempfile
from pathlib import Path

from . import export
from .store import REPO

LOG_FILES = ('events.jsonl', 'probes.jsonl')


def manifest_games(root):
    """Finished game IDs from the exporter's batches, independent of downloaded logs."""
    root = Path(root)
    games = set()
    for batch in (*export.BATCHES, *export.MIXED_BATCHES):
        for result in root.glob(batch + '/game-*/result.json'):
            if json.loads(result.read_text()).get('winner') not in ('good', 'evil'):
                continue
            if not (result.parent / 'config.json').is_file():
                raise ValueError(f'Missing committed config: {result.parent}')
            games.add(result.parent.relative_to(root).as_posix())
    if not games:
        raise ValueError('No finished game manifests found; refusing to publish an empty library')
    return sorted(games)


def prepare_games(manifests, snapshot, destination, games):
    """Stage exactly the committed games; never export extra games left in a download cache."""
    manifests, snapshot, destination = map(Path, (manifests, snapshot, destination))
    missing = [f'{game}/{name}' for game in games for name in LOG_FILES
               if not (snapshot / game / name).is_file()]
    if missing:
        raise ValueError(f'Missing {len(missing)} required game logs: ' + ', '.join(missing[:5]))
    for game in games:
        target = destination / game
        target.mkdir(parents=True, exist_ok=True)
        for name in ('config.json', 'result.json'):
            shutil.copyfile(manifests / game / name, target / name)
        for name in LOG_FILES:
            shutil.copyfile(snapshot / game / name, target / name)


def dataset_revision(revision='main'):
    from huggingface_hub import HfApi
    return HfApi().dataset_info(REPO, revision=revision, token=False).sha


def build(out=export.SITE / 'dist', revision='main', manifests=export.ROOT / 'games'):
    from huggingface_hub import snapshot_download

    games = manifest_games(manifests)
    revision = dataset_revision(revision)
    print(f'Building {len(games)} games from {REPO}@{revision}', flush=True)
    # One batch at a time, using the HF cache for unchanged files. No calls or conversations.
    for batch in (*export.BATCHES, *export.MIXED_BATCHES):
        members = [game for game in games if fnmatch.fnmatchcase(game.rsplit('/', 1)[0], batch)]
        if not members:
            continue
        snapshot = snapshot_download(
            REPO, repo_type='dataset', revision=revision, token=False, max_workers=8,
            allow_patterns=[f'{game}/{name}' for game in members for name in LOG_FILES],
        )
    with tempfile.TemporaryDirectory(prefix='clocktower-site-') as temporary:
        staged = Path(temporary) / 'games'
        prepare_games(manifests, snapshot, staged, games)
        rows = export.build(games_root=staged, out=out)
    actual = {row['id'] for row in rows}
    if actual != set(games):
        raise ValueError(f'Incomplete site build: expected {len(games)} games, exported {len(actual)}')
    print(f'Verified all {len(actual)} game replays', flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='main', help='Hugging Face dataset revision (resolved to a commit)')
    parser.add_argument('--out', type=Path, default=export.SITE / 'dist')
    parser.add_argument('--print-revision', action='store_true', help='Only print the resolved dataset commit')
    args = parser.parse_args()
    if args.print_revision:
        print(dataset_revision(args.revision))
    else:
        build(out=args.out, revision=args.revision)


if __name__ == '__main__':
    main()
