"""Inspect saved LeRobot policies on recorded frames; never connects to a robot."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import torch
from PIL import Image, ImageDraw
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.policies import make_pre_post_processors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--policy', choices=['smolvla', 'pi05'], required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--episodes', type=int, default=10)
    a = p.parse_args()
    if a.episodes < 1:
        raise ValueError('episodes must be positive')
    a.output.mkdir(parents=True, exist_ok=False)
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is required for this validation run')
    info = json.loads((a.dataset / 'meta/info.json').read_text())
    paths = sorted(a.dataset.glob('data/chunk-*/file-*.parquet'))
    if not paths:
        raise FileNotFoundError('Dataset Parquet files not found')
    indices = np.concatenate([
        pq.read_table(x, columns=['episode_index']).column('episode_index').to_numpy()
        for x in paths
    ])
    episodes = np.unique(indices)
    selected = episodes[np.unique(np.linspace(0, len(episodes)-1, min(a.episodes, len(episodes))).astype(int))]
    dataset = LeRobotDataset(repo_id='local/' + a.dataset.name, root=a.dataset)
    if len(dataset) != len(indices):
        raise ValueError('Dataset and Parquet row count differ')
    if a.policy == 'smolvla':
        from lerobot.policies.smolvla import SmolVLAPolicy
        cls = SmolVLAPolicy
    else:
        from lerobot.policies.pi05 import PI05Policy
        cls = PI05Policy
    policy = cls.from_pretrained(a.checkpoint).to('cuda').eval()
    pre, post = make_pre_post_processors(
        policy_cfg=policy.config, pretrained_path=a.checkpoint,
        preprocessor_overrides={'device_processor': {'device': 'cuda'}},
    )
    cameras = [k for k in policy.config.input_features if k.startswith('observation.images.')]
    names = info['features']['action'].get('names') or [str(i) for i in range(14)]
    if not isinstance(names, list) or len(names) != 14:
        raise ValueError('Expected a flat list of 14 action names')
    records = []
    for episode in selected:
        rows = np.flatnonzero(indices == episode)
        for index in np.unique([rows[0], rows[len(rows)//2], rows[-1]]):
            frame = dict(dataset[int(index)])
            batch = {k: v.unsqueeze(0) if isinstance(v, torch.Tensor) else [v] for k, v in frame.items()}
            policy.reset()  # Each selected frame is an independent observation.
            torch.cuda.synchronize()
            import time
            start = time.perf_counter()
            with torch.inference_mode():
                prediction = post(policy.select_action(pre(batch)))
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - start
            pred = prediction.detach().float().cpu().numpy()
            assert pred.shape == (1, 14), pred.shape
            assert np.isfinite(pred).all()
            target = frame['action'].float().cpu().numpy()
            state = frame['observation.state'].float().cpu().numpy()
            assert target.shape == state.shape == (14,)
            assert np.isfinite(target).all() and np.isfinite(state).all()
            for j, name in enumerate(names):
                records.append({
                    'episode': int(episode), 'dataset_row': int(index), 'joint': name,
                    'prediction': float(pred[0,j]), 'recorded_action': float(target[j]),
                    'state': float(state[j]), 'prediction_minus_action': float(pred[0,j]-target[j]),
                    'prediction_minus_state': float(pred[0,j]-state[j]),
                    'inference_seconds': elapsed,
                })
            sheet = Image.new('RGB', (320*len(cameras), 205), 'white')
            draw = ImageDraw.Draw(sheet)
            for j, key in enumerate(cameras):
                pixels = frame[key].permute(1,2,0).cpu().numpy()
                assert np.isfinite(pixels).all()
                assert pixels.min() >= 0 and pixels.max() <= 1.001
                tile = Image.fromarray(np.rint(np.clip(pixels,0,1)*255).astype('uint8'))
                tile.thumbnail((320,180))
                sheet.paste(tile, (j*320,25))
                draw.text((j*320+3,3), key.replace('observation.images.',''), fill='black')
            sheet.save(a.output / f'episode_{int(episode):03d}_row_{int(index):06d}.jpg')
            print(f'episode={int(episode)} row={int(index)} action=(1,14) finite=True elapsed={elapsed:.3f}s', flush=True)
    with (a.output/'actions.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    summary = {
        'checkpoint': str(a.checkpoint.resolve()), 'dataset': str(a.dataset.resolve()),
        'policy': a.policy, 'episodes_checked': [int(e) for e in selected],
        'frames_checked': len(records)//14, 'action_names': names,
        'state_names': info['features']['observation.state'].get('names'),
        'input_features': list(policy.config.input_features), 'fps': info['fps'],
        'torch_version': torch.__version__, 'gpu': torch.cuda.get_device_name(),
        'scope': 'Recorded training observations; independent frames; no closed-loop or safety evaluation.',
    }
    (a.output/'summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print('RECORDED-FRAME CHECK: PASS')


if __name__ == '__main__':
    main()
