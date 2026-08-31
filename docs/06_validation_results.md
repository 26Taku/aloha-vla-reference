# Validation Results

本資料では、Phase 1で実際に研究室環境・ALOHA実機を用いて確認した範囲を記録する。検証結果と設計上の提案を混同しないため、実機確認済みの内容だけを主に記載する。

## 1. Reference environment

検証機:

```text
OS: Ubuntu 24.04.4 LTS
CPU: Intel Xeon w9-3575X
RAM: 約503 GiB
GPU: NVIDIA RTX PRO 6000 96GB x4
```

GPU 0は他用途で使用中だったため、Phase 1のdata collection validationではheavy GPU workloadを避けた。

Software reference:

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
Trossen Arm 1.10.0
```

## 2. Baseline ALOHA validation — 2026-08-27

### Clean environment setup

**[HW-VERIFIED]** 既存研究forkとは別directoryへTrossen公式repositoryをcloneし、固定commitで `uv sync --frozen` が完了した。

### Hardware preflight

**[HW-VERIFIED]** 以下を確認した。

- follower arms x2: environment-specific IPを設定して到達性を確認
- leader arms x2: environment-specific IPを設定して到達性を確認
- Intel RealSense D405 x4
- environment-specific camera serial mappingがconfigと一致
- data rootへの書き込みと十分な空き容量

### Teleoperation

**[HW-VERIFIED]** Bimanual leader-follower teleoperation、左右gripper、4 camera viewを確認した。loopは概ね30 Hzで動作した。

### Baseline recording

**[HW-VERIFIED]** 15秒・1 episode recordingが完了した。

```text
Dataset format        LeRobotDataset v3.0
frames                449
action                14D
observation.state     14D
camera streams        4
camera video          424x240 / 30 fps
```

Dataset validatorでmetadata、Parquet、episode metadata、4 video streamの先頭frame decodeまでPASSした。

### Trossen external effort

**[HW-VERIFIED]** `include_external_effort=true` でrecordingし、左右7値ずつのexternal effortが追加されることを確認した。

```text
action                14D
observation.state     28D
```

これはTrossen driver内部のstate extension確認であり、独立外部F/T sensorの検証とは区別する。

### Wrapper recording

**[HW-VERIFIED]** `record.sh` を使用した1 episode smoke testで299 framesを保存し、validator PASSを確認した。

## 3. High-rate numeric sensor validation — 2026-08-31

検証sensorとして研究室既存のMMS101 ROS 2 streamを使用した。物理的な左右取付状態やforce値の妥当性を評価する試験ではなく、**異周期numeric streamの取得・timestamp・alignment architecture**を確認する試験である。

### Sensor rate

**[HW-VERIFIED]** 使用したUMI sensor workspaceのraw topics:

```text
/force_torque/left
/force_torque/right
```

実測rateは左右とも約100 Hzだった。

別環境のMMS101 driverでは異なるsampling intervalを持つ場合があるため、この100 Hzをsensor一般仕様として扱わない。

### Concurrent acquisition

**[HW-VERIFIED]** ALOHA recordingとMMS101 sidecarを同時実行した。

ALOHA dataset:

```text
frames                299
target fps            30
action                14D
observation.state     14D
camera streams        4
validator             PASS
```

MMS101 sidecarの60秒試行では左右約6005 samplesを取得した。

### Generic causal alignment

**[HW-VERIFIED]** generic loggerとrobot timestamp sidecarを使用した検証結果:

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

**[HW-VERIFIED]** `(t-200 ms, t]` のcausal history manifestを作成した。

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

## 4. Asynchronous camera validation — 2026-08-31

検証camera: GelSight Mini R0B 1台。

この試験も触覚値・接触taskの妥当性ではなく、**robot FPSと異なるcamera streamの取得・timestamp・causal alignment**を確認するものとした。

### Device / format

V4L2で確認したmode:

```text
MJPEG
3280x2464
advertised 25 fps
```

`v4l2-ctl` / OpenCV grab / FFmpeg stream copyでは実効約18.7--18.8 Hzだった。advertised 25 fpsには到達しなかった。

### Capture implementation comparison

Phase 1で作成したfull-resolution JPEG-per-frame prototype:

```text
captured              87 frames / 10 s
capture rate          8.598 Hz
queue drops           0
```

同じcameraをV4L2 MJPEGのstream copyで保存:

```text
188 frames / 約10 s
≈18.8 Hz
```

この比較は**Phase 1 prototypeの方式選定用**であり、研究室既存GelSight codeまたはGelSight公式softwareのbenchmarkではない。

### Timestamp preservation

**[HW-VERIFIED]** FFmpeg `-copyts -timestamps default -c:v copy` で保存したMKV packet PTSが、同一hostの `time.monotonic()` と同じclock domainになることを確認した。

5秒試行では94 framesを保存し、MKV packet PTSとhost `time.monotonic()` が同一clock domainで連続していることを確認した。absolute monotonic値そのものは環境固有かつ再利用価値がないためreferenceには固定値として残さない。

### Final concurrent validation

**[HW-VERIFIED]** GelSight streamを先に開始し、ALOHA 10秒recordingを並行実行した。

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

18.753 Hzのframe periodは約53 msであり、30 Hz robot frameに対するlatest causal frameのage分布として整合する。

## 5. Verification limits

以下はPhase 1で確認していない、または保証しない。

- GelSight 2台同時使用時のUSB/CPU/storage capacity
- GelSightをALOHA gripperへ取り付けた状態での触覚task性能
- MMS101のforce値そのもののground truth validation
- hardware-trigger levelのcamera/sensor synchronization
- 複数PC間clock synchronization
- VLA modelのtraining/inference performance

GelSight 1台でも、asynchronous camera architecture、packet timestamp保持、concurrent recording、causal alignmentの成立は検証できている。2台試験はarchitecture成立条件ではなくcapacity testとして扱う。

## 6. Final delivery acceptance

提出物そのものをclean checkoutし、次を上から実行して最終確認する。

```text
[ ] setup.sh
[ ] check_hardware.sh -> READY
[ ] teleoperate.sh -> bimanual + gripper + 4 cameras
[ ] record.sh -> 1 episode completes
[ ] validate_dataset.sh -> PASS
```

この欄は最終acceptance run後にcommit hashと結果を追記する。
