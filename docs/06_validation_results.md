# Validation Results

## 1. この資料の役割

本資料は、**本referenceで実際に実機・workstation上で確認した結果の証跡**を記録する。

操作手順は [02 Data Collection](02_data_collection.md)、設計は [01 Reference Stack](01_reference_stack.md) / [03 Architecture and Extension](03_architecture_and_extension.md) を参照する。

## 2. Reference environment

検証workstation:

```text
OS: Ubuntu 24.04.4 LTS
CPU: Intel Xeon w9-3575X
RAM: 約503 GiB
GPU: NVIDIA RTX PRO 6000 96GB x4
```

data collection validationではheavy GPU workloadを使用していない。

Software:

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
Trossen Arm 1.10.0
```

machine-specific Arm IP、camera serial、USB serial等は記載しない。

## 3. Baseline ALOHA validation — 2026-08-27

### Clean environment setup

**[HW-VERIFIED]**

Trossen公式repositoryをclean directoryへcloneし、固定commitで `uv sync --frozen` が完了した。

### Hardware preflight

**[HW-VERIFIED]**

- follower arms x2
- leader arms x2
- Intel RealSense D405 x4
- camera physical mapping
- data root write access / free space

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

### Wrapper recording

**[HW-VERIFIED]**

`record.sh` による1 episode smoke test:

```text
frames                299
validator             PASS
```

## 4. High-rate numeric sensor validation — 2026-08-31

MMS101 ROS 2 streamを、robot recording rateと異なるnumeric sensor architectureのtest caseとして使用した。

### Native rate

**[HW-VERIFIED]**

使用driverではraw topicsが約100 Hzで動作した。

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

GelSight Mini R0B 1台を、robot FPSと異なるcamera architectureのtest caseとして使用した。

### V4L2 mode / actual rate

```text
format                MJPEG
resolution            3280x2464
advertised            25 fps
actual stream         約18.7-18.8 Hz
```

### Capture方式比較

full-resolution JPEG-per-frame経路:

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

この結果から、asynchronous camera referenceではnative compressed stream copyを採用した。

### Timestamp preservation

**[HW-VERIFIED]**

FFmpeg `-copyts -timestamps default -c:v copy` で保存したMKV packet PTSと、同一hostの `time.monotonic()` が同じclock domainになることを確認した。

5秒試行:

```text
frames                94
effective rate        約18.8 Hz
```

### Concurrent validation

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

## 6. Clean-checkout end-to-end validation — 2026-09-01

**[HW-VERIFIED]**

fresh cloneからData Collectionの手順を実行し、以下を確認した。

```text
repository clean checkout                 PASS
setup.sh                                  PASS
Arm network interface confirmation        PASS
trossen-arm discover                      PASS
physical Arm mapping with identify        PASS
RealSense D405 x4 discovery               PASS
camera physical mapping                   PASS
check_hardware.sh                         READY
bimanual teleoperation                    PASS
one-episode recording                     PASS
dataset validation                        PASS
```

Arm identificationでは4台のControllerを検出し、全台でfirmware `1.10.0`、`No error` を確認した。

RealSenseは4台を列挙し、保存画像を用いてphysical camera roleとの対応を確認した。

### Teleoperation startup safety

**[HW-VERIFIED]**

teleoperation起動時、Leaderが操作可能になってからFollowerの追従loopが開始するまで短い時間差が生じる事例を確認した。

追従開始前にLeaderを大きく移動した試行では、Follower追従開始時にjoint velocity limitへ到達し、Controllerがidle/error状態へ移行した。

Controller restart後に正常復帰し、Leaderを保持したままFollower追従開始を待つことでteleoperationを正常に継続できた。

error停止姿勢からControllerの電源を切る際には保持力が失われ、Armが自重で落下することも確認した。Data CollectionとTroubleshootingに起動時の待機手順とpower cycle前の支持を反映した。

## 7. Single-source hardware configuration validation — 2026-09-01

**[HW-VERIFIED]**

machine-specific hardware identityを `config/hardware-local.yaml` の1ファイルに集約し、teleoperation / recording用runtime configをtracked templateと自動合成する構成を実機で通した。

確認項目:

```text
hardware-local.yaml                         PASS
runtime teleop config generation            PASS
runtime record config generation            PASS
check_hardware.sh                           READY
bimanual teleoperation                      PASS
one-episode recording                       PASS
dataset validation                          PASS
```

camera serialはruntime config生成時に文字列へ正規化され、YAML上でnumeric scalarとして入力した場合もLeRobot用configへ正しく反映できることを確認した。

## 8. Verification limits

以下は未検証または本referenceの保証範囲外である。

- GelSight 2台同時使用時のUSB / CPU / storage capacity
- GelSightをgripperへ取り付けた状態での触覚task性能
- MMS101 force値のground truth
- hardware-trigger level synchronization
- 複数PC間clock synchronization
- VLA training / inference performance

## 9. Validation結果の扱い

本資料の数値は、記載したhardware / software構成で得たreference resultである。

LeRobot / Trossen Arm、camera mode、sensor driver、recording FPS、Dataset schema等を変更した場合は [05 Maintenance](05_maintenance.md) に従って再検証する。
