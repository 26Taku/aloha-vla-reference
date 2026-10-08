# 11 学習済みVLAを実機へ接続し、動作を評価する

[08 学習・オフライン推論](08_vla_training_inference.md)で確認したcheckpointを、Trossen AI seriesの双腕ロボットへ接続します。まず接続経路を確認し、次に物体を扱うタスクを実行し、失敗した段階を記録します。モデルから数値のactionが出ることと、実機でタスクが成功することを分けて判断できるようになることが、本章の目的です。

標準の起動方法は[Trossen公式の非同期推論](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot_plugin/async_inference.html)を参照してください。本章は、実際に通した際に必要だった環境の分離、入力の照合、設定の変更、動作の評価を補います。接続先とカメラの個体設定は02で用意したものを引き継ぎます。

> **この章の確認範囲**：LeRobot 0.6.0と固定TrossenプラグインによるSmolVLA・π₀.₅の実機接続、および後述するタスク動作を確認しました。第3節のコマンドは、その実行コードを各研究室で設定できる形に整理した起動例です。整理したスクリプトは構文とロボット非接続の設定生成を確認しています。整理後の環境構築・GPU実行・実機動作は再確認前です。過去の実機実績と、現在の起動例の確認範囲を区別してください。

## 1. ここまでの章とのつながり

| 必要なこと | 参照先 | 本章へ進む条件 |
|---|---|---|
| state・action・episode・VLAの意味 | [00](00_concepts_and_terminology.md) | 数値の指令とタスクの成功が別だと説明できる |
| 駆動・データ形式・モデル・実行系の選択 | [01](01_reference_stack.md)、[07](07_vla_model_selection.md)、[10](10_stack_decisions_and_extension.md) | 今回はLeRobot版SmolVLAまたはπ₀.₅を使うと決めている |
| 個体識別、接続、テレオペ、収録 | [02](02_data_collection.md) | 自分の装置で収録でき、使用した収録YAMLを保存している |
| 学習、checkpoint保存、前後処理を含む再読込 | [08](08_vla_training_inference.md) | 自分のcheckpointからオフラインで有限なactionが出る |
| OFTの変換・専用学習経路 | [09](09_openvla_oft_data_bridge.md) | 本章の起動例には接続しない。OFTの実機controllerは未確認 |
| センサ追加と保守 | [03](03_architecture_and_extension.md)、[05](05_maintenance.md) | 既存経路を通した後、変更箇所と再確認範囲を考える |

初心者は00→01→02→07→08→11の順に進めます。03・09・10は研究目的に応じて参照します。収録の正常性は[06](06_validation_results.md)、接続やデバイスの問題は[04](04_troubleshooting.md)へ戻って確認します。

## 2. ロボットを動かす前に準備する

### 2.1 serverとclientを分ける

非同期推論では、**serverがモデルを読み込み、画像・stateからactionを生成**し、**clientがロボットとカメラを扱い、観測を送ってactionを実行**します。モデルは1回の推論で複数時刻のaction（action chunk）をまとめて出し、clientが順番に実行します。今回の実機検証は同じPCの2端末で行いました。学習PCからネットワーク越しにロボットを動かした例ではありません。

収録用の環境にはTrossenプラグインとカメラの依存、推論用の環境にはモデルとGPUの依存が必要です。GPUに合わせて推論環境を調整しても、動作確認済みの収録環境を一緒に更新しない構成にしました。別PC構成へ変更する場合は、localhostの置換だけでなく通信遅延・切断時の動作も確認します。

今回の実行環境は次のとおりです。必要資源の下限を示す表ではありません。

| 項目 | 実機検証時の値 |
|---|---|
| OS | Ubuntu 24.04.4 LTS |
| 推論GPU | NVIDIA RTX PRO 6000 Blackwell Max-Q Workstation Edition。共有PC上の1台 |
| 推論Python / LeRobot | 3.12.3 / 0.6.0 |
| 推論PyTorch / Transformers | 2.7.1+cu128 / 5.5.4 |
| 非同期追加依存 | grpcio 1.84.0、protobuf 7.36.2 |
| Trossenプラグイン | a4336933f34192a3daa7e9fb52674284bb5ae48e |
| trossen-arm | 1.10.0 |

