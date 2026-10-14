param(
    [string]$LocalPath = (Join-Path $PSScriptRoot '..\r13_preflighted_taskdef_launch_test_evidence_20260830_v5.json'),
    [string]$CanonicalPath = 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r13-preflighted-taskdef-launch-test-evidence-20260830-v5.json',
    [ValidatePattern('^[0-9a-f]{32}$')][string]$RegistrationCanaryCaseId = '09fbf45bfb594b12bbed7fc946ec273a'
)

$ErrorActionPreference = 'Stop'
$prefix = 'paper-text-v1-multiseed-cap128-r13-20260830'
$children = @("$prefix-split42-model42", "$prefix-split43-model43")
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$trainingRoot = Join-Path $projectRoot 'paper_faithful\training'
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$runtimeRoot = Join-Path $bulkRoot 'runtime'
$logRoot = Join-Path $runtimeRoot 'training-logs'
$driverRecoveryRoot = Join-Path $runtimeRoot 'driver-recovery'
$ps51 = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$lockedPython = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
$wslProjectRoot = '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction'

function Get-Sha256([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-External([string]$FilePath, [string[]]$Arguments) {
    $priorErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = @(& $FilePath @Arguments 2>&1 | ForEach-Object { [string]$_ })
        $exitCode = [int]$LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $priorErrorActionPreference
    }
    [pscustomobject]@{
        exit_code = $exitCode
        output = ($output -join [Environment]::NewLine)
    }
}

function Read-SingleJson([string]$Text, [string]$Label) {
    try { $Text.Trim() | ConvertFrom-Json -ErrorAction Stop }
    catch { throw "$Label did not emit one valid JSON document: $($_.Exception.Message)" }
}

function Assert-NoProductionNamespace {
    $paths = @(
        (Join-Path $driverRecoveryRoot 'canonical-r13-multiseed-launch-gate-20260830.json'),
        (Join-Path $driverRecoveryRoot 'r13-explicit-user-launch-confirmation-20260830.json'),
        (Join-Path $logRoot "$prefix.dispatch.lock"),
        (Join-Path $logRoot "$prefix.launch.lock"),
        (Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"),
        (Join-Path $logRoot "$prefix.dispatch.json"),
        (Join-Path $logRoot "$prefix.lifecycle.jsonl"),
        (Join-Path $logRoot "$prefix.stdout.log"),
        (Join-Path $logRoot "$prefix.stderr.log"),
        (Join-Path $logRoot "$prefix.workload-exit-code.txt"),
        (Join-Path (Join-Path $bulkRoot 'runs') $children[0]),
        (Join-Path (Join-Path $bulkRoot 'runs') $children[1])
    )
    $present = @($paths | Where-Object { Test-Path -LiteralPath $_ })
    if ($present.Count) { throw "r13 production path exists: $($present -join ', ')" }

    $service = New-Object -ComObject 'Schedule.Service'
    $service.Connect()
    $productionTasks = @($service.GetFolder('\').GetTasks(1) | Where-Object { $_.Name -match '^SleepStagePaper-r13-COM-' })
    $canaryTasks = @($service.GetFolder('\').GetTasks(1) | Where-Object { $_.Name -match '^SleepStagePaper-R13-TaskDef-Canary-' })
    if ($productionTasks.Count -or $canaryTasks.Count) { throw 'r13 Task Scheduler namespace is not empty' }

    $windowsTraining = @(Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -match 'paper_faithful\.training\.cli (pilot|multi-seed-pilot)'
    })
    if ($windowsTraining.Count) { throw 'Windows training process is present' }
    $wslTraining = Invoke-External 'wsl.exe' @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',"pgrep -af '[p]aper_faithful.training.cli (pilot|multi-seed-pilot)' || true")
    if ($wslTraining.exit_code -ne 0 -or -not [string]::IsNullOrWhiteSpace($wslTraining.output)) { throw 'WSL training process is present or probe failed' }
}

if (Test-Path -LiteralPath $LocalPath) { throw "Local immutable evidence already exists: $LocalPath" }
if (Test-Path -LiteralPath $CanonicalPath) { throw "Canonical immutable evidence already exists: $CanonicalPath" }
Assert-NoProductionNamespace

$staticRun = Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'r13_static_fail_closed_smoke.ps1'))
$preflightRun = Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'r13_task_scheduler_com_preflight_smoke.ps1'))
$refusalRun = Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'r13_exactly_once_refusal_smoke.ps1'))
$gpuRefusalRun = Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'r13_gpu_compute_refusal_smoke.ps1'))
$semanticDiffRun = Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'r13_supervisor_semantic_diff_smoke.ps1'))
foreach ($run in @($staticRun, $preflightRun, $refusalRun, $gpuRefusalRun, $semanticDiffRun)) { if ($run.exit_code -ne 0) { throw "Focused r13 test failed: $($run.output)" } }
$static = Read-SingleJson $staticRun.output 'r13 static test'
$preflight = Read-SingleJson $preflightRun.output 'r13 TaskDefinition preflight'
$refusal = Read-SingleJson $refusalRun.output 'r13 exactly-once refusal test'
$gpuRefusal = Read-SingleJson $gpuRefusalRun.output 'r13 GPU compute-process refusal test'
$semanticDiff = Read-SingleJson $semanticDiffRun.output 'r12-to-r13 supervisor semantic diff test'
if ($static.status -ne 'pass' -or $preflight.status -ne 'pass' -or $refusal.status -ne 'pass' -or $gpuRefusal.status -ne 'pass' -or $semanticDiff.status -ne 'pass') { throw 'Focused r13 JSON status is not pass' }

