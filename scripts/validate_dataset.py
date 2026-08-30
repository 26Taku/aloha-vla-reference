#!/usr/bin/env python3

import argparse
import json
import math
import sys
from pathlib import Path

import av
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml


def result(status: str, message: str) -> None:
    print(f"[{status}] {message}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a LeRobot dataset against the lab ALOHA reference schema."
    )
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--expected-action-dim", type=int, default=14)
    parser.add_argument("--expected-state-dim", type=int, default=14)
    parser.add_argument("--expected-version", default="v3.0")
    args = parser.parse_args()

    root = args.dataset.resolve()
    config_path = args.config.resolve()

    failures = 0
    warnings = 0

    def ok(message):
        result("OK", message)

    def fail(message):
        nonlocal failures
        failures += 1
        result("FAIL", message)

    def warn(message):
        nonlocal warnings
        warnings += 1
        result("WARN", message)

    print("=== LeRobot Dataset Validation ===")
    print(f"Dataset: {root}")
    print()

    # ------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------
    print("Metadata")

    info_path = root / "meta" / "info.json"

    if not info_path.is_file():
        fail(f"Missing {info_path}")
        return 1

    try:
        info = json.loads(info_path.read_text())
        ok("meta/info.json is readable")
    except Exception as exc:
        fail(f"Could not parse info.json: {exc}")
        return 1

    version = info.get("codebase_version")
    if version == args.expected_version:
        ok(f"Dataset version: {version}")
    else:
        fail(
            f"Dataset version: {version!r} "
            f"(expected {args.expected_version!r})"
        )

    fps = info.get("fps")
    if isinstance(fps, (int, float)) and fps > 0:
        ok(f"FPS: {fps}")
    else:
        fail(f"Invalid FPS: {fps!r}")

    total_frames_meta = info.get("total_frames")
    total_episodes_meta = info.get("total_episodes")

    if isinstance(total_frames_meta, int) and total_frames_meta > 0:
        ok(f"Metadata frames: {total_frames_meta}")
    else:
        fail(f"Invalid total_frames: {total_frames_meta!r}")

    if isinstance(total_episodes_meta, int) and total_episodes_meta > 0:
        ok(f"Metadata episodes: {total_episodes_meta}")
    else:
        fail(f"Invalid total_episodes: {total_episodes_meta!r}")

    print()

    # ------------------------------------------------------------
    # Expected schema
    # ------------------------------------------------------------
    print("Schema")

    try:
        cfg = yaml.safe_load(config_path.read_text())
        camera_names = list(cfg["robot"].get("cameras", {}).keys())
    except Exception as exc:
        fail(f"Could not read config {config_path}: {exc}")
        return 1

    features = info.get("features", {})

    for required in ("action", "observation.state"):
        if required in features:
            ok(f"Feature exists: {required}")
        else:
            fail(f"Missing required feature: {required}")

    action_shape = features.get("action", {}).get("shape")
    state_shape = features.get("observation.state", {}).get("shape")

    if action_shape == [args.expected_action_dim]:
        ok(f"action dimension: {args.expected_action_dim}")
    else:
        fail(
            f"action shape is {action_shape}; "
            f"expected [{args.expected_action_dim}]"
        )

    if state_shape == [args.expected_state_dim]:
        ok(f"observation.state dimension: {args.expected_state_dim}")
    else:
        fail(
            f"observation.state shape is {state_shape}; "
            f"expected [{args.expected_state_dim}]"
        )

    expected_video_features = [
        f"observation.images.{name}" for name in camera_names
    ]

    for feature in expected_video_features:
        if feature in features and features[feature].get("dtype") == "video":
            shape = features[feature].get("shape")
            ok(f"{feature}: video {shape}")
        else:
            fail(f"Missing required video feature: {feature}")

    print()

    # ------------------------------------------------------------
    # Parquet data
    # ------------------------------------------------------------
    print("Parquet")

    parquet_files = sorted((root / "data").glob("**/*.parquet"))

    if not parquet_files:
        fail("No data parquet files found")
    else:
        ok(f"Found {len(parquet_files)} data parquet file(s)")

    total_rows = 0
    last_timestamp = {}
    last_frame_index = {}
    episode_stats = {}

    observed_action_dim = None
    observed_state_dim = None

    for parquet_path in parquet_files:
        try:
            parquet_file = pq.ParquetFile(parquet_path)
        except Exception as exc:
            fail(f"Could not open {parquet_path}: {exc}")
            continue

        required_columns = {
            "action",
            "observation.state",
            "timestamp",
            "frame_index",
            "episode_index",
        }

        columns = set(parquet_file.schema_arrow.names)

        missing = required_columns - columns
        if missing:
            fail(
                f"{parquet_path.name}: missing column(s): "
                + ", ".join(sorted(missing))
            )
            continue

        action_type = parquet_file.schema_arrow.field("action").type
        state_type = parquet_file.schema_arrow.field("observation.state").type

        if pa.types.is_fixed_size_list(action_type):
            observed_action_dim = action_type.list_size

        if pa.types.is_fixed_size_list(state_type):
            observed_state_dim = state_type.list_size

        for batch in parquet_file.iter_batches(
            columns=[
                "timestamp",
                "frame_index",
                "episode_index",
            ],
            batch_size=4096,
        ):
            timestamps = np.asarray(batch.column("timestamp"))
            frames = np.asarray(batch.column("frame_index"))
            episodes = np.asarray(batch.column("episode_index"))

            total_rows += len(timestamps)

            for ts, frame, episode in zip(timestamps, frames, episodes):
                ts = float(ts)
                frame = int(frame)
                episode = int(episode)

                if not math.isfinite(ts):
                    fail(f"Non-finite timestamp in episode {episode}")
                    continue

                if episode in last_timestamp and ts <= last_timestamp[episode]:
                    fail(
                        f"Timestamp is not strictly increasing "
                        f"in episode {episode}"
                    )

                if (
                    episode in last_frame_index
                    and frame != last_frame_index[episode] + 1
                ):
                    fail(
                        f"Non-contiguous frame_index in episode {episode}: "
                        f"{last_frame_index[episode]} -> {frame}"
                    )

                last_timestamp[episode] = ts
                last_frame_index[episode] = frame

                stats = episode_stats.setdefault(
                    episode,
                    {
                        "first_ts": ts,
                        "last_ts": ts,
                        "frames": 0,
                    },
                )
                stats["last_ts"] = ts
                stats["frames"] += 1

    if observed_action_dim == args.expected_action_dim:
        ok(f"Parquet action type: float[{observed_action_dim}]")
    else:
        fail(
            f"Parquet action dimension {observed_action_dim}; "
            f"expected {args.expected_action_dim}"
        )

    if observed_state_dim == args.expected_state_dim:
        ok(f"Parquet state type: float[{observed_state_dim}]")
    else:
        fail(
            f"Parquet state dimension {observed_state_dim}; "
            f"expected {args.expected_state_dim}"
        )

    if total_rows == total_frames_meta:
        ok(f"Parquet rows == metadata frames: {total_rows}")
    else:
        fail(
            f"Parquet rows ({total_rows}) != "
            f"metadata total_frames ({total_frames_meta})"
        )

    if len(episode_stats) == total_episodes_meta:
        ok(f"Observed episodes: {len(episode_stats)}")
    else:
        fail(
            f"Observed {len(episode_stats)} episode(s); "
            f"metadata says {total_episodes_meta}"
        )

    # Do not require exact duration * fps frame count.
    # Real recording loops can legitimately produce one or a few fewer frames.
    for episode, stats in sorted(episode_stats.items()):
        if stats["frames"] > 1:
            duration = stats["last_ts"] - stats["first_ts"]

            if duration > 0:
                effective_fps = (stats["frames"] - 1) / duration

                if abs(effective_fps - fps) / fps <= 0.10:
                    ok(
                        f"Episode {episode}: "
                        f"{stats['frames']} frames, "
                        f"effective {effective_fps:.2f} Hz"
                    )
                else:
                    warn(
                        f"Episode {episode}: "
                        f"effective {effective_fps:.2f} Hz "
                        f"(target {fps} Hz)"
                    )

    print()

    # ------------------------------------------------------------
    # Episode metadata
    # ------------------------------------------------------------
    print("Episode metadata")

    episode_files = sorted((root / "meta" / "episodes").glob("**/*.parquet"))

    if not episode_files:
        fail("No episode metadata parquet found")
    else:
        episode_rows = 0

        for path in episode_files:
            try:
                episode_rows += pq.ParquetFile(path).metadata.num_rows
            except Exception as exc:
                fail(f"Could not read {path}: {exc}")

        if episode_rows == total_episodes_meta:
            ok(f"Episode metadata rows: {episode_rows}")
        else:
            fail(
                f"Episode metadata rows ({episode_rows}) != "
                f"total_episodes ({total_episodes_meta})"
            )

    print()

    # ------------------------------------------------------------
    # Video files
    # ------------------------------------------------------------
    print("Videos")

    for feature in expected_video_features:
        video_dir = root / "videos" / feature
        video_files = sorted(video_dir.glob("**/*.mp4"))

        if not video_files:
            fail(f"No video file found for {feature}")
            continue

        metadata = features[feature]
        expected_height, expected_width, _ = metadata["shape"]
        expected_video_fps = metadata.get("info", {}).get("video.fps", fps)

        for path in video_files:
            if path.stat().st_size == 0:
                fail(f"Empty video file: {path}")
                continue

            try:
                with av.open(str(path)) as container:
                    if not container.streams.video:
                        fail(f"No video stream: {path}")
                        continue

                    stream = container.streams.video[0]

                    if (
                        stream.width != expected_width
                        or stream.height != expected_height
                    ):
                        fail(
                            f"{feature}: video size "
                            f"{stream.width}x{stream.height}, expected "
                            f"{expected_width}x{expected_height}"
                        )
                    else:
                        ok(
                            f"{feature}: "
                            f"{stream.width}x{stream.height}"
                        )

                    if stream.average_rate is not None:
                        actual_fps = float(stream.average_rate)

                        if abs(actual_fps - expected_video_fps) <= 0.5:
                            ok(f"{feature}: {actual_fps:.2f} fps")
                        else:
                            warn(
                                f"{feature}: {actual_fps:.2f} fps, "
                                f"metadata says {expected_video_fps}"
                            )

                    # Decode at least one frame to catch corrupt video files.
                    frame = next(container.decode(video=0), None)

                    if frame is None:
                        fail(f"{feature}: video could not be decoded")
                    else:
                        ok(f"{feature}: first frame decodes correctly")

            except Exception as exc:
                fail(f"{feature}: could not open {path}: {exc}")

    print()
    print("Summary")

    if failures:
        result(
            "FAIL",
            f"{failures} failure(s), {warnings} warning(s). "
            "Dataset should not be used for training yet.",
        )
        return 1

    if warnings:
        result(
            "PASS",
            f"Dataset structure is valid with {warnings} warning(s).",
        )
        return 0

    result("PASS", "Dataset matches the expected ALOHA reference schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
