# Maintenance

## 1. この資料の役割

本資料は、**一度動作確認したreferenceを変更・更新するときのルール**を定める。

初回利用手順は [02 Data Collection](02_data_collection.md)、設計変更の考え方は [03 Architecture and Extension](03_architecture_and_extension.md)、既存の実機検証結果は [06 Validation Results](06_validation_results.md) を参照する。

## 2. 基本方針

本成果物は「常に最新版へ追従する環境」ではなく、実機で通したrevisionをreferenceとして固定する。

reference versionは [01 Reference Stack](01_reference_stack.md) を正とする。

更新は必要なときに明示的に行い、更新後にacceptance pathを再実行する。

## 3. Trossen / LeRobotを更新する場合

少なくとも以下を確認する。

```text
[ ] dependency resolution
[ ] robot / teleoperator type名
[ ] config field名
[ ] Arm connect / disconnect
[ ] teleoperation
[ ] camera acquisition
[ ] one-episode recording
[ ] Dataset schema
[ ] dataset validator
[ ] action保存semantics
[ ] custom robot-frame timestamp sidecar
```

特に `examples/custom_sensor/record_with_timestamps.py` はLeRobot 0.6.0のrecord loopへ実行時patchを当てるreferenceである。

upstreamのfunction signature、processor順序、dataset write位置、stop handlingが変わった場合は、そのまま使用しない。source diffを確認し、timestampを取得する意味的位置が維持されているかを確認してから実機smoke testを行う。

## 4. Hardwareを変更する場合

### Arm

対象環境のIPを再確認し、Git管理外の

```text
config/teleop-local.yaml
config/record-local.yaml
```

だけを更新する。

tracked templateのplaceholderは維持する。

### RealSense

camera交換・配置変更時は次を再確認する。

- serial
- physical role
- resolution
- FPS
- teleoperation / recording config間のidentity

更新後は `check_hardware.sh` とteleoperationを再実行する。

### External sensor

device path、serial adapter、topic、driver、native rate、timestamp semanticsを再確認する。

## 5. Public repositoryへ含めない値

tracked fileへ保存しないもの:

- Arm IP address
- RealSense / GelSight / USB adapter等の個体serial
- `/dev/*/by-id/...` の個体固有path
- username / hostnameを含むabsolute path
- 個人・組織固有のdataset namespace

一方、再現性に意味がある以下はreferenceへ残してよい。

- software version
- verified upstream commit
- device model
- resolution / target FPS
- workstation specification
- validationで得たrate / alignment統計

公開前はworking treeだけでなくGit historyにもmachine-specific identifierが残っていないか確認する。private開発履歴に固有値が含まれている場合、public releaseはfinal treeからclean historyを作る方が安全である。

## 6. Dataset schemaを変更する場合

state / action / camera featureを変更した場合は以下を確認する。

- `meta/info.json` feature shape / type
- Parquet column type / row count
- episode metadata
- video stream数 / resolution / FPS
- loaderで読み込めること
- validatorの期待schema

baseline validatorは4 RGB camera / 14D action / 14D stateを主対象とする。featureを追加する場合はvalidatorも更新する。

## 7. External sensor referenceを変更する場合

transportではなくtimestamp contractを維持する。

最低限保持する情報:

```text
sample/frame index
source/device timestamp (availableなら)
host monotonic timestamp
raw data
sensor/config metadata
```

### ROS 2 numeric sensor

確認:

- topic
- message type
- publisher QoS
- actual topic rate
- `header.stamp` semantics

### V4L2 camera

確認:

- device mapping
- advertised format / resolution / FPS
- actual capture rate
- packet timestamp domain
- concurrent robot recordingへの影響

## 8. Provenanceを維持する

vendor公式code、研究室/project-specific code、本成果物で新規作成したreference codeを混同しない。

GelSightについてのPhase 1整理:

- GelSight Inc.公式 `gsrobotics`: GelSight Mini用OpenCV based SDK / demo
- 研究室側helper: 公式構造をベースにproject-specific変更が加わったもの
- 研究室側ROS 2 publisher: 元repositoryまでは特定できなかったproject-specific wrapper
- 本成果物camera reference: V4L2/FFmpeg + timestamp alignmentとして独立実装

vendor / upstream sourceを成果物へコピーする場合はlicenseと出典を別途確認する。

## 9. 更新後のacceptance criteria

baselineに影響する変更後は [02 Data Collection](02_data_collection.md) のacceptance pathを再実行する。

最低限:

```text
setup
  ↓
hardware identification / config
  ↓
hardware check
  ↓
teleoperation
  ↓
one-episode recording
  ↓
dataset validation
```

external sensor codeを変更した場合は、対象sensorのnative acquisitionとcausal alignmentも追加で確認する。

結果は [06 Validation Results](06_validation_results.md) またはproject-specific validation logへ追記する。
