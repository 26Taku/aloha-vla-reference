# Validation Results

## 1. この資料の役割

本資料は、**Phase 1で実際に実機・workstation上で確認した結果の証跡**を記録する。

操作手順は [02 Data Collection](02_data_collection.md)、設計理由は [01 Reference Stack](01_reference_stack.md) / [03 Architecture and Extension](03_architecture_and_extension.md) に分離する。

## 2. Reference environment

検証workstation:

```text
OS: Ubuntu 24.04.4 LTS
CPU: Intel Xeon w9-3575X
RAM: 約503 GiB
GPU: NVIDIA RTX PRO 6000 96GB x4
```

GPU 0は他用途で使用中だったため、Phase 1 data collection validationではheavy GPU workloadを避けた。

Software:

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
Trossen Arm 1.10.0
```

Machine-specific Arm IP、camera serial、USB serial等は公開referenceへ記録しない。

## 3. Baseline ALOHA validation — 2026-08-27

### Clean environment setup

**[HW-VERIFIED]**

既存研究forkとは別directoryへTrossen公式repositoryをcloneし、固定commitで `uv sync --frozen` が完了した。

### Hardware preflight

**[HW-VERIFIED]**

- follower arms x2
- leader arms x2
- Intel RealSense D405 x4
- configured camera physical mapping
- data root write access / free space

environment-specific identifierを設定した上でpreflightを通した。

### Teleoperation

**[HW-VERIFIED]**

Bimanual leader-follower teleoperation、左右gripper、4 camera viewを確認した。loopは概ね30 Hzで動作した。

### Baseline recording

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

### Trossen external effort

**[HW-VERIFIED]**

`include_external_effort=true`:

```text
action                14D
observation.state     28D
```

Trossen driver内部state extensionの確認であり、独立外部F/T sensorとは区別する。

### Wrapper recording

**[HW-VERIFIED]**

`record.sh` による1 episode smoke test:

```text
frames                299
validator             PASS
```

## 4. High-rate numeric sensor validation — 2026-08-31

研究室既存のMMS101 ROS 2 streamを、異周期numeric sensor architectureのtest caseとして使用した。force値のground truthや物理取付の妥当性を評価する試験ではない。

### Native rate

**[HW-VERIFIED]**

使用したdriverではraw topicsが約100 Hzで動作した。

この値は使用driver/configurationの結果であり、MMS101一般の固定仕様として扱わない。

### Concurrent acquisition

**[HW-VERIFIED]**

ALOHA:

```text
frames                299
target fps            30
action                14D
observation.state     14D
camera streams        4
validator             PASS
```

Sensor sidecar:

```text
約60 s
左右約6005 samples
```

### Causal latest-sample alignment

**[HW-VERIFIED]**

```text
robot frames          299
sensor samples        9005
aligned frames        299
missing frames        0
future samples used   0
sensor age median     7.752 ms
sensor age p95        15.094 ms
sensor age max        16.396 ms
```

### 200 ms history window

**[HW-VERIFIED]**

```text
robot frames          299
ok frames             299
insufficient          0
future samples used   0
samples/window median 20
p05                   19
p95                   21
min                   19
max                   21
```

## 5. Asynchronous camera validation — 2026-08-31

GelSight Mini R0B 1台を、robot FPSと異なるcamera architectureのtest caseとして使用した。触覚task性能の評価ではない。

### V4L2 mode / actual rate

```text
format                MJPEG
resolution            3280x2464
advertised             25 fps
actual stream          約18.7-18.8 Hz
```

### Capture implementation comparison

Phase 1 full-resolution JPEG-per-frame comparison prototype:

```text
captured              87 frames / 10 s
capture rate          8.598 Hz
queue drops           0
```

V4L2 MJPEG stream copy:

```text
188 frames / 約10 s
≈18.8 Hz
```

これはPhase 1で作成したprototypeの方式比較であり、研究室既存codeまたはGelSight公式softwareのbenchmarkではない。

### Timestamp preservation

**[HW-VERIFIED]**

FFmpeg `-copyts -timestamps default -c:v copy` で保存したMKV packet PTSと、同一hostの `time.monotonic()` が同じclock domainになることを確認した。

5秒試行:

```text
frames                94
effective rate        約18.8 Hz
```

absolute monotonic値そのものは再利用価値がないため公開referenceには固定しない。

### Final concurrent validation

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
frames                1126
effective rate        18.753 Hz
```

Causal alignment:

```text
robot frames          299
aligned frames        299
missing frames        0
future frames used    0
reused assignments    111
camera age median     27.462 ms
camera age p95        50.602 ms
camera age max        53.836 ms
```

## 6. Verification limits

Phase 1では以下を保証しない。

- GelSight 2台同時使用時のUSB / CPU / storage capacity
- GelSightをgripperへ取り付けた状態での触覚task性能
- MMS101 force値のground truth
- hardware-trigger level synchronization
- 複数PC間clock synchronization
- VLA training / inference performance

GelSight 1台で、asynchronous camera architecture、packet timestamp保持、concurrent recording、causal alignmentの成立まで確認した。2台同時試験はarchitecture成立条件ではなくcapacity testとして扱う。

## 7. Final delivery acceptance

最終提出commitに対するacceptance結果をここへ記録する。

現在:

```text
Status: PENDING FINAL CLEAN-CHECKOUT ACCEPTANCE
```

完了後に以下のみ追記する。

```text
repository commit:
setup:
hardware identification / local config:
hardware check:
teleoperation:
recording:
dataset validation:
```

実行手順そのものは [02 Data Collection](02_data_collection.md) を正とする。
