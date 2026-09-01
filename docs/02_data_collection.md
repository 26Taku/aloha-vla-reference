# Data Collection

## 1. この資料の役割

本資料は、研究室のALOHAを用いてVLA・模倣学習向けデータを収集する際の、**初回利用からDataset validation完了までの詳細操作マニュアル**である。

初めて利用する場合は、このページを上から順に実行する。各段階を独立したcheckpointとして扱い、途中で問題が発生した場合は後段へ進まず、[04 Troubleshooting](04_troubleshooting.md) を参照してその段階で原因を切り分ける。

標準的な作業フロー:

```text
Repository取得
    ↓
Environment setup
    ↓
Hardware identification / local configuration
    ↓
Hardware check -> READY
    ↓
Teleoperation -> visual check
    ↓
Recording -> one episode or more
    ↓
Dataset validation -> PASS
```

対象とする標準構成と採用理由は [01 Reference Stack](01_reference_stack.md) に記載する。本資料では、実際に操作を進めるために必要な手順と各checkpointを扱う。

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

既存の研究用repositoryや個別プロジェクト用environmentを上書きせず、本成果物は独立したdirectoryで使用する。

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
- 本成果物で使用するdata / log directoryを準備する

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

本成果物では検証済みrevisionを固定して使用する。最新版への追従は自動では行わない。LeRobot / Trossen Plugin / Trossen Arm等を更新する場合は、[05 Maintenance](05_maintenance.md) に従って再検証する。

### Checkpoint A

以下を確認する。

- `setup.sh` がerrorなく終了する
- `lerobot_trossen` のcommitが上記reference revisionと一致する
- Python 3.12系である
- LeRobot 0.6.0、Trossen Arm 1.10.0を含む検証済み構成が確認できる

**Setup後はまだteleoperationへ進まない。次にhardware固有値を調査し、local configを作成する。**

---

## 4. Hardware identification / local configuration

### 4.1 目的

本repositoryのtracked configには、特定個体のArm IP addressやRealSense serial numberを保存しない。

初回利用時は、単に候補identifierを列挙するだけでなく、**どのidentifierがどの物理deviceに対応するかまで確認した上で** local configへ設定する。

確認する対応関係:

| Physical role | Config field | Identifier |
|---|---|---|
| follower left | `robot.left_arm_ip_address` | Arm IP |
| follower right | `robot.right_arm_ip_address` | Arm IP |
| leader left | `teleop.left_arm_ip_address` | Arm IP |
| leader right | `teleop.right_arm_ip_address` | Arm IP |
| high camera | `robot.cameras.cam_high.serial_number_or_name` | RealSense serial |
| low camera | `robot.cameras.cam_low.serial_number_or_name` | RealSense serial |
| left wrist camera | `robot.cameras.cam_left_wrist.serial_number_or_name` | RealSense serial |
| right wrist camera | `robot.cameras.cam_right_wrist.serial_number_or_name` | RealSense serial |

列挙順、過去のconfig、他環境の値だけを根拠に対応関係を決めない。

### 4.2 local configを作成

tracked templateをコピーする。

```bash
cp config/teleop-template.yaml config/teleop-local.yaml
cp config/record-template.yaml config/record-local.yaml
```

`*-local.yaml` は `.gitignore` 対象である。Arm IPやcamera serial等のmachine-specific identifierはlocal configにのみ設定し、tracked templateには書き込まない。

---

### 4.3 Arm IPと物理Armを対応付ける

Armでは、

1. network上に存在するArm ControllerのIPを見つける
2. そのIPが `follower left / follower right / leader left / leader right` のどれに対応するか確認する

という2段階が必要である。

#### 4.3.1 Trossen標準kitの参考IP

Trossen公式ドキュメントでは、LeRobot等のTrossen-supported frameworkを使用するkitについて、以下のIP割り当てが期待値として示されている。

