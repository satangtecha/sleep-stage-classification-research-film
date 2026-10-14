param(
    [Parameter(Mandatory=$true)][string]$LocalPath,
    [string]$CanonicalPath
)

$ErrorActionPreference='Stop'
$prefix='paper-text-v1-multiseed-cap128-r12-20260830'
$children=@("$prefix-split42-model42","$prefix-split43-model43")
$local=(Resolve-Path -LiteralPath $LocalPath).Path
$evidence=Get-Content -LiteralPath $local -Raw|ConvertFrom-Json -ErrorAction Stop
if($evidence.schema_version-ne2-or$evidence.status-ne'pass'-or$evidence.not_a_training_run-ne$true-or$evidence.pilot_launched-ne$false){throw 'r12 launch-test evidence status failed'}
if($evidence.run_id_prefix-ne$prefix-or(@($evidence.seeds)-join'|')-ne'42|43'-or(@($evidence.expected_children)-join'|')-ne($children-join'|')){throw 'r12 launch-test identity failed'}
$c=$evidence.windows_task_scheduler_com_canary
if($c.status-ne'pass'-or$c.acceptance_evidence-ne$true-or$c.debug_short_success-ne$false-or$c.pilot_launched-ne$false-or[int]$c.success_duration_seconds-lt180-or[int]$c.heartbeat_span_seconds-lt180-or[int]$c.heartbeat_count-lt36-or[int]$c.heartbeat_interval_seconds_max-gt10-or$c.boot_id_continuous-ne$true-or$c.dispatcher_exited-ne$true-or$c.supervisor_parent-ne'svchost.exe'-or$c.wsl_alive_after_dispatcher_exit-ne$true-or$c.attempt_marker_exclusively_held-ne$true-or$c.stable_input_write_refused-ne$true-or$c.stable_input_replace_refused-ne$true-or$c.atomic_exit_evidence-ne$true-or[int]$c.success_exit_code-ne0-or[int]$c.failure_exit_code-ne23-or[int]$c.second_dispatch_refused_exit_code-ne91-or[int]$c.second_supervisor_refused_exit_code-ne91-or[int]$c.trigger_count-ne0-or$c.multiple_instances-ne'IgnoreNew'-or[int]$c.restart_count-ne0-or$c.execution_time_limit-ne'PT0S'){throw 'r12 long COM canary evidence failed'}

function Read-JsonFile([string]$Path){Get-Content -LiteralPath $Path -Raw|ConvertFrom-Json -ErrorAction Stop}
function Read-JsonLines([string]$Path){
    $items=@()
    foreach($line in Get-Content -LiteralPath $Path){if(-not[string]::IsNullOrWhiteSpace($line)){$items+=($line|ConvertFrom-Json -ErrorAction Stop)}}
    return @($items)
}
function Assert-Exact([bool]$Condition,[string]$Message){if(-not$Condition){throw $Message}}
function Assert-ArtifactHashes([string]$Kind,[string]$Root,$HashObject,$Map){
    foreach($entry in $Map.GetEnumerator()){
        $path=Join-Path $Root $entry.Value
        Assert-Exact (Test-Path -LiteralPath $path -PathType Leaf) "r12 $Kind canary artifact absent: $($entry.Value)"
        $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
        Assert-Exact ($actual-eq[string]$HashObject.($entry.Key)) "r12 $Kind canary artifact changed: $($entry.Value)"
    }
}

$caseId=[string]$c.case_id
Assert-Exact ($caseId-match'^[0-9a-f]{32}$') 'r12 canary case identity failed'
$successRoot=(Resolve-Path -LiteralPath ([string]$c.success_evidence_root)).Path
$failureRoot=(Resolve-Path -LiteralPath ([string]$c.failure_evidence_root)).Path
$expectedSuccessRoot="com-long-success-$caseId";$expectedFailureRoot="com-long-failure-$caseId"
Assert-Exact ((Split-Path -Leaf $successRoot)-eq$expectedSuccessRoot-and(Split-Path -Leaf $failureRoot)-eq$expectedFailureRoot) 'r12 canary evidence root identity failed'
$successInvocation="r12-com-long-success-$caseId";$failureInvocation="r12-com-long-failure-$caseId"
$successTask="SleepStagePaper-R12-COM-Long-Success-$caseId";$failureTask="SleepStagePaper-R12-COM-Long-Failure-$caseId"

