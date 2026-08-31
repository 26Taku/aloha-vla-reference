# Data Collection

## 1. この資料の役割

本資料は、**初回利用からDataset validation完了までの唯一の詳細操作マニュアル**である。

初めて利用する場合は、このページを上から順に実行する。途中で問題が発生した場合は後段へ進まず、[04 Troubleshooting](04_troubleshooting.md) を参照してそのcheckpointで解決する。

完了条件:

```text
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

## 2. 前提とrepository取得

検証済みOSはUbuntu 24.04である。少なくとも `git` と `uv` が必要。

```bash
git --version
uv --version
```

`uv` がない場合は公式手順で導入する。

- https://docs.astral.sh/uv/getting-started/installation/

GitHubから取得する場合:

```bash
git clone https://github.com/26Taku/aloha-vla-reference.git
cd aloha-vla-reference
```

ZIP等で受け取った場合は展開し、`README.md` と `setup.sh` があるrepository rootへ移動する。

```bash
pwd
ls README.md setup.sh
```

## 3. Environment setup

実行:

```bash
./setup.sh
```

このscriptは以下を行う。

- Trossen公式 `lerobot_trossen` を取得
- 検証済みcommitへ固定
- `uv sync --frozen` でPython environmentを構築
- Python / LeRobot / Trossen Arm versionを表示
- `data/` と `logs/` を作成

Reference revision:

```text
a4336933f34192a3daa7e9fb52674284bb5ae48e
```

Checkpoint A:

- `setup.sh` がerrorなく終了する
- Trossen revisionがreference commitと一致する
- Python 3.12系、LeRobot 0.6.0、Trossen Arm 1.10.0が確認できる

**Setup後はまだteleoperationへ進まない。次にhardware固有値を調査してlocal configを作る。**

## 4. Hardware identification / local configuration

### 4.1 local configを作成

tracked templateをコピーする。

```bash
cp config/teleop-template.yaml config/teleop-local.yaml
cp config/record-template.yaml config/record-local.yaml
```

`*-local.yaml` は `.gitignore` 対象である。Arm IPやcamera serial等のmachine-specific identifierはこの2ファイルにのみ設定する。

### 4.2 Arm IPを確認

確認対象:

```text
left follower
right follower
left leader
right leader
```

PC側networkの確認例:

```bash
ip -br addr
ip neigh
```

ただし `ip neigh` の結果だけでleft/rightやleader/followerを断定しない。Arm controller/network設定と実機の物理配置を照合して4つのIPを確定する。

他環境で使われていたIPを推測で流用しない。

### 4.3 RealSense serialとphysical roleを確認

setup後のPython environmentから接続deviceを列挙できる。

```bash
cd lerobot_trossen

uv run python - <<'PY'
import pyrealsense2 as rs

for dev in rs.context().query_devices():
    print(
        dev.get_info(rs.camera_info.name),
        dev.get_info(rs.camera_info.serial_number),
    )
PY

cd ..
```

必要に応じて `rs-enumerate-devices` やRealSense Viewerも利用する。

serial一覧だけではphysical roleは分からない。映像を確認する、または1台ずつ接続状態を確認して、次の対応を決める。

```text
cam_high
cam_low
cam_left_wrist
cam_right_wrist
```

### 4.4 local configを編集

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

`robot.id: bimanual_follower` と `teleop.id: bimanual_leader` はLeRobot上のlogical identifierであり、hardware serialではない。通常は変更しない。

`teleop-local.yaml` のcamera FPSは15、`record-local.yaml` は30としている。hardware identityは同じだが、用途に応じて取得設定が異なるため、この差は意図したものである。

### 4.5 placeholderとGit管理状態を確認

次が無出力になることを確認する。

```bash
grep -RIn 'REPLACE_WITH_' \
  config/teleop-local.yaml \
  config/record-local.yaml
```

local configがGit管理外であることも確認できる。

```bash
git check-ignore -v \
  config/teleop-local.yaml \
  config/record-local.yaml