$caseId = $RegistrationCanaryCaseId
$canaryRoot = Join-Path (Join-Path $driverRecoveryRoot 'r13-taskdef-registration-canaries') $caseId
$canaryResultPath = Join-Path $canaryRoot 'result.json'
$canaryXmlPath = Join-Path $canaryRoot 'task-definition.xml'
$canarySentinelPath = Join-Path $canaryRoot 'completed.txt'
foreach ($path in @($canaryResultPath, $canaryXmlPath, $canarySentinelPath)) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Canary artifact absent: $path" } }
$registration = Get-Content -LiteralPath $canaryResultPath -Raw | ConvertFrom-Json -ErrorAction Stop
if ($registration.status -ne 'pass' -or $registration.task_name -ne "SleepStagePaper-R13-TaskDef-Canary-$caseId" -or $registration.task_registered -ne $true -or $registration.task_runex_requested -ne $true) { throw 'Selected persisted registration canary is invalid' }

$hostUnit = Invoke-External 'python' @('-m','unittest','paper_faithful.training.tests.test_multi_seed')
$wslUnitCommand = "cd '$wslProjectRoot' && PYTHONDONTWRITEBYTECODE=1 $lockedPython -m unittest paper_faithful.training.tests.test_multi_seed"
$wslUnit = Invoke-External 'wsl.exe' @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',$wslUnitCommand)
foreach ($unit in @($hostUnit, $wslUnit)) {
    if ($unit.exit_code -ne 0 -or $unit.output -notmatch 'Ran 10 tests' -or $unit.output -notmatch '(?m)^OK\s*$') { throw "Regression test failed: $($unit.output)" }
}

