# 08 自分で収録したデータから学習・オフライン推論へ

[02 データ収集](02_data_collection.md)で得た**自分のLeRobotDataset v3**を、まず検証し、次にVLAの入力へ渡します。02の最後で収録した`data/aloha_vla_demo`を本章と[09](09_openvla_oft_data_bridge.md)の共通例にします。[07](07_vla_model_selection.md)はモデル選定の教材です。この章はLeRobot版π₀.₅の実習AとSmolVLAの実習Bです。実機成功例を入口にする場合は第3節のSmolVLAから始められます。実習の掲載順は性能順位ではありません。どちらも学習後の重みを別プロセスで読み、収録済み観測からactionを出すところまで扱います。この章ではロボットへの指令送信は扱いません。

データは各自が[02](02_data_collection.md)で収録したものを使います。`first_demo`は収録確認用、`aloha_vla_demo`は以後の学習・推論に使うデモです。episode数は成功率の目標値ではありません。最初の3-step学習は経路の確認で、技能の獲得を測るものではありません。


> **動作確認の範囲**：SmolVLAとLeRobot版π₀.₅は、収録済みデータによる短い学習・checkpoint再読込・オフライン推論を確認しています。Ubuntu 22.04.5のRTX A6000ワークステーションで、教材の新規取得とPython 3.12.13の仮想環境作成後、版指定したコマンドでπ₀.₅の3-step、SmolVLAの3・200-step学習からcheckpoint再読込・オフライン推論まで再確認しました。既存OS・uv・認証・キャッシュは利用しており、OSを含むクリーン環境の検証ではありません。その後の20K checkpointを使った実機接続とタスク結果は[11](11_robot_policy_execution.md)に記録しています。短い学習の性能評価と、未構築環境から実機までの一括再現はしていません。

### 収録済みデータを別の学習PCで使う

ロボットを接続していないGPU搭載PCでも、本章を実行できます。02のStep 1でソフトウェア環境を準備し、収録済みDatasetのディレクトリ全体をコピーするか、読める場所へ置きます。Armのdiscover・identify、teleoperationはこの学習PCでは不要です。`validate_dataset.sh`はcamera名を記録templateから読み、実機のIP・serial設定を要求しません。

