# 07 VLAの選び方と関連研究

[02](02_data_collection.md)で収録した`aloha_vla_demo`を使い、モデルと学習プログラムの関係を理解します。**まず第1・2節を読み、[08の学習とオフライン推論](08_vla_training_inference.md)へ進んでください。** 第3節以降には、基盤モデルから派生した公開研究と、その実装を確認するときの手掛かりを置きました。必要な箇所だけ参照できます。ACTなどVLA以外のモデルは最後の参考節に分けています。

読み終えると、LeRobotとモデルの違いを説明し、手元のデータを学習へ渡す前に何を確かめるか判断できるようになります。

構成を選ぶ際の判断材料とセンサ拡張の適用条件は[10](10_stack_decisions_and_extension.md)を参照してください。

## 基本編：実習に進む前に読む

## 1. 収録データと学習モデルの関係

[02](02_data_collection.md)では、画像、アームの状態、操作者の行動、タスク文を時刻ごとに記録しました。学習する**方策（policy）**は、カメラ画像や関節状態という**観測**から次の**行動**を予測します。VLAは画像に加えて自然言語の指示を用いて行動を出すモデルです。

### 1.1 LeRobotが担当すること

[LeRobot](https://huggingface.co/docs/lerobot/index)はロボット接続、データ収集、学習、推論を扱うソフトウェア群です。**モデル名はSmolVLAやπ₀.₅、LeRobotはそれらを動かす手段の一つ**です。Trossenの[`lerobot_trossen`](https://github.com/TrossenRobotics/lerobot_trossen)は、ALOHAのアームとカメラをLeRobotに接続するプラグインです。

| 段階 | LeRobot内で扱うもの | 自分が確認するもの |
|---|---|---|
| 操作と収録 | ロボットとカメラからデモを記録 | 装置の対応、観測と行動の順序、収録fps |
| データ読込 | LeRobotDatasetのepisode・frameを取り出す | 画像名、状態・行動の次元、タスク文 |
| 学習 | `lerobot-train`で方策へデータを渡す | モデル重み、追加依存、前処理とGPU |
| 推論 | 保存した方策と前後処理で行動を計算 | 実機に使う場合は単位、指令範囲、停止方法も確認 |

[LeRobotDataset v3](https://huggingface.co/docs/lerobot/lerobot-dataset-v3)は、この教材で保存するデータ形式です。数値の状態・行動、動画、タスク文、episodeの境界を対応づけます。一つのMP4が一つのepisodeとは限らないため、動画の本数ではなくdataset loaderで数えます。

別の資料で見かける**HDF5**は元祖ALOHAなどで使う階層的なファイル形式、**RLDS**はepisodeとstepでロボット試行を表す規約です。形式を変える場合には、画像、関節状態、行動、タスク文と時刻の対応を検証します。同じ14次元でも関節の順序や指令の意味まで一致するとは限りません。

### 1.2 モデルと実行プログラムの組合せ

本教材では、π₀.₅とSmolVLAを**LeRobotの実装**で学びます。OpenVLAから発展したOpenVLA-OFTは別の学習プログラムを使い、[09](09_openvla_oft_data_bridge.md)でデータの接続を学びます。πシリーズの開発元が公開する`openpi`は、同じモデル系列でもLeRobot版とはデータ設定や実行環境が異なります。モデル名だけを見て学習コマンドを流用しないでください。

まだ収録経路を選んでいない場合は[02のTrossenプラグイン](02_data_collection.md)がこの実習とつながります。元祖[ALOHAのROS/HDF5経路](https://github.com/Interbotix/aloha)や[Trossen Aloha UI](https://docs.trossenrobotics.com/aloha_docs/2.0/gui.html)から収録した場合は、実際の出力形式と学習プログラムの入力条件を照合します。ハードウェア側をつなぐソフトと学習側のモデルは別々に選ぶ項目です。

## 2. この教材で扱うVLAの経路

ここでは**画像と指示文から行動を生成するVLA**のうち、本教材で具体的な接続手順を用意した三つの系統を取り上げます。VLA全体の代表三選や性能順位ではありません。SmolVLAとLeRobot版π₀.₅は既存のLeRobot v3収録データを直接使える経路です。OFTはALOHA向けの公開手順があり、別の実行系へ変換して短い学習と保存済みモデルの推論まで接続する経路です。既存データの再利用と、行動表現・実行系を変える際の作業を比較できることを選定理由にしています。候補ごとの保留理由と再検討条件は[10の第2節](10_stack_decisions_and_extension.md)に整理しています。固定作業の模倣だけが目的なら、最後の[非VLAの参考節](#7-もっと知りたい人へ関連する非vlaと汎用方策)も見てください。

| この教材で扱う系統 | 理解できる違い | `aloha_vla_demo`からの次の作業 |
|---|---|---|
| **SmolVLA** | 比較的小さなVLAで、画像・指示文・状態がどう行動生成へ渡るか理解する | [08の第二実習](08_vla_training_inference.md)で学習とオフライン推論、[11](11_robot_policy_execution.md)で実機の成功例と調整点 |
| **π₀→π₀.₅** | VLMと行動生成部分の組合せ、多様な環境への汎化を学ぶ | [08の主実習](08_vla_training_inference.md)でLeRobot版π₀.₅を学習。[11](11_robot_policy_execution.md)で実機接続と失敗・制約を確認 |
| **OpenVLA→OpenVLA-OFT** | 元の基盤モデルの行動表現を、後続研究がどう変えたかを学ぶ | [09](09_openvla_oft_data_bridge.md)でv3からHDF5・RLDSを経て専用ローダへ接続し、第5節で短い学習・保存・再読込を確認 |

**基盤モデル**は追加データで新しい作業に合わせる出発点、**fine-tuning**はその重みを手元のデモで更新することです。OpenVLA-OFTはOpenVLAの発展研究なので、本教材では元のOpenVLAとOFTを同じ基盤からの別経路として扱います。元の離散行動出力とOFTの連続行動・chunkでは、実行条件を別々に照合します。**action chunk**は未来の複数時刻の指令をまとめて予測する出力です。指示文を入力できても、少数のデモだけで未知の指示に対応するとは限りません。

### 2.1 学習へ接続するときの確認点

| 経路 | 実際に確認する条件 | この教材での手順 |
|---|---|---|
| SmolVLA / LeRobot | `lerobot[smolvla]`の追加依存、画像feature、state/actionの次元。個別に最新版`transformers`を導入するとlockの依存と衝突しうる | [08](08_vla_training_inference.md)でデータから入力特徴を構成し、保存したcheckpointから行動を読む |
| π₀.₅ / LeRobot | PaliGemmaの利用条件と認証、`q01`・`q99`統計、`accelerate`、GPUメモリ | [08](08_vla_training_inference.md)で学習・checkpoint再読込・オフライン推論 |
| OpenVLA-OFT / 専用実装 | v3からRLDSへの変換、dataset名の登録、公開ALOHA設定の3画像、収録fpsと行動列長 | [09](09_openvla_oft_data_bridge.md)で1 episodeの変換を確かめ、全episodeの変換・短い学習・checkpoint推論へ進む |

この比較は**自分のデータを入力できるか**の判断です。モデルの成功率の順位ではありません。4視点の画像が保存され、policy設定に4画像が並んでも、それぞれの視点が成績に寄与した証拠にはなりません。

### 2.2 何を学んで次へ進むか

検証時の双腕タスクで成功した構成を最初の実例にしたい場合、[08のSmolVLA実習](08_vla_training_inference.md)と[11の実機記録](11_robot_policy_execution.md)を使います。π₀.₅のデータ読込・重み取得・学習・checkpoint再読込も08に用意しています。章の配置は性能順位ではありません。基盤モデルの行動表現を変更したいならOpenVLAとOFTの論文を比較し、[09](09_openvla_oft_data_bridge.md)で学習プログラムへデータを届ける道筋を確かめます。どの経路もオフラインのactionが出ただけで実機のタスク成功とは判断しません。

---

## 参考編：基盤モデルから派生した公開研究

ここからは、各基盤モデルを使った研究にどのような例があるかを紹介します。**08を始める前に読む必要はありません。** 紹介する論文や実装は、個々の目的に合わせて原典を調べる入口です。本教材の手順がそれらの拡張を再現・検証するわけではありません。

## 3. 基盤モデルと発展研究を読む

発展論文では「元モデルの何を変え、何を改善しようとしたか」を確認できます。たとえば**action head**はモデルが行動を出力する部分、**正規化**は数値の大きさを学習しやすい範囲に揃える処理です。原典を参照する際は、次の点を見ると基盤モデルとの関係を読み取りやすくなります。

| 読み取る項目 | 質問 |
|---|---|
| 出発点 | どの基盤モデル、データ、ロボットを引き継いでいるか |
| 変更点 | データ量、action head、微調整方式、推論時の制御、センサ入力のどれを変えたか |
| 研究グループの動機 | 既存方式のどの失敗・計算負荷・汎化限界を解決しようとしたか |
| 必要条件 | 必要データ、GPU、追加ラベル、ロボット設定、専用ランタイムは何か |
| 手元のデータへの移植性 | ALOHAのLeRobot v3データをそのまま使えるか。変換やコード改修が必要か |
| 判断への使い方 | この発展は、どの種類の案件で元の基盤モデルを選ぶ理由になるか |

### 3.1 基盤モデルからの派生例

- **OpenVLA → OpenVLA-OFT**：OFT論文はOpenVLAを代表モデルとして、action decoding、action representation、learning objectiveなどの適応設計を検討し、OFTレシピを提案しています。推論速度やファインチューニング方法が案件の制約となる場合、OFT研究グループが比較した設計と必要GPU・入力視点・行動チャンクを読みます。論文のベンチマーク結果を本教材のALOHA上の実績とは扱いません。
- **π₀ → π₀.₅**：π₀の視覚・言語・行動生成を土台に、π₀.₅論文は知識の移転と異種データを通じたopen-world generalizationを主題にします。LeRobot版π₀.₅をv3データで学習する経路があるので、この実装を近道にできます。モデル内部・独自データ変換まで改変する案件は**Physical Intelligenceの`openpi`**を別経路として調べます。同名モデルでも重み・前処理・実行系は同一とは仮定しません。
- **SmolVLA**：LeRobot上で小規模なVLA微調整を始める基準経路として扱う。本教材で確認するのは、4カメラ・状態・言語タスクを用いたデータ読込、短時間の学習、チェックポイント読込、有限値のaction推論までである。実機でタスクが成功することや、少数データで十分な性能が得られることは示していない。

### 3.2 VLAの発展研究を読むためのヒント

次の「発展」はすべて同じ意味ではありません。**flow matching**は連続値の行動を生成する学習法、**行動トークン化**は行動を記号列として扱う方法、**蒸留**は学習済みモデルの振る舞いを別のモデルへ移す方法です。詳しい数式は、目的に合う論文を選んでから確認します。**後継モデル**、**基盤モデルの微調整方法**、**データ・センサの変更**、**推論時の工夫**を区別します。この表はVLAの発展例です。いずれも発展論文そのものを最初の学習候補に置くための一覧ではなく、基盤モデルから先へ進める研究課題を知るための入口です。

| 出発点と参考研究 | 研究グループが主に変えたもの | この研究を読むと役立つ場面 | ALOHA教材からの距離 |
|---|---|---|---|
| [SmolVLA](https://arxiv.org/abs/2506.01844) ＋ [非同期推論](https://huggingface.co/docs/lerobot/main/en/async)、[RTC](https://huggingface.co/docs/lerobot/main/en/rtc) | 前者は予測と実行を分離し、後者は前後のaction chunkのつながりを扱う。**後継基盤モデルではなく推論側の拡張** | オフラインでactionが出た後、実機で計算待ちやchunk境界のぎくしゃくが問題になる場合 | 08はオフライン推論、11は非同期実機接続を扱う。RTCの実機検証はしていない。固定LeRobot 0.6.0で、現行mainのRTC機能が同一に使えるとは仮定しない |
| [π₀](https://arxiv.org/abs/2410.24164) → [π₀-FAST](https://www.pi.website/research/fast)、[π₀.₅](https://arxiv.org/abs/2504.16054) → [π*₀.₆ / RECAP](https://www.pi.website/blog/pistar06) | FASTは行動トークン化の別経路、π₀.₅は開いた環境への汎化、RECAPはデモ・自律試行・介入を使う経験からの改善 | 行動表現、事前学習の汎化、失敗後の介入データという**別々の研究目的**を選ぶ場合 | 08にはLeRobot版π₀.₅の3-step接続確認と20K checkpointの確認記録がある。RECAPを同じCLIで実行できるという意味ではない |
| [OpenVLA](https://proceedings.mlr.press/v270/kim25c.html) → [OpenVLA-OFT](https://arxiv.org/abs/2502.19645) | 離散action tokenを出す基盤モデルに対し、並列デコード、連続行動表現、action chunk、微調整目的を検討 | 高頻度の双腕操作やaction headの研究を始める際、**OFT研究グループが旧方式のどこを変えたか**を学べる | OFTのALOHA例は3画像＋RLDS。本教材のv3/4画像から変換が必要 |
| [π₀](https://arxiv.org/abs/2410.24164) → [ForceVLA](https://github.com/ft-robotic/ForceVLA) | 外部グループがπ₀とopenpiを基に力覚を組み込む。**π₀.₅の直接拡張と混同しない** | 力覚を単に記録する段階から、行動生成の条件として使う研究へ進む場合 | 03・06の力覚同期はモデル入力まで通した実績ではない。独自のセンサデータ、表現と学習経路が要る |
| [π₀.₅](https://arxiv.org/abs/2504.16054) → [OptimusVLA](https://github.com/iLearn-Lab/CVPR26-OptimusVLA) | 外部グループがπ₀.₅を起点に時間的な記憶を加える方向を検討 | 1枚の現在画像だけでは足りない長い操作や時間的整合性を研究する場合 | OptimusVLA公開コードは本教材のLeRobot移植版と同一ではない。追加依存とチェックポイントの取り扱いを確認 |

**読み方の例：** 「力覚を足したい」なら、まず[03](03_architecture_and_extension.md)と[08の第4節](08_vla_training_inference.md)で収録からモデル入力までを辿ります。OpenVLA-OFTの高速化結果だけでは力覚入力の作り方は分かりません。一方、素早い双腕操作の行動列を生成したいなら、OFT研究グループが元のOpenVLAから行動の出し方を変えた理由を読み、データ変換に要する作業も確かめます。

## 4. 用途ごとに参照できる公開研究

次の二例は、センサ入力や行動生成について公開研究が何を扱っているかを示します。各論文の結果はその論文の実験条件での報告です。本教材のALOHAで同じ改善を得られるという意味ではありません。

| 関心のある機能 | 公開研究の例 | 本教材との接続点と追加で確認すること |
|---|---|---|
| 力覚や触覚を行動生成に使う | [ForceVLA](https://github.com/ft-robotic/ForceVLA)はπ₀と`openpi`を基に力覚を扱う例。π₀.₅へそのまま追加できる機能ではない | [03](03_architecture_and_extension.md)はセンサの収録・同期まで。[08の第4節](08_vla_training_inference.md)でdatasetからモデル入力までの確認箇所を示す。モデル内部の融合は公開研究のコードを別途調べる |
| 行動表現や汎化を調べる | [π₀.₅](https://arxiv.org/abs/2504.16054)は異種データによる汎化、[OpenVLA-OFT](https://arxiv.org/abs/2502.19645)は行動復号やfine-tuning方法を検討した例 | 08はLeRobot版π₀.₅、09はデータ変換から短い学習・checkpoint推論まで。公開実装へ進む場合はデータ形式、視点、action表現、専用実行系を確認する |

二つの用途は重なる場合もあります。公開された発展研究の存在は、変更を手元のALOHAで再現できた証拠にはなりません。

### 拡張の「公式の入口」と研究の境界

LeRobotの[Bring Your Own Hardware](https://huggingface.co/docs/lerobot/main/integrate_hardware)は、ロボットの`observation_features`と`get_observation()`の対応や、camera/robotプラグインによる観測追加の入口を説明しています。[LeRobotDataset v3](https://huggingface.co/docs/lerobot/lerobot-dataset-v3)は複数カメラと多様な時系列観測の保存・読込形式です。[Robot Processor](https://huggingface.co/docs/lerobot/implement_your_own_processor)は入力変換の拡張点です。これらは**記録・入力整形のAPI**であり、任意の力覚や触覚を既存VLAの事前学習済み重みが意味のある情報として使う標準レシピではありません。[固定版Trossenのconfig](https://github.com/TrossenRobotics/lerobot_trossen/blob/a4336933f34192a3daa7e9fb52674284bb5ae48e/packages/lerobot_robot_trossen/src/lerobot_robot_trossen/config_widowxai_follower.py)にも`include_effort`・`include_external_effort`が存在します。ただし、モータ側の推定値と外付けの力覚センサは別です。取得フラグがあることは、既存VLAがその値を利用する学習経路や効果が検証済みであることを意味しません。

03の収録と同期までは教材の既存経路です。モデル内の融合位置、学習目的、実機での利用は研究設計です。後者はForceVLAなどの研究グループが公開した論文・コードを**参考事例**として示し、汎用手順としての動作を保証しません。

## 5. OpenVLA-OFTの公開実装を参照する

OpenVLAの行動表現や微調整法を変更したい場合は、OFTの[論文](https://arxiv.org/abs/2502.19645)と[ALOHA実装](https://github.com/moojink/openvla-oft/blob/main/ALOHA.md)を読みます。研究の起点はOpenVLAで、OFTはその発展例です。収録済みデータから変換して学習用ローダへ渡す[09の演習](09_openvla_oft_data_bridge.md)で、LeRobot内の二つの実習と何が異なるかを確かめられます。09第5節では短い学習とcheckpoint推論も扱います。実機制御とタスク性能は別の検証項目です。

## 6. ほかのVLA・実行系（参考）

RDT、GR00T、X-VLAも公開されているVLAの例です。ここには入口となる資料と必要な確認事項のみを示します。学習コマンドや入力形式をこの教材の実習から流用できるという意味ではありません。

| VLA | 関心の入口 | 初めに確認する条件 |
|---|---|---|
| [RDT-1B](https://arxiv.org/abs/2410.07864) / [RDT2](https://github.com/thu-ml/RDT2) | 双腕データと行動表現 | データ変換、計算資源、ALOHAの関節対応 |
| [GR00T N1.6](https://research.nvidia.com/labs/gear/gr00t-n1_6/) / [N1.7](https://github.com/NVIDIA/Isaac-GR00T) | 複数ロボットとIsaac環境 | `modality.json`、専用実行系、対象版 |
| [X-VLA](https://github.com/2toinf/X-VLA) | 身体構成の異なるロボットへの適応 | 対応モデル版、soft promptと入力変換 |

### 用途別の参照先

- **自然言語でタスクを切り替えたい**：SmolVLAのようなLeRobot経路でデータ・タスク文を整え、言語条件が学習と推論の双方で有効か評価する。
- **π系モデルを使いたい**：LeRobot版π₀.₅の接続実績を基準とし、Physical Intelligenceのopenpiへ移す必要がある変更だけを特定する。移すならv3の変換試験を別途行う。
- **力覚・触覚・高周波時系列を加えたい**：03章の収集・同期設計から始める。ログに記録できることと、モデルが特徴を利用できることを分け、データ列→前処理→モデル→推論入力まで追跡する。
- **専用エコシステムを選びたい**：Isaac-GR00T等の専用実行系について、既存GPU・OS、フォーマット変換、推論接続、保守負担を含めて採用判断する。

## 7. もっと知りたい人へ：関連する非VLAと汎用方策

ここまでのVLAは、画像と言語を行動へ結びつける研究の入口でした。**毎回同じブロックを同じトレイへ置く**だけなら、指示文で作業を切り替える仕組みは必須ではありません。比較基準や動作生成を研究したいときは、以下を別の系統として読んでください。08・09のVLA実習を始めるために、これらをすべて学ぶ必要はありません。

| 関連する方策 | VLAとの違い | 役立つとき |
|---|---|---|
| [ACT](https://arxiv.org/abs/2304.13705) | 通常は画像と関節状態から未来の複数指令をまとめて予測し、自然言語指示を主入力としない | ALOHAの固定作業を模倣する基準や、action chunkの概念を知りたい |
| [Diffusion Policy](https://arxiv.org/abs/2303.04137) | 画像や状態を条件として行動列を段階的に生成する。標準の形はVLAの言語・視覚の事前学習とは別 | 複数の妥当な軌道や生成過程を研究したい |
| [Octo](https://octo-models.github.io/) | 言語指示でも目標画像でも条件づけできる公開generalist policy。**言語入力があるので単純な「非VLA」と断定しない**が、本章のVLMを中心としたVLA群とは設計と学習経路が異なる | 複数ロボットのデータで事前学習する汎用方策の系譜を比較したい |

ACTはaction chunkを使いますが、「chunkを出すモデル＝VLA」ではありません。逆にOctoは言語条件を扱えるため、VLAの定義を広く取る資料では同じ範囲で論じられることもあります。本教材では**VLMを基盤に画像・言語・行動を結ぶモデルを主たるVLA候補**として先に扱い、Octoを関連研究としてここに置きます。名称だけで機能を決めず、モデルが実際に受け取る入力、事前学習、行動の出し方を確認してください。

Trossenの[学習・評価の公式案内](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot_plugin/train_and_evaluate.html)にACTやDiffusion Policyがあっても、本教材ではこの二つの**学習コマンドと実機推論を試していません**。固定作業の非VLA比較基準として選ぶ場合は、指示文によるタスク切替えを期待しないで、各モデルの画像キー、観測・行動の次元、収録fpsに対する行動列、学習用追加依存、推論時の実行間隔を、使用する版の公式例と自分のdatasetで確認します。この確認をせず、VLA実習のcheckpointや設定を流用しません。

非VLAからの発展例として、[Mobile ALOHA](https://arxiv.org/abs/2401.02117)はACTを使う双腕操作を移動型ロボットとそのデータへ広げます。[DP3](https://arxiv.org/abs/2403.03954)は点群による3D観測、[Consistency Policy](https://arxiv.org/abs/2405.07503)はDiffusion Policyを踏まえた推論高速化を調べる入口です。いずれも、追加しただけでVLAの自然言語理解を獲得する研究ではありません。固定作業だけが目的なら、まずACT等を比較基準にする判断もあります。

## 参考資料

- [Trossen Arm: Getting Started](https://docs.trossenrobotics.com/trossen_arm/main/getting_started.html) / [Software Setup](https://docs.trossenrobotics.com/trossen_arm/main/getting_started/software_setup.html) / [Training and Evaluating](https://docs.trossenrobotics.com/trossen_arm/main/tutorials/lerobot_plugin/train_and_evaluate.html) — 接続、初期設定、学習後の実機経路は公式手順を参照。
- [Trossen Robotics LeRobot integration](https://github.com/TrossenRobotics/lerobot_trossen) — 本教材の統合revisionと記録経路。
- [LeRobot ACT](https://github.com/huggingface/lerobot/blob/main/docs/source/act.mdx) / [Diffusion Policy](https://diffusion-policy.cs.columbia.edu/) — 非VLAの模倣学習基準候補。
- [LeRobot: SmolVLA](https://github.com/huggingface/lerobot/blob/main/docs/source/smolvla.mdx) — SmolVLAの概念・学習設定。上流のmainは更新されるため、再現では使用revisionを固定する。
- [LeRobot SmolVLA training code](https://github.com/huggingface/lerobot/blob/main/src/lerobot/policies/smolvla/modeling_smolvla.py) — 実装と追加依存の確認。
- [OpenVLA paper](https://arxiv.org/abs/2406.09246) / [OpenVLA-OFT paper](https://arxiv.org/abs/2502.19645) / [OFT project and code](https://openvla-oft.github.io/) / [OFT ALOHA tutorial](https://github.com/moojink/openvla-oft/blob/main/ALOHA.md) — 基盤モデルと、fine-tuning時のaction decoding・action representation・objective、ALOHA向けRLDS変換の発展。
- [π₀ paper](https://arxiv.org/abs/2410.24164) / [π₀.₅ paper](https://arxiv.org/abs/2504.16054) / [LeRobot π₀.₅](https://huggingface.co/docs/lerobot/pi05) / [Physical Intelligenceのopenpi](https://github.com/Physical-Intelligence/openpi) — 研究上の系譜と二つの実行系を区別する。
- [SmolVLA paper](https://arxiv.org/abs/2506.01844) / [LeRobot SmolVLA tutorial](https://github.com/huggingface/lerobot/blob/main/docs/source/smolvla.mdx) — 小規模VLAとLeRobot内の学習経路。
- [NVIDIA Isaac-GR00T](https://github.com/NVIDIA/Isaac-GR00T) / [N1.6 research page](https://research.nvidia.com/labs/gear/gr00t-n1_6/) — GR00Tの専用実行系・データ要件・版の固定。
- [RDT-1B paper](https://arxiv.org/abs/2410.07864) — 双腕ロボット基盤モデルの設計・データ要件。

---

**調査時点**：関連研究一覧は2026-09-30。2026-10-06に候補選定の補足を[10](10_stack_decisions_and_extension.md)へ追加しました。モデルや公式実装は更新されるため、実行時は論文だけでなく、公式リポジトリのrelease・commit・checkpoint revisionも併記する。
