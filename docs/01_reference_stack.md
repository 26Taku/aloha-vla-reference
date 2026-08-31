# Reference Stack

## 1. 目的

本資料では、研究室のALOHAを用いてVLA・模倣学習向けデータを収集する際の標準構成を整理する。

ALOHAにはTrossenの各種driverやROS 2など複数の利用方法があるが、本プロジェクトでは、teleoperationからLeRobotDatasetの作成までを一つの流れで扱える **Trossen Robotics公式 LeRobot Plugin (`lerobot_trossen`)** をデータ収集のbaselineとして採用する。

この構成は研究室のALOHA実機で動作確認済みである。

---

## 2. 標準構成

### Software

| 項目 | 採用構成 |
|---|---|
| Trossen integration | `TrossenRobotics/lerobot_trossen` |
| Verified commit | `a4336933f34192a3daa7e9fb52674284bb5ae48e` |
| LeRobot | 0.6.0 |
| Python | 3.12 |
| Environment manager | `uv` |
| Trossen Arm library | 1.10.0 |
| Dataset format | LeRobotDataset v3.0 |

公式 `lerobot_trossen` はLeRobot向けのTrossen AI series integrationであり、Trossen側でも `uv` を用いた導入手順が提供されている。

本成果物では、検証済みcommitを固定して使用する。最新版への追従は自動では行わず、更新時にはsetup、hardware check、teleoperation、recording、dataset validationを再実行する。

### Hardware

実機確認時の構成は以下。

- Bimanual leader: 2 arms
- Bimanual follower: 2 arms
- Intel RealSense D405: 4 cameras
- Camera views:
  - high
  - low
  - left wrist
  - right wrist

研究室固有のIP addressおよびcamera serialは `config/teleop-lab.yaml` と `config/record-template.yaml` に記載する。

---

## 3. この構成をbaselineとする理由

本プロジェクトの目的は、ALOHAそのものを制御することではなく、**VLA・模倣学習に利用できるデータを収集すること**である。

そのため、以下を一つのsoftware stackで扱えることを重視した。

1. Leader-Follower teleoperation
2. Robot state / actionの取得
3. 複数cameraの取得
4. Episode単位のrecording
5. LeRobotDatasetへの保存
6. 後段の学習処理との接続

LeRobotではrobotを共通interfaceとして扱い、observationの取得とactionの送信をrecordingやpolicy側から利用する構造になっている。Trossen公式Pluginを使用することで、ALOHA固有のhardware interfaceとLeRobotのrecording pipelineの間を公式実装で接続できる。

このため、本プロジェクトではVLA向けデータ収集の最初の選択肢としてこの構成を使用する。

---

## 4. 他の構成との使い分け

### Trossen公式 LeRobot Plugin

**標準選択。**

以下の場合に使用する。

- ALOHAのteleoperation dataを収集したい
- RGB cameraとrobot state/actionをまとめて保存したい
- LeRobotDatasetを利用したい
- LeRobot上のpolicyや、LeRobotDatasetを入力にできる学習系へ接続したい

本成果物のQuick Startはこの構成を対象とする。

### ROS 2

本プロジェクトではALOHAの標準的なteleoperation / recording経路としては使用しない。

一方で、以下のような場合は併用を検討する。

- 外部sensorのdriverがROS 2として提供されている
- 高周期sensorを独立して取得したい
- 他のROS 2 nodeとの連携が必要
- timestamp付きのsensor streamを別系統で保持したい

外部sensorを追加する場合に、必ずROS 2が必要という意味ではない。LeRobot側へ直接統合する方法と、ROS 2等で独立取得して同期する方法を用途に応じて選択する。

詳細は `docs/03_architecture_and_extension.md` に記載する。

### Trossen driverを直接利用する構成

独自制御や低レベルのhardware accessが必要な場合には候補となる。

ただし、VLA向けdataset収集だけが目的であれば、teleoperation、camera、dataset writer等を別途組み合わせる必要が生じるため、本プロジェクトのbaselineにはしない。

### 既存の研究用fork

研究室PC上には研究用途で変更された既存環境が存在するが、本成果物では標準構成として使用しない。

本プロジェクトでは既存環境に変更を加えず、別ディレクトリにTrossen公式repositoryからclean environmentを構築して検証した。

既存fork固有の機能が必要な案件では、その差分を確認した上で個別に利用する。

---

## 5. 実機で確認済みの範囲

以下は研究室のALOHAで実際に確認済み。

- clean environmentでのdependency installation
- 4台のTrossen Armへの接続
- RealSense D405 4台の認識
- 左右Leader-Follower teleoperation
- Rerun Viewerでのcamera / state表示
- 4 cameraを含むepisode recording
- LeRobotDataset v3.0としての保存
- baseline datasetの14-dimensional action / 14-dimensional observation state
- Trossen側のexternal effortを追加した28-dimensional observation stateの保存
- 保存後datasetのmetadata / Parquet / videoのvalidation
- MMS101 ROS 2 streamのnative-rate取得（約100 Hz）とALOHA frameへのcausal alignment
- GelSight Miniのnative MJPEG取得（実効18.753 Hz）とALOHA 30 Hz recordingへのcausal alignment

`external effort` はTrossen driver内部のstate extension確認である。独立した外部sensorについては別経路として、raw acquisition + host timestamp + derived alignmentを実機確認した。詳細は `docs/03_architecture_and_extension.md` と `docs/06_validation_results.md` を参照する。

---

## 6. 標準構成から変更する場合

以下を変更する場合は、Quick Startをそのまま使用せず、関連箇所を確認する。

| 変更内容 | 主に確認する資料 |
|---|---|
| Arm IP / camera serial | `config/` |
| Camera追加・変更 | `docs/03_architecture_and_extension.md` |
| Robot state追加 | `docs/03_architecture_and_extension.md` |
| 外部sensor追加 | `docs/03_architecture_and_extension.md` |
| LeRobot / Trossen Plugin更新 | `docs/05_maintenance.md` |
| Dataset schema変更 | `docs/02_data_collection.md` / `docs/06_validation_results.md` |

---

## 7. 公式資料

- Trossen Robotics LeRobot integration  
  https://github.com/TrossenRobotics/lerobot_trossen

- Trossen Robotics LeRobot Installation Guide  
  https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot_plugin/setup.html

- Hugging Face LeRobot documentation  
  https://huggingface.co/docs/lerobot/
