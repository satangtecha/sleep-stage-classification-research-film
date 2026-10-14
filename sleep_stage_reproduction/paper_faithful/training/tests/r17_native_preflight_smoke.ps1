param(
    [string]$HelperPath = (Join-Path $PSScriptRoot '..\r17_exactly_once_helpers.ps1'),
    [string]$SupervisorPath = (Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r17.ps1')
)
$ErrorActionPreference = 'Stop'
$helper = (Resolve-Path -LiteralPath $HelperPath).Path
$supervisor = (Resolve-Path -LiteralPath $SupervisorPath).Path
. $helper
$parentPid = Get-R17NativeParentProcessId
if ($parentPid -le 0 -or -not (Get-Process -Id $parentPid -ErrorAction SilentlyContinue)) { throw 'Native parent PID probe failed' }
$power = Get-R17NativePowerStatus
if ($power.unknown -or -not $power.power_online -or $power.critical -or $power.battery_percent -lt 5) { throw 'Native power probe failed' }
$cFree = Get-R17NativeDriveFreeGiB 'C:\'
$eFree = Get-R17NativeDriveFreeGiB 'E:\'
if ($cFree -le 0 -or $eFree -le 0) { throw 'Native storage probe failed' }
$gateSha = 'a' * 64
$confirmationSha = 'b' * 64
$caseId = '1' * 32
$productionTask = "SleepStagePaper-r17-COM-$caseId"
$canaryTask = "SleepStagePaper-r17-Canary-$caseId"
$canaryRoot = "E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r17-supervisor-canaries\$caseId"
$productionArgs = New-R17SupervisorActionArguments $supervisor $gateSha $confirmationSha $productionTask
$canaryArgs = New-R17SupervisorActionArguments $supervisor $gateSha $confirmationSha $canaryTask $canaryRoot
Assert-R17SupervisorActionArguments $productionArgs $supervisor $gateSha $confirmationSha $productionTask | Out-Null
Assert-R17SupervisorActionArguments $canaryArgs $supervisor $gateSha $confirmationSha $canaryTask $canaryRoot | Out-Null
if ($productionArgs -match 'CanaryRoot' -or $canaryArgs -notmatch 'CanaryRoot') { throw 'Production/canary action separation failed' }
$badRootRefused = $false
try { New-R17SupervisorActionArguments $supervisor $gateSha $confirmationSha $canaryTask 'E:\wrong' | Out-Null } catch { $badRootRefused = $true }
if (-not $badRootRefused) { throw 'Out-of-namespace CanaryRoot was accepted' }
$productionRootRefused = $false
try { New-R17SupervisorActionArguments $supervisor $gateSha $confirmationSha $productionTask $canaryRoot | Out-Null } catch { $productionRootRefused = $true }
if (-not $productionRootRefused) { throw 'Production action accepted CanaryRoot' }
[ordered]@{
    status='pass';pilot_launched=$false;native_parent_pid=$parentPid;native_power_online=$power.power_online
    native_battery_percent=$power.battery_percent;production_action_has_no_canary_root=$true
    native_c_free_gib=[Math]::Round($cFree,3);native_e_free_gib=[Math]::Round($eFree,3)
    canary_action_binds_exact_root=$true;bad_canary_root_refused=$true;production_canary_root_refused=$true
}|ConvertTo-Json -Compress
