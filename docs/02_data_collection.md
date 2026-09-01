# Data Collection

## 1. この資料の役割

本資料は、ALOHAを用いてVLA・模倣学習向けデータを収集する際の、**初回利用からDataset validation完了までの詳細操作マニュアル**である。

初めて利用する場合は、このページを上から順に実行する。各段階をcheckpointとして扱い、問題が発生した場合は後段へ進まず [04 Troubleshooting](04_troubleshooting.md) を参照する。

標準フロー:

```text
Repository取得
    ↓
Environment setup
    ↓
Arm / RealSense identification
    ↓
hardware-local.yaml 作成
    ↓
Hardware check -> READY
    ↓
Teleoperation -> visual check
    ↓
Recording -> one episode or more
    ↓
Dataset validation -> PASS
```

対象とする標準構成と採用理由は [01 Reference Stack](01_reference_stack.md) に記載する。

---

## 2. 前提とrepository取得

検証済みOSはUbuntu 24.04である。少なくとも `git` と `uv` が必要である。

```bash
git --version
uv --version
```

`uv` がない場合は公式手順で導入する。

- uv installation: https://docs.astral.sh/uv/getting-started/installation/

GitHubから取得する場合:

```bash
git clone https://github.com/26Taku/aloha-vla-reference.git
cd aloha-vla-reference
```

ZIP等で受け取った場合は展開し、`README.md` と `setup.sh` が存在するrepository rootへ移動する。

```bash
pwd
ls README.md setup.sh
```

本成果物は独立したdirectoryで使用する。

---

## 3. Environment setup

### 3.1 実行

```bash
./setup.sh
```

### 3.2 `setup.sh` が行うこと

- Trossen公式 `lerobot_trossen` repositoryを取得する
- 検証済みcommitへ固定する
- `uv sync --frozen` によりPython environmentを構築する
- Python / LeRobot / Trossen Armのversionを表示する
- data / log directoryを準備する

検証済み `lerobot_trossen` revision:

```text
a4336933f34192a3daa7e9fb52674284bb5ae48e
```

検証済み主要version:

```text
Python       3.12.x
LeRobot      0.6.0
Trossen Arm  1.10.0
```

LeRobot / Trossen Plugin / Trossen Arm等を更新する場合は [05 Maintenance](05_maintenance.md) に従って再検証する。

### Checkpoint A

- `setup.sh` がerrorなく終了する
- `lerobot_trossen` のcommitがreference revisionと一致する
- Python 3.12系である
- LeRobot 0.6.0、Trossen Arm 1.10.0が確認できる

---

## 4. Hardware identification / local configuration

### 4.1 確認する対応関係

初回利用時に以下のphysical roleとidentifierを確認する。

| Physical role | `hardware-local.yaml` field | Identifier |
|---|---|---|
| follower left | `arms.follower_left_ip` | Arm IP |
| follower right | `arms.follower_right_ip` | Arm IP |
| leader left | `arms.leader_left_ip` | Arm IP |
| leader right | `arms.leader_right_ip` | Arm IP |
| high camera | `cameras.cam_high` | RealSense serial |
| low camera | `cameras.cam_low` | RealSense serial |
| left wrist camera | `cameras.cam_left_wrist` | RealSense serial |
| right wrist camera | `cameras.cam_right_wrist` | RealSense serial |

### 4.2 Arm IPとphysical roleを確認

#### PC側network

```bash
ip -br addr
```

Trossen標準kitの `192.168.1.x` 系Armを使用する場合は、`192.168.1.x/24` のIPv4 addressを持つUP状態のnetwork interfaceが存在することを確認する。

表示例:

```text
<interface>    UP    192.168.1.1/24
```

#### Arm Controllerを検出

```bash
(
  cd lerobot_trossen
  uv run trossen-arm discover
)
```

4台のArm ControllerについてIP、model、firmware、`Error State` が表示されることを確認する。

Trossen標準kitの参考IP:

| Physical role | 参考IP |
|---|---|
| leader left | `192.168.1.3` |
| leader right | `192.168.1.2` |
| follower left | `192.168.1.5` |
| follower right | `192.168.1.4` |

#### IPとphysical Armを対応付ける

