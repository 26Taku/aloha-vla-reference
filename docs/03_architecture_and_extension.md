# Architecture and Extension

## 1. 目的

本資料では、研究室ALOHAの標準recording経路と、外部sensorを追加するときの境界を整理する。

確認状態は以下で区別する。

- **[HW-VERIFIED]**: 研究室の実機で確認済み
- **[CODE-VERIFIED]**: 固定したsource codeまたはoffline testで確認済み
- **[DESIGN]**: 推奨設計。対象条件での実機確認前
- **[NOT-VERIFIED]**: 明示的に未確認

## 2. Baseline stack

- Trossen integration: `TrossenRobotics/lerobot_trossen`
- verified commit: `a4336933f34192a3daa7e9fb52674284bb5ae48e`
- LeRobot: 0.6.0
- Dataset: LeRobotDataset v3.0

主なTrossen側実装:

```text
packages/lerobot_robot_trossen/src/lerobot_robot_trossen/
  config_bi_widowxai_follower.py
  bi_widowxai_follower.py
  config_widowxai_follower.py
  widowxai_follower.py

packages/lerobot_teleoperator_trossen/src/lerobot_teleoperator_trossen/
  config_bi_widowxai_leader.py
  bi_widowxai_leader.py
  config_widowxai_leader.py
  widowxai_leader.py
```

LeRobot recording側は `src/lerobot/scripts/lerobot_record.py` を確認対象とする。

## 3. Baselineのデータ経路

```text
YAML configuration
      │
      ├───────────────┐
      ▼               ▼
Follower config    Leader config
      │               │
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
        LeRobotDataset v3.0
```

**[CODE-VERIFIED]** Dataset schemaは `robot.action_features` と `robot.observation_features` を基に構築される。Robot interfaceへ新しいstateを直接統合する場合は、feature定義と `get_observation()` の出力を一致させる必要がある。

## 4. Trossen Robot側の拡張点

Bimanual followerは左右single-arm observationへprefixを付け、camera observationと統合する。baselineではjoint positionを使用し、設定によりvelocity、effort、external effortを追加できる。

```text
include_velocity        -> .vel
include_effort          -> .eff
include_external_effort -> .ext_eff
```

**[HW-VERIFIED]** `include_external_effort=true` のrecordingでは、baseline 14D stateに左右7値ずつのexternal effortが加わり、`observation.state` が28DになってDatasetへ保存された。

これはTrossen driver内で取得可能なstateの追加経路が機能することを示す。一方、独立したMMS101等の外部sensorとは取得周期・driver・clockが異なるため、同じ問題として扱わない。

## 5. Action保存に関する注意

**[CODE-VERIFIED]** LeRobot 0.6.0のrecording loopでは、`robot.send_action()` の戻り値は `_sent_action` に受けるが、Dataset action frameはprocessed `action_values` から生成される。

Trossen側で `max_relative_target` によるclipを有効にすると、「Datasetへ記録したaction」と「Followerへ実際に送ったaction」が一致しない可能性がある。

研究室baselineでは `left_arm_max_relative_target: null`、`right_arm_max_relative_target: null` としている。safety clippingを変更する場合はaction semanticsを再確認する。

## 6. Sensor extensionの標準原則

外部sensorでは、**acquisition rate、robot/control rate、policy inference rateを同一と仮定しない**。

標準原則は以下。

1. sensorが自然にbaseline FPSへ適合し、LeRobot Camera/Robot interfaceへ無理なく統合できる場合は直接統合する。
2. native rateやlatencyが異なるsensorは、robot recordingと独立してnative/actual rateで取得する。
3. raw dataと実timestampをcanonical dataとして保持する。
4. policy用の同期表現はderived dataとして後処理で生成する。
5. causal online useを想定する場合、未来sample/frameをalignmentに使用しない。
6. software timestampで不足するtaskだけhardware synchronizationを導入する。

したがって、ROS 2を必須の標準interfaceにはしない。ROS 2、V4L2、vendor SDK等はsensor acquisition adapterとして利用し、保存時の共通contractを揃える。

```text
Sensor-specific acquisition
   ├─ ROS 2 topic
   ├─ V4L2 camera
   └─ vendor SDK
          │
          ▼
raw data + timestamps + metadata
          │
          ▼
derived causal view for policy/training
```

