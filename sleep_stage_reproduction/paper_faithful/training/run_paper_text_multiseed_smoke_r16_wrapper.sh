#!/usr/bin/env bash
# Source-bound foreground wrapper for r16. All arguments must be absolute WSL paths.
set -u
if [[ $# -ne 4 ]]; then
  echo 'r16 foreground wrapper requires runner, stdout, stderr, and exit-evidence paths' >&2
  exit 74
fi
runner=$1
stdout_path=$2
stderr_path=$3
exit_path=$4
case "$runner|$stdout_path|$stderr_path|$exit_path" in
  *[[:space:]\"\']*) echo 'r16 foreground wrapper arguments contain unsafe whitespace or quotes' >&2; exit 75 ;;
esac
cd '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction' || exit 73
set +e
bash "$runner" >"$stdout_path" 2>"$stderr_path"
rc=$?
tmp="${exit_path}.tmp.$$"
printf '%s\n' "$rc" >"$tmp"
mv -f -- "$tmp" "$exit_path"
exit "$rc"