| Physical role | 参考IP |
|---|---|
| leader left | `192.168.1.3` |
| leader right | `192.168.1.2` |
| follower left | `192.168.1.5` |
| follower right | `192.168.1.4` |

また、単体Arm Controllerのfactory default IPは `192.168.1.2` とされている。

これらは**候補値・参考値であり、対象実機の対応を保証するものではない**。Arm ControllerのIPは変更可能なので、対象実機で物理Armとの対応を確認してからlocal configへ設定する。

公式ソース:

- Trossen Arm Documentation — Software Setup / Arm Network Setup  
  https://docs.trossenrobotics.com/trossen_arm/main/getting_started/software_setup.html
- Trossen Arm Documentation — Trossen AI Configuration  
  https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot/configuration.html

#### 4.3.2 事前安全確認

Arm identification中はteleoperation / recordingを起動しない。Arm周辺に人や物体が干渉しないことを確認してから作業する。

#### 4.3.3 PC側networkを確認

```bash
ip -br addr
ip neigh
```

PCがArm Controllerと同一subnetに接続されていることを確認する。

`ip neigh` は候補deviceを把握する参考にはなるが、ARP cacheが残る場合があり、そこからphysical roleを確定することはできない。

標準kitの参考IPを利用して到達性を確認する場合:

```bash
ping -c 2 192.168.1.2
ping -c 2 192.168.1.3
ping -c 2 192.168.1.4
ping -c 2 192.168.1.5
```

4つすべてに応答があっても、その時点ではphysical roleとの対応は未確認である。

#### 4.3.4 `trossen-arm discover` が利用できる場合

Trossen Arm DriverにはArm Controllerを探索するCLIが用意されている。まず現在のpinned environmentで利用できるか確認する。

```bash
cd lerobot_trossen
uv run trossen-arm --help
uv run trossen-arm discover
```

`discover` はsubnet上のTrossen Arm Controllerを探索し、IP等を表示する。

`trossen-arm` CLIは `trossen_arm` packageのoptional `cli` extraを必要とする。現在のpinned environmentでCLI dependenciesが入っていない場合は、実機確認の途中でenvironmentへ追加installして構成を変えず、後述のfallback方法を使用する。CLIを本成果物の標準依存へ追加する場合は、dependency変更として別途検証する。

#### 4.3.5 `trossen-arm identify` でphysical roleを確認

CLIが利用可能な場合は、指定IPの物理Armを識別できる。

まずhelpを確認する。

```bash
uv run trossen-arm identify --help
```

周囲の安全を確認してからcandidate IPごとに実行する。

```bash
uv run trossen-arm identify --ip <CANDIDATE_IP>
```

公式CLIでは、指定IPへ接続し、gripperの開閉とcontroller LEDの変化によってphysical Armを識別する。

どのArmが反応したかを記録し、最終的に以下を確定する。

```text
follower left  -> <IP>
follower right -> <IP>
leader left    -> <IP>
leader right   -> <IP>
```

公式ソース:

- Trossen Arm Documentation — Command Line Interface (`discover`, `identify`)  
  https://docs.trossenrobotics.com/trossen_arm/main/getting_started/cli.html

#### 4.3.6 Fallback: Ethernet接続を切り分ける

`identify` が使用できない場合は、robot control processを全て終了した状態でEthernet接続を切り分けて確認する。

1. candidate IPへpingが通ることを確認する
2. 物理ArmのEthernet接続を1台だけ外す
3. candidate IPへ再度pingし、応答しなくなったIPを確認する
4. Ethernetを再接続し、応答が復帰することを確認する
5. 4 Armについて繰り返す

例:

```bash
ping -c 2 <CANDIDATE_IP>
```

`ip neigh` のentry消失だけではなく、ping等の実際の到達性で確認する。

---

### 4.4 RealSense serialとphysical roleを対応付ける

確認するphysical role:

```text
cam_high
cam_low
cam_left_wrist
cam_right_wrist
```

