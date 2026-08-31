#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"
CONFIG="$ROOT_DIR/config/record-local.yaml"

if [[ ! -f "$CONFIG" ]]; then
    echo "[FAIL] Local recording config not found:"
    echo "       $CONFIG"
    echo "Create it from config/record-template.yaml and set this machine's hardware identifiers."
    exit 1
fi

if [[ $# -lt 1 ]]; then
    echo "Usage:"
    echo "  ./validate_dataset.sh DATASET_PATH [validator options]"
    exit 2
fi

DATASET_PATH="$1"
shift

# Resolve relative dataset paths before changing directory.
if [[ "$DATASET_PATH" != /* ]]; then
    DATASET_PATH="$ROOT_DIR/$DATASET_PATH"
fi

if [[ ! -d "$DATASET_PATH" ]]; then
    echo "[FAIL] Dataset directory not found:"
    echo "       $DATASET_PATH"
    exit 1
fi

cd "$TROSSEN_DIR"

exec uv run python "$ROOT_DIR/scripts/validate_dataset.py" \
    "$DATASET_PATH" \
    --config "$ROOT_DIR/config/record-local.yaml" \
    "$@"
