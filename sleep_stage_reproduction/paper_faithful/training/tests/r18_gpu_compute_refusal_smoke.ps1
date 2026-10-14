param(
 [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r18.ps1'),
 [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r18.ps1'),
 [string]$HelperPath=(Join-Path $PSScriptRoot '..\r18_exactly_once_helpers.ps1')
)
$ErrorActionPreference='Stop'
$dispatcher=Get-Content -LiteralPath (Resolve-Path -LiteralPath $DispatcherPath) -Raw;$supervisor=Get-Content -LiteralPath (Resolve-Path -LiteralPath $SupervisorPath) -Raw;. (Resolve-Path -LiteralPath $HelperPath).Path
Assert-R17GpuComputeProbeResult 0 @() 'idle'
$active=$false;try{Assert-R17GpuComputeProbeResult 0 @('4242') 'active'}catch{$active=$_.Exception.Message-match'GPU compute process collision'};if(!$active){throw 'active GPU PID accepted'}
$failed=$false;try{Assert-R17GpuComputeProbeResult 17 @() 'failed'}catch{$failed=$_.Exception.Message-match'GPU compute-process probe failed'};if(!$failed){throw 'failed GPU probe accepted'}
$gpuAt=$dispatcher.IndexOf("Assert-R17GpuComputeIdle 'dispatcher-pre-dispatch'",[StringComparison]::Ordinal);$markerAt=$dispatcher.IndexOf("Open-R17PermanentMarker `$dispatch 'dispatch'",[StringComparison]::Ordinal);if($gpuAt-lt0-or$markerAt-le$gpuAt){throw 'dispatcher GPU gate ordering failed'}
$attemptAt=$supervisor.IndexOf('Open-R17PermanentMarker $attemptMarker',[StringComparison]::Ordinal);$recheckAt=$supervisor.IndexOf("Assert-R17GpuComputeIdle 'supervisor-post-attempt-pre-workload'",[StringComparison]::Ordinal);$wslAt=$supervisor.IndexOf('$child=Start-R17WslForeground',[StringComparison]::Ordinal);if($attemptAt-lt0-or$recheckAt-le$attemptAt-or$wslAt-le$recheckAt){throw 'supervisor post-attempt GPU recheck ordering failed'}
$workloadStarted=$false;$handoffRefused=$false;try{Assert-R17GpuComputeProbeResult 0 @('4242') 'supervisor-post-attempt-pre-workload';$workloadStarted=$true}catch{$handoffRefused=$_.Exception.Message-match'GPU compute process collision'};if(!$handoffRefused-or$workloadStarted){throw 'GPU activity introduced after dispatcher preflight did not block workload handoff'}
[ordered]@{status='pass';pilot_launched=$false;active_compute_pid_refused=$true;failed_probe_refused=$true;dispatcher_gpu_before_dispatch=$true;supervisor_gpu_recheck_after_attempt=$true;supervisor_gpu_recheck_before_workload=$true;synthetic_post_dispatch_gpu_activity_refused=$true;workload_started=$false;wsl_only_after_attempt=$true}|ConvertTo-Json -Compress
