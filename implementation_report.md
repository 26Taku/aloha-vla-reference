# Phase 1 Implementation Report

## 1. 目的

研究室のALOHAについて、初見の利用者が環境構築からteleoperation、実データ収録まで再現でき、今後のVLA案件でsoftware構成・sensor extension方法を毎回ゼロから調査しなくて済むreferenceを作成した。

Phase 1の主対象はdata collection stackであり、model training / inferenceはPhase 2の対象とする。

## 2. 採用したbaseline

標準構成にはTrossen Robotics公式 `lerobot_trossen` pluginを採用し、実機検証済みcommitを固定した。

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
LeRobotDataset v3.0
```

採用理由:

- Trossen AI seriesのhardware integrationがTrossen公式として提供される
- leader-follower teleoperation、robot state/action、複数camera、LeRobotDataset recordingを同一stackで扱える
- LeRobot系policyへの接続点が明確
- 研究室固有forkに標準手順を依存させずに済む

既存の研究用forkは変更せず、clean environmentで再現性を確認した。

## 3. 実装した成果物

### Baseline workflow

```text
setup.sh
check_hardware.sh
teleoperate.sh
record.sh
validate_dataset.sh
```

設定は `config/` に集約した。Arm IPとRealSense serialは環境固有値のためtracked templateではplaceholderとし、初回利用時にhardware identificationを行ってGit管理外の `*-local.yaml` へ設定する方式とした。

`record.sh` はDataset名、task、episode数、時間だけを受け取り、Hub uploadを無効にしたlocal recordingを生成する。

`validate_dataset.py` はLeRobotDataset v3のmetadata、Parquet、episode metadata、camera videoを確認する。

### External sensor reference

`examples/custom_sensor/` に、baseline recordingを壊さずに異周期sensorを追加するreferenceを実装した。

- robot frame host timestamp sidecar
- generic ROS 2 numeric/time-series logger
- causal latest-sample alignment
- causal history-window manifest
- asynchronous V4L2 camera timestamp extraction/alignment

## 4. Sensor architectureの選定

初期段階では、外部sensorをLeRobot observationへ直接追加する方法、ROS 2 sidecarを標準化する方法等を検討した。

最終的にはtransportを固定せず、以下を標準原則とした。

```text
acquisition rate != robot rate != policy rate

raw data + real timestamp = canonical
policy-specific synchronized view = derived
```

理由は、F/T、tactile camera、RGB cameraではnative rateとinterfaceが異なり、すべてを30 Hz LeRobot observationへ同期取得するとraw dynamicsの喪失やrobot loopへの負荷につながるためである。

### Numeric high-rate sensor

MMS101 ROS 2 streamを約100 Hzでnative-rate保存し、同一hostのmonotonic clockでALOHA 30 Hz frameへcausal alignmentした。299/299 frameをmissing 0 / future 0で対応付け、200 ms history windowも検証した。

### Asynchronous camera

GelSight Miniは25 fps modeをadvertiseしたが、検証機では実効約18.75 Hzだった。このため30 Hz robot loopへ同期cameraとして待たせず、V4L2 MJPEGを独立保存する方式を採用した。

FFmpeg stream copyによりdecode/re-encodeを避け、packet PTSを保持した。ALOHA 299 framesとGelSight 1126 framesの並行取得後、299/299 robot framesをcausal alignmentできた。

## 5. GelSight codeの出典整理

研究室で使用されていたGelSight helperは、GelSight Inc.公式 `gelsightinc/gsrobotics` のOpenCV based `GelSightMini`構造に対応する部分を持ち、その上に研究室/project-specificな変更が加わっていた。

研究室のROS 2 publisherはそのhelperを利用するwrapperであるが、確認したファイルだけから元repositoryまでは特定できなかった。このため、本成果物ではTrossen公式codeやGelSight公式標準codeとは表記しない。

Phase 1で比較用に作成したfull-resolution JPEG-per-frame prototypeが約8.6 Hzだった結果は、あくまで**本Phase 1 prototypeの実装比較**として扱う。研究室既存codeやGelSight公式codeの性能問題を示すものではない。

最終referenceには研究室側GelSight sourceをコピーせず、V4L2/FFmpeg + timestamp alignmentという独立した汎用経路のみを含めた。

## 6. 実機検証結果の要約

### Baseline ALOHA

- clean setup: PASS
- bimanual teleoperation: PASS
- 4 RealSense recording: PASS
- LeRobotDataset v3: PASS
- baseline 14D action / 14D state: PASS
- Trossen external effortによる28D state: PASS
- wrapper recording / validator: PASS

### High-rate sensor

- MMS101 raw rate: 約100 Hz
- robot frames: 299
- causal alignment: 299/299
- missing: 0
- future: 0
- sensor age p95: 15.094 ms
- 200 ms window: 19--21 samples

### Asynchronous camera

- GelSight native MJPEG: 18.753 Hz
- ALOHA concurrent recording: 299 frames / 30 Hz
- causal alignment: 299/299
- missing: 0
- future: 0
- camera age p95: 50.602 ms

詳細は `docs/06_validation_results.md` に記載した。

## 7. 制約

Phase 1のsoftware synchronizationは同一host monotonic clockを基準とし、hardware triggerやsub-millisecond synchronizationを保証しない。

また、GelSightは1台でarchitecture validationを行った。2台同時利用時のthroughputは未検証であり、実際に2台を標準搭載する案件ではcapacity testを追加する。

外部sensorをpolicyへどのようにencodeするか、VLAをどのruntimeでtraining/inferenceするかはPhase 2の設計事項とする。

## 8. 保守方針

本成果物は検証済みrevisionを固定する。Trossen/LeRobot update時は、clean setupからteleoperation、one-episode recording、Dataset validationまでを再実行する。

特にrobot frame timestamp referenceはLeRobot 0.6.0のrecord loopに依存するため、upstream更新時にはsource diffと再validationを必須とする。

## 9. 納品時の最終確認

最終提出commitを現地workstationへclean checkoutし、成果物に記載した手順だけで

```text
setup -> hardware identification/configuration -> hardware check -> teleoperation -> recording -> validation
```

を通す。最終結果は `docs/06_validation_results.md` に追記する。
