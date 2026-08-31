#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"
TELEOP_CONFIG="$ROOT_DIR/config/teleop-local.yaml"
RECORD_CONFIG="$ROOT_DIR/config/record-local.yaml"

if ! command -v uv >/dev/null 2>&1; then
    echo "[FAIL] uv is not available."
    echo "Run ./setup.sh first."
    exit 1
fi

if [[ ! -d "$TROSSEN_DIR" ]]; then
    echo "[FAIL] Trossen repository not found:"
    echo "       $TROSSEN_DIR"
    echo "Run ./setup.sh first."
    exit 1
fi

if [[ ! -f "$TELEOP_CONFIG" || ! -f "$RECORD_CONFIG" ]]; then
    echo "[FAIL] Machine-specific config files are missing."
    echo "Create them from the tracked templates, then replace all REPLACE_WITH_... values:"
    echo "  cp config/teleop-template.yaml config/teleop-local.yaml"
    echo "  cp config/record-template.yaml config/record-local.yaml"
    exit 1
fi

cd "$TROSSEN_DIR"

exec uv run python "$ROOT_DIR/scripts/check_hardware.py" \
    --teleop-config "$TELEOP_CONFIG" \
    --record-config "$RECORD_CONFIG" \
    --trossen-dir "$TROSSEN_DIR" \
    --data-root "$ROOT_DIR/data"
