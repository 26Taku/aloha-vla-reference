# Architecture and Extension

## 1. 目的

本資料では、研究室のALOHAで採用する標準構成について、設定ファイルからTrossen Arm、teleoperation、LeRobotDatasetまでのデータ経路を整理する。また、カメラや外部センサを追加する場合に、どの層を変更すべきかを示す。

確認状態は以下のように区別する。

- **[HW-VERIFIED]**: 研究室のALOHA実機で確認済み
- **[CODE-VERIFIED]**: 固定したソースコード上で確認済み
- **[DESIGN]**: 推奨設計。実機確認前
- **[NOT-VERIFIED]**: 対象ハードウェアでは未確認

## 2. 対象バージョン

### Trossen側

- Repository: `TrossenRobotics/lerobot_trossen`
- Verified commit: `a4336933f34192a3daa7e9fb52674284bb5ae48e`

主に確認するファイル:

```text
packages/lerobot_robot_trossen/src/lerobot_robot_trossen/
├── config_bi_widowxai_follower.py
├── bi_widowxai_follower.py
├── config_widowxai_follower.py
└── widowxai_follower.py

packages/lerobot_teleoperator_trossen/src/lerobot_teleoperator_trossen/
├── config_bi_widowxai_leader.py
├── bi_widowxai_leader.py
├── config_widowxai_leader.py
└── widowxai_leader.py
```

### LeRobot側

- LeRobot: `v0.6.0`
- 主なrecording実装: `src/lerobot/scripts/lerobot_record.py`

## 3. 全体のデータ経路

標準構成の主要な経路は以下。

```text
YAML configuration
        │
        ├───────────────┐
        ▼               ▼
Follower config     Leader config
        │               │
        ▼               ▼
BiWidowXAIFollower  BiWidowXAILeader
        │               │
        │          get_action()
        │               │
        ├──── observation/action ────┐
        │                            │
        ▼                            ▼
robot.get_observation()         teleop.get_action()
        │                            │
        ▼                            ▼
observation processor          action processor
        │                            │
        │                       robot.send_action()
        │                            │
        └────────────┬───────────────┘
                     ▼
              build_dataset_frame()
                     │
                     ▼
               dataset.add_frame()
                     │
                     ▼
              LeRobotDataset v3.0
```

**[CODE-VERIFIED]** LeRobot側ではDataset作成時に `robot.action_features` と `robot.observation_features` からDataset schemaを構築する。recording loopでは `robot.get_observation()` と `teleop.get_action()` の結果を処理し、`build_dataset_frame()` を経て `dataset.add_frame()` へ渡す。

このため、Robot interfaceが公開するfeature定義と実際のdictionary出力を整合させることが、追加データをDatasetへ保存する際の中心になる。

## 4. Follower側の構造

### 4.1 Bimanual config

`config_bi_widowxai_follower.py` の `BiWidowXAIFollowerRobotConfig` には、主に以下が定義されている。

- left/right Arm IP
- `max_relative_target`
- `min_time_to_move_multiplier`
- `loop_rate`
- `include_velocity`
- `include_effort`
- `include_external_effort`
- `cameras`

**[CODE-VERIFIED]** `include_velocity`、`include_effort`、`include_external_effort` は左右のsingle-arm configへそのまま渡される。Trossen Arm自身が提供する追加状態量については、single-arm層でfeatureと値を追加する構造になっている。

### 4.2 Bimanual Follower

`bi_widowxai_follower.py` の `BiWidowXAIFollowerRobot` は内部に以下を持つ。

```text
left_arm  -> WidowXAIFollower
right_arm -> WidowXAIFollower
cameras   -> make_cameras_from_configs(config.cameras)
```

`observation_features` は左右Armのfeature名に `left_` / `right_` prefixを付け、camera featureと結合する。`action_features` も同様に左右をprefix付きで結合する。

`get_observation()` は左右Armのobservationを取得し、prefixを付け、各cameraから最新frameを取得して一つのdictionaryとして返す。

`send_action()` はbimanual actionを左右に分割し、prefixを外して各Armへ渡す。

## 5. Single Followerと状態量

`widowxai_follower.py` の `WidowXAIFollower` が実際のTrossen driverと接続する。

### `observation_features`

baselineではjoint position featureを公開する。設定によって以下を追加する。

```text
include_velocity        -> .vel
include_effort          -> .eff
include_external_effort -> .ext_eff
```

### `get_observation()`

Trossen driverの `get_robot_output().joint.all` からjoint情報を取得し、設定に応じて以下をdictionaryへ追加する。

```text
<joint>.pos
<joint>.vel
<joint>.eff
<joint>.ext_eff
```

