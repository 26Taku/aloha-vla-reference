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

| 条件 | 使用する方式 |
|---|---|
| robot FPS程度で取得でき、各robot frameに1値/1frameあれば十分 | **Pattern A: LeRobot observationへ直接統合** |
| F/T・IMU等の高周期numeric streamをraw waveformのまま残したい | **Pattern B: native-rate numeric sidecar** |
| tactile camera等、robot FPSと異なるcamera streamを残したい | **Pattern C: asynchronous camera sidecar** |
| sub-ms同期、同時exposure、複数host間の厳密同期が必要 | **Pattern D: hardware synchronization** |

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

### 5.1 前提確認

repository rootで:

```bash
./check_hardware.sh
```

`[READY]` を確認する。

通常のteleoperationと1 episode recordingが未確認の場合は、先に [02 Data Collection](02_data_collection.md) を完了する。

### 5.2 timestamp付きrecording configを生成

例として10秒・1 episodeの `sensor_timestamp_smoke` を作る。

```bash
mkdir -p .runtime data

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output ../.runtime/sensor-timestamp-smoke.yaml \
    --dataset-name sensor_timestamp_smoke \
    --task "Sensor timestamp smoke test" \
    --num-episodes 1 \
    --episode-time-s 10 \
    --dataset-root ../data/sensor_timestamp_smoke
)
```

同名Datasetが既にある場合は別名を使用する。

### 5.3 timestamp付きrecordingを実行

```bash
(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path=../.runtime/sensor-timestamp-smoke.yaml
)
```

通常のLeRobotDatasetに加えて次が生成される。

```text
data/sensor_timestamp_smoke/
└── meta/
    └── frame_timestamps/
        ├── episode_000000.jsonl
        └── episode_000000.meta.json
```

代表robot時刻は:

```text
observation_end_monotonic_ns
```

である。

### 5.4 Datasetを検証

```bash
./validate_dataset.sh data/sensor_timestamp_smoke
```

`[PASS]` を確認する。

### 5.5 timestamp sidecarを確認

```bash
head -n 2 \
  data/sensor_timestamp_smoke/meta/frame_timestamps/episode_000000.jsonl
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

この節は、**sensor-specific driver / SDKの起動そのものではなく、Section 4.1のnumeric contractを満たしたstreamをALOHAへ接続するところから**扱う。

本repositoryはROS 2 numeric topic用のgeneric loggerをreference pathとして提供する。

### 6.1 Checkpoint B0: numeric stream ready

ROS 2 streamを使用する場合、driverを起動したshell環境で次を確認する。

```bash
ros2 topic list
ros2 topic type <SENSOR_TOPIC>
ros2 topic echo <SENSOR_TOPIC> --once
ros2 topic hz <SENSOR_TOPIC>
```

記録する項目:

```text
topic:
message type:
actual rate:
source timestamp:
```

Pass criteria:

```text
[ ] <SENSOR_TOPIC> が存在する
[ ] message typeを取得できる
[ ] 1 message以上を受信できる
[ ] ros2 topic hz が継続してsampleを観測する
[ ] payloadに必要なnumeric valueが含まれる
```

B0を満たさない場合はSection 6.2以降へ進まない。sensor-specific driver / SDK / hardware設定、または既存実験環境の起動手順を確認する。本reference側でtopic名やdevice固有設定を推測して進めない。

既存streamがROS 2ではない場合は、Section 4.1を満たすadapterを用意してから次へ進む。

### 6.2 Logger単体test

repository rootで、ROS 2 environmentをsourceしたshellから実行する。

```bash
mkdir -p data/_sensor_runs/numeric_smoke

python3 examples/custom_sensor/ros2_timeseries_logger.py \
  --topic <SENSOR_TOPIC> \
  --msg-type <MESSAGE_TYPE> \
  --sensor-id numeric_smoke \
  --output data/_sensor_runs/numeric_smoke/raw.jsonl \
  --duration 10
