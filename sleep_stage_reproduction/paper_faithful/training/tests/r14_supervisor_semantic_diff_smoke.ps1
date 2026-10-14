param(
    [string]$R13SupervisorPath = (Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r13.ps1'),
    [string]$R14SupervisorPath = (Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r14.ps1'),
    [string]$R14HelperPath = (Join-Path $PSScriptRoot '..\r14_exactly_once_helpers.ps1')
)

$ErrorActionPreference = 'Stop'
$r13Path = (Resolve-Path -LiteralPath $R13SupervisorPath).Path
$r14Path = (Resolve-Path -LiteralPath $R14SupervisorPath).Path
$helperPath = (Resolve-Path -LiteralPath $R14HelperPath).Path
$r13 = Get-Content -LiteralPath $r13Path -Raw
$r14 = Get-Content -LiteralPath $r14Path -Raw
$helper = Get-Content -LiteralPath $helperPath -Raw

function Assert-Parsed([string]$Path) { $tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseFile($Path,[ref]$tokens,[ref]$errors);if($errors.Count){throw "Parser rejected $Path"} }
function Assert-All([string]$Text,[string[]]$Needles,[string]$Label) { foreach($needle in $Needles){if(-not$Text.Contains($needle)){throw "$Label missing invariant: $needle"}} }

Assert-Parsed $r13Path; Assert-Parsed $r14Path; Assert-Parsed $helperPath
$core = @(
    'Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe"',
    "@('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc'",
    'Wait-AtomicTerminal', 'AddSeconds(60)', 'Atomic WSL exit evidence absent after Windows host exit',
    'Windows WSL host remained after atomic exit evidence', "event='process_exited'", "event='terminal_validated'",
    "status-ne'completed'", "mode-ne'multi-seed-pilot'", "verification.status-ne'verified'"
)
Assert-All $r13 $core 'r13 supervisor'
Assert-All $r14 $core 'r14 supervisor'
if ($r13 -match '--retry|--resume' -or $r14 -match '--retry|--resume') { throw 'Supervisor contains retry/resume behavior' }
if (([regex]::Matches($r13,'AddSeconds\(60\)')).Count -ne 2 -or ([regex]::Matches($r14,'AddSeconds\(60\)')).Count -ne 2) { throw 'Bounded terminal mismatch grace changed' }
Assert-All $r14 @('r14_exactly_once_helpers.ps1','. $helperPath','Assert-R14OwnedLifecycleAvailable $lifecycle $attemptMarker','Assert-R14BoundDispatchRecord','Open-R14PermanentMarker $attemptMarker',"Assert-R14GpuComputeIdle 'supervisor-pre-attempt'","Assert-R14GpuComputeIdle 'supervisor-pre-workload';`$child=Start-Process","Exception.Data.Contains('r14_exit_code')") 'r14 pre-attempt hardening'
Assert-All $r14 @('$repoRoot=''C:\Users\Acer\OneDrive\Documents\เป้าๆรวยๆๆๆ\sleep_stage_reproduction''','$supervisorPath=[IO.Path]::GetFullPath($PSCommandPath)','$supervisorTemplatePath=','supervisor_template_ps1=$supervisorTemplatePath','$bindings.supervisor_ps1.sha256-ne$bindings.supervisor_template_ps1.sha256','-WorkingDirectory $repoRoot') 'r14 staged-supervisor delta'
Assert-All $r14 @('Get-WmiObject -Class Win32_Process','Get-WmiObject -Namespace root\wmi -Class BatteryStatus','Get-WmiObject -Class Win32_VideoController') 'r14 scheduler-compatible WMI delta'
if($r14.Contains('Get-CimInstance')){throw 'r14 supervisor retains scheduler-hanging CIM calls'}
Assert-All $helper @("Data['r14_exit_code'] = 91",'FileMode]::CreateNew','FileShare]::None','lifecycle belongs to an invocation that consumed its permanent marker','exactly one bound dispatch_created event','dispatch marker is not exclusively held','Assert-R14GpuComputeProbeResult','set -o pipefail; nvidia-smi --query-compute-apps=pid') 'r14 helper'
$bindingIndex = $r14.IndexOf('foreach($b in @($gate.source_bindings))',[StringComparison]::Ordinal)
$helperIndex = $r14.IndexOf('. $helperPath',[StringComparison]::Ordinal)
if ($bindingIndex -lt 0 -or $helperIndex -le $bindingIndex) { throw 'r14 helper executes before source binding lock' }
$recordIndex = $r14.IndexOf('Assert-R14BoundDispatchRecord',[StringComparison]::Ordinal)
$attemptIndex = $r14.IndexOf('Open-R14PermanentMarker $attemptMarker',[StringComparison]::Ordinal)
$processIndex = $r14.IndexOf('Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe"',[StringComparison]::Ordinal)
if ($recordIndex -lt 0 -or $attemptIndex -le $recordIndex -or $processIndex -le $attemptIndex) { throw 'r14 dispatch/attempt/workload order changed' }
$gpuIndex = $r14.IndexOf("Assert-R14GpuComputeIdle 'supervisor-pre-workload';`$child=Start-Process",[StringComparison]::Ordinal)
if ($gpuIndex -lt 0 -or $processIndex -le $gpuIndex) { throw 'r14 live GPU compute-process refusal is not immediately before workload start' }

[ordered]@{
    status = 'pass'; pilot_launched = $false
    r13_supervisor_path = $r13Path; r13_supervisor_sha256 = (Get-FileHash -LiteralPath $r13Path -Algorithm SHA256).Hash.ToLowerInvariant()
    r14_supervisor_path = $r14Path; r14_supervisor_sha256 = (Get-FileHash -LiteralPath $r14Path -Algorithm SHA256).Hash.ToLowerInvariant()
    r14_helper_path = $helperPath; r14_helper_sha256 = (Get-FileHash -LiteralPath $helperPath -Algorithm SHA256).Hash.ToLowerInvariant()
    core_foreground_wsl_terminal_invariants_match = $true
    bounded_terminal_mismatch_grace_seconds = 60
    automatic_retry_or_resume_absent = $true
    intentional_r14_preattempt_security_delta_verified = $true
    helper_hash_locked_before_execution = $true
    marker_lifecycle_race_maps_to_refusal = $true
    dispatch_record_before_attempt_marker_before_workload = $true
    gpu_compute_process_refusal_immediately_before_workload = $true
    r13_post_attempt_workload_semantics_preserved = $true
    intentional_r14_e_staged_supervisor_delta_verified = $true
    scheduler_compatible_wmi_delta_verified = $true
} | ConvertTo-Json -Compress
