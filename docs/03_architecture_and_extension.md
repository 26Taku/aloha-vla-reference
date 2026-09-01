# Architecture and Sensor Extension

## 1. この資料の役割

本資料は、**ALOHAへcamera・F/T・IMU・tactile sensor等を追加するときの設計・実装判断を行うための標準ガイド**である。

通常のALOHA setup、hardware identification、teleoperation、baseline recordingは [02 Data Collection](02_data_collection.md) を使用する。ここでは「新しいsensorを追加するとき、どの取得方式を選び、何を保存し、どこで同期し、何を検証するか」を扱う。

reference implementationの具体的な実行コマンドは [Custom Sensor Reference](../examples/custom_sensor/README.md)、実機検証の数値は [06 Validation Results](06_validation_results.md) に分離する。

確認状態:

- **[HW-VERIFIED]**: 実機で確認済み
- **[CODE-VERIFIED]**: source codeまたはoffline testで確認済み
- **[DESIGN]**: 推奨設計。対象条件での実機確認前
- **[NOT-VERIFIED]**: 明示的に未確認

## 2. Baseline data path

baselineはTrossen公式 `lerobot_trossen` とLeRobot 0.6.0を使用する。

```text
YAML configuration
      │
      ├───────────────┐
      ▼               ▼
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

**[CODE-VERIFIED]** Dataset schemaはRobotのaction / observation feature定義を基に構築される。Robot observationへfeatureを直接追加する場合は、feature定義と `get_observation()` のkey / shapeを一致させる必要がある。

baselineではRobot joint state/actionと4 RGB cameraをLeRobot標準recordingで保存する。外部sensorを追加するときも、このbaseline経路を不要に複雑化させないことを基本とする。

## 3. 最初に決めること: sensor integration decision guide

新しいsensorを追加する前に、次の順に判断する。

```text
新しいsensor
    │
    ├─ robot FPS程度で取得でき、
    │  各robot frameに1値 / 1frameあれば十分
    │       ↓
    │   A. LeRobot observationへ直接統合
    │
    ├─ robot FPSより高周期の数値時系列を保持したい
    │       ↓
    │   B. native-rate numeric sidecar
    │      + robot timestamp
    │      + causal alignment
    │
    ├─ camera / tactile cameraでrobot FPSと異なる
    │       ↓
    │   C. asynchronous camera stream
    │      + frame/packet timestamp
    │      + causal alignment
    │
    └─ exposure・sampleをsub-ms精度等で合わせる必要がある
            ↓
        D. hardware synchronization
           （本referenceのsoftware sync範囲外）
```

### A. LeRobotへ直接統合する

向いている条件:

- sensor rateがrobot/control rateと同程度
- raw high-rate waveformを保持する必要がない
- 1 robot frameに対して1つのsensor stateがあれば十分
- sensor取得がcontrol loopを大きくblockingしない

例: 低周期の状態量、robot driverが既に提供するstate、robot FPSに自然に合わせられるcamera。

### B. High-rate numeric sidecar

向いている条件:

- F/T、IMU等の時系列sensor
- 30 Hz等へdownsampleする前のraw dynamicsを残したい
- sensor driverがROS 2、serial、vendor SDK等として独立している

canonical rawはnative / actual rateで保存し、robot frameとの対応は後処理で作る。

### C. Asynchronous camera stream

向いている条件:

- GelSight等のtactile camera
- high-resolution camera
- advertised FPS / actual FPSがrobot recording FPSと異なる
- capture pathでdecode / re-encodeするとthroughputを落とす可能性がある

camera streamを独立保存し、frame/packet timestampを使ってrobot frameへ対応付ける。

### D. Hardware synchronization

次が必要ならsoftware timestampだけでは不十分な可能性がある。

- exposure instantそのものを揃える
- sub-millisecond級の同期
- 複数PC間で厳密なclock共有が必要
- sensor内部clockとrobot clockのoffsetを厳密に保証したい

この場合はhardware trigger、共有clock、PTP等を対象hardwareに合わせて別途設計する。

## 4. Sensor extensionで固定するdata contract

transportやvendor SDKを統一するのではなく、**保存する情報のcontractを統一する**。

外部sensor raw streamには可能な限り以下を保持する。

```text
sample/frame index
source/device timestamp        (availableなら)
host monotonic timestamp
raw data
sensor/config metadata
```

### 4.1 rawをcanonicalとする

収集時点でpolicy用表現へ不可逆に変換しない。

```text
raw acquisition
      ↓
