param(
 [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r15.ps1'),
 [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r15.ps1'),
 [string]$HelperPath=(Join-Path $PSScriptRoot '..\r15_exactly_once_helpers.ps1')
)
$ErrorActionPreference='Stop'
$dispatcher=Get-Content -LiteralPath (Resolve-Path -LiteralPath $DispatcherPath) -Raw;$supervisor=Get-Content -LiteralPath (Resolve-Path -LiteralPath $SupervisorPath) -Raw;. (Resolve-Path -LiteralPath $HelperPath).Path
Assert-R15GpuComputeProbeResult 0 @() 'idle'
$active=$false;try{Assert-R15GpuComputeProbeResult 0 @('4242') 'active'}catch{$active=$_.Exception.Message-match'GPU compute process collision'};if(!$active){throw 'active GPU PID accepted'}
$failed=$false;try{Assert-R15GpuComputeProbeResult 17 @() 'failed'}catch{$failed=$_.Exception.Message-match'GPU compute-process probe failed'};if(!$failed){throw 'failed GPU probe accepted'}
$gpuAt=$dispatcher.IndexOf("Assert-R15GpuComputeIdle 'dispatcher-pre-dispatch'",[StringComparison]::Ordinal);$markerAt=$dispatcher.IndexOf("Open-R15PermanentMarker `$dispatch 'dispatch'",[StringComparison]::Ordinal);if($gpuAt-lt0-or$markerAt-le$gpuAt){throw 'dispatcher GPU gate ordering failed'}
if($supervisor.Contains('Assert-R15GpuComputeIdle')){throw 'scheduler supervisor unexpectedly performs external GPU probe before attempt'}
$attemptAt=$supervisor.IndexOf('Open-R15PermanentMarker $attemptMarker',[StringComparison]::Ordinal);$wslAt=$supervisor.IndexOf('Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe"',[StringComparison]::Ordinal);if($attemptAt-lt0-or$wslAt-le$attemptAt){throw 'supervisor WSL workload is not after attempt marker'}
[ordered]@{status='pass';pilot_launched=$false;active_compute_pid_refused=$true;failed_probe_refused=$true;dispatcher_gpu_before_dispatch=$true;supervisor_external_gpu_preflight_absent=$true;wsl_only_after_attempt=$true}|ConvertTo-Json -Compress
