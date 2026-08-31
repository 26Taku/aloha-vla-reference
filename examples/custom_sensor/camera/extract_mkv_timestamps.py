#!/usr/bin/env python3
"""
Export preserved MKV packet timestamps to JSONL.

Assumption:
- The MKV was recorded from V4L2 with `-copyts -timestamps default -c:v copy`.
- Packet PTS therefore remains in the host monotonic clock domain.

Output fields:
- frame_index
- pts_time_s
- receive_monotonic_ns
- video
- video_frame_index

The name `receive_monotonic_ns` is kept for compatibility with the camera
alignment script, but semantically this timestamp comes from the V4L2/FFmpeg
packet PTS rather than Python callback time.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("video", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    video = args.video.expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"[FAIL] Video not found: {video}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "packet=pts_time",
        "-of", "json",
        str(video),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    packets = payload.get("packets", [])
    if not packets:
        raise SystemExit("[FAIL] No video packets found.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    previous_ns = None

    with args.output.open("w", encoding="utf-8") as out:
        for packet in packets:
            pts_text = packet.get("pts_time")
            if pts_text is None:
                continue
            pts_s = float(pts_text)
            pts_ns = round(pts_s * 1_000_000_000)

            if previous_ns is not None and pts_ns < previous_ns:
                raise SystemExit("[FAIL] Packet PTS is not monotonic.")
            previous_ns = pts_ns

            record = {
                "frame_index": written,
                "pts_time_s": pts_s,
                "receive_monotonic_ns": pts_ns,
                "timestamp_source": "V4L2 packet PTS preserved by FFmpeg -copyts",
                "video": str(video),
                "video_frame_index": written,
            }
            out.write(json.dumps(record, separators=(",", ":")) + "\n")
            written += 1

    duration_s = (
        (previous_ns - round(float(packets[0]["pts_time"]) * 1_000_000_000)) / 1e9
        if written > 1
        else 0.0
    )
    effective_hz = (written - 1) / duration_s if duration_s > 0 else 0.0

    print("=== MKV Timestamp Export ===")
    print(f"video frames        : {written}")
    print(f"effective rate      : {effective_hz:.3f} Hz")
    print(f"output              : {args.output}")
    print("[PASS] Monotonic packet timestamps exported.")


if __name__ == "__main__":
    main()