canonical raw + timestamps
      ↓
derived synchronized view
      ↓
policy / training input
```

例えば100 HzのF/Tを30 Hzへ直接落として保存すると、後から200 ms history等を作れない。逆にrawを保持していれば、current value、history window、別FPSへのresamplingを後から生成できる。

### 4.2 acquisition rate / robot rate / policy rateを分離する

以下を同一と仮定しない。

```text
sensor acquisition rate
robot/control rate
policy inference rate
```

sensor acquisitionはdeviceが安定して取得できるnative / actual rateを優先する。robotやpolicyへ渡すrateはderived representation側で決める。

### 4.3 timestampのclock domainを明示する

source/device timestampとhost `CLOCK_MONOTONIC` は同じclockとは限らない。

本referenceでは、同一hostでのsoftware alignmentに **host monotonic timestamp** を使用する。device timestampが得られる場合も捨てずに保存するが、clock semanticsを確認せずhost timestampと直接差分を取らない。

## 5. Robot frameの実timestamp

通常のLeRobotDataset timestampはtarget FPSに基づくlogical frame timeとして扱われるため、外部sensorの実受信時刻とのalignmentには別の実clockを使用する。

`examples/custom_sensor/record_with_timestamps.py` はLeRobot 0.6.0のrecord loopへ実行時patchを適用し、robot frameごとにhost monotonic timestampをsidecarへ保存する。インストール済みLeRobot sourceは変更しない。

主なfield:

```text
loop_start_monotonic_ns
observation_start_monotonic_ns
observation_end_monotonic_ns
observation_end_wall_ns
action_sent_monotonic_ns
frame_added_monotonic_ns
```

本referenceでは `observation_end_monotonic_ns` を、observationがpolicy側で利用可能になった代表robot時刻として使用する。

**[HW-VERIFIED]** timestamp sidecarと通常のLeRobotDataset recordingが併存することを確認した。

このreferenceはLeRobot 0.6.0のrecording implementationに依存する。LeRobot更新時は [05 Maintenance](05_maintenance.md) に従ってsource diffと実機再検証を行う。

## 6. Pattern A: LeRobot observationへ直接統合する

**[DESIGN]**

### 6.1 実装対象

直接統合する場合は、少なくとも次を揃える。

1. sensorのconnect / disconnect lifecycle
2. observation featureのkey / shape / dtype
3. `get_observation()` が返す実データ
4. Dataset schemaへの反映
5. validatorの期待schema
6. robot/control loop rateへの影響

Robot observationへ新しいkeyを追加する場合、feature定義だけを増やして実データを返さない、あるいは逆に `get_observation()` だけを変更してschemaを更新しない、といった片側変更を避ける。

### 6.2 直接統合を選ばない方がよい例

次のsensorを無理に30 Hz robot loopへ合わせることは標準としない。

- 100 Hz以上のF/T / IMU等でraw waveformを残したい
- camera FPSがrobot FPSと一致しない
- sensor callback / decodeがblockingしてrobot loopを遅くする
- 将来別policy rateで利用する可能性が高い

これらはPattern BまたはCを使用する。

## 7. Pattern B: High-rate numeric / time-series sensor

**[HW-VERIFIED]**

F/T、IMU等はraw waveformをnative / actual rateで別streamとして保存する。

```text
High-rate sensor
      │
      ├─> raw JSONL
      │     sample index
      │     source timestamp (if available)
      │     host receive monotonic timestamp
      │     raw values
      │
Robot │
      └─> LeRobotDataset + robot monotonic timestamps
                  │
                  ▼
          causal alignment
             ├─ latest value
             └─ history window
