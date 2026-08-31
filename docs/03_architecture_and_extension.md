# Architecture and Extension

## 1. この資料の役割

本資料は、**baselineの内部data flowと、camera・F/T・tactile等を追加するときの設計境界**を説明する。

通常の初回利用手順は [02 Data Collection](02_data_collection.md) に、実機検証の数値は [06 Validation Results](06_validation_results.md) に分離する。

確認状態:

- **[HW-VERIFIED]**: 実機で確認済み
- **[CODE-VERIFIED]**: source codeまたはoffline testで確認済み
- **[DESIGN]**: 推奨設計。対象条件での実機確認前
- **[NOT-VERIFIED]**: 明示的に未確認

## 2. Baseline data path

BaselineはTrossen公式 `lerobot_trossen` とLeRobot 0.6.0を使用する。

```text
YAML configuration
      │
      ├───────────────┐
      ▼               ▼
Follower Robot     Teleoperator
      │               │
      │ get_observation() / get_action()
      └──────────┬────┘
                 ▼
             processors
                 │
                 ├─> robot.send_action()
                 │
                 ▼
        build_dataset_frame()
                 │
                 ▼
          dataset.add_frame()
                 │
                 ▼
        LeRobotDataset v3
```

**[CODE-VERIFIED]** Dataset schemaはrobotのaction / observation feature定義を基に構築される。Robot observationへfeatureを直接追加する場合は、feature定義と `get_observation()` の出力を一致させる必要がある。

## 3. Trossen Robot側のstate extension

Bimanual followerは左右single-arm observationを統合し、設定によりvelocity、effort、external effortを追加できる。

```text
include_velocity        -> .vel
include_effort          -> .eff
include_external_effort -> .ext_eff
```

**[HW-VERIFIED]** external effortを有効化し、追加stateがDataset schema / Parquetまで伝播することを確認した。具体的なshapeは [06 Validation Results](06_validation_results.md) を参照する。

独立した外部F/T sensorはdriver、rate、clockが異なるため、Trossen内部state extensionとは別の問題として扱う。

## 4. Action保存semantics

**[CODE-VERIFIED]** LeRobot 0.6.0のrecording loopでは、`robot.send_action()` の戻り値とは別に、processed actionからDataset frameを構築する。

`max_relative_target` 等でcommandがrobot側でclipされる構成では、「Datasetへ記録されたaction」と「実際に送信されたaction」が一致しない可能性がある。

baselineではrelative target clippingを無効として検証した。safety clippingを変更する場合はrecorded/sent action semanticsを再確認する。

## 5. Sensor extensionの標準原則

外部sensorでは、次を同一と仮定しない。

```text
acquisition rate
robot/control rate
policy inference rate
```

標準原則:

1. baseline FPSへ自然に適合するsensorはLeRobotへ直接統合できる
2. rate / latency / interfaceが異なるsensorは独立してnative/actual rateで取得する
3. raw dataと実timestampをcanonicalとして保持する
4. policy用同期表現はderived dataとして後処理で生成する
5. causal useでは未来sample/frameを使用しない
6. software timestampで不足するtaskのみhardware synchronizationを導入する

ROS 2を標準transportとして固定しない。ROS 2、V4L2、vendor SDK等はsensor-specific acquisition adapterとして扱う。

```text
Sensor-specific acquisition
   ├─ ROS 2
   ├─ V4L2
   └─ vendor SDK
          │
          ▼
raw data + timestamps + metadata
          │
          ▼
derived causal view
```

## 6. Robot frameの実timestamp

通常のLeRobotDataset timestampはtarget FPSに基づくlogical frame timeとして扱われるため、外部sensorの実受信時刻との比較には別の実clockを使用する。

`examples/custom_sensor/record_with_timestamps.py` はLeRobot 0.6.0のrecord loopへ実行時patchを適用し、robot frameごとにhost monotonic timestampを記録する。

主なfield:

```text
loop_start_monotonic_ns
observation_start_monotonic_ns
observation_end_monotonic_ns
observation_end_wall_ns
action_sent_monotonic_ns
frame_added_monotonic_ns
```

本referenceでは `observation_end_monotonic_ns` を、observationがpolicy側で利用可能になった代表robot時刻とする。

**[HW-VERIFIED]** timestamp sidecarと通常のLeRobotDataset recordingが併存することを確認した。

このreferenceはLeRobot 0.6.0のrecording implementationに依存する。LeRobot更新時は [05 Maintenance](05_maintenance.md) に従って再検証する。

## 7. Policy-rate sensorを直接統合する場合

**[DESIGN]** baseline FPS程度で取得でき、raw high-rate waveformを保持する必要がないsensorはRobot observationへ直接追加できる。

```text
External sensor
     ↓
adapter / latest buffer
     ↓
Robot observation
     ↓
LeRobotDataset
```

確認項目:

1. sensor lifecycle
2. observation feature定義
3. `get_observation()` のkey / shape
4. Dataset schema / Parquet
5. robot loop rateへの影響

