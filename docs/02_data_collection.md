# Data Collection

## 1. 目的

本資料では、研究室のALOHAを用いてVLA・模倣学習向けデータを収集する際の流れと、各段階で確認する内容を整理する。

Quick Startでは最短の実行手順のみを示す。本資料では、各コマンドが何を確認しているか、どのようなデータが保存されるか、収録後に何を検証するかを補足する。

対象とする標準構成は `docs/01_reference_stack.md` に記載したTrossen Robotics公式 `lerobot_trossen` ベースの構成である。

---

## 2. データ収集の流れ

標準的な作業は以下の6段階で行う。

```text
Environment setup
      ↓
Hardware identification / configuration
      ↓
Hardware check
      ↓
Teleoperation
      ↓
Recording
      ↓
Dataset validation
```

それぞれの段階を独立したcheckpointとして扱う。途中で問題が出た場合は、後段へ進まず、その段階で原因を切り分ける。

---

## 3. Environment setup

### 実行

```bash
./setup.sh
```

### 目的

- Trossen公式 `lerobot_trossen` を取得する
- 検証済みcommitへ固定する
- `uv sync --frozen` により依存関係を構築する
- 使用する主要package versionを確認する

本成果物では、検証済みcommitとして以下を使用する。

```text
a4336933f34192a3daa7e9fb52674284bb5ae48e
```

研究室PCでは、Ubuntu 24.04環境上でPython 3.12.3を使用し、LeRobot 0.6.0、Trossen Arm 1.10.0を含む環境構築を確認した。

### Checkpoint A

以下を確認する。

- setup scriptがエラーなく終了する
- repositoryのcommitが検証済みcommitと一致する
- Pythonが3.12系である
- LeRobotおよびTrossen Arm packageのversionが検証済み構成と一致する

`setup.sh` は既存の研究用repositoryを変更せず、成果物用の別ディレクトリで使用することを前提とする。

---

## 4. Hardware identification / configuration

### 目的

本repositoryのconfigは特定個体のArm IP addressやRealSense serial numberを含まない。初回利用時は、実機を動かす前にhardware構成を確認してtemplateを編集する。

最初にtracked templateからmachine-specific configを作る。

```bash
cp config/teleop-template.yaml config/teleop-local.yaml
cp config/record-template.yaml config/record-local.yaml
```

編集対象は `config/teleop-local.yaml` と `config/record-local.yaml`。これらは `.gitignore` 対象であり、hardware固有値をrepositoryへcommitしない。

両local configで設定する項目:

```text
robot.left_arm_ip_address
robot.right_arm_ip_address
teleop.left_arm_ip_address
teleop.right_arm_ip_address
robot.cameras.<camera_name>.serial_number_or_name
```

RealSenseはserialを列挙しただけではphysical viewとの対応が分からないため、viewerまたは1台ずつの確認で `cam_high`, `cam_low`, `cam_left_wrist`, `cam_right_wrist` を対応付ける。

Arm IPはcontroller/network設定を確認する。repository内のplaceholderや他環境のIPをそのまま使用しない。

### Checkpoint B

- 4 ArmのIPとleft/right・leader/followerの対応を説明できる
- 4 RealSense serialとphysical camera positionの対応を説明できる
- 両local configから `REPLACE_WITH_` がなくなっている

---

## 5. Hardware check

### 実行

```bash
./check_hardware.sh
```

### 目的

recordingを開始する前に、設定ファイルと実機の基本状態が一致しているかを確認する。

checkerは `config/teleop-local.yaml` と `config/record-local.yaml` を参照し、主に以下を確認する。

- placeholderが残っていないこと
- 2つのconfigでArm IPとcamera serial mappingが一致すること
- 使用するsoftware version
- 4台のArmへのネットワーク到達性
- 4台のRealSense D405の認識
- camera serialが設定値と一致しているか
- データ保存先への書き込み可否
- 保存先の空き容量

### Checkpoint C

すべての確認が通ると `[READY]` が表示される。

注意点として、Armへのpingが成功することはネットワーク到達性を示すだけであり、Robot driverを用いた実動作まで保証するものではない。実際のArm制御は次のteleoperationで確認する。

4台すべてのArmへのpingが失敗する場合は、まずALOHA本体の電源状態を確認する。実機検証では、Arm電源OFF時に全IPへのpingが失敗し、電源投入後に復旧することを確認した。

---

## 6. Teleoperation

### 実行

```bash
./teleoperate.sh
```

### 目的

recording前に、Leader-Follower制御とcamera acquisitionを実機で確認する。

teleoperationのmachine-specific設定は `config/teleop-local.yaml` に記載する。

実機確認時は以下の構成を使用した。

- left follower
- right follower
- left leader
- right leader
- high camera
- low camera
- left wrist camera
- right wrist camera

### Checkpoint D

recordingへ進む前に、少なくとも以下を目視確認する。

- 左Leaderの操作が左Followerへ対応している
- 右Leaderの操作が右Followerへ対応している
- 左右Gripperが意図した側で動作する
- 4つのcamera viewが取得できている
- 不自然な振動や連続的な異常動作がない

終了時は `Ctrl+C` を使用し、Armおよびcameraが正常にdisconnectされることを確認する。

実機検証では、標準構成でteleoperation loopが約30 Hzで動作することを確認した。ただし、実際の周期はPC負荷やcamera処理等の影響を受けるため、常に厳密な30 Hzになることを保証するものではない。

Rerun / graphics backend由来のwarningが表示されてもteleoperation自体が正常に動作する場合がある。既知のwarningは `docs/04_troubleshooting.md` に整理する。