$successArtifacts=@{
    acceptance_json='acceptance.json';dispatch_json='dispatch.json';lifecycle_jsonl='lifecycle.jsonl';refusals_jsonl='refusals.jsonl';
    heartbeats_jsonl='wsl-child.heartbeats.jsonl';exit_code_txt='wsl-child.exit-code.txt';supervisor_parent_json='supervisor-parent.json';
    task_policy_json='task-policy.json';refusal_results_json='refusal-results.json';runtime_probes_json='runtime-probes.json';attempt_lock='attempt.lock';dispatch_lock='dispatch.lock';stable_input_txt='stable-input.txt'
}
$failureArtifacts=@{
    dispatch_json='dispatch.json';lifecycle_jsonl='lifecycle.jsonl';heartbeats_jsonl='wsl-child.heartbeats.jsonl';
    exit_code_txt='wsl-child.exit-code.txt';attempt_lock='attempt.lock';dispatch_lock='dispatch.lock';stable_input_txt='stable-input.txt'
}
Assert-ArtifactHashes 'success' $successRoot $c.success_artifact_sha256 $successArtifacts
Assert-ArtifactHashes 'failure' $failureRoot $c.failure_artifact_sha256 $failureArtifacts

$acceptance=Read-JsonFile (Join-Path $successRoot 'acceptance.json')
Assert-Exact ($acceptance.status-eq'pass'-and$acceptance.acceptance_evidence-eq$true-and$acceptance.debug_short_success-eq$false-and$acceptance.pilot_launched-eq$false) 'r12 raw acceptance status failed'
Assert-Exact ((@($acceptance.evidence_roots)-join'|')-eq(@($successRoot,$failureRoot)-join'|')) 'r12 raw acceptance roots failed'

$successDispatch=Read-JsonFile (Join-Path $successRoot 'dispatch.json');$failureDispatch=Read-JsonFile (Join-Path $failureRoot 'dispatch.json')
Assert-Exact ($successDispatch.status-eq'dispatched'-and$successDispatch.task_name-eq$successTask-and$successDispatch.invocation_name-eq$successInvocation-and$successDispatch.mode-eq'success') 'r12 success dispatch binding failed'
Assert-Exact ($failureDispatch.status-eq'dispatched'-and$failureDispatch.task_name-eq$failureTask-and$failureDispatch.invocation_name-eq$failureInvocation-and$failureDispatch.mode-eq'failure') 'r12 failure dispatch binding failed'
Assert-Exact ([int]$successDispatch.dispatcher_pid-gt0-and[int]$failureDispatch.dispatcher_pid-gt0-and-not[string]::IsNullOrWhiteSpace([string]$successDispatch.running_task_instance_guid)-and-not[string]::IsNullOrWhiteSpace([string]$failureDispatch.running_task_instance_guid)) 'r12 dispatch process identity failed'