$hostImportRun = Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'r13_import_closure_smoke.ps1'))
if ($hostImportRun.exit_code -ne 0) { throw "Host import closure failed: $($hostImportRun.output)" }
$hostImport = Read-SingleJson $hostImportRun.output 'host import closure'
$wslImportCommand = "cd '$wslProjectRoot' && bash -n paper_faithful/training/run_paper_text_multiseed_smoke_r13.sh && PYTHONDONTWRITEBYTECODE=1 $lockedPython paper_faithful/training/tests/r13_import_closure_probe.py"
$wslImportRun = Invoke-External 'wsl.exe' @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',$wslImportCommand)
if ($wslImportRun.exit_code -ne 0) { throw "Locked WSL import closure or bash syntax failed: $($wslImportRun.output)" }
try { $wslImportDocument = $wslImportRun.output.Trim() | ConvertFrom-Json -ErrorAction Stop }
catch { throw "locked WSL import closure did not emit valid JSON: $($_.Exception.Message)" }
$wslImport = @()
foreach ($entry in $wslImportDocument) { $wslImport += $entry }
$hostReachable = @($hostImport.source_bindings | ForEach-Object {
    $fullImportPath = [IO.Path]::GetFullPath([string]$_.path)
    if (-not $fullImportPath.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Import path escaped project root: $fullImportPath" }
    $fullImportPath.Substring($projectRoot.Length + 1).Replace('\','/')
} | Sort-Object -Unique)
$wslReachable = @($wslImport | ForEach-Object { [string]$_.path } | Sort-Object -Unique)
$closureDiff = @(Compare-Object -ReferenceObject $hostReachable -DifferenceObject $wslReachable -CaseSensitive)
if ($hostImport.status -ne 'pass' -or $hostImport.reachable_repository_modules -ne 18 -or $hostImport.bound_repository_modules -ne 18 -or $hostImport.omission_refused -ne $true -or $hostReachable.Count -ne 18 -or $wslReachable.Count -ne 18 -or $closureDiff.Count) {
    throw "Host/locked-WSL import closure differs: status=$($hostImport.status) host_reported=$($hostImport.reachable_repository_modules) bound=$($hostImport.bound_repository_modules) omission=$($hostImport.omission_refused) host_count=$($hostReachable.Count) wsl_count=$($wslReachable.Count) diff=$($closureDiff | ConvertTo-Json -Compress)"
}

Assert-NoProductionNamespace
$failClosed = Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $trainingRoot 'launch_paper_text_multiseed_smoke_r13.ps1'),'-ExpectedCanonicalGateSha256',('0' * 64),'-ExpectedUserConfirmationSha256',('0' * 64))
if ($failClosed.exit_code -ne 92) { throw "Absent-gate launcher did not fail closed with exit 92: $($failClosed.output)" }
Assert-NoProductionNamespace

