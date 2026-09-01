# Implementation Report

## 1. この文書の役割

本書は、本reference作成で行った**調査、選定、実装、設計判断、実機検証、制約**を納品・レビュー向けに要約する。

利用者向けのbaseline操作は `docs/02_data_collection.md`、sensor extensionのend-to-end操作・設計は `docs/03_architecture_and_extension.md`、実測値は `docs/06_validation_results.md` を正とする。

---

## 2. 目的

ALOHAについて、初見の利用者がsoftware setupからteleoperation、実Dataset収録まで再現でき、camera・F/T・tactile等の追加sensorについても既存の取得環境を再利用しながら共通のintegration pathへ接続できるreferenceを作成した。

Model training / inferenceそのものは本書の実機validation範囲外とする。

---

## 3. 採用baseline

標準構成にはTrossen Robotics公式`lerobot_trossen` pluginを採用し、実機検証済みrevisionを固定した。

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
LeRobotDataset v3.0
```

採用理由:

- Trossen AI seriesのhardware integrationが公式に提供される
- leader-follower teleoperation、robot state/action、複数camera、Dataset recordingを同一stackで扱える
- LeRobotDatasetを後段の学習stackへ接続しやすい
- 研究室固有forkをbaseline dependencyにしなくてよい

既存研究forkは変更せず、clean environmentでreference stackを検証した。

---

## 4. 実装成果物

### 4.1 Baseline workflow

```text
setup.sh
check_hardware.sh
teleoperate.sh
record.sh
validate_dataset.sh
```

### 4.2 Hardware identityとoperational configの分離

Machine-specific identityを1 fileへ集約した。

```text
config/hardware-template.yaml    tracked
config/hardware-local.yaml       local / gitignored
```

Operational settingはtracked templateとして保持する。

```text
config/teleop-template.yaml
config/record-template.yaml
```

Wrapper実行時に`hardware-local.yaml`とoperational templateを結合し、`.runtime/`以下へcomplete configを生成する。

```text
hardware-local.yaml
      +
teleop-template.yaml / record-template.yaml
      ↓
build_runtime_config.py
      ↓