$successEvents=Read-JsonLines (Join-Path $successRoot 'lifecycle.jsonl');$failureEvents=Read-JsonLines (Join-Path $failureRoot 'lifecycle.jsonl')
Assert-Exact ((@($successEvents.event)-join'|')-eq'supervisor_started|stable_input_locked|process_started|process_exited|terminal_validated') 'r12 success lifecycle ordering failed'
Assert-Exact ((@($failureEvents.event)-join'|')-eq'supervisor_started|stable_input_locked|process_started|process_exited|terminal_validation_failed') 'r12 failure lifecycle ordering failed'
foreach($binding in @(@($successEvents,$successInvocation,'success'),@($failureEvents,$failureInvocation,'failure'))){
    $events=@($binding[0]);$invocation=[string]$binding[1];$mode=[string]$binding[2];$started=$events[0];$processStarted=$events[2];$processExited=$events[3]
    Assert-Exact ($started.ownership_claim-eq'task_scheduler_com'-and$started.invocation_name-eq$invocation-and$started.mode-eq$mode-and[int]$started.supervisor_pid-gt0) "r12 $mode supervisor ownership binding failed"
    Assert-Exact (@($events|Where-Object{[int]$_.supervisor_pid-ne[int]$started.supervisor_pid}).Count-eq0) "r12 $mode supervisor PID continuity failed"
    Assert-Exact ($processStarted.invocation_name-eq$invocation-and$processStarted.child_kind-eq'wsl'-and[int]$processStarted.child_pid-gt0) "r12 $mode process start binding failed"
    Assert-Exact ($processExited.invocation_name-eq$invocation-and[int]$processExited.child_pid-eq[int]$processStarted.child_pid-and$processExited.exit_code_source-eq'atomic_wsl_evidence'-and$processExited.windows_host_exited-eq$true) "r12 $mode atomic exit binding failed"
}
$successStarted=$successEvents[0];$successProcessStarted=$successEvents[2];$successExited=$successEvents[3];$successTerminal=$successEvents[4]
$failureStarted=$failureEvents[0];$failureProcessStarted=$failureEvents[2];$failureExited=$failureEvents[3];$failureTerminal=$failureEvents[4]
Assert-Exact ([int]$successExited.exit_code-eq0-and[int]$successExited.windows_host_exit_code-eq0-and$successTerminal.event-eq'terminal_validated'-and[int]$successTerminal.exit_code-eq0-and$successTerminal.boot_id-eq$successExited.wsl_boot_id-and[int]$successTerminal.child_pid-eq[int]$successProcessStarted.child_pid) 'r12 success terminal evidence failed'
Assert-Exact ([int]$failureExited.exit_code-eq23-and[int]$failureExited.windows_host_exit_code-eq23-and$failureTerminal.event-eq'terminal_validation_failed'-and-not[string]::IsNullOrWhiteSpace([string]$failureTerminal.reason)) 'r12 failure terminal evidence failed'

$parent=Read-JsonFile (Join-Path $successRoot 'supervisor-parent.json')
Assert-Exact ($parent.supervisor_parent_name-eq'svchost.exe'-and[int]$parent.supervisor_parent_pid-gt0-and[int]$parent.supervisor_pid-eq[int]$successStarted.supervisor_pid-and$parent.windows_identity-eq$successStarted.windows_identity-and[int]$parent.session_id-eq[int]$successStarted.session_id-and$parent.ownership_claim-eq$successStarted.ownership_claim) 'r12 supervisor parent evidence failed'

$successHeartbeats=Read-JsonLines (Join-Path $successRoot 'wsl-child.heartbeats.jsonl');$failureHeartbeats=Read-JsonLines (Join-Path $failureRoot 'wsl-child.heartbeats.jsonl')
Assert-Exact ($successHeartbeats.Count-ge36-and$failureHeartbeats.Count-ge1) 'r12 heartbeat count failed'
$successBootIds=@($successHeartbeats.boot_id|Select-Object -Unique);$failureBootIds=@($failureHeartbeats.boot_id|Select-Object -Unique);$successUsers=@($successHeartbeats.wsl_user|Select-Object -Unique);$failureUsers=@($failureHeartbeats.wsl_user|Select-Object -Unique)
Assert-Exact ($successBootIds.Count-eq1-and$failureBootIds.Count-eq1-and$successBootIds[0]-eq$failureBootIds[0]-and$successBootIds[0]-eq$successExited.wsl_boot_id-and$failureBootIds[0]-eq$failureExited.wsl_boot_id) 'r12 heartbeat boot continuity failed'
Assert-Exact ($successUsers.Count-eq1-and$failureUsers.Count-eq1-and$successUsers[0]-eq'techatat'-and$failureUsers[0]-eq'techatat') 'r12 heartbeat user continuity failed'
$heartbeatSpan=[int64]$successHeartbeats[-1].epoch_seconds-[int64]$successHeartbeats[0].epoch_seconds;$heartbeatIntervalMax=0
for($i=1;$i-lt$successHeartbeats.Count;$i++){$delta=[int64]$successHeartbeats[$i].epoch_seconds-[int64]$successHeartbeats[$i-1].epoch_seconds;if($delta-gt$heartbeatIntervalMax){$heartbeatIntervalMax=$delta}}
Assert-Exact ($heartbeatSpan-ge180-and$heartbeatIntervalMax-le10) 'r12 heartbeat duration/interval failed'

