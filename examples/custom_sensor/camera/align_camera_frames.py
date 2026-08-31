#!/usr/bin/env python3
"""
Causally align asynchronous camera/video frames to LeRobot robot frames.

For each robot observation time t_robot, choose the newest camera frame with:

    camera_time <= t_robot

The same camera frame may be referenced by multiple robot frames. No future
camera frame is ever used and video frames are not duplicated.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
from pathlib import Path


def load_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{n}: {e}") from e
    return rows


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--robot-frames", type=Path, required=True)
    p.add_argument("--camera-timestamps", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-age-ms", type=float, default=None)
    args = p.parse_args()

    robot = load_jsonl(args.robot_frames)
    camera = load_jsonl(args.camera_timestamps)
    if not robot or not camera:
        raise SystemExit("[FAIL] Empty robot or camera timestamp file.")

    rt = [int(r["observation_end_monotonic_ns"]) for r in robot]
    ct = [int(c["receive_monotonic_ns"]) for c in camera]
    if any(b < a for a, b in zip(rt, rt[1:])):
        raise SystemExit("[FAIL] Robot timestamps are not monotonic.")
    if any(b < a for a, b in zip(ct, ct[1:])):
        raise SystemExit("[FAIL] Camera timestamps are not monotonic.")

    max_age_ns = None if args.max_age_ms is None else int(args.max_age_ms * 1e6)
    ages = []
    aligned = 0
    missing = 0
    reused = 0
    last_camera_index = None

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as out:
        for r, t in zip(robot, rt, strict=True):
            i = bisect.bisect_right(ct, t) - 1
            base = {
                "episode_index": r.get("episode_index"),
                "frame_index": r.get("frame_index"),
                "dataset_timestamp_s": r.get("dataset_timestamp_s"),
                "robot_time_ns": t,
            }

            if i < 0:
                out.write(json.dumps({
                    **base,
                    "status": "missing",
                    "reason": "no_prior_camera_frame",
                }, separators=(",", ":")) + "\n")
                missing += 1
                continue

            age = t - ct[i]
            if max_age_ns is not None and age > max_age_ns:
                out.write(json.dumps({
                    **base,
                    "status": "missing",
                    "reason": "camera_frame_too_old",
                    "candidate_camera_age_ns": age,
                }, separators=(",", ":")) + "\n")
                missing += 1
                continue

            if last_camera_index == i:
                reused += 1
            last_camera_index = i
            c = camera[i]

            out.write(json.dumps({
                **base,
                "status": "aligned",
                "camera_frame_index": c.get("frame_index", i),
                "camera_time_ns": ct[i],
                "camera_pts_time_s": c.get("pts_time_s"),
                "camera_age_ns": age,
                "video": c.get("video"),
                "video_frame_index": c.get("video_frame_index", i),
                "timestamp_source": c.get("timestamp_source"),
            }, separators=(",", ":")) + "\n")
            ages.append(age)
            aligned += 1

    med = percentile(ages, 0.50)
    p95 = percentile(ages, 0.95)
    mx = max(ages) if ages else None

    def ms(x):
        return "n/a" if x is None else f"{x/1e6:.3f} ms"

    print("=== Async Camera Alignment ===")
    print(f"robot frames        : {len(robot)}")
    print(f"camera frames       : {len(camera)}")
    print(f"aligned frames      : {aligned}")
    print(f"missing frames      : {missing}")
    print("future frames used  : 0")
    print(f"reused assignments  : {reused}")
    print(f"camera age median   : {ms(med)}")
    print(f"camera age p95      : {ms(p95)}")
    print(f"camera age max      : {ms(mx)}")
    print(f"output              : {args.output}")

    if missing:
        print("[WARN] Some robot frames have no acceptable camera frame.")
    else:
        print("[PASS] Camera alignment is causal and complete.")


if __name__ == "__main__":
    main()
