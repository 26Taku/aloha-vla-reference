# 実装・検証報告書

## 1. この文書の役割

本書は、第一期・第二期の**調査、選定、実装、設計判断、実機検証、制約**を納品・レビュー向けに要約する。教材本体とは別に提出し、教材を読む人に報告書の閲覧を前提としない。

利用者向けのbaseline操作は`docs/02_data_collection.md`、sensor extensionの操作・設計は`docs/03_architecture_and_extension.md`、第一期の実測値は`docs/06_validation_results.md`を正とする。第二期のVLA選択と実習は`docs/07_vla_model_selection.md`・`docs/08_vla_training_inference.md`、OpenVLA-OFTのデータ接続は`docs/09_openvla_oft_data_bridge.md`にまとめた。

利用者向け資料は、前提知識がない配属直後の学生が概念を学びながら作業できるよう、`docs/00_concepts_and_terminology.md`を入口とする教材構成へ改訂した。01〜05では用語の役割、作業目的、判断理由、成功条件を実際に使う箇所でも再説明する。06は操作手順ではなく、記載内容を実機で確認した証跡として位置づける。

---

## 2. 目的

ALOHAについて、初見の利用者がsoftware setupからteleoperation、Dataset収録、形式確認、VLAの短い学習、保存した重みからのオフライン推論まで進める教材を作成した。camera・F/T・tactile等の追加sensorについては既存の取得環境を再利用するintegration pathを示した。ソフトウェア、データ形式、モデル、実行系を区別し、用途に応じて次に調べる選択肢を示した。

第一期は機器とデータ収集を実機で、第二期はSmolVLA・LeRobot版π₀.₅の短い学習とオフライン推論をGPU上で検証した。**学習済み方策による実機の閉ループ制御や成功率は検証していない。**

---

## 3. 採用baseline

標準構成にはTrossen Robotics公式`lerobot_trossen` pluginを採用し、実機検証済みrevisionを固定した。

```text
TrossenRobotics/lerobot_trossen
a4336933f34192a3daa7e9fb52674284bb5ae48e
LeRobot 0.6.0
Python 3.12
LeRobotDataset v3.0
```

採用理由:

- Trossen AI seriesのhardware integrationが公式に提供される
- leader-follower teleoperation、robot state/action、複数camera、Dataset recordingを同一stackで扱える
- LeRobotDatasetを後段の学習stackへ接続しやすい
- 研究室固有forkをbaseline dependencyにしなくてよい

既存研究forkは変更せず、第一期ではclean environmentでreference stackを検証した。第二期には、同じ固定revisionの新規構築環境へ収録データを移して学習を実行した。この別PCの利用は当時の作業条件であり、標準手順の必須構成ではない。

---

## 4. 実装成果物

### 4.1 Baseline workflow

```text
setup.sh
check_hardware.sh
teleoperate.sh
record.sh
validate_dataset.sh
```

### 4.2 Hardware identityとoperational configの分離

Machine-specific identityを1 fileへ集約した。

```text
config/hardware-template.yaml    tracked
config/hardware-local.yaml       local / gitignored
```

Operational settingはtracked templateとして保持する。

```text
config/teleop-template.yaml
config/record-template.yaml
```

Wrapper実行時に`hardware-local.yaml`とoperational templateを結合し、`.runtime/`以下へcomplete configを生成する。

```text
hardware-local.yaml
      +
teleop-template.yaml / record-template.yaml
      ↓
build_runtime_config.py
      ↓
.runtime/*.yaml
```

これにより、Arm IPやcamera serialを複数fileへ重複入力せず、tracked repositoryへmachine-specific identifierを保存しない構成にした。

### 4.3 External sensor reference

- `record_with_timestamps.py`: robot frame host timestamp sidecar
- `ros2_timeseries_logger.py`: generic ROS 2 numeric/time-series logger
- `align_timeseries.py`: causal latest-sample alignment
- `build_sensor_windows.py`: causal history-window manifest
- `validate_alignment.py`: numeric alignment validation
- `camera/extract_mkv_timestamps.py`: asynchronous camera packet timestamp export
- `camera/align_camera_frames.py`: camera causal latest-frame alignment

### 4.4 第二期の教材と変換例

