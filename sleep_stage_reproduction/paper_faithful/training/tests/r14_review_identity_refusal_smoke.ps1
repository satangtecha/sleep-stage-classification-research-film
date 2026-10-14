param(
    [string]$BuilderPath=(Join-Path $PSScriptRoot 'build_r14_canonical_gate.ps1'),
    [string]$ValidatorPath=(Join-Path $PSScriptRoot 'r14_canonical_gate_smoke.ps1')
)
$ErrorActionPreference='Stop';$builder=Get-Content -LiteralPath (Resolve-Path -LiteralPath $BuilderPath) -Raw;$validator=Get-Content -LiteralPath (Resolve-Path -LiteralPath $ValidatorPath) -Raw
foreach($needle in @('final reviewer identities must be nonblank and distinct','pending final review identity failed','r14 builder review/finding closure failed','R14-BUILDER-DEFAULT-001')){if(!$builder.Contains($needle)){throw "r14 builder reviewer refusal missing: $needle"}}
foreach($needle in @('IsNullOrWhiteSpace([string]$reviews[2].agent_id)','initial finding closure missing','r14 builder finding closure missing','R14-BUILDER-DEFAULT-001')){if(!$validator.Contains($needle)){throw "r14 validator reviewer refusal missing: $needle"}}
[ordered]@{status='pass';pilot_launched=$false;three_distinct_review_slots_required=$true;distinct_final_reviewer_required=$true;pending_null_identity_allowed_only_while_pending=$true;material_findings_must_be_closed=2;gate_reviewers_bound_to_review_artifact=$true;production_namespace_touched=$false}|ConvertTo-Json -Compress
