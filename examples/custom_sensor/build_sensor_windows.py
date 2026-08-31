#!/usr/bin/env python3
"""
Build causal history-window manifests for a high-rate sensor stream.

For each robot frame at time t, this script identifies sensor samples in

    (t - window, t]

using the same host monotonic clock. It stores only indices/timestamps and
summary metadata; it does not duplicate raw sensor values.

This is the reference input view for policy architectures that want temporal
sensor dynamics instead of only the latest sample.
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
    parser.add_argument("--window-ms", type=float, default=200.0)
    parser.add_argument("--robot-time-field", default="observation_end_monotonic_ns")
    parser.add_argument("--sensor-time-field", default="receive_monotonic_ns")
    parser.add_argument(
        "--min-samples",
        type=int,
        default=1,
        help="Frames with fewer samples are marked insufficient.",
    )
    args = parser.parse_args()

    if args.window_ms <= 0:
        raise SystemExit("--window-ms must be positive")
    if args.min_samples < 0:
        raise SystemExit("--min-samples must be non-negative")

    robot = load_jsonl(args.robot_frames)
    sensor = load_jsonl(args.sensor)
    if not robot:
        raise SystemExit("Robot frame sidecar is empty.")
    if not sensor:
        raise SystemExit("Sensor sidecar is empty.")

    robot_times = [int(r[args.robot_time_field]) for r in robot]
    sensor_times = [int(s[args.sensor_time_field]) for s in sensor]
    require_nondecreasing(robot_times, "robot timestamps")
    require_nondecreasing(sensor_times, "sensor timestamps")

    window_ns = int(args.window_ms * 1e6)
    counts: list[int] = []
    complete = 0
    insufficient = 0
    future_samples_used = 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as output:
        for robot_record, robot_time_ns in zip(robot, robot_times, strict=True):
            window_start_ns = robot_time_ns - window_ns

            # Open-left, closed-right interval: (t-window, t]
            first = bisect.bisect_right(sensor_times, window_start_ns)
            last_exclusive = bisect.bisect_right(sensor_times, robot_time_ns)
            count = max(0, last_exclusive - first)

            if last_exclusive > 0 and sensor_times[last_exclusive - 1] > robot_time_ns:
                future_samples_used += 1

            status = "ok" if count >= args.min_samples else "insufficient"
            if status == "ok":
                complete += 1
            else:
                insufficient += 1

            record = {
                "episode_index": robot_record.get("episode_index"),
                "frame_index": robot_record.get("frame_index"),
                "dataset_timestamp_s": robot_record.get("dataset_timestamp_s"),
                "robot_time_ns": robot_time_ns,
                "window_ms": args.window_ms,
                "window_start_ns": window_start_ns,
                "window_end_ns": robot_time_ns,
                "status": status,
                "num_samples": count,
                "sensor_start_row": first if count else None,
                "sensor_end_row_exclusive": last_exclusive if count else None,
                "sensor_start_sample_index": (
                    sensor[first].get("sample_index", first) if count else None
                ),
                "sensor_end_sample_index": (
                    sensor[last_exclusive - 1].get("sample_index", last_exclusive - 1)
                    if count else None
                ),
                "oldest_sensor_time_ns": sensor_times[first] if count else None,
                "newest_sensor_time_ns": sensor_times[last_exclusive - 1] if count else None,
                "newest_sensor_age_ns": (
                    robot_time_ns - sensor_times[last_exclusive - 1] if count else None
                ),
            }
            output.write(json.dumps(record, separators=(",", ":")) + "\n")
            counts.append(count)

    positive_counts = [c for c in counts if c > 0]
    summary = {
        "robot_frames": len(robot),
        "sensor_samples": len(sensor),
        "window_ms": args.window_ms,
        "min_samples": args.min_samples,
        "ok_frames": complete,
        "insufficient_frames": insufficient,
        "future_samples_used": future_samples_used,
        "samples_per_window": {
            "median": percentile_nearest_rank(positive_counts, 0.50),
            "p05": percentile_nearest_rank(positive_counts, 0.05),
            "p95": percentile_nearest_rank(positive_counts, 0.95),
            "min": min(positive_counts) if positive_counts else None,
            "max": max(positive_counts) if positive_counts else None,
        },
    }
    summary_path = args.output.with_suffix(args.output.suffix + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("=== Sensor History Window Build ===")
    print(f"robot frames        : {len(robot)}")
    print(f"sensor samples      : {len(sensor)}")
    print(f"window              : {args.window_ms:.1f} ms")
    print(f"ok frames           : {complete}")
    print(f"insufficient frames : {insufficient}")
    print(f"future samples used : {future_samples_used}")
    print(
        "samples/window      : "
        f"median={summary['samples_per_window']['median']} "
        f"p05={summary['samples_per_window']['p05']} "
        f"p95={summary['samples_per_window']['p95']} "
        f"min={summary['samples_per_window']['min']} "
        f"max={summary['samples_per_window']['max']}"
    )
    print(f"output              : {args.output}")
    print(f"summary             : {summary_path}")

    if future_samples_used:
        raise SystemExit("[FAIL] Future samples entered at least one history window.")


if __name__ == "__main__":
    main()