```

終了後:

```bash
wc -l data/_sensor_runs/numeric_smoke/raw.jsonl
head -n 1 data/_sensor_runs/numeric_smoke/raw.jsonl
cat data/_sensor_runs/numeric_smoke/raw.jsonl.meta.json
```

確認するfield:

```text
sample_index
source_timestamp_ns
receive_monotonic_ns
values
```

`receive_monotonic_ns` がhost側alignment用timestampである。`source_timestamp_ns` はmessageに有効な `header.stamp` がある場合に保存される。

### Checkpoint B1

```text
[ ] loggerがerrorなく終了
[ ] raw.jsonlが0行ではない
[ ] sample_indexが保存される
[ ] receive_monotonic_nsが保存される
[ ] receive_monotonic_nsが単調増加する
[ ] valuesが空ではない
[ ] ros2 topic hzでactual rateを確認した
```

`values` が空の場合、message payloadがgeneric numeric flatteningの対象外である。driver本体を書き換える前に、message変換用の薄いROS 2 adapterを追加することを検討する。

### 6.3 ALOHAと同時取得する

新しいDataset名を使用する。以下では `sensor_numeric_smoke` とする。

まずruntime configを生成する。

```bash
mkdir -p .runtime data/_sensor_runs/sensor_numeric_smoke

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output ../.runtime/sensor-numeric-smoke.yaml \
    --dataset-name sensor_numeric_smoke \
    --task "High-rate numeric sensor smoke test" \
    --num-episodes 1 \
    --episode-time-s 10 \
    --dataset-root ../data/sensor_numeric_smoke
)
```

#### Terminal A: sensor-specific acquisition

B0を通過したsensor driver / SDK / adapterを継続起動する。

#### Terminal B: raw sensor logger

robot recordingより先に開始し、robot recordingより長いdurationを指定する。

```bash
python3 examples/custom_sensor/ros2_timeseries_logger.py \
  --topic <SENSOR_TOPIC> \
  --msg-type <MESSAGE_TYPE> \
  --sensor-id <SENSOR_ID> \
  --output data/_sensor_runs/sensor_numeric_smoke/raw.jsonl \
  --duration 30
```

loggerがsampleを受信している状態で次へ進む。

#### Terminal C: timestamp付きALOHA recording

```bash
(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path=../.runtime/sensor-numeric-smoke.yaml
)
```

recording後:

```bash
./validate_dataset.sh data/sensor_numeric_smoke
```

`[PASS]` を確認する。

### 6.4 Current-value alignment

```bash
python3 examples/custom_sensor/align_timeseries.py \
  --robot-frames \
    data/sensor_numeric_smoke/meta/frame_timestamps/episode_000000.jsonl \
  --sensor \
    data/_sensor_runs/sensor_numeric_smoke/raw.jsonl \
  --output \
    data/_sensor_runs/sensor_numeric_smoke/aligned_latest.jsonl
```

出力例:

```text
robot frames
sensor samples
aligned frames
missing frames
future samples used
sensor age median
sensor age p95
sensor age max
```

続けて構造を検証する。

```bash
python3 examples/custom_sensor/validate_alignment.py \
  data/_sensor_runs/sensor_numeric_smoke/aligned_latest.jsonl \
  --require-complete
```

期待値:

```text
future samples used : 0
malformed records   : 0
[PASS]
```

`missing frames` はsensor logger開始時刻、rate、drop、`--max-age-ms` 条件に依存する。`--require-complete`を使用したsmoke testでは0を完了条件とする。

### 6.5 History-window view

200 msのhistoryを作る例:

```bash
python3 examples/custom_sensor/build_sensor_windows.py \
  --robot-frames \
    data/sensor_numeric_smoke/meta/frame_timestamps/episode_000000.jsonl \
  --sensor \
    data/_sensor_runs/sensor_numeric_smoke/raw.jsonl \
  --output \
    data/_sensor_runs/sensor_numeric_smoke/windows_200ms.jsonl \
  --window-ms 200
