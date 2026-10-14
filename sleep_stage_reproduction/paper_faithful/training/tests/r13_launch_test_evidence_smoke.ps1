param(
    [Parameter(Mandatory=$true)][string]$LocalPath,
    [Parameter(Mandatory=$true)][string]$CanonicalPath
)

$ErrorActionPreference = 'Stop'
$prefix = 'paper-text-v1-multiseed-cap128-r13-20260830'
$children = @("$prefix-split42-model42", "$prefix-split43-model43")
$local = (Resolve-Path -LiteralPath $LocalPath).Path
$canonical = (Resolve-Path -LiteralPath $CanonicalPath).Path
$localHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $local).Hash.ToLowerInvariant()
$canonicalHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $canonical).Hash.ToLowerInvariant()
if ($localHash -ne $canonicalHash -or -not [Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($local), [IO.File]::ReadAllBytes($canonical))) { throw 'r13 launch evidence copies differ' }

$evidence = Get-Content -LiteralPath $local -Raw | ConvertFrom-Json -ErrorAction Stop
if ($evidence.schema_version -ne 1 -or $evidence.status -ne 'pass' -or $evidence.not_a_training_run -ne $true -or $evidence.pilot_launched -ne $false) { throw 'r13 launch evidence status failed' }
if ($evidence.run_id_prefix -ne $prefix -or (@($evidence.seeds) -join '|') -ne '42|43' -or (@($evidence.expected_children) -join '|') -ne ($children -join '|')) { throw 'r13 launch evidence identity failed' }
if ($evidence.r12_failure_boundary.sha256 -ne '60b3f6b82d5de2dfa69249feede52f50f07c750bcf6662dc9c52decbc7490caa' -or $evidence.r12_failure_boundary.retry_resume_relaunch_reuse_forbidden -ne $true) { throw 'r13 predecessor boundary failed' }

$canary = $evidence.task_definition_registration_canary
if ($canary.status -ne 'pass' -or $canary.pilot_launched -ne $false -or $canary.task_registered -ne $true -or $canary.task_runex_requested -ne $true -or $canary.task_name -notmatch '^SleepStagePaper-R13-TaskDef-Canary-[0-9a-f]{32}$') { throw 'r13 TaskDefinition canary status failed' }
$root = (Resolve-Path -LiteralPath ([string]$canary.evidence_root)).Path
$requiredArtifacts = @('result_json', 'task_definition_xml', 'sentinel_txt')
foreach ($name in $requiredArtifacts) {
    $artifact = $canary.artifacts.$name
    $path = (Resolve-Path -LiteralPath ([string]$artifact.path)).Path
    if (-not $path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw "r13 canary artifact escaped evidence root: $name" }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() -ne [string]$artifact.sha256) { throw "r13 canary artifact hash changed: $name" }
}
$result = Get-Content -LiteralPath ([string]$canary.artifacts.result_json.path) -Raw | ConvertFrom-Json -ErrorAction Stop
if ($result.status -ne 'pass' -or $result.pilot_launched -ne $false -or $result.task_registered -ne $true -or $result.task_runex_requested -ne $true -or $result.allow_demand_start -ne $true -or $result.multiple_instances -ne 'IgnoreNew' -or [int]$result.restart_count -ne 0 -or $result.execution_time_limit -ne 'PT0S' -or [int]$result.trigger_count -ne 0) { throw 'r13 raw canary result semantics failed' }
if ((Get-Content -LiteralPath ([string]$canary.artifacts.sentinel_txt.path) -Raw).Trim() -ne 'ok') { throw 'r13 raw canary sentinel failed' }
$xml = [xml](Get-Content -LiteralPath ([string]$canary.artifacts.task_definition_xml.path) -Raw)
$trigger = $xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Triggers"]')
$allow = $xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="AllowStartOnDemand"]')
$multiple = $xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="MultipleInstancesPolicy"]')
$limit = $xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="ExecutionTimeLimit"]')
$command = $xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Actions"]/*[local-name()="Exec"]/*[local-name()="Command"]')
if ($null -eq $trigger -or @($trigger.ChildNodes | Where-Object { $_.NodeType -eq [Xml.XmlNodeType]::Element }).Count -ne 0 -or $allow.InnerText -ne 'true' -or $multiple.InnerText -ne 'IgnoreNew' -or $limit.InnerText -ne 'PT0S' -or $command.InnerText -notmatch 'WindowsPowerShell') { throw 'r13 raw registered TaskDefinition XML failed' }

