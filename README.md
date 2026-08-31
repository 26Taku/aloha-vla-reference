# ALOHA VLA Data Collection Reference

ALOHAでVLA・模倣学習向けデータ収集を始めるためのreference repositoryです。

Trossen Robotics公式 `lerobot_trossen` をbaselineとして、環境構築、hardware確認、teleoperation、LeRobotDataset収録、dataset validationまでを一つの再現可能な流れとして整理しています。外部sensorについては、baselineを複雑化させない形で追加するためのarchitectureとreference codeを別途用意しています。

## Start here

**初めてこのrepositoryを使う場合は、[docs/02_data_collection.md](docs/02_data_collection.md) を上から順に実行してください。**

初回利用の正式な手順は `docs/02_data_collection.md` に一本化しています。READMEは入口と全体像のみを示し、詳細手順は重複して記載しません。

```text
Repository取得
    ↓
Environment setup
    ↓
Hardware identification
    ↓
Local config作成・編集
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

## このrepositoryでできること

Baseline:

- Trossen公式LeRobot pluginの検証済みrevisionを再現
- Bimanual leader-follower teleoperation
- RealSense 4視点を含むLeRobotDataset v3 recording
- dataset metadata / Parquet / videoのvalidation

Optional extension:

- robot frameへのhost monotonic timestamp付与
- 高周期numeric sensorのnative-rate保存とcausal alignment
- asynchronous cameraのnative compressed保存とcausal alignment

外部sensorはbaseline Quick Startの必須要件ではありません。

## Documentation map

| 読みたい内容 | 資料 | 役割 |
|---|---|---|
| 初回セットアップから収録完了まで進めたい | [02 Data Collection](docs/02_data_collection.md) | **唯一の詳細操作マニュアル** |
| なぜこのsoftware stackを採用したか知りたい | [01 Reference Stack](docs/01_reference_stack.md) | baselineの選定理由・固定version・代替構成 |
| camera / F/T / tactile等を追加したい | [03 Architecture and Extension](docs/03_architecture_and_extension.md) | data flow・timestamp・sensor extension設計 |
| 実行中の問題を切り分けたい | [04 Troubleshooting](docs/04_troubleshooting.md) | 症状別の確認項目と対処 |
| hardware / LeRobot / Trossenを更新したい | [05 Maintenance](docs/05_maintenance.md) | 更新時の変更箇所・再検証条件・public化方針 |
| どこまで実機で確認済みか知りたい | [06 Validation Results](docs/06_validation_results.md) | 実機検証結果と未検証範囲 |
| Phase 1で何を調査・実装したか確認したい | [Implementation Report](implementation_report.md) | 納品・実施内容の要約 |

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
│   ├── teleop-template.yaml
│   └── record-template.yaml
├── scripts/
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

Arm IP addressやcamera serial number等のmachine-specific identifierはtracked fileへ保存しません。初回利用時にtemplateからGit管理外のlocal configを作成し、対象hardwareを調査して設定します。

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

Baselineのclean setup、4 Arm接続、bimanual teleoperation、RealSense 4視点recording、LeRobotDataset v3保存、dataset validationを実機確認しています。

外部sensorについては、高周期numeric streamとGelSight Mini 1台を用いて、同一host monotonic clockによるconcurrent acquisitionとcausal alignmentまで確認しています。

hardware-trigger同期、GelSight 2台同時capacity、VLA training / inferenceはPhase 1の検証範囲外です。詳細な数値は [docs/06_validation_results.md](docs/06_validation_results.md) を参照してください。
