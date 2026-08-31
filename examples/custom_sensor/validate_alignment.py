#!/usr/bin/env python3
"""Validate a causal robot-frame / high-rate-sensor alignment JSONL file."""

from __future__ import annotations

import argparse
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


def percentile_nearest_rank(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("alignment", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--max-p95-age-ms", type=float, default=None)
    args = parser.parse_args()

    records = load_jsonl(args.alignment)
    if not records:
        raise SystemExit("[FAIL] Alignment file is empty.")

    previous_frame_index = None
    ages: list[int] = []
    missing = 0
    future = 0
    malformed = 0

    for record in records:
        frame_index = record.get("frame_index")
        if frame_index is None:
            malformed += 1
        elif previous_frame_index is not None and frame_index <= previous_frame_index:
            malformed += 1
        previous_frame_index = frame_index

        if record.get("status") != "aligned":
            missing += 1
            continue

        age_ns = record.get("sensor_age_ns")
        robot_time_ns = record.get("robot_time_ns")
        sensor_time_ns = record.get("sensor_time_ns")
        if not all(isinstance(v, int) for v in (age_ns, robot_time_ns, sensor_time_ns)):
            malformed += 1
            continue

        if sensor_time_ns > robot_time_ns or age_ns < 0:
            future += 1
        ages.append(age_ns)

    med = percentile_nearest_rank(ages, 0.50)
    p95 = percentile_nearest_rank(ages, 0.95)
    maximum = max(ages) if ages else None

    def fmt_ms(value: int | None) -> str:
        return "n/a" if value is None else f"{value / 1e6:.3f} ms"

    print("=== High-rate Sensor Alignment Validation ===")
    print(f"robot frames        : {len(records)}")
    print(f"aligned frames      : {len(ages)}")
    print(f"missing frames      : {missing}")
    print(f"future samples used : {future}")
    print(f"malformed records   : {malformed}")
    print(f"sensor age median   : {fmt_ms(med)}")
    print(f"sensor age p95      : {fmt_ms(p95)}")
    print(f"sensor age max      : {fmt_ms(maximum)}")

    failures = []
    if future:
        failures.append(f"{future} future sensor sample(s) were used")
    if malformed:
        failures.append(f"{malformed} malformed/non-monotonic record(s)")
    if args.require_complete and missing:
        failures.append(f"{missing} frame(s) have no aligned sensor sample")
    if (
        args.max_p95_age_ms is not None
        and p95 is not None
        and p95 > int(args.max_p95_age_ms * 1e6)
    ):
        failures.append(
            f"p95 sensor age {p95 / 1e6:.3f} ms exceeds "
            f"{args.max_p95_age_ms:.3f} ms"
        )

    if failures:
        print("[FAIL] " + "; ".join(failures))
        raise SystemExit(1)

    print("[PASS] Alignment is causal and structurally valid.")


if __name__ == "__main__":
    main()