$successExit=[int](Get-Content -LiteralPath (Join-Path $successRoot 'wsl-child.exit-code.txt') -Raw).Trim();$failureExit=[int](Get-Content -LiteralPath (Join-Path $failureRoot 'wsl-child.exit-code.txt') -Raw).Trim()
Assert-Exact ($successExit-eq0-and$failureExit-eq23-and$successExit-eq[int]$successExited.exit_code-and$failureExit-eq[int]$failureExited.exit_code) 'r12 atomic exit file evidence failed'
$refusals=@(Read-JsonLines (Join-Path $successRoot 'refusals.jsonl'));$refusalResults=Read-JsonFile (Join-Path $successRoot 'refusal-results.json')
Assert-Exact ($refusals.Count-eq1-and$refusals[0].event-eq'marker_collision_refused'-and$refusals[0].invocation_name-eq$successInvocation-and[int]$refusalResults.second_dispatch_exit_code-eq91-and[int]$refusalResults.second_supervisor_exit_code-eq91) 'r12 duplicate refusal evidence failed'

$runtimeProbes=Read-JsonFile (Join-Path $successRoot 'runtime-probes.json');$probes=@($runtimeProbes.probes)
Assert-Exact ($runtimeProbes.schema_version-eq1-and$runtimeProbes.case_id-eq$caseId-and(@($probes.name)-join'|')-eq'dispatcher_exit|supervisor_alive_after_dispatcher_exit|wsl_alive_after_dispatcher_exit|attempt_marker_exclusive_open|stable_input_write_open|stable_input_replace') 'r12 runtime probe identity/order failed'
foreach($probe in $probes){Assert-Exact (-not[string]::IsNullOrWhiteSpace([string]$probe.observed_at)) "r12 runtime probe timestamp absent: $($probe.name)"}
Assert-Exact ([int]$probes[0].dispatcher_pid-eq[int]$successDispatch.dispatcher_pid-and$probes[0].exited-eq$true-and[int]$probes[0].exit_code-eq0) 'r12 dispatcher exit probe failed'
Assert-Exact ([int]$probes[1].dispatcher_pid-eq[int]$successDispatch.dispatcher_pid-and[int]$probes[1].supervisor_pid-eq[int]$successStarted.supervisor_pid-and$probes[1].alive-eq$true) 'r12 supervisor survival probe failed'
Assert-Exact ([int]$probes[2].dispatcher_pid-eq[int]$successDispatch.dispatcher_pid-and[int]$probes[2].supervisor_pid-eq[int]$successStarted.supervisor_pid-and[int]$probes[2].wsl_pid-eq[int]$successProcessStarted.child_pid-and$probes[2].alive-eq$true) 'r12 WSL survival probe failed'
Assert-Exact ($probes[3].open_refused-eq$true-and$probes[3].exception_type-eq'System.IO.IOException'-and[IO.Path]::GetFullPath([string]$probes[3].path)-eq[IO.Path]::GetFullPath((Join-Path $successRoot 'attempt.lock'))) 'r12 attempt marker exclusive probe failed'
Assert-Exact ($probes[4].open_refused-eq$true-and$probes[4].exception_type-eq'System.IO.IOException'-and[IO.Path]::GetFullPath([string]$probes[4].path)-eq[IO.Path]::GetFullPath((Join-Path $successRoot 'stable-input.txt'))) 'r12 stable input write probe failed'
Assert-Exact ($probes[5].replace_refused-eq$true-and-not[string]::IsNullOrWhiteSpace([string]$probes[5].exception_type)-and[IO.Path]::GetFullPath([string]$probes[5].path)-eq[IO.Path]::GetFullPath((Join-Path $successRoot 'stable-input.txt'))) 'r12 stable input replace probe failed'

