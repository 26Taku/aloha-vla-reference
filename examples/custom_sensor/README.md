# Custom Sensor Reference

このdirectoryは、ALOHA標準recordingとは取得周期やinterfaceが異なる外部sensorを扱うためのreference implementationをまとめる。

sensor integration方式の選択、raw data、timestamp、software / hardware synchronizationの設計は [docs/03_architecture_and_extension.md](../../docs/03_architecture_and_extension.md) を参照する。本資料では各scriptの実行方法、入力、出力を扱う。

基本方針:

```text
sensor acquisition rate != robot/control rate != policy rate

raw data + timestamp              = canonical
policy-specific synchronized view = derived
```

## 1. Robot frame timestamp sidecar

`record_with_timestamps.py` はLeRobot 0.6.0のrecording loopへ実行時patchを適用し、各Dataset frameについてhost monotonic clockによるtimestamp sidecarを追加する。

代表robot時刻には `observation_end_monotonic_ns` を使用する。

### 1.1 timestamp付きrecording configを生成

repository rootで、baselineのhardware identityとrecording templateからruntime configを生成する。

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

### 1.2 recording

```bash
(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path=../.runtime/sensor-record.yaml
)
```

Dataset rootに以下が追加される。

```text
data/sensor_reference/meta/frame_timestamps/
  episode_000000.jsonl
  episode_000000.meta.json
```

`record_with_timestamps.py` はLeRobot 0.6.0のrecording implementationに依存する。LeRobot更新時は [05 Maintenance](../../docs/05_maintenance.md) に従って再確認する。

## 2. High-rate numeric / time-series sensor

ROS 2 topicとして提供される数値sensorは `ros2_timeseries_logger.py` でnative / actual rateのままJSONLへ保存する。

対象PCでROS 2と対象message packageをsourceしたshellから実行する。

```bash
python3 examples/custom_sensor/ros2_timeseries_logger.py \
  --topic /force_torque/left \
  --msg-type geometry_msgs/msg/WrenchStamped \
  --sensor-id example_ft \
  --output /tmp/example_ft.jsonl \
  --duration 60
```

各sample:

- `sample_index`
- `source_timestamp_ns`（messageにtimestampがある場合）
- `receive_monotonic_ns`
- host wall clock
- numeric values

同一hostでの標準alignmentには `receive_monotonic_ns` を使用する。

### 2.1 Current-value view

各robot frameに対して、

```text
sensor_time <= robot_observation_time
```

を満たす最新sampleを選択する。

```bash
python3 examples/custom_sensor/align_timeseries.py \
  --robot-frames data/sensor_reference/meta/frame_timestamps/episode_000000.jsonl \
  --sensor /tmp/example_ft.jsonl \
  --output /tmp/aligned_ft.jsonl

python3 examples/custom_sensor/validate_alignment.py \
  /tmp/aligned_ft.jsonl \
  --require-complete
```

確認項目:

- future sample = 0
- missing
- timestamp ordering
- sensor age

### 2.2 History-window view

robot frame時刻 `t` に対して `(t-W, t]` のraw sample範囲を生成する。

```bash
python3 examples/custom_sensor/build_sensor_windows.py \
  --robot-frames data/sensor_reference/meta/frame_timestamps/episode_000000.jsonl \
  --sensor /tmp/example_ft.jsonl \
  --output /tmp/ft_windows.jsonl \
  --window-ms 200
```

outputはraw sample index / timestamp範囲を保持する。

## 3. Asynchronous camera

GelSight等、実効camera rateがrobot recording rateと一致しないcameraは [camera/README.md](camera/README.md) を使用する。

reference path:

```text
native compressed capture
    ↓
video + frame/packet timestamp
    ↓
timestamp export
    ↓
causal latest-frame alignment
```

camera timestamp extraction:

```text
camera/extract_mkv_timestamps.py
```

robot frameへの対応付け:

```text
camera/align_camera_frames.py
```

## 4. 新しいsensorへ流用する場合

adapterは次の情報を出力する。

```text
[ ] raw data
[ ] sample/frame index
[ ] source timestamp（取得可能な場合）
[ ] host monotonic timestamp
[ ] sensor/config metadata
```

実装後、[docs/03_architecture_and_extension.md](../../docs/03_architecture_and_extension.md) のvalidation checklistに従ってactual rate、timestamp、concurrent acquisition、causal alignmentを確認する。

## 5. Policy / VLAへ渡すとき

policy-specific representationはcanonical rawから生成する。

- current value: causal latest sample/frame
- history window: 一定時間のraw sample群
- fast/slow構成: 高周期local controllerで処理したsummaryを低速policyへ渡す

具体的なrepresentationはpolicy architectureに合わせて決定する。
