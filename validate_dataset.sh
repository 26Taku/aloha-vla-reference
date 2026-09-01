#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"
HARDWARE_CONFIG="$ROOT_DIR/config/hardware-local.yaml"
RECORD_TEMPLATE="$ROOT_DIR/config/record-template.yaml"
RUNTIME_DIR="$ROOT_DIR/.runtime"
RUNTIME_CONFIG="$RUNTIME_DIR/validate.yaml"

if [[ $# -lt 1 ]]; then
    echo "Usage:"
    echo "  ./validate_dataset.sh DATASET_PATH [validator options...]"
    exit 2
fi

DATASET_PATH="$1"
shift

if [[ "$DATASET_PATH" != /* ]]; then
    DATASET_PATH="$ROOT_DIR/$DATASET_PATH"
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

mkdir -p "$RUNTIME_DIR"

cd "$TROSSEN_DIR"

uv run python "$ROOT_DIR/scripts/build_runtime_config.py" \
    --template "$RECORD_TEMPLATE" \
    --hardware "$HARDWARE_CONFIG" \
    --output "$RUNTIME_CONFIG"

exec uv run python "$ROOT_DIR/scripts/validate_dataset.py" \
    "$DATASET_PATH" \
    --config "$RUNTIME_CONFIG" \
    "$@"
