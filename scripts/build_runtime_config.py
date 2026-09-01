#!/usr/bin/env python3
"""Build a complete LeRobot runtime YAML from a tracked template and local hardware identity."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

PLACEHOLDER_PREFIX = "REPLACE_WITH_"

REQUIRED_ARM_KEYS = (
    "follower_left_ip",
    "follower_right_ip",
    "leader_left_ip",
    "leader_right_ip",
)

REQUIRED_CAMERA_KEYS = (
    "cam_high",
    "cam_low",
    "cam_left_wrist",
    "cam_right_wrist",
)


def load_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level YAML value must be a mapping")
    return data


def normalize_identifier(value: Any, field: str) -> str:
    if value is None:
        raise ValueError(f"{field}: value is missing")
    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError(f"{field}: identifier must be a scalar value")

    text = str(value).strip()
    if not text:
        raise ValueError(f"{field}: value is empty")
    if text.startswith(PLACEHOLDER_PREFIX):
        raise ValueError(f"{field}: placeholder has not been replaced")
    return text


def load_hardware(path: Path) -> dict[str, dict[str, str]]:
    data = load_mapping(path)

    arms = data.get("arms")
    cameras = data.get("cameras")
    if not isinstance(arms, dict):
        raise ValueError(f"{path}: 'arms' must be a mapping")
    if not isinstance(cameras, dict):
        raise ValueError(f"{path}: 'cameras' must be a mapping")

    missing_arms = [key for key in REQUIRED_ARM_KEYS if key not in arms]
    missing_cameras = [key for key in REQUIRED_CAMERA_KEYS if key not in cameras]
    if missing_arms:
        raise ValueError(f"{path}: missing arm keys: {', '.join(missing_arms)}")
    if missing_cameras:
        raise ValueError(f"{path}: missing camera keys: {', '.join(missing_cameras)}")

    normalized_arms = {
        key: normalize_identifier(value, f"arms.{key}")
        for key, value in arms.items()
    }
    normalized_cameras = {
        key: normalize_identifier(value, f"cameras.{key}")
        for key, value in cameras.items()
    }

    if len(normalized_arms.values()) != len(set(normalized_arms.values())):
        raise ValueError(f"{path}: Arm IP addresses must be unique")
    if len(normalized_cameras.values()) != len(set(normalized_cameras.values())):
        raise ValueError(f"{path}: camera serials must be unique")

    return {"arms": normalized_arms, "cameras": normalized_cameras}


def build_runtime_config(
    template: dict[str, Any],
    hardware: dict[str, dict[str, str]],
) -> dict[str, Any]:
    cfg = deepcopy(template)

    robot = cfg.get("robot")
    teleop = cfg.get("teleop")
    if not isinstance(robot, dict):
        raise ValueError("template: 'robot' must be a mapping")
    if not isinstance(teleop, dict):
        raise ValueError("template: 'teleop' must be a mapping")

    arms = hardware["arms"]
    robot["left_arm_ip_address"] = arms["follower_left_ip"]
    robot["right_arm_ip_address"] = arms["follower_right_ip"]
    teleop["left_arm_ip_address"] = arms["leader_left_ip"]
    teleop["right_arm_ip_address"] = arms["leader_right_ip"]

    template_cameras = robot.get("cameras")
    if not isinstance(template_cameras, dict) or not template_cameras:
        raise ValueError("template: 'robot.cameras' must be a non-empty mapping")

    hardware_cameras = hardware["cameras"]

    missing_in_hardware = sorted(set(template_cameras) - set(hardware_cameras))
    if missing_in_hardware:
        raise ValueError(
            "hardware config is missing camera identities required by the template: "
            + ", ".join(missing_in_hardware)
        )

    unused_hardware_cameras = sorted(set(hardware_cameras) - set(template_cameras))
    if unused_hardware_cameras:
        raise ValueError(
            "hardware config contains cameras that are not defined in the template: "
            + ", ".join(unused_hardware_cameras)
        )

    for camera_name, camera_cfg in template_cameras.items():
        if not isinstance(camera_cfg, dict):
            raise ValueError(
                f"template: robot.cameras.{camera_name} must be a mapping"
            )
        camera_cfg["serial_number_or_name"] = hardware_cameras[camera_name]

    return cfg


def apply_record_overrides(cfg: dict[str, Any], args: argparse.Namespace) -> None:
    record_options = (
        args.dataset_name,
        args.task,
        args.num_episodes,
        args.episode_time_s,
        args.dataset_root,
    )
    if not any(value is not None for value in record_options):
        return

    dataset = cfg.get("dataset")
    if not isinstance(dataset, dict):
        raise ValueError("record overrides were supplied, but template has no 'dataset' mapping")

    if args.dataset_name is not None:
        dataset["repo_id"] = f"local/{args.dataset_name}"
    if args.task is not None:
        dataset["single_task"] = args.task
    if args.num_episodes is not None:
        if args.num_episodes < 1:
            raise ValueError("--num-episodes must be >= 1")
        dataset["num_episodes"] = args.num_episodes
    if args.episode_time_s is not None:
        if args.episode_time_s <= 0:
            raise ValueError("--episode-time-s must be > 0")
        dataset["episode_time_s"] = args.episode_time_s
    if args.dataset_root is not None:
        dataset["root"] = str(args.dataset_root)

    dataset["push_to_hub"] = False
    dataset["private"] = True
    dataset["video"] = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--hardware", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)

    parser.add_argument("--dataset-name")
    parser.add_argument("--task")
    parser.add_argument("--num-episodes", type=int)
    parser.add_argument("--episode-time-s", type=float)
    parser.add_argument("--dataset-root", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    template = load_mapping(args.template)
    hardware = load_hardware(args.hardware)
    cfg = build_runtime_config(template, hardware)
    apply_record_overrides(cfg, args)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(cfg, sort_keys=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