検出したcandidate IPごとに以下を実行する。

```bash
(
  cd lerobot_trossen
  uv run trossen-arm identify --ip <ARM_IP>
)
```

gripperが動作したphysical Armを確認し、次の対応を記録する。

```text
follower left  -> <IP>
follower right -> <IP>
leader left    -> <IP>
leader right   -> <IP>
```

`identify` 実行前にgripper周辺へ指、工具、配線等がないことを確認する。

公式資料:

- Trossen Arm — Software Setup / Arm Network Setup  
  https://docs.trossenrobotics.com/trossen_arm/main/getting_started/software_setup.html
- Trossen Arm — Command Line Interface  
  https://docs.trossenrobotics.com/trossen_arm/main/getting_started/cli.html

### 4.3 RealSense serialとphysical roleを確認

以下を実行する。

```bash
(
  cd lerobot_trossen
  uv run lerobot-find-cameras realsense
)
```

検出されたRealSenseのserialが表示され、cameraごとの画像が以下に保存される。

```text
lerobot_trossen/outputs/captured_images/
```

保存画像を確認し、次の対応を記録する。

```text
cam_high        -> <SERIAL>
cam_low         -> <SERIAL>
cam_left_wrist  -> <SERIAL>
cam_right_wrist -> <SERIAL>
```

画像だけで判別しにくい場合は、camera lensを1台ずつ手やカードで覆って再取得する。

公式資料:

- Trossen Arm — Trossen AI Configuration  
  https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot/configuration.html
- Trossen SDK — Finding Device Identifiers  
  https://docs.trossenrobotics.com/trossen_sdk/configuration.html

### 4.4 `hardware-local.yaml` を作成

repository rootで以下を実行する。

```bash
cp config/hardware-template.yaml config/hardware-local.yaml
```

任意のeditorで開く。

```bash
nano config/hardware-local.yaml
```

前節で確認した4 ArmのIPと4 RealSenseのserialを設定する。

例:

```yaml
arms:
  follower_left_ip: <FOLLOWER_LEFT_IP>
  follower_right_ip: <FOLLOWER_RIGHT_IP>
  leader_left_ip: <LEADER_LEFT_IP>
  leader_right_ip: <LEADER_RIGHT_IP>

cameras:
  cam_high: <CAM_HIGH_SERIAL>
  cam_low: <CAM_LOW_SERIAL>
  cam_left_wrist: <LEFT_WRIST_SERIAL>
  cam_right_wrist: <RIGHT_WRIST_SERIAL>
```

数字だけで構成されるcamera serialは、YAML上で引用符あり・なしのどちらでも入力できる。runtime config生成時に文字列へ正規化される。

`hardware-local.yaml` は `.gitignore` 対象である。Git管理状態を確認する。

```bash
git check-ignore -v config/hardware-local.yaml
```

placeholderが残っていないことを確認する。

```bash
grep -n 'REPLACE_WITH_' config/hardware-local.yaml
```

このcommandが無出力になることを確認する。

### Checkpoint B

- 4 ArmのIPとphysical roleの対応を確認した
- 4 RealSense serialとphysical roleの対応を確認した
- `config/hardware-local.yaml` に8個のidentifierを設定した
- `REPLACE_WITH_` が残っていない
- `hardware-local.yaml` がGit管理対象外である

---

## 5. Hardware check

ALOHAとcameraの電源・接続を確認してから実行する。

```bash
./check_hardware.sh
```

このscriptは `hardware-local.yaml` とtracked templateからpreflight用runtime configを生成し、主に以下を確認する。

- local hardware configが完成している
- runtime configが生成できる
- software version
- 4 Armへのnetwork reachability
- RealSense D405 x4の認識
- configured camera serialとの一致
- data directoryへの書き込み
- storage free space

すべて通ると以下を表示する。

```text
[READY]
```

### Checkpoint C

`[READY]` を確認してからteleoperationへ進む。

---

## 6. Teleoperation

### 6.1 実行前の安全確認

Follower Arm周辺に、人、工具、camera、配線等の干渉物がないことを確認する。

### 6.2 起動直後の操作

```bash
./teleoperate.sh
```

