param(
    [Parameter(Mandatory=$true)][string]$LocalPath,
    [string]$CanonicalPath
)

$ErrorActionPreference='Stop'
$expectedPrefix='paper-text-v1-multiseed-cap128-r11-20260830'
$expectedChildren=@("$expectedPrefix-split42-model42","$expectedPrefix-split43-model43")

$localResolved=(Resolve-Path -LiteralPath $LocalPath).Path
$evidence=Get-Content -LiteralPath $localResolved -Raw|ConvertFrom-Json -ErrorAction Stop
if($evidence.schema_version -ne 1 -or $evidence.status -ne 'pass' -or $evidence.not_a_training_run -ne $true -or $evidence.pilot_launched -ne $false){throw 'r11 launch-test evidence status failed'}
if($evidence.run_id_prefix -ne $expectedPrefix -or (@($evidence.seeds) -join '|') -ne '42|43' -or (@($evidence.expected_children) -join '|') -ne ($expectedChildren -join '|')){throw 'r11 launch-test evidence identity failed'}
$canary=$evidence.durable_supervisor_canary
if($canary.status -ne 'pass' -or $canary.pilot_launched -ne $false -or $canary.caller_termination_survived -ne $true -or $canary.supervisor_owned_by_systemd_interop -ne $true -or $canary.lockholder_parent_name -ne 'wslhost.exe' -or $canary.systemd_restart -ne 'no' -or $canary.terminal_validated_recorded -ne $true -or $canary.atomic_nonzero_exit_recorded -ne $true -or $canary.automatic_restart_observed -ne $false){throw 'r11 durable canary evidence failed'}
if($evidence.lifecycle_append_hardening.status -ne 'pass' -or $evidence.lifecycle_append_hardening.post_hardening_full_canary_passed -ne $true){throw 'r11 lifecycle append hardening evidence failed'}
if($evidence.gpu_schema_and_pre_marker_ordering.status -ne 'pass' -or $evidence.gpu_schema_and_pre_marker_ordering.canonical_field -ne 'windows_driver_version' -or $evidence.gpu_schema_and_pre_marker_ordering.obsolete_driver_version_field_refused -ne $true -or $evidence.gpu_schema_and_pre_marker_ordering.lockholder_gpu_storage_cache_process_power_gates_precede_attempt_marker -ne $true){throw 'r11 GPU schema or pre-marker ordering evidence failed'}
if($evidence.supersedes_invalidated_evidence.ineligible_for_final_gate -ne $true -or [string]$evidence.supersedes_invalidated_evidence.sha256 -notmatch '^[0-9a-f]{64}$'){throw 'r11 invalidated v1 evidence lineage failed'}
if($evidence.syntax_and_static_validation.status -ne 'pass' -or $evidence.fail_closed_absent_gate.status -ne 'pass' -or $evidence.fail_closed_absent_gate.production_artifacts_created -ne 0){throw 'r11 static or fail-closed evidence failed'}
if($evidence.regression_tests.host_pytest.tests_run -ne 10 -or $evidence.regression_tests.host_pytest.status -ne 'pass' -or $evidence.regression_tests.locked_wsl_tf24_unittest.tests_run -ne 10 -or $evidence.regression_tests.locked_wsl_tf24_unittest.status -ne 'pass'){throw 'r11 regression evidence failed'}
if($evidence.production_namespace_absence.status -ne 'pass' -or $evidence.production_namespace_absence.dispatch_marker_absent -ne $true -or $evidence.production_namespace_absence.attempt_marker_absent -ne $true -or $evidence.production_namespace_absence.child_directories_absent -ne $true){throw 'r11 namespace absence evidence failed'}
foreach($property in $evidence.source_sha256.PSObject.Properties){if([string]$property.Value -notmatch '^[0-9a-f]{64}$'){throw "Invalid r11 source SHA-256: $($property.Name)"}}

if(-not [string]::IsNullOrWhiteSpace($CanonicalPath)){
    $canonicalResolved=(Resolve-Path -LiteralPath $CanonicalPath).Path
    $localHash=(Get-FileHash -LiteralPath $localResolved -Algorithm SHA256).Hash
    $canonicalHash=(Get-FileHash -LiteralPath $canonicalResolved -Algorithm SHA256).Hash
    if($localHash -ne $canonicalHash -or -not [Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($localResolved),[IO.File]::ReadAllBytes($canonicalResolved))){throw 'r11 launch-test evidence copies are not byte-identical'}
}

[pscustomobject]@{status='pass';pilot_launched=$false;validated_by_windows_powershell_5_1=$true;local_path=$localResolved;canonical_path=$CanonicalPath}|ConvertTo-Json -Compress
