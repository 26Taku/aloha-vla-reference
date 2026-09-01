# Reference Stack

## 1. この資料の役割

本資料は、**何をbaselineとして採用したか、なぜ採用したか**を説明する。

初回セットアップや収録の操作手順はここでは扱わない。実際に作業する場合は [02 Data Collection](02_data_collection.md) を使用する。実機検証結果の数値は [06 Validation Results](06_validation_results.md) に分離する。

## 2. 採用baseline

| 項目 | Reference |
|---|---|
| Trossen integration | `TrossenRobotics/lerobot_trossen` |
| Verified commit | `a4336933f34192a3daa7e9fb52674284bb5ae48e` |
| LeRobot | 0.6.0 |
| Python | 3.12 |
| Environment manager | `uv` |
| Trossen Arm library | 1.10.0 |
| Dataset format | LeRobotDataset v3.0 |

本成果物では実機で通したrevisionをreferenceとして固定する。versionを更新する場合の再検証条件は [05 Maintenance](05_maintenance.md) に記載する。

## 3. 想定hardwareとconfiguration

baselineは以下の構成を対象とする。

- Bimanual leader: 2 arms
- Bimanual follower: 2 arms
- Intel RealSense D405: 4 cameras
- Camera roles:
  - `cam_high`
  - `cam_low`
  - `cam_left_wrist`
  - `cam_right_wrist`

machine-specific hardware identityは、Git管理外の1ファイルに集約する。

```text
config/hardware-local.yaml
```

このfileには以下を設定する。

```text
4 ArmのIP address
4 RealSenseのserial number
```

tracked configの役割は以下。

```text
hardware-template.yaml  hardware identityの入力template
teleop-template.yaml    teleoperation固有設定
record-template.yaml    recording固有設定
```

各wrapperは実行時に `hardware-local.yaml` と用途別templateを合成し、`.runtime/` 以下へLeRobot用configを生成する。

具体的なhardware identificationとlocal config作成手順は [02 Data Collection](02_data_collection.md) に記載する。

## 4. この構成をbaselineとする理由

本referenceの主目的は、ALOHAを用いてVLA・模倣学習向けDatasetを再現可能に収集し、camera・F/T・tactile等の追加sensorを案件ごとにゼロから設計し直さずに済む基準を残すことである。

そのため、以下を一つのsoftware stackで扱えることを重視した。

1. Leader-Follower teleoperation
2. Robot state / action acquisition
3. 複数camera acquisition
4. Episode recording
5. LeRobotDatasetへの保存
6. LeRobot系training / inference stackへの接続性

Trossen公式LeRobot pluginを使用することで、ALOHA固有hardware interfaceとLeRobot recording pipelineの接続をvendor側の公開実装へ寄せられる。研究固有機能はbaseline上の差分として追加する。

## 5. 他の構成との使い分け

| 構成 | 本referenceでの位置づけ | 主な用途 |
|---|---|---|
| Trossen公式 LeRobot Plugin | **標準baseline** | teleoperation、RGB、state/action、LeRobotDataset収録 |
| ROS 2 | sensor acquisition adapter | ROS 2 driverで提供される外部sensor、他ROS nodeとの連携 |
| Trossen driver直接利用 | project-specific | 独自制御、低レベルhardware access |
| 研究用fork | project-specific | 既存研究機能を明示的に必要とする場合 |

### ROS 2

外部sensorにはROS 2、V4L2、serial API、vendor SDK等、deviceごとのinterfaceを使用する。

ROS 2 driverで提供されるF/TやIMU等はROS 2 adapterとして取得できる。sensor追加時の保存形式、timestamp、同期、検証項目は [03 Architecture and Extension](03_architecture_and_extension.md) を正とする。

### 既存研究fork

研究用途で変更されたrepositoryにはproject-specificな機能が含まれる。本referenceはTrossen公式repositoryのclean revisionをbaselineとし、必要な研究機能だけを明示的な差分として追加する。

## 6. Referenceとするもの / 環境ごとに決めるもの

固定するもの:

- upstream repository
- verified commit
- package version
- Dataset version
- baseline schema
- validation procedure
- operation-specific template

環境ごとに確認するもの:

- Arm IP address
- camera serial number
- camera physical roleとの対応
- external sensor device path / serial
- data storage policy

環境固有値は `hardware-local.yaml` またはproject-specific local fileに保持する。public repositoryへ含める情報の基準は [05 Maintenance](05_maintenance.md) に記載する。

## 7. Baselineから変更する場合

| 変更内容 | 主に確認する資料 |
|---|---|
| Arm / RealSenseを交換 | [02 Data Collection](02_data_collection.md), [05 Maintenance](05_maintenance.md) |
| Camera / sensorを追加 | [03 Architecture and Extension](03_architecture_and_extension.md) |
| Robot stateを追加 | [03 Architecture and Extension](03_architecture_and_extension.md) |
| LeRobot / Trossenを更新 | [05 Maintenance](05_maintenance.md) |
| Dataset schemaを変更 | [03 Architecture and Extension](03_architecture_and_extension.md), [05 Maintenance](05_maintenance.md) |
| 実機確認済み範囲を確認 | [06 Validation Results](06_validation_results.md) |

## 8. 公式資料

- Trossen Robotics LeRobot integration  
  https://github.com/TrossenRobotics/lerobot_trossen
- Trossen Robotics LeRobot Installation Guide  
  https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot_plugin/setup.html
- Hugging Face LeRobot documentation  
  https://huggingface.co/docs/lerobot/
