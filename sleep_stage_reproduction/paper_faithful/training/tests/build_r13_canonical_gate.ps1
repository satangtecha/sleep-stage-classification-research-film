param(
    [Parameter(Mandatory=$true)][string]$ReviewEvidencePath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedLaunchEvidenceSha256
)

$ErrorActionPreference = 'Stop'
$prefix = 'paper-text-v1-multiseed-cap128-r13-20260830'
$children = @("$prefix-split42-model42", "$prefix-split43-model43")
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$trainingRoot = Join-Path $projectRoot 'paper_faithful\training'
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$runtimeRoot = Join-Path $bulkRoot 'runtime'
$logRoot = Join-Path $runtimeRoot 'training-logs'
$launchLocal = Join-Path $trainingRoot 'r13_preflighted_taskdef_launch_test_evidence_20260830_v5.json'
$launchCanonical = Join-Path $runtimeRoot 'driver-recovery\r13-preflighted-taskdef-launch-test-evidence-20260830-v5.json'
$launchExpectedSha = $ExpectedLaunchEvidenceSha256.ToLowerInvariant()
$r12FailureSha = '60b3f6b82d5de2dfa69249feede52f50f07c750bcf6662dc9c52decbc7490caa'

function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }

function Assert-ProductionNamespaceEmpty {
    $paths = @(
        (Join-Path $runtimeRoot 'driver-recovery\r13-explicit-user-launch-confirmation-20260830.json'),
        (Join-Path $logRoot "$prefix.dispatch.lock"),(Join-Path $logRoot "$prefix.launch.lock"),
        (Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.dispatch.json"),
        (Join-Path $logRoot "$prefix.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.stdout.log"),
        (Join-Path $logRoot "$prefix.stderr.log"),(Join-Path $logRoot "$prefix.workload-exit-code.txt"),
        (Join-Path (Join-Path $bulkRoot 'runs') $children[0]),(Join-Path (Join-Path $bulkRoot 'runs') $children[1])
    )
    $present = @($paths | Where-Object { Test-Path -LiteralPath $_ })
    if ($present.Count) { throw "r13 production namespace is not empty: $($present -join ', ')" }
    $service = New-Object -ComObject 'Schedule.Service'; $service.Connect()
    $tasks = @($service.GetFolder('\').GetTasks(1) | Where-Object { $_.Name -match '^SleepStagePaper-r13-COM-|^SleepStagePaper-R13-TaskDef-Canary-' })
    if ($tasks.Count) { throw 'r13 scheduler namespace is not empty' }
}

if (Test-Path -LiteralPath $OutputPath) { throw "Immutable gate output already exists: $OutputPath" }
Assert-ProductionNamespaceEmpty
$launchLocalResolved = (Resolve-Path -LiteralPath $launchLocal).Path
$launchCanonicalResolved = (Resolve-Path -LiteralPath $launchCanonical).Path
if ((Get-Sha256 $launchLocalResolved) -ne $launchExpectedSha -or (Get-Sha256 $launchCanonicalResolved) -ne $launchExpectedSha -or -not [Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($launchLocalResolved), [IO.File]::ReadAllBytes($launchCanonicalResolved))) { throw 'r13 launch-test evidence changed or copies differ' }
$launch = Get-Content -LiteralPath $launchLocalResolved -Raw | ConvertFrom-Json -ErrorAction Stop
if ($launch.status -ne 'pass' -or $launch.pilot_launched -ne $false -or $launch.training_launch_authorized -ne $false) { throw 'r13 launch-test evidence boundary failed' }
$reviewResolved = (Resolve-Path -LiteralPath $ReviewEvidencePath).Path
$review = Get-Content -LiteralPath $reviewResolved -Raw | ConvertFrom-Json -ErrorAction Stop
if ($review.schema_version -ne 1 -or $review.run_id_prefix -ne $prefix -or $review.pilot_launched -ne $false -or $review.launch_test_evidence_sha256 -ne $launchExpectedSha -or @($review.reviews).Count -ne 2 -or $review.reviews[0].status -ne 'no_material_finding' -or @('pending_final_review','pass') -notcontains $review.status -or [string]::IsNullOrWhiteSpace([string]$review.reviews[0].agent_id)) { throw 'r13 review evidence state failed' }
if ($review.status -eq 'pending_final_review') {
    if ($review.reviews[1].status -ne 'pending' -or -not [string]::IsNullOrWhiteSpace([string]$review.reviews[1].agent_id)) { throw 'r13 pending final reviewer identity failed' }
}
else {
    if ($review.reviews[1].status -ne 'no_material_finding' -or [string]::IsNullOrWhiteSpace([string]$review.reviews[1].agent_id) -or [string]$review.reviews[0].agent_id -eq [string]$review.reviews[1].agent_id) { throw 'r13 final reviewer identities must be nonblank and distinct' }
}

$sourceBindings = @()
$byName = @{}
foreach ($binding in @($launch.source_bindings)) {
    $path = (Resolve-Path -LiteralPath ([string]$binding.path)).Path
    $actualSha = Get-Sha256 $path
    if ($byName.ContainsKey([string]$binding.name) -or $actualSha -ne [string]$binding.sha256) { throw "r13 launch source binding changed: $($binding.name)" }
    $normalized = [ordered]@{ name = [string]$binding.name; path = $path; sha256 = $actualSha }
    $sourceBindings += @($normalized); $byName[$normalized.name] = $normalized
}
$additional = [ordered]@{
    r13_canonical_gate_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_canonical_gate_smoke.ps1')
    r13_canonical_gate_builder_ps1 = $PSCommandPath
    r13_review_identity_refusal_smoke_ps1 = (Join-Path $PSScriptRoot 'r13_review_identity_refusal_smoke.ps1')
    launch_test_evidence_json = $launchLocalResolved
    review_evidence_json = $reviewResolved
}
foreach ($entry in $additional.GetEnumerator()) {
    if ($byName.ContainsKey([string]$entry.Key)) { throw "Duplicate r13 gate binding: $($entry.Key)" }
    $path = (Resolve-Path -LiteralPath ([string]$entry.Value)).Path
    $binding = [ordered]@{ name = [string]$entry.Key; path = $path; sha256 = (Get-Sha256 $path) }
    $sourceBindings += @($binding); $byName[$binding.name] = $binding
}

$cacheManifest = $byName.cache_manifest_json
$cacheValidator = $byName.cache_validator_log
$validatorEvents = @(Get-Content -LiteralPath ([string]$cacheValidator.path) | ForEach-Object { if ($_){ try { $_ | ConvertFrom-Json -ErrorAction Stop } catch {} } } | Where-Object { $_.status })
if (-not $validatorEvents -or $validatorEvents[-1].status -ne 'valid' -or $validatorEvents[-1].cache_manifest_sha256 -ne $cacheManifest.sha256) { throw 'r13 cache validator binding failed' }

$batteries = @(Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus | Where-Object { $_.Active -eq $true })
if (-not $batteries.Count -or @($batteries | Where-Object { $_.PowerOnline -ne $true -or $_.Critical -ne $false }).Count) { throw 'r13 gate requires AC-online noncritical power' }
$gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1
if ($null -eq $gpu -or $gpu.Status -ne 'OK') { throw 'r13 gate GPU probe failed' }
$gpuProcesses = @(& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "set -o pipefail; nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d'" 2>$null)
if ($LASTEXITCODE -ne 0 -or $gpuProcesses.Count) { throw 'r13 gate requires zero GPU compute processes' }
$cFree = [math]::Round((Get-PSDrive C).Free / 1GB, 3)
$eFree = [math]::Round((Get-PSDrive E).Free / 1GB, 3)
if ($cFree -lt 10 -or $eFree -lt 100) { throw 'r13 gate storage minimum failed' }

$gate = [ordered]@{
    schema_version = 1
    status = 'pass'
    fresh_launch_authorized = $true
    publication_is_not_launch = $true
    run_id_prefix = $prefix
    seeds = @(42,43)
    expected_children = $children
    protocol = [ordered]@{
        protocol_id = 'PAPER_TEXT_V1'; command = 'multi-seed-pilot'; cap = 128
        stage3_hardware_microbatch = 1; stage3_effective_batch = 128; stage3_gradient_accumulation_steps = 128
        stage3_optimizer = 'SGD'; stage3_learning_rate = 0.1
        stage3_stability_adaptation_id = 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1'; stage3_gradient_clip_norm = 1.0
        stage3_gradient_clip_application_point = 'after_effective_batch_average_before_optimizer_step'
        single_strict_canonical_cache_load = $true; sequential_children = $true
        standalone_verify_run_per_completed_child = $true; halt_before_later_child_on_failure = $true; resume_forbidden = $true
    }
    durable_supervisor = [ordered]@{
        design_id = 'R13_WINDOWS_TASK_SCHEDULER_COM_PREFLIGHTED_TASKDEF_V1'; owner = 'Windows Task Scheduler COM'; supervisor_parent = 'svchost.exe'
        trigger_count = 0; multiple_instances = 'IgnoreNew'; restart_count = 0; execution_time_limit = 'PT0S'
        allow_demand_start = $true; invalid_allow_start_on_demand_forbidden = $true
        task_definition_constructed_before_dispatch_marker = $true; task_definition_semantically_validated_before_dispatch_marker = $true
        registration_and_runex_after_dispatch_marker = $true; foreground_wsl_wait_required = $true
        atomic_wsl_exit_evidence_required = $true; bound_dispatch_handshake_required = $true; automatic_restart_forbidden = $true
    }
    exactly_once = [ordered]@{
        dispatch_marker = (Join-Path $logRoot "$prefix.dispatch.lock"); attempt_marker = (Join-Path $logRoot "$prefix.launch.lock")
        file_mode = 'CreateNew'; file_share = 'None'; no_retry_resume_reuse = $true; attempt_count = 0
        dispatch_marker_absent = $true; attempt_marker_absent = $true; child_run_directories_absent = $true
    }
    cache_gate = [ordered]@{
        path = [string]$cacheManifest.path; sha256 = [string]$cacheManifest.sha256
        validator_v2_log_path = [string]$cacheValidator.path; validator_v2_log_sha256 = [string]$cacheValidator.sha256
        validator_status = 'valid'; single_strict_validation_in_long_lived_process_required = $true
    }
    launch_test_evidence = [ordered]@{
        status = 'pass'; pilot_launched = $false; validated_by_windows_powershell_5_1 = $true; byte_identical = $true
        local_path = $launchLocalResolved; canonical_path = $launchCanonicalResolved; sha256 = $launchExpectedSha
    }
    predecessor_evidence = [ordered]@{
        run_id_prefix = 'paper-text-v1-multiseed-cap128-r12-20260830'; status = 'failed_before_training'; training_launched = $false
        retry_resume_relaunch_reuse_forbidden = $true; sha256 = $r12FailureSha
    }
    source_bindings = $sourceBindings
    environment = [ordered]@{
        locked_python = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'; wsl_distribution = 'Ubuntu'; wsl_user = 'techatat'
        source_binding_count = $sourceBindings.Count; import_closure_repository_modules = 18
    }
    power_gate = [ordered]@{ required_power_online = $true; required_noncritical = $true; observed_power_online = $true; observed_critical = $false; recheck_immediately_before_launch = $true }
    storage_gate = [ordered]@{ c_minimum_gib = 10; e_minimum_gib = 100; observed_c_free_gib = $cFree; observed_e_free_gib = $eFree; recheck_immediately_before_launch = $true }
    gpu_gate = [ordered]@{ required_status = 'OK'; required_compute_process_count = 0; name = [string]$gpu.Name; windows_driver_version = [string]$gpu.DriverVersion; observed_compute_process_count = 0; recheck_immediately_before_launch = $true }
    explicit_user_confirmation = [ordered]@{
        required = $true; present = $false; must_bind_exact_gate_sha256 = $true; prior_confirmations_invalid = $true
        must_bind_exact_prefix_seeds_children_stage3_adaptation_and_permanent_markers = $true; launch_before_confirmation_forbidden = $true
    }
    review_evidence = [ordered]@{ path = $reviewResolved; sha256 = (Get-Sha256 $reviewResolved); status = [string]$review.status }
    reviewer_bindings = @($review.reviews)
    canonical_publication = [ordered]@{ local_output_path = [IO.Path]::GetFullPath($OutputPath); canonical_path = (Join-Path $runtimeRoot 'driver-recovery\canonical-r13-multiseed-launch-gate-20260830.json'); byte_identical_required = $true; publication_is_not_launch = $true }
}

$json = $gate | ConvertTo-Json -Depth 12
$bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($OutputPath))) | Out-Null
$stream = [IO.File]::Open([IO.Path]::GetFullPath($OutputPath), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
Assert-ProductionNamespaceEmpty
[ordered]@{ status = 'pass'; output_path = [IO.Path]::GetFullPath($OutputPath); sha256 = (Get-Sha256 $OutputPath); source_bindings = $sourceBindings.Count; review_status = [string]$review.status; publication_is_not_launch = $true } | ConvertTo-Json -Compress