- `docs/07_vla_model_selection.md`: VLAの入口、選択の判断点、公開研究への参照。ACTとDiffusion Policyは非VLAとして参考節へ分けた。
- `docs/08_vla_training_inference.md`: 各自の収録データからLeRobot版π₀.₅とSmolVLAの短い学習、checkpoint再読込、オフライン推論へ進む実習。
- `docs/09_openvla_oft_data_bridge.md`と`examples/openvla_oft/`: LeRobotDataset v3からHDF5、TFDS/RLDS、OpenVLA-OFTローダへの1 episode変換例。標準のLeRobot→OFT変換コマンドではなく、本教材で作成した接続例である。

教材用の`aloha_vla_demo`は読者が02で収録して使う仮の共通名である。検証時の黄色いスポンジボールの収録条件やepisode数を、教材の標準データ量としていない。機器固有のIP・serial、校正値、Hub token、収録データも成果物には含めない。

---

## 5. Sensor extension設計

Sensor implementationそのものを標準化するのではなく、**ALOHAへ接続するinterface boundaryと、その境界以降のvalidation pathを標準化する**方針を採用した。

```text
sensor-specific implementation
        ↓
integration interface
        ↓
native raw acquisition + host timestamp
        ↓
concurrent ALOHA recording
        ↓
causal alignment
        ↓
validation / policy-specific derived view
```

共通原則:

```text
sensor acquisition rate != robot/control rate != policy rate

raw data + real timestamp          = canonical
policy-specific synchronized view = derived
future sample/frame                = prohibited in causal alignment
```

この設計により、vendor SDK、研究室既存driver、ROS 2 node、V4L2 camera等の既存資産を置き換える必要はない。利用者はsensor streamを取得可能な状態まで準備し、03で定義したinterface contractへ合わせる。interfaceが一致しない場合のみthin adapterを追加する。

Pattern BではROS 2 numeric stream、Pattern CではV4L2 asynchronous cameraを具体例としてend-to-end validationした。

---

## 6. Sensor-specific codeのprovenance / distribution boundary

### MMS101

検証で使用したROS 2 driverには複数の開発・修正履歴があるため、sensor-specific driver sourceは本referenceへ含めない。

Reference側は次のinterfaceだけを要求する。

```text
running numeric stream
known message/data format
actual rateを測定可能
hostで受信timestampを取得可能
```

実機では`geometry_msgs/msg/WrenchStamped`を使用し、MMS101固有workspaceをsubscriber側でsourceしないclean shellからgeneric loggerへ接続できることを確認した。

### GelSight Mini

研究室固有helper / ROS 2 wrapperをreference dependencyにせず、Linux V4L2 + FFmpegのnative compressed captureを採用した。GelSight固有SDK、marker tracking、depth等が必要な場合はsensor-specific layerで別途扱う。

この分離により、provenanceが不明確な研究室内codeを再配布せず、ALOHA integration側だけを独立したreferenceとして提供できる。

---

## 7. Baseline実機検証で得た運用上の知見

Teleoperation起動時、Leaderが操作可能になってからFollower follow loop開始まで短い時間差が生じる場合があった。follow開始前にLeaderを大きく移動すると、Followerが蓄積したpose gapを急に解消しようとしてjoint velocity limitで停止する試行があった。

このため、起動直後はLeaderを保持し、小さなLeader motionへFollowerが連続追従することを確認してから通常操作を開始する手順を`docs/02_data_collection.md` / `docs/04_troubleshooting.md`へ反映した。

また、error停止状態からArm Controllerの電源を切ると保持力が失われるため、power cycle前にArmを物理的に支持し、落下経路を空ける安全手順を採用した。

---

## 8. 実機検証の要約

Baseline:

```text
clean setup / fixed upstream revision      PASS
hardware preflight                         PASS
bimanual teleoperation                     PASS
RealSense 4-view recording                 PASS
LeRobotDataset v3 validation               PASS
configuration-unified end-to-end path      PASS
```

Pattern B — high-rate numeric:

```text
clean-shell interface boundary             PASS
native acquisition                         PASS
ALOHA concurrent recording                 PASS
299 / 299 causal alignment                 PASS
missing / future                           0 / 0
200 ms history window                      PASS
```

