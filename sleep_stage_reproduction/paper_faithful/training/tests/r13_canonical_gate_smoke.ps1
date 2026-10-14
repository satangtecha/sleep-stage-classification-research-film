param(
    [Parameter(Mandatory=$true)][string]$GatePath,
    [switch]$AllowPendingFinalReview,
    [ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGateSha256
)

$ErrorActionPreference = 'Stop'
$prefix = 'paper-text-v1-multiseed-cap128-r13-20260830'
$children = @("$prefix-split42-model42", "$prefix-split43-model43")
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$logRoot = Join-Path $bulkRoot 'runtime\training-logs'
$resolved = (Resolve-Path -LiteralPath $GatePath).Path
$hash = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not [string]::IsNullOrWhiteSpace($ExpectedGateSha256) -and $hash -ne $ExpectedGateSha256.ToLowerInvariant()) { throw 'r13 gate SHA-256 mismatch' }
$gate = Get-Content -LiteralPath $resolved -Raw | ConvertFrom-Json -ErrorAction Stop
if ($gate.schema_version -ne 1 -or $gate.status -ne 'pass' -or $gate.fresh_launch_authorized -ne $true -or $gate.publication_is_not_launch -ne $true) { throw 'r13 gate status failed' }
if ($gate.run_id_prefix -ne $prefix -or (@($gate.seeds) -join '|') -ne '42|43' -or (@($gate.expected_children) -join '|') -ne ($children -join '|')) { throw 'r13 gate identity failed' }

