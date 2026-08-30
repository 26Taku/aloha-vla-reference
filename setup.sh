#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TROSSEN_DIR="$ROOT_DIR/lerobot_trossen"

TROSSEN_REPO="https://github.com/TrossenRobotics/lerobot_trossen.git"
TROSSEN_COMMIT="a4336933f34192a3daa7e9fb52674284bb5ae48e"

echo "=== ALOHA Reference Setup ==="
echo

# ------------------------------------------------------------
# Basic commands
# ------------------------------------------------------------
for cmd in git uv; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[FAIL] Required command not found: $cmd"
        if [[ "$cmd" == "uv" ]]; then
            echo "Install uv following the official uv installation instructions."
        fi
        exit 1
    fi
done

echo "[OK] git: $(git --version)"
echo "[OK] uv:  $(uv --version)"
echo

# ------------------------------------------------------------
# OS information
# ------------------------------------------------------------
if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    echo "Operating system: ${PRETTY_NAME:-unknown}"

    if [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]]; then
        echo "[OK] Reference OS family: Ubuntu 24.04"
    else
        echo "[WARN] Reference environment was validated on Ubuntu 24.04."
    fi
fi

echo

# ------------------------------------------------------------
# Trossen repository
# ------------------------------------------------------------
if [[ ! -d "$TROSSEN_DIR/.git" ]]; then
    echo "Cloning official Trossen LeRobot plugin..."
    git clone "$TROSSEN_REPO" "$TROSSEN_DIR"
fi

ACTUAL_REMOTE="$(git -C "$TROSSEN_DIR" remote get-url origin 2>/dev/null || true)"

if [[ "$ACTUAL_REMOTE" != "$TROSSEN_REPO" ]]; then
    echo "[FAIL] Unexpected origin:"
    echo "       $ACTUAL_REMOTE"
    echo "Expected:"
    echo "       $TROSSEN_REPO"
    exit 1
fi

if [[ -n "$(git -C "$TROSSEN_DIR" status --porcelain)" ]]; then
    echo "[FAIL] Trossen repository has local modifications."
    echo "       Refusing to change revisions automatically."
    echo
    git -C "$TROSSEN_DIR" status --short
    exit 1
fi

CURRENT_COMMIT="$(git -C "$TROSSEN_DIR" rev-parse HEAD)"

if [[ "$CURRENT_COMMIT" != "$TROSSEN_COMMIT" ]]; then
    echo "Checking out validated Trossen revision..."
    git -C "$TROSSEN_DIR" fetch origin "$TROSSEN_COMMIT"
    git -C "$TROSSEN_DIR" checkout --detach "$TROSSEN_COMMIT"
fi

CURRENT_COMMIT="$(git -C "$TROSSEN_DIR" rev-parse HEAD)"

if [[ "$CURRENT_COMMIT" != "$TROSSEN_COMMIT" ]]; then
    echo "[FAIL] Could not select validated Trossen revision."
    exit 1
fi

echo "[OK] Trossen revision: ${CURRENT_COMMIT:0:12}"
echo

# ------------------------------------------------------------
# Python environment
# ------------------------------------------------------------
echo "Creating/verifying isolated Python environment..."
cd "$TROSSEN_DIR"
uv sync --frozen

echo

PYTHON_VERSION="$(uv run python -c 'import platform; print(platform.python_version())')"
LEROBOT_VERSION="$(uv run python -c 'import importlib.metadata as m; print(m.version("lerobot"))')"
TROSSEN_ARM_VERSION="$(uv run python -c 'import importlib.metadata as m; print(m.version("trossen-arm"))')"

echo "[OK] Python:      $PYTHON_VERSION"
echo "[OK] LeRobot:     $LEROBOT_VERSION"
echo "[OK] trossen-arm: $TROSSEN_ARM_VERSION"

echo

# ------------------------------------------------------------
# Lab directories
# ------------------------------------------------------------
mkdir -p "$ROOT_DIR/data" "$ROOT_DIR/logs"

echo "=== Setup complete ==="
echo
echo "Next:"
echo "  ./check_hardware.sh"
