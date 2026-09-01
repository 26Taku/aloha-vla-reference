# Custom Sensor Script Reference

このdirectoryは、[03 Architecture and Sensor Extension](../../docs/03_architecture_and_extension.md) で使用するreference scriptを提供する。

**新しいsensorを追加するときの実行順序は03を参照する。**  
本資料はscriptごとのCLI、input、outputを確認するときに使用する。

## 1. Script map

| Script | Purpose | Main input | Main output |
|---|---|---|---|
| `record_with_timestamps.py` | LeRobot recordingへhost timestamp sidecarを追加 | LeRobot runtime YAML | Dataset + `meta/frame_timestamps/*.jsonl` |
| `ros2_timeseries_logger.py` | ROS 2 numeric streamをnative/actual rateで保存 | ROS 2 topic | raw JSONL + metadata |
| `align_timeseries.py` | robot frameへcausal latest numeric sampleを対応付け | robot timestamp + sensor JSONL | alignment JSONL + summary |
| `validate_alignment.py` | numeric alignmentのcausality / completenessを検証 | alignment JSONL | PASS / FAIL + age統計 |
| `build_sensor_windows.py` | `(t-W, t]` のhistory-window manifestを生成 | robot timestamp + sensor JSONL | window JSONL + summary |
| `camera/extract_mkv_timestamps.py` | MKV packet PTSをJSONLへexport | MKV | camera timestamp JSONL |
| `camera/align_camera_frames.py` | robot frameへcausal latest camera frameを対応付け | robot + camera timestamps | camera alignment JSONL |

camera device discoveryとFFmpeg capture optionは [camera/README.md](camera/README.md) を参照する。

---

## 2. `record_with_timestamps.py`

### Purpose

LeRobot 0.6.0のrecord loopへ実行時patchを適用し、通常のDataset frameごとにhost monotonic timestampをsidecarへ保存する。

representative robot time:

```text
observation_end_monotonic_ns
```

### Runtime configの生成例

repository root:

```bash
mkdir -p .runtime data

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output ../.runtime/sensor-record.yaml \
    --dataset-name sensor_reference \
    --task "Sensor reference recording" \
    --num-episodes 1 \
    --episode-time-s 10 \
    --dataset-root ../data/sensor_reference
)
```

### Run

```bash
(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path=../.runtime/sensor-record.yaml
)
```

### Output

```text
data/sensor_reference/meta/frame_timestamps/
├── episode_000000.jsonl
└── episode_000000.meta.json
```

JSONLには以下を含む。

```text
episode_index
frame_index
dataset_timestamp_s
loop_start_monotonic_ns
observation_start_monotonic_ns
observation_end_monotonic_ns
observation_end_wall_ns
action_sent_monotonic_ns
frame_added_monotonic_ns
observation_duration_ns
```

---

## 3. `ros2_timeseries_logger.py`

### Purpose

任意のROS 2 numeric messageをflattenし、callback entry時のhost monotonic timestampとともにJSONLへ保存する。

### Prerequisites

実行shellで次が使用できること。

```bash
ros2 topic list
python3 -c "import rclpy; import rosidl_runtime_py"
```

対象message packageも同じenvironmentからimport可能である必要がある。

### Run

```bash
python3 examples/custom_sensor/ros2_timeseries_logger.py \
  --topic <TOPIC> \
  --msg-type <PACKAGE/msg/TYPE> \
  --sensor-id <SENSOR_ID> \
  --output <RAW_JSONL> \
  --duration 10
```

主なoption:

```text
--topic              required
--msg-type           required
--sensor-id          default: external_sensor
--output             required
--duration           0 = Ctrl+Cまで継続
--qos-reliability    best_effort | reliable
--flush-interval     default: 0.5 s
```

### Output

`<RAW_JSONL>`:

```json
{
  "sample_index": 0,
  "sensor_id": "example",
  "source_timestamp_ns": 0,
  "receive_wall_ns": 0,
  "receive_monotonic_ns": 0,
  "elapsed_s": 0.0,
  "values": {}
}
```

