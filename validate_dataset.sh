#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"
RECORD_TEMPLATE="$ROOT_DIR/config/record-template.yaml"

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

# Dataset validation needs camera feature names, not physical device identities.
cd "$TROSSEN_DIR"

exec uv run python "$ROOT_DIR/scripts/validate_dataset.py" \
    "$DATASET_PATH" \
    --config "$RECORD_TEMPLATE" \
    "$@"
