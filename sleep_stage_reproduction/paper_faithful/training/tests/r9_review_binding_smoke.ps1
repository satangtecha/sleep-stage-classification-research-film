param([string]$LauncherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r9.ps1'))
$ErrorActionPreference='Stop';$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath),[ref]$tokens,[ref]$errors);if($errors.Count){throw 'r9 launcher does not parse'}
$functionAst=$ast.Find({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-R9ReviewBindings'},$true);if(!$functionAst){throw 'r9 review gate missing'};Invoke-Expression $functionAst.Extent.Text
$prefix='paper-text-v1-multiseed-cap128-r9-20260828';$launcherHash='b'*64;$runnerHash='c'*64;$contractHash='d'*64
function New-Source {[pscustomobject]@{launcher_ps1=$launcherHash;runner_sh=$runnerHash;lean_team_contract_json=$contractHash}}
function New-ValidGate {
 [pscustomobject]@{launch_test_evidence=[pscustomobject]@{sha256='a'*64};reviewer_bindings=[pscustomobject]@{
  implementation_review=[pscustomobject]@{review_id='implementation-review';agent_id='implementation-agent';role='implementation_reviewer';status='no_material_finding';run_id_prefix=$prefix;reviewed_source_sha256=(New-Source);all_findings_closed=$true;multi_seed_implementation_reviewed=$true;two_child_contract_reviewed=$true}
  launch_gate_review=[pscustomobject]@{review_id='launch-review';agent_id='launch-agent';role='launch_gate_reviewer';status='no_material_finding';run_id_prefix=$prefix;reviewed_source_sha256=(New-Source);all_findings_closed=$true;exactly_once_launch_gate_reviewed=$true;lifecycle_failure_evidence_reviewed=$true;fresh_launch_authorized=$true;launch_test_evidence_sha256='a'*64}
 }}
}
function Assert-Refused([string]$Name,[scriptblock]$Mutate){$gate=New-ValidGate;& $Mutate $gate;$refused=$false;try{Assert-R9ReviewBindings $gate $prefix $launcherHash $runnerHash $contractHash}catch{$refused=$true};if(!$refused){throw "review field accepted: $Name"}}
$cases=@(
 @('implementation_record',{param($g)$g.reviewer_bindings.implementation_review=$null}),@('launch_record',{param($g)$g.reviewer_bindings.launch_gate_review=$null}),
 @('implementation_review_id',{param($g)$g.reviewer_bindings.implementation_review.review_id=''}),@('launch_review_id',{param($g)$g.reviewer_bindings.launch_gate_review.review_id=''}),@('distinct_review_id',{param($g)$g.reviewer_bindings.launch_gate_review.review_id='implementation-review'}),
 @('implementation_agent_id',{param($g)$g.reviewer_bindings.implementation_review.agent_id=''}),@('launch_agent_id',{param($g)$g.reviewer_bindings.launch_gate_review.agent_id=''}),@('distinct_agent_id',{param($g)$g.reviewer_bindings.launch_gate_review.agent_id='implementation-agent'}),
 @('implementation_role',{param($g)$g.reviewer_bindings.implementation_review.role='wrong'}),@('launch_role',{param($g)$g.reviewer_bindings.launch_gate_review.role='wrong'}),
 @('implementation_status',{param($g)$g.reviewer_bindings.implementation_review.status='finding'}),@('launch_status',{param($g)$g.reviewer_bindings.launch_gate_review.status='finding'}),
 @('implementation_prefix',{param($g)$g.reviewer_bindings.implementation_review.run_id_prefix='wrong'}),@('launch_prefix',{param($g)$g.reviewer_bindings.launch_gate_review.run_id_prefix='wrong'}),
 @('implementation_launcher',{param($g)$g.reviewer_bindings.implementation_review.reviewed_source_sha256.launcher_ps1='e'*64}),@('implementation_runner',{param($g)$g.reviewer_bindings.implementation_review.reviewed_source_sha256.runner_sh='e'*64}),@('implementation_contract',{param($g)$g.reviewer_bindings.implementation_review.reviewed_source_sha256.lean_team_contract_json='e'*64}),
 @('launch_launcher',{param($g)$g.reviewer_bindings.launch_gate_review.reviewed_source_sha256.launcher_ps1='e'*64}),@('launch_runner',{param($g)$g.reviewer_bindings.launch_gate_review.reviewed_source_sha256.runner_sh='e'*64}),@('launch_contract',{param($g)$g.reviewer_bindings.launch_gate_review.reviewed_source_sha256.lean_team_contract_json='e'*64}),
 @('implementation_closure',{param($g)$g.reviewer_bindings.implementation_review.all_findings_closed=$false}),@('launch_closure',{param($g)$g.reviewer_bindings.launch_gate_review.all_findings_closed=$false}),
 @('implementation_reviewed',{param($g)$g.reviewer_bindings.implementation_review.multi_seed_implementation_reviewed=$false}),@('two_child_reviewed',{param($g)$g.reviewer_bindings.implementation_review.two_child_contract_reviewed=$false}),
 @('exactly_once_reviewed',{param($g)$g.reviewer_bindings.launch_gate_review.exactly_once_launch_gate_reviewed=$false}),@('lifecycle_reviewed',{param($g)$g.reviewer_bindings.launch_gate_review.lifecycle_failure_evidence_reviewed=$false}),@('fresh_authorized',{param($g)$g.reviewer_bindings.launch_gate_review.fresh_launch_authorized=$false})
)
foreach($case in $cases){Assert-Refused $case[0] $case[1]}
$evidenceBindingGate=New-ValidGate;$evidenceBindingGate.reviewer_bindings.launch_gate_review.launch_test_evidence_sha256='e'*64;$evidenceBindingRefused=$false;try{Assert-R9ReviewBindings $evidenceBindingGate $prefix $launcherHash $runnerHash $contractHash}catch{$evidenceBindingRefused=$true};if(!$evidenceBindingRefused){throw 'launch review accepted a mismatched launch-test evidence SHA-256'}
$valid=New-ValidGate;Assert-R9ReviewBindings $valid $prefix $launcherHash $runnerHash $contractHash
[pscustomobject]@{status='pass';refused_launch_critical_fields=$cases.Count;two_distinct_reviews_accepted=$true;launch_test_evidence_sha256_refused=$evidenceBindingRefused;pilot_launched=$false}|ConvertTo-Json -Compress