$sourceMap = [ordered]@{
    dispatcher_ps1 = (Join-Path $trainingRoot 'launch_paper_text_multiseed_smoke_r13.ps1')
    supervisor_ps1 = (Join-Path $trainingRoot 'supervise_paper_text_multiseed_smoke_r13.ps1')
    runner_sh = (Join-Path $trainingRoot 'run_paper_text_multiseed_smoke_r13.sh')
    r13_exactly_once_helpers_ps1 = (Join-Path $trainingRoot 'r13_exactly_once_helpers.ps1')
    r12_supervisor_ps1 = (Join-Path $trainingRoot 'supervise_paper_text_multiseed_smoke_r12.ps1')
    r13_static_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_static_fail_closed_smoke.ps1')
    r13_preflight_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_task_scheduler_com_preflight_smoke.ps1')
    r13_registration_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_task_scheduler_com_registration_smoke.ps1')
    r13_exactly_once_refusal_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_exactly_once_refusal_smoke.ps1')
    r13_gpu_compute_refusal_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_gpu_compute_refusal_smoke.ps1')
    r13_supervisor_semantic_diff_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_supervisor_semantic_diff_smoke.ps1')
    r13_import_closure_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_import_closure_smoke.ps1')
    r13_import_closure_probe_py = (Join-Path $PSScriptRoot 'r13_import_closure_probe.py')
    r13_launch_test_evidence_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_launch_test_evidence_smoke.ps1')
    r13_launch_test_evidence_builder_ps1 = $PSCommandPath
    test_multi_seed_py = (Join-Path $PSScriptRoot 'test_multi_seed.py')
    lean_team_contract_json = (Join-Path $projectRoot 'r13_preflighted_taskdef_run_contract.json')
    r13_protocol_json = (Join-Path $trainingRoot 'r13_windows_task_scheduler_com_protocol_20260830.json')
    r12_failure_evidence_json = (Join-Path $trainingRoot 'r12_infrastructure_failure_evidence_20260830.json')
    r12_launch_test_evidence_v4_json = (Join-Path $trainingRoot 'r12_task_scheduler_com_launch_test_evidence_20260830_v4.json')
    source_manifest_json = (Join-Path $projectRoot 'paper_faithful\manifests\source_manifest.json')
    environment_manifest_json = (Join-Path $projectRoot 'paper_faithful\environment\results\wsl_tf24_probe.json')
    cache_manifest_json = (Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json')
    cache_validator_log = (Join-Path $runtimeRoot 'integrity-logs\full-cache-validation-v2.stdout.log')
}
foreach ($binding in @($hostImport.source_bindings)) { $sourceMap[[string]$binding.name] = [string]$binding.path }
$sourceBindings = @($sourceMap.GetEnumerator() | ForEach-Object {
    $resolved = (Resolve-Path -LiteralPath ([string]$_.Value)).Path
    [ordered]@{ name = [string]$_.Key; path = $resolved; sha256 = (Get-Sha256 $resolved) }
})

$r12FailureSha = Get-Sha256 $sourceMap.r12_failure_evidence_json
if ($r12FailureSha -ne '60b3f6b82d5de2dfa69249feede52f50f07c750bcf6662dc9c52decbc7490caa') { throw 'r12 failure evidence changed' }
$r12Failure = Get-Content -LiteralPath $sourceMap.r12_failure_evidence_json -Raw | ConvertFrom-Json -ErrorAction Stop
if ($r12Failure.training_launched -ne $false -or $r12Failure.retriable -ne $false -or $r12Failure.recovery_boundary.r12_retry_resume_relaunch_reuse_forbidden -ne $true) { throw 'r12 failure boundary is invalid' }
$r12LaunchSha = Get-Sha256 $sourceMap.r12_launch_test_evidence_v4_json
if ($r12LaunchSha -ne '3338dea287daed23566ceeecfad7dffbe766e728ada76cbcacf636226ed81558') { throw 'accepted r12 long-canary evidence changed' }
$r12Launch = Get-Content -LiteralPath $sourceMap.r12_launch_test_evidence_v4_json -Raw | ConvertFrom-Json -ErrorAction Stop
if ($r12Launch.status -ne 'pass' -or $r12Launch.windows_task_scheduler_com_canary.case_id -ne '32682db47f0c41f7b0410bc064414245') { throw 'accepted r12 long canary is invalid' }
$protocol = Get-Content -LiteralPath $sourceMap.r13_protocol_json -Raw | ConvertFrom-Json -ErrorAction Stop
if ($protocol.design_id -ne 'R13_WINDOWS_TASK_SCHEDULER_COM_PREFLIGHTED_TASKDEF_V1' -or $protocol.run_id_prefix -ne $prefix -or $protocol.approval_boundary.training_launch_authorized -ne $false) { throw 'r13 preregistered protocol boundary failed' }

$batteries = @(Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus | Where-Object { $_.Active -eq $true })
if (-not $batteries.Count) { throw 'No active battery status' }
$powerOnline = -not @($batteries | Where-Object { $_.PowerOnline -ne $true }).Count
$critical = [bool]@($batteries | Where-Object { $_.Critical -eq $true }).Count
$charge = @(Get-CimInstance -Namespace root\wmi -ClassName BatteryFullChargedCapacity | Where-Object { $_.Active -eq $true } | Select-Object -First 1)
$remaining = @(Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus | Where-Object { $_.Active -eq $true } | Select-Object -First 1)
$batteryPercent = $null
if ($charge.Count -and $remaining.Count -and [double]$charge[0].FullChargedCapacity -gt 0) { $batteryPercent = [math]::Round(100.0 * [double]$remaining[0].RemainingCapacity / [double]$charge[0].FullChargedCapacity, 1) }
if (-not $powerOnline -or $critical) { throw 'Power is not AC-online and noncritical' }
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1
if ($null -eq $gpu -or $gpu.Status -ne 'OK') { throw 'NVIDIA GPU is absent or unhealthy' }
$gpuProcesses = Invoke-External 'wsl.exe' @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',"set -o pipefail; nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d'")
if ($gpuProcesses.exit_code -ne 0) { throw 'WSL GPU compute-process probe failed' }
$gpuProcessCount = @($gpuProcesses.output -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }).Count
if ($gpuProcessCount) { throw 'GPU compute process is present before gate publication' }

