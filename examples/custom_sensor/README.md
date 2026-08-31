# Custom Sensor Reference

このディレクトリは、ALOHA標準の30 Hz recordingとは取得周期やinterfaceが異なる外部sensorを扱うためのreference implementationである。

基本方針は、**sensorのraw acquisition rateとrobot/policy rateを分離し、raw dataと実timestampを保持する**ことである。学習時に必要な30 Hz等の表現は、raw dataから後処理で生成する。

この方式は研究室の実機で、ROS 2経由の高周期6軸F/T streamとGelSight Miniで確認した。これはsoftware-level synchronizationであり、hardware trigger、PTP、共有device clock等による同期ではない。

## 1. Robot frame timestamp sidecar

`record_with_timestamps.py` は、固定したLeRobot 0.6.0のrecording loopを実行時に差し替え、各Dataset frameについてhostのmonotonic clockによるtimestamp sidecarを追加する。インストール済みLeRobot packageのファイルは変更しない。

代表時刻には、robot observationがpolicy側で利用可能になった時点として `observation_end_monotonic_ns` を使用する。

```bash
cd /path/to/lerobot_trossen
uv run python /path/to/examples/custom_sensor/record_with_timestamps.py \
  --config_path=/path/to/record-config.yaml
```

Datasetに以下が追加される。

```text
<dataset_root>/meta/frame_timestamps/
  episode_000000.jsonl
  episode_000000.meta.json
```

このscriptはLeRobot 0.6.0のrecording implementationに依存するため、LeRobot更新時は `docs/05_maintenance.md` に従って再確認する。

## 2. High-rate numeric / time-series sensor

ROS 2 topicとして提供される数値sensorは、`ros2_timeseries_logger.py` でnative rateのままJSONLへ保存できる。

このscriptはoptional exampleであり、base setupはROS 2を導入しない。使用する場合は、対象PC上でROS 2と対象message packageが利用できる環境をsourceしてから実行する。

例:

```bash
python3 examples/custom_sensor/ros2_timeseries_logger.py \
  --topic /force_torque/left \
  --msg-type geometry_msgs/msg/WrenchStamped \
  --sensor-id example_ft \
  --output /tmp/example_ft.jsonl \
  --duration 60
```

各sampleには以下を保存する。

- `sample_index`
- publisherの `header.stamp` が存在する場合の `source_timestamp_ns`
- callback受信時の `receive_monotonic_ns`
- callback受信時のwall clock
- message内のnumeric values

異なるclock domainを無条件に比較しないため、標準のalignmentには同一hostで取得した `receive_monotonic_ns` を使用する。

### Current-value view

各robot frameに対して、未来を使用しない

```text
sensor_time <= robot_observation_time
```

を満たす最新sampleを選択する。

```bash
python3 examples/custom_sensor/align_timeseries.py \
  --robot-frames <dataset_root>/meta/frame_timestamps/episode_000000.jsonl \
  --sensor /tmp/example_ft.jsonl \
  --output /tmp/aligned_ft.jsonl

python3 examples/custom_sensor/validate_alignment.py \
  /tmp/aligned_ft.jsonl \
  --require-complete
```

### History-window view

高周期の波形情報を使う場合は、robot frame時刻 `t` に対して `(t-W, t]` のraw sample indexを保持する。

```bash
python3 examples/custom_sensor/build_sensor_windows.py \
  --robot-frames <dataset_root>/meta/frame_timestamps/episode_000000.jsonl \
  --sensor /tmp/example_ft.jsonl \
  --output /tmp/ft_windows.jsonl \
  --window-ms 200
```

raw valuesをDataset frameごとに複製せず、必要なsample範囲だけをmanifestとして保持する。

## 3. Asynchronous camera

GelSight等、実効camera rateがrobot recording rateと一致しないcameraは `camera/README.md` を参照する。

実機検証では、GelSight MiniのV4L2 MJPEG streamをdecode/re-encodeせず保存し、V4L2 packet PTSをhost monotonic clockとして保持した上で、30 Hzのrobot frameへcausal latest-frame alignmentした。

## 4. Policy / VLAへの接続境界

収集時点ではraw dataを保持し、policy-specific representationは後から生成する。

- current value: causal latest sample/frame
- history window: 時系列encoderへ渡す一定時間のraw sample群
- fast/slow構成: 高速なlocal controller/reflexで処理したsummaryを低速VLAへ渡す

どの表現を採るかはpolicy architectureに依存するため、raw acquisition formatで固定しない。