```

確認する値:

```text
ok frames
insufficient frames
future samples used
samples/window median
p05 / p95
min / max
```

### Checkpoint B2: integration complete

```text
[ ] ALOHA Dataset validator -> PASS
[ ] sensor raw streamをrobot recordingより前から取得
[ ] robot timestamp sidecarが存在
[ ] aligned frames = robot frames
[ ] missing frames = 0
[ ] future samples used = 0
[ ] validation -> PASS
[ ] history windowでfuture samples used = 0
[ ] actual sensor rate / sensor ageを記録
```

ここまででhigh-rate numeric sensorのsoftware-level integration確認を完了とする。

---

## 7. Validated example: MMS101

**[HW-VERIFIED]**

MMS101をPattern Bの具体例として実機確認した。

### 7.1 Driver / provenanceの扱い

検証では研究室内で使用されているROS 2 driverを利用した。このdriverは複数の開発・修正履歴を含むため、**sensor-specific driver sourceは本referenceの配布物に含めない**。

本referenceがMMS101について要求する開始条件は、driverの種類やlaunch file名ではなく次のinterfaceである。

```text
transport       ROS 2 topic
payload         numeric 6-axis force / torque
verified type   geometry_msgs/msg/WrenchStamped
rate            固定値を仮定せず実測
```

MMS101の接続、serial device設定、driver build、sensor initialization、calibration等はsensor-specific layerとして利用者側で準備する。既に別実験で使用しているdriverがある場合は、その環境を優先して再利用する。

### 7.2 Section 6へのhandoff

MMS101 driverを起動した後、topic名を確認する。

```bash
ros2 topic list
```

使用するtopicを1つ選び、以下を確認する。

```bash
SENSOR_TOPIC=<MMS101_TOPIC>

ros2 topic type "$SENSOR_TOPIC"
ros2 topic echo "$SENSOR_TOPIC" --once
ros2 topic hz "$SENSOR_TOPIC"
```

`geometry_msgs/msg/WrenchStamped` がpublishされている場合、そのままgeneric loggerへ接続できる。

```bash
mkdir -p data/_sensor_runs/mms101_smoke

python3 examples/custom_sensor/ros2_timeseries_logger.py \
  --topic "$SENSOR_TOPIC" \
  --msg-type geometry_msgs/msg/WrenchStamped \
  --sensor-id mms101_smoke \
  --output data/_sensor_runs/mms101_smoke/raw.jsonl \
  --duration 10
```

この単体loggerがCheckpoint B1を通過した後、Section 6.3--6.5をそのまま実行する。

MMS101を左右2台使用する場合も、integration contractは同じである。必要なstreamごとにlogger processを起動し、個体・取付位置のsemantic mappingは対象実験側のconfigurationとして管理する。

### 7.3 Verified scope

過去のreference validationでは、MMS101由来のROS 2 numeric streamについて次を確認している。

```text
native-rate acquisition
ALOHA concurrent recording
robot/sensor causal latest-value alignment
future sample = 0
200 ms history-window generation
```

actual rateはdriver / configuration / host条件に依存するため、MMS101の固定仕様値として扱わない。各環境で `ros2 topic hz` と保存sample数から実測する。

実測値は [06 Validation Results](06_validation_results.md) を参照する。

---

## 8. Pattern C: Asynchronous cameraを追加する

対象例:

- tactile camera
- high-resolution USB camera
- robot recording FPSと異なるcamera
- native compressed streamを保持したいcamera

この節は、**camera固有SDKや画像処理pipelineの構築ではなく、Section 4.2のcamera contractを満たしたstreamをALOHAへ接続するところから**扱う。

本referenceではLinux V4L2で認識されるcameraを直接取得するpathを提供する。

### 8.1 Checkpoint C0: camera stream ready

必要commandを確認する。

```bash
v4l2-ctl --version
ffmpeg -version
ffprobe -version
```

対象cameraを列挙する。

```bash
v4l2-ctl --list-devices
```

stable pathがある場合:

```bash
ls -l /dev/v4l/by-id/
```

candidate deviceのformatを確認する。

```bash
v4l2-ctl \
  --device <VIDEO_DEVICE> \
  --list-formats-ext
