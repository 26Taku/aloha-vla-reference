# 06 実機検証結果と正常性の判断

この章は、自分の環境で得た結果を解釈するための比較資料である。[02](02_data_collection.md)と[03](03_architecture_and_extension.md)に記載した手順を実機で実行したとき、どのような値と挙動が得られたかを示す。

数値を完全に一致させる必要はない。PC負荷、収録時間の境界、USB構成、sensor設定によって変動する。次のように使う。

| 自分の結果 | 判断と次の確認 |
|---|---|
| 同じ10秒収録でframe数が299前後 | baselineと同程度。validatorと映像内容を確認する |
| frame数やcamera FPSが大幅に少ない | USB、CPU、storage負荷、camera modeを調べる |
| Sensor rateが製品仕様と異なる | 仕様値ではなく実測値を記録し、task要件を満たすか判断する |
| `future samples used`が1以上 | causalでない。clockまたはalignment処理を修正する |
| validatorはPASSだがtaskが失敗 | file構造は正常。demonstration内容を目視で評価する |

## 1. 検証環境

| 項目 | 検証時の構成 |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| CPU | Intel Xeon w9-3575X |
| RAM | 約503 GiB |
| GPU | NVIDIA RTX PRO 6000 96GB ×4 |
| Trossen integration | `TrossenRobotics/lerobot_trossen` |
| Integration commit | `a4336933f34192a3daa7e9fb52674284bb5ae48e` |
| LeRobot | 0.6.0 |
| Python | 3.12 |
| Trossen Arm | 1.10.0 |
| Dataset | LeRobotDataset v3.0 |

Data collection自体は重いGPU計算を必要としない。GPU構成が異なるだけで失敗と判断しない。

実機固有のArm IP、camera serial、USB serial、device pathは別個体へ流用できないため記載していない。[02](02_data_collection.md)の方法で自分の機器を識別する。

## 2. Baseline ALOHA

### 2.1 Hardware preflight

`./check_hardware.sh`で次を確認した。

| 項目 | 結果 |
|---|---|
| Follower Arm | 2台 |
| Leader Arm | 2台 |
| RealSense D405 | 4台 |
| IP / serialと物理配置の対応 | 確認済み |
| 保存先 | 書き込み可能 |
| 最終表示 | `[READY]` |

利用者側でも、台数だけでなく物理的な左右・camera画角との対応を確認する。4台見えていても、左右が入れ替わっていれば収録準備は完了していない。

### 2.2 Teleoperation

左右のLeader-Follower、gripper、4画面を確認した。通常動作時のcontrol loopは概ね30 Hzだった。

起動直後、Leaderが操作可能になってからFollowerの追従loopが始まるまで短い時間差が生じる場合があった。この間にLeaderを大きく動かすと、Followerが姿勢差を急に解消しようとしてjoint velocity limitで停止した試行がある。

このため、正常な開始手順は次のように判断する。

1. 起動後、Leaderを現在位置付近で保持する。
2. Followerが小さな動きへ連続追従することを確認する。
3. その後に通常の操作範囲へ移る。

約30 Hzは比較値であり、表示が一時的に前後するだけで異常とは限らない。動作の引っ掛かり、継続的な低下、warningの反復が同時にあるかを見る。

### 2.3 Baseline recording

| 条件 | 15秒試験 | 10秒smoke test |
|---|---:|---:|
| Episode | 1 | 1 |
| Frames | 449 | 299 |
| Action | 14D | 14D |
| Observation state | 14D | 14D |
| Camera streams | 4 | 4 |
| Video | 424×240、約30 fps | 424×240、約30 fps |
| Validator | PASS | PASS |

target 30 fpsなら、理想計算は10秒で300 frames、15秒で450 framesである。実測はそれぞれ1 frame少なかった。開始・終了時刻の境界による小さな差はあり得るため、固定値だけで判定しない。

次をまとめて正常性の基準にする。

- 収録秒数とframe数がおおむね整合する。
- 4本のvideoがあり、先頭frameをdecodeできる。
- action / stateが14Dである。
- timestampが単調に増加する。
- validatorが`[PASS]`になる。
- 映像を再生し、task内容とcamera画角が正しい。

## 3. 高rateの数値sensor: 力覚streamの例

MMS101由来のROS 2 streamを、[03のPattern B](03_architecture_and_extension.md)の実例として使用した。ここで評価しているのはsensor精度ではなく、既存の数値streamをALOHAと同時に保存し、時刻で対応付けられるかである。

### 3.1 入力の確認

| 項目 | 実測条件 |
|---|---|
| Topic | `/force_torque/left` |
| Message type | `geometry_msgs/msg/WrenchStamped` |
| Payload | 6-axis force / torque |
| Clean-shell test | 3秒で298 samples |

Sensor driverを別processで起動し、subscriber側ではROS 2 Jazzyだけをsourceしたclean shellからtopic type、1 sample、logger動作を確認できた。これはloggerがMMS101固有workspaceの内部実装へ直接依存せず、標準message境界から取得できたことを意味する。

### 3.2 Sensor単体

| 項目 | 結果 |
|---|---:|
| 収録時間 | 10 s |
| Samples | 1002 |
| Actual rate | 約100 Hz |
| Raw format | JSONL |
| Alignment clock | `receive_monotonic_ns` |

「100 Hz」はこのdriverと設定での実測値であり、製品一般の固定性能として扱わない。

### 3.3 ALOHAとの同時収録

Sensor loggerを60秒間動かし、その区間内で10秒のALOHA episodeを収録した。

