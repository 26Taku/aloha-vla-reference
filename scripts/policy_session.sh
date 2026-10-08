#!/usr/bin/env bash
# Load paths only. Never prompts, installs packages, or connects to a robot.
if [[ -z "${BASH_VERSION:-}" ]]; then
    printf '%s\n' 'Use bash to source scripts/policy_session.sh.' >&2
    return 2 2>/dev/null || exit 2
fi
_policy_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)" || return
source "$_policy_repo/scripts/session.sh" || return
export POLICY_TYPE="${POLICY_TYPE:-smolvla}"
case "$POLICY_TYPE" in smolvla|pi05) ;; *) printf 'Unsupported policy: %s\n' "$POLICY_TYPE" >&2; return 2 ;; esac
export CLIENT_PY="${CLIENT_PY:-$REPO/lerobot_trossen/.venv/bin/python}"
export INFER_PY="${INFER_PY:-$REPO/.venvs/vla-inference/bin/python}"
# Recompute: earlier chapters may have selected a short smoke checkpoint,
# and earlier sessions may have selected a snapshot of the record config.
export RECORD_CFG="$REPO/.runtime/record-$(basename -- "$DATASET").yaml"
export CHECKPOINT="$OUTPUTS/${POLICY_TYPE}_4cam_20k/checkpoints/020000/pretrained_model"
export MODEL_CACHE="${MODEL_CACHE:-${HF_HUB_CACHE:-${HF_HOME:-$HOME/.cache/huggingface}/hub}}"
_policy_local="$REPO/.runtime/policy-local.sh"
_policy_checkpoint="$REPO/.runtime/policy-checkpoint-$POLICY_TYPE.sh"
if [[ -f "$_policy_local" ]]; then source "$_policy_local" || return; fi
if [[ -f "$_policy_checkpoint" ]]; then source "$_policy_checkpoint" || return; fi
printf 'Policy: %s\nRecord config: %s\nCheckpoint: %s\nInference Python: %s\n' \
    "$POLICY_TYPE" "$RECORD_CFG" "$CHECKPOINT" "$INFER_PY"
printf '%s\n' 'Paths loaded. GPU and motion limits are configured in the later steps; no robot connected.'
unset _policy_repo _policy_local _policy_checkpoint
