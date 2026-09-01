# Validation Results

## 1. この資料の役割

本資料は、**本referenceで実際に実機・workstation上で確認した結果の証跡**を記録する。

操作手順は [02 Data Collection](02_data_collection.md)、sensor extensionの実行・設計手順は [03 Architecture and Sensor Extension](03_architecture_and_extension.md) を正とする。本資料では手順を重複させず、検証条件、結果、未検証範囲を記録する。

---

## 2. Reference environment

検証workstation:

```text
OS: Ubuntu 24.04.4 LTS
CPU: Intel Xeon w9-3575X
RAM: 約503 GiB
GPU: NVIDIA RTX PRO 6000 96GB x4
```

Data collection validationではheavy GPU workloadを必要としない。

Software baseline:

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
Trossen Arm 1.10.0
LeRobotDataset v3.0
```

2026-09-01のfinal sensor validationはreference repositoryのshort revision `5a30533` を基点として実施した。その後のdocument-only revisionでは実機scriptの動作条件を変更しない。

Machine-specific Arm IP、camera serial、USB serial、`/dev/.../by-id` 等の個体識別値は公開referenceへ記録しない。

---

## 3. Baseline ALOHA validation

### 3.1 Clean environment / dependency setup

**[HW-VERIFIED]**

既存研究forkとは別directoryへTrossen公式repositoryをcloneし、固定commitでdependency installationを完了した。

### 3.2 Hardware preflight

**[HW-VERIFIED]**

```text
follower arms       2
leader arms         2
RealSense D405      4
hardware mapping    confirmed
storage check       PASS
```

Machine-specific identityはGit管理外の`config/hardware-local.yaml`へ一度だけ設定し、tracked operational templateからruntime configを生成する構成で確認した。

### 3.3 Teleoperation

**[HW-VERIFIED]**

Bimanual leader-follower teleoperation、左右gripper、4 camera viewを確認した。通常動作時のcontrol loopは概ね30 Hzだった。

起動直後はLeaderが操作可能になってからFollower追従開始まで短い時間差が生じる場合があった。追従開始前にLeaderを大きく移動するとFollowerがpose gapを急に解消しようとしてjoint velocity limitで停止する試行があったため、起動直後はLeaderを保持し、小さなmotionへFollowerが連続追従することを確認してから通常操作へ移る手順を採用した。

### 3.4 Baseline recording

**[HW-VERIFIED]**

15秒・1 episode:

```text
Dataset format        LeRobotDataset v3.0
frames                449
action                14D
observation.state     14D
camera streams        4
camera video          424x240 / 30 fps
validator             PASS
```

`record.sh`による10秒・1 episode smoke testでも299 frames / validator PASSを確認した。

### 3.5 Configuration-unified end-to-end acceptance — 2026-09-01

**[HW-VERIFIED]**

```text
hardware-local config
-> check_hardware
-> teleoperation
-> recording
-> dataset validation
```

上記を実機で通し、baseline data collection pathを完了した。

---

## 4. High-rate numeric sensor validation — 2026-09-01

MMS101由来のROS 2 streamをPattern Bのtest caseとして使用した。sensor-specific driverの性能、force ground truth、取付精度を評価する試験ではなく、**既存numeric streamをALOHA recordingへ接続するinterface / timestamp / alignment path**を検証した。

### 4.1 Interface boundary

**[HW-VERIFIED]**

```text
topic         /force_torque/left
message type  geometry_msgs/msg/WrenchStamped
payload       6-axis force / torque
```

MMS101 driverを別processで起動した状態で、環境を継承しないclean shellからROS 2 Jazzyのみをsourceし、topic type / echoとgeneric loggerを実行できた。clean-shell loggerは3秒で298 samplesを保存した。

この結果から、subscriber側はMMS101固有workspaceをsourceせず、標準message interfaceから後段referenceへ接続できることを確認した。

### 4.2 Standalone acquisition

**[HW-VERIFIED]**

```text
samples              1002 / 10 s
actual rate          約100 Hz
raw format           JSONL
alignment clock      receive_monotonic_ns
```

rateは検証driver / configurationでの実測値であり、MMS101一般の固定仕様として扱わない。

### 4.3 Final concurrent validation

**[HW-VERIFIED]**

Sensor loggerを60秒で先に開始し、その取得区間内で10秒のALOHA episodeを収録した。

ALOHA:

```text
frames                299
target fps            30
action                14D
observation.state     14D
camera streams        4
timestamp sidecar     299 records
validator             PASS
```

Sensor sidecar:

```text
samples               6002 / 60 s
actual rate           約100 Hz
```

### 4.4 Causal latest-sample alignment

**[HW-VERIFIED]**

```text
robot frames          299
sensor samples        6002
aligned frames        299
missing frames        0
future samples used   0
malformed records     0
sensor age median     7.727 ms
sensor age p95        15.029 ms
sensor age max        16.809 ms
validator             PASS
```

### 4.5 200 ms history window

**[HW-VERIFIED]**

```text
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

