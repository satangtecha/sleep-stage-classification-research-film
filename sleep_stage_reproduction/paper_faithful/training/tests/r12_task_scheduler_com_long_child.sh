#!/usr/bin/env bash
set -euo pipefail

sleep_seconds="${1:?sleep seconds required}"
requested_exit_code="${2:?exit code required}"
evidence_root="${3:?evidence root required}"
heartbeat_interval=5

if (( sleep_seconds < 2 )); then
  printf 'sleep seconds must be at least 2\n' >&2
  exit 64
fi

exec >"${evidence_root}/wsl-child.stdout.log" \
  2>"${evidence_root}/wsl-child.stderr.log"

wsl_user="$(id -un)"
wsl_uid="$(id -u)"
boot_id="$(cat /proc/sys/kernel/random/boot_id)"
if [[ -z "${boot_id}" ]]; then
  printf 'missing WSL boot id\n' >&2
  exit 65
fi

printf 'WSL_USER=%s\n' "${wsl_user}"
printf 'WSL_UID=%s\n' "${wsl_uid}"
printf 'WSL_BOOT_ID=%s\n' "${boot_id}"
printf 'WSL_PWD=%s\n' "$PWD"

if [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then
  gpu_line="$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=name,driver_version --format=csv,noheader | head -n 1)"
  if [[ -z "${gpu_line}" ]]; then
    printf 'WSL_GPU_UNAVAILABLE\n'
    exit 66
  fi
  printf 'WSL_GPU=%s\n' "${gpu_line}"
else
  printf 'WSL_GPU_UNAVAILABLE\n'
  exit 66
fi

heartbeat_path="${evidence_root}/wsl-child.heartbeats.jsonl"
deadline=$(( $(date +%s) + sleep_seconds ))
while :; do
  now="$(date +%s)"
  current_boot_id="$(cat /proc/sys/kernel/random/boot_id)"
  if [[ "${current_boot_id}" != "${boot_id}" ]]; then
    printf 'WSL boot id changed while child was running\n' >&2
    exit 67
  fi
  printf '{"event":"heartbeat","epoch_seconds":%s,"wsl_user":"%s","boot_id":"%s"}\n' \
    "${now}" "${wsl_user}" "${boot_id}" >>"${heartbeat_path}"
  remaining=$(( deadline - now ))
  if (( remaining <= 0 )); then
    break
  fi
  if (( remaining < heartbeat_interval )); then
    sleep "${remaining}"
  else
    sleep "${heartbeat_interval}"
  fi
done

tmp_exit="${evidence_root}/wsl-child.exit-code.$$.tmp"
printf '%s\n' "${requested_exit_code}" >"${tmp_exit}"
mv -f -- "${tmp_exit}" "${evidence_root}/wsl-child.exit-code.txt"
exit "${requested_exit_code}"
