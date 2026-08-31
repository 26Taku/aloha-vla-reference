# Maintenance

## 1. 基本方針

本成果物は「常に最新版へ追従する環境」ではなく、研究室実機で通したrevisionをreferenceとして固定する。

更新は必要なときに明示的に行い、更新後にacceptance pathを再実行する。

現在のreference:

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
LeRobotDataset v3.0
```

## 2. Trossen / LeRobotを更新する場合

少なくとも以下を確認する。

```text
[ ] setup.sh / dependency resolution
[ ] pluginのrobot / teleoperator type名
[ ] config field名
[ ] Arm connect/disconnect
[ ] teleoperation
[ ] camera acquisition
[ ] one-episode recording
[ ] Dataset schema
[ ] dataset validator
[ ] action保存semantics
[ ] custom timestamp sidecar
```

特に `examples/custom_sensor/record_with_timestamps.py` はLeRobot 0.6.0の `lerobot_record.py` のrecord loopへ実行時patchを当てるreferenceである。upstreamのfunction signature、processor順序、dataset write位置、stop handlingが変更された場合は、そのまま使用しない。

更新時は旧版と新版の `lerobot_record.py` を比較し、timestampを取得する意味的位置が維持されているか確認した上で実機smoke testを行う。

## 3. Hardware configurationを変更する場合

### Arm

tracked templateはplaceholderのまま維持し、`config/teleop-local.yaml` と `config/record-local.yaml` のIPを対象環境で確認した値へ更新する。

### RealSense

serial、resolution、fpsを更新する。camera交換時は、接続deviceを再列挙してphysical viewとの対応を確認し、`check_hardware.sh` を再実行する。

個体固有のserial numberはreference repositoryへ保存せず、各環境の `*-local.yaml` で設定する。

### Public repositoryへ含めない値

以下はmachine-specific local config / local notesにのみ保持し、tracked fileへcommitしない。

- Arm IP address
- RealSense / GelSight / USB adapter等の個体serial
- `/dev/*/by-id/...` の個体固有path
- user名・hostnameを含むabsolute path
- 個人・組織固有のdataset namespace

一方、software version、verified commit、device model、resolution/fps、workstation specification、validationで得たrate/alignment統計は再現性のためreferenceへ残す。

## 4. Dataset schemaを変更する場合

state/action/camera featureを変更した場合は、少なくとも以下を確認する。

- `meta/info.json` のfeature shape/type
- Parquet column type / row count
- episode metadata
- video stream数、resolution、fps
- Datasetがloaderで読めること
- validator側の期待schema

baseline validatorは研究室標準の4 RGB camera / 14D action / 14D stateを主対象とする。新しいfeatureをLeRobotDataset本体へ直接追加する場合はvalidatorも更新する。

## 5. 外部sensorを更新する場合

transportではなくtimestamp contractを維持する。

最低限保持する情報:

```text
sample/frame index
source/device timestamp (availableなら)
host monotonic timestamp
raw data
sensor/config metadata
```

raw acquisition rateを変更した場合は、target valueではなく実測rateをvalidationへ残す。

### ROS 2 sensor

- topic名
- message type
- publisher QoS
- actual topic rate
- `header.stamp` semantics

を確認する。

### V4L2 camera

- `/dev/v4l/by-id` identifier
- advertised format/resolution/fps
- actual capture rate
- packet timestamp domain
- concurrent robot recordingへの影響

を確認する。

## 6. Provenanceを維持する

研究室既存code、vendor公式code、Phase 1で新規作成したreference codeを混同しない。

GelSightについて本Phase 1で確認した整理:

- GelSight Inc.公式 `gsrobotics`: GelSight Mini用OpenCV based SDK / demo
- 研究室側helper: 公式構造をベースにproject-specific変更が加わったもの
- 研究室側ROS 2 publisher: 出典repositoryまでは特定できなかったproject-specific wrapper
- 本成果物のcamera reference: V4L2/FFmpeg + timestamp alignmentとして新規に整理した独立reference

vendor / upstream codeを成果物へコピーする場合はlicenseと出典を別途確認する。本成果物では研究室側GelSight sourceそのものは再配布しない。

## 7. Update後のacceptance criteria

更新後は最低限、clean checkoutから以下を通す。

```text
setup
  ↓
hardware check
  ↓
teleoperation
  ↓
1 episode recording
  ↓
dataset validation
```

外部sensor codeを変更した場合は、対象sensorについてnative acquisitionとcausal alignmentを追加で確認する。
