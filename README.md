# ALOHA VLA Data Collection Reference

研究室のALOHAを用いて、VLA・模倣学習向けのデータ収集を開始するためのリファレンスです。

Trossen Robotics公式のLeRobot Pluginをベースに、研究室のALOHAで実機確認した構成・設定・確認用スクリプトをまとめています。

本リポジトリでは、単に公式ドキュメントの手順を再掲するのではなく、以下を整理します。

- VLA向けデータ収集に使用する標準構成
- 環境構築からteleoperation、recordingまでの手順
- 収録したDatasetの確認方法
- カメラや外部センサを追加する際の標準architectureとreference実装
- 実機検証中に確認した問題と対処方法

## 1. 対象

以下の流れでALOHAのデータを収集する場合を対象とします。

```text
Leaderによる操作
        ↓
ALOHA Follower
        ↓
Robot state / action + RGB cameras
        ↓
LeRobotDataset
        ↓
VLA・模倣学習
```

標準構成では、Trossen Robotics公式の `lerobot_trossen` を使用します。

## 2. 検証済み環境

研究室のALOHA実機で、以下を確認しています。

- Trossen Robotics公式 `lerobot_trossen`
- verified commit: `a4336933f34192a3daa7e9fb52674284bb5ae48e`
- LeRobot 0.6.0
- Python 3.12
- Trossen Arm 4台
- Intel RealSense D405 4台
- 左右Leader-Followerによるteleoperation
- 4視点RGBを含むrecording
- LeRobotDataset v3.0形式での保存

詳細な構成は [docs/01_reference_stack.md](docs/01_reference_stack.md) を参照してください。

外部sensorについては、MMS101相当の高周期numeric streamとGelSight Miniを用いて、native-rate acquisitionとcausal timestamp alignmentまで実機確認しています。標準baselineのsetupにROS 2やGelSight固有softwareを必須化せず、optional referenceとして `examples/custom_sensor/` に分離しています。

## 3. Quick Start

### 3.1 Environment setup

```bash
./setup.sh
```

Trossen公式リポジトリを検証済みcommitで取得し、必要なPython環境を構築します。

### 3.2 Hardware check

ALOHAとカメラの電源・接続を確認した後、

```bash
./check_hardware.sh
```

を実行します。

以下をまとめて確認します。

- Armへのネットワーク接続
- RealSenseの認識
- 使用するソフトウェアversion
- データ保存先

`[READY]` が表示されたら次へ進みます。

> Armへのping確認はネットワーク到達性の確認です。Robot driverを含めた実際の動作確認は次のteleoperationで行います。

### 3.3 Teleoperation

```bash
./teleoperate.sh
```

Rerun Viewerを確認しながら、以下を確認します。

- 左右のArmが正しく対応して動くこと
- Gripperが正しく動くこと
- 4台のカメラ映像が取得できること

終了時は `Ctrl+C` を使用します。

### 3.4 Recording

例えば、10秒のepisodeを1回収録する場合、

```bash
./record.sh test_dataset "Pick and place an object" 1 10
```

とします。

収録データはデフォルトではローカルに保存され、Hugging Face Hubにはuploadしません。

### 3.5 Dataset validation

収録後、

```bash
./validate_dataset.sh data/test_dataset
```

を実行します。

Dataset metadata、Parquet、frame数、timestamp、camera videoなどを確認し、問題がなければPASSを表示します。

## 4. Optional external sensors

robot FPSと取得周期が異なるsensorを追加する場合は、まず [examples/custom_sensor/README.md](examples/custom_sensor/README.md) と [docs/03_architecture_and_extension.md](docs/03_architecture_and_extension.md) を参照してください。

標準原則は、raw sensorを無理に30 Hzへ落とさず、raw dataと実timestampを保持し、policy用の同期表現を後処理で生成することです。

```text
High-rate numeric sensor -> native-rate JSONL -> causal current/history view
Async camera             -> native compressed video -> causal latest-frame view
```

これらはbaseline Quick Startとは独立したoptional extensionです。

## 5. 次に読む資料

- [Reference Stack](docs/01_reference_stack.md): 使用するsoftware構成、version、研究室固有設定
- [Data Collection](docs/02_data_collection.md): teleoperation、recording、Datasetの詳細
- [Architecture and Extension](docs/03_architecture_and_extension.md): ALOHAからLeRobotDatasetまでのコード構造と、camera・sensor追加時の変更箇所
- [Troubleshooting](docs/04_troubleshooting.md): 実機検証で確認した問題と対処
- [Maintenance](docs/05_maintenance.md): version更新時の確認方法
- [Validation Results](docs/06_validation_results.md): 実機で確認済みの範囲

## 6. Verification scope

本リポジトリでは、実際に研究室のALOHAで確認した内容と、設計・コード調査のみの内容を区別して記載します。

実機確認済みのbaselineに加え、高周期F/T streamと非同期GelSight cameraについて、同一host clockによるconcurrent acquisitionとcausal alignmentを確認しています。hardware-trigger同期、GelSight 2台同時capacity、VLA training/inferenceはPhase 1の検証範囲外です。
