# Tutorial ALOHA RLDS builder (`aloha_vla_demo`)

This is an adaptation of the [OpenVLA-OFT ALOHA builder example](https://github.com/moojink/rlds_dataset_builder/tree/main/aloha1_put_X_into_pot_300_demos) at commit `6174b0b6bb69df6361f1117944952bf14afb0cc3`. `conversion_utils.py` comes from that upstream example. See the [upstream license](https://github.com/moojink/rlds_dataset_builder/blob/main/LICENSE) when redistributing the code.

The conversion reads `train/*.hdf5` under `ALOHA_HDF5_ROOT`, preserves four 256×256 RGB views, 14D joint states and actions, and the language instruction in each source file's HDF5 attribute. It creates an RLDS/TFDS train split. The OpenVLA-OFT loader selects the high and two wrist views; the low view remains stored but is not used by that three-camera setting.

The 598-step episode used for validation is not distributed with this tutorial. This packaged builder was run with `ALOHA_HDF5_ROOT` after renaming to `aloha_vla_demo`; it generated one RLDS episode, which the patched OpenVLA-OFT loader read as three images, 14D proprioception, and 30×14 actions. Run the HDF5-to-RLDS readback in [the tutorial](../../../docs/09_openvla_oft_data_bridge.md) for your own data. Model fine-tuning and robot control were not validated.
