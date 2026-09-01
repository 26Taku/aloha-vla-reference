# Architecture and Sensor Extension

## 1. この資料の役割と責任境界

本資料は、**追加sensorの実装そのものではなく、既存のsensor streamをALOHA / LeRobotへ接続する境界と、その境界以降の収録・timestamp・alignment・validationを標準化する操作・設計マニュアル**である。

通常のALOHA setup、hardware identification、teleoperation、baseline recordingは [02 Data Collection](02_data_collection.md) を先に完了する。

追加sensorについては、研究室内driver、過去の実験code、vendor SDK、ROS 2 wrapper等、既に利用可能な取得系を優先して再利用する。動作しているsensor-specific implementationを本reference専用実装へ置き換えることは要求しない。

責任境界は次のように置く。

```text
Sensor-specific layer                         Reference integration layer
────────────────────────────────────────────────────────────────────────────
hardware connection
firmware / vendor setup
sensor-specific driver / SDK
project-specific initialization
calibration when required
        │
        │  usable data stream
        │  + known interface / format
        ▼
==================== integration boundary ====================
        │
        ├─ stream inspection / actual-rate measurement
        ├─ native-rate raw acquisition
        ├─ host timestamp assignment
        ├─ ALOHA timestamped recording
        ├─ concurrent acquisition
        ├─ causal alignment
        └─ validation
```

本referenceを開始する時点で、対象sensorからdata streamを取得できることを前提とする。代表的な開始点は次のいずれかである。

```text
ROS 2 numeric sensor : 対象topicがpublishされている
V4L2 camera          : 対象video deviceからstreamを取得できる
vendor SDK / API     : sample / frameを継続取得できる
```

既存implementationがSection 4のinterface contractを満たす場合はそのまま接続する。満たさない場合のみ、driver本体を大きく変更するのではなく、必要最小限のadapterを追加してcontractへ合わせる。

本repositoryが直接提供するreference pathは次の二つである。

1. **High-rate numeric stream**
   - ROS 2 topicを `ros2_timeseries_logger.py` でnative-rate sidecarへ保存する
2. **Asynchronous camera stream**
   - Linux V4L2 cameraをFFmpegでnative compressed streamとして保存する

MMS101とGelSight Miniは、上記contractを実機で確認した具体例として扱う。sensor-specific driver / wrapperのsource codeは、本referenceのinterface contractとは分離する。driver sourceを本repositoryへ含める場合は、provenanceとlicenseを別途確認する。

`examples/custom_sensor/README.md` は各reference scriptのCLI / input / output仕様をまとめる。camera captureのFFmpeg option等の詳細は `examples/custom_sensor/camera/README.md` を参照する。実測結果は [06 Validation Results](06_validation_results.md) に記録する。

### 1.1 実行手順の読み方

本資料では、command blockを次の2種類に明確に分ける。

#### 利用者向け実行コマンド

利用者が自分の環境へ合わせて実行するtemplateである。変更が必要な値には必ず `REPLACE_WITH_...` を使用する。

```bash
SENSOR_TOPIC=REPLACE_WITH_SENSOR_TOPIC
```

`REPLACE_WITH_...` があるblockは、そのまま実行してはならない。直前の「変更する値」にある調べ方で値を決めてから実行する。

#### 実機検証例

本referenceの検証環境で**実際に実行し、記載した成功条件まで確認したliteral command**である。

実機検証例には次を含めない。

```text
REPLACE_WITH_...
<SENSOR_TOPIC> のようなplaceholder
未確認のdevice path / message type / mode
```

実機検証例は、`REPLACE_WITH_...` にどのような値が入るかを示す具体例でもある。別環境では値をそのまま流用せず、「利用者向け実行コマンド」の値を対象hardwareに合わせて決定する。

各操作は原則として次の順序で記載する。

```text
目的
↓
変更する値
↓
利用者向け実行コマンド
↓
実機検証例
↓
成功条件
```

確認状態:

- **[HW-VERIFIED]**: 実機で確認済み
- **[CODE-VERIFIED]**: source codeまたはoffline testで確認済み
- **[DESIGN]**: 推奨設計。対象条件での実機確認前

---

## 2. Sensor extensionの開始条件と完了条件

### 2.1 Entry checkpoint S0

ALOHA integrationへ進む前に、sensor-specific layerが次を満たすことを確認する。

```text
[ ] 対象sensorをhardware / OS / driverから利用できる
[ ] sample / frameを継続取得できる
[ ] interfaceを特定できる
[ ] data format / message typeを確認できる
[ ] actual acquisition rateを測定できる
```

ROS 2 sensorの場合は、少なくとも次が成立する状態を開始点とする。

```bash
ros2 topic list
ros2 topic type <SENSOR_TOPIC>
ros2 topic echo <SENSOR_TOPIC> --once
ros2 topic hz <SENSOR_TOPIC>
```

V4L2 cameraの場合は、少なくとも対象deviceと使用可能なformatを確認できる状態を開始点とする。

```bash
v4l2-ctl --list-devices
v4l2-ctl --device <VIDEO_DEVICE> --list-formats-ext
```

S0を満たさない場合、まだALOHA integrationの問題とは判定しない。sensor固有のdriver / SDK / hardware設定、または既存実験環境の起動手順を確認し、streamを取得可能にしてから本資料へ戻る。

既存streamの形式がSection 4のcontractに一致しない場合は、薄いadapterを追加する。adapterの目的はinterface変換に限定し、sensorのraw informationやnative rateを不要に失わないこと。

### 2.2 End-to-end completion

S0を通過したsensorは、sensor単体が読めた時点では完了としない。以下を最後まで確認する。

```text
Baseline ALOHA -> READY / PASS
        ↓
Entry checkpoint S0 -> PASS
        ↓
Integration patternを選択
        ↓
Reference側でsensor単体取得
        ↓
actual acquisition rateを確認
        ↓
ALOHA timestamp付きrecordingを準備
        ↓
Sensor + ALOHA concurrent acquisition
        ↓
raw data / timestampsを保存
        ↓
causal alignment
        ↓
validation
        ↓
Sensor extension complete
```

最低限のacceptance criteria:

```text
[ ] baselineの ./check_hardware.sh -> READY
[ ] baseline teleoperation / recording / validation -> PASS
[ ] Entry checkpoint S0 -> PASS
[ ] reference側のsensor単体取得が継続する
[ ] sensorのactual rateを確認した
[ ] raw sample/frameとtimestampを保存した
[ ] ALOHAとsensorを同時取得できた
[ ] robot frame timestamp sidecarを保存した
[ ] timestampが単調増加する
[ ] causal alignmentでfuture sample/frame = 0
[ ] missing数とsensor/camera ageを確認した
```

