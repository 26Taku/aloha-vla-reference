#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"
TEMPLATE="$ROOT_DIR/config/record-template.yaml"
RUNTIME_DIR="$ROOT_DIR/.runtime"

usage() {
    echo 'Usage:'
    echo '  ./record.sh DATASET_NAME "TASK" [NUM_EPISODES] [EPISODE_TIME_S]'
    echo
    echo 'Example:'
    echo '  ./record.sh pick_cube "Pick up the cube." 20 30'
}

if [[ $# -lt 2 || $# -gt 4 ]]; then
    usage
    exit 2
fi

DATASET_NAME="$1"
TASK="$2"
NUM_EPISODES="${3:-10}"
EPISODE_TIME_S="${4:-30}"

if [[ ! "$DATASET_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "[FAIL] Invalid DATASET_NAME."
    exit 2
fi

if [[ ! "$NUM_EPISODES" =~ ^[1-9][0-9]*$ ]]; then
    echo "[FAIL] NUM_EPISODES must be a positive integer."
    exit 2
fi

if [[ ! "$EPISODE_TIME_S" =~ ^[1-9][0-9]*$ ]]; then
    echo "[FAIL] EPISODE_TIME_S must be a positive integer."
    exit 2
fi

DATASET_ROOT="$ROOT_DIR/data/$DATASET_NAME"

if [[ -e "$DATASET_ROOT" ]]; then
    echo "[FAIL] Dataset already exists:"
    echo "       $DATASET_ROOT"
    exit 1
fi

mkdir -p "$RUNTIME_DIR"
RUNTIME_CONFIG="$RUNTIME_DIR/record-${DATASET_NAME}.yaml"

cd "$TROSSEN_DIR"

uv run python - \
    "$TEMPLATE" \
    "$RUNTIME_CONFIG" \
    "$DATASET_NAME" \
    "$TASK" \
    "$DATASET_ROOT" \
    "$NUM_EPISODES" \
    "$EPISODE_TIME_S" <<'PY'
import sys
from pathlib import Path
import yaml

template = Path(sys.argv[1])
output = Path(sys.argv[2])

cfg = yaml.safe_load(template.read_text())

cfg["dataset"]["repo_id"] = f"lab/{sys.argv[3]}"
cfg["dataset"]["single_task"] = sys.argv[4]
cfg["dataset"]["root"] = sys.argv[5]
cfg["dataset"]["num_episodes"] = int(sys.argv[6])
cfg["dataset"]["episode_time_s"] = int(sys.argv[7])

# Lab defaults: keep data local unless deliberately changed.
cfg["dataset"]["push_to_hub"] = False
cfg["dataset"]["private"] = True
cfg["dataset"]["video"] = True

output.write_text(
    yaml.safe_dump(cfg, sort_keys=False),
    encoding="utf-8",
)
PY

echo "=== ALOHA Recording ==="
echo "Dataset:      $DATASET_NAME"
echo "Task:         $TASK"
echo "Episodes:     $NUM_EPISODES"
echo "Episode time: ${EPISODE_TIME_S}s"
echo "Output:       $DATASET_ROOT"
echo "Hub upload:   disabled"
echo

exec uv run lerobot-record \
    --config_path="$RUNTIME_CONFIG"
