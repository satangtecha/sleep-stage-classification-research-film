param(
    [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r11.ps1'),
    [string]$LockholderPath=(Join-Path $PSScriptRoot '..\hold_paper_text_multiseed_smoke_r11.ps1'),
    [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r11.sh'),
    [string]$RunnerPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r11.sh')
)

$ErrorActionPreference='Stop'
$dispatcher=Get-Content -LiteralPath $DispatcherPath -Raw
$lockholder=Get-Content -LiteralPath $LockholderPath -Raw
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
    "if(!(Test-Path -LiteralPath `$gatePath))",
    "if(!(Test-Path -LiteralPath `$confirmationPath))",
    "foreach(`$binding in @(`$gate.source_bindings))",
    "foreach(`$path in @(`$dispatchMarker",
    "A native WSL single-pilot or multi-seed process already exists",
    "`$gate.gpu_gate.windows_driver_version",
    "`$capabilityWrite=[IO.File]::Open(`$dispatchCapability",
    "try {`$dispatchStream=[IO.File]::Open(`$dispatchMarker",
    "'--property=Restart=no'",
    "systemd-run @arguments",
    "`$_.event -eq 'stable_locks_ready'"
) 'dispatcher trust/marker/dispatch ordering'

Assert-Ordered $lockholder @(
    "`$gateLock=Open-StableJsonLock",
    "`$confirmationLock=Open-StableJsonLock",
    "`$capabilityLock=Open-StableReadLock `$dispatchCapability",
    "r11 dispatch capability validation failed",
    "foreach(`$binding in @(`$gate.source_bindings))",
    "if(!(Test-Path -LiteralPath `$dispatchMarker))",
    "if(`$parent.Name -ne 'wslhost.exe')",
    "foreach(`$path in @(`$attemptMarker",
    "`$gate.gpu_gate.windows_driver_version",
    "r11 cache validator status failed",
    "A Windows single-pilot or multi-seed process already exists",
    "Get-StableAcPowerFacts",
    "try {`$attemptStream=[IO.File]::Open(`$attemptMarker",
    "event='stable_locks_ready'",
    "while(!(Test-Path -LiteralPath `$workloadExitEvidence)",
    "event='terminal_validated'"
) 'lockholder trust/marker/terminal ordering'

if($lockholder -match 'Start-Process|wsl\.exe'){throw 'Production lock holder must not launch or re-enter WSL'}
if($dispatcher -match '\.gpu_gate\.driver_version' -or $lockholder -match '\.gpu_gate\.driver_version'){throw 'Production scripts use the obsolete r11 GPU gate field'}
$restartValues=@([regex]::Matches($dispatcher,'--property=Restart=([^''"]+)')|ForEach-Object{$_.Groups[1].Value})
if($restartValues.Count -ne 1 -or $restartValues[0] -ne 'no'){throw 'Dispatcher does not bind exactly one Restart=no policy'}
if($supervisor -match '--resume|--retry'){throw 'Supervisor contains retry or resume arguments'}
if($runner -match '--resume|--retry'){throw 'Runner contains retry or resume arguments'}

Assert-Ordered $supervisor @(
    'hold_paper_text_multiseed_smoke_r11.ps1',
    'if [[ -f "$ready" ]]',
    './paper_faithful/training/run_paper_text_multiseed_smoke_r11.sh',
    'mv -f -- "$exit_temp" "$exit_evidence"',
    'terminal_(validated|validation_failed)',
    'wait "$lockholder_proxy_pid"'
) 'systemd supervisor lock/runner/terminal ordering'

foreach($required in @(
    '--run-id-prefix paper-text-v1-multiseed-cap128-r11-20260830',
    '--seeds 42 43',
    '--cap 128',
    '--stage3-gradient-clip-norm 1.0',
    '--stage3-stability-adaptation-id PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1'
)){
    if(!$runner.Contains($required)){throw "Runner protocol token absent: $required"}
}

$prefix='paper-text-v1-multiseed-cap128-r11-20260830'
$logRoot='E:\blp\sleep_stage_reproduction\runtime\training-logs'
$artifacts=@(
    "$prefix.dispatch.lock","$prefix.dispatch-capability.json","$prefix.launch.lock","$prefix.dispatch.lifecycle.jsonl",
    "$prefix.dispatch.json","$prefix.lifecycle.jsonl","$prefix.lockholder-ready.json",
    "$prefix.stdout.log","$prefix.stderr.log","$prefix.workload-exit-code.txt"
)|ForEach-Object{Join-Path $logRoot $_}
$present=@($artifacts|Where-Object{Test-Path -LiteralPath $_})
if($present.Count){throw "Production r11 artifacts appeared during static smoke: $($present -join ', ')"}

[ordered]@{
    status='pass'
    pilot_launched=$false
    gate_and_confirmation_precede_dispatch_marker=$true
    source_locks_and_collisions_precede_attempt_marker=$true
    restart_policy='no'
    lockholder_reenters_wsl=$false
    atomic_exit_precedes_terminal_barrier=$true
    exact_prefix_and_stage3_protocol_bound=$true
    production_artifacts_present=0
}|ConvertTo-Json -Compress
