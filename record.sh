#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"
HARDWARE_CONFIG="$ROOT_DIR/config/hardware-local.yaml"
TEMPLATE="$ROOT_DIR/config/record-template.yaml"
RUNTIME_DIR="$ROOT_DIR/.runtime"

usage() {
    echo 'Usage:'
    echo '  ./record.sh DATASET_NAME "TASK" [NUM_EPISODES] [EPISODE_TIME_S]'
}

if [[ $# -lt 2 || $# -gt 4 ]]; then
    usage
    exit 2
fi

DATASET_NAME="$1"
TASK="$2"
NUM_EPISODES="${3:-1}"
EPISODE_TIME_S="${4:-15}"

if [[ "$DATASET_NAME" == */* || "$DATASET_NAME" == "." || "$DATASET_NAME" == ".." ]]; then
    echo "[FAIL] DATASET_NAME must be a single directory name without '/'."
    exit 2
fi

if [[ ! "$NUM_EPISODES" =~ ^[0-9]+$ || "$NUM_EPISODES" -lt 1 ]]; then
    echo "[FAIL] NUM_EPISODES must be a positive integer."
    exit 2
fi

if [[ ! "$EPISODE_TIME_S" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "[FAIL] EPISODE_TIME_S must be a positive number."
    exit 2
fi

if [[ ! -d "$TROSSEN_DIR" ]]; then
    echo "[FAIL] Trossen environment not found:"
    echo "       $TROSSEN_DIR"
    echo "Run ./setup.sh first."
    exit 1
fi

if [[ ! -f "$HARDWARE_CONFIG" ]]; then
    echo "[FAIL] Local hardware config not found:"
    echo "       $HARDWARE_CONFIG"
    echo "Create it with:"
    echo "  cp config/hardware-template.yaml config/hardware-local.yaml"
    exit 1
fi

DATASET_ROOT="$ROOT_DIR/data/$DATASET_NAME"
if [[ -e "$DATASET_ROOT" ]]; then
    echo "[FAIL] Dataset already exists:"
    echo "       $DATASET_ROOT"
    exit 1
fi

mkdir -p "$RUNTIME_DIR" "$ROOT_DIR/data"

RUNTIME_CONFIG="$RUNTIME_DIR/record-${DATASET_NAME}.yaml"

cd "$TROSSEN_DIR"

uv run python "$ROOT_DIR/scripts/build_runtime_config.py" \
    --template "$TEMPLATE" \
    --hardware "$HARDWARE_CONFIG" \
    --output "$RUNTIME_CONFIG" \
    --dataset-name "$DATASET_NAME" \
    --task "$TASK" \
    --num-episodes "$NUM_EPISODES" \
    --episode-time-s "$EPISODE_TIME_S" \
    --dataset-root "$DATASET_ROOT"

exec uv run lerobot-record \
    --config_path="$RUNTIME_CONFIG"