command実行後、Follower Armが起動時のstaged positionへ移動し、camera等の初期化が進む。

実機検証では、**Leader Armを動かせる状態になってからFollowerの追従loopが開始するまで短い時間差が生じる場合がある**ことを確認した。

追従開始を確認するまではLeaderを大きく移動しない。Leaderを現在位置付近で保持し、小さな動きにFollowerが連続して追従することを確認してから通常操作を開始する。

追従開始前にLeaderを大きく移動すると、追従loop開始時にFollowerがLeaderの現在姿勢へ急速に移動し、joint velocity limit等で安全停止する場合がある。

### 6.3 動作確認

recording前に以下を確認する。

- left leader -> left follower
- right leader -> right follower
- 左右gripper
- `cam_high`
- `cam_low`
- `cam_left_wrist`
- `cam_right_wrist`
- 不自然な振動や連続的な異常動作がない

終了時は `Ctrl+C` を使用し、Armおよびcameraが正常にdisconnectされることを確認する。

### 6.4 異常停止した場合

`Joint limit exceeded` 等でteleoperationが異常終了すると、Arm Controllerが現在姿勢を保持したままidle/error状態になる場合がある。

**Armがresting positionにない状態でControllerの電源を切る場合は、電源OFF前に必ずArmを物理的に支持する。**

power offで保持力が失われると、Armが自重で落下して机、camera、他Arm等へ衝突する可能性がある。