---

## 3. 追加sensorの方式を選ぶ

まずsensorの出力形式と必要な時間解像度を確認する。

| 条件                                                         | 使用する方式                                 |
| ------------------------------------------------------------ | -------------------------------------------- |
| robot FPS程度で取得でき、各robot frameに1値/1frameあれば十分 | **Pattern A: LeRobot observationへ直接統合** |
| F/T・IMU等の高周期numeric streamをraw waveformのまま残したい | **Pattern B: native-rate numeric sidecar**   |
| tactile camera等、robot FPSと異なるcamera streamを残したい   | **Pattern C: asynchronous camera sidecar**   |
| sub-ms同期、同時exposure、複数host間の厳密同期が必要         | **Pattern D: hardware synchronization**      |

代表的な判断:

```text
既存sensor stream
    │
    ├─ numeric time series?
    │      │
    │      ├─ robot FPS程度で瞬時値のみ必要
    │      │      -> Pattern A
    │      │
    │      └─ high-rate waveform/historyが必要
    │             -> Pattern B
    │
    ├─ camera / tactile image?
    │      │
    │      ├─ robot FPSへ自然に統合できる
    │      │      -> Pattern A
    │      │
    │      └─ native FPSを保持したい
    │             -> Pattern C
    │
    └─ software timestampでは同期精度が不足
           -> Pattern D
```

transportやdriver名だけで方式を決めない。同じROS 2 topicでも、raw historyを残す必要があればPattern B、robot frameごとの瞬時値だけで十分ならPattern Aとなる。

### 3.1 既存implementationを接続する順序

新しいsensorを追加するときは、まず既存実装が直接contractを満たすか確認する。

```text
existing driver / SDK / experiment code
        │
        ├─ ROS 2 numeric topicとして使える
        │      -> Pattern B reference loggerへ直接接続
        │
        ├─ V4L2 cameraとして使える
        │      -> Pattern C reference captureへ直接接続
        │
        ├─ LeRobot observationへ安全に載せられる
        │      -> Pattern A
        │
        └─ そのままではcontractを満たさない
               -> thin adapter
               -> Section 4のcontractへ合わせる
```

adapterを追加する場合も、sensor acquisition rate、raw value、source timestamp等を不要に変換・間引きしない。policy向けのresamplingやfeature extractionはraw取得後のderived stageで行う。

---

## 4. Integration interface contract

本referenceで標準化するのはsensor-specific driverではなく、driver / SDKからALOHA integration側へ渡す境界である。

### 4.1 Pattern B: high-rate numeric contract

Pattern Bへ直接接続するstreamは次を満たすこと。

```text
Required
[ ] sampleを継続取得できる
[ ] sampleにnumeric valueが含まれる
[ ] data format / message typeを特定できる
[ ] actual rateを測定できる
[ ] host側でsample受信時刻を付与できる

Recommended
[ ] source/device timestampを保持できる
[ ] stableなdevice / stream identifierを使用できる
[ ] acquisitionをrobot control loopから独立して実行できる

Not required
[ ] 特定sensor model
[ ] 特定topic名
[ ] 特定driver implementation
[ ] robot FPSと同じsampling rate
```

本repositoryの `ros2_timeseries_logger.py` を直接使用する場合は、追加で次を満たす。

```text
interface       ROS 2 topic
message type    rosidl_runtime_py から解決可能
payload         message内にnumeric fieldを含む
source time     header.stamp があれば保存、なくても可
host time       logger callback入口で CLOCK_MONOTONIC を付与
```

`geometry_msgs/msg/WrenchStamped` は検証済みの一例であり、必須message typeではない。

既存driverがROS 2を使用しない場合は、次のどちらかを選ぶ。

1. 既存driverの出力をROS 2 numeric topicへ変換する薄いadapterを用意し、reference loggerへ接続する
2. 同等のcanonical raw recordを直接保存するadapterを用意し、Section 4.4のtimestamp contractと後段alignmentが使える形にする

2を選ぶ場合は、reference scriptそのものを通していないことをvalidation記録へ明記する。

### 4.2 Pattern C: asynchronous camera contract

Pattern Cへ接続するcamera streamは次を満たすこと。

```text
Required
[ ] frameを継続取得できる
[ ] frame順序を保持できる
[ ] captureされたframeに対応するtimestampを取得または復元できる
[ ] actual frame rateを測定できる

Recommended
[ ] stableなdevice identifierを使用できる
[ ] native compressed streamを取得できる
[ ] captureをrobot recordingと独立processで実行できる

Not required
[ ] 特定camera model
[ ] robot FPSと同じframe rate
[ ] ROS 2 camera wrapper
```

本repositoryのPattern C reference pathを直接使用する場合は、Linux V4L2から対象video streamを取得できることを開始条件とする。

```text
V4L2 video device
    ↓
FFmpeg native capture
    ↓
MKV packet timestamps
    ↓
extract_mkv_timestamps.py
    ↓
causal alignment
```

vendor SDKやROS 2 image topicしか利用できないcameraは、そのinterfaceから同等のraw frame + timestamp contractへ変換するadapterを用意するか、対象interface向けのacquisition pathを別途実装する。

### 4.3 Pattern A: direct observation contract

Pattern Aでは、sensor readがrobot loopを長時間blockせず、各robot frameに対して一貫したshape / dtypeのobservationを返せることを要求する。

```text
[ ] sensor connect / disconnectを管理できる
[ ] observation key / shape / dtypeを固定できる
[ ] get_observation()から値を返せる
[ ] target loop rateを大きく低下させない
[ ] Dataset schema / validatorを更新できる
```

raw high-rate dynamicsを保持する必要がある場合はPattern Aだけに押し込まず、Pattern Bを併用する。

### 4.4 Canonical raw data / timestamp contract

外部sensor streamには可能な限り次を保持する。

```text
sample/frame index
source/device timestamp        (取得可能な場合)
host monotonic timestamp
raw data
sensor/config metadata
```

収集時点でpolicy用表現だけへ変換せず、raw data + timestampをcanonicalとする。

```text
raw acquisition
      ↓
canonical raw + timestamps
      ↓
derived synchronized view
      ↓
policy / training input
```

### 4.5 Rateを分離する

次のrateを同一と仮定しない。

```text
sensor acquisition rate
robot/control rate
policy inference rate
```

sensorは安定して取得できるnative / actual rateで保存し、robot / policyへ渡すrateはderived representation側で決める。

### 4.6 Host monotonic clock

同一host上でのsoftware alignmentには `CLOCK_MONOTONIC` を使用する。

