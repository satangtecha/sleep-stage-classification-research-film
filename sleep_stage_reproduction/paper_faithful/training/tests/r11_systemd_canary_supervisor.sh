#!/usr/bin/env bash
set -euo pipefail

sleep_seconds="${1:?sleep seconds required}"
requested_exit_code="${2:?exit code required}"
evidence_root_wsl="${3:?WSL evidence root required}"
evidence_root_windows="${4:?Windows evidence root required}"
lockholder_windows="${5:?Windows lockholder path required}"
invocation_name="${6:?invocation name required}"

powershell_exe='/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'

"$powershell_exe" \
  -NoProfile \
  -NonInteractive \
  -ExecutionPolicy Bypass \
  -File "$lockholder_windows" \
  -EvidenceRoot "$evidence_root_windows" \
  -InvocationName "$invocation_name" \
  -Mode "$([[ "$requested_exit_code" == 0 ]] && printf success || printf failure)" \
  -TimeoutSeconds 180 &
lockholder_proxy_pid=$!

ready_path="${evidence_root_wsl}/lockholder-ready.json"
for _ in $(seq 1 600); do
  if [[ -f "$ready_path" ]]; then
    break
  fi
  if ! kill -0 "$lockholder_proxy_pid" 2>/dev/null; then
    set +e
    wait "$lockholder_proxy_pid"
    lockholder_rc=$?
    set -e
    exit "$lockholder_rc"
  fi
  sleep 0.2
done
if [[ ! -f "$ready_path" ]]; then
  exit 98
fi

exec 3>"${evidence_root_wsl}/wsl-child.stdout.log"
exec 4>"${evidence_root_wsl}/wsl-child.stderr.log"
printf 'WSL_USER=%s\n' "$(id -un)" >&3
printf 'WSL_UID=%s\n' "$(id -u)" >&3
printf 'WSL_PWD=%s\n' "$PWD" >&3
if [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then
  /usr/lib/wsl/lib/nvidia-smi \
    --query-gpu=name,driver_version \
    --format=csv,noheader >&3 2>&4
else
  printf 'WSL_GPU_UNAVAILABLE\n' >&3
fi
exec 3>&-
exec 4>&-

sleep "$sleep_seconds"
status_temp="${evidence_root_wsl}/wsl-child.exit-code.tmp.$$"
printf '%s\n' "$requested_exit_code" >"$status_temp"
mv -f -- "$status_temp" "${evidence_root_wsl}/wsl-child.exit-code.txt"

terminal_observed=false
lifecycle_path="${evidence_root_wsl}/lifecycle.jsonl"
for _ in $(seq 1 900); do
  if [[ -f "$lifecycle_path" ]] && \
     grep -Eq '"event":"terminal_(validated|validation_failed)"' "$lifecycle_path"; then
    terminal_observed=true
    break
  fi
  sleep 0.2
done
if [[ "$terminal_observed" != true ]]; then
  exit 99
fi

set +e
wait "$lockholder_proxy_pid"
lockholder_rc=$?
set -e
if [[ "$lockholder_rc" -ne "$requested_exit_code" ]]; then
  exit 100
fi
exit "$requested_exit_code"
