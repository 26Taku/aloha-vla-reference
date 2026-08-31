# Troubleshooting

本資料は、研究室ALOHAでPhase 1のsetup / teleoperation / recording / external sensor validation中に実際に遭遇した事項を中心に整理する。

## 1. 4台すべてのArmにpingが通らない

まずALOHA Armの電源状態とPC側network interfaceを確認する。

実機検証ではArm電源OFF時に設定済みの4 Armすべてへ到達できず、電源投入後に復旧した。

まずtemplateへ設定したIPを確認し、対象ごとにpingする。

```bash
grep -n 'arm_ip_address' config/teleop-local.yaml
ARM_IP=YOUR_CONFIGURED_ARM_IP
ping -c 2 "$ARM_IP"
```

`<configured-arm-ip>` は実際にconfigへ設定した値へ置き換える。

`check_hardware.sh` のping成功はnetwork reachabilityのみを示す。driverを含む実動作は `teleoperate.sh` で確認する。

## 2. setup.shが既存repositoryを変更しない

`setup.sh` は成果物直下の `lerobot_trossen/` を使用する。既存repositoryにlocal modificationがある場合は自動checkoutを拒否する。

研究用途の既存forkを流用してsetup failureを回避しようとせず、成果物用clean directoryを使用する。

## 3. RealSenseが認識されない / serialが一致しない

```bash
rs-enumerate-devices
```

等でdeviceとserialを確認し、`config/teleop-local.yaml` / `config/record-local.yaml` と照合する。

USB差し替えやcamera交換時はdevice indexではなくserialを基準にする。

## 4. Rerun / Vulkan / EGL warning

実機検証ではgraphics backend由来のwarningが表示される場合があったが、Arm controlとrecording自体が継続できたケースがある。

warning文字列だけで失敗と判断せず、以下を確認する。

- Armが正常に応答する
- camera viewが更新される
- control loopが継続する
- recording終了後にDataset validatorがPASSする

viewer自体が不要な切り分けではdisplayを無効化して原因を分離する。

## 5. Dataset directory already exists

`record.sh` は既存datasetを誤上書きしないため、同名directoryがあると停止する。

新しいdataset名を使うか、不要であることを確認して既存datasetを別途退避・削除する。

## 6. frame数が `duration x fps` と1 frame程度ずれる

10秒・30 Hzで299 frames、15秒で449 framesとなる等、実時間によるloop終了境界のため完全一致しない場合がある。

固定個数一致だけで成否を判断せず、`validate_dataset.sh` でmetadata / Parquet / video / frame orderingを確認する。

## 7. 外部ROS 2 sensor loggerが0 sample

まずpublisherが実際に動作中か確認する。

```bash
ros2 topic list
ros2 topic hz /force_torque/left
ros2 topic info -v /force_torque/left
```

publisher停止をQoS mismatchと誤認しないよう、topic存在とrateを先に確認する。

`ros2_timeseries_logger.py` のdefaultは `best_effort`。publisher条件に応じて `--qos-reliability reliable` を選べる。

## 8. MMS101の `/dev/mms101_*` aliasがない

検証機では固定aliasが存在せず、FTDI USB serial adapterが `/dev/serial/by-id/...` に見えていた。

```bash
ls -l /dev/serial/by-id/
udevadm info --query=property --name=/dev/ttyUSB0 | grep -E 'ID_(MODEL|SERIAL|SERIAL_SHORT)'
```

`/dev/serial/by-id/` に含まれるidentifierは環境ごとに異なるためrepositoryへ固定値を埋め込まない。また、FTDI adapterのidentifierはsensor本体固有IDと同義とは限らない。adapter/sensor対応を変更する場合は再確認する。

## 9. UMI側MMS101と別環境のMMS101 rateが違う

検証したUMI sensor workspaceのMMS101 nodeは約100 Hzだった。別のUR3用driverでは1 ms intervalを使用する実装が存在する。

「MMS101は常に1 kHz」または「常に100 Hz」と一般化せず、使用するdriver/configurationのtimer/continuous intervalと実測rateを確認する。

## 10. GelSightのadvertised FPSと実測FPSが違う

検証したGelSight MiniはV4L2でMJPEG 3280x2464 @ 25 fpsをadvertiseしたが、`v4l2-ctl` / OpenCV grab / FFmpeg stream-copyでは約18.75 Hzだった。

camera capability表示だけでsampling rateを決めず、実際のframe timestamp/countからrateを測定する。

## 11. GelSightを個別JPEG保存するとrateが低い

Phase 1で作成したfull-resolution JPEG-per-frame比較prototypeでは約8.6 Hzだった。これは研究室既存codeやGelSight公式codeの評価ではなく、今回作成したprototypeの処理負荷による比較結果である。

referenceではV4L2 MJPEGを `ffmpeg -c:v copy` で保存し、capture中のdecode/re-encodeを避ける。

## 12. `ffmpeg -copyts`でoutput fileがemptyになる

絶対monotonic timestampを保持した状態で、duration `-t` をoutput optionとして `-i` より後ろへ置いた試行ではempty outputになった。

本referenceでは `-t` をinput optionとして `-i` より前に置く。

```bash
ffmpeg \
  -copyts \
  -f v4l2 \
  -input_format mjpeg \
  -video_size 3280x2464 \
  -framerate 25 \
  -timestamps default \
  -t 10 \
  -i "$DEVICE" \
  -c:v copy \
  -avoid_negative_ts disabled \
  output.mkv
```

## 13. camera alignmentで冒頭frameがmissingになる

camera loggerをrobot recordingより遅く起動すると、最初のrobot framesより前にcamera frameが存在しないため `missing` になる。これはcausal alignmentの正常な挙動である。

最終検証ではcamera acquisitionを先に開始し、数秒後にrobot recordingを開始する。

`future frames used = 0` を維持したまま `missing = 0` になることを確認する。

## 14. 同じcamera frameが複数robot frameへ割り当てられる

異常ではない。例えば18.75 Hz cameraを30 Hz robot streamへcausal latest-frame alignmentすると、camera frameの再利用が必然的に発生する。

画像をrobot frameごとに複製せず、mappingだけを保存する。

## 15. timestampが同じclockか不明

外部sensorの `header.stamp` やdevice timestampがhost `CLOCK_MONOTONIC` と同じとは限らない。

本referenceでは、ROS 2 numeric sensorはcallback-entryの `receive_monotonic_ns` を標準alignment clockとする。GelSight/V4L2については検証環境でpacket PTSとhost `time.monotonic()` が同じdomainであることを実測確認した。

別hardware/driverへ変更した場合はclock semanticsを再確認する。