$policy=Read-JsonFile (Join-Path $successRoot 'task-policy.json')
Assert-Exact ($policy.Count-eq2-and(@($policy.task_name)-join'|')-eq(@($successTask,$failureTask)-join'|')) 'r12 task policy identity failed'
foreach($item in $policy){Assert-Exact ([int]$item.trigger_element_count-eq0-and[string]::IsNullOrWhiteSpace([string]$item.triggers_inner_xml)-and$item.multiple_instances-eq'IgnoreNew'-and[int]$item.restart_count-eq0-and$item.execution_time_limit-eq'PT0S') 'r12 task policy failed'}
foreach($root in @($successRoot,$failureRoot)){Assert-Exact ((Test-Path -LiteralPath (Join-Path $root 'attempt.lock') -PathType Leaf)-and(Test-Path -LiteralPath (Join-Path $root 'dispatch.lock') -PathType Leaf)-and((Get-Content -LiteralPath (Join-Path $root 'stable-input.txt') -Raw)-eq'immutable-canary-input')) 'r12 permanent marker/stable input evidence failed'}

Assert-Exact ([int]$acceptance.success_duration_seconds-eq[int]$c.success_duration_seconds-and[bool]$acceptance.dispatcher_exited-eq[bool]$probes[0].exited-and[bool]$acceptance.wsl_alive_after_dispatcher_exit-eq[bool]$probes[2].alive-and[bool]$acceptance.attempt_marker_exclusively_held-eq[bool]$probes[3].open_refused-and[bool]$acceptance.stable_input_write_refused-eq[bool]$probes[4].open_refused-and[bool]$acceptance.stable_input_replace_refused-eq[bool]$probes[5].replace_refused-and$acceptance.supervisor_parent-eq$parent.supervisor_parent_name-and[int]$acceptance.heartbeat_count-eq$successHeartbeats.Count-and[int]$acceptance.heartbeat_span_seconds-eq$heartbeatSpan-and[int]$acceptance.heartbeat_interval_seconds_max-eq$heartbeatIntervalMax-and[int]$acceptance.success_exit_code-eq$successExit-and[int]$acceptance.failure_exit_code-eq$failureExit-and[int]$acceptance.second_dispatch_refused-eq[int]$refusalResults.second_dispatch_exit_code-and[int]$acceptance.second_supervisor_refused-eq[int]$refusalResults.second_supervisor_exit_code) 'r12 acceptance/derived evidence mismatch'
Assert-Exact ([bool]$c.dispatcher_exited-eq[bool]$probes[0].exited-and[bool]$c.wsl_alive_after_dispatcher_exit-eq[bool]$probes[2].alive-and[bool]$c.attempt_marker_exclusively_held-eq[bool]$probes[3].open_refused-and[bool]$c.stable_input_write_refused-eq[bool]$probes[4].open_refused-and[bool]$c.stable_input_replace_refused-eq[bool]$probes[5].replace_refused-and$c.supervisor_parent-eq$parent.supervisor_parent_name-and[int]$c.heartbeat_count-eq$successHeartbeats.Count-and[int]$c.heartbeat_span_seconds-eq$heartbeatSpan-and[int]$c.heartbeat_interval_seconds_max-eq$heartbeatIntervalMax-and$c.boot_id-eq$successBootIds[0]-and$c.wsl_user-eq$successUsers[0]-and[int]$c.success_exit_code-eq$successExit-and[int]$c.failure_exit_code-eq$failureExit-and$c.success_terminal_event-eq$successTerminal.event-and$c.failure_terminal_event-eq$failureTerminal.event-and[int]$c.second_dispatch_refused_exit_code-eq[int]$refusalResults.second_dispatch_exit_code-and[int]$c.second_supervisor_refused_exit_code-eq[int]$refusalResults.second_supervisor_exit_code) 'r12 launch summary/derived evidence mismatch'