高周期F/Tや異FPS tactile cameraを無理にこの経路へ合わせることは標準としない。

## 8. High-rate numeric / time-series sensor

F/T、IMU等はraw waveformをnative rateで別streamとして保存する。

```text
High-rate sensor
      │
      ├─> raw JSONL
      │     sample index
      │     source timestamp (if available)
      │     host receive monotonic timestamp
      │     raw values
      │
Robot │
      └─> LeRobotDataset + robot monotonic timestamps
                  │
                  ▼
          causal alignment
             ├─ latest value
             └─ history window
```

`ros2_timeseries_logger.py` はgeneric ROS 2 numeric messageをflattenし、callback entryでhost monotonic timestampを付けるreferenceである。ROS 2自体はbaseline dependencyではない。

publisherの `header.stamp` はsource timestampとして保持できるが、clock semanticsを確認できない限りhost monotonicとの直接比較には使用しない。

`align_timeseries.py` は各robot frameに対して、robot時刻以前で最も新しいsampleを選択する。

`build_sensor_windows.py` は `(t-W, t]` のcausal history sample範囲を生成する。raw valueをrobot frameごとに複製せず、index / timestamp manifestを作る。

**[HW-VERIFIED]** 高周期ROS 2 numeric streamを用いてnative-rate acquisition、concurrent ALOHA recording、latest-value alignment、history-window generationまで確認した。実測値は [06 Validation Results](06_validation_results.md) に記載する。

## 9. Asynchronous camera

GelSight等、実効camera rateがrobot FPSと異なるcameraはnative compressed streamを独立取得する。

検証したreference path:

```text
V4L2 MJPEG
   ↓
FFmpeg stream copy
   ↓  -copyts / no decode-re-encode
MKV + packet PTS
   ↓
causal latest-frame mapping
   ↓
robot frames
```

`extract_mkv_timestamps.py` はMKV packet PTSをJSONLへexportする。`align_camera_frames.py` は各robot observation以前で最も新しいcamera frameを対応付ける。

**[HW-VERIFIED]** GelSight Mini 1台でnative compressed acquisition、packet timestamp保持、ALOHAとのconcurrent recording、causal latest-frame alignmentまで確認した。実効rateとage統計は [06 Validation Results](06_validation_results.md) に分離する。

### Capture方式の選定

Phase 1で作成したfull-resolution JPEG-per-frame比較prototypeでは、decode / re-encodeを伴う保存経路がnative streamより遅かった。

そのためreference implementationでは、raw acquisition中の不要なdecode/re-encodeを避け、V4L2 MJPEGをstream copyする方式を採用した。

この比較はPhase 1で作成したprototypeの方式選定であり、研究室既存GelSight codeやGelSight公式softwareのbenchmarkではない。

## 10. GelSight code provenance

研究室で使用されていたGelSight helperには、GelSight Inc.公式 `gelsightinc/gsrobotics` のOpenCV based `GelSightMini`構造に対応する部分があり、その上にproject-specific変更が加わっていた。

別のROS 2 publisherはそのhelperを利用するwrapperであるが、確認したfileだけから元repositoryまでは特定できなかった。そのため、本成果物ではTrossen公式codeやGelSight公式標準pipelineとは表記しない。

本repositoryのasynchronous camera referenceは研究室wrapperをコピーしたものではなく、V4L2/FFmpeg + timestamp alignmentに限定した独立referenceである。

- GelSight official repository: https://github.com/gelsightinc/gsrobotics

## 11. Software syncとhardware syncの境界

本成果物で実機確認したsensor synchronizationは、同一hostのmonotonic clockを基準とするsoftware-level alignmentである。

保証しないもの:

- camera exposure instantの一致
- sensor内部clockとhost clockの厳密なoffset
- sub-millisecond synchronization
- 複数PC間のclock synchronization

これらが必要なtaskではhardware trigger、共有clock、PTP等を別途設計する。

## 12. 変更時の確認箇所

| 変更 | 主な変更・確認箇所 |
|---|---|
| Arm / camera identity | local config + hardware check |
| LeRobot対応camera追加 | `config.cameras` + Dataset schema |
| Trossen state追加 | feature定義 + observation + validator |
| policy-rate external state | Robot feature + observation + loop rate |
| high-rate numeric sensor | native logger + robot timestamp + causal alignment |
| 異FPS camera | native compressed capture + timestamp + causal alignment |
| action clipping | recorded/sent action semantics |
| LeRobot更新 | [05 Maintenance](05_maintenance.md) |

## 13. まとめ

標準化するのは特定transportではなく、次の境界である。

```text
raw acquisition rate != robot rate != policy rate

raw data + real timestamps       -> canonical
policy-specific synchronized view -> derived
```

baseline RGB / robot dataはLeRobot標準recordingを利用し、rateやinterfaceが異なるsensorだけを独立取得する。
