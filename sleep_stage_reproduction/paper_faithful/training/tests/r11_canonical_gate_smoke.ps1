param(
    [Parameter(Mandatory=$true)][string]$GatePath,
    [switch]$AllowPendingFinalReview,
    [ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGateSha256
)

$ErrorActionPreference='Stop'
$prefix='paper-text-v1-multiseed-cap128-r11-20260830'
$children=@("$prefix-split42-model42","$prefix-split43-model43")
$bulkRoot='E:\blp\sleep_stage_reproduction'
$logRoot=Join-Path $bulkRoot 'runtime\training-logs'
$expectedUnit='sleep-stage-r11-paper-text-multiseed-cap128-20260830.service'
$gateResolved=(Resolve-Path -LiteralPath $GatePath).Path
$gateHash=(Get-FileHash -LiteralPath $gateResolved -Algorithm SHA256).Hash.ToLowerInvariant()
if(-not [string]::IsNullOrWhiteSpace($ExpectedGateSha256) -and $gateHash -ne $ExpectedGateSha256.ToLowerInvariant()){throw 'r11 canonical gate SHA-256 mismatch'}
$gate=Get-Content -LiteralPath $gateResolved -Raw|ConvertFrom-Json -ErrorAction Stop

if($gate.schema_version -ne 1 -or $gate.status -ne 'pass' -or $gate.fresh_launch_authorized -ne $true -or $gate.publication_is_not_launch -ne $true){throw 'r11 canonical gate status failed'}
if($gate.run_id_prefix -ne $prefix -or (@($gate.seeds) -join '|') -ne '42|43' -or (@($gate.expected_children) -join '|') -ne ($children -join '|')){throw 'r11 canonical gate identity failed'}
$protocol=$gate.protocol
if($protocol.protocol_id -ne 'PAPER_TEXT_V1' -or $protocol.stage3_stability_adaptation_id -ne 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1' -or [double]$protocol.stage3_gradient_clip_norm -ne 1.0 -or $protocol.stage3_gradient_clip_application_point -ne 'after_effective_batch_average_before_optimizer_step' -or [int]$protocol.stage3_gradient_accumulation_steps -ne 128 -or [int]$protocol.stage3_effective_batch -ne 128 -or [int]$protocol.stage3_hardware_microbatch -ne 1 -or [double]$protocol.stage3_learning_rate -ne 0.1){throw 'r11 protocol binding failed'}
$durable=$gate.durable_supervisor
if($durable.design_id -ne 'R11_SYSTEMD_WINDOWS_LOCKHOLDER_V1' -or $durable.unit_name -ne $expectedUnit -or $durable.systemd_restart -ne 'no' -or $durable.systemd_collect -ne $true -or $durable.windows_lockholder_required -ne $true -or $durable.atomic_wsl_exit_evidence_required -ne $true -or $durable.dispatch_capability_required -ne $true){throw 'r11 durable supervisor binding failed'}
$dispatchMarker=Join-Path $logRoot "$prefix.dispatch.lock"
$attemptMarker=Join-Path $logRoot "$prefix.launch.lock"
if($gate.exactly_once.dispatch_marker -ne $dispatchMarker -or $gate.exactly_once.attempt_marker -ne $attemptMarker -or $gate.exactly_once.file_mode -ne 'CreateNew' -or $gate.exactly_once.file_share -ne 'None' -or $gate.exactly_once.no_retry_resume_reuse -ne $true){throw 'r11 exactly-once binding failed'}
if($gate.launch_test_evidence.status -ne 'pass' -or $gate.launch_test_evidence.pilot_launched -ne $false -or [string]$gate.launch_test_evidence.sha256 -notmatch '^[0-9a-f]{64}$'){throw 'r11 launch-test evidence binding failed'}
if([string]$gate.gpu_gate.windows_driver_version -notmatch '^\d+(\.\d+)+$' -or $gate.gpu_gate.PSObject.Properties.Name -contains 'driver_version'){throw 'r11 GPU gate schema failed'}

$names=@{}
foreach($binding in @($gate.source_bindings)){
    $name=[string]$binding.name
    $path=[string]$binding.path
    $sha=[string]$binding.sha256
    if([string]::IsNullOrWhiteSpace($name) -or $names.ContainsKey($name) -or $sha -notmatch '^[0-9a-f]{64}$'){throw 'r11 source binding is invalid or duplicated'}
    $resolved=(Resolve-Path -LiteralPath $path).Path
    $actual=(Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    if($actual -ne $sha){throw "r11 source binding changed: $name"}
    $names[$name]=$binding
}
foreach($required in @('dispatcher_ps1','lockholder_ps1','supervisor_sh','runner_sh','lean_team_contract_json','launch_test_evidence_json','review_evidence_json','cache_manifest_json','cache_validator_log','r10_infrastructure_abort_evidence_json','r10_stability_protocol_json','r10_stability_implementation_evidence_json')){if(!$names.ContainsKey($required)){throw "Required r11 source binding absent: $required"}}
if($names.launch_test_evidence_json.sha256 -ne $gate.launch_test_evidence.sha256){throw 'r11 launch-test source binding disagrees with gate'}
if($names.cache_manifest_json.sha256 -ne $gate.cache_gate.sha256 -or $names.cache_validator_log.sha256 -ne $gate.cache_gate.validator_v2_log_sha256){throw 'r11 cache source binding disagrees with gate'}
$launchEvidence=Get-Content -LiteralPath ([string]$names.launch_test_evidence_json.path) -Raw|ConvertFrom-Json -ErrorAction Stop
if([string]$launchEvidence.resource_snapshot.gpu.windows_driver_version -ne [string]$gate.gpu_gate.windows_driver_version){throw 'r11 gate and launch evidence disagree on Windows GPU driver'}
$dispatcherSource=Get-Content -LiteralPath ([string]$names.dispatcher_ps1.path) -Raw
$lockholderSource=Get-Content -LiteralPath ([string]$names.lockholder_ps1.path) -Raw
$dispatcherGpu=$dispatcherSource.IndexOf('$gate.gpu_gate.windows_driver_version',[StringComparison]::Ordinal)
$dispatcherMarker=$dispatcherSource.IndexOf('$capabilityWrite=[IO.File]::Open($dispatchCapability',[StringComparison]::Ordinal)
$lockholderGpu=$lockholderSource.IndexOf('$gate.gpu_gate.windows_driver_version',[StringComparison]::Ordinal)
$lockholderMarker=$lockholderSource.IndexOf('try {$attemptStream=[IO.File]::Open($attemptMarker',[StringComparison]::Ordinal)
if($dispatcherGpu -lt 0 -or $dispatcherMarker -lt 0 -or $dispatcherGpu -gt $dispatcherMarker -or $lockholderGpu -lt 0 -or $lockholderMarker -lt 0 -or $lockholderGpu -gt $lockholderMarker -or $dispatcherSource -match '\.gpu_gate\.driver_version' -or $lockholderSource -match '\.gpu_gate\.driver_version'){throw 'r11 gate-to-script GPU mapping or pre-marker ordering failed'}
$validatorEvents=@(Get-Content -LiteralPath ([string]$names.cache_validator_log.path)|ForEach-Object{if(-not [string]::IsNullOrWhiteSpace($_)){try{$_|ConvertFrom-Json -ErrorAction Stop}catch{}}}|Where-Object{$_.status})
if(!$validatorEvents -or $validatorEvents[-1].status -ne 'valid' -or $validatorEvents[-1].cache_manifest_sha256 -ne $gate.cache_gate.sha256){throw 'r11 cache validation evidence failed'}

$reviewEvidence=Get-Content -LiteralPath ([string]$names.review_evidence_json.path) -Raw|ConvertFrom-Json -ErrorAction Stop
$reviews=@($gate.reviewer_bindings)
if($reviews.Count -ne 2 -or $reviews[0].status -ne 'no_material_finding'){throw 'r11 implementation review binding failed'}
if($AllowPendingFinalReview){
    if($reviewEvidence.status -ne 'pending_final_review' -or $reviews[1].status -ne 'pending'){throw 'r11 pending final-review state failed'}
} else {
    if($reviewEvidence.status -ne 'pass' -or @($reviewEvidence.reviews).Count -ne 2 -or @($reviewEvidence.reviews|Where-Object{$_.status -eq 'no_material_finding'}).Count -ne 2){throw 'r11 distinct review evidence failed'}
    if($reviews[1].status -ne 'no_material_finding' -or $reviews[0].review_id -eq $reviews[1].review_id -or $reviews[0].agent_id -eq $reviews[1].agent_id){throw 'r11 distinct canonical reviewer bindings failed'}
}

$confirmation=Join-Path $bulkRoot 'runtime\driver-recovery\r11-explicit-user-launch-confirmation-20260830.json'
$capability=Join-Path $logRoot "$prefix.dispatch-capability.json"
$paths=@($confirmation,$capability,$dispatchMarker,$attemptMarker,(Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.stdout.log"),(Join-Path $logRoot "$prefix.stderr.log"),(Join-Path $logRoot "$prefix.workload-exit-code.txt"))+($children|ForEach-Object{Join-Path (Join-Path $bulkRoot 'runs') $_})
$present=@($paths|Where-Object{Test-Path -LiteralPath $_})
if($present.Count -ne 0){throw "r11 production namespace is not empty: $($present -join ', ')"}
$unitLines=@(& wsl.exe -d Ubuntu -u root -e systemctl show $expectedUnit --property=LoadState,ActiveState,SubState,Restart --no-pager 2>$null|ForEach-Object{"$_"})
if(($unitLines -join ';') -notmatch 'LoadState=not-found' -or ($unitLines -join ';') -notmatch 'ActiveState=inactive'){throw 'r11 production systemd unit already exists or is active'}

[pscustomobject]@{status='pass';pilot_launched=$false;gate_sha256=$gateHash;pending_final_review=[bool]$AllowPendingFinalReview;source_bindings=@($gate.source_bindings).Count;production_artifacts_present=0;validated_by_windows_powershell_5_1=$true}|ConvertTo-Json -Compress
