"""Register the custom TFDS builder before invoking the unchanged OFT trainer."""
import os
import runpy
from pathlib import Path

import tensorflow as tf
tf.config.set_visible_devices([], 'GPU')  # TensorFlow decodes data; PyTorch owns the GPU.
import aloha_vla_demo.aloha_vla_demo_dataset_builder

target = Path(os.environ['OFT'])/'vla-scripts/finetune.py'
runpy.run_path(str(target), run_name='__main__')