復旧手順は [04 Troubleshooting](04_troubleshooting.md#7-teleoperationが-joint-limit-exceeded-で停止する) を参照する。

### Checkpoint D

- left/rightのLeader-Follower対応が正しい
- gripperが意図した側で動く
- 4 camera viewのphysical mappingが正しい
- Followerの追従開始を確認してから通常操作を開始できる
- 異常な動作がない
- `Ctrl+C` 後に正常にdisconnectできる

検証済み標準構成ではteleoperation loopが概ね30 Hzで動作した。

Rerun / Vulkan / EGL等のwarningが表示されてもteleoperation自体が正常に動作する場合がある。既知の症状は [04 Troubleshooting](04_troubleshooting.md) を参照する。

---

## 7. Recording

### 7.1 実行

形式:

```bash
./record.sh DATASET_NAME "TASK" [NUM_EPISODES] [EPISODE_TIME_S]
```

例:

```bash
./record.sh test_dataset "Pick and place an object" 1 10
```

### 7.2 `record.sh` が行うこと

- `config/hardware-local.yaml` を読み込む
- `config/record-template.yaml` とhardware identityを合成する
- dataset名を設定する
- task descriptionを設定する
- episode数とepisode時間を設定する
- local保存先を設定する
- Hugging Face Hubへの自動uploadを無効にする
- `.runtime/record-<DATASET_NAME>.yaml` を生成する
- Trossen公式 `lerobot-record` を実行する

同名datasetが既に存在する場合は上書きせず停止する。

### 7.3 標準recording構成

baseline:

- dataset format: LeRobotDataset v3.0
- target fps: 30
- RGB cameras: 4 streams
- RGB resolution: 424 x 240
- action: 14 dimensions
- observation state: 14 dimensions
- Hub upload: disabled
- output: `data/DATASET_NAME`

14次元のaction / observation stateは、左右Armそれぞれ7値の合計で構成される。

### Checkpoint E

収録終了後、以下を確認する。

- recording processが異常終了していない
- `data/DATASET_NAME/` が作成されている
- metadataが生成されている
- episode data / Parquetが保存されている
- 4 cameraのvideoが保存されている

15秒・1 episodeのreference testでは449 framesが保存された。frame数は実行境界や処理負荷の影響を受けるため、固定frame数だけで成否を判断しない。

---

## 8. LeRobotDatasetの内容

baseline recordingでは、少なくとも以下が保存される。

```text
LeRobotDataset
├── robot action
├── robot observation state
├── camera videos
├── timestamp / frame information
├── task / episode metadata
└── dataset metadata
```

baseline schema:

```text
action             14D
observation.state  14D
camera             4 streams
dataset format     LeRobotDataset v3.0
```

camera画像はvideoとして保存され、Parquetにはrobot state/actionやframe/timestamp等の情報が保存される。

schema例:

```text
reference/dataset_examples/baseline/info.json
```

実機検証結果は [06 Validation Results](06_validation_results.md) を参照する。

---

## 9. Dataset validation

```bash
./validate_dataset.sh data/DATASET_NAME
```

例:

```bash
./validate_dataset.sh data/test_dataset
```

validatorでは主に以下を確認する。

- `meta/info.json`
- Dataset version
- fps
- episode数
- frame数
- expected camera features
- action dimension
- observation state dimension
- Parquet file
- 必要column
- row数
- frame indexの連続性
- timestampの単調増加
- metadataと実データの整合性
- video file
- video resolution
- average fps
- video先頭frameのdecode

すべて通れば `[PASS]` を表示する。

### Checkpoint F

```text
[PASS]
```

を確認する。

validatorはDataset構造の健全性を確認する。demonstrationのtask成功、操作品質、camera occlusion等は収録内容として別途確認する。

---

## 10. 外部sensorを追加する場合

baselineは14Dのrobot state/actionと4 RGB cameraを対象とする。

camera、F/T、IMU、tactile sensor等の追加方法は [03 Architecture and Extension](03_architecture_and_extension.md) を正とする。

基本方針:

- robot FPS程度で1値/1frameが必要なsensorはLeRobot observationへの直接統合を検討する
- 高周期numeric sensorはnative / actual rateで保存する
- robot FPSと異なるcameraはnative streamとtimestampを保存する
- robot/control rate、sensor acquisition rate、policy inference rateを分離する
- raw data + timestampをcanonicalとする
- policy用の同期表現はderived dataとして生成する
- causal alignmentではfuture sample/frameを使用しない
- stricter synchronizationが必要なtaskではhardware trigger / shared clock / PTP等を設計する

reference implementationの実行方法は [Custom Sensor Reference](../examples/custom_sensor/README.md)、実機検証結果は [06 Validation Results](06_validation_results.md) を参照する。

---

## 11. Dataset収録時に残す情報

実験datasetごとに少なくとも以下を記録する。

- 使用した本repositoryのcommit
- `lerobot_trossen` のcommit
- task description
- episode数
- episode時間
- camera構成
- Arm / sensor構成にbaselineからの変更があるか
- recording中に発生したwarning / error
- dataset validation結果

machine-specific identifierが必要な場合はlocalな実験記録として管理する。

---

## 12. Baseline完了条件

```text
[ ] repository obtained
[ ] setup completed
[ ] Arm IPとphysical roleの対応を確認
[ ] RealSense serialとphysical roleの対応を確認
[ ] hardware-local.yaml completed
[ ] hardware check -> READY
[ ] teleoperation visually verified
[ ] recording completed
[ ] dataset validation -> PASS
```

この条件を満たした時点で、baseline data collection environmentの動作確認完了とする。

---

## 13. 次に読む資料

外部sensorを追加する:

- [03 Architecture and Extension](03_architecture_and_extension.md)
- [Custom Sensor Reference](../examples/custom_sensor/README.md)

versionやhardwareを更新する:

- [05 Maintenance](05_maintenance.md)

問題を切り分ける:

- [04 Troubleshooting](04_troubleshooting.md)

採用stackを確認する:

- [01 Reference Stack](01_reference_stack.md)

実機検証結果を確認する:

- [06 Validation Results](06_validation_results.md)

---

## 14. 公式資料

- Trossen Robotics `lerobot_trossen`  
  https://github.com/TrossenRobotics/lerobot_trossen
- Trossen Arm — Software Setup / Arm Network Setup  
  https://docs.trossenrobotics.com/trossen_arm/main/getting_started/software_setup.html
- Trossen Arm — Command Line Interface  
  https://docs.trossenrobotics.com/trossen_arm/main/getting_started/cli.html
- Trossen Arm — Trossen AI Configuration  
  https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot/configuration.html
- Trossen SDK — Configuration / Finding Device Identifiers  
  https://docs.trossenrobotics.com/trossen_sdk/configuration.html
- Hugging Face LeRobot documentation  
  https://huggingface.co/docs/lerobot/