```

記録する。

```text
device:
pixel format:
resolution:
advertised FPS:
```

Pass criteria:

```text
[ ] target cameraを一意に選べる
[ ] 使用するvideo nodeを決められる
[ ] pixel format / resolution / advertised FPSを確認できる
[ ] 継続captureに使用できるformatが存在する
```

C0を満たさない場合はSection 8.2以降へ進まない。camera固有のdriver / vendor setup / USB connection等を確認し、OSからstreamを取得可能にしてから戻る。

V4L2を使用できずvendor SDKやROS 2 image topicのみ利用できる場合は、Section 4.2を満たすacquisition adapterを用意する。以下のFFmpeg pathをそのまま使用したとは記録しない。

### 8.2 Camera単体capture

native compressed formatとしてMJPEG等が利用できる場合、Pattern Cではcompressed stream copyを使用できる。

```bash
mkdir -p data/_sensor_runs/camera_smoke

DEVICE=<VIDEO_DEVICE>
OUT=data/_sensor_runs/camera_smoke/raw.mkv

ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size <WIDTH>x<HEIGHT> \
  -framerate <ADVERTISED_FPS> \
  -timestamps default \
  -t 10 \
  -i "$DEVICE" \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  "$OUT"
```

使用するpixel format / resolution / FPSはCheckpoint C0で対象cameraについて確認した値へ置き換える。

出力を確認する。

```bash
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,avg_frame_rate \
  -of default=noprint_wrappers=1 \
  "$OUT"
```

### 8.3 Packet timestampをexport

```bash
python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  data/_sensor_runs/camera_smoke/raw.mkv \
  --output data/_sensor_runs/camera_smoke/timestamps.jsonl
```

scriptはframe数とeffective rateを表示する。

### Checkpoint C1

```text
[ ] MKV captureが完了
[ ] ffprobeでvideoを読める
[ ] packet timestampが単調増加
[ ] effective rateを記録
[ ] advertised FPSとactual rateを区別した
```

### 8.4 ALOHAと同時取得

新しいDataset名を使用する。以下では `sensor_camera_smoke` とする。

```bash
mkdir -p .runtime data/_sensor_runs/sensor_camera_smoke

(
  cd lerobot_trossen

  uv run python ../scripts/build_runtime_config.py \
    --template ../config/record-template.yaml \
    --hardware ../config/hardware-local.yaml \
    --output ../.runtime/sensor-camera-smoke.yaml \
    --dataset-name sensor_camera_smoke \
    --task "Asynchronous camera smoke test" \
    --num-episodes 1 \
    --episode-time-s 10 \
    --dataset-root ../data/sensor_camera_smoke
)
```

#### Terminal A: asynchronous camera

robot recordingより先に開始し、長めのdurationを指定する。

```bash
DEVICE=<VIDEO_DEVICE>
OUT=data/_sensor_runs/sensor_camera_smoke/raw.mkv

ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size <WIDTH>x<HEIGHT> \
  -framerate <ADVERTISED_FPS> \
  -timestamps default \
  -t 30 \
  -i "$DEVICE" \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  "$OUT"
```

camera captureが開始してからTerminal Bへ進む。

#### Terminal B: timestamp付きALOHA recording

```bash
(
  cd lerobot_trossen

  uv run python ../examples/custom_sensor/record_with_timestamps.py \
    --config_path=../.runtime/sensor-camera-smoke.yaml
)
```

recording後:

```bash
./validate_dataset.sh data/sensor_camera_smoke
```

### 8.5 Camera timestampsをexport

```bash
python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  data/_sensor_runs/sensor_camera_smoke/raw.mkv \
  --output data/_sensor_runs/sensor_camera_smoke/timestamps.jsonl