.runtime/*.yaml
```

これにより、Arm IPやcamera serialを複数fileへ重複入力せず、tracked repositoryへmachine-specific identifierを保存しない構成にした。

### 4.3 External sensor reference

- `record_with_timestamps.py`: robot frame host timestamp sidecar
- `ros2_timeseries_logger.py`: generic ROS 2 numeric/time-series logger
- `align_timeseries.py`: causal latest-sample alignment
- `build_sensor_windows.py`: causal history-window manifest
- `validate_alignment.py`: numeric alignment validation
- `camera/extract_mkv_timestamps.py`: asynchronous camera packet timestamp export
- `camera/align_camera_frames.py`: camera causal latest-frame alignment

---

## 5. Sensor extension設計

Sensor implementationそのものを標準化するのではなく、**ALOHAへ接続するinterface boundaryと、その境界以降のvalidation pathを標準化する**方針を採用した。

```text
sensor-specific implementation
        ↓
integration interface
        ↓
native raw acquisition + host timestamp
        ↓
concurrent ALOHA recording
        ↓
causal alignment
        ↓
validation / policy-specific derived view
```

共通原則:

```text
sensor acquisition rate != robot/control rate != policy rate

raw data + real timestamp          = canonical
policy-specific synchronized view = derived
future sample/frame                = prohibited in causal alignment
```

この設計により、vendor SDK、研究室既存driver、ROS 2 node、V4L2 camera等の既存資産を置き換える必要はない。利用者はsensor streamを取得可能な状態まで準備し、03で定義したinterface contractへ合わせる。interfaceが一致しない場合のみthin adapterを追加する。

Pattern BではROS 2 numeric stream、Pattern CではV4L2 asynchronous cameraを具体例としてend-to-end validationした。

---

## 6. Sensor-specific codeのprovenance / distribution boundary

### MMS101

検証で使用したROS 2 driverには複数の開発・修正履歴があるため、sensor-specific driver sourceは本referenceへ含めない。

Reference側は次のinterfaceだけを要求する。

```text
running numeric stream
known message/data format
actual rateを測定可能
hostで受信timestampを取得可能
```

実機では`geometry_msgs/msg/WrenchStamped`を使用し、MMS101固有workspaceをsubscriber側でsourceしないclean shellからgeneric loggerへ接続できることを確認した。

### GelSight Mini

研究室固有helper / ROS 2 wrapperをreference dependencyにせず、Linux V4L2 + FFmpegのnative compressed captureを採用した。GelSight固有SDK、marker tracking、depth等が必要な場合はsensor-specific layerで別途扱う。

この分離により、provenanceが不明確な研究室内codeを再配布せず、ALOHA integration側だけを独立したreferenceとして提供できる。

---

## 7. Baseline実機検証で得た運用上の知見

Teleoperation起動時、Leaderが操作可能になってからFollower follow loop開始まで短い時間差が生じる場合があった。follow開始前にLeaderを大きく移動すると、Followerが蓄積したpose gapを急に解消しようとしてjoint velocity limitで停止する試行があった。

このため、起動直後はLeaderを保持し、小さなLeader motionへFollowerが連続追従することを確認してから通常操作を開始する手順を`docs/02_data_collection.md` / `docs/04_troubleshooting.md`へ反映した。

また、error停止状態からArm Controllerの電源を切ると保持力が失われるため、power cycle前にArmを物理的に支持し、落下経路を空ける安全手順を採用した。

---

## 8. 実機検証の要約

Baseline:

```text
clean setup / fixed upstream revision      PASS
hardware preflight                         PASS
bimanual teleoperation                     PASS
RealSense 4-view recording                 PASS
LeRobotDataset v3 validation               PASS
configuration-unified end-to-end path      PASS
```

Pattern B — high-rate numeric:

```text
clean-shell interface boundary             PASS
native acquisition                         PASS
ALOHA concurrent recording                 PASS
299 / 299 causal alignment                 PASS
missing / future                           0 / 0
200 ms history window                      PASS
```

Pattern C — asynchronous camera:

```text
V4L2 native compressed acquisition         PASS
packet timestamp export                    PASS
ALOHA concurrent recording                 PASS
299 / 299 causal alignment                 PASS
missing / future                           0 / 0
```

詳細なrate、frame数、age distributionは`docs/06_validation_results.md`に集約した。

---

## 9. 制約

- 同期は同一host monotonic clockを基準とするsoftware-level alignmentであり、hardware triggerやsub-millisecond synchronizationを保証しない
- GelSight 2台同時captureのUSB / CPU / storage capacityは未検証
- MMS101のforce ground truth / calibration accuracyは本validationの対象外
- sensor-specific driverの他hardware / firmware / OSでの互換性は保証しない
- policyへsensor historyをどうencodeするかはtask / model architectureに依存する
- VLA training / inference performanceは本reportの実機validation範囲外

---

## 10. 保守方針

本成果物は検証済みupstream revisionを固定する。

Trossen / LeRobot / hardware / Dataset schemaを変更した場合は`docs/05_maintenance.md`に従って関連acceptance pathを再実行する。特に`record_with_timestamps.py`はLeRobot 0.6.0のrecord loop実装に依存するため、upstream更新時にはsource diffと再validationを行う。

External sensorを変更する場合はsensor名ではなくinterface contractを再確認する。

```text
data format
actual rate
source/device timestamp semantics
host monotonic timestamp
causal alignment
missing / age distribution
```

---

## 11. 納品時の最終確認

Hardwareを必要とするbaseline / Pattern B / Pattern C validationは完了した。

Final document revisionをcommitした後、最終repository treeに対して以下を行う。

```text
git diff --check
Markdown relative link check
machine-specific identifier scan
personal/staging repository URL scan
generated/runtime/data artifact exclusion check
fresh clone / setup static path check
```

Final commitとrelease check結果は`docs/06_validation_results.md`のDelivery acceptance statusへ記録する。
