# ALOHA VLA Data Collection Reference

ALOHAでVLA・模倣学習向けデータ収集を始め、camera・F/T・tactile等の追加sensorへ拡張するためのreference repositoryです。

Trossen Robotics公式 `lerobot_trossen` をbaselineとして、環境構築、hardware identification、teleoperation、LeRobotDataset収録、dataset validationまでを一つの再現可能な流れとして整理しています。加えて、取得周期やinterfaceが異なる外部sensorを追加するための設計原則、timestamp、同期、reference implementationを提供します。

## Start here

目的に応じて、最初に読む資料を選びます。

- **ALOHAを初めてセットアップしてDatasetを収録したい**  
  → [docs/02_data_collection.md](docs/02_data_collection.md) を上から順に実行する
- **camera / F/T / tactile等のsensorを追加したい**  
  → baselineを一度動作確認した後、[docs/03_architecture_and_extension.md](docs/03_architecture_and_extension.md) のdecision guideから方式を選ぶ

通常の初回利用フロー:

```text
Repository取得
    ↓
Environment setup
    ↓
Hardware identification
    ↓
hardware-local.yaml 作成
    ↓
Hardware check
    ↓
Teleoperation
    ↓
Recording
    ↓
Dataset validation
```

途中で問題が発生した場合は [docs/04_troubleshooting.md](docs/04_troubleshooting.md) を参照してください。

## このrepositoryが提供する2つのreference

### 1. Reproducible ALOHA data collection

- Trossen公式LeRobot pluginの検証済みrevisionを再現
- Bimanual leader-follower teleoperation
- RealSense 4視点を含むLeRobotDataset v3 recording
- dataset metadata / Parquet / videoのvalidation
- machine-specific hardware identityを1つのlocal configで管理
- fresh cloneからDataset validationまでのend-to-end確認手順

詳細操作は [02 Data Collection](docs/02_data_collection.md) に一本化しています。

### 2. Sensor extension reference

- 新しいsensorをLeRobotへ直接統合するか、独立streamとして取得するかのdecision guide
- robot frameへのhost monotonic timestamp付与
- 高周期numeric sensorのnative-rate保存
- asynchronous cameraのnative compressed保存
- robot/sensor間のcausal alignment
- current-value / history-window等のderived representation
- software synchronizationとhardware synchronizationの境界

設計判断は [03 Architecture and Extension](docs/03_architecture_and_extension.md)、reference codeの実行方法は [examples/custom_sensor/README.md](examples/custom_sensor/README.md) を参照してください。

外部sensorを使用しない場合は、baseline data collectionだけで完結します。

## Documentation map

| 読みたい内容 | 資料 | 役割 |
|---|---|---|
| 初回セットアップから収録完了まで進めたい | [02 Data Collection](docs/02_data_collection.md) | **baselineの唯一の詳細操作マニュアル** |
| camera / F/T / tactile等を追加したい | [03 Architecture and Extension](docs/03_architecture_and_extension.md) | **sensor extensionの唯一の設計ガイド** |
| sensor reference codeを実行したい | [Custom Sensor Reference](examples/custom_sensor/README.md) | scriptの入力・出力・CLI |
| なぜこのsoftware stackを採用したか知りたい | [01 Reference Stack](docs/01_reference_stack.md) | baselineの選定理由・固定version・代替構成 |
| 実行中の問題を切り分けたい | [04 Troubleshooting](docs/04_troubleshooting.md) | 症状別の確認項目と安全な復旧 |
| hardware / LeRobot / Trossenを更新したい | [05 Maintenance](docs/05_maintenance.md) | 更新時の変更箇所・再検証条件・public化方針 |
| どこまで実機で確認済みか知りたい | [06 Validation Results](docs/06_validation_results.md) | 実機検証結果と未検証範囲 |
| 調査・選定・実装内容を確認したい | [Implementation Report](implementation_report.md) | 納品・実施内容の要約 |

## Repository layout

```text
.
├── README.md
├── setup.sh
├── check_hardware.sh
├── teleoperate.sh
├── record.sh
├── validate_dataset.sh
├── config/
│   ├── hardware-template.yaml
│   ├── teleop-template.yaml
│   └── record-template.yaml
├── scripts/
│   └── build_runtime_config.py
├── examples/
│   └── custom_sensor/
├── docs/
│   ├── 01_reference_stack.md
│   ├── 02_data_collection.md
│   ├── 03_architecture_and_extension.md
│   ├── 04_troubleshooting.md
│   ├── 05_maintenance.md
│   └── 06_validation_results.md
└── implementation_report.md
```

初回利用時は `config/hardware-template.yaml` からGit管理外の `config/hardware-local.yaml` を作成します。Arm IP addressとcamera serial number等のmachine-specific identifierは、このlocal fileだけに設定します。

`teleop-template.yaml` と `record-template.yaml` は、camera FPS等の用途別設定を保持します。各wrapperは実行時にhardware identityとtemplateを合成し、`.runtime/` 以下へLeRobot用configを生成します。

## Reference baseline

実機検証したbaseline:

```text
TrossenRobotics/lerobot_trossen
verified commit: a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot:         0.6.0
Python:          3.12
Dataset:         LeRobotDataset v3.0
```

この構成を採用した理由と代替構成との使い分けは [docs/01_reference_stack.md](docs/01_reference_stack.md) に記載しています。

## Verification scope

baselineのclean setup、4 Arm identification、4 RealSense identification、single-source hardware configuration、bimanual teleoperation、LeRobotDataset v3 recording、dataset validationを実機確認しています。

外部sensorについては、高周期numeric streamとGelSight Mini 1台をtest caseとして、同一host monotonic clockによるconcurrent acquisitionとcausal alignmentまで確認しています。

hardware-trigger同期、GelSight 2台同時capacity、VLA training / inferenceは本referenceの検証範囲外です。詳細な数値は [docs/06_validation_results.md](docs/06_validation_results.md) を参照してください。