Pattern Bのsoftware-level integration validationは完了した。

---

## 5. Asynchronous camera validation — 2026-09-01

GelSight Mini 1台をPattern Cのtest caseとして使用した。触覚task性能やGelSight固有画像処理を評価する試験ではなく、**robot FPSと異なるnative camera streamを保存し、host timestampでALOHAへcausal alignmentするpath**を検証した。

### 5.1 V4L2 mode

**[HW-VERIFIED]**

Current validation hostでは2つのcandidate video nodeで同じmodeを確認し、1台validationには`/dev/video6`を使用した。

```text
pixel format          MJPG / MJPEG
resolution            3280x2464
advertised fps        25
```

Device nodeはUSB enumeration等で変化し得るため、別hostでは固定値を流用せず再確認する。

### 5.2 Standalone native capture

**[HW-VERIFIED]**

FFmpeg stream copyで10秒captureを実行した。

```text
video frames          188
effective rate        18.754 Hz
codec                 mjpeg
resolution            3280x2464
first-frame decode    PASS
timestamp export      PASS
packet timestamps     monotonic
```

Capture開始時に`EOI missing, emulating`が1回表示されたが、MKV保存、decode smoke、timestamp exportまで正常に完了した。

### 5.3 Final concurrent validation

**[HW-VERIFIED]**

ALOHA:

```text
frames                299
Dataset               v3.0
action/state          14D / 14D
4 RGB videos          PASS
validator             PASS
```

GelSight:

```text
frames                750 / 約40 s
effective rate        18.728 Hz
```

Causal alignment:

```text
robot frames          299
aligned frames        299
missing frames        0
future frames used    0
reused assignments    111
camera age median     26.461 ms
camera age p95        50.617 ms
camera age max        53.083 ms
alignment             PASS
```

Robot 30 Hzに対してcamera actual rateが約18.7 Hzであるため、同一camera frameが複数robot frameへ割り当てられる`reused assignments`は想定内である。

Pattern Cのsoftware-level integration validationは完了した。

---

## 6. Verification limits

本referenceの実機validationでは以下を保証しない。

- GelSight 2台同時使用時のUSB / CPU / storage capacity
- GelSightをgripperへ取り付けた状態での触覚task性能
- MMS101 force値のground truth / calibration accuracy
- sensor-specific driverの他hardware / firmware / OSでの互換性
- hardware-trigger level synchronization
- sub-millisecond synchronization
- 複数PC間clock synchronization
- VLA training / inference performance

Sensor synchronizationは同一hostのmonotonic clockを基準とするsoftware-level alignmentである。より厳密な同期が必要なtaskではhardware trigger、共有clock、PTP等を別途設計する。

---

## 7. Delivery acceptance status

実機を必要とするvalidationは完了している。

```text
Baseline ALOHA path                 PASS
Pattern B high-rate numeric         PASS
Pattern C asynchronous camera       PASS
MMS101 hardware needed further      NO
GelSight hardware needed further    NO
```

Final document revision適用後は、hardwareを再使用せず、最終repository commitに対して以下のrelease checkを行う。

```text
[ ] git diff --check
[ ] Markdown relative link check
[ ] machine-specific identifier scan
[ ] personal/staging repository URL scan
[ ] generated/runtime/data artifact exclusion check
[ ] fresh clone / setup static path check
[ ] final commitを記録
```

最終commit hashは上記release check完了後に本sectionへ追記する。操作手順そのものは [02 Data Collection](02_data_collection.md) を正とする。