source/device timestampが得られる場合も保存するが、そのclock domainを確認せずhost timestampと直接比較しない。

### 4.7 LeRobotDataset timestamp

通常のLeRobotDataset timestampはtarget FPSに基づくlogical frame timeとして扱う。

外部sensorの実受信時刻とのalignmentには、Section 5で追加するrobot frameのhost monotonic timestampを使用する。

---

## 5. 共通準備: ALOHAへ実timestampを追加してrecordingする

Pattern B / Cでは、通常のLeRobotDatasetに加えてrobot frameごとのhost timestampを保存する。

### 5.1 Baseline状態を確認

#### 利用者向け実行コマンド

```bash
./check_hardware.sh
```

#### 実機検証例

```bash
./check_hardware.sh
```

#### 成功条件

```text
[READY]
```

通常のteleoperationと1 episode recordingが未確認の場合は、先に [02 Data Collection](02_data_collection.md) を完了する。

### 5.2 timestamp付きrecording configを生成

#### 変更する値

| 変数             | 内容                            | 値の決め方                          |
| ---------------- | ------------------------------- | ----------------------------------- |
| `RUN_ID`         | Datasetとsidecarをまとめるrun名 | 既存Datasetと重複しない名前を付ける |
| `TASK`           | episodeのtask description       | 収録内容を短く記述する              |
| `EPISODE_TIME_S` | recording時間                   | testでは10秒程度から開始する        |

同じ`RUN_ID`をDataset、runtime config、sensor sidecarで共有する。

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
TASK="REPLACE_WITH_TASK"
EPISODE_TIME_S=REPLACE_WITH_EPISODE_TIME_S

mkdir -p .runtime data

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output "../.runtime/$RUN_ID.yaml" \
    --dataset-name "$RUN_ID" \
    --task "$TASK" \
    --num-episodes 1 \
    --episode-time-s "$EPISODE_TIME_S" \
    --dataset-root "../data/$RUN_ID"
)
```

#### 実機検証例 — MMS101 / current workspace

以下は現在の検証workspaceで次回のPattern B final acceptanceに使用する具体値である。placeholderはない。

```bash
mkdir -p .runtime data

test ! -e data/sensor_numeric_final

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output ../.runtime/sensor_numeric_final.yaml \
    --dataset-name sensor_numeric_final \
    --task "High-rate numeric sensor final validation" \
    --num-episodes 1 \
    --episode-time-s 10 \
    --dataset-root ../data/sensor_numeric_final
)
```

`test ! -e` が失敗する場合は同名Datasetが既に存在する。既存Datasetを削除せず、利用者向け実行コマンドで別`RUN_ID`を設定する。

### 5.3 timestamp付きrecordingを実行

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID

(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path="../.runtime/$RUN_ID.yaml"
)
```

#### 実機検証例 — MMS101 / current workspace

```bash
(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path=../.runtime/sensor_numeric_final.yaml
)
```

通常のLeRobotDatasetに加えて、利用者向けcommandでは次の形式で生成される。

```text
data/<RUN_ID>/
└── meta/
    └── frame_timestamps/
        ├── episode_000000.jsonl
        └── episode_000000.meta.json
```

current workspaceの実機検証例では次になる。

```text
data/sensor_numeric_final/meta/frame_timestamps/episode_000000.jsonl
data/sensor_numeric_final/meta/frame_timestamps/episode_000000.meta.json
```

代表robot時刻は `observation_end_monotonic_ns` である。

### 5.4 Datasetを検証

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
./validate_dataset.sh "data/$RUN_ID"
```

#### 実機検証例 — MMS101 / current workspace

```bash
./validate_dataset.sh data/sensor_numeric_final
```

#### 成功条件

```text
[PASS] Dataset matches the expected ALOHA reference schema.
```

### 5.5 timestamp sidecarを確認

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID

head -n 2 \
  "data/$RUN_ID/meta/frame_timestamps/episode_000000.jsonl"
```

#### 実機検証例 — MMS101 / current workspace

```bash
head -n 2 \
  data/sensor_numeric_final/meta/frame_timestamps/episode_000000.jsonl
```

各recordに少なくとも以下が存在することを確認する。

```text
frame_index
dataset_timestamp_s
observation_end_monotonic_ns
```

**[HW-VERIFIED]** 通常のLeRobotDataset recordingとtimestamp sidecarを同時に保存できることを確認済みである。

---

## 6. Pattern B: High-rate numeric sensorを追加する

対象例:

- 6-axis F/T
- IMU
- pressure
- encoder
- high-rate scalar / vector sensor

この節は、sensor-specific driver / SDKを起動してnumeric streamが利用可能になったところから開始する。

### 6.1 Step B0 — topic / message type / actual rateを確認

#### 変更する値

`SENSOR_TOPIC`を`ros2 topic list`から選ぶ。topic名は推測しない。

`MESSAGE_TYPE`は手入力で推測せず、`ros2 topic type`の出力を確認する。

#### 利用者向け実行コマンド

```bash
ros2 topic list

SENSOR_TOPIC=REPLACE_WITH_SENSOR_TOPIC

ros2 topic type "$SENSOR_TOPIC"
ros2 topic echo "$SENSOR_TOPIC" --once
ros2 topic hz "$SENSOR_TOPIC"
```

`ros2 topic type`が例えば次を返した場合、

```text
geometry_msgs/msg/WrenchStamped
```

loggerへ渡す値も同じ完全修飾typeである。

#### 実機検証例 — MMS101 / current workspace

前提として、既存MMS101 driverが起動し `/force_torque/left` をpublishしていること。

```bash
source /opt/ros/jazzy/setup.bash

ros2 topic type /force_torque/left
test "$(ros2 topic type /force_torque/left)" = "geometry_msgs/msg/WrenchStamped"
ros2 topic echo /force_torque/left --once
ros2 topic hz /force_torque/left
```

このworkspaceで確認されたmessage typeは `geometry_msgs/msg/WrenchStamped` である。

**[HW-VERIFIED]** subscriber側はMMS101 workspaceのoverlayを必要としない。MMS101 driverを別processで起動した状態で、環境を継承しないclean shellから `/opt/ros/jazzy/setup.bash` のみをsourceし、topic type / echoとgeneric loggerの3秒取得を確認した。loggerは298 sampleを保存した。

#### 成功条件 B0

```text
[ ] SENSOR_TOPICが存在する
[ ] MESSAGE_TYPEを取得できる
[ ] 1 message以上を受信できる
[ ] ros2 topic hzが継続してsampleを観測する
[ ] payloadに必要なnumeric valueが含まれる
```

