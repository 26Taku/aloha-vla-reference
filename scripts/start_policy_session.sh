#!/usr/bin/env bash
# Creates a run record and session pointer, without loading or moving a robot.
set -euo pipefail
for name in REPO CLIENT_PY INFER_PY RECORD_CFG CHECKPOINT POLICY_TYPE MODEL_CACHE GPU_UUID JOINT_CAP GRIPPER_CAP; do
    if [[ -z "${!name:-}" ]]; then printf 'Missing %s; complete chapter 11 Steps 1-3 before creating a session.\n' "$name" >&2; exit 2; fi
done
test -x "$CLIENT_PY"
test -x "$INFER_PY"
test -f "$RECORD_CFG"
test -f "$CHECKPOINT/config.json"
test -d "$MODEL_CACHE"
umask 077
mkdir -p "$REPO/outputs/robot_trials" "$REPO/.runtime"
SESSION_DIR=$(mktemp -d "$REPO/outputs/robot_trials/session-$POLICY_TYPE-XXXXXXXX")
cp "$RECORD_CFG" "$SESSION_DIR/record-source.yaml"
RECORD_CFG="$SESSION_DIR/record-source.yaml"
for name in REPO CLIENT_PY INFER_PY RECORD_CFG CHECKPOINT POLICY_TYPE MODEL_CACHE GPU_UUID JOINT_CAP GRIPPER_CAP SESSION_DIR; do
    printf 'export %s=%q\n' "$name" "${!name}"
done > "$SESSION_DIR/session.sh"
cp "$REPO/scripts/robot_policy_server.py" "$REPO/scripts/robot_policy_client.py" "$SESSION_DIR/"
uv pip freeze --python "$INFER_PY" > "$SESSION_DIR/inference-packages.txt"
uv pip freeze --python "$CLIENT_PY" > "$SESSION_DIR/client-packages.txt"
git -C "$REPO" rev-parse HEAD > "$SESSION_DIR/manual_commit.txt"
git -C "$REPO" diff -- scripts docs/11_robot_policy_execution.md > "$SESSION_DIR/manual_changes.patch"
git -C "$REPO/lerobot_trossen" rev-parse HEAD > "$SESSION_DIR/plugin_commit.txt"
# Record hashes of the config and executed code alongside the Git metadata.
"$CLIENT_PY" -I - "$SESSION_DIR" <<'PYHASH'
import hashlib
import json
import sys
from pathlib import Path
session = Path(sys.argv[1])
files = ["record-source.yaml", "robot_policy_server.py", "robot_policy_client.py"]
checksums = {name: hashlib.sha256((session / name).read_bytes()).hexdigest() for name in files}
(session / "file_sha256.json").write_text(json.dumps(checksums, indent=2) + "\n")
PYHASH
# Atomically update the same-PC pointer; earlier sessions remain intact.
_pointer=$(mktemp "$REPO/.runtime/policy-session-XXXXXXXX")
printf 'source %q\n' "$SESSION_DIR/session.sh" > "$_pointer"
mv -- "$_pointer" "$REPO/.runtime/policy-session.sh"
printf 'Session: %s\n' "$SESSION_DIR"
printf 'Both terminals: source "$REPO/.runtime/policy-session.sh"\n'