serialの一覧だけではphysical roleは分からない。各serialのcamera imageまたはlive viewを見て対応を確定する。

#### 4.4.1 LeRobot utilityを使用する（推奨）

setup後のenvironmentで以下を実行する。

```bash
cd lerobot_trossen
uv run lerobot-find-cameras realsense
```

検出されたRealSenseのserial等が表示され、cameraごとの画像が `outputs/captured_images/` に保存される。

例:

```text
outputs/captured_images/
├── realsense__<SERIAL_A>.png
├── realsense__<SERIAL_B>.png
├── realsense__<SERIAL_C>.png
└── realsense__<SERIAL_D>.png
```

画像を確認して、次のmappingを作る。

```text
cam_high        -> <SERIAL>
cam_low         -> <SERIAL>
cam_left_wrist  -> <SERIAL>
cam_right_wrist -> <SERIAL>
```

画像だけでは判別しにくい場合は、camera lensを1台ずつ手やカードで覆って再取得し、どのserialの画像が遮蔽されたかを確認する。

`Camera #0` のような列挙番号は恒久的なhardware identifierとして扱わない。本referenceではRealSense serialを使用する。

#### 4.4.2 RealSense Viewerを使用する

利用可能な場合は、

```bash
realsense-viewer
```

を起動する。各cameraのlive viewとInfo欄のSerial Numberを対応付ける。

物理cameraを1台ずつ手で覆う、あるいは視野内で明確な目印を動かすことでphysical roleを判別できる。

#### 4.4.3 Fallback: 1台ずつ接続して確認

上記で判別できない場合は、camera acquisition processを終了した状態でUSB接続を1台ずつ切り分ける。1台だけ接続した状態でserialとphysical positionを確認し、4台について繰り返す。

USBを抜き差しする前にrecording / viewer等のcamera利用processを終了する。

公式ソース:

- Trossen Arm Documentation — Trossen AI Configuration / Camera Serial Number  
  https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot/configuration.html
- Trossen SDK Documentation — Finding Device Identifiers  
  https://docs.trossenrobotics.com/trossen_sdk/configuration.html

---

### 4.5 local configを編集

repository rootへ戻る。

```bash
cd ..
```

すでにrepository rootにいる場合は不要である。

編集対象:

```text
config/teleop-local.yaml
config/record-local.yaml
```

任意のeditorを使用する。例:

```bash
nano config/teleop-local.yaml
nano config/record-local.yaml
```

両configで設定するhardware identity:

```text
robot.left_arm_ip_address
robot.right_arm_ip_address
teleop.left_arm_ip_address
teleop.right_arm_ip_address
robot.cameras.<camera_name>.serial_number_or_name
```

`robot.id: bimanual_follower` と `teleop.id: bimanual_leader` はLeRobot上のlogical identifierであり、hardware serialやIPではない。通常は変更しない。

`teleop-local.yaml` と `record-local.yaml` ではhardware identityを一致させる。一方、本repositoryではteleoperation時のcamera FPSを15、recording時のcamera FPSを30としており、用途に応じて取得設定が異なる。この差は意図したものであり、hardware identityの不一致ではない。

### 4.6 placeholderとGit管理状態を確認

次が無出力になることを確認する。

```bash
grep -RIn 'REPLACE_WITH_' \
  config/teleop-local.yaml \
  config/record-local.yaml
```

local configがGit管理外であることも確認する。

```bash
git check-ignore -v \
  config/teleop-local.yaml \
  config/record-local.yaml
```

### Checkpoint B

以下をすべて満たしてから次へ進む。

- 4 ArmのIPと `follower left / follower right / leader left / leader right` の物理対応を確認した
- 4 RealSense serialと `cam_high / cam_low / cam_left_wrist / cam_right_wrist` の物理対応を確認した
- 対応を列挙順や推測だけで決めていない
- 両local configへ同じhardware mappingを反映した
- `REPLACE_WITH_` が残っていない
- machine-specific identifierをtracked templateへ書いていない
- local configがGit管理対象外であることを確認した

