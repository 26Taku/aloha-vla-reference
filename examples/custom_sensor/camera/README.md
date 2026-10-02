# Asynchronous Camera Reference

この資料は、Linux V4L2で認識されるasynchronous cameraをnative compressed streamとして保存する際の実装詳細をまとめる。

End-to-endの作業順序は[03 外部センサを追加する](../../../docs/03_architecture_and_extension.md)のPattern Cを参照する。

reference path:

```text
V4L2 camera
    ↓
native compressed stream
    ↓
FFmpeg stream copy + preserved packet PTS
    ↓
MKV
    ↓
extract_mkv_timestamps.py
    ↓
causal latest-frame alignment
```

---

## 実行例の作業場所

[02の作業場所の設定](../../../docs/02_data_collection.md#作業場所の設定)を行い、`cd "$REPO"`で教材ルートへ戻る。以下の出力パスは例で、既存fileの上書きが必要な場合は新しい出力名を選ぶ。数値sensor資料と併用する場合はvideoとtimestampの設定を共通にする。

```bash
CAMERA_DIR="$REPO/data/sensor_logs"
mkdir -p "$CAMERA_DIR"
OUT="$CAMERA_DIR/camera.mkv"
CAMERA_TIMESTAMP_JSONL="$CAMERA_DIR/camera_timestamps.jsonl"
CAMERA_ALIGNMENT_JSONL="$CAMERA_DIR/camera_alignment.jsonl"
ROBOT_FRAMES="$REPO/data/sensor_reference/meta/frame_timestamps/episode_000000.jsonl"
```

別の収録済みfileを使う場合は、例えば`read -r -p "入力MKV: " OUT`でパスを一度入力する。別Datasetのrobot timestampを使う場合も`ROBOT_FRAMES`へ同じ方法で入力する。

## 1. Prerequisites

```bash
v4l2-ctl --version
ffmpeg -version
ffprobe -version
```

---

## 2. Device discovery

camera一覧:

```bash
v4l2-ctl --list-devices
```

stable symbolic linkが存在する場合:

```bash
ls -l /dev/v4l/by-id/
```

一覧で見つけたdeviceを問いへ入力する。candidate deviceのcapability:

```bash
read -r -p "Camera device（例 /dev/video6）: " DEVICE
v4l2-ctl \
  --device "$DEVICE" \
  --all
```

format一覧:

```bash
v4l2-ctl \
  --device "$DEVICE" \
  --list-formats-ext
```

使用するdevice / modeについて次を記録する。

```text
device
pixel format
resolution
advertised FPS
```

複数video nodeを持つdeviceでは、実際に必要なformatを提供するnodeを選択する。

---

## 3. Native compressed capture

MJPEGを提供するcameraの例:

```bash
read -r -p "Resolution（例 3280x2464）: " VIDEO_SIZE
read -r -p "Advertised FPS: " CAMERA_FPS

ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size "$VIDEO_SIZE" \
  -framerate "$CAMERA_FPS" \
  -timestamps default \
  -t 10 \
  -i "$DEVICE" \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  "$OUT"
```

`VIDEO_SIZE`と`CAMERA_FPS`には、`v4l2-ctl --list-formats-ext`で確認したmodeを入力する。

このreferenceではduration指定の `-t` を `-i` より前に置く。

`-c:v copy` によりcapture時のdecode / re-encodeを避ける。

---

## 4. Capture resultを確認

```bash
ffprobe -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height,avg_frame_rate \
  -show_entries format=duration \
  -of default=noprint_wrappers=1 \
  "$OUT"
```

packet数とPTSを確認する場合:

```bash
ffprobe -v error \
  -select_streams v:0 \
  -show_entries packet=pts_time \
  -of csv=p=0 \
  "$OUT" \
  | head
```

---

## 5. Export packet timestamps

```bash
python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  "$OUT" \
  --output "$CAMERA_TIMESTAMP_JSONL"
```

scriptはpacket PTSをnanosecondsへ変換し、

```text
receive_monotonic_ns
```

fieldとしてalignment scriptへ渡す。

出力時に以下を表示する。

```text
video frames
effective rate
[PASS] Monotonic packet timestamps exported.
```

### Clock assumption

このreferenceは、V4L2 `-timestamps default` とFFmpeg `-copyts` で保持したpacket PTSを同一host monotonic clockとして扱う。

別camera、driver、OS、FFmpeg configurationへ変更した場合はtimestamp semanticsを再確認する。

---

## 6. Concurrent capture with ALOHA

camera captureをrobot recordingより先に開始し、camera capture durationをrobot episodeより長くする。

例:

```text
Terminal A:
camera capture 30 s

Terminal B:
timestamp付き ALOHA recording 10 s
```

これによりrobot episode先頭で利用できるprior camera frameを確保する。

---

## 7. Causal alignment

robot frame timestamp sidecar:

```text
data/<DATASET>/meta/frame_timestamps/episode_000000.jsonl
```

camera timestamp:

```text
<CAMERA_TIMESTAMP_JSONL>
```

alignment:

```bash
python3 examples/custom_sensor/camera/align_camera_frames.py \
  --robot-frames \
    "$ROBOT_FRAMES" \
  --camera-timestamps \
    "$CAMERA_TIMESTAMP_JSONL" \
  --output \
    "$CAMERA_ALIGNMENT_JSONL"
```

algorithm:

```text
camera_time <= robot_time
```

を満たす最新camera frameを選ぶ。

robot FPSがcamera rateより高い場合、同一camera frameが複数robot frameへ割り当てられる。

raw video frame自体は複製しない。

---

## 8. Validation

最低限確認する。

```text
[ ] videoがdecode可能
[ ] packet timestampが単調増加
[ ] actual camera rateを記録
[ ] robot timestampが単調増加
[ ] aligned frames = robot frames
[ ] missing frames = 0
[ ] future frames used = 0
[ ] reused assignmentsを記録
[ ] camera age median / p95 / maxを記録
```

---

## 9. GelSight Mini validated example

**[HW-VERIFIED]**

GelSight Miniで確認したmode:

```text
pixel format       MJPEG
resolution         3280x2464
advertised FPS     25
```

capture:

```bash
read -r -p "GelSight camera device: " DEVICE
OUT="$CAMERA_DIR/gelsight_smoke.mkv"

ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size 3280x2464 \
  -framerate 25 \
  -timestamps default \
  -t 10 \
  -i "$DEVICE" \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  "$OUT"
```

過去のreference validationではactual rateは約18.7--18.8 Hzだった。

advertised 25 fpsをactual rateとして扱わず、`extract_mkv_timestamps.py` の出力から実測する。

GelSight Mini 1台について、native compressed capture、packet timestamp保持、ALOHAとのconcurrent recording、causal alignmentまで確認済みである。

2台同時capture時のUSB / CPU / storage capacityは別途capacity testを行う。