if($evidence.production_hardening.status-ne'pass'-or$evidence.production_hardening.rejected_runner_blocker_removed-ne$true-or$evidence.production_hardening.single_strict_canonical_cache_load_delegated_to_cli-ne$true-or$evidence.production_hardening.full_confirmation_source_binding_closure_checked-ne$true-or$evidence.production_hardening.task_owned_supervisor_parent_checked_before_attempt_marker-ne$true-or$evidence.production_hardening.bound_supervisor_handshake_required_before_dispatcher_exit-ne$true){throw 'r12 production hardening evidence failed'}
if($evidence.syntax_and_static_validation.status-ne'pass'-or$evidence.fail_closed_absent_gate_and_confirmation.status-ne'pass'-or[int]$evidence.fail_closed_absent_gate_and_confirmation.production_artifacts_created-ne0){throw 'r12 syntax/static/fail-closed evidence failed'}
if($evidence.regression_tests.host_unittest.status-ne'pass'-or[int]$evidence.regression_tests.host_unittest.tests_run-ne10-or$evidence.regression_tests.locked_wsl_tf24_unittest.status-ne'pass'-or[int]$evidence.regression_tests.locked_wsl_tf24_unittest.tests_run-ne10){throw 'r12 regression evidence failed'}
if($evidence.import_closure.status-ne'pass'-or[int]$evidence.import_closure.host_reachable_repository_modules-ne18-or[int]$evidence.import_closure.locked_wsl_tf24_reachable_repository_modules-ne18-or[int]$evidence.import_closure.bound_repository_modules-ne18-or$evidence.import_closure.omission_refused-ne$true){throw 'r12 import closure evidence failed'}
if($evidence.production_namespace_absence.status-ne'pass'-or$evidence.production_namespace_absence.dispatch_marker_absent-ne$true-or$evidence.production_namespace_absence.attempt_marker_absent-ne$true-or$evidence.production_namespace_absence.child_directories_absent-ne$true-or$evidence.production_namespace_absence.task_scheduler_r12_namespace_empty-ne$true){throw 'r12 production namespace evidence failed'}