$bindings = @{}
foreach ($binding in @($evidence.source_bindings)) {
    $name = [string]$binding.name
    if ([string]::IsNullOrWhiteSpace($name) -or $bindings.ContainsKey($name) -or [string]$binding.sha256 -notmatch '^[0-9a-f]{64}$') { throw 'r13 launch evidence source binding invalid or duplicated' }
    $path = (Resolve-Path -LiteralPath ([string]$binding.path)).Path
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() -ne [string]$binding.sha256) { throw "r13 launch evidence source changed: $name" }
    $bindings[$name] = $binding
}
$required = @(
    'dispatcher_ps1','supervisor_ps1','runner_sh','r13_exactly_once_helpers_ps1','r12_supervisor_ps1',
    'r13_static_smoke_ps1','r13_preflight_smoke_ps1','r13_registration_smoke_ps1',
    'r13_exactly_once_refusal_smoke_ps1','r13_gpu_compute_refusal_smoke_ps1','r13_supervisor_semantic_diff_smoke_ps1','r13_import_closure_smoke_ps1','r13_import_closure_probe_py',
    'r13_launch_test_evidence_smoke_ps1','r13_launch_test_evidence_builder_ps1','test_multi_seed_py','lean_team_contract_json','r13_protocol_json',
    'r12_failure_evidence_json','r12_launch_test_evidence_v4_json','source_manifest_json',
    'environment_manifest_json','cache_manifest_json','cache_validator_log',
    'training_init_py','training_cache_loader_py','cli_py','training_metrics_py','training_models_py',
    'training_protocols_py','training_run_manifest_py','training_splits_py','training_storage_py',
    'trainer_py','verify_run_py','sst_init_py','sst_cache_manifest_py','sst_cache_writer_py',
    'sst_cohort_cache_py','sst_storage_py','sst_transform_py','sst_windowing_py'
)
foreach ($name in $required) { if (-not $bindings.ContainsKey($name)) { throw "Required r13 launch evidence source absent: $name" } }

$r12Failure = Get-Content -LiteralPath ([string]$bindings.r12_failure_evidence_json.path) -Raw | ConvertFrom-Json -ErrorAction Stop
if ($r12Failure.training_launched -ne $false -or $r12Failure.retriable -ne $false -or $r12Failure.recovery_boundary.r12_retry_resume_relaunch_reuse_forbidden -ne $true) { throw 'r13 raw r12 failure boundary failed' }
$r12Canary = Get-Content -LiteralPath ([string]$bindings.r12_launch_test_evidence_v4_json.path) -Raw | ConvertFrom-Json -ErrorAction Stop
if ($r12Canary.status -ne 'pass' -or $r12Canary.windows_task_scheduler_com_canary.case_id -ne '32682db47f0c41f7b0410bc064414245' -or $r12Canary.windows_task_scheduler_com_canary.success_duration_seconds -lt 180 -or $r12Canary.windows_task_scheduler_com_canary.success_exit_code -ne 0 -or $r12Canary.windows_task_scheduler_com_canary.failure_exit_code -ne 23) { throw 'r13 accepted long-canary predecessor failed' }
$semantic = $evidence.supervisor_semantic_diff
if ($semantic.status -ne 'pass' -or $semantic.pilot_launched -ne $false -or $semantic.r12_supervisor_sha256 -ne [string]$bindings.r12_supervisor_ps1.sha256 -or $semantic.r13_supervisor_sha256 -ne [string]$bindings.supervisor_ps1.sha256 -or $semantic.r13_helper_sha256 -ne [string]$bindings.r13_exactly_once_helpers_ps1.sha256 -or $semantic.core_foreground_wsl_terminal_invariants_match -ne $true -or $semantic.intentional_r13_preattempt_security_delta_verified -ne $true -or $semantic.helper_hash_locked_before_execution -ne $true -or $semantic.marker_lifecycle_race_maps_to_refusal -ne $true -or $semantic.dispatch_record_before_attempt_marker_before_workload -ne $true -or $semantic.gpu_compute_process_refusal_immediately_before_workload -ne $true -or $semantic.accepted_r12_long_canary_remains_applicable_to_post_attempt_workload_semantics -ne $true) { throw 'r13 supervisor semantic-diff evidence failed' }
$refusal = $evidence.focused_tests.windows_powershell_5_1_exactly_once_refusal
if ($refusal.second_marker_exit_code -ne 91 -or $refusal.marker_plus_lifecycle_race_exit_code -ne 91 -or $refusal.lifecycle_without_marker_exit_code -ne 92 -or $refusal.mismatched_dispatch_refused -ne $true -or $refusal.duplicated_dispatch_refused -ne $true -or $refusal.unlocked_dispatch_refused -ne $true) { throw 'r13 exactly-once refusal evidence failed' }
$gpuRefusal = $evidence.focused_tests.windows_powershell_5_1_gpu_compute_refusal
if ($gpuRefusal.status -ne 'pass' -or $gpuRefusal.pilot_launched -ne $false -or $gpuRefusal.active_compute_pid_refused -ne $true -or $gpuRefusal.failed_probe_refused -ne $true -or $gpuRefusal.wrapper_pipeline_failure_refused -ne $true -or $gpuRefusal.live_probe_uses_pipefail -ne $true -or $gpuRefusal.dispatcher_pre_dispatch_check -ne $true -or $gpuRefusal.supervisor_pre_attempt_check -ne $true -or $gpuRefusal.supervisor_immediate_pre_workload_check -ne $true) { throw 'r13 GPU compute-process refusal evidence failed' }
$superseded = @($evidence.supersedes_invalidated_evidence)
if ($superseded.Count -ne 4 -or $superseded[0].sha256 -ne '171de2b717cff765004333edbb8b0322af21b3bf649ffcfe63d680edde9d3e3e' -or $superseded[1].sha256 -ne '8970c5b7bf68b1a402f9849ca022e0dd9e63b728f9b7a93440ebefd7d591eefb' -or $superseded[2].sha256 -ne 'af9e7514410765d7a3b85f1b91acb7cb87b19cb90ac3ceb4dfa0ea1bdd4107ec' -or $superseded[3].sha256 -ne '6605d6f88ee33c58bb899ea7a2191ffaf069eeeb433add92c0e71183cfcfc22a' -or @($superseded | Where-Object { $_.ineligible_for_gate -ne $true }).Count) { throw 'r13 superseded evidence boundary failed' }
if ($evidence.regression_tests.host_unittest.tests_run -ne 10 -or $evidence.regression_tests.host_unittest.status -ne 'pass' -or $evidence.regression_tests.locked_wsl_tf24_unittest.tests_run -ne 10 -or $evidence.regression_tests.locked_wsl_tf24_unittest.status -ne 'pass') { throw 'r13 regression evidence failed' }
if ($evidence.import_closure.host_reachable_repository_modules -ne 18 -or $evidence.import_closure.locked_wsl_tf24_reachable_repository_modules -ne 18 -or $evidence.import_closure.bound_repository_modules -ne 18 -or $evidence.import_closure.omission_refused -ne $true) { throw 'r13 import closure evidence failed' }

