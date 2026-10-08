"""Compare every exported HDF5 state/action with the generated training RLDS."""
import os, json
from pathlib import Path
import h5py, numpy as np, tensorflow_datasets as tfds
w = Path(os.environ['WORK'])
m = json.loads((w/'aloha_vla_demo/manifest.json').read_text())
b = tfds.builder_from_directory(str(w/'tfds/aloha_vla_demo/1.0.0'))
assert b.info.splits['train'].num_examples == m['total_episodes']
seen = set(); frames = 0
for ep in tfds.as_numpy(b.as_dataset(split='train', shuffle_files=False)):
    path = Path(ep['episode_metadata']['file_path'].decode())
    assert path.parent.resolve() == (w/'aloha_vla_demo/train').resolve()
    assert path.name not in seen; seen.add(path.name)
    with h5py.File(path, 'r') as f:
        n = len(f['action']); count = 0
        for i,s in enumerate(ep['steps']):
            np.testing.assert_array_equal(s['action'], f['action'][i])
            np.testing.assert_array_equal(s['observation']['state'], f['observations/qpos'][i])
            assert s['language_instruction'].decode() == f.attrs['language_instruction']
            assert bool(s['is_first']) == (i == 0)
            assert bool(s['is_last']) == (i == n-1)
            count += 1
        assert count == n; frames += count
assert frames == m['total_frames']
assert len(seen) == m['total_episodes']
print('FULL RLDS READBACK: PASS; episodes=', len(seen), 'frames=', frames)