```

Checkpoint B:

- 4 ArmのIPと役割を確認した
- 4 RealSense serialとphysical roleを確認した
- 両local configを編集した
- `REPLACE_WITH_` が残っていない
- machine-specific identifierをtracked templateへ書いていない

## 5. Hardware check

ALOHAとcameraの電源・接続を確認してから実行する。

```bash
./check_hardware.sh
```

checkerは主に以下を確認する。

- local configの存在
- placeholder残存
- teleoperation / recording config間のArm IPとcamera serial mapping
- software version
- Armへのnetwork reachability
- RealSense認識とserial mapping
- data directoryへの書き込み
- storage free space

すべて通ると `[READY]` を表示する。

Checkpoint C:

```text
[READY]
```

が出ること。

注意: Armへのpingはnetwork reachabilityの確認であり、driverを含めた実動作保証ではない。次のteleoperationで実機動作を確認する。

## 6. Teleoperation

実行:

```bash
./teleoperate.sh
```

確認項目:

- left leader -> left follower
- right leader -> right follower
- 左右gripper
- `cam_high`
- `cam_low`
- `cam_left_wrist`
- `cam_right_wrist`
- 不自然な振動や連続的な異常動作がない

終了:

```text
Ctrl+C
```

Checkpoint D:

- 左右対応が正しい
- gripperが意図した側で動く
- 4 camera viewのphysical mappingが正しい
- 正常にdisconnectできる

Rerun / Vulkan / EGL等のwarningが出た場合は、warning文字列だけで失敗と判断せず [04 Troubleshooting](04_troubleshooting.md) を参照する。

## 7. Recording

形式:

```bash
./record.sh DATASET_NAME "TASK" [NUM_EPISODES] [EPISODE_TIME_S]
```

例:

```bash
./record.sh test_dataset "Pick and place an object" 1 10
```

`record.sh` は `config/record-local.yaml` を基にruntime configを作り、dataset固有値を設定して `lerobot-record` を実行する。

主なdefault:

- LeRobotDataset v3
- target FPS: 30
- RGB cameras: 4
- resolution: 424 x 240
- Hub upload: disabled
- output: `data/DATASET_NAME`

同名datasetが既に存在する場合は上書きせず停止する。

Checkpoint E:

- recording processが正常終了した
- `data/DATASET_NAME/` が作成された
- metadata / Parquet / videoが生成された

`duration x fps` とframe数は実行境界により1 frame程度ずれる場合がある。固定frame数だけで成否を判断しない。

## 8. Dataset validation

実行:

```bash
./validate_dataset.sh data/DATASET_NAME
```

例:

```bash
./validate_dataset.sh data/test_dataset
```

validatorは主に以下を確認する。

- `meta/info.json`
- Dataset version / fps / episode count / frame count
- action / observation.state schema
- Parquet row count / frame index / timestamp
- camera features
- video resolution / average FPS
- video先頭frameのdecode

すべて通れば `[PASS]` を表示する。

Checkpoint F:

```text
[PASS]
```

が出ること。

validatorはDataset構造の健全性を確認する。demonstrationのtask success、操作品質、occlusion等は別途確認する。

## 9. Baseline完了条件

初回環境のacceptanceは次をすべて満たした時点で完了とする。

```text
[ ] setup completed
[ ] hardware identifier identified
[ ] local configs completed
[ ] hardware check -> READY
[ ] teleoperation visually verified
[ ] recording completed
[ ] dataset validation -> PASS
```

実機検証済みschemaやframe数の例は [06 Validation Results](06_validation_results.md) に記載する。

## 10. 次に行うこと

Baseline収録だけが目的ならここで完了。

外部sensorを追加する場合:

- [03 Architecture and Extension](03_architecture_and_extension.md)
- [../examples/custom_sensor/README.md](../examples/custom_sensor/README.md)

versionやhardwareを更新する場合:

- [05 Maintenance](05_maintenance.md)

問題が発生した場合:

- [04 Troubleshooting](04_troubleshooting.md)