ここを満たさない場合はreference loggerへ進まず、sensor driver / SDK / hardware側を確認する。

### 6.2 Step B1 — ROS Pythonを決める

`ros2` commandが動作していても、activeな`python3`が`rclpy`と互換とは限らない。

#### 利用者向け実行コマンド

```bash
which python3
python3 --version
/usr/bin/python3 --version

python3 -c 'import sys, rclpy; print(sys.executable); print(sys.version)'
```

activeな`python3`で失敗した場合は、ROS 2と互換なinterpreterを確認する。

```bash
/usr/bin/python3 -c 'import sys, rclpy; print(sys.executable); print(sys.version)'
```

成功したinterpreterを`ROS_PYTHON`へ設定する。

```bash
ROS_PYTHON=REPLACE_WITH_ROS_COMPATIBLE_PYTHON
```

#### 実機検証例 — MMS101 / current workspace

```bash
which python3
python3 --version
/usr/bin/python3 --version

/usr/bin/python3 -c 'import sys, rclpy; print(sys.executable); print(sys.version)'
/usr/bin/python3 -c 'import rclpy; print("rclpy import: OK")'
```

このworkspaceでは次を確認した。

```text
active python3     /home/ubuntu/miniforge3/bin/python3
active version     Python 3.13.13
system Python      Python 3.12.3
ROS_PYTHON         /usr/bin/python3
```

#### 成功条件

```text
rclpy import: OK
```

### 6.3 Step B2 — sensor loggerを単体確認

#### 変更する値

| 変数           | 内容                        | 調べ方             |
| -------------- | --------------------------- | ------------------ |
| `RUN_ID`       | 単体testの識別名            | 一意な名前を付ける |
| `SENSOR_TOPIC` | sensor topic                | Step B0            |
| `MESSAGE_TYPE` | 完全修飾ROS 2 type          | Step B0            |
| `ROS_PYTHON`   | `rclpy`をimportできるPython | Step B1            |

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
SENSOR_TOPIC=REPLACE_WITH_SENSOR_TOPIC
MESSAGE_TYPE=REPLACE_WITH_FULL_ROS2_MESSAGE_TYPE
ROS_PYTHON=REPLACE_WITH_ROS_COMPATIBLE_PYTHON

SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
mkdir -p "$SENSOR_RUN_DIR"

"$ROS_PYTHON" examples/custom_sensor/ros2_timeseries_logger.py \
  --topic "$SENSOR_TOPIC" \
  --msg-type "$MESSAGE_TYPE" \
  --sensor-id "$RUN_ID" \
  --output "$SENSOR_RUN_DIR/raw.jsonl" \
  --duration 10

wc -l "$SENSOR_RUN_DIR/raw.jsonl"
head -n 1 "$SENSOR_RUN_DIR/raw.jsonl"
cat "$SENSOR_RUN_DIR/raw.jsonl.meta.json"
```

#### 実機検証例 — MMS101 / 実行済みcommand

以下は実際に成功したcommandである。

```bash
source /opt/ros/jazzy/setup.bash

mkdir -p data/_sensor_runs/numeric_smoke

/usr/bin/python3 examples/custom_sensor/ros2_timeseries_logger.py \
  --topic /force_torque/left \
  --msg-type geometry_msgs/msg/WrenchStamped \
  --sensor-id numeric_smoke \
  --output data/_sensor_runs/numeric_smoke/raw.jsonl \
  --duration 10

wc -l data/_sensor_runs/numeric_smoke/raw.jsonl
head -n 1 data/_sensor_runs/numeric_smoke/raw.jsonl
cat data/_sensor_runs/numeric_smoke/raw.jsonl.meta.json
```

実測結果:

```text
1002 samples / 10 s
```

先頭recordでは `wrench.force.x/y/z` と `wrench.torque.x/y/z` がnumeric valuesとして保存された。

#### 成功条件 B1

```text
[ ] loggerがerrorなく終了
[ ] raw.jsonlが0行ではない
[ ] sample_indexが保存される
[ ] receive_monotonic_nsが保存される
[ ] valuesが空ではない
[ ] actual rateを確認できる
```

### 6.4 Step B3 — concurrent recording用のrunを準備

単体testとconcurrent testは別`RUN_ID`を使用する。

#### 変更する値

```text
RUN_ID
TASK
EPISODE_TIME_S
```

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
TASK="REPLACE_WITH_TASK"
EPISODE_TIME_S=REPLACE_WITH_EPISODE_TIME_S

SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
DATASET_DIR="data/$RUN_ID"
RUNTIME_CONFIG=".runtime/$RUN_ID.yaml"

mkdir -p .runtime "$SENSOR_RUN_DIR"
test ! -e "$DATASET_DIR"

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output "../$RUNTIME_CONFIG" \
    --dataset-name "$RUN_ID" \
    --task "$TASK" \
    --num-episodes 1 \
    --episode-time-s "$EPISODE_TIME_S" \
    --dataset-root "../$DATASET_DIR"
)
```

#### 実機検証例 — MMS101 / current workspace final acceptance

```bash
mkdir -p .runtime data/_sensor_runs/sensor_numeric_final

test ! -e data/sensor_numeric_final

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output ../.runtime/sensor_numeric_final.yaml \
    --dataset-name sensor_numeric_final \
    --task "High-rate numeric sensor final validation" \
    --num-episodes 1 \
    --episode-time-s 10 \
    --dataset-root ../data/sensor_numeric_final
)
```

### 6.5 Step B4 — sensorとALOHAを同時取得

重要なのは起動順である。

```text
Terminal A: sensor driver
        ↓
Terminal B: raw sensor logger START
        ↓
loggerの開始messageを確認
        ↓
Terminal C: ALOHA recording START
        ↓
ALOHA recording END
        ↓
Terminal B: sensor logger END

required:
sensor recording interval ⊇ robot recording interval
```

#### Terminal B — 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
SENSOR_TOPIC=REPLACE_WITH_SENSOR_TOPIC
MESSAGE_TYPE=REPLACE_WITH_FULL_ROS2_MESSAGE_TYPE
ROS_PYTHON=REPLACE_WITH_ROS_COMPATIBLE_PYTHON

SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
mkdir -p "$SENSOR_RUN_DIR"

"$ROS_PYTHON" examples/custom_sensor/ros2_timeseries_logger.py \
  --topic "$SENSOR_TOPIC" \
  --msg-type "$MESSAGE_TYPE" \
  --sensor-id "$RUN_ID" \
  --output "$SENSOR_RUN_DIR/raw.jsonl" \
  --duration 60
