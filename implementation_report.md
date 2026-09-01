# Implementation Report

## 1. この文書の役割

本書は、本reference作成で行った**調査、選定、実装、実機検証、制約**を納品・レビュー向けに要約する。

利用者向けの操作マニュアルは `docs/02_data_collection.md`、sensor extension設計は `docs/03_architecture_and_extension.md`、実機検証結果は `docs/06_validation_results.md` を参照する。

## 2. 目的

ALOHAについて、初見の利用者が環境構築からteleoperation、実データ収録まで再現でき、今後のVLA・模倣学習案件でsoftware構成やsensor extension方法を毎回ゼロから調査しなくて済むreferenceを作成した。

対象はdata collectionとsensor extensionである。model training / inferenceは本成果物の対象外とする。

## 3. 採用baseline

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
LeRobotDataset v3.0
```

主な採用理由:

- Trossen AI seriesのhardware integrationがTrossen公式として提供される
- leader-follower teleoperation、robot state/action、複数camera、LeRobotDataset recordingを同一stackで扱える
- LeRobot系policyへの接続点が明確
- project-specific forkとbaselineを分離できる

選定理由の詳細は `docs/01_reference_stack.md` に記載する。

## 4. Baseline data collectionの実装

整理したwrapper / checker:

```text
setup.sh
check_hardware.sh
teleoperate.sh
record.sh
validate_dataset.sh
```

役割:

- `setup.sh`: upstream取得、verified commit固定、dependency setup
- `check_hardware.sh`: hardware config、Arm reachability、RealSense、software version、storageを事前確認
- `teleoperate.sh`: teleoperation用runtime configを生成して起動
- `record.sh`: recording用runtime configを生成し、task / episode条件を指定してLeRobotDatasetを収録
- `validate_dataset.sh`: metadata、Parquet、schema、videoを検証

## 5. Hardware configurationの一元化

machine-specific hardware identityは1つのGit管理外fileに集約した。

```text
config/hardware-local.yaml
```

tracked file:

```text
config/hardware-template.yaml
config/teleop-template.yaml
config/record-template.yaml
scripts/build_runtime_config.py
```

役割:

```text
hardware-local.yaml
    4 Arm IP + 4 RealSense serial

teleop-template.yaml
    teleoperation固有設定

record-template.yaml
    recording固有設定

build_runtime_config.py
    hardware identityを用途別templateへ注入
```

各wrapperは `.runtime/` 以下へcomplete LeRobot configを生成する。

この構成により、同じArm IP / camera serialをteleoperation用とrecording用の2ファイルへ重複入力する必要がなくなった。camera serialはruntime生成時に文字列へ正規化する。

## 6. Hardware identification

Arm:

```text
PC network確認
    ↓
trossen-arm discover
    ↓
trossen-arm identify --ip ...
    ↓
physical Armとの対応確定
```

RealSense:

```text
lerobot-find-cameras realsense
    ↓
serialごとの画像保存
    ↓
physical camera roleとの対応確定
```

fresh checkoutからこの経路を実機で確認した。

## 7. Teleoperation safety

実機検証で、Leaderが操作可能になってからFollower追従loop開始まで短い時間差が生じる場合があることを確認した。

追従開始前にLeaderを大きく移動した試行では、追従開始時にFollowerがLeaderの現在姿勢へ急速に移動し、joint velocity limitで停止した。

利用者向け手順には、teleoperation起動直後はLeaderを保持し、小さな動きへFollowerが連続追従することを確認してから通常操作を開始する手順を追加した。

また、error停止姿勢からControllerの電源を切ると保持力が失われArmが落下するため、power cycle前にArmを支持する安全手順を `docs/02_data_collection.md` と `docs/04_troubleshooting.md` に記載した。

## 8. Sensor extensionで解決する問題

外部sensor追加では、次を扱う必要がある。

- sensorごとのnative / actual rate
- robot/control rateとpolicy inference rate
- ROS 2、V4L2、vendor SDK等のinterface
- source/device clockとhost clock
- high-rate raw dynamicsの保持
- robot frameとのcausal alignment

本referenceでは次を共通境界とする。

```text
sensor acquisition rate != robot/control rate != policy rate

raw data + real timestamp          = canonical
policy-specific synchronized view = derived
```

## 9. Sensor architecture

### LeRobot observationへの直接統合

robot FPS程度で取得でき、robot frameごとに1値/1frameで十分なsensorに使用する。

### Native-rate numeric sidecar

F/T、IMU等の高周期numeric streamをnative / actual rateで保存し、robot timestampからcausal latest-valueまたはhistory-windowを生成する。

### Asynchronous camera

robot FPSと異なるcameraをnative compressed streamで保存し、frame/packet timestampからcausal latest-frame mappingを生成する。

### Hardware synchronization

software timestampで不足するtaskではhardware trigger、共有clock、PTP等を対象hardwareに合わせて設計する。

詳細は `docs/03_architecture_and_extension.md` に記載する。

## 10. External sensor reference implementation

- `record_with_timestamps.py`: robot frame host timestamp sidecar
- `ros2_timeseries_logger.py`: generic numeric/time-series acquisition
- `align_timeseries.py`: causal latest-sample alignment
- `validate_alignment.py`: causality / missing / age等の検証
- `build_sensor_windows.py`: causal history-window manifest
- `extract_mkv_timestamps.py`: asynchronous camera packet timestamp export
- `align_camera_frames.py`: causal latest-frame alignment

実行方法は `examples/custom_sensor/README.md` に記載する。

## 11. Sensor architecture validation

### High-rate numeric stream

```text
native-rate acquisition
+ concurrent ALOHA recording
+ robot frame timestamp
+ causal latest-sample alignment
+ history-window generation
```

まで実機確認した。

### Asynchronous camera

GelSight Mini 1台で、

```text
V4L2 MJPEG native compressed acquisition
+ packet timestamp保持
+ concurrent ALOHA recording
+ causal latest-frame alignment
```

まで確認した。

実測値は `docs/06_validation_results.md` に集約する。

## 12. GelSight code provenance

確認したGelSight関連codeを次のように区別した。

- GelSight Inc.公式 `gelsightinc/gsrobotics`: GelSight Mini用OpenCV based SDK / demo
- project-specific helper: 公式構造をベースに変更されたもの
- project-specific ROS 2 publisher: helperを利用するwrapper
- 本repositoryのcamera reference: V4L2/FFmpeg + timestamp alignmentとして独立実装

本repositoryへvendor / upstream sourceをコピーする場合はlicenseと出典を確認する。

## 13. End-to-end validation

fresh cloneから、

```text
setup
-> hardware identification
-> hardware-local.yaml
-> hardware check
-> teleoperation
-> recording
-> dataset validation
```

を通した。

hardware configuration一元化後にも同じpathを再実行し、hardware check、teleoperation、one-episode recording、dataset validationまで完了した。

## 14. 制約

software synchronizationは同一host monotonic clockを基準とする。hardware-trigger levelの同期、sub-millisecond synchronization、複数PC間clock synchronizationは別途設計が必要である。

GelSight 2台同時使用時のcapacity、外部sensorをpolicyへencodeする具体方式、VLA training / inference runtimeは本成果物では固定しない。

## 15. 保守方針

Trossen / LeRobot / hardware / Dataset schemaを変更した場合は `docs/05_maintenance.md` に従ってacceptance pathを再実行する。

robot frame timestamp referenceはLeRobot 0.6.0のrecord loopに依存するため、upstream更新時にはsource diffと再validationを行う。
