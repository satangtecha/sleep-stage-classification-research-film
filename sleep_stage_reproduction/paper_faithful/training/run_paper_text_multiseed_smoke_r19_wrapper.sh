#!/usr/bin/env bash
# Source-bound bootstrap-diagnostic foreground wrapper for r19.
set -u

if [[ $# -ne 4 ]]; then
  echo 'r19 foreground wrapper requires runner, stdout, stderr, and exit-evidence paths' >&2
  exit 74
fi

runner=$1
stdout_path=$2
stderr_path=$3
exit_path=$4
stage=argument_validation

if [[ "${PAPER_FAITHFUL_R19_CAPABILITY_TOKEN_FROM_STDIN:-}" == "1" ]]; then
  IFS= read -r capability_token || true
  capability_token=${capability_token%$'\r'}
  capability_token=${capability_token#$'\ufeff'}
  case "$capability_token" in
    ''|*[!0-9a-f]*) echo 'r19 capability token received from stdin is invalid' >&2; exit 78 ;;
  esac
  if [[ ${#capability_token} -ne 64 ]]; then
    echo 'r19 capability token received from stdin has invalid length' >&2
    exit 78
  fi
  export PAPER_FAITHFUL_R19_SUPERVISOR_CAPABILITY_TOKEN="$capability_token"
fi

write_terminal_sidecar() {
  rc=$?
  trap - EXIT
  tmp="${exit_path}.tmp.$$"
  if ! printf '{"schema_version":1,"exit_code":%s,"stage":"%s"}\n' "$rc" "$stage" >"$tmp"; then
    echo "r19 could not write atomic sidecar temp at stage=$stage rc=$rc" >&2
    exit "$rc"
  fi
  if ! mv -f -- "$tmp" "$exit_path"; then
    echo "r19 could not publish atomic sidecar at stage=$stage rc=$rc" >&2
    exit "$rc"
  fi
  exit "$rc"
}
trap write_terminal_sidecar EXIT

case "$runner|$stdout_path|$stderr_path|$exit_path" in
  *[[:space:]\"\']*) echo 'r19 foreground wrapper arguments contain unsafe whitespace or quotes' >&2; exit 75 ;;
esac

stage=cwd
cd '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction' || exit 73

stage=stdout_open
: >"$stdout_path" || exit 76
stage=stderr_open
: >"$stderr_path" || exit 77

set +e
stage=runner
bash "$runner" >>"$stdout_path" 2>>"$stderr_path"
rc=$?
stage=runner_complete
exit "$rc"
