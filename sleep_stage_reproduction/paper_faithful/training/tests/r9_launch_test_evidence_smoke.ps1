param([string]$LauncherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r9.ps1'))
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'r9 launcher does not parse'}
$functionAst=$ast.Find({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-R9LaunchTestEvidence'},$true)
if(!$functionAst){throw 'r9 launch-test evidence helper missing'}
Invoke-Expression $functionAst.Extent.Text

$prefix='paper-text-v1-multiseed-cap128-r9-20260828';$seeds=@(42,43);$children=@("$prefix-split42-model42","$prefix-split43-model43")
$hashNames=@('launcher_ps1','runner_sh','training_init_py','training_cache_loader_py','cli_py','training_metrics_py','training_models_py','training_protocols_py','training_run_manifest_py','training_splits_py','training_storage_py','trainer_py','verify_run_py','sst_init_py','sst_cache_manifest_py','sst_cache_writer_py','sst_cohort_cache_py','sst_storage_py','sst_transform_py','sst_windowing_py','test_multi_seed_py','probe_pilot_progress_ps1','probe_pilot_process_sh','r9_power_gate_smoke_ps1','r9_user_confirmation_gate_smoke_ps1','r9_review_binding_smoke_ps1','r9_lifecycle_failure_smoke_ps1','r9_probe_progress_smoke_ps1','r9_live_power_gate_probe_ps1','r9_launch_test_evidence_smoke_ps1','r9_stable_read_lock_smoke_ps1','r9_import_closure_smoke_ps1','lean_team_contract_json','r8_verification_evidence_json','multi_seed_implementation_evidence_json')
$expectedHashes=[pscustomobject]@{};foreach($name in $hashNames){$expectedHashes|Add-Member -NotePropertyName $name -NotePropertyValue ('a'*64)}
function New-ValidEvidence {
 $source=[pscustomobject]@{};foreach($name in $hashNames){$source|Add-Member -NotePropertyName $name -NotePropertyValue ('a'*64)}
 [pscustomobject]@{
  status='pass';not_a_training_run=$true;pilot_launched=$false;run_id_prefix=$prefix;seeds=@(42,43);expected_children=$children
  powershell_parser=[pscustomobject]@{status='pass'}
  git_bash_syntax=[pscustomobject]@{status='pass';runner_sh=[pscustomobject]@{status='pass';exit_code=0};probe_pilot_process_sh=[pscustomobject]@{status='pass';exit_code=0}}
  r9_smokes=[pscustomobject]@{
   power_gate=[pscustomobject]@{status='pass';refused_failure_classes=14;accepted_statuses=@(2,3,6,7,8,11);pilot_launched=$false}
   user_confirmation_gate=[pscustomobject]@{status='pass';refused_launch_critical_fields=21;valid_confirmation_accepted=$true;external_anchors_precede_parse=$true;marker_ordered=$true;pilot_launched=$false}
   review_binding=[pscustomobject]@{status='pass';refused_launch_critical_fields=27;two_distinct_reviews_accepted=$true;launch_test_evidence_sha256_refused=$true;pilot_launched=$false}
   lifecycle_failure=[pscustomobject]@{status='pass';static_collision_precedes_marker=$true;attempt_evidence_immediate=$true;prelaunch_failure_recorded=$true;raw_exit_precedes_validation=$true;terminal_failure_recorded=$true;pilot_launched=$false}
   probe_progress=[pscustomobject]@{status='pass';multiseed_phase='training_or_evaluation';multiseed_execution_status='running';single_pilot_phase='strict_cache_scan';pilot_launched=$false}
   live_hidden_host_refusal=[pscustomobject]@{status='pass';accepted=$false;refusal='Battery is not stable AC/noncritical';pilot_launched=$false}
   stable_read_race=[pscustomobject]@{
    status='pass'
    c_drive=[pscustomobject]@{drive='C';same_bytes_hashed_and_parsed=$true;windows_read_succeeded=$true;windows_write_refused=$true;windows_replace_refused=$true;wsl_read_succeeded=$true;wsl_write_refused=$true;wsl_replace_refused=$true}
    e_drive=[pscustomobject]@{drive='E';same_bytes_hashed_and_parsed=$true;windows_read_succeeded=$true;windows_write_refused=$true;windows_replace_refused=$true;wsl_read_succeeded=$true;wsl_write_refused=$true;wsl_replace_refused=$true}
    pilot_launched=$false
   }
   import_closure=[pscustomobject]@{status='pass';entry_modules=@('paper_faithful.training.cli','paper_faithful.training.verify_run');reachable_repository_modules=18;bound_repository_modules=18;omission_refused=$true;pilot_launched=$false}
  }
  host_test_multi_seed=[pscustomobject]@{status='pass';tests_run=7;skipped=0;exit_code=0}
  locked_wsl_test_multi_seed=[pscustomobject]@{status='pass';tests_run=7;skipped=0;exit_code=0}
  launch_artifact_check=[pscustomobject]@{status='pass';checked=9;present=0}
  source_sha256=$source
 }
}
function Copy-Evidence($Evidence){$Evidence|ConvertTo-Json -Depth 20|ConvertFrom-Json}
function Get-PathParent($Object,[string]$Path){$parts=$Path.Split('.');$parent=$Object;for($index=0;$index -lt $parts.Count-1;$index++){$parent=$parent.($parts[$index])};[pscustomobject]@{parent=$parent;leaf=$parts[-1]}}
function Remove-PathValue($Object,[string]$Path){$target=Get-PathParent $Object $Path;$target.parent.PSObject.Properties.Remove($target.leaf)}
function Set-PathValue($Object,[string]$Path,$Value){$target=Get-PathParent $Object $Path;$target.parent.($target.leaf)=$Value}
function Add-UnexpectedPathValue($Object,[string]$Path,[string]$Name,$Value){$target=$Object;if(-not [string]::IsNullOrWhiteSpace($Path)){foreach($part in $Path.Split('.')){$target=$target.$part}};$target|Add-Member -NotePropertyName $Name -NotePropertyValue $Value}
function Assert-Refused($Evidence,[string]$Name){$refused=$false;try{Assert-R9LaunchTestEvidence $Evidence $prefix $seeds $children $expectedHashes}catch{$refused=$true};if(!$refused){throw "launch-test evidence accepted invalid case: $Name"}}

$resultCases=@(
 [pscustomobject]@{path='status';invalid='fail'},[pscustomobject]@{path='not_a_training_run';invalid=$false},[pscustomobject]@{path='pilot_launched';invalid=$true},[pscustomobject]@{path='run_id_prefix';invalid='wrong'},[pscustomobject]@{path='seeds';invalid=@(43,42)},[pscustomobject]@{path='expected_children';invalid=@('wrong')},
 [pscustomobject]@{path='powershell_parser.status';invalid='fail'},[pscustomobject]@{path='git_bash_syntax.status';invalid='fail'},[pscustomobject]@{path='git_bash_syntax.runner_sh.status';invalid='fail'},[pscustomobject]@{path='git_bash_syntax.runner_sh.exit_code';invalid=1},[pscustomobject]@{path='git_bash_syntax.probe_pilot_process_sh.status';invalid='fail'},[pscustomobject]@{path='git_bash_syntax.probe_pilot_process_sh.exit_code';invalid=1},
 [pscustomobject]@{path='r9_smokes.power_gate.status';invalid='fail'},[pscustomobject]@{path='r9_smokes.power_gate.refused_failure_classes';invalid=13},[pscustomobject]@{path='r9_smokes.power_gate.accepted_statuses';invalid=@(2,3)},[pscustomobject]@{path='r9_smokes.power_gate.pilot_launched';invalid=$true},
 [pscustomobject]@{path='r9_smokes.user_confirmation_gate.status';invalid='fail'},[pscustomobject]@{path='r9_smokes.user_confirmation_gate.refused_launch_critical_fields';invalid=20},[pscustomobject]@{path='r9_smokes.user_confirmation_gate.valid_confirmation_accepted';invalid=$false},[pscustomobject]@{path='r9_smokes.user_confirmation_gate.external_anchors_precede_parse';invalid=$false},[pscustomobject]@{path='r9_smokes.user_confirmation_gate.marker_ordered';invalid=$false},[pscustomobject]@{path='r9_smokes.user_confirmation_gate.pilot_launched';invalid=$true},
 [pscustomobject]@{path='r9_smokes.review_binding.status';invalid='fail'},[pscustomobject]@{path='r9_smokes.review_binding.refused_launch_critical_fields';invalid=26},[pscustomobject]@{path='r9_smokes.review_binding.two_distinct_reviews_accepted';invalid=$false},[pscustomobject]@{path='r9_smokes.review_binding.launch_test_evidence_sha256_refused';invalid=$false},[pscustomobject]@{path='r9_smokes.review_binding.pilot_launched';invalid=$true},
 [pscustomobject]@{path='r9_smokes.lifecycle_failure.status';invalid='fail'},[pscustomobject]@{path='r9_smokes.lifecycle_failure.static_collision_precedes_marker';invalid=$false},[pscustomobject]@{path='r9_smokes.lifecycle_failure.attempt_evidence_immediate';invalid=$false},[pscustomobject]@{path='r9_smokes.lifecycle_failure.prelaunch_failure_recorded';invalid=$false},[pscustomobject]@{path='r9_smokes.lifecycle_failure.raw_exit_precedes_validation';invalid=$false},[pscustomobject]@{path='r9_smokes.lifecycle_failure.terminal_failure_recorded';invalid=$false},[pscustomobject]@{path='r9_smokes.lifecycle_failure.pilot_launched';invalid=$true},
 [pscustomobject]@{path='r9_smokes.probe_progress.status';invalid='fail'},[pscustomobject]@{path='r9_smokes.probe_progress.multiseed_phase';invalid='strict_cache_scan'},[pscustomobject]@{path='r9_smokes.probe_progress.multiseed_execution_status';invalid='not_started'},[pscustomobject]@{path='r9_smokes.probe_progress.single_pilot_phase';invalid='process_missing'},[pscustomobject]@{path='r9_smokes.probe_progress.pilot_launched';invalid=$true},
 [pscustomobject]@{path='r9_smokes.live_hidden_host_refusal.status';invalid='fail'},[pscustomobject]@{path='r9_smokes.live_hidden_host_refusal.accepted';invalid=$true},[pscustomobject]@{path='r9_smokes.live_hidden_host_refusal.refusal';invalid=''},[pscustomobject]@{path='r9_smokes.live_hidden_host_refusal.pilot_launched';invalid=$true},
 [pscustomobject]@{path='r9_smokes.stable_read_race.status';invalid='fail'},[pscustomobject]@{path='r9_smokes.stable_read_race.pilot_launched';invalid=$true},
 [pscustomobject]@{path='r9_smokes.stable_read_race.c_drive.drive';invalid='E'},[pscustomobject]@{path='r9_smokes.stable_read_race.c_drive.same_bytes_hashed_and_parsed';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.c_drive.windows_read_succeeded';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.c_drive.windows_write_refused';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.c_drive.windows_replace_refused';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.c_drive.wsl_read_succeeded';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.c_drive.wsl_write_refused';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.c_drive.wsl_replace_refused';invalid=$false},
 [pscustomobject]@{path='r9_smokes.stable_read_race.e_drive.drive';invalid='C'},[pscustomobject]@{path='r9_smokes.stable_read_race.e_drive.same_bytes_hashed_and_parsed';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.e_drive.windows_read_succeeded';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.e_drive.windows_write_refused';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.e_drive.windows_replace_refused';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.e_drive.wsl_read_succeeded';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.e_drive.wsl_write_refused';invalid=$false},[pscustomobject]@{path='r9_smokes.stable_read_race.e_drive.wsl_replace_refused';invalid=$false},
 [pscustomobject]@{path='r9_smokes.import_closure.status';invalid='fail'},[pscustomobject]@{path='r9_smokes.import_closure.entry_modules';invalid=@('paper_faithful.training.verify_run','paper_faithful.training.cli')},[pscustomobject]@{path='r9_smokes.import_closure.reachable_repository_modules';invalid=17},[pscustomobject]@{path='r9_smokes.import_closure.bound_repository_modules';invalid=17},[pscustomobject]@{path='r9_smokes.import_closure.omission_refused';invalid=$false},[pscustomobject]@{path='r9_smokes.import_closure.pilot_launched';invalid=$true},
 [pscustomobject]@{path='host_test_multi_seed.status';invalid='fail'},[pscustomobject]@{path='host_test_multi_seed.tests_run';invalid=6},[pscustomobject]@{path='host_test_multi_seed.skipped';invalid=1},[pscustomobject]@{path='host_test_multi_seed.exit_code';invalid=1},
 [pscustomobject]@{path='locked_wsl_test_multi_seed.status';invalid='fail'},[pscustomobject]@{path='locked_wsl_test_multi_seed.tests_run';invalid=6},[pscustomobject]@{path='locked_wsl_test_multi_seed.skipped';invalid=1},[pscustomobject]@{path='locked_wsl_test_multi_seed.exit_code';invalid=1},
 [pscustomobject]@{path='launch_artifact_check.status';invalid='fail'},[pscustomobject]@{path='launch_artifact_check.checked';invalid=8},[pscustomobject]@{path='launch_artifact_check.present';invalid=1}
)
$resultRefusals=0
foreach($case in $resultCases){$removed=Copy-Evidence (New-ValidEvidence);Remove-PathValue $removed $case.path;Assert-Refused $removed "removed $($case.path)";$resultRefusals++;$mutated=Copy-Evidence (New-ValidEvidence);Set-PathValue $mutated $case.path $case.invalid;Assert-Refused $mutated "mutated $($case.path)";$resultRefusals++}
$hashRefusals=0
foreach($name in $hashNames){$removed=Copy-Evidence (New-ValidEvidence);Remove-PathValue $removed "source_sha256.$name";Assert-Refused $removed "removed source hash $name";$hashRefusals++;$mutated=Copy-Evidence (New-ValidEvidence);Set-PathValue $mutated "source_sha256.$name" ('e'*64);Assert-Refused $mutated "mutated source hash $name";$hashRefusals++}
$extra=Copy-Evidence (New-ValidEvidence);$extra.source_sha256|Add-Member -NotePropertyName unexpected_file -NotePropertyValue ('a'*64);Assert-Refused $extra 'extra source hash entry';$hashRefusals++
$openObjectCases=@(
 [pscustomobject]@{path='';name='unexpected';value=$true},[pscustomobject]@{path='powershell_parser';name='errors';value=1},[pscustomobject]@{path='git_bash_syntax';name='unexpected';value=$true},
 [pscustomobject]@{path='git_bash_syntax.runner_sh';name='errors';value=1},[pscustomobject]@{path='git_bash_syntax.probe_pilot_process_sh';name='errors';value=1},[pscustomobject]@{path='r9_smokes';name='unexpected';value=$true},
 [pscustomobject]@{path='r9_smokes.power_gate';name='errors';value=1},[pscustomobject]@{path='r9_smokes.user_confirmation_gate';name='errors';value=1},[pscustomobject]@{path='r9_smokes.review_binding';name='errors';value=1},
 [pscustomobject]@{path='r9_smokes.lifecycle_failure';name='errors';value=1},[pscustomobject]@{path='r9_smokes.probe_progress';name='errors';value=1},[pscustomobject]@{path='r9_smokes.live_hidden_host_refusal';name='errors';value=1},
 [pscustomobject]@{path='r9_smokes.stable_read_race';name='errors';value=1},[pscustomobject]@{path='r9_smokes.stable_read_race.c_drive';name='errors';value=1},[pscustomobject]@{path='r9_smokes.stable_read_race.e_drive';name='errors';value=1},[pscustomobject]@{path='r9_smokes.import_closure';name='errors';value=1},
 [pscustomobject]@{path='host_test_multi_seed';name='failures';value=7},[pscustomobject]@{path='locked_wsl_test_multi_seed';name='failures';value=7},[pscustomobject]@{path='launch_artifact_check';name='unexpected';value=$true}
)
$openObjectRefusals=0;foreach($case in $openObjectCases){$mutated=Copy-Evidence (New-ValidEvidence);Add-UnexpectedPathValue $mutated $case.path $case.name $case.value;Assert-Refused $mutated "unexpected field $($case.path).$($case.name)";$openObjectRefusals++}
$coherentRefused=New-ValidEvidence;Assert-R9LaunchTestEvidence $coherentRefused $prefix $seeds $children $expectedHashes
$coherentAccepted=Copy-Evidence (New-ValidEvidence);$coherentAccepted.r9_smokes.live_hidden_host_refusal.accepted=$true;$coherentAccepted.r9_smokes.live_hidden_host_refusal.refusal=$null;Assert-R9LaunchTestEvidence $coherentAccepted $prefix $seeds $children $expectedHashes
$liveContradictions=@(
 [pscustomobject]@{name='accepted_with_reason';accepted=$true;refusal='unexpected reason'},
 [pscustomobject]@{name='refused_without_reason';accepted=$false;refusal=$null},
 [pscustomobject]@{name='non_bool_accepted';accepted='true';refusal=$null},
 [pscustomobject]@{name='accepted_with_non_string_refusal';accepted=$true;refusal=0},
 [pscustomobject]@{name='refused_with_non_string_refusal';accepted=$false;refusal=1}
)
$liveContradictionRefusals=0;foreach($case in $liveContradictions){$mutated=Copy-Evidence (New-ValidEvidence);$mutated.r9_smokes.live_hidden_host_refusal.accepted=$case.accepted;$mutated.r9_smokes.live_hidden_host_refusal.refusal=$case.refusal;Assert-Refused $mutated $case.name;$liveContradictionRefusals++}
[pscustomobject]@{status='pass';required_result_fields=$resultCases.Count;result_removal_and_mutation_refusals=$resultRefusals;required_source_hashes=$hashNames.Count;source_hash_refusals=$hashRefusals;exact_result_objects=$openObjectCases.Count;unexpected_field_refusals=$openObjectRefusals;coherent_accepted_state_accepted=$true;coherent_refused_state_accepted=$true;live_contradiction_refusals=$liveContradictionRefusals;pilot_launched=$false}|ConvertTo-Json -Compress