**[HW-VERIFIED]** `include_external_effort=true` とした実機recordingでは、左右7値ずつの `.ext_eff` が追加され、`observation.state` が14Dから28Dへ拡張されてDatasetへ保存された。

これは以下の経路が実際に機能することを示す。

```text
config flag
   ↓
observation_features
   ↓
get_observation()
   ↓
BiWidowXAIFollowerRobot
   ↓
LeRobot recording
   ↓
Dataset schema / Parquet
```

ただし、これはTrossen driver内部で取得可能な状態量の追加であり、MMS101等の独立した外部センサ統合そのものではない。

## 6. Leader側の構造

`bi_widowxai_leader.py` の `BiWidowXAILeaderRobot` は左右の `WidowXAILeaderTeleop` をまとめる。

`action_features` は左右のjoint positionを `left_<joint>.pos` / `right_<joint>.pos` として公開する。

`get_action()` は左右Leaderからactionを読み、prefixを付けて一つのaction dictionaryとして返す。このactionがLeRobot recording loopで処理され、Followerへ送られると同時にDataset actionとして使用される。

## 7. LeRobot recording側

`src/lerobot/scripts/lerobot_record.py` がRobot / TeleoperatorとDatasetを接続する。

### 7.1 Dataset schemaの生成

**[CODE-VERIFIED]** Dataset作成前に、`robot.action_features` と `robot.observation_features` を基にinitial featureを生成し、processor pipelineによるfeature変換を反映した後、`LeRobotDataset.create()` の `features` として渡す。

したがって、追加する数値sensorをLeRobotDatasetの標準observationとして保存する場合には、

1. `observation_features` にfeatureを追加する
2. `get_observation()` が同じkeyで値を返す

の両方が必要になる。

### 7.2 Recording loop

**[CODE-VERIFIED]** observation側は、

```text
robot.get_observation()
        ↓
robot_observation_processor
        ↓
build_dataset_frame(..., prefix=observation)
```

action側は、

```text
teleop.get_action()
        ↓
teleop_action_processor
        ↓
robot_action_processor
        ↓
robot.send_action()
```

Datasetへの書き込みは、

```text
observation_frame + action_frame + task
        ↓
dataset.add_frame()
```

となる。

### 7.3 action保存に関する注意

**[CODE-VERIFIED]** LeRobot v0.6.0のrecording loopでは、`robot.send_action()` の戻り値を `_sent_action` に格納しているが、Datasetのaction frameは `_sent_action` ではなく `action_values` から生成される。

一方、Trossen側の `send_action()` は `max_relative_target` が設定されている場合、actionをclipする可能性がある。

したがって、標準構成のように `max_relative_target=None` であれば通常問題にならないが、action clippingを有効にする場合には、「Datasetに記録されたaction」と「Followerへ実際に送られたaction」が一致するかを別途確認する必要がある。

## 8. Cameraを追加・変更する場合

### 8.1 LeRobotが対応済みのcameraを追加する場合

**[CODE-VERIFIED]** cameraは `config.cameras` から生成される。

```text
config.cameras
      ↓
make_cameras_from_configs()
      ↓
BiWidowXAIFollowerRobot.cameras
      ↓
_cameras_ft
      ↓
get_observation()
      ↓
LeRobotDataset video feature
```

対応済みcameraを追加するだけであれば、基本的にはconfigurationを変更する。

確認項目:

- camera type
- serial / device identifier
- width / height
- fps
- RGB / depth設定
- USB帯域
- recording loopへの負荷

**[HW-VERIFIED]** 研究室構成ではRealSense D405 4台のRGB recordingを確認済み。

### 8.2 未対応cameraを追加する場合

**[DESIGN]** LeRobotのCamera interfaceへadapterを追加し、既存cameraと同様に `config.cameras` から生成できる形にするのが望ましい。Robot側でcamera SDKを直接呼び出すより、camera interfaceへ閉じ込める方が再利用しやすい。

## 9. 外部数値センサを追加する場合

MMS101等の外部sensorでは、Trossen Arm内部のexternal effortとは異なり、独立driver、独立sampling rate、sensor timestamp、connection lifecycle、synchronizationを考慮する必要がある。

用途によって2つの方式を分ける。

### 9.1 Policy-rateでLeRobot observationへ統合する

**[DESIGN]** VLAやpolicyへ30 Hz程度で入力する値として使用する場合。

```text
External sensor
     ↓
Sensor adapter / buffer
     ↓
latest or aggregated value
     ↓
Robot observation
     ↓
LeRobotDataset
```

6軸F/T sensorであれば、例えば以下のfeatureを追加する。

```text
external_ft.fx
external_ft.fy
external_ft.fz
external_ft.tx
external_ft.ty
external_ft.tz
```

必要な変更は概念的に以下。

