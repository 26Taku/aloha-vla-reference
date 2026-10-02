#!/usr/bin/env bash
# Source from the repository root: source ./scripts/session.sh
# Only sets paths in the current shell; installs nothing and writes no files.
if [[ -z "${BASH_VERSION:-}" ]]; then
    printf '%s\n' 'Use bash to source scripts/session.sh.' >&2
    return 2 2>/dev/null || exit 2
fi

_aloha_session_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)" || return
export REPO="$_aloha_session_root"
export DATASET="${DATASET:-$REPO/data/aloha_vla_demo}"
export OUTPUTS="${OUTPUTS:-$REPO/outputs}"
export BRIDGE="${BRIDGE:-$(dirname -- "$REPO")/openvla_oft_bridge}"
export BUILDER_ENV="${BUILDER_ENV:-$(dirname -- "$REPO")/rlds-builder-env}"
export OFT="${OFT:-$(dirname -- "$REPO")/openvla-oft}"
unset _aloha_session_root
printf 'Repository: %s\nDataset: %s\n' "$REPO" "$DATASET"