```

#### Terminal B — 実機検証例: MMS101 / current workspace

```bash
source /opt/ros/jazzy/setup.bash

mkdir -p data/_sensor_runs/sensor_numeric_final

/usr/bin/python3 examples/custom_sensor/ros2_timeseries_logger.py \
  --topic /force_torque/left \
  --msg-type geometry_msgs/msg/WrenchStamped \
  --sensor-id sensor_numeric_final \
  --output data/_sensor_runs/sensor_numeric_final/raw.jsonl \
  --duration 60
```

loggerの開始messageが出たらTerminal Cを開始する。

#### Terminal C — 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID

(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path="../.runtime/$RUN_ID.yaml"
)

./validate_dataset.sh "data/$RUN_ID"
```

#### Terminal C — 実機検証例: MMS101 / current workspace

```bash
(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path=../.runtime/sensor_numeric_final.yaml
)

./validate_dataset.sh data/sensor_numeric_final

wc -l \
  data/sensor_numeric_final/meta/frame_timestamps/episode_000000.jsonl
```

実機検証ではDataset validatorが`[PASS]`となり、timestamp sidecarは299行だった。

#### 成功条件

Dataset validatorが`[PASS]`になり、timestamp sidecarのframe数がDataset metadataと一致し、sensor loggerの取得区間がrobot recording全体を包含すること。10秒・30 Hzの検証例では299 frameだった。

### 6.6 Step B5 — causal alignment

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
DATASET_DIR="data/$RUN_ID"

python3 examples/custom_sensor/align_timeseries.py \
  --robot-frames \
    "$DATASET_DIR/meta/frame_timestamps/episode_000000.jsonl" \
  --sensor \
    "$SENSOR_RUN_DIR/raw.jsonl" \
  --output \
    "$SENSOR_RUN_DIR/aligned_latest.jsonl"

python3 examples/custom_sensor/validate_alignment.py \
  "$SENSOR_RUN_DIR/aligned_latest.jsonl" \
  --require-complete
```

#### 実機検証例 — MMS101 / current workspace final acceptance

```bash
python3 examples/custom_sensor/align_timeseries.py \
  --robot-frames \
    data/sensor_numeric_final/meta/frame_timestamps/episode_000000.jsonl \
  --sensor \
    data/_sensor_runs/sensor_numeric_final/raw.jsonl \
  --output \
    data/_sensor_runs/sensor_numeric_final/aligned_latest.jsonl

python3 examples/custom_sensor/validate_alignment.py \
  data/_sensor_runs/sensor_numeric_final/aligned_latest.jsonl \
  --require-complete
```

#### 成功条件

```text
aligned frames      = robot frames
missing frames      = 0
future samples used = 0
malformed records   = 0
[PASS]
```

`future samples used = 0`だが先頭または末尾にまとまった`missing frames`が出る場合は、sensor loggerがrobot recording全体を包含していたか確認する。別runのraw fileを指定していないかも確認する。

### 6.7 Step B6 — 200 ms history window

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
DATASET_DIR="data/$RUN_ID"

python3 examples/custom_sensor/build_sensor_windows.py \
  --robot-frames \
    "$DATASET_DIR/meta/frame_timestamps/episode_000000.jsonl" \
  --sensor \
    "$SENSOR_RUN_DIR/raw.jsonl" \
  --output \
    "$SENSOR_RUN_DIR/windows_200ms.jsonl" \
  --window-ms 200
```

#### 実機検証例 — MMS101 / current workspace final acceptance

```bash
python3 examples/custom_sensor/build_sensor_windows.py \
  --robot-frames \
    data/sensor_numeric_final/meta/frame_timestamps/episode_000000.jsonl \
  --sensor \
    data/_sensor_runs/sensor_numeric_final/raw.jsonl \
  --output \
    data/_sensor_runs/sensor_numeric_final/windows_200ms.jsonl \
  --window-ms 200
```

#### 成功条件 B2

```text
[ ] ALOHA Dataset validator -> PASS
[ ] sensor raw streamがrobot recording全体を包含
[ ] robot timestamp sidecarが存在
[ ] aligned frames = robot frames
[ ] missing frames = 0
[ ] future samples used = 0
[ ] alignment validation -> PASS
[ ] history windowでfuture samples used = 0
[ ] actual sensor rate / sensor ageを記録
```

ここまででPattern Bのsoftware-level integration確認を完了とする。

---

## 7. Validated example: MMS101

MMS101はPattern Bの具体例として使用する。

### 7.1 Driver / provenance

検証では研究室内で使用されているROS 2 driverを利用した。このdriverには複数の開発・修正履歴があるため、sensor-specific driver sourceは本referenceの配布物に含めない。

本reference側の開始条件はdriver名やlaunch file名ではなく、次のinterfaceである。

```text
transport       ROS 2 topic
payload         numeric 6-axis force / torque
verified type   geometry_msgs/msg/WrenchStamped
verified topic  /force_torque/left
rate            固定値を仮定せず実測
```

MMS101の接続、serial device設定、driver build、sensor initialization、calibrationはsensor-specific layerとして利用者側で準備する。

### 7.2 別sensorへ置き換えるときの対応

| MMS101検証値                      | 別sensorで決める値 | 調べ方                            |
| --------------------------------- | ------------------ | --------------------------------- |
| `/force_torque/left`              | `SENSOR_TOPIC`     | `ros2 topic list`                 |
| `geometry_msgs/msg/WrenchStamped` | `MESSAGE_TYPE`     | `ros2 topic type "$SENSOR_TOPIC"` |
| `/usr/bin/python3`                | `ROS_PYTHON`       | `rclpy` import test               |
| `sensor_numeric_final`            | `RUN_ID`           | 一意な名前を付ける                |

Section 6の「利用者向け実行コマンド」では上記を`REPLACE_WITH_...`へ代入する。Section 6の「実機検証例」はMMS101/current workspace向けの具体値をすべて入れたcommandである。

### 7.3 実機検証結果

**[HW-VERIFIED] interface boundary**

MMS101 driverを別processで起動した状態で、subscriber側はROS 2 Jazzyの標準環境だけで接続できることを確認した。環境を継承しないclean shellで `/opt/ros/jazzy/setup.bash` のみをsourceし、`/force_torque/left` のtype / payloadを取得できた。

確認されたinterface:

```text
topic         /force_torque/left
message type  geometry_msgs/msg/WrenchStamped
payload       6-axis force / torque
```

generic loggerも同じclean shellから実行し、3秒で298 sampleを保存した。したがってsubscriber / logger側はMMS101固有workspaceをsourceしない。driver側でtopicがpublish済みであり、subscriber側でmessage packageを利用できることをentry conditionとする。