収録環境の作成は02、学習環境は08を参照します。推論を別環境で行う場合も、公式の非同期推論に従い、serverに`async`とモデルに対応するextra、clientに`async`とロボットプラグインを用意します。SmolVLAのextraは`smolvla`、π₀.₅は`pi`です。本教材の版と揃える場合、LeRobotを0.6.0に固定します。パッケージ一覧の表はlockfileの代わりにはなりません。

今回のGPUでは、収録環境のPyTorchをそのまま使ったGPU計算が通らず、推論環境にCUDA 12.8系buildを用意しました。`torch.cuda.is_available()`がtrueであるだけでは、対象GPUで演算できると判断しません。[PyTorch公式の版別インストール手順](https://pytorch.org/get-started/previous-versions/)でGPU・driverに合うbuildを選び、実際のCUDA演算を確認します。

**実機PCに推論環境を新規作成する場合**は、02で`REPO`を設定した後、収録用の`.venv`と別の場所を使います。次は今回使ったCUDA 12.8 buildを選ぶ場合の組立例です。別のGPU・driverにはbuildの選択をそのまま流用しません。既存環境がある場合は再作成せず、第3節でそのPythonを上書き指定します。

```bash
set -euo pipefail
: "${REPO:?02のscripts/session.shをsourceしてください}"
INFER_ENV="$REPO/.venvs/vla-inference"
test ! -e "$INFER_ENV"
uv venv --python 3.12 "$INFER_ENV"
INFER_PY="$INFER_ENV/bin/python"
uv pip install --python "$INFER_PY" \
  'torch==2.7.1' 'torchvision==0.22.1' \
  --index-url https://download.pytorch.org/whl/cu128
printf '%s\n' 'torch==2.7.1+cu128' 'torchvision==0.22.1+cu128' \
  'transformers==5.5.4' > "$INFER_ENV/inference-constraints.txt"
uv pip install --python "$INFER_PY" \
  --constraint "$INFER_ENV/inference-constraints.txt" \
  'lerobot[async,smolvla,pi]==0.6.0'
uv pip check --python "$INFER_PY"
printf '推論Python: %s\n' "$INFER_PY"
```

この例は両モデルのextraを用意し、PyTorchのbuildとTransformersの版を保持します。推移的依存まで固定した環境原本ではなく、整理後の新規構築例です。インストールが通ること、対象GPUの演算、モデルの再読込を順に確認します。収録環境へのasync追加は、その環境の既存版を維持して行います。

### 2.2 checkpointとキャッシュを用意する

08で保存した`pretrained_model`ディレクトリ全体を用意します。`model.safetensors`だけをコピーせず、モデル設定、前処理、後処理、その統計ファイルも含めます。基盤モデル・tokenizerへのアクセス条件は08を参照してください。

| 今回必要だった追加ファイル | 確認したrevision |
|---|---|
| SmolVLA：HuggingFaceTB/SmolVLM2-500M-Video-Instructのキャッシュ | 7b375e1b73b11138ff12fe22c8f2822d8fe03467 |
| π₀.₅：google/paligemma-3b-pt-224のtokenizerキャッシュ | 35e4f46485b4d07967e7e9935bc3786aad50687c |

オフライン実行では、キャッシュも推論側から読める場所に置きます。Hugging Faceのキャッシュを移すときはrefs・snapshots・blobsとsymlinkの参照先を保持します。別環境で取得した認証tokenをキャッシュと一緒に配布しません。

今回のπ₀.₅では、ファイルの転送・ハッシュ照合後も名前による読込に失敗しました。`refs/main`が指すrevision文字列の改行を除いた後、オフライン読込が通りました。ファイルが存在するか、指定したキャッシュを見ているか、参照文字列が正しいかを分けて確認します。

### 2.3 学習入力と実機入力を照合する

| 照合する項目 | 今回の対応 | 合わない場合の対応 |
|---|---|---|
| 画像feature | cam_high、cam_low、cam_left_wrist、cam_right_wristの4視点 | 02の物理対応とcheckpointのinput_featuresを見比べる |
| state/actionの順序 | 左6関節→左gripper→右6関節→右gripper | Datasetのfeature名とロボット側の並びを照合する |
| 単位 | 関節rad、gripper m | 次元数だけで互換と判断せず、保存・読込・指令の単位を確認する |
| action表現 | 今回は絶対関節目標。π₀.₅はuse_relative_actions=false | 前後処理を含めて確認し、別表現の重みをそのまま送らない |
| task文 | 収録YAMLのdataset.single_task | 学習時の文を使う。新しい文への汎化は別の評価とする |
| 開始姿勢・画角・物体配置 | おおよそ収録範囲内 | 新配置への汎化と接続確認を一度に評価しない |

14次元のshapeが合っていても、左右・順序・単位は保証されません。また、driverの初期位置と収録開始姿勢は必ずしも一致しません。デモ収録時の開始姿勢と、接続・終了時の姿勢移動を確認します。

clientの起動・終了にも姿勢移動があります。今回のCtrl+Cでは初期位置への復帰が見られました。**Ctrl+Cは、この構成では移動を伴う終了であり、その場での即時停止ではありません。** 接続・終了時の経路と、現地で使用できる停止手段を担当者と確認してからclientを起動します。

## 3. 標準の保存先を使い、同じPCの2端末で起動する

以下はUbuntuのbash用です。02で設定した`REPO`と`DATASET`を使います。標準構成ならパスを書き換える必要はありません。参照先の確認→GPUとオフライン推論の確認→試行上限の説明と入力→server/client起動の順に進めます。独自の配置を使う場合の上書き方法はStep 1にまとめています。

### Step 1：モデルとファイルの参照先を確認する

08の第7.2節まで同じPCで進めた場合、学習結果をコピーし直す必要はありません。11は次の場所を直接参照します。`OUTPUTS`を08で変更している場合も、その変数を引き継ぎます。新しい端末では08と同じ`DATASET`・`OUTPUTS`を設定してください。

| 内容 | 標準の参照先 |
|---|---|
| SmolVLA checkpoint | `$OUTPUTS/smolvla_4cam_20k/checkpoints/020000/pretrained_model/` |
| π₀.₅ checkpoint | `$OUTPUTS/pi05_4cam_20k/checkpoints/020000/pretrained_model/` |
| 収録YAML | `$REPO/.runtime/record-$(basename "$DATASET").yaml` |
| client Python | `$REPO/lerobot_trossen/.venv/bin/python` |
| 推論Python | `$REPO/.venvs/vla-inference/bin/python` |
| Hugging Faceキャッシュ | `HF_HUB_CACHE`、または通常の`~/.cache/huggingface/hub`（`HF_HOME`も参照） |

02のデータ名`aloha_vla_demo`なら、収録YAMLは`record-aloha_vla_demo.yaml`です。このファイルから実機の接続・カメラ設定とtask文を引き継ぎます。別PCで学習した場合は、checkpoint一式と必要なキャッシュを実機PCへ転送し、実機PCで収録に使ったYAMLを指定します。

```bash
source "$REPO/scripts/policy_session.sh"
```

このコマンドは、**モデル種別と上表の参照先をシェル変数へ設定し、表示するだけ**です。入力待ちにはならず、GPUの選択、動作上限の決定、モデルのロード、実機接続は行いません。08で一時的に使った3-step・200-stepの`CHECKPOINT`変数は引き継がず、20Kの参照先を設定します。

モデルは08でexportした`POLICY_TYPE`を引き継ぎ、未設定ならSmolVLAです。π₀.₅を使う場合は次を実行します。参照先もπ₀.₅用へ切り替わります。

```bash
export POLICY_TYPE=pi05
source "$REPO/scripts/policy_session.sh"
```

表示された`Checkpoint`と`Record config`が対象のファイルか確認してください。学習が完了していない、または別名の学習結果を使う場合は、そのまま次へ進まず以下で参照先を指定します。

**既存の学習結果が別名・別の場所にある場合だけ**、次を実行します。`pretrained_model`まで含む絶対パスを入力します。モデル名に対応するローカル設定へ保存するため、次回のsourceでも再利用できます。

入力例（端末表示の例。次のパス自体を実行するものではありません）：

```text
既存のpretrained_modelの絶対パス: /home/student/aloha-vla-reference/outputs/pi05_4cam_b8_20k_20261005_190207/checkpoints/020000/pretrained_model
```

```bash
read -r -p "既存のpretrained_modelの絶対パス: " CHECKPOINT
export CHECKPOINT
test -f "$CHECKPOINT/config.json" &&
mkdir -p "$REPO/.runtime" &&
printf 'export CHECKPOINT=%q\n' "$CHECKPOINT" \
  > "$REPO/.runtime/policy-checkpoint-$POLICY_TYPE.sh"
```

`last/pretrained_model`は最新保存checkpointへの参照です。評価条件を固定するため、本章では`020000/pretrained_model`のようにstepを明示した場所を使います。ファイル名を標準形へ変更したり、学習し直したりする必要はありません。

**推論Pythonが別の場所にある場合だけ**、次のように指定します。`RECORD_CFG`や`MODEL_CACHE`も独自の配置なら同じ方法で上書きできます。

```text
既存の推論Pythonの絶対パス: /home/student/vla-inference/.venv/bin/python
```

```bash
read -r -p "既存の推論Pythonの絶対パス: " INFER_PY
export INFER_PY
```

入力するのはパスの文字列だけです。引用符を付けず、Enterで確定します。`export`は通常、何も表示しません。繰り返し使うPython・キャッシュなどのパスは、`.runtime/policy-local.sh`に`export`行として保存できます。checkpointの設定はモデル別の`policy-checkpoint-<モデル名>.sh`に分けています。これらはローカル設定でありGitには含めません。

### Step 2：GPU・依存・入力を確認する（ロボット非接続）

GPUはモデルの計算に使います。まず使用許可のあるGPUを一覧の`index`番号で選びます。選んだ番号からGPU固有のUUIDを取得し、以後の計算先を固定します。ここでは動作上限を入力しません。

例えば使用してよいGPUが一覧のindex 1なら、入力は次のようになります。空きメモリだけで利用許可を判断せず、共有機では利用状況を確認します。

```text
使用するGPU番号（一覧のindex）: 1
Selected GPU: GPU-12345678-1234-1234-1234-123456789abc
```

```bash
nvidia-smi --query-gpu=index,uuid,name,memory.free,utilization.gpu --format=csv
read -r -p "使用するGPU番号（一覧のindex）: " GPU_INDEX
GPU_UUID="$(nvidia-smi -i "$GPU_INDEX" --query-gpu=uuid --format=csv,noheader)" &&
export GPU_UUID
printf 'Selected GPU: %s\n' "$GPU_UUID"
```

UUIDは表示形式の例です。実際には自分のGPUの値が表示されます。番号の指定に失敗した場合は、次へ進まず一覧を確認してください。続けて両環境とGPU演算を確認します。

```bash
uv pip check --python "$INFER_PY"
uv pip check --python "$CLIENT_PY"
CUDA_VISIBLE_DEVICES="${GPU_UUID:?Step 2でGPUを選択してください}" "$INFER_PY" -I - <<'PY'
import torch
import lerobot.async_inference.policy_server
assert torch.cuda.is_available(), "CUDA unavailable"
print("GPU:", torch.cuda.get_device_name(0))
print("CUDA calculation:", torch.ones(1, device="cuda").sum().item())
print("SERVER IMPORT AND CUDA: PASS")
PY
"$CLIENT_PY" -I - <<'PY'
import lerobot.async_inference.robot_client
from lerobot.utils.import_utils import register_third_party_plugins
register_third_party_plugins()
print("CLIENT IMPORT: PASS")
PY
```

`pip check`が通っていても任意のextraが揃っているとは限りません。**`grpcio`不足の場合だけ**、次のブロックでclientの既存版を制約として保存してから`async`を追加します。推論側なら同じ方法で`INFER_PY`を対象にします。制約で失敗した場合は、無制約の更新へ切り替える前に依存差分を調べます。

```bash
mkdir -p "$REPO/.runtime"
"$CLIENT_PY" -I - <<'PY' > "$REPO/.runtime/client-before-constraints.txt"
from importlib.metadata import distributions
for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
    print(f'{dist.metadata["Name"]}=={dist.version}')
PY
uv pip install --python "$CLIENT_PY" \
  --constraint "$REPO/.runtime/client-before-constraints.txt" \
  'lerobot[async]==0.6.0'
uv pip check --python "$CLIENT_PY"
```

追加した場合は上のimportを再確認します。次に、**推論用環境でも**収録画像によるオフライン推論を行います。初回はネットワーク接続と08の認証条件を使って必要なキャッシュを取得します。最初の確認が通った後、続くブロックで外部への取得を無効にし、同じcheckpointをオフラインでも読み込めるか確認します。

```bash
INSPECTION="$OUTPUTS/robot_input_check_$(date +%Y%m%d_%H%M%S)"
CUDA_VISIBLE_DEVICES="$GPU_UUID" HF_HUB_CACHE="$MODEL_CACHE" \
  "$INFER_PY" -I "$REPO/scripts/inspect_lerobot_checkpoint.py" \
  --policy "$POLICY_TYPE" --dataset "$DATASET" \
  --checkpoint "$CHECKPOINT" --output "$INSPECTION" --episodes 1
```

```bash
INSPECTION="$OUTPUTS/robot_offline_check_$(date +%Y%m%d_%H%M%S)"
CUDA_VISIBLE_DEVICES="$GPU_UUID" HF_HUB_CACHE="$MODEL_CACHE" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  "$INFER_PY" -I "$REPO/scripts/inspect_lerobot_checkpoint.py" \
  --policy "$POLICY_TYPE" --dataset "$DATASET" \
  --checkpoint "$CHECKPOINT" --output "$INSPECTION" --episodes 1
```

両方で`RECORDED-FRAME CHECK: PASS`が目安です。画像で4視点の対応、CSVで前後処理後のactionを確認します。このPASSは実機のカメラ対応やタスク成功を保証しません。ここまで通ってから、最初の実機確認の条件を決めます。

### Step 3：最初の試行の上限を設定し、実行条件を保存する

ここまでで、実機を動かさずにモデル・入力・GPUを確認しました。次に、**最初の短い実機確認に使う暫定の動作上限**を設定します。タスクを最後まで実行できる最適値を、この段階で確定するわけではありません。

モデルは各関節の目標位置を出力します。`max_relative_target`は、その目標と現在位置の差が大きい場合に、今回送る目標を現在位置の近くへ切り詰める設定です。例えば現在0 rad、モデルの目標0.2 rad、上限0.05 radなら、制限後の目標は0.05 radになります。

| 入力する変数 | 単位・意味 | この教材で試した値 |
|---|---|---|
| `JOINT_CAP` | 各関節の目標差分上限、rad。0.05 radは約2.9度 | 0.05、0.1 rad |
| `GRIPPER_CAP` | gripperの目標差分上限、m。0.01 mは10 mm | 0.01 m |

これは関節の絶対可動域、gripperの最大開口、速度上限の指定ではありません。指令を繰り返せば移動は積み重なり、接続・終了時の姿勢移動も別にあります。小さければ常に安全、大きければ学習動作を正しく再現する、とも限りません。今回も上限が小さい条件ではclampが続いて動作が変わり、0.1 rad条件ではπ₀.₅に激しい動作が見られました。

機体の取扱いを担当者と確認し、開始・終了時に接触しない配置と停止手段を用意してから、短い確認の条件を選びます。まず上限の適用と動作を観察し、変更が必要なら一度終了して第4節に従って調整します。

次は入力方法の例です。0.05と0.01は今回使用した条件の一つであり、すべての装置へ推奨する安全値ではありません。数字だけを入力し、単位は入力しません。

```text
最初の試行の関節目標差分上限（rad）: 0.05
最初の試行のgripper目標差分上限（m）: 0.01
```

```bash
read -r -p "最初の試行の関節目標差分上限（rad）: " JOINT_CAP
read -r -p "最初の試行のgripper目標差分上限（m）: " GRIPPER_CAP
export JOINT_CAP GRIPPER_CAP
```

選んだ上限と、ここまで確認したファイル・GPU・環境を一つのsessionに保存します。sessionは同じ条件で行う試行のまとまりです。

```bash
bash "$REPO/scripts/start_policy_session.sh" &&
source "$REPO/.runtime/policy-session.sh" &&
"$CLIENT_PY" -I "$SESSION_DIR/robot_policy_client.py" \
  --record "$RECORD_CFG" --checkpoint "$CHECKPOINT" --policy "$POLICY_TYPE" \
  --joint-cap "$JOINT_CAP" --gripper-cap "$GRIPPER_CAP" \
  --output "$SESSION_DIR/config-check"
```

`CLIENT CONFIG: PASS (robot not created or connected)`が目安です。`--execute`を付けないため、ここでもロボットは作成・接続しません。不正な数値やモデル種別の不一致なら、実機起動へ進まず指定を確認します。

入力YAML、スクリプト、package一覧、教材とプラグインのcommitを`outputs/robot_trials/session-…/`へ保存します。以後は保存したYAMLとコードを使います。`config-check/requested_limits.json`は指定値の記録で、実機への適用証明ではありません。適用値はStep 5で確認します。

### Step 4：端末Aでserverを起動する

端末A・Bとも、02と同じリポジトリのルートで次を実行します。端末ごとにパスを入力せず、最後に作成したsessionを読み込みます。別sessionを同時に扱う場合は、共通ポインタを使わず対象session内の`session.sh`を明示します。

```bash
source ./scripts/session.sh
source "$REPO/.runtime/policy-session.sh"
```

端末Aでserverを起動します。保存コードは観測類似判定の`atol=0.01`、localhost:8080、30 Hzを使います。

```bash
bash "$REPO/scripts/run_with_log.sh" "$SESSION_DIR/server.log" env \
  CUDA_VISIBLE_DEVICES="$GPU_UUID" HF_HUB_CACHE="$MODEL_CACHE" \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  PYTHONUNBUFFERED=1 \
  "$INFER_PY" -I "$SESSION_DIR/robot_policy_server.py"
```

`PolicyServer started on 127.0.0.1:8080`の後に表示が止まるのはclient待機です。checkpointはclientから指定され、初回接続でロードされます。起動表示だけでモデルロード完了と判断しません。

### Step 5：端末Bでclientを起動する（実機が動く）

端末BでStep 4のsession読込を行います。周辺、開始・終了時の移動経路、停止手段を確認し、他のteleop・record・clientを終了してから実行します。

```bash
RUN=$(mktemp -d "$SESSION_DIR/trial-XXXXXXXX")
printf 'Trial directory: %s\n' "$RUN"
bash "$REPO/scripts/run_with_log.sh" "$RUN/client.log" env PYTHONUNBUFFERED=1 \
  "$CLIENT_PY" -I "$SESSION_DIR/robot_policy_client.py" \
  --record "$RECORD_CFG" --checkpoint "$CHECKPOINT" --policy "$POLICY_TYPE" \
  --joint-cap "$JOINT_CAP" --gripper-cap "$GRIPPER_CAP" \
  --output "$RUN/client" --execute
```

左右の`limits`表示と`client/effective_limits.json`を確認します。factoryで構成した各armへ関節別dictを設定してから接続します。保存`client.yaml`のscalarは生成時の値であり、**実行時の上限はdictの方**です。固定版と双腕WidowX AI向けなので、別のrobot・LeRobot版では構成と接続の順序を確認します。

初回ロードには待ち時間があります。serverのロード・推論、clientの観測送信・指令実行を照合してください。

### Step 6：終了して次の試行を残す

端末BでCtrl+Cし、終了時の姿勢移動が完了したことを確認します。serverも終了する場合はその後に端末AでCtrl+Cします。**Ctrl+C後も初期位置への移動があります。即時停止手段の代わりにはしません。**

同じモデル・条件なら開始条件を戻し、Step 5を繰り返します。試行ごとに別の保存先ができます。上限だけを変更する場合は両プロセスを終了し、Step 3で新しい値を入力して新sessionを作ります。モデル・パス・コードを変える場合は、Step 1から対応する設定と確認をやり直します。ログの上書きを拒否するため、同じserverを再起動する場合も新しいsessionを作ってください。

## 4. 同じ場所を繰り返すときの診断

### 4.1 三つの設定を混同しない

| 設定 | 何を変えるか | 今回の値と注意点 |
|---|---|---|
| serverのobservations_similarのatol | stateに基づく観測の類似判定。画像の類似ではない | 既定値1から0.01へ変更。単位の混在するstateに対する実装の閾値で、関節別の安全値ではない |
| max_relative_target | 現在位置と目標位置の差を切り詰める | 最終条件は関節0.1 rad、gripper0.01 m。速度・絶対可動範囲・衝突回避とは別 |
| relative actionの前後処理 | モデルが学習・予測するactionの表現 | 今回のπ₀.₅は無効。上の制限を変えてもaction表現は変わらない |

今回の非同期設定は30 Hz、50 actions/chunk、chunk_size_threshold 0.5、weighted_averageでした。ロボット設定にはmin_time_to_move_multiplier 3.0、loop_rate 30を使いました。第3節はこれらのロボット設定を収録YAMLから引き継ぐため、YAMLの内容も確認します。設定30 Hzは、全試行で30 Hzを実測保証したという意味ではありません。

### 4.2 症状から、確認する層を絞る

| 症状 | 先に確認するもの | 今回得られた対処・判断 |
|---|---|---|
| async moduleのimportでgrpcio不足 | server/client双方のextra | 通常の依存整合性チェックはPASSでもasyncは不足。既存版を保ちながら追加して双方のimportを確認 |
| CUDA検出は通るが演算できない | GPUとPyTorch build | 収録環境を保ち、対象GPUでCUDA演算が通る推論環境を別に用意 |
| オフライン読込でファイルが見つからない | checkpoint一式、キャッシュ指定、refsと参照先 | tokenizer転送のハッシュが通っても参照が不正なら読めない。実際のロードまで確認 |
| serverの起動表示から進まない | clientを起動したか、初回ロード中か | serverの待機と障害を区別。起動時点ではモデル未ロードの場合がある |
| 接近後に上下動を繰り返す、clamp警告が続く | 予測目標とclamp後の指令、実行時の上限 | 小さなscalar制限が動作を変えていた可能性。関節とgripperを分けて記録・調整 |
| 奥行きがずれる、片指だけ触れる | 画角、開始姿勢、物体配置、収録範囲 | 画像を使っていないとは即断しない。収録範囲内で接触位置を確認 |
| 持ち上げ・輸送中に落とす | 把持の深さ、物体・箱との接触、閉じるタイミング | 輸送中落下と受け渡し失敗を分ける。今回の端を掴むデモは原因候補であり確定原因ではない |
| 大きく振れる、危険な動作が出る | 適用条件、停止方法、接続・終了を含む経路 | 試行を終了して記録する。上限を拡大し続けて解決しようとしない |

診断では一つずつ条件を変え、変更前後の設定と結果を対にして残します。今回の調整は、物体配置・乱数・GPU負荷を固定した対照実験ではありません。観測類似判定の変更だけ、または制限の変更だけが改善原因だったとは確定していません。

### 4.3 調整する場所と再確認する範囲

| 変更したいもの | 編集する場所 | 次に確認すること |
|---|---|---|
| GPU | Step 2のGPU番号入力 | 選択GPUでCUDA演算とモデル再読込を確認 |
| 関節・gripperの目標差分上限 | Step 3の`JOINT_CAP`、`GRIPPER_CAP`入力 | 新しいsessionで左右のlimits表示と短い動作を確認 |
| 独自の環境・checkpoint・キャッシュ | Step 1の上書き指定。checkpointはモデル別設定ファイル、その他は`.runtime/policy-local.sh`にも保存可能 | 対象モデルのオフライン再読込とGPU演算 |
| カメラ・接続先・loop_rate・move multiplier | 対象の収録YAML、または02のローカル設定から生成し直したYAML | まず02の接続・画像確認。収録と推論で対応が変わっていないか |
| 観測類似判定のatol | `scripts/robot_policy_server.py` | 新しいsessionにコードを保存し、状態変化に対する推論の更新を確認 |
| chunk長・threshold・aggregation・fps | `scripts/robot_policy_client.py`のconfig生成部。fpsはserver側も照合 | モデルのchunk設定、消費速度、queueと動作。30 Hzという指定だけで実効周期を保証しない |

元ファイルを変更したらStep 2で影響する部分を確認し、Step 3で新しいsessionを作ります。古いsession内のコピーを編集して過去の条件を書き換えないでください。`client.yaml`のscalarだけを変更しても、起動コードが関節別dictで上書きするため意図した上限にならないことがあります。

## 5. 試行を記録し、成功を定義する

接続経路の完了条件は、観測送信→前後処理を含む推論→指令実行→終了が確認できることです。タスクの完了条件は、その前に別途決めます。箱に入れば成功なのか、受け渡しも必要なのかを試行後に変えません。

今回のデモは「右手で黄色いスポンジボールを把持→箱の上で左手へ受け渡し→左手から箱へ投入」です。task文は`Move the yellow sponge ball into the cardboard box.`でした。本章の**全工程成功**は受け渡しと投入まで行ったものを指します。

自分の試行には次の表を使います。録画した場合は保存名を記入し、ない場合も空欄ではなく「なし」と残します。

| 試行ID・保存先 | モデル・checkpoint | 関節/gripper上限・他の変更 | 開始条件 | 把持 | 輸送 | 受け渡し | 投入 | 手動停止・理由 | 動画・備考 |
|---|---|---|---|---|---|---|---|---|---|
| trial-… | … | … | … | … | … | … | … | … | … |

実行に使ったコード、`client.yaml`、`effective_limits.json`、server/clientのログ、package一覧を同じsessionに対応づけます。起動例のコピーも保存してください。設定の保存だけでは、コード中の上書きを復元できないことがあります。初期姿勢と配置を数値で固定しない場合は、写真や「収録範囲内／外」の説明を残します。

### 5.1 今回の学習条件と結果

同じ50 episode・29,947 frame・30 Hz・4 RGB画像・14次元state/actionのDatasetで、両モデルをseed 1000、batch 8、20,000 step学習しました。20K checkpointと保存された前後処理を実機に使いました。

| 学習設定 | SmolVLA | LeRobot版π₀.₅ |
|---|---|---|
| freeze_vision_encoder / train_expert_only | true / true | true / true |
| state/action正規化 | MEAN_STD | QUANTILES |
| action表現の設定 | ALOHA用delta joint変換なし | use_relative_actions=false |
| chunk_size / n_action_steps | 50 / 50 | 50 / 50 |

同名flagでも更新されるparameter集合は実装ごとに異なります。同じbatch・stepでもoptimizerや正規化が異なるため、lossを直接比較してモデルの優劣を決めません。LeRobot版π₀.₅の結果を、openpiの公式手法全体の結果ともみなしません。

以下は実行者の観察報告です。全試行の映像と完全なログを揃えた独立評価ではありません。

| モデル | 関節上限 / gripper上限 | 試行数 | 観察結果 |
|---|---|---:|---|
| SmolVLA | 0.05 rad / 0.01 m | 5 | 把持成功なし。位置ずれ、閉じきらないように見える動作 |
| π₀.₅ | 0.05 rad / 0.01 m | 5 | 3回は把持・輸送開始後に落下。全工程成功なし |
| SmolVLA | 0.1 rad / 0.01 m | 3 | 3回とも把持。全工程成功2回、把持後落下1回。成功の1回は落下後に再試行 |
| π₀.₅ | 0.1 rad / 0.01 m | 3 | 受け渡し失敗、激しい動作による早期終了、ボールを弾く動作。全工程成功なし |

SmolVLAの成功2回はいずれも受け渡し・投入まで実行しました。落下後に少しずれたボールへの追従も観察されました。π₀.₅には予備試行で箱へ落とした例がありますが、受け渡しは失敗し、試行の分母も不明なため上表と合算しません。

初期SmolVLAではscalar 0.005/0.01とclamp警告を確認し、その後関節0.05、0.1 radへ調整しました。小さな指令制限が学習動作を変え、モデルの失敗のように見える場合がある、という診断の実例です。成功2/3を一般的な成功率、「小型モデルは少数データに強い」を証明する比較実験として使いません。今回の構成ではSmolVLAが学習から実機まで通した最初の実例になる、という範囲で使います。

π₀.₅の0.05条件では、参照できる記録から関節別上限は確認できますが、起動設定全体は確認できていません。また、全試行とログの対応も完全ではありません。このため、上表は実行者の観察結果として扱い、全条件を固定した再現可能な性能比較とは区別します。

## 6. ここから自分の研究へ進む

| 研究で確かめたいこと | 本章から引き継ぐ確認 | 次に変更・評価するもの |
|---|---|---|
| カメラ追加で接触位置を改善したい | 既存視点の対応、収録範囲内の位置ずれ | [03](03_architecture_and_extension.md)で収録・同期、[10](10_stack_decisions_and_extension.md)でmodel inputと推論入力の変更箇所を確認 |
| 力覚・触覚で落下を減らしたい | 把持・輸送・受け渡しのどこで失敗したか | 接触・滑りを観測できるsensor、同期方法、学習入力。センサを保存しただけではモデルへ入らない |
| action生成や実行方法を変えたい | 予測actionとclamp後の指令の違い | chunk、aggregation、action表現の変更を分け、介入回数や落下後の再試行を評価 |
| 別モデル・実行系を使いたい | 入出力の意味と前後処理、実機側の接続境界 | [07](07_vla_model_selection.md)・[10](10_stack_decisions_and_extension.md)でデータ形式・専用実行系・資源を照合 |

本章を終えた時点では、自分のcheckpointと装置を結び、失敗した段階を説明できれば実行経路の確認になります。安定した成功率、未知配置への汎化、言語指示切替、モデルの性能順位は別の研究課題です。新しいセンサやモデルを追加する際は[05](05_maintenance.md)に従い、変更が影響する経路を再確認します。
