#!/usr/bin/env bash
set -euo pipefail

sleep_seconds="${1:?sleep seconds required}"
requested_exit_code="${2:?exit code required}"
evidence_root="${3:?evidence root required}"

exec >"${evidence_root}/wsl-child.stdout.log" \
  2>"${evidence_root}/wsl-child.stderr.log"

printf 'WSL_USER=%s\n' "$(id -un)"
printf 'WSL_UID=%s\n' "$(id -u)"
printf 'WSL_PWD=%s\n' "$PWD"

if [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then
  /usr/lib/wsl/lib/nvidia-smi \
    --query-gpu=name,driver_version \
    --format=csv,noheader
else
  printf 'WSL_GPU_UNAVAILABLE\n'
fi

sleep "$sleep_seconds"
printf '%s\n' "$requested_exit_code" >"${evidence_root}/wsl-child.exit-code.tmp"
mv -f -- \
  "${evidence_root}/wsl-child.exit-code.tmp" \
  "${evidence_root}/wsl-child.exit-code.txt"
exit "$requested_exit_code"
