#!/usr/bin/env bash
# Usage: run_with_log.sh LOG COMMAND [ARG ...]
# Preserve the command's environment, working directory, arguments and exit status.
set -u
if (( $# < 2 )); then
    printf '%s\n' 'Usage: run_with_log.sh LOG COMMAND [ARG ...]' >&2
    exit 2
fi
_aloha_log=$1
shift
mkdir -p -- "$(dirname -- "$_aloha_log")" || exit 1
# Refuse to overwrite earlier evidence, including when two runs race.
if ! (set -o noclobber; printf 'Started UTC: %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$_aloha_log") 2>/dev/null; then
    printf 'Log already exists or cannot be created: %s\n' "$_aloha_log" >&2
    exit 1
fi
"$@" 2>&1 | tee -a "$_aloha_log"
_aloha_status=("${PIPESTATUS[@]}")
printf 'Finished UTC: %s\nCommand exit status: %s\nLog writer exit status: %s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${_aloha_status[0]}" "${_aloha_status[1]}" >> "$_aloha_log" || exit 1
if (( _aloha_status[0] != 0 )); then
    exit "${_aloha_status[0]}"
fi
exit "${_aloha_status[1]}"
