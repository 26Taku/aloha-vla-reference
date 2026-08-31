# Phase 1 Implementation Report

## 1. この文書の役割

本書はPhase 1で行った**調査、選定、実装、実機検証、残課題**を納品者・レビュー者向けに要約する。

利用者向けの操作マニュアルではない。初回利用手順は `docs/02_data_collection.md`、実機検証の詳細数値は `docs/06_validation_results.md` を正とする。

## 2. 目的

ALOHAについて、初見の利用者が環境構築からteleoperation、実データ収録まで再現でき、今後のVLA案件でsoftware構成・sensor extension方法を毎回ゼロから調査しなくて済むreferenceを作成した。

Phase 1の主対象はdata collection stackであり、model training / inferenceはPhase 2の対象とする。

## 3. 採用baseline

標準構成にはTrossen Robotics公式 `lerobot_trossen` pluginを採用し、実機検証済みcommitを固定した。

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
LeRobotDataset v3.0
```

主な採用理由:

- Trossen AI seriesのhardware integrationがTrossen公式として提供される
- leader-follower teleoperation、robot state/action、複数camera、LeRobotDataset recordingを同一stackで扱える
- LeRobot系policyへの接続点が明確
- 研究室固有forkをbaselineに依存させずに済む

既存研究forkは変更せず、clean environmentでreference stackを検証した。

選定理由の詳細は `docs/01_reference_stack.md` に記載した。

## 4. 実装成果物

Baseline workflow:

```text
setup.sh
check_hardware.sh
teleoperate.sh
record.sh
validate_dataset.sh
```

Hardware固有値はtracked configへ入れず、templateからGit管理外のlocal configを作る方式にした。

```text
config/teleop-template.yaml -> config/teleop-local.yaml
config/record-template.yaml -> config/record-local.yaml
```

これにより、public repositoryへArm IPやcamera serialを埋め込まず、利用者が対象hardwareを確認する工程を初回手順に含めた。

External sensor reference:

- robot frame host timestamp sidecar
- generic ROS 2 numeric/time-series logger
- causal latest-sample alignment
- causal history-window manifest
- asynchronous V4L2 camera timestamp extraction / alignment

## 5. Sensor architectureの選定

外部sensorをすべてLeRobot observationへ直接追加する方法、ROS 2 sidecarを標準化する方法等を比較した。

最終的にはtransportを固定せず、次を標準原則とした。

```text
acquisition rate != robot rate != policy rate

raw data + real timestamp          = canonical
policy-specific synchronized view = derived
```

F/T、tactile camera、RGB cameraではnative rateとinterfaceが異なる。すべてを30 Hz robot loopへ同期取得するとraw dynamicsの喪失やcontrol loopへの負荷につながるためである。

設計の詳細は `docs/03_architecture_and_extension.md` に記載した。

## 6. GelSight code provenance

研究室で使用されていたGelSight helperには、GelSight Inc.公式 `gelsightinc/gsrobotics` のOpenCV based `GelSightMini`構造に対応する部分があり、その上にproject-specific変更が加わっていた。

研究室のROS 2 publisherはそのhelperを利用するwrapperだが、確認したfileだけから元repositoryまでは特定できなかった。このためTrossen公式codeやGelSight公式標準codeとは表記しない。

Phase 1で作成したfull-resolution JPEG-per-frame comparison prototypeの結果は、本Phase 1内の実装比較としてのみ扱う。研究室既存codeやGelSight公式codeの性能評価ではない。

最終referenceには研究室側GelSight sourceをコピーせず、V4L2/FFmpeg + timestamp alignmentという独立した汎用経路のみを含めた。

## 7. 実機検証の要約

Baseline:

- clean setup: PASS
- bimanual teleoperation: PASS
- RealSense 4-view recording: PASS
- LeRobotDataset v3: PASS
- wrapper recording / validator: PASS
- Trossen external effort state propagation: PASS

External sensor architecture:

- high-rate numeric stream native acquisition: PASS
- robot/sensor causal alignment: PASS
- history-window generation: PASS
- asynchronous GelSight native compressed acquisition: PASS
- robot/camera causal alignment: PASS

詳細なframe数、rate、age distribution等は `docs/06_validation_results.md` に集約した。

## 8. 制約

Phase 1のsoftware synchronizationは同一host monotonic clockを基準とし、hardware triggerやsub-millisecond synchronizationを保証しない。

GelSightは1台でarchitecture validationを行った。2台同時利用時のthroughputは未検証であり、2台を標準搭載する案件ではcapacity testを追加する。

外部sensorをpolicyへどのようにencodeするか、VLAをどのruntimeでtraining / inferenceするかはPhase 2の設計事項とする。

## 9. 保守方針

本成果物は検証済みrevisionを固定する。

Trossen / LeRobot / hardware / Dataset schemaを変更した場合は `docs/05_maintenance.md` に従い、`docs/02_data_collection.md` のacceptance pathを再実行する。

特にrobot frame timestamp referenceはLeRobot 0.6.0のrecord loopに依存するため、upstream更新時にはsource diffと再validationを必須とする。

## 10. 納品時の最終確認

最終提出commitをclean checkoutし、`docs/02_data_collection.md` の正式手順だけで以下を通す。

```text
setup
-> hardware identification / local configuration
-> hardware check
-> teleoperation
-> recording
-> dataset validation
```

最終結果は `docs/06_validation_results.md` のFinal delivery acceptanceへ記録する。