---

## 5. Hardware check

### 5.1 実行

ALOHAとcameraの電源・接続を確認してから実行する。

```bash
./check_hardware.sh
```

### 5.2 目的

recordingを開始する前に、local configと実機の基本状態が一致していることを確認する。

checkerは主に以下を確認する。

- `config/teleop-local.yaml` / `config/record-local.yaml` の存在
- placeholderが残っていないこと
- teleoperation / recording config間のArm IPとcamera serial mapping
- 使用するsoftware version
- Armへのnetwork reachability
- RealSense D405の認識
- camera serialが設定値と一致すること
- data directoryへの書き込み可否
- storage free space

すべて通ると `[READY]` を表示する。

### Checkpoint C

```text
[READY]
```

が出ること。

Armへのping成功はnetwork reachabilityを示すだけであり、robot driverを用いた実動作まで保証するものではない。実際のLeader-Follower制御は次のteleoperationで確認する。

すべてのArmへのpingが失敗する場合は、まずArm本体・controllerの電源とPC側networkを確認する。

---

## 6. Teleoperation

### 6.1 実行

```bash
./teleoperate.sh
```

### 6.2 目的

recording前に、Leader-Follower制御とcamera acquisitionを実機で確認する。

確認対象:

- left leader -> left follower
- right leader -> right follower
- 左右gripper
- `cam_high`
- `cam_low`
- `cam_left_wrist`
- `cam_right_wrist`
- 不自然な振動や連続的な異常動作がないこと

終了時は:

```text
Ctrl+C
```

を使用し、Armおよびcameraが正常にdisconnectされることを確認する。

### Checkpoint D

- left/rightのLeader-Follower対応が正しい
- gripperが意図した側で動く
- 4 camera viewのphysical mappingが正しい
- 異常な動作がない
- `Ctrl+C` 後に正常にdisconnectできる

検証済み標準構成ではteleoperation loopが概ね30 Hzで動作した。ただし実周期はPC負荷やcamera処理等の影響を受けるため、常に厳密な30 Hzを保証するものではない。

Rerun / Vulkan / EGL等のwarningが表示されてもteleoperation自体が正常に動作する場合がある。warning文字列だけで失敗と判断せず、[04 Troubleshooting](04_troubleshooting.md) を参照する。

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

- `config/record-local.yaml` を基にruntime configを生成する
- dataset名を設定する
- task descriptionを設定する
- episode数とepisode時間を設定する
- local保存先を設定する
- Hugging Face Hubへの自動uploadを無効にする
- Trossen公式 `lerobot-record` を実行する

runtime configはrepository内の一時directoryに生成され、Git管理対象には含めない。

同名datasetが既に存在する場合は上書きせず停止する。必要なdatasetを誤って削除しないよう、既存datasetの扱いを確認してから再実行する。

### 7.3 標準recording構成

本成果物で確認したbaselineは以下。

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

検証済み構成では、15秒・1 episodeのbaseline収録で449 framesが保存された。target fps × episode時間と保存frame数は、実行境界や処理負荷等により完全一致しない場合があるため、固定frame数だけで成否を判断しない。

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

本成果物のbaseline schema:

```text
action             14D
observation.state  14D
camera              4 streams
dataset format      LeRobotDataset v3.0
```

camera画像はdataset内ではvideoとして保存され、Parquetにはrobot state/actionやframe/timestamp等の情報が保存される。

具体的なschema例は以下に保存している。

```text
reference/dataset_examples/baseline/info.json
```

実機検証したdatasetの詳細な結果は [06 Validation Results](06_validation_results.md) を参照する。

---

## 9. Dataset validation

### 9.1 実行

```bash
./validate_dataset.sh data/DATASET_NAME
```

