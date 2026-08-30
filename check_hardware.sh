#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"

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

cd "$TROSSEN_DIR"

exec uv run python "$ROOT_DIR/scripts/check_hardware.py" \
    --config "$ROOT_DIR/config/teleop-lab.yaml" \
    --trossen-dir "$TROSSEN_DIR" \
    --data-root "$ROOT_DIR/data"