```

### 7.1 Acquisition adapter

`ros2_timeseries_logger.py` はgeneric ROS 2 numeric messageをflattenし、callback entryでhost monotonic timestampを付けるreferenceである。

ROS 2自体をbaseline dependencyとはしない。対象sensorがvendor SDKやserial APIで提供される場合も、同じdata contractを満たすadapterへ置き換えればよい。

publisherの `header.stamp` はsource timestampとして保持できるが、clock semanticsを確認できない限りhost monotonicとの直接比較には使用しない。

### 7.2 Current-value view

`align_timeseries.py` は各robot frameに対して、

```text
sensor_time <= robot_observation_time
```

を満たす最新sampleを選択する。

これによりfuture sampleを使用しないcausal viewを生成する。

### 7.3 History-window view

`build_sensor_windows.py` はrobot frame時刻 `t` に対して `(t-W, t]` のsample範囲を生成する。

raw valuesをrobot frameごとに複製せず、必要なsample index / timestamp範囲をmanifestとして保持する。

### 7.4 検証項目

新しいnumeric sensorで最低限確認する。

```text
[ ] native / actual acquisition rateを実測
[ ] sample indexが連続
[ ] host monotonic timestampが単調増加
[ ] robot recordingと同時取得できる
[ ] alignmentでfuture sample used = 0
[ ] missing frame数を確認
[ ] sensor age distributionを確認
[ ] history windowのsample数を確認
```

**[HW-VERIFIED]** 高周期ROS 2 numeric streamを用いてnative-rate acquisition、ALOHAとのconcurrent recording、latest-value alignment、history-window generationまで確認した。実測値は [06 Validation Results](06_validation_results.md) を参照する。

## 8. Pattern C: Asynchronous camera / tactile camera

**[HW-VERIFIED]**

GelSight等、実効camera rateがrobot FPSと異なるcameraはnative streamを独立取得する。

検証したreference path:

```text
V4L2 MJPEG
   ↓
FFmpeg stream copy
   ↓  timestamp保持 / no decode-re-encode
MKV + packet PTS
   ↓
causal latest-frame mapping
   ↓
robot frames
```

`extract_mkv_timestamps.py` はMKV packet PTSをJSONLへexportする。`align_camera_frames.py` は各robot observation以前で最も新しいcamera frameを対応付ける。

### 8.1 Capture方式

raw acquisition中に不要なdecode、resize、JPEG再encode、per-frame file outputを入れるとthroughputが低下する場合がある。

GelSight Miniの方式比較では、full-resolution decode / JPEG再encode経路よりV4L2 MJPEGのnative compressed stream copyの方が高い実効rateを得た。このためcamera referenceにはFFmpeg stream copyを採用する。

この比較はreference実装の方式選定であり、研究室既存GelSight codeやGelSight公式softwareのbenchmarkではない。

### 8.2 Causal alignment

robot frame時刻以前で最も新しいcamera frameを選ぶ。

robot FPSの方がcamera FPSより高い場合、同じcamera frameが複数robot frameへ割り当てられることは正常である。raw imageをrobot frameごとに複製せず、mappingだけをderived dataとして保持する。

### 8.3 検証項目

```text
[ ] device / physical sensor mappingを確認
[ ] advertised format / resolution / FPSを確認
[ ] actual capture rateを実測
[ ] frame/packet timestampのclock domainを確認
[ ] robot recordingと同時取得できる
[ ] alignmentでfuture frame used = 0
[ ] missing / reused assignment数を確認
[ ] camera age distributionを確認
```

**[HW-VERIFIED]** GelSight Mini 1台でnative compressed acquisition、packet timestamp保持、ALOHAとのconcurrent recording、causal latest-frame alignmentまで確認した。実測値は [06 Validation Results](06_validation_results.md) を参照する。

## 9. ROS 2の位置づけ

ROS 2を外部sensorの標準transportとして固定しない。

```text
Sensor-specific acquisition
   ├─ ROS 2
   ├─ V4L2
   ├─ serial / USB API
   └─ vendor SDK
          │
          ▼
raw data + timestamps + metadata
          │
          ▼