例:

```bash
./validate_dataset.sh data/test_dataset
```

### 9.2 目的

recording processが終了しただけでは、学習用datasetとして必要な構造とfileが揃っていることまでは保証できない。そのため、収録後にdataset自体を検証する。

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
- video先頭frameがdecode可能であること

すべて通れば `[PASS]` を表示する。

### Checkpoint F

```text
[PASS]
```

が出ること。

validatorはDataset構造の健全性を確認するものであり、demonstrationそのものの品質を評価するものではない。task failure、操作ミス、camera occlusion等は別途確認する。

---

## 10. Robot state・外部sensorを追加する場合

baselineは14Dのrobot state/actionと4 RGB cameraを対象とする。追加のrobot stateや外部sensorを利用する場合は、baselineを直接書き換えて情報を不可逆に落とすのではなく、sensorの更新周期・timestamp・interfaceに応じた取得方法を選択する。

本成果物では、標準的な考え方を以下とする。

- robot/control rateとsensor acquisition rateを分離して考える
- RGB camera等、LeRobotのrecording rateと自然に一致するdeviceは直接統合を検討する
- 高周期F/T sensorや異なるFPSのtactile camera等はnative / actual rateで独立取得し、timestampを保持する
- raw streamを保存し、policy用の同期表現は後処理で生成する
- 同期にはfuture sampleを使用しないcausal alignmentを基本とする
- より厳密な同期が必要なtaskではhardware trigger / shared clock等を検討する

外部sensorの取得・同期方法、設計理由、実機検証例は以下を参照する。

- [03 Architecture and Extension](03_architecture_and_extension.md)
- [Custom Sensor Example](../examples/custom_sensor/README.md)
- [06 Validation Results](06_validation_results.md)

ここで示すbaseline Datasetを変更する場合は、変更後のschemaを必ず記録し、`validate_dataset.sh` または対象schemaに対応するvalidatorで保存結果を確認する。

---

## 11. Dataset収録時に残す情報

再現性のため、実験datasetを作成するときは少なくとも以下を記録する。

- 使用した本repositoryのcommit
- `lerobot_trossen` のcommit
- task description
- episode数
- episode時間
- camera構成
- Arm / sensor構成に標準設定からの変更があるか
- recording中に発生したwarning / error
- dataset validation結果

hardware構成やsoftware versionを変更した場合は、その変更内容も記録する。

実機固有のIP addressやserial numberを公開repositoryへ記録する必要はない。必要な場合はmachine-localな実験記録として管理する。

---

## 12. Baseline完了条件

初回環境の動作確認は次をすべて満たした時点で完了とする。

```text
[ ] repository obtained
[ ] setup completed
[ ] Arm IPとphysical roleの対応を確認
[ ] RealSense serialとphysical roleの対応を確認
[ ] local configs completed
[ ] hardware check -> READY
[ ] teleoperation visually verified
[ ] recording completed
[ ] dataset validation -> PASS
```

この一連の確認により、「packageがinstallできた」「Armがpingへ応答した」といった部分確認だけではなく、実際にLeader-Follower操作を行い、cameraを含む学習用Datasetが生成・検証されるところまでを確認する。

実機検証済みschema、frame数、取得rate等の結果は [06 Validation Results](06_validation_results.md) に記載する。

---

## 13. 次に行うこと

Baseline収録だけが目的ならここで完了である。

外部sensorを追加する場合:

- [03 Architecture and Extension](03_architecture_and_extension.md)
- [Custom Sensor Example](../examples/custom_sensor/README.md)

versionやhardwareを更新する場合:

- [05 Maintenance](05_maintenance.md)

問題が発生した場合:

- [04 Troubleshooting](04_troubleshooting.md)

採用したsoftware stackと他方式との使い分けを確認する場合:

- [01 Reference Stack](01_reference_stack.md)

実機でどこまで確認済みかを確認する場合:

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