**[HW-VERIFIED] standalone logger**

```text
1002 samples / 10 s
raw JSONL + receive_monotonic_ns
```

**[HW-VERIFIED] final concurrent validation**

実機検証ではALOHAのinitialization時間を十分に包含するため、sensor loggerを60秒で先に開始し、その中で10秒のALOHA episodeを収録した。

```text
ALOHA Dataset
  frames                299
  target rate           30 Hz
  action                14D
  observation.state     14D
  camera streams        4
  validator             PASS
  timestamp sidecar     299 records

MMS101 raw stream
  samples               6002 / 60 s
  actual rate           約100 Hz

Causal latest alignment
  robot frames          299
  sensor samples        6002
  aligned frames        299
  missing frames        0
  future samples used   0
  malformed records     0
  sensor age median     7.727 ms
  sensor age p95        15.029 ms
  sensor age max        16.809 ms
  validation            PASS

200 ms history window
  robot frames          299
  ok frames             299
  insufficient frames   0
  future samples used   0
  samples/window median 20
  p05                   19
  p95                   21
  min                   19
  max                   21
```

これにより、MMS101をtest caseとしたPattern Bのsoftware-level integration validationは完了とする。

---

## 8. Pattern C: Asynchronous cameraを追加する

対象例:

- tactile camera
- high-resolution USB camera
- robot recording FPSと異なるcamera
- native compressed streamを保持したいcamera

この節はcamera固有SDKの構築ではなく、V4L2からcamera streamを取得可能になったところから開始する。

### 8.1 Step C0 — deviceとmodeを確認

#### 変更する値

```text
DEVICE
PIXEL_FORMAT
WIDTH
HEIGHT
ADVERTISED_FPS
```

値は`v4l2-ctl`の出力から決める。

#### 利用者向け実行コマンド

```bash
v4l2-ctl --version
ffmpeg -version
ffprobe -version

v4l2-ctl --list-devices
ls -l /dev/v4l/by-id/

DEVICE=REPLACE_WITH_VIDEO_DEVICE

v4l2-ctl \
  --device "$DEVICE" \
  --list-formats-ext
```

#### 実機検証例 — GelSight Mini / current workspace

```bash
v4l2-ctl --version
ffmpeg -version
ffprobe -version

v4l2-ctl --list-devices

v4l2-ctl --device /dev/video6 --list-formats-ext
v4l2-ctl --device /dev/video26 --list-formats-ext
```

両candidate nodeで次を確認した。

```text
pixel format    MJPG
resolution      3280x2464
interval        0.040 s
advertised FPS  25
```

Pattern Cの1台検証には `/dev/video6` を使用した。

#### 成功条件 C0

```text
[ ] target cameraを一意に選べる
[ ] video nodeを決められる
[ ] pixel format / resolution / advertised FPSを確認できる
[ ] 継続captureに使用できるmodeが存在する
```

### 8.2 Step C1 — camera単体capture

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
DEVICE=REPLACE_WITH_VIDEO_DEVICE
WIDTH=REPLACE_WITH_WIDTH
HEIGHT=REPLACE_WITH_HEIGHT
ADVERTISED_FPS=REPLACE_WITH_ADVERTISED_FPS

SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
OUT="$SENSOR_RUN_DIR/raw.mkv"

mkdir -p "$SENSOR_RUN_DIR"

ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size "${WIDTH}x${HEIGHT}" \
  -framerate "$ADVERTISED_FPS" \
  -timestamps default \
  -t 10 \
  -i "$DEVICE" \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  "$OUT"

ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,avg_frame_rate \
  -of default=noprint_wrappers=1 \
  "$OUT"

python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  "$OUT" \
  --output "$SENSOR_RUN_DIR/timestamps.jsonl"
```

#### 実機検証例 — GelSight Mini / current workspace

```bash
mkdir -p data/_sensor_runs/gelsight_smoke

ffmpeg -y \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size 3280x2464 \
  -framerate 25 \
  -timestamps default \
  -t 10 \
  -i /dev/video6 \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  data/_sensor_runs/gelsight_smoke/raw.mkv
```

保存結果を確認した。

```bash
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,avg_frame_rate \
  -of default=noprint_wrappers=1 \
  data/_sensor_runs/gelsight_smoke/raw.mkv

ffmpeg -v error \
  -i data/_sensor_runs/gelsight_smoke/raw.mkv \
  -frames:v 1 \
  -f null -

python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  data/_sensor_runs/gelsight_smoke/raw.mkv \
  --output data/_sensor_runs/gelsight_smoke/timestamps.jsonl

wc -l data/_sensor_runs/gelsight_smoke/timestamps.jsonl
head -n 2 data/_sensor_runs/gelsight_smoke/timestamps.jsonl
```

確認結果:

```text
codec             mjpeg
resolution        3280x2464
container rate    25/1
video frames      188
effective rate    18.754 Hz
decode smoke      PASS
timestamp export  PASS
timestamp monotonic
```

capture開始時にFFmpegから `EOI missing, emulating` が1回表示されたが、MKV保存、frame decode、timestamp exportまで正常に完了した。

#### 成功条件 C1

```text
[ ] MKV captureが完了
[ ] ffprobeでvideoを読める
[ ] packet timestampをexportできる
[ ] timestampが単調増加
[ ] actual rateを確認できる
```

### 8.3 Step C2 — concurrent recordingを準備

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
TASK="REPLACE_WITH_TASK"
EPISODE_TIME_S=REPLACE_WITH_EPISODE_TIME_S

SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
DATASET_DIR="data/$RUN_ID"
RUNTIME_CONFIG=".runtime/$RUN_ID.yaml"

mkdir -p .runtime "$SENSOR_RUN_DIR"
test ! -e "$DATASET_DIR"

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output "../$RUNTIME_CONFIG" \
    --dataset-name "$RUN_ID" \
    --task "$TASK" \
    --num-episodes 1 \
    --episode-time-s "$EPISODE_TIME_S" \
    --dataset-root "../$DATASET_DIR"
)
```

#### 実機検証例 — GelSight Mini / current workspace

```bash
mkdir -p .runtime data/_sensor_runs/sensor_gelsight_final

test ! -e data/sensor_gelsight_final

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output ../.runtime/sensor_gelsight_final.yaml \
    --dataset-name sensor_gelsight_final \
    --task "Asynchronous GelSight camera smoke test" \
    --num-episodes 1 \
    --episode-time-s 10 \
    --dataset-root ../data/sensor_gelsight_final
)
```

### 8.4 Step C3 — cameraとALOHAを同時取得

起動順:

```text
Terminal A: camera capture START
        ↓
FFmpegがframeを受信していることを確認
        ↓
Terminal B: ALOHA recording START
        ↓
ALOHA recording END
        ↓
Terminal A: camera capture END

required:
camera recording interval ⊇ robot recording interval
```

#### Terminal A — 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
DEVICE=REPLACE_WITH_VIDEO_DEVICE
WIDTH=REPLACE_WITH_WIDTH
HEIGHT=REPLACE_WITH_HEIGHT
ADVERTISED_FPS=REPLACE_WITH_ADVERTISED_FPS

SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
OUT="$SENSOR_RUN_DIR/raw.mkv"

ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size "${WIDTH}x${HEIGHT}" \
  -framerate "$ADVERTISED_FPS" \
  -timestamps default \
  -t 30 \
  -i "$DEVICE" \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  "$OUT"
```

#### Terminal A — 実機検証例: GelSight Mini / current workspace

```bash
ffmpeg -y \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size 3280x2464 \
  -framerate 25 \
  -timestamps default \
  -t 40 \
  -i /dev/video6 \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  data/_sensor_runs/sensor_gelsight_final/raw.mkv
```

FFmpegがframeを受信していることを確認してからTerminal Bを開始した。

#### Terminal B — 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID

(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path="../.runtime/$RUN_ID.yaml"
)

./validate_dataset.sh "data/$RUN_ID"
```

#### Terminal B — 実機検証例: GelSight Mini / current workspace

```bash
(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path=../.runtime/sensor_gelsight_final.yaml
)

./validate_dataset.sh data/sensor_gelsight_final
```

Dataset validatorで次を確認した。

```text
Dataset version   v3.0
FPS               30
frames            299
episodes          1
action            14D
observation       14D
RealSense videos  4
validation        PASS
```

### 8.5 Step C4 — timestamp exportとcausal alignment

#### 利用者向け実行コマンド

```bash
RUN_ID=REPLACE_WITH_RUN_ID
SENSOR_RUN_DIR="data/_sensor_runs/$RUN_ID"
DATASET_DIR="data/$RUN_ID"

python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  "$SENSOR_RUN_DIR/raw.mkv" \
  --output "$SENSOR_RUN_DIR/timestamps.jsonl"

python3 examples/custom_sensor/camera/align_camera_frames.py \
  --robot-frames \
    "$DATASET_DIR/meta/frame_timestamps/episode_000000.jsonl" \
  --camera-timestamps \
    "$SENSOR_RUN_DIR/timestamps.jsonl" \
  --output \
    "$SENSOR_RUN_DIR/aligned_latest.jsonl"
```

#### 実機検証例 — GelSight Mini / current workspace

```bash
python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  data/_sensor_runs/sensor_gelsight_final/raw.mkv \
  --output data/_sensor_runs/sensor_gelsight_final/timestamps.jsonl

python3 examples/custom_sensor/camera/align_camera_frames.py \
  --robot-frames \
    data/sensor_gelsight_final/meta/frame_timestamps/episode_000000.jsonl \
  --camera-timestamps \
    data/_sensor_runs/sensor_gelsight_final/timestamps.jsonl \
  --output \
    data/_sensor_runs/sensor_gelsight_final/aligned_latest.jsonl
```

確認結果:

```text
robot frames        299
camera frames       750
effective rate      18.728 Hz
aligned frames      299
missing frames      0
future frames used  0
reused assignments  111
camera age median   26.461 ms
camera age p95      50.617 ms
camera age max      53.083 ms
alignment           PASS
```

robot 30 Hzに対してcamera actual rateが約18.7 Hzであるため、`reused assignments = 111`は想定内である。

#### 成功条件 C2

```text
[ ] ALOHA Dataset validator -> PASS
[ ] camera recordingがrobot recording全体を包含
[ ] packet timestamp export -> PASS
[ ] aligned frames = robot frames
[ ] missing frames = 0
[ ] future frames used = 0
[ ] actual camera rateを記録
[ ] camera age distributionを記録
```

robot FPSがcamera actual rateより高い場合、同じcamera frameが複数robot frameへ割り当てられることは正常である。

FFmpeg / V4L2 optionの詳細は [Asynchronous Camera Reference](../examples/custom_sensor/camera/README.md) を参照する。

---

## 9. Validated example: GelSight Mini

**[HW-VERIFIED]**

GelSight MiniをPattern Cのtest caseとして使用した。

### 9.1 Software / driver boundary

GelSight固有SDK、画像処理、marker tracking、calibrationはsensor-specific layerとして扱う。本referenceでは研究室固有ROS 2 wrapperを必須とせず、Linux V4L2 cameraとしてstreamを取得可能な状態を開始点とする。

### 9.2 Current workspaceで確認したinterface

```text
device used        /dev/video6
pixel format       MJPG / MJPEG
resolution         3280x2464
advertised FPS     25
standalone frames  188 / 約10 s
standalone rate    18.754 Hz
```

`/dev/video26`でも同じadvertised modeを確認したが、Pattern Cの1台validationには`/dev/video6`を使用した。

device pathはUSB enumeration等で変化し得るため、別環境ではSection 8.1から再確認する。

### 9.3 End-to-end validation

current workspaceで次を最後まで確認した。

```text
V4L2 /dev/video6
→ MJPEG 3280x2464 @ advertised 25 fps
→ FFmpeg stream copy
→ MKV packet timestamp export
→ timestamp付きALOHA recording
→ Dataset validation
→ causal latest-frame alignment
```

final run:

```text
ALOHA frames        299
ALOHA rate          30 Hz
camera frames       750
camera actual rate  18.728 Hz
aligned frames      299
missing frames      0
future frames used  0
reused assignments  111
camera age median   26.461 ms
camera age p95      50.617 ms
camera age max      53.083 ms
Dataset validation  PASS
camera alignment    PASS
```

これにより、GelSight Mini 1台を用いたPattern Cのsoftware-level integration validationは完了とする。

2台同時capture時のUSB / CPU / storage capacityは未検証であり、必要な構成では別途capacity testを行う。

最終的な実測値は [06 Validation Results](06_validation_results.md) にも記録する。

---

## 10. Pattern A: LeRobot observationへ直接統合する

**[DESIGN]**

Pattern Aは、sensor dataを各robot frameのobservationとして直接LeRobotDatasetへ追加する方法である。

向いている条件:

- sensor rateがrobot/control rateと同程度
- raw high-rate waveformを保持する必要がない
- 1 robot frameに1つのsensor stateで十分
- sensor readがcontrol loopを長時間blockしない

### 10.1 実装項目

