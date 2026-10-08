"""Copy a pinned HF snapshot into a new work area before OFT changes model files."""
import argparse
import json
import shutil
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    raise FileExistsError(a.output)
repo = 'openvla/openvla-7b'
revision = HfApi().model_info(repo).sha
source = Path(snapshot_download(repo_id=repo, revision=revision))
# OFT rewrites config/modeling files: do not point it at shared HF cache.
shutil.copytree(source, a.output, symlinks=False)
(a.output/'validation_source.json').write_text(json.dumps({'repo':repo, 'revision':revision}, indent=2))
print('BASE MODEL COPY: PASS; revision=', revision)
