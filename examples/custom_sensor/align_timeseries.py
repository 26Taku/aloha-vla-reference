#!/usr/bin/env python3
"""
Causally align a native-rate sensor stream to robot frames.

For each robot frame at t_robot, select the newest sensor sample satisfying

    sensor_time <= t_robot

No future sample is ever selected. This is the "current-value" training view.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return records


def require_nondecreasing(values: list[int], name: str) -> None:
    for index in range(1, len(values)):
        if values[index] < values[index - 1]:
            raise ValueError(
                f"{name} is not monotonic at index {index}: "
                f"{values[index - 1]} -> {values[index]}"
            )


def percentile_nearest_rank(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--robot-frames", type=Path, required=True)
    parser.add_argument("--sensor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--robot-time-field", default="observation_end_monotonic_ns")
    parser.add_argument("--sensor-time-field", default="receive_monotonic_ns")
    parser.add_argument(
        "--max-age-ms",
        type=float,
        default=None,
        help="Mark a causal sample missing if it is older than this threshold.",
    )
    args = parser.parse_args()

    robot = load_jsonl(args.robot_frames)
    sensor = load_jsonl(args.sensor)
    if not robot:
        raise SystemExit("Robot frame sidecar is empty.")
    if not sensor:
        raise SystemExit("Sensor sidecar is empty.")

    robot_times = [int(record[args.robot_time_field]) for record in robot]
    sensor_times = [int(record[args.sensor_time_field]) for record in sensor]
    require_nondecreasing(robot_times, "robot timestamps")
    require_nondecreasing(sensor_times, "sensor timestamps")

    max_age_ns = None if args.max_age_ms is None else int(args.max_age_ms * 1e6)
    ages: list[int] = []
    aligned_count = 0
    missing_count = 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for robot_record, robot_time_ns in zip(robot, robot_times, strict=True):
            sensor_index = bisect.bisect_right(sensor_times, robot_time_ns) - 1
            base = {
                "episode_index": robot_record.get("episode_index"),
                "frame_index": robot_record.get("frame_index"),
                "dataset_timestamp_s": robot_record.get("dataset_timestamp_s"),
                "robot_time_ns": robot_time_ns,
            }

            if sensor_index < 0:
                output.write(json.dumps({
                    **base,
                    "status": "missing",
                    "reason": "no_prior_sensor_sample",
                }, separators=(",", ":")) + "\n")
                missing_count += 1
                continue

            sensor_record = sensor[sensor_index]
            sensor_time_ns = sensor_times[sensor_index]
            age_ns = robot_time_ns - sensor_time_ns
            if age_ns < 0:
                raise RuntimeError("Internal error: future sensor sample selected.")

            if max_age_ns is not None and age_ns > max_age_ns:
                output.write(json.dumps({
                    **base,
                    "status": "missing",
                    "reason": "sensor_sample_too_old",
                    "candidate_sensor_age_ns": age_ns,
                }, separators=(",", ":")) + "\n")
                missing_count += 1
                continue

            output.write(json.dumps({
                **base,
                "status": "aligned",
                "sensor_sample_index": sensor_record.get("sample_index", sensor_index),
                "sensor_id": sensor_record.get("sensor_id"),
                "sensor_time_ns": sensor_time_ns,
                "sensor_age_ns": age_ns,
                "source_timestamp_ns": sensor_record.get("source_timestamp_ns"),
                "values": sensor_record.get("values"),
            }, separators=(",", ":")) + "\n")
            ages.append(age_ns)
            aligned_count += 1

    summary = {
        "robot_frames": len(robot),
        "sensor_samples": len(sensor),
        "aligned_frames": aligned_count,
        "missing_frames": missing_count,
        "future_samples_used": 0,
        "sensor_age_ns": {
            "median": percentile_nearest_rank(ages, 0.50),
            "p95": percentile_nearest_rank(ages, 0.95),
            "max": max(ages) if ages else None,
        },
        "robot_time_field": args.robot_time_field,
        "sensor_time_field": args.sensor_time_field,
        "max_age_ms": args.max_age_ms,
    }
    summary_path = args.output.with_suffix(args.output.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    def fmt_ms(value: int | None) -> str:
        return "n/a" if value is None else f"{value / 1e6:.3f} ms"

    print(f"robot frames       : {len(robot)}")
    print(f"sensor samples     : {len(sensor)}")
    print(f"aligned frames     : {aligned_count}")
    print(f"missing frames     : {missing_count}")
    print("future samples used: 0")
    print(f"sensor age median  : {fmt_ms(summary['sensor_age_ns']['median'])}")
    print(f"sensor age p95     : {fmt_ms(summary['sensor_age_ns']['p95'])}")
    print(f"sensor age max     : {fmt_ms(summary['sensor_age_ns']['max'])}")
    print(f"output             : {args.output}")
    print(f"summary            : {summary_path}")


if __name__ == "__main__":
    main()