Pattern C — asynchronous camera:

```text
V4L2 native compressed acquisition         PASS
packet timestamp export                    PASS
ALOHA concurrent recording                 PASS
299 / 299 causal alignment                 PASS
missing / future                           0 / 0
```

詳細なrate、frame数、age distributionは`docs/06_validation_results.md`に集約した。

---

## 9. 第二期の収録データと検証器の修正

ALOHA実機で、右Armによるボールの把持、左Armへの受け渡し、左Armによる箱への投入を50 episode収録した。2 episodeは受け渡しに失敗し、1 episodeは成功したが開始時のgripper状態が他と異なった。元の50 episodeを保持し、失敗した2件を除く48 episodeの学習用派生データを作成した。開始状態の違う成功例は、それだけを理由に除外しなかった。

別に開始位置を変えた12 episode（A・B・C各4件）を収録し、Cの4件が失敗したためCを4件撮り直した。A・Bの成功8件と再収録の成功4件で12 episodeの派生データを作成した。これらのepisode数は検証時の事実であり、実用性能に必要な収録数を示さない。成功・失敗の選別と評価用holdoutをどう扱うかは、教材08で用途に応じた判断として説明した。

収録データはLeRobotDataset v3、30 fps、424×240の4画像、14次元`action`・`observation.state`である。カメラごとのMP4分割位置は異なったが、metadataを通してepisodeとframeを読めた。48 episodeの派生データと12 episodeの派生データについて、validatorとLeRobotDatasetローダで読込を確認した。Parquetの14次元ベクトルが`list<float>`として保存された派生データを、第一期の`validate_dataset.py`が固定長リスト以外は異常と判定した箇所は**自作検証器の不備**である。要素数の確認に対応させて再検証した。LeRobot本体のデータ不良とは扱わない。

収録loopが一時的に30 Hzを下回る警告も見たが原因は特定していない。同時期の計算機負荷などを切り分けず、特定解像度への変更を一般的な対処法とはしていない。読者は自機でframe数、動画、継続的な警告、計算機負荷を照合する。

## 10. 第二期の学習とオフライン推論

固定したTrossen revisionから、Ubuntu 22.04.5 LTS、RTX A6000 48 GB×2の別PCにPython 3.12の環境を構築した。PyTorch 2.7.1+cu126でCUDAを確認し、収録データのvalidatorとLeRobotDatasetローダ読込を通した。これは第一期のALOHAワークステーションでの収録から、別のGPU環境へデータを渡せることも示すが、別PCへの移送を教材の標準フローとはしていない。

| モデル・経路 | 確認した段階 | 未確認の段階 |
|---|---|---|
| SmolVLA / LeRobot 0.6.0 | 4画像・state・task・14D actionで3 step smoke testと200 stepの学習。保存checkpointの再読込、前後処理、有限値の`(1, 14)` actionを確認 | 未知の配置への汎化、タスク成功率、実機制御 |
| π₀.₅ / LeRobot 0.6.0 | PaliGemmaへのアクセスを確認し、3 stepの学習・checkpoint保存・再読込・有限値の`(1, 14)` actionを確認 | 長時間学習の性能、実機制御 |
| OpenVLA-OFT | 1 episodeのデータを学習用ローダまで接続（次節） | 重み学習、checkpoint推論、実機制御 |

学習環境で確認した版は`lerobot==0.6.0`、`torch==2.7.1`、`accelerate==1.15.0`である。SmolVLAの実行経路では`transformers==5.5.4`、`safetensors==0.6.2`を確認した。初回試行では`uv`がPython 3.14を選びlockの`==3.12.*`と衝突し、また`lerobot-train`の`accelerate`不足と、Trossen pluginにはない`training` extraの指定で停止した。個別の`uv pip install`後に`uv run`が依存を再同期し、直前に入れた`transformers`と`safetensors`の版が食い違う試行もあった。教材では使った版と実行コマンドを明示し、依存が変わる場合は実行プロセス内で再確認する。これらのエラーは当時の版・環境で生じた事実であり、すべての導入先で必ず再現する問題ではない。

いずれのオフライン推論も、学習に使ったデータの観測から値を得た経路確認である。holdoutは形式と読込を確認したが、未知条件でのロボット成功率やモデル間性能を測定していない。