$project=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$paths=[ordered]@{
    dispatcher_ps1='paper_faithful\training\launch_paper_text_multiseed_smoke_r12.ps1'
    supervisor_ps1='paper_faithful\training\supervise_paper_text_multiseed_smoke_r12.ps1'
    runner_sh='paper_faithful\training\run_paper_text_multiseed_smoke_r12.sh'
    r12_static_smoke_ps1='paper_faithful\training\tests\r12_task_scheduler_com_static_smoke.ps1'
    r12_survival_smoke_ps1='paper_faithful\training\tests\r12_task_scheduler_com_long_survival_smoke.ps1'
    r12_canary_worker_ps1='paper_faithful\training\tests\r12_task_scheduler_com_long_worker.ps1'
    r12_canary_child_sh='paper_faithful\training\tests\r12_task_scheduler_com_long_child.sh'
    r12_import_closure_smoke_ps1='paper_faithful\training\tests\r12_import_closure_smoke.ps1'
    r12_import_closure_probe_py='paper_faithful\training\tests\r12_import_closure_probe.py'
    r12_launch_test_evidence_smoke_ps1='paper_faithful\training\tests\r12_launch_test_evidence_smoke.ps1'
    r12_canonical_gate_smoke_ps1='paper_faithful\training\tests\r12_canonical_gate_smoke.ps1'
    test_multi_seed_py='paper_faithful\training\tests\test_multi_seed.py'
    probe_pilot_progress_ps1='paper_faithful\training\probe_pilot_progress.ps1'
    probe_pilot_process_sh='paper_faithful\training\probe_pilot_process.sh'
    lean_team_contract_json='r12_windows_supervisor_run_contract.json'
    r12_protocol_json='paper_faithful\training\r12_windows_task_scheduler_com_protocol_20260830.json'
    r8_verification_evidence_json='paper_faithful\training\r8_verification_evidence_20260828.json'
    r9_failure_evidence_json='paper_faithful\training\r9_failure_evidence_20260829.json'
    r10_stability_protocol_json='paper_faithful\training\r10_stage3_stability_protocol_20260829.json'
    r10_stability_implementation_evidence_json='paper_faithful\training\r10_stability_implementation_evidence_20260829.json'
    r10_infrastructure_abort_evidence_json='paper_faithful\training\r10_infrastructure_abort_evidence_20260830.json'
    r11_infrastructure_failure_evidence_json='paper_faithful\training\r11_infrastructure_failure_evidence_20260830.json'
    multi_seed_implementation_evidence_json='paper_faithful\training\multi_seed_pilot_implementation_test_evidence_20260828.json'
    training_init_py='paper_faithful\training\__init__.py'
    training_cache_loader_py='paper_faithful\training\cache_loader.py'
    cli_py='paper_faithful\training\cli.py'
    training_metrics_py='paper_faithful\training\metrics.py'
    training_models_py='paper_faithful\training\models.py'
    training_protocols_py='paper_faithful\training\protocols.py'
    training_run_manifest_py='paper_faithful\training\run_manifest.py'
    training_splits_py='paper_faithful\training\splits.py'
    training_storage_py='paper_faithful\training\storage.py'
    trainer_py='paper_faithful\training\trainer.py'
    verify_run_py='paper_faithful\training\verify_run.py'
    sst_init_py='paper_faithful\sst\__init__.py'
    sst_cache_manifest_py='paper_faithful\sst\cache_manifest.py'
    sst_cache_writer_py='paper_faithful\sst\cache_writer.py'
    sst_cohort_cache_py='paper_faithful\sst\cohort_cache.py'
    sst_storage_py='paper_faithful\sst\storage.py'
    sst_transform_py='paper_faithful\sst\transform.py'
    sst_windowing_py='paper_faithful\sst\windowing.py'
    source_manifest_json='paper_faithful\manifests\source_manifest.json'
    environment_manifest_json='paper_faithful\environment\results\wsl_tf24_probe.json'
}
foreach($entry in $paths.GetEnumerator()){
    $actual=(Get-FileHash -LiteralPath (Join-Path $project $entry.Value) -Algorithm SHA256).Hash.ToLowerInvariant()
    if($actual-ne[string]$evidence.source_sha256.($entry.Key)){throw "r12 launch evidence source changed: $($entry.Key)"}
}
$external=@{cache_manifest_json='E:\blp\sleep_stage_reproduction\sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json';cache_validator_log='E:\blp\sleep_stage_reproduction\runtime\integrity-logs\full-cache-validation-v2.stdout.log'}
foreach($entry in $external.GetEnumerator()){$actual=(Get-FileHash -LiteralPath $entry.Value -Algorithm SHA256).Hash.ToLowerInvariant();if($actual-ne[string]$evidence.source_sha256.($entry.Key)){throw "r12 external evidence changed: $($entry.Key)"}}

if(-not[string]::IsNullOrWhiteSpace($CanonicalPath)){
    $canonical=(Resolve-Path -LiteralPath $CanonicalPath).Path
    if((Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash-ne(Get-FileHash -LiteralPath $canonical -Algorithm SHA256).Hash-or-not[Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($local),[IO.File]::ReadAllBytes($canonical))){throw 'r12 launch-test evidence copies differ'}
}

[ordered]@{status='pass';pilot_launched=$false;validated_by_windows_powershell_5_1=$true;local_path=$local;canonical_path=$CanonicalPath}|ConvertTo-Json -Compress
