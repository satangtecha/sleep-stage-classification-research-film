param(
    [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r12.ps1'),
    [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r12.ps1'),
    [string]$RunnerPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r12.sh')
)

$ErrorActionPreference='Stop'
$dispatcher=Get-Content -LiteralPath $DispatcherPath -Raw
$supervisor=Get-Content -LiteralPath $SupervisorPath -Raw
$runner=Get-Content -LiteralPath $RunnerPath -Raw

function Assert-Ordered([string]$Text,[string[]]$Needles,[string]$Label) {
    $position=-1
    foreach($needle in $Needles){
        $next=$Text.IndexOf($needle,$position+1,[StringComparison]::Ordinal)
        if($next -lt 0){throw "$Label is missing ordered token: $needle"}
        $position=$next
    }
}

Assert-Ordered $dispatcher @(
    '$g=Lock $gatePath;$c=Lock $confirmationPath',
    '$confirm.user_message_sha256-ne(Get-Sha $excerptBytes)',
    '$confirmationBindings.Count-ne$bindings.Count',
    '$svc=New-Object -ComObject ''Schedule.Service'';$svc.Connect()',
    'Power-OK;$gpu=Get-CimInstance Win32_VideoController',
    '$marker=[IO.File]::Open($dispatch,[IO.FileMode]::CreateNew',
    '$def.Settings.MultipleInstances=2',
    '$def.Settings.RestartCount=0',
    '$def.Settings.ExecutionTimeLimit=''PT0S''',
    '$task=$folder.RegisterTaskDefinition',
    '$running=$task.RunEx',
    '$handshake=Wait-SupervisorHandshake',
    "event='supervisor_handshake_validated'"
) 'dispatcher trust/pre-marker/COM/handshake ordering'

Assert-Ordered $supervisor @(
    '$gateLock=Open-Stable $gatePath;$confirmationLock=Open-Stable $confirmationPath',
    '$confirmation.user_message_sha256-ne(Get-Sha $excerptBytes)',
    '$confirmationBindings.Count-ne$bindings.Count',
    '$self=Get-CimInstance Win32_Process -Filter "ProcessId=$PID"',
    'Assert-Power;$gpu=Assert-Gpu $gate',
    '$attemptStream=[IO.File]::Open($attemptMarker,[IO.FileMode]::CreateNew',
    "event='supervisor_started'",
    '$child=Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe"',
    '$terminalBarrier=Wait-AtomicTerminal $child',
    '$atomic=Read-Exit',
    "event='process_exited'",
    "event='terminal_validated'"
) 'supervisor trust/pre-marker/foreground/terminal ordering'

foreach($required in @(
    '--run-id-prefix "$prefix"',
    '--seeds 42 43',
    '--cap 128',
    '--stage3-gradient-clip-norm 1.0',
    '--stage3-stability-adaptation-id PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1'
)){
    if(!$runner.Contains($required)){throw "Runner protocol token absent: $required"}
}

if(([regex]::Matches($runner,'paper_faithful\.training\.cli multi-seed-pilot')).Count -ne 1){throw 'Runner must invoke multi-seed-pilot exactly once'}
if($runner -match '--resume|--retry' -or $supervisor -match '--resume|--retry' -or $dispatcher -match '--resume|--retry'){throw 'Production sources contain retry or resume arguments'}
if($runner -match "cache_root|data\['files'\]|read_bytes\(\)"){throw 'Runner contains the rejected non-canonical cache pre-scan'}
if(!$dispatcher.Contains('$def.Settings.MultipleInstances=2') -or !$dispatcher.Contains('$def.Settings.RestartCount=0') -or !$dispatcher.Contains("`$def.Settings.ExecutionTimeLimit='PT0S'")){throw 'Task policy is not triggerless IgnoreNew/no-restart/no-limit'}
if($dispatcher -match '\$def\.Triggers\.Create'){throw 'Production Task Scheduler definition unexpectedly creates a trigger'}
if(!$supervisor.Contains("DeleteTask(`$TaskName,0)")){throw 'Supervisor does not remove the ephemeral Scheduler task'}

$prefix='paper-text-v1-multiseed-cap128-r12-20260830'
$bulkRoot='E:\blp\sleep_stage_reproduction'
$logRoot=Join-Path $bulkRoot 'runtime\training-logs'
$children=@("$prefix-split42-model42","$prefix-split43-model43")
$paths=@(
    (Join-Path $bulkRoot 'runtime\driver-recovery\r12-explicit-user-launch-confirmation-20260830.json'),
    (Join-Path $logRoot "$prefix.dispatch.lock"),(Join-Path $logRoot "$prefix.launch.lock"),
    (Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.dispatch.json"),
    (Join-Path $logRoot "$prefix.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.stdout.log"),
    (Join-Path $logRoot "$prefix.stderr.log"),(Join-Path $logRoot "$prefix.workload-exit-code.txt")
)+($children|ForEach-Object{Join-Path (Join-Path $bulkRoot 'runs') $_})
$present=@($paths|Where-Object{Test-Path -LiteralPath $_})
if($present.Count){throw "Production r12 artifacts appeared during static smoke: $($present -join ', ')"}

$scheduler=New-Object -ComObject 'Schedule.Service';$scheduler.Connect()
$tasks=@($scheduler.GetFolder('\').GetTasks(1)|Where-Object{$_.Name -match '^SleepStagePaper-r12-COM-'})
if($tasks.Count){throw "Production r12 Scheduler task namespace is not empty: $($tasks.Name -join ', ')"}

[ordered]@{
    status='pass'
    pilot_launched=$false
    gate_confirmation_and_full_source_closure_precede_dispatch_marker=$true
    task_scheduler_com_connected_before_dispatch_marker=$true
    supervisor_parent_power_gpu_storage_and_process_gates_precede_attempt_marker=$true
    task_scheduler_parent_required='svchost.exe'
    multiple_instances='IgnoreNew'
    restart_count=0
    execution_time_limit='PT0S'
    trigger_count=0
    foreground_wsl_and_atomic_exit_required=$true
    bound_handshake_required=$true
    single_strict_canonical_cache_load=$true
    exact_prefix_and_stage3_protocol_bound=$true
    production_artifacts_present=0
}|ConvertTo-Json -Compress
