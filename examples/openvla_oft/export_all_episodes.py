"""Use the existing validated exporter for every episode into a new work area."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np
import pyarrow.parquet as pq


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--exporter', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    # Refuse to mix these exports with the old one-episode loader check.
    a.output.mkdir(parents=True, exist_ok=False)
    train = a.output/'train'; train.mkdir()
    files = sorted(a.source.glob('data/chunk-*/file-*.parquet'))
    if not files:
        raise FileNotFoundError('No data Parquet files')
    ids = np.concatenate([pq.read_table(x, columns=['episode_index']).column('episode_index').to_numpy() for x in files])
    episodes, counts = np.unique(ids, return_counts=True)
    info = json.loads((a.source/'meta/info.json').read_text())
    assert len(episodes) == info['total_episodes']
    assert len(ids) == info['total_frames']
    manifest = []
    for episode, count in zip(episodes, counts):
        target = train/f'episode_{int(episode)}.hdf5'
        subprocess.run([
            sys.executable, str(a.exporter.resolve()), '--source', str(a.source.resolve()),
            '--episode', str(int(episode)), '--output', str(target.resolve()),
        ], check=True)
        with h5py.File(target, 'r') as f:
            assert len(f['action']) == int(count)
            assert int(f.attrs['source_episode_index']) == int(episode)
        manifest.append({'episode': int(episode), 'frames': int(count), 'file': target.name})
    (a.output/'manifest.json').write_text(json.dumps({
        'source': str(a.source.resolve()), 'total_episodes': len(episodes),
        'total_frames': len(ids), 'split': 'train only; no held-out validation', 'episodes': manifest,
    }, indent=2))
    print(f'FULL EXPORT: PASS; episodes={len(episodes)} frames={len(ids)}')


if __name__ == '__main__':
    main()