最低限、次を一貫して変更する。

1. sensor connect / disconnect
2. observation featureのkey / shape / dtype
3. `get_observation()` が返すdata
4. Dataset schema
5. validator
6. loop rateへの影響確認

```text
External sensor
      ↓
sensor adapter / latest buffer
      ↓
Robot observation
      ↓
build_dataset_frame()
      ↓
LeRobotDataset
```

### 10.2 実装確認

変更後に短いrecordingを実行し、

```text
[ ] meta/info.jsonにfeatureが存在
[ ] Parquetに対応columnが存在
[ ] shape / dtypeがfeature定義と一致
[ ] video / baseline state/actionを壊していない
[ ] target loop rateへ大きな低下がない
[ ] validatorが変更後schemaを検証
```

を確認する。

Pattern Aのsensor固有実装は対象driverに依存するため、本referenceでは特定sensor classを標準実装として固定しない。

---

## 11. Pattern D: Hardware synchronization

software timestampで必要精度を満たせない場合に使用する。

対象例:

- camera exposure instantを揃える
- sub-millisecond同期
- 複数host間で厳密なclock共有
- sensor内部clockとrobot clockのoffset保証

候補:

```text
hardware trigger
shared device clock
PTP
external synchronization signal
```

必要な同期精度と対象hardwareのcapabilityを定義してから方式を選ぶ。

本referenceで実機確認したPattern B / Cは、同一host monotonic clockによるsoftware-level synchronizationである。

---

## 12. Baseline data pathとextension boundary

baselineはTrossen公式 `lerobot_trossen` とLeRobot 0.6.0を使用する。

```text
Follower Robot     Teleoperator
      │               │
      │ get_observation() / get_action()
      └──────────┬────┘
                 ▼
              processors
                 │
                 ├─> robot.send_action()
                 │
                 ▼
        build_dataset_frame()
                 │
                 ▼
          dataset.add_frame()
                 │
                 ▼
        LeRobotDataset v3
```

Pattern Aではこのobservation schemaを拡張する。

Pattern B / Cではbaseline Dataset pathを維持し、外部sensor raw streamとtimestampをsidecarとして独立取得する。

この分離により、sensor acquisition rateとrobot loop rateを独立に管理できる。

---

## 13. Robot frame timestamp implementation

`examples/custom_sensor/record_with_timestamps.py` はLeRobot 0.6.0のrecord loopへ実行時patchを適用する。

記録field:

```text
loop_start_monotonic_ns
observation_start_monotonic_ns
observation_end_monotonic_ns
observation_end_wall_ns
action_sent_monotonic_ns
frame_added_monotonic_ns
```

本referenceでは `observation_end_monotonic_ns` を、observationがpolicy側で利用可能になった代表robot時刻として使用する。

LeRobot更新時は [05 Maintenance](05_maintenance.md) に従ってsource diffと実機再検証を行う。

---

## 14. Action保存semantics

**[CODE-VERIFIED]**

LeRobot 0.6.0のrecording loopでは、`robot.send_action()` の戻り値とは別にprocessed actionからDataset frameを構築する。

`max_relative_target` 等でcommandがrobot側でclipされる構成では、「Datasetへ記録されたaction」と「実際に送信されたaction」が一致しない可能性がある。

safety clippingを変更する場合はrecorded / sent action semanticsを再確認する。

---

## 15. Policy / VLAへの接続

収集時点ではcanonical rawを保持し、policy-specific representationを後処理で生成する。

### Current value

各robot frameに対してcausal latest sample/frameを使用する。

### History window

一定時間のraw sample群を1D CNN、MLP、Transformer等へ入力し、embeddingとしてpolicyへ融合する。

### Fast / slow構成

high-rate sensorをlocal controller / reflex側で処理し、summaryやstateのみを低rate policyへ渡す。

具体的なrepresentationはpolicy architectureとtask要件に合わせて決定する。

---

## 16. 新しいsensorを追加するときのchecklist

### Responsibility boundary

```text
[ ] sensor-specific layerの担当範囲を決めた
[ ] 本referenceへ渡すintegration boundaryを決めた
[ ] 既存driver / SDK / experiment codeを再利用できるか確認した
[ ] working driverを不要に置き換えていない
[ ] interface不一致時は必要最小限のadapterで接続する方針にした
```

### Entry checkpoint S0

```text
[ ] OS / driver / SDKからsensorを利用できる
[ ] streamを継続取得できる
[ ] interfaceを確認した
[ ] data shape / unitまたはmessage typeを確認した
[ ] ROS 2の場合はros2 topic typeで完全修飾message typeを取得した
[ ] actual rateを測定できる
```

S0を満たさない場合はALOHA integrationへ進まない。

### Interface contract

```text
[ ] Pattern A / B / C / Dを選択
[ ] 対象PatternのRequired項目を満たす
[ ] raw historyが必要か判断
[ ] source/device timestampの有無を確認
[ ] host timestampを付与する位置を決めた
[ ] clock semanticsを確認
[ ] software syncの精度で十分か判断
[ ] canonical raw formatを決定
```

### Acquisition

```text
[ ] reference側でsensor単体取得
[ ] ROS 2 loggerではrclpyとPython interpreterの互換性を確認
[ ] standard messageをsubscribeするだけならsensor-specific workspaceがsubscriber側に不要か確認
[ ] run ID / dataset path / sidecar pathを一貫させた
[ ] raw sample/frameを保存
[ ] timestampを保存
[ ] actual rateを記録
[ ] ALOHA timestamp付きrecording
[ ] concurrent acquisition
[ ] sensor/camera recording intervalがrobot recording interval全体を含む
[ ] ALOHA Dataset validation
```

### Alignment

```text
[ ] robot timestamp monotonic
[ ] sensor/camera timestamp monotonic
[ ] future sample/frame = 0
[ ] missing数を確認
[ ] age distributionを確認
[ ] historyを使う場合はwindow sample数を確認
```

### Documentation / handoff

```text
[ ] 本reference開始前に利用者が準備する内容を明記
[ ] integration boundaryのinput interfaceを明記
[ ] topic / message type / device format等を明記
[ ] actual rateの測定方法を明記
[ ] timestamp source / clockを明記
[ ] exact execution commandsを明記
[ ] 各checkpointのPASS条件を明記
[ ] failure時に戻る層を明記
[ ] validation resultを記録
[ ] 未検証範囲を記録
[ ] 配布するsensor-specific codeはprovenance / licenseを確認
```

新しいsensorを標準referenceへ追加する場合は、このchecklistを満たす実機結果を [06 Validation Results](06_validation_results.md) と同等の形式で記録する。
