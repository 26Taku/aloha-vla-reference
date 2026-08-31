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

本成果物では最新版へ自動追従せず、実機で通したrevisionをreferenceとして固定する。versionを更新する場合の再検証条件は [05 Maintenance](05_maintenance.md) に記載する。

## 3. 想定hardware

baselineは以下の構成を対象とする。

- Bimanual leader: 2 arms
- Bimanual follower: 2 arms
- Intel RealSense D405: 4 cameras
- Camera roles:
  - `cam_high`
  - `cam_low`
  - `cam_left_wrist`
  - `cam_right_wrist`

Arm IP addressとcamera serial numberはmachine-specific identifierであり、repositoryには実機値を保存しない。tracked templateにはplaceholderを置き、利用者が対象環境を調査してlocal configへ設定する。

この設計は「特定のALOHA個体でのみ動く設定」を標準化しないためのものである。具体的なhardware identification手順は [02 Data Collection](02_data_collection.md) に一本化する。

## 4. この構成をbaselineとする理由

本プロジェクトの主目的は、ALOHAを用いてVLA・模倣学習向けDatasetを再現可能に収集することである。

そのため、以下を一つのsoftware stackで扱えることを重視した。

1. Leader-Follower teleoperation
2. Robot state / action acquisition
3. 複数camera acquisition
4. Episode recording
5. LeRobotDatasetへの保存
6. LeRobot系training / inference stackへの接続性

Trossen公式LeRobot pluginを使用することで、ALOHA固有hardware interfaceとLeRobot recording pipelineの接続をvendor側の公開実装へ寄せられる。研究室固有forkをbaselineにしないことで、project-specific変更と標準構成を分離できる。

## 5. 他の構成との使い分け

| 構成 | 本referenceでの位置づけ | 主な用途 |
|---|---|---|
| Trossen公式 LeRobot Plugin | **標準baseline** | teleoperation、RGB、state/action、LeRobotDataset収録 |
| ROS 2 | optional adapter | 外部sensor driver、独立stream、他ROS nodeとの連携 |
| Trossen driver直接利用 | project-specific | 独自制御、低レベルhardware access |
| 研究用fork | project-specific | 既存研究機能を明示的に必要とする場合 |

### ROS 2をbaselineにしない理由

外部sensorのdriverとしてROS 2が有用な場合はあるが、すべてのsensorをROS 2へ統一すること自体は目的ではない。

外部sensorは取得rateやinterfaceが異なるため、LeRobotへ直接統合する場合と、ROS 2 / V4L2 / vendor SDK等で独立取得する場合を使い分ける。詳細は [03 Architecture and Extension](03_architecture_and_extension.md) を参照する。

### 既存研究forkをbaselineにしない理由

研究用途で変更されたrepositoryは、そのprojectには有用でも、どの変更が標準動作に必要か判別しにくい。

本成果物では公式repositoryのclean revisionを別環境で検証し、研究固有機能が必要な案件だけ差分として追加する方針を採る。

## 6. Referenceとするもの / 環境ごとに決めるもの

固定するもの:

- upstream repository
- verified commit
- package version
- Dataset version
- baseline schema
- validation procedure

環境ごとに確認するもの:

- Arm IP address
- camera serial number
- camera physical roleとの対応
- optional external sensor device path / serial
- data storage policy

環境固有値をtracked fileへ残さないルールは [05 Maintenance](05_maintenance.md) に記載する。

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