derived causal view
```

ROS 2は、既存driverがROS 2で提供される、複数nodeと連携する、topic/QoS管理が有用、といった場合のadapterである。

重要なのはtransportではなく、Section 4のdata contractとtimestamp semanticsを維持することである。

## 10. Policy / VLAへの接続境界

収集時点ではraw dataを保持し、policy-specific representationは後から生成する。

代表的な接続方法:

### Current value

robot frameごとにcausal latest sample/frameを使用する。

低周期stateや、瞬時値で十分なsensorに向く。

### History window

一定時間のraw sample群を1D CNN、MLP、Transformer等の時系列encoderへ入力し、embeddingとしてproprioception / vision-language featureへ融合する。

高周期F/Tや触覚dynamicsを利用したい場合に向く。

### Fast / slow構成

高周期sensorをlocal controller / reflex側で処理し、summaryやstateのみを低速VLAへ渡す。

VLA inference rateより速い反応が必要なtaskに向く。

どの表現を採るかはpolicy architectureに依存するため、raw acquisition formatで固定しない。

## 11. Software syncとhardware syncの境界

本referenceで実機確認したsensor synchronizationは、同一hostのmonotonic clockを基準とするsoftware-level alignmentである。

保証しないもの:

- camera exposure instantの一致
- sensor内部clockとhost clockの厳密なoffset
- sub-millisecond synchronization
- 複数PC間clock synchronization

これらが必要なtaskではhardware trigger、共有clock、PTP等を別途設計する。

## 12. Action保存semantics

**[CODE-VERIFIED]** LeRobot 0.6.0のrecording loopでは、`robot.send_action()` の戻り値とは別にprocessed actionからDataset frameを構築する。

`max_relative_target` 等でcommandがrobot側でclipされる構成では、「Datasetへ記録されたaction」と「実際に送信されたaction」が一致しない可能性がある。

safety clippingを変更する場合はrecorded/sent action semanticsを再確認する。

## 13. Reference implementationとprovenance

本repositoryの外部sensor referenceは、sensor固有のacquisition codeを共通の取得・timestamp・alignment境界へ接続する構成とする。

GelSightについて確認したprovenance:

- GelSight Inc.公式 `gelsightinc/gsrobotics`: GelSight Mini用OpenCV based SDK / demo
- 研究室側helper: 公式構造をベースにproject-specific変更が加わったもの
- 研究室側ROS 2 publisher: 確認したfileだけから元repositoryまでは特定できなかったproject-specific wrapper
- 本repositoryのcamera reference: V4L2/FFmpeg + timestamp alignmentとして独立実装

本repositoryへvendor / upstream sourceをコピーする場合はlicenseと出典を別途確認する。

- GelSight official repository: https://github.com/gelsightinc/gsrobotics

## 14. 新しいsensorを追加するときのchecklist

### 設計前

```text
[ ] sensorのphysical quantity / data shapeを確認
[ ] native / advertised rateを確認
[ ] actual rateを実測する方法を決める
[ ] interface / driverを確認
[ ] source timestampの有無とclock semanticsを確認
[ ] robot frameごとの瞬時値で十分か、raw historyが必要か決める
[ ] software syncで十分か判断する
```

### 実装

```text
[ ] Pattern A / B / C / Dを選択
[ ] machine-specific identifierをtracked fileへ固定しない
[ ] raw dataとtimestampを保存
[ ] robot timestampとの対応方法を実装
[ ] derived viewをrawと分離
```

### 検証

```text
[ ] robot単体recordingが壊れていない
[ ] sensor単体acquisitionが安定
[ ] concurrent acquisitionが安定
[ ] actual rateを測定
[ ] timestamp monotonicityを確認
[ ] causal alignmentでfuture sample/frame = 0
[ ] missing / age / reuse等の統計を確認
[ ] Dataset schemaを変更した場合はvalidatorも更新
```

実測結果はproject-specific logまたは [06 Validation Results](06_validation_results.md) と同等の形式で残す。

## 15. まとめ

標準化するのは特定transportや特定sensor名ではなく、次の境界である。

```text
raw acquisition rate != robot rate != policy rate

raw data + real timestamps        -> canonical
policy-specific synchronized view -> derived
```

baseline RGB / robot dataはLeRobot標準recordingを利用し、rate、latency、interface、timestamp特性が異なるsensorだけを適切な独立経路へ分離する。
