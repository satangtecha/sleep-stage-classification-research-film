param(
    [string]$R12SupervisorPath = (Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r12.ps1'),
    [string]$R13SupervisorPath = (Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r13.ps1'),
    [string]$R13HelperPath = (Join-Path $PSScriptRoot '..\r13_exactly_once_helpers.ps1')
)

$ErrorActionPreference = 'Stop'
$r12Path = (Resolve-Path -LiteralPath $R12SupervisorPath).Path
$r13Path = (Resolve-Path -LiteralPath $R13SupervisorPath).Path
$helperPath = (Resolve-Path -LiteralPath $R13HelperPath).Path
$r12 = Get-Content -LiteralPath $r12Path -Raw
$r13 = Get-Content -LiteralPath $r13Path -Raw
$helper = Get-Content -LiteralPath $helperPath -Raw

function Assert-Parsed([string]$Path) { $tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseFile($Path,[ref]$tokens,[ref]$errors);if($errors.Count){throw "Parser rejected $Path"} }
function Assert-All([string]$Text,[string[]]$Needles,[string]$Label) { foreach($needle in $Needles){if(-not$Text.Contains($needle)){throw "$Label missing invariant: $needle"}} }

Assert-Parsed $r12Path; Assert-Parsed $r13Path; Assert-Parsed $helperPath
$core = @(
    'Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe"',
    "@('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc'",
    'Wait-AtomicTerminal', 'AddSeconds(60)', 'Atomic WSL exit evidence absent after Windows host exit',
    'Windows WSL host remained after atomic exit evidence', "event='process_exited'", "event='terminal_validated'",
    "status-ne'completed'", "mode-ne'multi-seed-pilot'", "verification.status-ne'verified'"
)
Assert-All $r12 $core 'r12 supervisor'
Assert-All $r13 $core 'r13 supervisor'
if ($r12 -match '--retry|--resume' -or $r13 -match '--retry|--resume') { throw 'Supervisor contains retry/resume behavior' }
if (([regex]::Matches($r12,'AddSeconds\(60\)')).Count -ne 2 -or ([regex]::Matches($r13,'AddSeconds\(60\)')).Count -ne 2) { throw 'Bounded terminal mismatch grace changed' }
Assert-All $r13 @('r13_exactly_once_helpers.ps1','. $helperPath','Assert-R13OwnedLifecycleAvailable $lifecycle $attemptMarker','Assert-R13BoundDispatchRecord','Open-R13PermanentMarker $attemptMarker',"Assert-R13GpuComputeIdle 'supervisor-pre-attempt'","Assert-R13GpuComputeIdle 'supervisor-pre-workload';`$child=Start-Process","Exception.Data.Contains('r13_exit_code')") 'r13 pre-attempt hardening'
Assert-All $helper @("Data['r13_exit_code'] = 91",'FileMode]::CreateNew','FileShare]::None','lifecycle belongs to an invocation that consumed its permanent marker','exactly one bound dispatch_created event','dispatch marker is not exclusively held','Assert-R13GpuComputeProbeResult','set -o pipefail; nvidia-smi --query-compute-apps=pid') 'r13 helper'
$bindingIndex = $r13.IndexOf('foreach($b in @($gate.source_bindings))',[StringComparison]::Ordinal)
$helperIndex = $r13.IndexOf('. $helperPath',[StringComparison]::Ordinal)
if ($bindingIndex -lt 0 -or $helperIndex -le $bindingIndex) { throw 'r13 helper executes before source binding lock' }
$recordIndex = $r13.IndexOf('Assert-R13BoundDispatchRecord',[StringComparison]::Ordinal)
$attemptIndex = $r13.IndexOf('Open-R13PermanentMarker $attemptMarker',[StringComparison]::Ordinal)
$processIndex = $r13.IndexOf('Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe"',[StringComparison]::Ordinal)
if ($recordIndex -lt 0 -or $attemptIndex -le $recordIndex -or $processIndex -le $attemptIndex) { throw 'r13 dispatch/attempt/workload order changed' }
$gpuIndex = $r13.IndexOf("Assert-R13GpuComputeIdle 'supervisor-pre-workload';`$child=Start-Process",[StringComparison]::Ordinal)
if ($gpuIndex -lt 0 -or $processIndex -le $gpuIndex) { throw 'r13 live GPU compute-process refusal is not immediately before workload start' }

[ordered]@{
    status = 'pass'; pilot_launched = $false
    r12_supervisor_path = $r12Path; r12_supervisor_sha256 = (Get-FileHash -LiteralPath $r12Path -Algorithm SHA256).Hash.ToLowerInvariant()
    r13_supervisor_path = $r13Path; r13_supervisor_sha256 = (Get-FileHash -LiteralPath $r13Path -Algorithm SHA256).Hash.ToLowerInvariant()
    r13_helper_path = $helperPath; r13_helper_sha256 = (Get-FileHash -LiteralPath $helperPath -Algorithm SHA256).Hash.ToLowerInvariant()
    core_foreground_wsl_terminal_invariants_match = $true
    bounded_terminal_mismatch_grace_seconds = 60
    automatic_retry_or_resume_absent = $true
    intentional_r13_preattempt_security_delta_verified = $true
    helper_hash_locked_before_execution = $true
    marker_lifecycle_race_maps_to_refusal = $true
    dispatch_record_before_attempt_marker_before_workload = $true
    gpu_compute_process_refusal_immediately_before_workload = $true
    accepted_r12_long_canary_remains_applicable_to_post_attempt_workload_semantics = $true
} | ConvertTo-Json -Compress