$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$logRoot = Join-Path $bulkRoot 'runtime\training-logs'
$productionPaths = @(
    'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\canonical-r13-multiseed-launch-gate-20260830.json',
    'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r13-explicit-user-launch-confirmation-20260830.json',
    (Join-Path $logRoot "$prefix.dispatch.lock"), (Join-Path $logRoot "$prefix.launch.lock"),
    (Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"), (Join-Path $logRoot "$prefix.dispatch.json"),
    (Join-Path $logRoot "$prefix.lifecycle.jsonl"), (Join-Path $logRoot "$prefix.stdout.log"),
    (Join-Path $logRoot "$prefix.stderr.log"), (Join-Path $logRoot "$prefix.workload-exit-code.txt")
) + ($children | ForEach-Object { Join-Path (Join-Path $bulkRoot 'runs') $_ })
$present = @($productionPaths | Where-Object { Test-Path -LiteralPath $_ })
if ($present.Count) { throw "r13 production namespace is not empty: $($present -join ', ')" }
$scheduler = New-Object -ComObject 'Schedule.Service'
$scheduler.Connect()
$productionTasks = @($scheduler.GetFolder('\').GetTasks(1) | Where-Object { $_.Name -match '^SleepStagePaper-r13-COM-' })
$canaryTasks = @($scheduler.GetFolder('\').GetTasks(1) | Where-Object { $_.Name -match '^SleepStagePaper-R13-TaskDef-Canary-' })
if ($productionTasks.Count -or $canaryTasks.Count) { throw 'r13 Task Scheduler namespace is not empty after tests' }

& $env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ([string]$bindings.r13_exactly_once_refusal_smoke_ps1.path) | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'r13 exactly-once refusal validator rerun failed' }
& $env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ([string]$bindings.r13_gpu_compute_refusal_smoke_ps1.path) -DispatcherPath ([string]$bindings.dispatcher_ps1.path) -SupervisorPath ([string]$bindings.supervisor_ps1.path) -HelperPath ([string]$bindings.r13_exactly_once_helpers_ps1.path) | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'r13 GPU compute-process refusal validator rerun failed' }
& $env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ([string]$bindings.r13_supervisor_semantic_diff_smoke_ps1.path) -R12SupervisorPath ([string]$bindings.r12_supervisor_ps1.path) -R13SupervisorPath ([string]$bindings.supervisor_ps1.path) -R13HelperPath ([string]$bindings.r13_exactly_once_helpers_ps1.path) | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'r13 supervisor semantic-diff validator rerun failed' }

[ordered]@{
    status = 'pass'
    pilot_launched = $false
    validated_by_windows_powershell_5_1 = $true
    local_path = $local
    canonical_path = $canonical
    sha256 = $localHash
    source_bindings = @($evidence.source_bindings).Count
    registration_canary_case_id = [string]$canary.case_id
    production_artifacts_present = 0
} | ConvertTo-Json -Compress
