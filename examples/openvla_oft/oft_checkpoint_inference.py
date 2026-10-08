"""Reload a merged OFT+ checkpoint and infer from an exported HDF5 observation."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import torch
import tensorflow as tf
tf.config.set_visible_devices([], 'GPU')
from prismatic.vla.constants import ACTION_DIM, PROPRIO_DIM, NUM_ACTIONS_CHUNK
from experiments.robot.openvla_utils import (
    get_vla, get_processor, get_action_head, get_proprio_projector, get_vla_action,
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--hdf5', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert (ACTION_DIM, PROPRIO_DIM, NUM_ACTIONS_CHUNK) == (14,14,30)
    assert torch.cuda.is_available()
    if not (a.checkpoint/'config.json').is_file():
        raise FileNotFoundError('Merged model checkpoint not found; use merge_lora_during_training=True')
    for part in ['action_head', 'proprio_projector', 'vision_backbone']:
        if len(list(a.checkpoint.glob(part+'--*.pt'))) != 1:
            raise ValueError(f'Expected exactly one {part} file')
    a.output.mkdir(parents=True, exist_ok=False)
    cfg = SimpleNamespace(
        pretrained_checkpoint=str(a.checkpoint.resolve()), use_film=True,
        lora_rank=32, num_images_in_input=3, load_in_8bit=False, load_in_4bit=False,
        use_l1_regression=True, use_diffusion=False, use_proprio=True,
        center_crop=True, unnorm_key='aloha_vla_demo',
    )
    vla = get_vla(cfg)
    processor = get_processor(cfg)
    head = get_action_head(cfg, vla.llm_dim)
    proprio = get_proprio_projector(cfg, vla.llm_dim, PROPRIO_DIM)
    if cfg.unnorm_key not in vla.norm_stats:
        raise KeyError(f'Normalization key not found: {list(vla.norm_stats)}')
    results = []
    with h5py.File(a.hdf5, 'r') as f:
        n = len(f['action'])
        task = f.attrs['language_instruction']
        if isinstance(task, bytes): task = task.decode('utf-8')
        for i in sorted(set([0,n//2,n-1])):
            # Explicit order: primary, left wrist, right wrist; verify against loader.
            obs = {
                'full_image': f['observations/images/cam_high'][i],
                'left_wrist_image': f['observations/images/cam_left_wrist'][i],
                'right_wrist_image': f['observations/images/cam_right_wrist'][i],
                'state': f['observations/qpos'][i].copy(),
            }
            action = np.asarray(get_vla_action(
                cfg, vla, processor, obs, str(task), action_head=head,
                proprio_projector=proprio, use_film=True,
            ))
            assert action.shape == (30,14), action.shape
            assert np.isfinite(action).all()
            np.save(a.output/f'action_frame_{i}.npy', action)
            results.append({'frame': i, 'shape': list(action.shape), 'finite': True})
            print(f'frame={i} action={action.shape} finite=True', flush=True)
    (a.output/'summary.json').write_text(json.dumps({
        'checkpoint': str(a.checkpoint.resolve()), 'hdf5': str(a.hdf5.resolve()),
        'results': results, 'scope': 'Offline only; short training does not establish task performance.',
    }, indent=2))
    print('OFT CHECKPOINT INFERENCE: PASS')


if __name__ == '__main__':
    main()