---

## 7. Recording

### 実行

`record.sh` は、実機確認済みのrecording設定をtemplateとして使用し、dataset名、task、episode数、episode時間を指定して収録するwrapperである。

形式:

```bash
./record.sh DATASET_NAME "TASK" NUM_EPISODES EPISODE_TIME_S
```

例:

```bash
./record.sh test_dataset "Pick and place an object" 1 10
```

### `record.sh` が行うこと

- `config/record-local.yaml` を基にruntime用設定を生成する
- dataset名を設定する
- task descriptionを設定する
- episode数とepisode時間を設定する
- ローカル保存先を設定する
- Hugging Face Hubへの自動uploadを無効にする
- Trossen公式 `lerobot-record` を実行する

runtime用設定は `.runtime/` 以下に生成し、Git管理対象には含めない。

### 標準recording構成

実機確認したbaselineでは以下を使用した。

- recording target: LeRobotDataset v3.0
- target fps: 30
- camera: 4 streams
- RGB resolution: 424 × 240
- action: 14 dimensions
- observation state: 14 dimensions

14次元は左右Armそれぞれ7値の合計で構成される。

### Checkpoint E

収録終了後、以下を確認する。

- dataset directoryが作成されている
- metadataが生成されている
- episode dataが保存されている
- camera videoが保存されている
- recording processが異常終了していない

実機で行った15秒・1 episodeのbaseline収録では449 framesが保存された。

target fps × episode時間と保存frame数は、実行境界や処理負荷等により完全一致しない場合がある。そのため、単純な `duration × fps` の完全一致だけで成否を判断しない。

---

## 8. LeRobotDatasetの内容

baseline recordingでは、少なくとも以下の情報が保存される。

```text
LeRobotDataset
├── robot action
├── robot observation state
├── camera videos
├── timestamp / frame information
├── task / episode metadata
└── dataset metadata
```

実機確認したdatasetでは、

- action: 14-dimensional float data
- observation state: 14-dimensional float data
- camera video: 4 streams
- dataset format: LeRobotDataset v3.0

となった。

camera画像はdataset内ではvideoとして保存される。Parquetにはrobot state/actionやframe/timestamp等の情報が保存される。

具体的なschema例は `reference/dataset_examples/baseline/info.json` に保存している。

---

## 9. Dataset validation

### 実行

```bash
./validate_dataset.sh data/DATASET_NAME
```

例:

```bash
./validate_dataset.sh data/test_dataset
```

### 目的

recording processが終了しただけでは、学習用datasetとして必要なファイルが揃っていることまでは保証できない。そのため、収録後にdataset自体を検証する。

validatorでは主に以下を確認する。

- `meta/info.json` が読み込める
- Dataset version
- fps
- episode数
- frame数
- expected camera features
- action dimension
- observation state dimension
- Parquet fileの存在
- 必要columnの存在
- row数
- frame indexの連続性
- timestampの単調増加
- metadataと実データの整合性
- video fileの存在
- video resolution
- average fps
- videoの先頭frameがdecode可能か

すべて通ればPASSとなる。

### Checkpoint F

baseline datasetについて、

```bash
./validate_dataset.sh data/DATASET_NAME
```

がPASSすれば、標準的なVLA・模倣学習用収録フローの完了とする。

validatorはdatasetの構造的な健全性を確認するものであり、demonstrationの内容そのものの品質を評価するものではない。例えば、操作ミス、task failure、camera occlusion等は別途確認する必要がある。

---

## 10. 状態量を追加した場合

実機検証では、Trossen側で取得可能なexternal effortを有効化し、observation stateを14次元から28次元へ拡張したrecordingも確認した。

結果として、

```text
baseline:
action             14D
observation.state  14D

external effort enabled:
action             14D
observation.state  28D
```

となり、追加した状態量がLeRobotDatasetのschemaおよびParquetまで反映されることを確認した。

この検証は、LeRobotのRobot observationへ追加された数値情報がrecording pipelineを通ってDatasetへ保存されることを確認したものである。

独立した外部sensorは、Trossen driver内部のstate extensionとは分けて扱う。Phase 1ではMMS101相当の高周期numeric streamとGelSight Miniを用いて、raw acquisitionをrobot recordingから分離し、同一host monotonic clockによるcausal alignmentを実機確認した。

外部sensorの取得・alignment手順は `examples/custom_sensor/README.md`、設計理由と検証結果は `docs/03_architecture_and_extension.md` / `docs/06_validation_results.md` に記載する。

---

## 11. Dataset収録時に残す情報

再現性のため、実験datasetを作成するときは少なくとも以下を記録する。

- 使用した本成果物repositoryのcommit
- `lerobot_trossen` のcommit
- task description
- episode数
- episode時間
- camera構成
- Arm / sensor構成に標準設定からの変更があるか
- recording中に発生したwarning / error
- dataset validation結果

hardware構成やsoftware versionを変更した場合は、変更内容も記録する。

---

## 12. 標準フローの完了条件

VLA・模倣学習向けのbaseline data collectionでは、以下をすべて満たした時点を収録環境の動作確認完了とする。

```text
[ ] setupが完了
[ ] hardware identifierを調査しconfigへ設定
[ ] hardware checkerがREADY
[ ] teleoperationを目視確認
[ ] episode recordingが完了
[ ] dataset validatorがPASS
```

この6段階を通すことで、「packageが入った」「Armがpingに応答した」といった部分確認だけではなく、実際に学習用Datasetが生成されるところまでを一つのacceptance pathとして確認する。