$protocol = $gate.protocol
if ($protocol.protocol_id -ne 'PAPER_TEXT_V1' -or $protocol.command -ne 'multi-seed-pilot' -or [int]$protocol.cap -ne 128 -or [int]$protocol.stage3_hardware_microbatch -ne 1 -or [int]$protocol.stage3_effective_batch -ne 128 -or [int]$protocol.stage3_gradient_accumulation_steps -ne 128 -or $protocol.stage3_optimizer -ne 'SGD' -or [double]$protocol.stage3_learning_rate -ne 0.1 -or $protocol.stage3_stability_adaptation_id -ne 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1' -or [double]$protocol.stage3_gradient_clip_norm -ne 1.0 -or $protocol.stage3_gradient_clip_application_point -ne 'after_effective_batch_average_before_optimizer_step' -or $protocol.single_strict_canonical_cache_load -ne $true -or $protocol.sequential_children -ne $true -or $protocol.standalone_verify_run_per_completed_child -ne $true -or $protocol.halt_before_later_child_on_failure -ne $true -or $protocol.resume_forbidden -ne $true) { throw 'r13 protocol binding failed' }

$durable = $gate.durable_supervisor
if ($durable.design_id -ne 'R13_WINDOWS_TASK_SCHEDULER_COM_PREFLIGHTED_TASKDEF_V1' -or $durable.owner -ne 'Windows Task Scheduler COM' -or $durable.supervisor_parent -ne 'svchost.exe' -or $durable.trigger_count -ne 0 -or $durable.multiple_instances -ne 'IgnoreNew' -or [int]$durable.restart_count -ne 0 -or $durable.execution_time_limit -ne 'PT0S' -or $durable.allow_demand_start -ne $true -or $durable.invalid_allow_start_on_demand_forbidden -ne $true -or $durable.task_definition_constructed_before_dispatch_marker -ne $true -or $durable.task_definition_semantically_validated_before_dispatch_marker -ne $true -or $durable.registration_and_runex_after_dispatch_marker -ne $true -or $durable.foreground_wsl_wait_required -ne $true -or $durable.atomic_wsl_exit_evidence_required -ne $true -or $durable.bound_dispatch_handshake_required -ne $true -or $durable.automatic_restart_forbidden -ne $true) { throw 'r13 durable supervisor binding failed' }

$exact = $gate.exactly_once
$dispatch = Join-Path $logRoot "$prefix.dispatch.lock"
$attempt = Join-Path $logRoot "$prefix.launch.lock"
if ($exact.dispatch_marker -ne $dispatch -or $exact.attempt_marker -ne $attempt -or $exact.file_mode -ne 'CreateNew' -or $exact.file_share -ne 'None' -or $exact.no_retry_resume_reuse -ne $true -or $exact.attempt_count -ne 0 -or $exact.dispatch_marker_absent -ne $true -or $exact.attempt_marker_absent -ne $true -or $exact.child_run_directories_absent -ne $true) { throw 'r13 exactly-once binding failed' }

$launch = $gate.launch_test_evidence
if ($launch.status -ne 'pass' -or $launch.pilot_launched -ne $false -or $launch.validated_by_windows_powershell_5_1 -ne $true -or $launch.byte_identical -ne $true -or [string]$launch.sha256 -notmatch '^[0-9a-f]{64}$') { throw 'r13 launch-test binding failed' }
$localLaunch = (Resolve-Path -LiteralPath ([string]$launch.local_path)).Path
$canonicalLaunch = (Resolve-Path -LiteralPath ([string]$launch.canonical_path)).Path
if ((Get-FileHash -LiteralPath $localLaunch -Algorithm SHA256).Hash.ToLowerInvariant() -ne $launch.sha256 -or (Get-FileHash -LiteralPath $canonicalLaunch -Algorithm SHA256).Hash.ToLowerInvariant() -ne $launch.sha256 -or -not [Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($localLaunch), [IO.File]::ReadAllBytes($canonicalLaunch))) { throw 'r13 launch-test copies or SHA differ' }

$predecessor = $gate.predecessor_evidence
if ($predecessor.run_id_prefix -ne 'paper-text-v1-multiseed-cap128-r12-20260830' -or $predecessor.status -ne 'failed_before_training' -or $predecessor.training_launched -ne $false -or $predecessor.retry_resume_relaunch_reuse_forbidden -ne $true -or $predecessor.sha256 -ne '60b3f6b82d5de2dfa69249feede52f50f07c750bcf6662dc9c52decbc7490caa') { throw 'r13 predecessor failure boundary failed' }

$bindings = @{}
foreach ($binding in @($gate.source_bindings)) {
    $name = [string]$binding.name
    if ([string]::IsNullOrWhiteSpace($name) -or $bindings.ContainsKey($name) -or [string]$binding.sha256 -notmatch '^[0-9a-f]{64}$') { throw 'r13 source binding invalid or duplicated' }
    $path = (Resolve-Path -LiteralPath ([string]$binding.path)).Path
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne [string]$binding.sha256) { throw "r13 source binding changed: $name" }
    $bindings[$name] = $binding
}
$required = @(
    'dispatcher_ps1','supervisor_ps1','runner_sh','r13_exactly_once_helpers_ps1','r12_supervisor_ps1',
    'r13_static_smoke_ps1','r13_preflight_smoke_ps1','r13_registration_smoke_ps1',
    'r13_exactly_once_refusal_smoke_ps1','r13_gpu_compute_refusal_smoke_ps1','r13_supervisor_semantic_diff_smoke_ps1','r13_import_closure_smoke_ps1','r13_import_closure_probe_py',
    'r13_launch_test_evidence_smoke_ps1','r13_launch_test_evidence_builder_ps1','r13_canonical_gate_smoke_ps1','r13_canonical_gate_builder_ps1','r13_review_identity_refusal_smoke_ps1',
    'test_multi_seed_py','lean_team_contract_json','r13_protocol_json','launch_test_evidence_json','review_evidence_json',
    'r12_failure_evidence_json','r12_launch_test_evidence_v4_json','source_manifest_json','environment_manifest_json',
    'cache_manifest_json','cache_validator_log','training_init_py','training_cache_loader_py','cli_py',
    'training_metrics_py','training_models_py','training_protocols_py','training_run_manifest_py','training_splits_py',
    'training_storage_py','trainer_py','verify_run_py','sst_init_py','sst_cache_manifest_py','sst_cache_writer_py',
    'sst_cohort_cache_py','sst_storage_py','sst_transform_py','sst_windowing_py'
)
foreach ($name in $required) { if (-not $bindings.ContainsKey($name)) { throw "Required r13 source binding absent: $name" } }
if ($bindings.launch_test_evidence_json.sha256 -ne $launch.sha256 -or $bindings.r12_failure_evidence_json.sha256 -ne $predecessor.sha256 -or $bindings.cache_manifest_json.sha256 -ne $gate.cache_gate.sha256 -or $bindings.cache_validator_log.sha256 -ne $gate.cache_gate.validator_v2_log_sha256) { throw 'r13 evidence/cache source binding disagreement' }

$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$expectedPaths = @{
    dispatcher_ps1 = (Join-Path $project 'paper_faithful\training\launch_paper_text_multiseed_smoke_r13.ps1')
    supervisor_ps1 = (Join-Path $project 'paper_faithful\training\supervise_paper_text_multiseed_smoke_r13.ps1')
    runner_sh = (Join-Path $project 'paper_faithful\training\run_paper_text_multiseed_smoke_r13.sh')
    cache_manifest_json = 'E:\blp\sleep_stage_reproduction\sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
    cache_validator_log = 'E:\blp\sleep_stage_reproduction\runtime\integrity-logs\full-cache-validation-v2.stdout.log'
}
foreach ($entry in $expectedPaths.GetEnumerator()) {
    if (-not [IO.Path]::GetFullPath([string]$bindings[$entry.Key].path).Equals([IO.Path]::GetFullPath($entry.Value), [StringComparison]::OrdinalIgnoreCase)) { throw "r13 gate critical path differs: $($entry.Key)" }
}