$evidence = [ordered]@{
    schema_version = 1
    status = 'pass'
    not_a_training_run = $true
    pilot_launched = $false
    observed_at = (Get-Date).ToString('o')
    run_id_prefix = $prefix
    seeds = @(42, 43)
    expected_children = $children
    design_id = 'R13_WINDOWS_TASK_SCHEDULER_COM_PREFLIGHTED_TASKDEF_V1'
    scientific_protocol = [ordered]@{
        protocol_id = 'PAPER_TEXT_V1'
        stage3_stability_adaptation_id = 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1'
        stage3_gradient_clip_norm = 1.0
        stage3_gradient_accumulation_steps = 128
        gradient_clip_application_point = 'after_effective_batch_average_before_optimizer_step'
    }
    r12_failure_boundary = [ordered]@{
        status = 'failed_before_training'
        sha256 = $r12FailureSha
        training_launched = $false
        retriable = $false
        retry_resume_relaunch_reuse_forbidden = $true
    }
    accepted_predecessor_long_canary = [ordered]@{
        status = 'pass'
        case_id = '32682db47f0c41f7b0410bc064414245'
        evidence_sha256 = $r12LaunchSha
        success_duration_seconds = [int]$r12Launch.windows_task_scheduler_com_canary.success_duration_seconds
        supervisor_semantics_preserved = $true
    }
    supervisor_semantic_diff = $semanticDiff
    task_definition_registration_canary = [ordered]@{
        status = 'pass'
        pilot_launched = $false
        case_id = $caseId
        task_name = [string]$registration.task_name
        evidence_root = $canaryRoot
        task_registered = $true
        task_runex_requested = $true
        cleaned_up = $true
        artifacts = [ordered]@{
            result_json = [ordered]@{ path = $canaryResultPath; sha256 = (Get-Sha256 $canaryResultPath) }
            task_definition_xml = [ordered]@{ path = $canaryXmlPath; sha256 = (Get-Sha256 $canaryXmlPath) }
            sentinel_txt = [ordered]@{ path = $canarySentinelPath; sha256 = (Get-Sha256 $canarySentinelPath) }
        }
    }
    focused_tests = [ordered]@{
        windows_powershell_5_1_static = $static
        windows_powershell_5_1_task_definition_preflight = $preflight
        windows_powershell_5_1_registration_runex = $registration
        windows_powershell_5_1_exactly_once_refusal = $refusal
        windows_powershell_5_1_gpu_compute_refusal = $gpuRefusal
        windows_powershell_5_1_supervisor_semantic_diff = $semanticDiff
        bash_syntax = 'pass'
    }
    fail_closed_absent_gate_and_confirmation = [ordered]@{
        status = 'pass'
        dispatcher_exit_code = 92
        production_artifacts_created = 0
        task_scheduler_entries_created = 0
        pilot_launched = $false
    }
    regression_tests = [ordered]@{
        host_unittest = [ordered]@{ status = 'pass'; tests_run = 10; skipped = 0; exit_code = 0 }
        locked_wsl_tf24_unittest = [ordered]@{ status = 'pass'; tests_run = 10; skipped = 0; exit_code = 0; python = $lockedPython }
        test_module = 'paper_faithful.training.tests.test_multi_seed'
    }
    import_closure = [ordered]@{
        status = 'pass'
        entry_modules = @('paper_faithful.training.cli','paper_faithful.training.models','paper_faithful.training.verify_run')
        host_reachable_repository_modules = 18
        locked_wsl_tf24_reachable_repository_modules = 18
        bound_repository_modules = 18
        omission_refused = $true
        exact_host_wsl_path_match = $true
    }
    production_namespace_absence = [ordered]@{
        status = 'pass'
        canonical_gate_absent_during_test = $true
        confirmation_absent = $true
        dispatch_marker_absent = $true
        attempt_marker_absent = $true
        lifecycle_and_logs_absent = $true
        child_directories_absent = $true
        task_scheduler_r13_namespace_empty = $true
        training_processes_absent = $true
        gpu_training_processes_absent = $true
    }
    resource_snapshot = [ordered]@{
        observed_at = (Get-Date).ToString('o')
        power = [ordered]@{ power_online = $powerOnline; critical = $critical; battery_percent = $batteryPercent }
        gpu = [ordered]@{ name = [string]$gpu.Name; windows_driver_version = [string]$gpu.DriverVersion; status = [string]$gpu.Status; compute_processes = $gpuProcessCount }
        storage = [ordered]@{ c_free_gib = [math]::Round((Get-PSDrive C).Free / 1GB, 3); e_free_gib = [math]::Round((Get-PSDrive E).Free / 1GB, 3) }
        recheck_immediately_before_launch = $true
    }
    source_bindings = $sourceBindings
    supersedes_invalidated_evidence = @(
        [ordered]@{
            local_path = (Join-Path $trainingRoot 'r13_preflighted_taskdef_launch_test_evidence_20260830.json')
            canonical_path = (Join-Path $driverRecoveryRoot 'r13-preflighted-taskdef-launch-test-evidence-20260830.json')
            sha256 = '171de2b717cff765004333edbb8b0322af21b3bf649ffcfe63d680edde9d3e3e'
            ineligible_for_gate = $true
            reason = 'independent review found missing bound dispatch prerequisite, refusal exit-91 implementation, and mechanical supervisor semantic-diff evidence'
        },
        [ordered]@{
            local_path = (Join-Path $trainingRoot 'r13_preflighted_taskdef_launch_test_evidence_20260830_v2.json')
            canonical_path = (Join-Path $driverRecoveryRoot 'r13-preflighted-taskdef-launch-test-evidence-20260830-v2.json')
            sha256 = '8970c5b7bf68b1a402f9849ca022e0dd9e63b728f9b7a93440ebefd7d591eefb'
            ineligible_for_gate = $true
            reason = 'closure review found helper execution before its source hash lock and marker-specific lifecycle races that could return exit 92'
        },
        [ordered]@{
            local_path = (Join-Path $trainingRoot 'r13_preflighted_taskdef_launch_test_evidence_20260830_v3.json')
            canonical_path = (Join-Path $driverRecoveryRoot 'r13-preflighted-taskdef-launch-test-evidence-20260830-v3.json')
            sha256 = 'af9e7514410765d7a3b85f1b91acb7cb87b19cb90ac3ceb4dfa0ea1bdd4107ec'
            ineligible_for_gate = $true
            reason = 'final independent gate review found that live dispatcher and supervisor did not refuse concurrent GPU compute processes despite the zero-process gate policy'
        },
        [ordered]@{
            local_path = (Join-Path $trainingRoot 'r13_preflighted_taskdef_launch_test_evidence_20260830_v4.json')
            canonical_path = (Join-Path $driverRecoveryRoot 'r13-preflighted-taskdef-launch-test-evidence-20260830-v4.json')
            sha256 = '6605d6f88ee33c58bb899ea7a2191ffaf069eeeb433add92c0e71183cfcfc22a'
            ineligible_for_gate = $true
            reason = 'implementation closure review found that nvidia-smi failure could be masked by a Bash pipeline without pipefail in live and evidence probes'
        }
    )
    review_status = 'pending_two_distinct_independent_reviews'
    training_launch_authorized = $false
}

$json = $evidence | ConvertTo-Json -Depth 12
$bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($LocalPath))) | Out-Null
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($CanonicalPath))) | Out-Null
$localStream = [IO.File]::Open([IO.Path]::GetFullPath($LocalPath), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $localStream.Write($bytes, 0, $bytes.Length); $localStream.Flush($true) } finally { $localStream.Dispose() }
$canonicalStream = [IO.File]::Open([IO.Path]::GetFullPath($CanonicalPath), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $canonicalStream.Write($bytes, 0, $bytes.Length); $canonicalStream.Flush($true) } finally { $canonicalStream.Dispose() }

$localHash = Get-Sha256 $LocalPath
$canonicalHash = Get-Sha256 $CanonicalPath
if ($localHash -ne $canonicalHash -or -not [Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($LocalPath), [IO.File]::ReadAllBytes($CanonicalPath))) { throw 'Published r13 launch-test evidence copies differ' }
[ordered]@{ status = 'pass'; local_path = [IO.Path]::GetFullPath($LocalPath); canonical_path = [IO.Path]::GetFullPath($CanonicalPath); sha256 = $localHash; source_bindings = $sourceBindings.Count; canary_case_id = $caseId; pilot_launched = $false } | ConvertTo-Json -Compress