## 7. Robot frameの共通timestamp

外部sensorと同期する場合、LeRobotDataset v3の通常の `timestamp` だけを実clockとして使用しない。本検証環境のrecordingではDataset timestampはframe index / target FPSに対応するlogical timeであり、外部sensorの実受信時刻との比較には別の実clockが必要である。

`examples/custom_sensor/record_with_timestamps.py` は、LeRobot 0.6.0のrecording loopを実行時に差し替え、各robot frameへhost monotonic timestampを追加する。

主な記録値:

```text
loop_start_monotonic_ns
observation_start_monotonic_ns
observation_end_monotonic_ns
observation_end_wall_ns
action_sent_monotonic_ns
frame_added_monotonic_ns
```

本referenceでは `observation_end_monotonic_ns` を、observationがpolicy側で利用可能になった代表robot時刻とする。

**[HW-VERIFIED]** timestamp sidecarを付加したALOHA recordingを実機で行い、通常のLeRobotDataset v3 recordingと併存することを確認した。

注意: このscriptは固定したLeRobot 0.6.0のrecording implementationに依存する。LeRobot更新時には `docs/05_maintenance.md` に従って再確認する。

## 8. Policy-rate sensorを直接統合する場合

**[DESIGN]** 30 Hz程度で値が得られ、raw high-rate waveformを保持する必要がないsensorであれば、Robot observationへ直接追加する構成も選択できる。

```text
External sensor
     ↓
Sensor adapter / latest buffer
     ↓
Robot observation
     ↓
LeRobotDataset
```

この場合は、概念的に以下を行う。

1. sensor config / lifecycleを追加
2. `observation_features` にfeatureを追加
3. `get_observation()` で同じkeyを返す
4. Dataset schema / Parquetをvalidatorで確認
5. robot loop rateが許容範囲にあることを確認

ただし、高周期F/Tや異FPS tactile cameraをこの方法へ無理に合わせることは標準としない。

## 9. High-rate numeric / time-series sensor

F/T、IMU等ではraw waveform自体が意味を持つため、native rateで別streamとして保存する。

```text
High-rate sensor
      │
      ├─> raw JSONL @ native/actual rate
      │     sample index
      │     source timestamp (if available)
      │     host receive monotonic timestamp
      │     raw values
      │
Robot │
      └─> LeRobotDataset + robot frame monotonic timestamps
                  │
                  ▼
          causal alignment
             ├─ current value
             └─ history window
```

`examples/custom_sensor/ros2_timeseries_logger.py` はgeneric numeric ROS 2 messageをflattenし、callback entryで `time.monotonic_ns()` を付与するreferenceである。ROS 2自体はbase setupの依存ではない。

publisherの `header.stamp` は `source_timestamp_ns` として保存するが、そのclock semanticsはpublisher依存である。同一clockであることを確認できない限り、host monotonicとの直接比較には使用しない。

### 9.1 Current-value view

`align_timeseries.py` は各robot frameに対して

```text
sensor.receive_monotonic_ns <= robot.observation_end_monotonic_ns
```

を満たす最新sampleを選択する。未来sampleは使用しない。

**[HW-VERIFIED]** 研究室のMMS101 ROS 2 stream（この環境では約100 Hz）とALOHA 30 Hz recordingを同時取得し、299 robot framesすべてをcausalにalignmentできた。future sampleは0で、sensor age p95は15.094 msだった。

### 9.2 History-window view

`build_sensor_windows.py` はrobot時刻 `t` に対して `(t-W, t]` のsensor sample index範囲を生成する。raw valueそのものはframeごとに複製しない。

**[HW-VERIFIED]** 200 ms windowで299/299 frameが有効となり、1 windowあたり19--21 samplesだった。

VLA/policy側では、current valueをstateへ追加する方法のほか、history windowをMLP/1D CNN/Transformer等でencodeして融合する方法を選べる。どちらを採るかはPhase 2以降のmodel設計事項であり、collection formatでは固定しない。

## 10. Asynchronous camera

GelSight等、実効camera rateがrobot FPSと異なるcameraは、native compressed streamを独立取得する。

GelSight Miniで確認したreference path:

```text
GelSight Mini
   ↓ V4L2 MJPEG
FFmpeg stream copy
   ↓ -copyts / no decode-re-encode
MKV + preserved packet PTS
   ↓
causal latest-frame mapping
   ↓
30 Hz robot frames
```

`examples/custom_sensor/camera/extract_mkv_timestamps.py` はMKV packet PTSをJSONLへexportする。`align_camera_frames.py` は各robot observation以前で最も新しいcamera frameを対応付ける。

**[HW-VERIFIED]** 検証したGelSight MiniはV4L2上でMJPEG 3280x2464 @ 25 fpsをadvertiseしたが、実測native streamは約18.75 Hzだった。FFmpegのstream copyとALOHA recordingを並行実行し、ALOHA 299 frames / 30 Hzを維持したままGelSightを18.753 Hzで保存した。

causal alignment結果:

```text
robot frames        299
aligned frames      299
missing             0
future frames       0
reused assignments  111
camera age median   27.462 ms
camera age p95      50.602 ms
camera age max      53.836 ms
```

約18.75 Hzのcameraを30 Hz robot framesへlatest-frameで割り当てるため、同じcamera frameが複数robot frameから参照されることは正常である。

### Capture実装の選定

検証過程で、本Phase 1用に作成したfull-resolution JPEG-per-frame prototypeでは約8.6 Hzまで低下した。一方、V4L2 MJPEGをdecode/re-encodeせずstream copyすると約18.75 Hzを維持した。

この比較は**Phase 1で作成したprototypeとstream-copy方式の比較**であり、研究室既存GelSight codeやGelSight公式softwareの性能評価ではない。reference implementationでは、raw acquisition時の不要なdecode/re-encodeを避けるためstream copyを採用した。

## 11. GelSight code provenance

研究室で使用されていたGelSight helperには、GelSight Inc.公式 `gelsightinc/gsrobotics` の `GelSightMini` / OpenCVベースの構造と対応する部分があり、その上にbuffer設定、FPS要求、224x224固定crop/resize等のproject-specific変更が加わっていた。

別のROS 2 publisherはそのhelperを呼び出して `sensor_msgs/Image` / `CompressedImage` をpublishするwrapperであり、確認したファイルだけから作成元repositoryまでは特定できなかった。そのため、本成果物では「研究室/project-specific wrapper」として扱い、Trossen公式実装やGelSight公式標準pipelineとは表記しない。

本repositoryに含めるasynchronous camera referenceは、上記研究室wrapperをコピーしたものではなく、V4L2/FFmpegとtimestamp alignmentに限定した独立referenceである。

公式GelSight repository:

- https://github.com/gelsightinc/gsrobotics

## 12. Software syncとhardware syncの境界

本成果物で実機確認した外部sensor synchronizationは同一hostのmonotonic clockを基準とするsoftware-level alignmentである。

これは以下を保証しない。

- camera exposure instantの一致
- sensor内部clockとhost clockの厳密なoffset
- sub-millisecond synchronization
- 複数PC間のclock synchronization

taskがこれらを必要とする場合は、hardware trigger、共有clock、PTP等を別途設計する。

## 13. 変更目的と確認箇所

| 変更内容 | 主な変更・確認箇所 |
|---|---|
| Arm IP変更 | `config/*.yaml` |
| Camera serial変更 | `config/*.yaml` |
| LeRobot対応camera追加 | `config.cameras` |
| Trossen state追加 | `include_velocity/effort/external_effort` |
| policy-rate外部state | Robot feature + observation + validator |
| high-rate numeric sensor | native logger + robot timestamp + causal alignment |
| 異FPS camera | native compressed capture + timestamp + causal alignment |
| action clipping | `max_relative_target` とrecorded/sent action semantics |
| LeRobot更新 | `docs/05_maintenance.md` の再検証matrix |

## 14. まとめ

研究室標準として固定するのは「すべてをROS 2へ入れる」「すべてをLeRobot observationへ直接入れる」といった単一transportではなく、次の原則である。

```text
raw acquisition rate != robot rate != policy rate

raw data + real timestamps  -> canonical
policy-specific synchronized view -> derived
```

baseline RGB/robot dataはLeRobotの標準recordingを利用し、rate/interfaceが異なるsensorだけを独立取得する。この境界を維持することで、sensor追加ごとにALOHA recording stack全体を作り直さずに済む。
