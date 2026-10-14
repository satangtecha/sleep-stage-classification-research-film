param(
    [Parameter(Mandatory=$true)][string]$GatePath,
    [switch]$AllowPendingFinalReview,
    [ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGateSha256
)

$ErrorActionPreference='Stop'
$prefix='paper-text-v1-multiseed-cap128-r12-20260830'
$children=@("$prefix-split42-model42","$prefix-split43-model43")
$bulkRoot='E:\blp\sleep_stage_reproduction'
$logRoot=Join-Path $bulkRoot 'runtime\training-logs'
$resolved=(Resolve-Path -LiteralPath $GatePath).Path
$hash=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
if(-not[string]::IsNullOrWhiteSpace($ExpectedGateSha256)-and$hash-ne$ExpectedGateSha256.ToLowerInvariant()){throw 'r12 gate SHA-256 mismatch'}
$gate=Get-Content -LiteralPath $resolved -Raw|ConvertFrom-Json -ErrorAction Stop
if($gate.schema_version-ne1-or$gate.status-ne'pass'-or$gate.fresh_launch_authorized-ne$true-or$gate.publication_is_not_launch-ne$true){throw 'r12 gate status failed'}
if($gate.run_id_prefix-ne$prefix-or(@($gate.seeds)-join'|')-ne'42|43'-or(@($gate.expected_children)-join'|')-ne($children-join'|')){throw 'r12 gate identity failed'}
$protocol=$gate.protocol
if($protocol.protocol_id-ne'PAPER_TEXT_V1'-or$protocol.command-ne'multi-seed-pilot'-or[int]$protocol.cap-ne128-or[int]$protocol.stage3_hardware_microbatch-ne1-or[int]$protocol.stage3_effective_batch-ne128-or[int]$protocol.stage3_gradient_accumulation_steps-ne128-or$protocol.stage3_optimizer-ne'SGD'-or[double]$protocol.stage3_learning_rate-ne0.1-or$protocol.stage3_stability_adaptation_id-ne'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1'-or[double]$protocol.stage3_gradient_clip_norm-ne1.0-or$protocol.stage3_gradient_clip_application_point-ne'after_effective_batch_average_before_optimizer_step'-or$protocol.single_strict_canonical_cache_load-ne$true-or$protocol.sequential_children-ne$true-or$protocol.standalone_verify_run_per_completed_child-ne$true-or$protocol.halt_before_later_child_on_failure-ne$true-or$protocol.resume_forbidden-ne$true){throw 'r12 protocol binding failed'}
$durable=$gate.durable_supervisor
if($durable.design_id-ne'R12_WINDOWS_TASK_SCHEDULER_COM_FOREGROUND_WSL_V1'-or$durable.owner-ne'Windows Task Scheduler COM'-or$durable.supervisor_parent-ne'svchost.exe'-or$durable.trigger_count-ne0-or$durable.multiple_instances-ne'IgnoreNew'-or[int]$durable.restart_count-ne0-or$durable.execution_time_limit-ne'PT0S'-or$durable.foreground_wsl_wait_required-ne$true-or$durable.atomic_wsl_exit_evidence_required-ne$true-or$durable.bound_dispatch_handshake_required-ne$true-or$durable.automatic_restart_forbidden-ne$true){throw 'r12 durable supervisor binding failed'}
$exact=$gate.exactly_once
$dispatch=Join-Path $logRoot "$prefix.dispatch.lock";$attempt=Join-Path $logRoot "$prefix.launch.lock"
if($exact.dispatch_marker-ne$dispatch-or$exact.attempt_marker-ne$attempt-or$exact.file_mode-ne'CreateNew'-or$exact.file_share-ne'None'-or$exact.no_retry_resume_reuse-ne$true-or$exact.attempt_count-ne0-or$exact.dispatch_marker_absent-ne$true-or$exact.attempt_marker_absent-ne$true-or$exact.child_run_directories_absent-ne$true){throw 'r12 exactly-once binding failed'}
$launch=$gate.launch_test_evidence
if($launch.status-ne'pass'-or$launch.pilot_launched-ne$false-or$launch.validated_by_windows_powershell_5_1-ne$true-or$launch.byte_identical-ne$true-or[string]$launch.sha256-notmatch'^[0-9a-f]{64}$'){throw 'r12 launch-test binding failed'}
$localLaunch=(Resolve-Path -LiteralPath ([string]$launch.local_path)).Path;$canonicalLaunch=(Resolve-Path -LiteralPath ([string]$launch.canonical_path)).Path
if((Get-FileHash -LiteralPath $localLaunch -Algorithm SHA256).Hash.ToLowerInvariant()-ne$launch.sha256-or(Get-FileHash -LiteralPath $canonicalLaunch -Algorithm SHA256).Hash.ToLowerInvariant()-ne$launch.sha256-or-not[Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($localLaunch),[IO.File]::ReadAllBytes($canonicalLaunch))){throw 'r12 launch-test copies or SHA differ'}

$bindings=@{};foreach($binding in @($gate.source_bindings)){$name=[string]$binding.name;if([string]::IsNullOrWhiteSpace($name)-or$bindings.ContainsKey($name)-or[string]$binding.sha256-notmatch'^[0-9a-f]{64}$'){throw 'r12 source binding invalid or duplicated'};$path=(Resolve-Path -LiteralPath ([string]$binding.path)).Path;$actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();if($actual-ne[string]$binding.sha256){throw "r12 source binding changed: $name"};$bindings[$name]=$binding}
$required=@('dispatcher_ps1','supervisor_ps1','runner_sh','r12_static_smoke_ps1','r12_survival_smoke_ps1','r12_canary_worker_ps1','r12_canary_child_sh','r12_import_closure_smoke_ps1','r12_import_closure_probe_py','r12_launch_test_evidence_smoke_ps1','r12_canonical_gate_smoke_ps1','test_multi_seed_py','lean_team_contract_json','r12_protocol_json','launch_test_evidence_json','review_evidence_json','r11_infrastructure_failure_evidence_json','source_manifest_json','environment_manifest_json','cache_manifest_json','cache_validator_log','training_init_py','training_cache_loader_py','cli_py','training_metrics_py','training_models_py','training_protocols_py','training_run_manifest_py','training_splits_py','training_storage_py','trainer_py','verify_run_py','sst_init_py','sst_cache_manifest_py','sst_cache_writer_py','sst_cohort_cache_py','sst_storage_py','sst_transform_py','sst_windowing_py')
foreach($name in $required){if(!$bindings.ContainsKey($name)){throw "Required r12 source binding absent: $name"}}
if($bindings.launch_test_evidence_json.sha256-ne$launch.sha256-or$bindings.cache_manifest_json.sha256-ne$gate.cache_gate.sha256-or$bindings.cache_validator_log.sha256-ne$gate.cache_gate.validator_v2_log_sha256){throw 'r12 evidence/cache source binding disagreement'}

$project=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$expectedPaths=@{
    dispatcher_ps1=(Join-Path $project 'paper_faithful\training\launch_paper_text_multiseed_smoke_r12.ps1')
    supervisor_ps1=(Join-Path $project 'paper_faithful\training\supervise_paper_text_multiseed_smoke_r12.ps1')
    runner_sh=(Join-Path $project 'paper_faithful\training\run_paper_text_multiseed_smoke_r12.sh')
    cache_manifest_json='E:\blp\sleep_stage_reproduction\sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
    cache_validator_log='E:\blp\sleep_stage_reproduction\runtime\integrity-logs\full-cache-validation-v2.stdout.log'
}
foreach($entry in $expectedPaths.GetEnumerator()){if(-not[IO.Path]::GetFullPath([string]$bindings[$entry.Key].path).Equals([IO.Path]::GetFullPath($entry.Value),[StringComparison]::OrdinalIgnoreCase)){throw "r12 gate critical path differs: $($entry.Key)"}}

$validatorEvents=@(Get-Content -LiteralPath ([string]$bindings.cache_validator_log.path)|ForEach-Object{if($_){try{$_|ConvertFrom-Json -ErrorAction Stop}catch{}}}|Where-Object{$_.status})
if(!$validatorEvents-or$validatorEvents[-1].status-ne'valid'-or$validatorEvents[-1].cache_manifest_sha256-ne$gate.cache_gate.sha256){throw 'r12 cache validator evidence failed'}
& $env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ([string]$bindings.r12_launch_test_evidence_smoke_ps1.path) -LocalPath $localLaunch -CanonicalPath $canonicalLaunch|Out-Null
if($LASTEXITCODE-ne0){throw 'r12 launch-test validator refused gate-bound evidence'}
& $env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ([string]$bindings.r12_import_closure_smoke_ps1.path) -GatePath $resolved|Out-Null
if($LASTEXITCODE-ne0){throw 'r12 import closure validator refused gate'}

$review=Get-Content -LiteralPath ([string]$bindings.review_evidence_json.path) -Raw|ConvertFrom-Json -ErrorAction Stop
$reviews=@($gate.reviewer_bindings)
if($reviews.Count-ne2-or$reviews[0].status-ne'no_material_finding'){throw 'r12 implementation reviewer binding failed'}
if($AllowPendingFinalReview){if($review.status-ne'pending_final_review'-or$reviews[1].status-ne'pending'){throw 'r12 pending final review state failed'}}else{if($review.status-ne'pass'-or@($review.reviews).Count-ne2-or@($review.reviews|Where-Object{$_.status-eq'no_material_finding'}).Count-ne2-or$reviews[1].status-ne'no_material_finding'-or$reviews[0].agent_id-eq$reviews[1].agent_id){throw 'r12 distinct final review evidence failed'}}

$confirmation='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r12-explicit-user-launch-confirmation-20260830.json'
$paths=@($confirmation,$dispatch,$attempt,(Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.dispatch.json"),(Join-Path $logRoot "$prefix.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.stdout.log"),(Join-Path $logRoot "$prefix.stderr.log"),(Join-Path $logRoot "$prefix.workload-exit-code.txt"))+($children|ForEach-Object{Join-Path (Join-Path $bulkRoot 'runs') $_})
$present=@($paths|Where-Object{Test-Path -LiteralPath $_});if($present.Count){throw "r12 production namespace is not empty: $($present-join', ')"}
$scheduler=New-Object -ComObject 'Schedule.Service';$scheduler.Connect();$tasks=@($scheduler.GetFolder('\').GetTasks(1)|Where-Object{$_.Name-match'^SleepStagePaper-r12-COM-'})
if($tasks.Count){throw 'r12 Task Scheduler namespace is not empty'}

[ordered]@{status='pass';pilot_launched=$false;gate_sha256=$hash;pending_final_review=[bool]$AllowPendingFinalReview;source_bindings=@($gate.source_bindings).Count;production_artifacts_present=0;validated_by_windows_powershell_5_1=$true}|ConvertTo-Json -Compress
