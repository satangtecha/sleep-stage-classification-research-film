#!/usr/bin/env bash
set -euo pipefail

expected_gate_sha="${1:?canonical gate SHA-256 required}"
expected_confirmation_sha="${2:?confirmation SHA-256 required}"
expected_dispatch_nonce="${3:?dispatch nonce required}"

bulk_root=/mnt/e/blp/sleep_stage_reproduction
evidence_root_wsl="$bulk_root/runtime/training-logs"
prefix=paper-text-v1-multiseed-cap128-r11-20260830
project_root_windows='C:\Users\Acer\OneDrive\Documents\เป้าๆรวยๆๆๆ\sleep_stage_reproduction'
lockholder_windows="$project_root_windows\paper_faithful\training\hold_paper_text_multiseed_smoke_r11.ps1"
powershell_exe=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
lifecycle="$evidence_root_wsl/$prefix.lifecycle.jsonl"
ready="$evidence_root_wsl/$prefix.lockholder-ready.json"
stdout_log="$evidence_root_wsl/$prefix.stdout.log"
stderr_log="$evidence_root_wsl/$prefix.stderr.log"
exit_evidence="$evidence_root_wsl/$prefix.workload-exit-code.txt"

"$powershell_exe" \
  -NoProfile \
  -NonInteractive \
  -ExecutionPolicy Bypass \
  -File "$lockholder_windows" \
  -ExpectedCanonicalGateSha256 "$expected_gate_sha" \
  -ExpectedUserConfirmationSha256 "$expected_confirmation_sha" \
  -ExpectedDispatchNonce "$expected_dispatch_nonce" &
lockholder_proxy_pid=$!

for _ in $(seq 1 900); do
  if [[ -f "$ready" ]]; then
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
if [[ ! -f "$ready" ]]; then
  exit 98
fi

existing_training="$(pgrep -af '[p]aper_faithful.training.cli (pilot|multi-seed-pilot)' || true)"
if [[ -n "$existing_training" ]]; then
  printf 'Native WSL training-process collision:\n%s\n' "$existing_training" >"$stderr_log"
  : >"$stdout_log"
  workload_rc=101
else
  set +e
  ./paper_faithful/training/run_paper_text_multiseed_smoke_r11.sh \
    >"$stdout_log" \
    2>"$stderr_log"
  workload_rc=$?
  set -e
fi

exit_temp="$exit_evidence.tmp.$$"
printf '%s\n' "$workload_rc" >"$exit_temp"
mv -f -- "$exit_temp" "$exit_evidence"

terminal_observed=false
for _ in $(seq 1 1800); do
  if [[ -f "$lifecycle" ]] && \
     grep -Eq '"event":"terminal_(validated|validation_failed)"' "$lifecycle"; then
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
if [[ "$lockholder_rc" -ne "$workload_rc" ]]; then
  exit 100
fi
exit "$workload_rc"
