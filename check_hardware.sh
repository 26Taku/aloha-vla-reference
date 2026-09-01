#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"
HARDWARE_CONFIG="$ROOT_DIR/config/hardware-local.yaml"
TELEOP_TEMPLATE="$ROOT_DIR/config/teleop-template.yaml"
RECORD_TEMPLATE="$ROOT_DIR/config/record-template.yaml"
RUNTIME_DIR="$ROOT_DIR/.runtime"

if ! command -v uv >/dev/null 2>&1; then
    echo "[FAIL] uv is not available."
    exit 1
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

TELEOP_RUNTIME="$RUNTIME_DIR/preflight-teleop.yaml"
RECORD_RUNTIME="$RUNTIME_DIR/preflight-record.yaml"

cd "$TROSSEN_DIR"

uv run python "$ROOT_DIR/scripts/build_runtime_config.py" \
    --template "$TELEOP_TEMPLATE" \
    --hardware "$HARDWARE_CONFIG" \
    --output "$TELEOP_RUNTIME"

uv run python "$ROOT_DIR/scripts/build_runtime_config.py" \
    --template "$RECORD_TEMPLATE" \
    --hardware "$HARDWARE_CONFIG" \
    --output "$RECORD_RUNTIME"

exec uv run python "$ROOT_DIR/scripts/check_hardware.py" \
    --teleop-config "$TELEOP_RUNTIME" \
    --record-config "$RECORD_RUNTIME" \
    --trossen-dir "$TROSSEN_DIR" \
    --data-root "$ROOT_DIR/data"
