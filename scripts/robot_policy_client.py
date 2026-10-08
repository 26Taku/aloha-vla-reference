"""Generate a fixed LeRobot client config; --execute connects and moves the robot."""
import argparse
import json
import math
import sys
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--policy', choices=['smolvla', 'pi05'], required=True)
    parser.add_argument('--joint-cap', type=float, required=True)
    parser.add_argument('--gripper-cap', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not all(math.isfinite(x) and x > 0 for x in [args.joint_cap, args.gripper_cap]):
        raise ValueError('Caps must be finite and positive; this is not a safety certification')
    checkpoint = args.checkpoint.resolve()
    model = json.loads((checkpoint / 'config.json').read_text())
    if model['type'] != args.policy:
        raise ValueError('Checkpoint type differs from selected policy')
    record = yaml.safe_load(args.record.read_text())
    robot_cfg = record['robot']
    if robot_cfg['type'] != 'bi_widowxai_follower_robot':
        raise ValueError('This example only supports bi_widowxai_follower_robot')
    task = record['dataset']['single_task']
    if not isinstance(task, str) or not task.strip():
        raise ValueError('Record config must contain a nonempty single_task')
    robot_cfg['left_arm_max_relative_target'] = args.gripper_cap
    robot_cfg['right_arm_max_relative_target'] = args.gripper_cap
    config = {
        'robot': robot_cfg, 'policy_type': args.policy,
        'pretrained_name_or_path': str(checkpoint), 'actions_per_chunk': 50,
        'task': task, 'server_address': '127.0.0.1:8080',
        'policy_device': 'cuda', 'client_device': 'cpu', 'fps': 30,
        'chunk_size_threshold': 0.5, 'aggregate_fn_name': 'weighted_average',
        'debug_visualize_queue_size': False,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    config_path = args.output / 'client.yaml'
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    (args.output / 'requested_limits.json').write_text(json.dumps({
        'joint_rad': args.joint_cap, 'gripper_m': args.gripper_cap,
        'scope': 'Requested caps, not proof of application or safety.',
    }, indent=2))
    if not args.execute:
        print(f'CLIENT CONFIG: PASS (robot not created or connected): {config_path}', flush=True)
        return

    from lerobot.async_inference import robot_client
    from lerobot.utils.import_utils import register_third_party_plugins
    original_factory = robot_client.make_robot_from_config

    def make_robot_with_limits(cfg):
        robot = original_factory(cfg)
        applied = {}
        for side in ['left_arm', 'right_arm']:
            arm = getattr(robot, side)
            names = list(arm.config.joint_names)
            joints = {f'joint_{i}' for i in range(6)}
            if len(names) != 7 or len(set(names)) != 7 or not joints.issubset(names):
                raise ValueError(f'Unexpected joint names: {names}')
            limits = {name: args.joint_cap if name in joints else args.gripper_cap for name in names}
            arm.config.max_relative_target = limits
            applied[side] = limits
            print(f'{side} limits: {limits}', flush=True)
        (args.output / 'effective_limits.json').write_text(json.dumps(applied, indent=2))
        return robot

    robot_client.make_robot_from_config = make_robot_with_limits
    register_third_party_plugins()
    sys.argv = ['robot_client', f'--config_path={config_path}']
    robot_client.async_client()


if __name__ == '__main__':
    main()
