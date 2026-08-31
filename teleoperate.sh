#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"
CONFIG="$ROOT_DIR/config/teleop-local.yaml"

if [[ ! -d "$TROSSEN_DIR" ]]; then
    echo "[FAIL] Trossen environment not found."
    echo "Run ./setup.sh first."
    exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
    echo "[FAIL] Local teleoperation config not found:"
    echo "       $CONFIG"
    echo "Create it from config/teleop-template.yaml and set this machine's hardware identifiers."
    exit 1
fi

cd "$TROSSEN_DIR"

exec uv run lerobot-teleoperate \
    --config_path="$CONFIG"