## 11. OpenVLA-OFTへの接続確認

OpenVLA-OFT公開コードのcommit `e4287e94541f459edc4feabc4e181f537cd569a8`、紹介されているRLDS builderのcommit `6174b0b6bb69df6361f1117944952bf14afb0cc3`を基にした。元のALOHA例はHDF5を前処理しRLDSへ変換する経路を採用している。LeRobotDataset v3のMP4・Parquet・metadataをそのままOFTへ渡すことはできないため、本教材ではv3→HDF5→TFDS/RLDSの接続を実装した。元にない`qvel`や`effort`を合成しない。

1 episodeの598 frame、30 fps、4画像、14次元state/action、task文をHDF5とTFDSで照合した。配布名を`aloha_vla_demo`へ変えた後、配布するexport script・builder・OFT patchを別worktreeで組み合わせ、TFDS生成とOpenVLA-OFTの`RLDSDataset`の読込を**改名後の組合せで再実行**した。結果は3画像入力、proprio `(1, 14)`、30 step×14次元のaction chunkだった。低位置カメラはTFDSに残るが、このOFT設定でローダへ渡す3画像には入らない。30 stepは30 fpsの1秒に合わせた設定例で、元データを25 Hzとして扱っていない。

この結果はデータローダの接続までであり、OpenVLA-OFTの重み学習が通ることを保証しない。専用環境の依存解決、基盤重みの取得、GPUメモリ、学習スクリプトの実行とcheckpoint検査は別の検証となる。今回はOpenVLA-OFTの学習と実機実行を納品範囲に含めない。

## 12. 制約

- 同期は同一host monotonic clockを基準とするsoftware-level alignmentであり、hardware triggerやsub-millisecond synchronizationを保証しない
- GelSight 2台同時captureのUSB / CPU / storage capacityは未検証
- MMS101のforce ground truth / calibration accuracyは本validationの対象外
- sensor-specific driverの他hardware / firmware / OSでの互換性は保証しない
- policyへsensor historyをどうencodeするかはtask / model architectureに依存する
- 短いVLA学習とオフライン推論は処理経路の確認であり、模倣性能・未知配置への汎化・実機閉ループ制御は未検証
- OpenVLA-OFTはRLDS生成とローダ出力まで確認し、重み学習とcheckpoint推論は未実施

---

## 13. 保守方針

本成果物は検証済みupstream revisionを固定する。

Trossen / LeRobot / hardware / Dataset schemaを変更した場合は`docs/05_maintenance.md`に従って関連acceptance pathを再実行する。特に`record_with_timestamps.py`はLeRobot 0.6.0のrecord loop実装に依存するため、upstream更新時にはsource diffと再validationを行う。

第二期の経路では、LeRobotのprocessorと`meta/stats.json`、PyTorch・Transformers等の実行依存、OpenVLA-OFTの3ファイルへのdataset登録と行動chunk長も再検証の対象となる。

External sensorを変更する場合はsensor名ではなくinterface contractを再確認する。

```text
data format
actual rate
source/device timestamp semantics
host monotonic timestamp
causal alignment
missing / age distribution
```

---

## 14. 納品時の最終確認

Hardwareを必要とするbaseline / Pattern B / Pattern C validationと、第二期のGPU上の短い学習・オフライン推論、OpenVLA-OFTへの1 episode接続は、上記の範囲で完了した。

Final document revisionをcommitした後、最終repository treeに対して以下を行う。

```text
git diff --check
Markdown relative link check
machine-specific identifier scan
personal/staging repository URL scan
generated/runtime/data artifact exclusion check
fresh clone / setup static path check
```

教材化revisionでは、さらに以下を確認する。

```text
READMEのStart hereから00へ最初に到達できる
00から01 -> 02へ学習順序がつながる
02冒頭でteleoperation、達成目標、物理接続を説明する
03を具体的なsensor追加例から開始し、方式選択まで導く
06を利用者が自分の結果を比較・判断できる構成にする
納品・review向けの説明を教材本文へ混在させない
相対linkとMarkdown code fenceが壊れていない
```

Final commitとrelease check結果は提出時に別途確認する。利用者向けの`docs/06_validation_results.md`には納品確認を混在させない。