| 系統 | 結果 |
|---|---|
| ALOHA | 299 frames、4 cameras、14D action/state |
| ALOHA timestamp sidecar | 299 records |
| ALOHA validator | PASS |
| Sensor | 6002 samples / 60 s、約100 Hz |

Sensorを同時に動かしてもALOHAのbaselineが保たれている。自分の試験では、sensor単体時と同時収録時のrate、ALOHA frame数、validator結果を比較する。

### 3.4 Causal alignment

| 指標 | 結果 |
|---|---:|
| Robot frames | 299 |
| Sensor samples | 6002 |
| Aligned frames | 299 |
| Missing frames | 0 |
| Future samples used | 0 |
| Malformed records | 0 |
| Sensor age median | 7.727 ms |
| Sensor age p95 | 15.029 ms |
| Sensor age max | 16.809 ms |
| Validator | PASS |

`future samples used = 0`は必須条件である。約100 Hzならsample間隔はおよそ10 msだが、process schedulingや受信時刻の付け方によりageは常に10 ms未満とは限らない。medianだけでなくp95とmaxも見て、継続的な遅延や外れ値を判断する。

### 3.5 200 msの履歴window

1時点の値ではなく直前200 msの波形を各robot frameへ割り当てた。

| 指標 | 結果 |
|---|---:|
| Robot frames / OK frames | 299 / 299 |
| Insufficient frames | 0 |
| Future samples used | 0 |
| Samples per window median | 20 |
| p05 / p95 | 19 / 21 |
| min / max | 19 / 21 |

100 Hzのsensorでは200 msに約20 samples入るため、19〜21は期待と整合する。大幅に少ない場合は実測rate、timestamp gap、logger停止を調べる。

## 4. 非同期camera: tactile cameraの例

GelSight Mini 1台を、[03のPattern C](03_architecture_and_extension.md)の実例として使用した。触覚taskの性能ではなく、robotと異なるFPSのcameraをnative videoとして保存し、時刻で対応付けられるかを確認した。

### 4.1 Camera modeと単体収録

| 項目 | 設定・結果 |
|---|---|
| Pixel format | MJPG / MJPEG |
| Resolution | 3280×2464 |
| Advertised FPS | 25 |
| 10秒のframes | 188 |
| Effective rate | 18.754 Hz |
| Codec | MJPEG |
| First-frame decode | PASS |
| Timestamp | export成功、単調増加 |

advertised 25 fpsに対し実効rateは約18.8 Hzだった。仕様表だけを使わず、実際に保存できたframe数からrateを測る必要があることが分かる。

開始時に`EOI missing, emulating`が1回表示されたが、MKV保存、decode、timestamp exportは正常に完了した。warning単体ではなく、最終fileを読めるかまで確認して判断する。

### 4.2 ALOHAとの同時収録

| 系統 | 結果 |
|---|---|
| ALOHA | 299 frames、14D action/state、4 RGB videos |
| ALOHA validator | PASS |
| GelSight | 750 frames / 約40 s |
| GelSight effective rate | 18.728 Hz |

### 4.3 Causal alignment

| 指標 | 結果 |
|---|---:|
| Robot frames | 299 |
| Aligned frames | 299 |
| Missing frames | 0 |
| Future frames used | 0 |
| Reused assignments | 111 |
| Camera age median | 26.461 ms |
| Camera age p95 | 50.617 ms |
| Camera age max | 53.083 ms |
| Alignment | PASS |

ALOHAが約30 Hz、cameraが約18.7 Hzなので、1枚のcamera frameが複数のrobot frameへ割り当てられる。`reused assignments = 111`はこのrate差から生じる想定内の結果であり、ただちに欠落を意味しない。

一方、future framesは0でなければならない。ageの上限がtask要件を超える場合は、camera mode、取得rate、timestamp付与位置、またはhardware同期の必要性を見直す。

## 5. 結果を判断するための優先順位

測定値が比較例と異なる場合、次の順で確認する。

1. **成立性**: processが完走し、fileを読み出せるか。
2. **完全性**: 必要なstream、frame、metadataがそろっているか。
3. **因果性**: future sample / frameを使用していないか。
4. **時間品質**: actual rate、missing、ageがtask要件を満たすか。
5. **内容品質**: 映像、操作、sensor値が実際の現象を表しているか。

validatorがPASSでも、4と5は利用者が評価する必要がある。逆に実測値が本章と少し異なっても、task要件を満たし、理由を説明できれば直ちに失敗ではない。

## 6. この検証からは判断できないこと

次は未検証であり、本章の値から性能を推定しない。

- GelSight 2台同時使用時のUSB、CPU、storage capacity
- GelSightをgripperへ取り付けた状態での触覚task性能
- MMS101のforce ground truthやcalibration accuracy
- 別hardware、firmware、OSでのdriver互換性
- hardware-trigger levelやsub-millisecondの同期
- 複数PC間のclock synchronization
- VLA modelの学習・推論性能

ここで使用した同期は、同一PCのmonotonic clockを基準にしたsoftware-level alignmentである。より厳密な同期が必要なら、hardware trigger、共有clock、PTPなどを要件から設計する。

## 7. 自分の実験記録に残すもの

自分の環境で同じ試験を行ったら、少なくとも次を保存する。

- repositoryと`lerobot_trossen`のcommit
- OSと主要package version
- task、episode数、収録時間
- Arm、camera、追加sensorの構成
- target rateとactual rate
- validator結果
- aligned、missing、future、ageの統計
- warning、error、目視で気づいた挙動

実機固有identifierは公開資料へ貼らず、研究室内の実験記録として管理する。再現性に必要なのは、個体番号の公開ではなく、**どの方法で識別し、どの条件で測り、何を成功としたか**である。
