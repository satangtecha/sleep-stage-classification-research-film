param(
    [string]$DispatcherPath = (Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r14.ps1'),
    [string]$SupervisorPath = (Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r14.ps1'),
    [string]$HelperPath = (Join-Path $PSScriptRoot '..\r14_exactly_once_helpers.ps1')
)

$ErrorActionPreference = 'Stop'
$dispatcher = Get-Content -LiteralPath (Resolve-Path -LiteralPath $DispatcherPath) -Raw
$supervisor = Get-Content -LiteralPath (Resolve-Path -LiteralPath $SupervisorPath) -Raw
. (Resolve-Path -LiteralPath $HelperPath).Path

Assert-R14GpuComputeProbeResult 0 @() 'test-idle'
$activeRefused = $false
try { Assert-R14GpuComputeProbeResult 0 @('4242') 'test-active' }
catch { $activeRefused = $_.Exception.Message -match 'GPU compute process collision' }
if (-not $activeRefused) { throw 'Active GPU compute PID was accepted' }
$probeFailureRefused = $false
try { Assert-R14GpuComputeProbeResult 17 @() 'test-probe-failure' }
catch { $probeFailureRefused = $_.Exception.Message -match 'GPU compute-process probe failed' }
if (-not $probeFailureRefused) { throw 'Failed GPU compute-process probe was accepted' }
$null = & wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "set -o pipefail; false | sed '/^[[:space:]]*$/d'" 2>$null
$wrapperFailureCode = [int]$LASTEXITCODE
if ($wrapperFailureCode -eq 0) { throw 'Bash wrapper masked the upstream GPU-probe failure' }
$global:LASTEXITCODE = 0
$helper = Get-Content -LiteralPath (Resolve-Path -LiteralPath $HelperPath) -Raw
if (-not $helper.Contains('set -o pipefail; nvidia-smi --query-compute-apps=pid')) { throw 'Live GPU probe is not protected by Bash pipefail' }

$dispatcherGpu = $dispatcher.IndexOf("Assert-R14GpuComputeIdle 'dispatcher-pre-dispatch'", [StringComparison]::Ordinal)
$dispatcherMarker = $dispatcher.IndexOf("Open-R14PermanentMarker `$dispatch 'dispatch'", [StringComparison]::Ordinal)
if ($dispatcherGpu -lt 0 -or $dispatcherMarker -le $dispatcherGpu) { throw 'Dispatcher GPU-idle check is not before dispatch-marker consumption' }
$supervisorAttempt = $supervisor.IndexOf("Assert-R14GpuComputeIdle 'supervisor-pre-attempt'", [StringComparison]::Ordinal)
$supervisorMarker = $supervisor.IndexOf("Open-R14PermanentMarker `$attemptMarker 'attempt'", [StringComparison]::Ordinal)
$supervisorWorkload = $supervisor.IndexOf("Assert-R14GpuComputeIdle 'supervisor-pre-workload';`$child=Start-Process", [StringComparison]::Ordinal)
if ($supervisorAttempt -lt 0 -or $supervisorMarker -le $supervisorAttempt -or $supervisorWorkload -le $supervisorMarker) { throw 'Supervisor GPU-idle checks are not bound before attempt and workload start' }

[ordered]@{
    status = 'pass'
    pilot_launched = $false
    idle_probe_accepted = $true
    active_compute_pid_refused = $true
    failed_probe_refused = $true
    wrapper_pipeline_failure_refused = $true
    live_probe_uses_pipefail = $true
    dispatcher_pre_dispatch_check = $true
    supervisor_pre_attempt_check = $true
    supervisor_immediate_pre_workload_check = $true
    production_namespace_touched = $false
} | ConvertTo-Json -Compress
