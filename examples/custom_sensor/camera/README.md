# Asynchronous Camera Reference

robot/control FPSと実効取得rateが異なるcameraを、robot loopを待たせずに保存するreferenceである。

GelSight Miniで実機確認した経路は以下。

```text
V4L2 MJPEG
  -> FFmpeg stream copy (-c:v copy)
  -> MKV with preserved V4L2 packet PTS (-copyts)
  -> extract_mkv_timestamps.py
  -> causal latest-frame alignment
```

raw compressed videoをcanonical dataとし、robot-rateの対応表はderived dataとして後から作る。capture中のdecode/re-encodeは行わない。

## 1. Capture

例:

```bash
DEVICE=/dev/v4l/by-id/<camera-video-index0>
OUT=/path/to/gelsight.mkv

ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size 3280x2464 \
  -framerate 25 \
  -timestamps default \
  -t 60 \
  -i "$DEVICE" \
  -map 0:v:0 \
  -c:v copy \
  -copytb 1 \
  -avoid_negative_ts disabled \
  "$OUT"
```

`-copyts`と併用する場合、このreferenceではduration指定の `-t` を `-i` より前に置く。出力側の `-t` として使用すると、絶対timestampを保持した入力で期待通りに書き出されない場合がある。

GelSight Miniで確認したadvertised modeはMJPEG 3280x2464 @ 25 fpsだったが、検証機での実効rateは約18.75 Hzだった。advertised FPSと実測rateが一致するとは限らないため、実際のframe count/timestampを確認する。

## 2. Export packet timestamps

```bash
python3 examples/custom_sensor/camera/extract_mkv_timestamps.py \
  /path/to/gelsight.mkv \
  --output /path/to/gelsight_timestamps.jsonl
```

実機検証では、`-copyts -timestamps default` で保存したpacket PTSが同一hostの `time.monotonic()` と同じclock domainであることを確認した。

この確認はdevice/driver/FFmpeg環境依存である。別cameraや別環境へ変更した場合は再確認する。

## 3. Causal alignment

robot recordingは `../record_with_timestamps.py` でframe timestamp sidecarを生成しておく。

```bash
python3 examples/custom_sensor/camera/align_camera_frames.py \
  --robot-frames <dataset_root>/meta/frame_timestamps/episode_000000.jsonl \
  --camera-timestamps /path/to/gelsight_timestamps.jsonl \
  --output /path/to/gelsight_aligned.jsonl
```

各robot observationに対して、その時刻以前で最も新しいcamera frameだけを選ぶ。同じcamera frameが複数robot frameから参照されることは正常であり、画像そのものは複製しない。

## 4. Synchronization scope

この方式はshared host monotonic clockによるsoftware-level synchronizationである。camera exposure instant、hardware trigger、PTP、外部clock等を保証しない。

sub-frameの厳密同期が必要なtaskでは、hardware triggerまたはdevice間で共有できるclockを別途設計する。
