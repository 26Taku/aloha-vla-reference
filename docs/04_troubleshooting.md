# Troubleshooting

## 1. この資料の役割

本資料は、**通常フローが途中で止まったときの症状別切り分け**に限定する。

通常の実行順序は [02 Data Collection](02_data_collection.md) を参照する。ここではsetupからrecordingまでの手順を再掲しない。

## 2. `setup.sh` が失敗する

### `git` / `uv` が見つからない

```bash
git --version
uv --version
```

不足しているcommandを導入してから再実行する。

### `lerobot_trossen` にlocal modificationがある

`setup.sh` は既存の変更を自動破棄しない。成果物直下の `lerobot_trossen/` にlocal modificationがある場合は停止する。

```bash
git -C lerobot_trossen status --short
```

必要な変更を退避するか、clean directoryで再構築する。

## 3. `check_hardware.sh` がlocal config不足で止まる

tracked templateからlocal configを作成し、hardware identifierを設定する。

詳細は [02 Data Collection - Hardware identification](02_data_collection.md#4-hardware-identification--local-configuration) を参照する。

## 4. `REPLACE_WITH_...` が残っている

```bash
grep -RIn 'REPLACE_WITH_' \
  config/teleop-local.yaml \
  config/record-local.yaml
```

出力されたfieldを対象hardwareの値へ置き換える。tracked template自体はplaceholderのまま維持する。

## 5. Armにpingが通らない

まずArm電源とPC側network interfaceを確認する。

```bash
ip -br addr
ip neigh
grep -n 'arm_ip_address' config/teleop-local.yaml
```

対象IPへ個別に確認する場合:

```bash
ARM_IP=YOUR_CONFIGURED_ARM_IP
ping -c 2 "$ARM_IP"
```

4 Armすべてに到達できない場合は、個別IP誤設定より先に電源・network接続を疑う。

ping成功はnetwork reachabilityのみを示す。driverを含む実動作はteleoperationで確認する。

## 6. RealSenseが認識されない / serialが一致しない

接続deviceを再列挙する。

```bash
rs-enumerate-devices
```

またはLeRobot environmentの `pyrealsense2` を使用する。

USB差し替えやcamera交換時は `/dev/videoX` indexではなくserialを基準にする。

4台のserialが見えていてもphysical roleが誤っている場合があるため、映像と `cam_high` / `cam_low` / wrist cameraの対応も確認する。

## 7. Rerun / Vulkan / EGL warningが出る

graphics backend由来のwarningだけで失敗と判断しない。

確認するもの:

- Arm controlが継続している
- camera viewが更新されている
- processが異常終了していない
- recording後のDataset validatorがPASSする

viewer自体を問題から切り離せる場合はdisplayを無効にして切り分ける。

## 8. Dataset directory already exists

`record.sh` は既存datasetを上書きしない。

別の `DATASET_NAME` を使用するか、既存dataが不要であることを確認してから手動で退避・削除する。

## 9. frame数が `duration x fps` と完全一致しない

recording loopの開始・終了境界により1 frame程度ずれる場合がある。

固定個数だけで成否を判断せず、`validate_dataset.sh` でmetadata、Parquet、frame ordering、videoを確認する。

## 10. 外部ROS 2 sensor loggerが0 sample

publisherが実際に動作しているかを先に確認する。

```bash
ros2 topic list
ros2 topic hz /YOUR_TOPIC
ros2 topic info -v /YOUR_TOPIC
```

publisher停止をQoS mismatchと誤認しない。

`ros2_timeseries_logger.py` はreliabilityを選択できるため、publisherのQoSに合わせる。

## 11. USB serial deviceの固定aliasがない

```bash
ls -l /dev/serial/by-id/
```

必要なら:

```bash
udevadm info --query=property --name=/dev/ttyUSB0 \
  | grep -E 'ID_(MODEL|SERIAL|SERIAL_SHORT)'
```

`/dev/serial/by-id/` のidentifierは環境固有であり、tracked repositoryへ固定値を入れない。

USB-serial adapterのidentifierがsensor本体の固有IDと同義とは限らない点にも注意する。

## 12. sensorの実測rateが想定と違う

driver設定・timer・device modeと実測rateを確認する。

sensor名だけから「常に100 Hz」「常に1 kHz」等と一般化しない。reference validationで得たrateは [06 Validation Results](06_validation_results.md) に記録している。

## 13. GelSightのadvertised FPSと実測FPSが違う

camera capability表示と実際のsampling rateは一致しない場合がある。

frame count / timestampから実効rateを測定する。Phase 1の実測例は [06 Validation Results](06_validation_results.md) を参照する。

## 14. camera保存でrateが大きく低下する

decode、resize、JPEG再encode、個別file I/O等をcapture pathへ入れるとthroughputが低下する可能性がある。

本referenceでは異FPS cameraのcanonical raw保存としてnative compressed stream copyを採用する。設計理由は [03 Architecture and Extension](03_architecture_and_extension.md) を参照する。

## 15. `ffmpeg -copyts` でoutputがemptyになる

absolute timestampを保持する場合、duration optionの位置に注意する。

reference例では `-t` をinput optionとして `-i` より前に置く。

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

## 16. camera alignmentで冒頭frameがmissingになる

camera acquisitionをrobot recordingより遅く開始すると、最初のrobot frame以前にcamera frameが存在しないためmissingになる。これはcausal alignmentとして正常。

cameraを先に開始し、その後robot recordingを開始する。

## 17. 同じcamera frameが複数robot frameへ割り当てられる

異FPS cameraをより高FPSのrobot streamへlatest-frame alignmentする場合は正常。

raw imageをrobot frameごとに複製せず、mappingだけを保存する。

## 18. timestampのclock semanticsが不明

source/device timestampとhost `CLOCK_MONOTONIC` が同じclockとは限らない。

本referenceではhost側で取得したmonotonic timestampをalignment基準とする。driver/hardwareを変更した場合はclock semanticsを再確認する。