1. sensor configを追加
2. sensor adapterを初期化
3. Robotのconnect/disconnectとsensor lifecycleを接続
4. `observation_features` に6 featureを追加
5. `get_observation()` で値を返す
6. validatorで追加feature / dimensionを確認

既存の公式Trossen repositoryを直接改変するより、研究室側のwrapper / subclassまたは独立adapterとして実装し、upstreamとの差分を小さく保つ方が保守しやすい。

**[NOT-VERIFIED]** MMS101実機での統合は未確認。

### 9.2 高周期raw dataを保持する

**[DESIGN]** F/T、tactile等のsensorがrobot controlより高周期で動作し、raw waveform自体に意味がある場合は、すべてを30 Hzの `observation.state` に押し込まない。

推奨構成:

```text
                    ┌─> LeRobot observation @ policy rate
External sensor ────┤
                    └─> raw logger @ sensor rate
```

raw loggerでは最低限、sensor timestamp、host timestamp、raw sensor valuesを保存する。episode開始・終了時刻または共通clockを用いて、後処理でLeRobotDatasetとの同期を行う。

policy入力として使用するときだけ、latest、mean、max、window feature、resampling等によってpolicy-rateへ変換する。

## 10. ROS 2 sensorを使用する場合

**[DESIGN]** sensor driverがROS 2として提供されている場合、ALOHA全体をROS 2制御へ変更する必要はない。

一例:

```text
ROS 2 sensor node
       ↓
subscriber / bridge
       ↓
thread-safe latest-value buffer
       ↓
LeRobot Robot.get_observation()
```

高周期raw dataを保存する場合は、ROS 2側loggerとLeRobot recordingを独立させ、timestampで同期する方式も候補となる。

重要なのは、sensor acquisition rate、Dataset fps、policy inference rateを同一と仮定しないことである。

## 11. 変更目的と確認箇所

| 変更したい内容 | 主な変更・確認箇所 |
|---|---|
| Arm IP変更 | `config/*.yaml` |
| Camera serial変更 | `config/*.yaml` |
| 対応済みcamera追加 | `config.cameras` |
| RGB / depth切替 | camera config / `_cameras_ft` |
| Trossen velocity追加 | `include_velocity` |
| Trossen effort追加 | `include_effort` |
| Trossen external effort追加 | `include_external_effort` |
| 独立数値sensor追加 | sensor adapter + `observation_features` + `get_observation()` |
| 高周期raw sensor | 独立logger + timestamp同期 |
| action表現変更 | `action_features` / processor / `send_action()` |
| safety clipping有効化 | `max_relative_target` と保存actionの一致確認 |
| Dataset schema変更 | Robot features + processor + validator |
| LeRobot更新 | `docs/05_maintenance.md` の再検証 |

## 12. 外部6軸センサ用reference implementationの方針

**[DESIGN]** 特定のMMS101 driverへ直接依存する前に、最小の6軸sensor interfaceをreferenceとして作る。

想定interface:

```python
class ForceTorqueSensor:
    def connect(self) -> None:
        ...

    def read(self) -> dict[str, float]:
        # fx, fy, fz, tx, ty, tz
        ...

    def disconnect(self) -> None:
        ...
```

dummy backendを用いて、

```text
dummy 6D sensor
      ↓
sensor adapter
      ↓
Robot observation
      ↓
LeRobot Dataset
```

の経路をまずcode-levelで確認する。その後MMS101 backendへ置き換える場合は、`read()` より下のhardware acquisition部分だけを変更する。

このreference implementationにより、「LeRobot側へどう渡すか」と「sensor固有driverをどう読むか」を分離する。

## 13. 実機検証で確認する項目

外部sensor reference implementationを実機ALOHAへ接続した場合、以下をacceptance criteriaとする。

```text
[ ] baseline teleoperationが壊れていない
[ ] sensorなしでも従来構成が動作する
[ ] sensorありでconnect / disconnectできる
[ ] observation featureへ追加される
[ ] recordingが完了する
[ ] Dataset schemaへ追加featureが現れる
[ ] Parquetに実値が保存される
[ ] validatorがPASSする
[ ] recording loopの著しいrate低下がない
```

実MMS101を利用する場合には追加で、sensor timestamp、sampling rate、LeRobot frameとの同期方法を確認する。

## 14. まとめ

標準的な拡張では、LeRobot recording script自体を案件ごとに直接変更するのではなく、

```text
hardware / sensor
       ↓
Robot interface
       ↓
feature definition + observation
       ↓
standard LeRobot recording pipeline
```

という境界を維持する。

特に外部sensorでは、「policy-rate observationとして統合するデータ」と「高周期raw dataとして保持するデータ」を区別して設計する。これにより、sensorを追加するたびにrecording全体を作り直すのではなく、必要なinterface層だけを変更できる構成を目指す。