$validatorEvents = @(Get-Content -LiteralPath ([string]$bindings.cache_validator_log.path) | ForEach-Object { if ($_){ try { $_ | ConvertFrom-Json -ErrorAction Stop } catch {} } } | Where-Object { $_.status })
if (-not $validatorEvents -or $validatorEvents[-1].status -ne 'valid' -or $validatorEvents[-1].cache_manifest_sha256 -ne $gate.cache_gate.sha256) { throw 'r13 cache validator evidence failed' }
& $env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ([string]$bindings.r13_launch_test_evidence_smoke_ps1.path) -LocalPath $localLaunch -CanonicalPath $canonicalLaunch | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'r13 launch-test validator refused gate-bound evidence' }
& $env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ([string]$bindings.r13_import_closure_smoke_ps1.path) -GatePath $resolved | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'r13 import closure validator refused gate' }

$review = Get-Content -LiteralPath ([string]$bindings.review_evidence_json.path) -Raw | ConvertFrom-Json -ErrorAction Stop
$reviews = @($gate.reviewer_bindings)
if ($reviews.Count -ne 2 -or $reviews[0].status -ne 'no_material_finding' -or [string]::IsNullOrWhiteSpace([string]$reviews[0].agent_id) -or @($review.reviews).Count -ne 2) { throw 'r13 implementation reviewer binding failed' }
for ($i = 0; $i -lt 2; $i++) {
    foreach ($property in @('review_id','agent_id','role','status')) {
        if ([string]$reviews[$i].$property -ne [string]$review.reviews[$i].$property) { throw "r13 gate reviewer binding differs from review artifact: index=$i property=$property" }
    }
}
if ($AllowPendingFinalReview) {
    if ($review.status -ne 'pending_final_review' -or $reviews[1].status -ne 'pending' -or -not [string]::IsNullOrWhiteSpace([string]$reviews[1].agent_id)) { throw 'r13 pending final review state failed' }
}
else {
    if ($review.status -ne 'pass' -or @($review.reviews | Where-Object { $_.status -eq 'no_material_finding' }).Count -ne 2 -or $reviews[1].status -ne 'no_material_finding' -or [string]::IsNullOrWhiteSpace([string]$reviews[1].agent_id) -or [string]$reviews[0].agent_id -eq [string]$reviews[1].agent_id) { throw 'r13 distinct final review evidence failed' }
}

& $env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ([string]$bindings.r13_review_identity_refusal_smoke_ps1.path) -BuilderPath ([string]$bindings.r13_canonical_gate_builder_ps1.path) -ValidatorPath $PSCommandPath | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'r13 reviewer-identity refusal validator rerun failed' }

if ($gate.power_gate.required_power_online -ne $true -or $gate.power_gate.required_noncritical -ne $true -or $gate.storage_gate.c_minimum_gib -lt 10 -or $gate.storage_gate.e_minimum_gib -lt 100 -or $gate.gpu_gate.required_status -ne 'OK' -or $gate.gpu_gate.required_compute_process_count -ne 0) { throw 'r13 resource gate policy failed' }
if ($gate.explicit_user_confirmation.required -ne $true -or $gate.explicit_user_confirmation.present -ne $false -or $gate.explicit_user_confirmation.must_bind_exact_gate_sha256 -ne $true -or $gate.explicit_user_confirmation.prior_confirmations_invalid -ne $true -or $gate.explicit_user_confirmation.launch_before_confirmation_forbidden -ne $true) { throw 'r13 explicit confirmation boundary failed' }

$confirmation = 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r13-explicit-user-launch-confirmation-20260830.json'
$paths = @(
    $confirmation,$dispatch,$attempt,(Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.dispatch.json"),
    (Join-Path $logRoot "$prefix.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.stdout.log"),(Join-Path $logRoot "$prefix.stderr.log"),
    (Join-Path $logRoot "$prefix.workload-exit-code.txt")
) + ($children | ForEach-Object { Join-Path (Join-Path $bulkRoot 'runs') $_ })
$present = @($paths | Where-Object { Test-Path -LiteralPath $_ })
if ($present.Count) { throw "r13 production namespace is not empty: $($present -join ', ')" }
$scheduler = New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
$tasks = @($scheduler.GetFolder('\').GetTasks(1) | Where-Object { $_.Name -match '^SleepStagePaper-r13-COM-' })
$canaryTasks = @($scheduler.GetFolder('\').GetTasks(1) | Where-Object { $_.Name -match '^SleepStagePaper-R13-TaskDef-Canary-' })
if ($tasks.Count -or $canaryTasks.Count) { throw 'r13 Task Scheduler namespace is not empty' }

[ordered]@{
    status = 'pass'
    pilot_launched = $false
    gate_sha256 = $hash
    pending_final_review = [bool]$AllowPendingFinalReview
    source_bindings = @($gate.source_bindings).Count
    production_artifacts_present = 0
    validated_by_windows_powershell_5_1 = $true
} | ConvertTo-Json -Compress