```

### 8.6 Causal alignment

```bash
python3 examples/custom_sensor/camera/align_camera_frames.py \
  --robot-frames \
    data/sensor_camera_smoke/meta/frame_timestamps/episode_000000.jsonl \
  --camera-timestamps \
    data/_sensor_runs/sensor_camera_smoke/timestamps.jsonl \
  --output \
    data/_sensor_runs/sensor_camera_smoke/aligned_latest.jsonl
```

確認する値:

```text
robot frames
camera frames
aligned frames
missing frames
future frames used
reused assignments
camera age median
camera age p95
camera age max
```

robot FPSがcamera actual rateより高い場合、同じcamera frameが複数robot frameへ割り当てられることは正常である。

### Checkpoint C2: integration complete

```text
[ ] ALOHA Dataset validator -> PASS
[ ] camera captureをrobot recordingより前から開始
[ ] packet timestamp export -> PASS
[ ] aligned frames = robot frames
[ ] missing frames = 0
[ ] future frames used = 0
[ ] actual camera rateを記録
[ ] camera age distributionを記録
```

ここまででasynchronous cameraのsoftware-level integration確認を完了とする。

FFmpeg / V4L2 optionの詳細は [Asynchronous Camera Reference](../examples/custom_sensor/camera/README.md) を参照する。

---

## 9. Validated example: GelSight Mini

**[HW-VERIFIED]**

GelSight MiniをPattern Cのtest caseとして実機確認した。

### 9.1 Software / driverの扱い

GelSight固有のSDK、画像処理、marker tracking、calibration等はsensor-specific layerとして扱う。本referenceのPattern Cでは研究室固有のROS 2 wrapperを必須とせず、**GelSight MiniがLinux V4L2 cameraとして取得可能な状態**を開始点とした。

別環境でvendor softwareやROS 2 wrapperを利用している場合も、それを置き換える必要はない。V4L2 pathを利用できるならSection 8へ直接接続し、V4L2を利用しない場合はSection 4.2のcamera contractを満たすacquisition pathを用意する。

### 9.2 Device / mode確認

```bash
v4l2-ctl --list-devices
ls -l /dev/v4l/by-id/
```

GelSightに対応するvideo nodeを確認し、必ず対象環境でformatを再確認する。

```bash
v4l2-ctl \
  --device <GELSIGHT_VIDEO_DEVICE> \
  --list-formats-ext
```

過去の検証機で使用したmode:

```text
pixel format       MJPEG
resolution         3280x2464
advertised FPS     25
```

これは別個体・firmware・hostに対する固定設定ではない。

### 9.3 Capture example

上記modeが対象環境でも確認できた場合の例:

```bash
DEVICE=<GELSIGHT_VIDEO_DEVICE>
OUT=data/_sensor_runs/gelsight_smoke.mkv

ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size 3280x2464 \
  -framerate 25 \
  -timestamps default \
  -t 10 \
  -i "$DEVICE" \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  "$OUT"
```

packet timestampをexportする。

```bash
python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  data/_sensor_runs/gelsight_smoke.mkv \
  --output data/_sensor_runs/gelsight_smoke_timestamps.jsonl
```

過去のreference validationではactual rateは約18.7--18.8 Hzだった。advertised FPSをactual rateとして扱わず、各環境でtimestampから実測する。

ALOHAと同時取得する場合はSection 8.4--8.6をそのまま実行する。

### 9.4 Verified scope

GelSight Mini 1台について次を確認している。

```text
V4L2 native compressed acquisition
packet timestamp保持
ALOHA concurrent recording
causal latest-frame alignment
future frame = 0
```

2台同時capture時のUSB / CPU / storage capacityは未検証であり、必要な構成では別途capacity testを行う。

実測値は [06 Validation Results](06_validation_results.md) を参照する。

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
[ ] raw sample/frameを保存
[ ] timestampを保存
[ ] actual rateを記録
[ ] ALOHA timestamp付きrecording
[ ] concurrent acquisition
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