開始前に[02の作業場所の設定](02_data_collection.md#作業場所の設定)を行います。02から同じ端末で続ける場合は設定済みです。

### 学習に使うデータの場所を指定する

ここから収録済みのデータを使います。`DATASET`は入力データのディレクトリ、`OUTPUTS`は学習結果の保存先です。初期値はそれぞれ`$REPO/data/aloha_vla_demo`と`$REPO/outputs`です。02で教材内の`data/aloha_vla_demo`に収録した場合は、そのまま次の節へ進めます。

教材の外に保存したデータや、別の名前で収録したデータを使う場合だけ、次を実行して実際のディレクトリを入力してください。「教材の外」は保存場所の意味で、ALOHAで収録して別の学習PCに移したデータも含みます。取得元による区別ではありません。フォルダ名の変更は不要で、収録PCと同じ絶対パスも要求しません。パスに空白があっても引用符は入力しません。

```bash
read -r -p "Datasetのディレクトリ: " DATASET
export DATASET
test -d "$DATASET"
```

最初の`read`で`Datasetのディレクトリ: `と表示され、入力待ちになります。処理が止まったように見えてもエラーではありません。収録時に指定した名前のフォルダまで含むパス全体を入力し、Enterを押してください。例えば、`/mnt/data/yellow_ball_box_demo`に保存した場合の端末表示は次のようになります（表示例なので実行しません）。

```text
Datasetのディレクトリ: /mnt/data/yellow_ball_box_demo
```

入力後、`export`でそのパスを後続の処理へ渡せるようにし、`test -d`でディレクトリの存在を確認します。最後の2行がまだ実行されていなければ、順に実行してください。`export`と`test -d`は通常、何も表示しません。**何も表示されないだけでは、存在確認に成功したかは分かりません。** `test -d`の直後に次を実行すると結果を確認できます。

```bash
echo "$?"
```

`0`ならディレクトリが存在し、`1`なら存在しません。`1`の場合はパスやデータのコピー先を確認し、上の入力からやり直してください。ここではディレクトリの存在だけを確認し、Datasetの内容は次の節で検証します。学習結果を別の場所に保存したい場合だけ、同じ端末で次を実行します。保存先は後の学習処理で作成されるため、今は存在しなくても構いません。

```bash
read -r -p "学習結果の保存先ディレクトリ: " OUTPUTS
export OUTPUTS
```

保存先の入力例は`学習結果の保存先ディレクトリ: /mnt/data/aloha_outputs`です。表示された問いにパスを入力してEnterを押します。入力待ちの間に次のコマンドをパスとして入力しないようにしてください。

入力した値は同じ端末で08・09へ引き継ぎます。`session.sh`を再度sourceしても保持されます。新しい端末では作業場所の設定後、この節で入力先・保存先を指定し直してください。

## 学習ログを保存する

以下の学習コマンドは付属の`run_with_log.sh`を経由し、端末への表示と同時に`$OUT.log`へ標準出力・標準エラーを保存します。モデルの保存先`$OUT`とは別のファイルなので、LeRobotが新規出力先を要求する条件を変えません。例えば`$OUT`が`outputs/smolvla_4cam_tutorial_200steps`なら、ログは`outputs/smolvla_4cam_tutorial_200steps.log`です。

ログには開始・終了のUTC時刻と終了コードも残します。学習側またはログ書込みが失敗すれば、コマンドも失敗として終了します。同名ログが既にあると上書きせず停止するので、新しい実験には別の`OUT`を指定します。学習の引数・環境・作業場所は変えません。

checkpointには重み・学習設定・再開用状態が保存されますが、loss履歴の自動保存とは別です。W&Bを無効にした場合もこのログは残ります。tmuxはSSH切断後の継続に使い、ログ保存と併用します。学習後はログの終了コードと`End of training`、checkpoint生成、別プロセス再読込を確認してください。新しい端末では作業場所とDatasetを指定し直します。

## まず自分のdatasetを確認する

02の`./record.sh`で作成した実習用datasetを、次のように確認します。別の作業を収録した場合は、自分が付けた名前とタスク文に置き換えてください。

```bash
cd "$REPO"
test -d "$DATASET"
./validate_dataset.sh "$DATASET"
cd lerobot_trossen
DATASET="$DATASET" uv run python - <<'PYCODE'
import os
from pathlib import Path
from lerobot.datasets.lerobot_dataset import LeRobotDataset

root = Path(os.environ["DATASET"])
ds = LeRobotDataset(repo_id=f"local/{root.name}", root=root)
sample = ds[0]
print("episodes:", ds.meta.total_episodes)
for key in ("action", "observation.state"):
    print(key, tuple(sample[key].shape))
print("images:", {key: tuple(value.shape) for key, value in sample.items()
                  if key.startswith("observation.images.")})
print("task:", sample["task"])
PYCODE
```

この確認が通れば、第2・3節のコマンドには同じ`data/aloha_vla_demo`を渡します。画像が4種類、`observation.state`と`action`が各14次元という本教材の前提も確認してください。収録データの名前やshapeが異なる場合は、該当するパスとモデル設定を合わせます。

## 1. 実習用データと運用時のデータ選別

### 1.1 この実習で行うこと

[02](02_data_collection.md)で収録した`data/aloha_vla_demo`を、学習とオフライン推論の両方に使用します。**データセットを複製・分割する操作は、この実習には含めません。** 最初の3ステップの学習は、データを読み、重みを更新して保存し、再読込できるかを確かめるためのものです。同じデータからactionが出ても、未知の配置への対応やタスクの成功率は評価できません。

データの内容が学習の実行可否に無関係という意味ではありません。動画が読めること、画像や関節値のshape・値域・時刻が妥当なこと、task文があることを確認します。一方、成功デモだけで構成されているか、開始位置がどれほど多様かによる**方策の有用性**は、この短い接続試験では判定しません。

動画の分割位置がカメラ間で違っても、LeRobotDataset v3のmetadataを通してepisodeとframeが読めるなら、MP4を手で結合する必要はありません。画像4キー、`observation.state`と`action`各14次元、task文、fps、episode境界を`meta/info.json`とloaderで照合します。ただしshapeだけでは左右関節の順序、単位、グリッパ表現、absoluteかdeltaかは分かりません。

### 1.2 実運用で学習用データを整える場合（参考）

タスクの模倣や性能評価を目的にする場合は、元の収録データを残し、episodeごとに成功・失敗と開始状態を確認します。Behavior Cloningでは通常、記録された行動そのものが教師信号です。成功／失敗のラベルを学習器が利用しなければ、失敗デモも模倣対象になります。成功デモのみを使う方針なら、元データとは別の場所に学習用datasetを作り、除外したepisode番号と理由を記録します。その場合に限り、第2節以降の`DATASET`を派生datasetのrootに変更します。**本実習のコマンドをそのまま実行する場合は変更しません。**

一方、失敗後の回復を学習したい場合は、失敗を混ぜるだけでなく、どの区間をどの目的で学習するかを決め、選んだ方策がその情報を使えるか確かめます。開始時のグリッパ状態が一部だけ違う場合も、それだけで除外せず、運用中に起こり得る状態か、観測に記録されているかを確認します。

未知の配置での成功率を測る場合は、学習に使わない評価用episodeを条件を決めて別途収録します。オフラインで保存済み観測を1フレーム読み、有限値のactionを得る本実習とは異なる評価です。データ選別・評価設計は研究や用途に合わせて実施してください。

## 2. 実習A：LeRobot版π₀.₅

同じ端末では、冒頭で設定した`DATASET`を実習Bにも引き継ぎます。新しい端末では02の作業場所の設定と、本章冒頭のデータの場所の指定を行い直してください。次は入力先が存在するかの確認で、値を上書きしません。

```bash
test -d "$DATASET"
```

π₀.₅の学習コマンドは[02](02_data_collection.md)で作成した`lerobot_trossen`で実行します。`DATASET`には第1節と同じ`aloha_vla_demo`を指定します。例はALOHAの4 RGB画像（424×240、30 fps）、14次元の関節状態・行動を前提にします。画像キーや次元が異なる場合は先にモデルの設定と照合してください。

学習・オフライン推論の確認に使用した条件はUbuntu 22.04.5、Python 3.12、LeRobot 0.6.0、PyTorch 2.7.1+cu126、GPU 48 GBのRTX A6000です。GPU条件が異なる場合はメモリ消費を測ってください。

確認時の主要依存は以下のとおりです。これは実行環境の記録であり、全依存を再構築するlockではありません。`uv run --with`で追加した依存は基準環境と異なる場合があるため、学習・推論を実行する環境で版を確認してください。

| 依存 | 確認時の版・経路 |
|---|---|
| LeRobot | 0.6.0 |
| PyTorch | 2.7.1+cu126 |
| accelerate | 1.15.0 |
| transformers | 5.5.4（SmolVLA経路） |
| safetensors | 0.6.2（SmolVLA経路） |


### 2.1 基盤重みの利用許可とログイン

π₀.₅は画像と言語を扱うVLMに行動生成のexpertを組み合わせた系列です。[07のVLA解説](07_vla_model_selection.md#2-この教材で扱うvlaの経路)を参照しながら、事前学習済みVLAの入力・正規化・保存・推論までを追います。SmolVLAは第3節で同じデータを使う第二経路として扱います。この実習で使うのは**LeRobotのπ₀.₅実装**です。πシリーズの開発元Physical Intelligenceが公開する`openpi`とは学習環境とデータ設定が異なります。[LeRobot公式のπ₀.₅解説](https://huggingface.co/docs/lerobot/pi05)も参照してください。

π₀.₅の基盤重みを取得する前に、[PaliGemmaのモデルページ](https://huggingface.co/google/paligemma-3b-pt-224)で利用条件に同意し、同じHugging Faceアカウントで学習環境を認証します。ページを開くだけでは同意は完了しません。

1. Hugging Faceにログインしてモデルページを開き、表示された利用条件を読み、アクセス申請または同意ボタンを押します。アクセスが許可されたことを同じアカウントで確認します。
2. [Access Tokens](https://huggingface.co/settings/tokens)から**Read** tokenを発行します。Fine-grained tokenを選ぶ場合は対象のgatedモデルを読む権限を含めます。Hubへの重みのアップロードは本実習では無効なのでWrite権限は不要です。
3. 学習に使う端末で次を実行し、tokenを対話式プロンプトに貼ります。tokenをコマンドライン引数、スクリプト、Gitへ書き込まないでください。

```bash
cd "$REPO/lerobot_trossen"
uv run --with 'lerobot[pi]==0.6.0' hf auth login
uv run --with 'lerobot[pi]==0.6.0' hf auth whoami
```

ブラウザで同意したアカウントが`whoami`に表示されたら、次の小さなファイルでアクセスの入口を確かめます。

```bash
uv run --with 'lerobot[pi]==0.6.0' python - <<'PYCODE'
from huggingface_hub import hf_hub_download
p = hf_hub_download('google/paligemma-3b-pt-224', 'config.json')
print('PaliGemma access:', p)
PYCODE
```

`401`・`403`やgated repositoryのエラーなら、**モデルページの同意、CLIでログインしたアカウント、tokenのRead権限**をこの順に見直します。ログインだけでは利用条件への同意になりません。`config.json`の取得は大きな重みのダウンロードや学習が最後まで通る保証ではなく、次の短い学習で実際に確認します。

### 2.2 データ統計と計算機の確認

π₀.₅では`meta/stats.json`の`action`と`observation.state`に`q01`と`q99`が必要です。次のコマンドで自分のdatasetを確認します。不足している場合は[LeRobotのπ₀.₅資料](https://huggingface.co/docs/lerobot/pi05)の統計生成方法を調べてから学習します。

```bash
DATASET="$DATASET" python3 - <<'PYCODE'
import json, os
from pathlib import Path
stats = json.loads((Path(os.environ['DATASET']) / 'meta/stats.json').read_text())
for name in ('action', 'observation.state'):
    assert {'q01', 'q99'} <= stats[name].keys(), name
print('quantile stats: PASS')
PYCODE
```

GPUの空きメモリは`nvidia-smi`で確認します。次の例はbatch 1、BF16、gradient checkpointing、vision encoder freezeでメモリ消費を抑えます。別のGPUや長時間学習まで同条件で実行できるとは限りません。

### 2.3 短い学習とcheckpoint保存

```bash
cd "$REPO/lerobot_trossen"
OUT="$OUTPUTS/pi05_4cam_smoke"

bash "$REPO/scripts/run_with_log.sh" "$OUT.log" uv run --with 'lerobot[pi]==0.6.0' --with accelerate==1.15.0 lerobot-train \
  --dataset.repo_id="local/$(basename "$DATASET")" \
  --dataset.root="$DATASET" \
  --policy.type=pi05 \
  --policy.pretrained_path=lerobot/pi05_base \
  --policy.device=cuda \
  --policy.dtype=bfloat16 \
  --policy.gradient_checkpointing=true \
  --policy.freeze_vision_encoder=true \
  --policy.train_expert_only=true \
  --policy.push_to_hub=false \
  --output_dir="$OUT" \
  --job_name=pi05_4cam_smoke \
  --steps=3 \
  --batch_size=1 \
  --num_workers=0

test -f "$OUT/checkpoints/000003/pretrained_model/model.safetensors"
```

これは**基盤重みを読み、3回更新して保存する接続試験**です。`accelerate`がないと学習が開始できません。Trossenプラグインには`training` extraがないため、コマンドの`--with accelerate`を使います。`transformers`だけを単独で最新版に更新すると、lock内の`safetensors`と依存が衝突する場合があります。環境で実際に選ばれたパッケージ版と`train_config.json`を保存してください。LeRobotとaccelerateの指定だけでは、追加依存の全体や基盤重みのrevisionまでは固定しません。再現や研究比較には、実際の実行環境と使用した基盤重みのrevisionも記録してください。

**確認の目安：** 3-step終了後に`checkpoints/000003/pretrained_model/`ができ、再ロードできること。確認に使ったπ₀.₅ checkpointは約8.8 GBでした。保存容量はGPUの必要量や習得した技能を意味しません。

### 2.4 保存したπ₀.₅を別プロセスで確かめる

次のコードは同じ`aloha_vla_demo`から1フレームを取り、保存済みpolicyと前後処理を読み直します。成功率計算ではありません。`CHECKPOINT`の出力先を自分の場所に合わせます。

```bash
cd "$REPO/lerobot_trossen"
CHECKPOINT="$OUTPUTS/pi05_4cam_smoke/checkpoints/000003/pretrained_model"

CHECKPOINT="$CHECKPOINT" DATASET="$DATASET" \
uv run --with 'lerobot[pi]==0.6.0' --with accelerate==1.15.0 python - <<'PYCODE'
import os
from pathlib import Path
import torch
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.policies import make_pre_post_processors
from lerobot.policies.pi05 import PI05Policy

checkpoint = Path(os.environ["CHECKPOINT"])
dataset = LeRobotDataset(
    repo_id="local/" + Path(os.environ["DATASET"]).name,
    root=Path(os.environ["DATASET"]),
)
policy = PI05Policy.from_pretrained(checkpoint)
policy.to("cuda").eval()
pre, post = make_pre_post_processors(
    policy_cfg=policy.config,
    pretrained_path=checkpoint,
    preprocessor_overrides={"device_processor": {"device": "cuda"}},
)
frame = dict(dataset[0])
batch = {k: v.unsqueeze(0) if isinstance(v, torch.Tensor) else [v]
         for k, v in frame.items()}
with torch.inference_mode():
    action = post(policy.select_action(pre(batch)))
assert action.shape == (1, len(frame["action"])), action.shape
assert torch.isfinite(action).all()
print("Input features:", list(policy.config.input_features))
print("Postprocessed action shape:", tuple(action.shape))
print("PI05 OFFLINE INFERENCE: PASS")
PYCODE
```

出力にstateと4画像の入力キー、`(1, 14)`の有限値が表示されることを確かめます。vision embeddingの警告が出る場合は重みの読込成否と実行結果を見分けます。単位、関節順序、absolute/delta actionの一致はshape検査だけでは分かりません。

## 3. 実習B：SmolVLA

第2節の学習環境と同じデータを使います。必要な追加依存、モデル構成、checkpointの大きさを比べながら、stateとactionがどこでモデルに入出力されるかを確認してください。

### 3.1 学習前の確認

次のコマンドは、Trossen統合リポジトリ上でLeRobotのSmolVLA追加依存を実行環境に解決し、`DATASET`で3ステップ学習する第二実習です。3ステップは学習性能を見る長さではなく、データとモデルの互換性・GPU実行・チェックポイント保存を短時間で確認します。

```bash
cd "$REPO/lerobot_trossen"

OUT="$OUTPUTS/smolvla_4cam_smoke"

bash "$REPO/scripts/run_with_log.sh" "$OUT.log" uv run --with 'lerobot[smolvla]==0.6.0' lerobot-train \
  --dataset.repo_id="local/$(basename "$DATASET")" \
  --dataset.root="$DATASET" \
  --policy.path=lerobot/smolvla_base \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --policy.input_features=null \
  --policy.output_features='{"action":{"type":"ACTION","shape":[14]}}' \
  --output_dir="$OUT" \
  --job_name=smolvla_4cam_smoke \
  --steps=3 \
  --batch_size=1 \
  --num_workers=0
```

`--policy.input_features=null` によりデータセットの特徴からカメラ名・stateを読み取ります。出力のaction次元はこのALOHAデータに合わせて14に指定します。データの特徴や行動次元が異なる案件では、14をそのまま流用しません。

**通過判定：** 終了コードが0で、出力先に `checkpoints/000003/pretrained_model/` とモデル重みができること。標準エラーに不足依存が出た場合は、無関係な最新版を単独で追加インストールするのではなく、追加依存を含めた同じ実行環境の解決を確認します。

### 3.2 教材用の学習を実行する

smoke runが通ったら、短い教材学習を実行します。ここでは200ステップの出力チェックポイントを作成します。出力ディレクトリは実行ごとに分け、前のrunを上書きしません。

```bash
OUT="$OUTPUTS/smolvla_4cam_tutorial_200steps"

bash "$REPO/scripts/run_with_log.sh" "$OUT.log" uv run --with 'lerobot[smolvla]==0.6.0' lerobot-train \
  --dataset.repo_id="local/$(basename "$DATASET")" \
  --dataset.root="$DATASET" \
  --policy.path=lerobot/smolvla_base \
  --policy.device=cuda \
  --policy.push_to_hub=false \
  --policy.input_features=null \
  --policy.output_features='{"action":{"type":"ACTION","shape":[14]}}' \
  --output_dir="$OUT" \
  --job_name=smolvla_4cam_tutorial_200steps \
  --steps=200 \
  --batch_size=1 \
  --num_workers=0
```

データから学習・保存・再読込まで接続する、再現用の**小さな学習演習**です。標準的な収束条件や十分な性能を示すものではありません。ステップ数だけを増やしても、データの多様性、評価設計、行動表現の不一致は解決しません。

### 3.3 チェックポイントを読み戻し、オフライン推論する

学習が終わったら、学習中のメモリ上のモデルを使い回すのではなく、保存先の `pretrained_model` から再ロードします。別プロセスで指定したepisodeを読み込み、前処理後に推論したactionが存在し、すべて有限値かを確認します。

```bash
cd "$REPO/lerobot_trossen"
CHECKPOINT="$OUTPUTS/smolvla_4cam_tutorial_200steps/checkpoints/000200/pretrained_model"

CHECKPOINT="$CHECKPOINT" DATASET="$DATASET" uv run --with 'lerobot[smolvla]==0.6.0' python - <<'PYCODE'
import os
from pathlib import Path

import torch
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.policies import make_pre_post_processors
from lerobot.policies.smolvla import SmolVLAPolicy

checkpoint = Path(os.environ["CHECKPOINT"])
dataset_root = Path(os.environ["DATASET"])
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

dataset = LeRobotDataset(
    repo_id="local/" + Path(os.environ["DATASET"]).name,
    root=dataset_root,
)
policy = SmolVLAPolicy.from_pretrained(checkpoint)
policy.to(device).eval()
preprocessor, postprocessor = make_pre_post_processors(
    policy_cfg=policy.config,
    pretrained_path=checkpoint,
    preprocessor_overrides={"device_processor": {"device": str(device)}},
)

frame = dict(dataset[0])
batch = {
    key: value.unsqueeze(0) if isinstance(value, torch.Tensor) else [value]
    for key, value in frame.items()
}
with torch.inference_mode():
    batch = preprocessor(batch)
    action = policy.select_action(batch)
    action = postprocessor(action)

assert action.shape == (1, len(frame["action"])), action.shape
assert torch.isfinite(action).all(), "Action contains NaN or Inf"
print("Input features:", list(policy.config.input_features))
print("Postprocessed action shape:", tuple(action.shape))
print("All action values finite: True")
print("OFFLINE INFERENCE CHECK: PASS")
PYCODE
```

このスクリプトはチェックポイントを再ロードし、指定したdatasetの最初の観測フレームを4画像・state・タスク文のバッチにして推論します。4カメラとstateが入力になり、action `(1, 14)` の有限値を返すことを確かめます。この観測は学習にも使ったデータなので、未知条件での評価にはなりません。正しい軌道を予測すること、ブロックをトレイに置けること、物理的に安全な制御であることは確認していません。

> **安全境界**：オフライン推論で得たactionを、そのままロボットに送ってはいけません。実機実行には、ロボット用環境・カメラ入力・関節順序・単位・action chunkの実行方法・速度や範囲の制限・非常停止を確認する別のデプロイ手順が必要です。本章のオフライン推論は実機ポリシー実行を含みません。実機で確認した接続・調整・終了動作は[11](11_robot_policy_execution.md)を参照してください。

## 4. センサ収録から研究へ

センサ追加の必要性と効果を示す比較の考え方は[10の第3・4節](10_stack_decisions_and_extension.md)を参照します。以下は変更箇所を調べるための境界で、融合の有効性を実証した手順ではありません。

[03 外部センサの追加](03_architecture_and_extension.md)では力覚や触覚を取得・時刻対応させるまでを扱います。**記録しただけでモデルの入力にはなりません。** 例えば右手の力覚を使って把持を変える研究では、次の順に境界を確認します。

| 段階 | 学生が確認すること | 境界を越えた証拠 |
|---|---|---|
| 取得と同期 | いつ・どのarmで測ったか、画像・stateと時刻が対応するか | episodeを指定して同時刻の観測を読める |
| dataset表現 | `observation`のfeature名、単位、欠損と間引きの扱い | training sampleで予想した値とshapeになる |
| 前処理 | stateへ連結するか、時系列窓や触覚画像を別に扱うか | normalizerとbatch作成後にもfeatureが残る |
| モデル | 数値stateで足りるか、専用encoder/projectorが必要か | forwardとlossにセンサ入力が実際に入る |
| 推論と実機 | 収録時と同じ順序・同期・単位で取得できるか | 実機の入力経路と出力制限を確認できる |

14次元stateに新しい数値を連結してモデルの最大次元内に収める方法は**実装上の候補**ですが、学習済みVLAが力覚の意味を理解する保証はありません。GelSight画像を一般画像として入力する案も、触覚専用の表現学習とは異なります。時系列の力覚には一枚の観測だけでは足りない可能性があります。これらは研究の設計分岐です。4カメラの学習演習だけで力覚・触覚入力の有効性は分かりません。

研究でセンサを増やす際は、この表のどの段階から自分で設計する必要があるかを見極めてください。特に、`LeRobotDataset`から値を読めるだけでは、学習時の入力や実機推論時の入力に同じ情報が入るとは限りません。

## 5. 実機推論へ進むとき

本章のチェックポイントから数値のactionが出ても、実機で繰り返し閉ループ制御できたことにはなりません。[Trossen公式の学習・評価](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot_plugin/train_and_evaluate.html)および[非同期推論](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot_plugin/async_inference.html)を参照し、利用するロボットの接続、4カメラの対応、task文、前後処理、関節順序・単位・指令範囲、停止手段を一つずつ確認します。最初は物体や周辺との接触を避けられる条件から始めます。SmolVLAとLeRobot版π₀.₅の20K checkpointによる実機動作は[11](11_robot_policy_execution.md)で確認した条件と結果を記録しています。自分の装置では公式手順と11の差分を照合してから進めます。

固定版の[robot client](https://github.com/huggingface/lerobot/blob/v0.6.0/src/lerobot/async_inference/robot_client.py)は初期化でロボットへ接続します。[Trossen follower](https://github.com/TrossenRobotics/lerobot_trossen/blob/a4336933f34192a3daa7e9fb52674284bb5ae48e/packages/lerobot_robot_trossen/src/lerobot_robot_trossen/widowxai_follower.py)は接続時に所定姿勢へ移動し、終了時にも所定姿勢とsleep位置へ移動します。接続や終了だけの確認にも動作を伴うため、開始・終了姿勢と周辺空間を確認します。`max_relative_target`は現在位置からの目標差を制限するもので、絶対位置の制限や衝突回避ではありません。関節とgripperで単位が異なり、初期化・終了の移動も別経路なので、公式例の単一数値を安全値として流用しません。

実機では次の順に確認し、設定変更と結果を記録します。

1. checkpointの前後処理、Datasetのfeature名、実機のカメラ名・配置、関節順・単位・絶対位置か差分かを照合する。
2. GPUの現在の空きとモデル読込、観測取得、推論時間、chunkの実行方法と停止手段を確認する。まず実機側PCでの推論経路を検討し、別PCを使う場合は通信遅延・欠損・切断時の挙動も測る。
3. 接続・開始・停止・終了の動作を段階的に確かめてから、対象物を使う試行へ進む。観測や推論が停止したときの挙動を確認する。
4. タスクの成功条件、初期配置、終了条件、試行数を先に決め、成功・失敗・途中停止/介入と動画・ログを残す。モデルごとに条件を揃える。

| 記録項目 | 内容 |
|---|---|
| 実行条件 | model・checkpoint・commit、GPU、学習step/batch、Dataset、カメラ、fps、chunk実行長 |
| 試行条件 | 対象物の初期位置、指示文、開始姿勢、成功条件、終了条件 |
| 結果 | 成功数/試行数、停止/介入数、失敗の種類、動画・ログ |
| 実行系の違い | 初回/継続時の推論時間、画像取得不足、設定変更と理由 |
| 評価の限界 | 同一配置だけか、新配置や指示文切替を含むか |


## 6. 実習を終えて次へ進む

学習コマンドが終了したら、自分の結果を次の順序で確かめます。

1. **データ**：`validate_dataset.sh`が通り、`LeRobotDataset`の表示で画像、`observation.state`、`action`、タスク文とepisode数を説明できる。実習では`aloha_vla_demo`をそのまま使う。
2. **学習**：出力先に`checkpoints/<step>/pretrained_model/`があり、どのdatasetと基盤重みを使ったか`train_config.json`で確認できる。3ステップの学習は、長い実習へ進むための接続試験として読む。
3. **オフライン推論**：別プロセスで保存したpolicyと前後処理を読み、指定した観測から想定した次元の有限値のactionを得られる。学習に使ったデータを再利用した場合は、未知条件での評価とは呼ばない。

ここまで進んだら、[07の選定例](07_vla_model_selection.md)から自分の問いに近い候補を選びます。言語指示の切替え、追加センサ、行動生成法の改良では、次に変更する場所が異なります。実機で動かす場合は第5節の公式経路へ進み、ロボット側の入力とactionの意味を確かめます。**数値のactionが出たことだけではタスク成功や安全な実機動作は分かりません。**

## 7. 追加学習とcheckpointを比較する

### 7.1 追加確認した条件

2026年10月5日、50 episode・29,947 frame・30 Hz、4画像、14次元state/actionの収録データを使い、SmolVLAをbatch 8・20,000 stepで学習しました。学習ループは3時間18分44秒、ログ上160K sample・5.34 epoch、最終表示lossは0.040でした。これは1台のRTX A6000で得た実測例で、他のGPUの必要時間やタスク成功の保証ではありません。

保存した`checkpoints/020000/pretrained_model`を別プロセスで読み直し、10 episodeから先頭・中間・末尾の計30観測を独立に推論し、有限な`(1,14)`を確認しました。下の補助コードの推論区間は初回0.712秒、その後0.177〜0.184秒でした。毎回`policy.reset()`する計測のため、実機の制御周期やchunk消費速度と同一ではありません。30観測の4視点画像を目視し、CSVの全420行の有限値・差分と、比較するcheckpoint間で収録action/stateが一致することも確認しました。画像の低位置視点では箱による遮蔽が多く見られます。視点ごとの性能への寄与と実機対応は別の検証項目です。

2026年10月6日、π₀.₅のbatch 8・20K stepのcheckpoint保存と、同じ30観測での別プロセス再読込・有限な`(1,14)`を確認しました。推論区間は初回0.534秒、以降の29観測の中央値は0.251秒でした。学習完了と所要時間約18時間は実行者からの報告です。当時W&Bが無効で端末出力も保存していなかったため、正確な開始・終了時刻、最終lossとloss履歴は未記録です。SmolVLAのログや曖昧なlossの記憶から補いません。約18時間はSmolVLAのログで測った学習ループ時間とは計測精度が異なり、厳密な速度比較には使いません。以後の学習は本章のログ保存手順を使います。

### 7.2 追加学習のcheckpointを11へ渡す

3-step・200-stepは実行経路の確認です。今回の実機評価には20K checkpointを使いました。新しく同じ学習予算を使う場合は、次の組立例を使えます。既存checkpointを使う場合は学習し直さず、11のStep 1で参照先を指定します。学習時間の実測例は7.1、条件と性能評価の限界は11を参照してください。

次の例は第7.1節の20K学習条件に合わせたものです。学習条件の実行実績はありますが、このコマンド列そのものの20K実行は未確認です。最初に短い学習を通し、保存設定を照合してから長い学習へ進みます。SSHを切る予定がある場合は、事前にtmux等の切断後も残る端末を使います。

```bash
export POLICY_TYPE=smolvla
cd "$REPO/lerobot_trossen"
OUT="$OUTPUTS/${POLICY_TYPE}_4cam_20k"
test ! -e "$OUT"
case "$POLICY_TYPE" in
  smolvla)
    RUN_DEPS=(--with 'lerobot[smolvla]==0.6.0')
    POLICY_ARGS=(--policy.path=lerobot/smolvla_base
      --policy.input_features=null
      '--policy.output_features={"action":{"type":"ACTION","shape":[14]}}'
      --policy.freeze_vision_encoder=true --policy.train_expert_only=true
      --policy.train_state_proj=true)
    ;;
  pi05)
    RUN_DEPS=(--with 'lerobot[pi]==0.6.0' --with accelerate==1.15.0)
    POLICY_ARGS=(--policy.type=pi05 --policy.pretrained_path=lerobot/pi05_base
      --policy.dtype=bfloat16 --policy.gradient_checkpointing=true
      --policy.freeze_vision_encoder=true --policy.train_expert_only=true
      --policy.use_relative_actions=false)
    ;;
  *) printf 'Unsupported policy: %s\n' "$POLICY_TYPE"; exit 2 ;;
esac
bash "$REPO/scripts/run_with_log.sh" "$OUT.log" \
  uv run "${RUN_DEPS[@]}" lerobot-train \
  --dataset.repo_id="local/$(basename "$DATASET")" --dataset.root="$DATASET" \
  "${POLICY_ARGS[@]}" --policy.device=cuda --policy.push_to_hub=false \
  --output_dir="$OUT" --job_name="${POLICY_TYPE}_4cam_20k" \
  --steps=20000 --batch_size=8 --num_workers=0 --seed=1000 --save_freq=2000
```

π₀.₅を使う場合だけ、先頭の`POLICY_TYPE`を`pi05`にします。GPU指定とbatchは利用可能な資源に合わせて選び、変更した条件を記録します。20Kやbatch 8はタスク成功を保証する値ではありません。

学習終了後は、次の場所にcheckpoint一式が保存されています。モデル設定と学習設定が存在することを確認します。

```bash
CHECKPOINT="$OUT/checkpoints/020000/pretrained_model"
test -f "$CHECKPOINT/config.json" &&
test -f "$CHECKPOINT/train_config.json" &&
printf '学習済みcheckpoint: %s\n' "$CHECKPOINT"
```

| `POLICY_TYPE` | 本節の出力先 | 11が使うcheckpoint |
|---|---|---|
| `smolvla` | `$OUTPUTS/smolvla_4cam_20k/` | 同ディレクトリの`checkpoints/020000/pretrained_model/` |
| `pi05` | `$OUTPUTS/pi05_4cam_20k/` | 同ディレクトリの`checkpoints/020000/pretrained_model/` |

**同じPCで本節から11へ進む場合、フォルダ名の変更・コピー・パスの再入力は不要です。** 11の`policy_session.sh`が上表の場所を設定します。第2・3節の短い学習だけで終えた場合は、この20K checkpointはまだ作成されていません。十分に学習したモデルを用意してから実機へ進みます。

日付などを付けた別名の学習結果も、そのまま利用できます。11のStep 1で`pretrained_model`の参照先を一度指定してください。`last`は最新保存checkpointへの参照、`020000`は20K stepを明示した保存先です。条件を固定して比較する際はstepを明示します。

別PCで推論する場合は、`pretrained_model`ディレクトリ全体と必要な基盤キャッシュを転送します。移動先が標準の参照先と異なる場合も、11で一度指定すれば使えます。11ではcheckpointのtype、画像feature、関節順序・単位、action表現と前後処理を照合します。

### 7.3 同じ観測で保存モデルを確認する

第2・3節で保存したモデルや追加学習のcheckpointを指定します。次の`CHECKPOINT`には`pretrained_model`ディレクトリを、`INSPECTION`には未使用の出力先を入力します。問いが表示されるたびにパスを入力し、Enterを押します。例えば追加学習後のSmolVLAなら、次のような入力になります（保存先は自分の環境のものを使います）。

```text
確認するpretrained_modelディレクトリ: /home/student/aloha-vla-reference/outputs/smolvla_4cam_20k/checkpoints/020000/pretrained_model
観測確認の新規出力ディレクトリ: /home/student/aloha-vla-reference/outputs/smolvla_inspection_20k
```

```bash
read -r -p "確認するpretrained_modelディレクトリ: " CHECKPOINT
read -r -p "観測確認の新規出力ディレクトリ: " INSPECTION
export CHECKPOINT INSPECTION
cd "$REPO/lerobot_trossen"
uv run --with 'lerobot[smolvla]==0.6.0' python \
  "$REPO/scripts/inspect_lerobot_checkpoint.py" \
  --policy smolvla --dataset "$DATASET" \
  --checkpoint "$CHECKPOINT" --output "$INSPECTION" --episodes 10
```

**完了条件**：`RECORDED-FRAME CHECK: PASS`と、画像・`actions.csv`・`summary.json`の生成。このコードはCUDAを使い、最大10 episodeを均等に選び、各3観測で推論します。出力先が既にあると停止します。π₀.₅用には`--policy pi05`と`uv run --with 'lerobot[pi]==0.6.0' --with accelerate==1.15.0`を使います。この補助コードはSmolVLAの2K・20Kとπ₀.₅の20Kで実行し、各30観測のPASSを確認しています。

画像ではカメラの視点・左右・色を確認します。CSVには関節ごとの予測、収録action、現在state、その差と推論時間を残します。関節はrad、gripperはmというように単位が異なるため、混ぜた未正規化の平均誤差をモデル順位に使いません。確認した値域も、そのまま実機の安全な指令範囲とはみなしません。例えばSmolVLA 20Kでは右gripperに約−0.929 mm、π₀.₅20Kでは約−0.510 mmの予測が含まれました。有限値のPASSとは別に、実機の可動範囲とdriverの指令制限を照合します。

### 7.4 checkpointで言えること・実機で確かめること

同じepisode・frame・task文を使い、例えば2Kと20Kのcheckpointを別の出力先へ読み直すと、学習量に伴う出力や計算時間の変化を確認できます。確認例では、同じ30訓練観測上のSmolVLAの関節ごとの平均絶対誤差は、2Kから20Kへ全14次元で小さくなりました。これは訓練観測への適合の例で、実機性能が改善した証拠ではありません。2K checkpointも同じ全Datasetからsampleを読むため、「少ないepisodeだけで学習したモデル」の代用にはなりません。5・10・25・50 episodeのデータ量比較には、独立したsubset学習と固定評価セットが必要です。

SmolVLAとπ₀.₅を同じデータ・batch 8・20K stepで試す場合は、同じ160K sampleの学習予算による導入比較として扱います。loss、正規化、更新対象の重み、optimizerが異なるので、lossの絶対値だけで優劣を決めません。訓練観測の誤差は未知条件での性能を示さず、閉ループの滑らかさ、修正行動、介入、タスク成功は実機で確認します。今回の実機結果と限界は[11](11_robot_policy_execution.md)を参照してください。単一タスク・一つの指示文の確認から、言語理解や汎化全般を主張しません。

## 参考資料

- [Trossen Arm: Getting Started](https://docs.trossenrobotics.com/trossen_arm/main/getting_started.html) / [Software Setup](https://docs.trossenrobotics.com/trossen_arm/main/getting_started/software_setup.html) / [Training and Evaluating](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot_plugin/train_and_evaluate.html) — 接続、初期設定、学習後の実機経路は公式手順を参照。
- [Trossen Robotics LeRobot integration](https://github.com/TrossenRobotics/lerobot_trossen) — 本教材の統合revisionと記録経路。
- [LeRobot: SmolVLA](https://github.com/huggingface/lerobot/blob/main/docs/source/smolvla.mdx) — SmolVLAの概念・学習設定。上流のmainは更新されるため、再現では使用revisionを固定する。
- [LeRobot SmolVLA training code](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/smolvla/modeling_smolvla.py) — 実装と追加依存の確認。
- [OpenVLA paper](https://arxiv.org/abs/2406.09246) / [OpenVLA-OFT paper](https://arxiv.org/abs/2502.19645) / [OFT project and code](https://openvla-oft.github.io/) / [OFT ALOHA tutorial](https://github.com/moojink/openvla-oft/blob/main/ALOHA.md) — 基盤モデルと、fine-tuning時のaction decoding・action representation・objective、ALOHA向けRLDS変換の発展。
- [π₀ paper](https://arxiv.org/abs/2410.24164) / [π₀.₅ paper](https://arxiv.org/abs/2504.16054) / [LeRobot π₀.₅](https://huggingface.co/docs/lerobot/pi05) / [Physical Intelligenceのopenpi](https://github.com/Physical-Intelligence/openpi) — 研究上の系譜と二つの実行系を区別する。
- [SmolVLA paper](https://arxiv.org/abs/2506.01844) / [LeRobot SmolVLA tutorial](https://github.com/huggingface/lerobot/blob/main/docs/source/smolvla.mdx) — 小規模VLAとLeRobot内の学習経路。
- [NVIDIA Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T) / [N1.6 research page](https://research.nvidia.com/labs/gear/gr00t-n1_6/) — GR00Tの専用実行系・データ要件・版の固定。
- [RDT-1B paper](https://arxiv.org/abs/2410.07864) — 双腕ロボット基盤モデルの設計・データ要件。

---

**調査時点**：2026-09-30。モデルや公式実装は更新されるため、実行時は論文だけでなく、公式リポジトリのrelease・commit・checkpoint revisionも併記する。
