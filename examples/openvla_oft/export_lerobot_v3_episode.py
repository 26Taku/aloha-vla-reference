"""Export one LeRobotDataset v3 episode for the OpenVLA-OFT ALOHA RLDS builder.

Preserves episode observations, actions, and task metadata for data-loader
checks. Physical action compatibility must be verified separately.
"""

import argparse
import json
from pathlib import Path

import h5py
import numpy as np
import pyarrow.parquet as pq
from PIL import Image
from lerobot.datasets.lerobot_dataset import LeRobotDataset


CAMERAS = {
    "cam_high": "observation.images.cam_high",
    "cam_low": "observation.images.cam_low",
    "cam_left_wrist": "observation.images.cam_left_wrist",
    "cam_right_wrist": "observation.images.cam_right_wrist",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="LeRobot v3 dataset root")
    parser.add_argument("--episode", type=int, default=0, help="Source episode_index")
    parser.add_argument("--output", type=Path, required=True, help="New episode_N.hdf5 path")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    info = json.loads((source / "meta/info.json").read_text(encoding="utf-8"))
    fps = int(info["fps"])
    assert fps > 0
    parquet_paths = sorted(source.glob("data/chunk-*/file-*.parquet"))
    if not parquet_paths:
        raise FileNotFoundError(f"No data parquet files under {source}")
    episode_indices = np.concatenate([
        pq.read_table(path, columns=["episode_index"])
        .column("episode_index").to_numpy()
        for path in parquet_paths
    ])
    rows = np.flatnonzero(episode_indices == args.episode)
    if len(rows) == 0 or not np.array_equal(rows, np.arange(rows[0], rows[-1] + 1)):
        raise ValueError("Episode missing or not contiguous in dataset rows")

    dataset = LeRobotDataset(repo_id=f"local/{source.name}", root=source)
    if len(dataset) != len(episode_indices):
        raise ValueError("LeRobot row count differs from Parquet")
    output.parent.mkdir(parents=True, exist_ok=True)

    # Exclusive creation prevents replacing an existing export by accident.
    with h5py.File(output, "x") as file:
        file.attrs["sim"] = False
        file.attrs["fps"] = fps
        file.attrs["source_dataset"] = source.name
        file.attrs["source_episode_index"] = args.episode
        obs = file.create_group("observations")
        states = obs.create_dataset("qpos", (len(rows), 14), dtype="float32")
        actions = file.create_dataset("action", (len(rows), 14), dtype="float32")
        images = obs.create_group("images")
        image_outputs = {
            name: images.create_dataset(
                name, (len(rows), 256, 256, 3), dtype="uint8",
                chunks=(1, 256, 256, 3),
            )
            for name in CAMERAS
        }

        instruction = None
        for local_index, global_index in enumerate(rows):
            row = dataset[int(global_index)]
            if int(row["episode_index"]) != args.episode:
                raise ValueError(f"Episode mismatch at row {global_index}")
            if int(row["frame_index"]) != local_index:
                raise ValueError(f"Frame index mismatch at row {global_index}")
            if abs(float(row["timestamp"]) - local_index / fps) >= 0.001:
                raise ValueError(f"Timestamp mismatch at row {global_index}")
            task = row["task"]
            if instruction is None:
                instruction = task
                file.attrs["language_instruction"] = task
            elif task != instruction:
                raise ValueError("Task instruction changes within episode")

            state = row["observation.state"].cpu().numpy()
            action = row["action"].cpu().numpy()
            if state.shape != (14,) or action.shape != (14,):
                raise ValueError("Expected 14D state and action")
            if not np.isfinite(state).all() or not np.isfinite(action).all():
                raise ValueError(f"Nonfinite state or action at row {global_index}")
            states[local_index] = state
            actions[local_index] = action

            for name, key in CAMERAS.items():
                frame = row[key].permute(1, 2, 0).cpu().numpy()
                if frame.shape[2] != 3:
                    raise ValueError(f"Expected RGB image for {key}")
                if np.issubdtype(frame.dtype, np.floating):
                    if frame.min() < 0 or frame.max() > 1.001:
                        raise ValueError(f"Image range outside [0, 1] for {key}")
                    frame = np.rint(np.clip(frame, 0, 1) * 255).astype(np.uint8)
                else:
                    frame = frame.astype(np.uint8)
                image_outputs[name][local_index] = np.asarray(
                    Image.fromarray(frame).resize(
                        (256, 256), resample=Image.Resampling.BICUBIC
                    )
                )

    print(f"Created {output}: episode={args.episode}, frames={len(rows)}, fps={fps}")


if __name__ == "__main__":
    main()
