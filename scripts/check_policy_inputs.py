"""Check input metadata for the fixed Trossen stack; never loads a model or robot."""
import argparse
import json
from pathlib import Path


def check(dataset, checkpoint, policy):
    info = json.loads((dataset / 'meta/info.json').read_text())
    cfg = json.loads((checkpoint / 'config.json').read_text())
    if cfg.get('type') != policy:
        raise ValueError('Checkpoint type differs from --policy')
    names = [f'left_joint_{i}.pos' for i in range(6)] + ['left_left_carriage_joint.pos']
    names += [f'right_joint_{i}.pos' for i in range(6)] + ['right_left_carriage_joint.pos']
    features = info['features']
    for key in ('action', 'observation.state'):
        if features[key]['shape'] != [14] or features[key].get('names') != names:
            raise ValueError(f'{key}: expected fixed Trossen 14-joint names and order')
    if cfg['input_features']['observation.state']['shape'] != [14]:
        raise ValueError('Checkpoint state shape must be [14]')
    if cfg['output_features']['action']['shape'] != [14]:
        raise ValueError('Checkpoint action shape must be [14]')
    if cfg.get('action_feature_names') not in (None, names):
        raise ValueError('Checkpoint action names differ from Dataset')
    cameras = {k for k in cfg['input_features'] if k.startswith('observation.images.')}
    data_cameras = {k for k in features if k.startswith('observation.images.')}
    if not cameras or cameras != data_cameras:
        raise ValueError('Checkpoint and Dataset cameras differ')
    for key in sorted(cameras):
        shape = features[key]['shape']
        if len(shape) != 3 or shape[2] != 3:
            raise ValueError(f'{key}: expected RGB Dataset shape [height, width, 3]')
        if cfg['input_features'][key]['shape'] != [3, shape[0], shape[1]]:
            raise ValueError(f'{key}: image dimensions differ')
    if policy == 'pi05' and cfg.get('use_relative_actions') is not False:
        raise ValueError('This workflow expects pi05 use_relative_actions=false')
    return {'policy': policy, 'dataset': str(dataset.resolve()),
            'checkpoint': str(checkpoint.resolve()), 'fps': info['fps'],
            'action_names': names, 'state_names': names,
            'input_features': cfg['input_features'],
            'scope': 'Metadata only; not image content, units, model loading or robot behavior.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--policy', choices=['smolvla', 'pi05'], required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.dataset, args.checkpoint, args.policy), indent=2, ensure_ascii=False))
    print('INPUT METADATA CHECK: PASS')


if __name__ == '__main__':
    main()
