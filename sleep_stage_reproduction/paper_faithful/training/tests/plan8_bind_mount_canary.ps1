$ErrorActionPreference = 'Stop'

$target = 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\plan8-bind-mount-canary-v2-20261005'
$targetWsl = '/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/plan8-bind-mount-canary-v2-20261005'
$evidencePath = 'E:\blp\sleep_stage_reproduction\runtime\reviews\plan8-bind-mount-canary-v2-20261005.json'

New-Item -ItemType Directory -Force -Path $target | Out-Null
$bash = @'
set -u
target='/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/plan8-bind-mount-canary-v2-20261005'
source=$(mktemp -d /tmp/plan8-bind-source-XXXXXX)
mounted=0
cleanup() {
  if [ "$mounted" -eq 1 ]; then
    umount "$target" >/dev/null 2>&1 || true
  fi
  rmdir "$source" >/dev/null 2>&1 || true
}
trap cleanup EXIT
mount --bind "$source" "$target"
mounted=1
findmnt -T "$target" -o TARGET,SOURCE,FSTYPE,OPTIONS
source_device=$(stat -c '%d' "$source")
target_device=$(stat -c '%d' "$target")
test "$source_device" = "$target_device"
mountpoint -q "$target"
echo "CANARY_BIND_MOUNT_PASS source_device=$source_device target_device=$target_device"
'@

$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
$result = & wsl.exe -d Ubuntu -u root -- bash -lc "printf %s $payload | base64 -d | bash" 2>&1
$exitCode = $LASTEXITCODE
$output = ($result | Out-String).Trim()
$status = if ($exitCode -eq 0 -and $output -match 'CANARY_BIND_MOUNT_PASS') { 'pass' } else { 'fail' }
$targetExistsBeforeCleanup = Test-Path -LiteralPath $target
if ($targetExistsBeforeCleanup) {
  Remove-Item -LiteralPath $target -Force
}

$evidence = [ordered]@{
  schema = 'PLAN8_BIND_MOUNT_CANARY_V1'
  created_at = (Get-Date).ToUniversalTime().ToString('o')
  target = $target
  target_wsl = $targetWsl
  wsl_distribution = 'Ubuntu'
  wsl_user = 'root'
  status = $status
  exit_code = $exitCode
  output = $output
  original_cache_untouched = $true
  target_exists_before_cleanup = $targetExistsBeforeCleanup
  target_removed_after_test = -not (Test-Path -LiteralPath $target)
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $evidencePath) | Out-Null
$evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $evidencePath -Encoding utf8
if ($status -ne 'pass') {
  throw "Bind mount canary failed. Evidence: $evidencePath`n$output"
}
Write-Output $output
Write-Output "Evidence: $evidencePath"