`<RAW_JSONL>.meta.json`:

```text
topic
msg_type
sensor_id
receive clock
wall clock
QoS reliability
```

`header.stamp` が存在するmessageでは `source_timestamp_ns` として保存する。

---

## 4. `align_timeseries.py`

### Purpose

各robot frame時刻 `t_robot` に対して、

```text
sensor_time <= t_robot
```

を満たす最新sampleを選択する。

### Run

```bash
python3 examples/custom_sensor/align_timeseries.py \
  --robot-frames <ROBOT_TIMESTAMP_JSONL> \
  --sensor <RAW_SENSOR_JSONL> \
  --output <ALIGNMENT_JSONL>
```

optional:

```text
--robot-time-field    default: observation_end_monotonic_ns
--sensor-time-field   default: receive_monotonic_ns
--max-age-ms          古すぎるsampleをmissingとして扱うthreshold
```

### Output summary

```text
robot frames
sensor samples
aligned frames
missing frames
future samples used
sensor age median
sensor age p95
sensor age max
```

`<ALIGNMENT_JSONL>.summary.json` も生成する。

---

## 5. `validate_alignment.py`

### Run

```bash
python3 examples/custom_sensor/validate_alignment.py \
  <ALIGNMENT_JSONL>
```

smoke testで全robot frameにsampleを要求する場合:

```bash
python3 examples/custom_sensor/validate_alignment.py \
  <ALIGNMENT_JSONL> \
  --require-complete
```

optional:

```text
--max-p95-age-ms <MS>
```

PASS条件:

- future sample = 0
- malformed record = 0
- `--require-complete` 使用時はmissing = 0
- `--max-p95-age-ms` 指定時はthreshold以内

---

## 6. `build_sensor_windows.py`

### Purpose

各robot frame時刻 `t` に対して、

```text
(t - window, t]
```

のsensor sample範囲を生成する。

raw valueは複製せず、sample index / timestamp rangeをmanifestへ保存する。

### Run

```bash
python3 examples/custom_sensor/build_sensor_windows.py \
  --robot-frames <ROBOT_TIMESTAMP_JSONL> \
  --sensor <RAW_SENSOR_JSONL> \
  --output <WINDOW_JSONL> \
  --window-ms 200
```

optional:

```text
--min-samples <N>
--robot-time-field <FIELD>
--sensor-time-field <FIELD>
```

output summary:

```text
robot frames
sensor samples
window
ok frames
insufficient frames
future samples used
samples/window median / p05 / p95 / min / max
```

---

## 7. Camera scripts

### `camera/extract_mkv_timestamps.py`

```bash
python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  <VIDEO_MKV> \
  --output <CAMERA_TIMESTAMP_JSONL>
```

前提:

- V4L2 capture
- FFmpeg `-copyts`
- `-timestamps default`
- stream copy (`-c:v copy`)

output:

```text
frame_index
pts_time_s
receive_monotonic_ns
timestamp_source
video
video_frame_index
```

### `camera/align_camera_frames.py`

```bash
python3 examples/custom_sensor/camera/align_camera_frames.py \
  --robot-frames <ROBOT_TIMESTAMP_JSONL> \
  --camera-timestamps <CAMERA_TIMESTAMP_JSONL> \
  --output <CAMERA_ALIGNMENT_JSONL>
```

optional:

```text
--max-age-ms <MS>
```

summary:

```text
robot frames
camera frames
aligned frames
missing frames
future frames used
reused assignments
camera age median / p95 / max
```

---

## 8. End-to-end procedure

scriptを個別に試すだけではsensor extensionのacceptanceにはならない。

次のどちらかを [03 Architecture and Sensor Extension](../../docs/03_architecture_and_extension.md) に従って通す。

```text
High-rate numeric:
driver
-> stream inspection
-> raw logger
-> timestamped ALOHA recording
-> align_timeseries
-> validate_alignment
-> build_sensor_windows

Asynchronous camera:
device discovery
-> format inspection
-> native capture
-> timestamped ALOHA recording
-> extract_mkv_timestamps
-> align_camera_frames
```
