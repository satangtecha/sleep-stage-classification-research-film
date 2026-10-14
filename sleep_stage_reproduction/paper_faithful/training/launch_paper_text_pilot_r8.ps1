param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{64}$')]
    [string]$ExpectedRecoveryGateSha256,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{64}$')]
    [string]$ExpectedUserConfirmationSha256
)

$ErrorActionPreference = 'Stop'
$scriptExitCode = 1

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$cacheManifest = Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
$validationLog = Join-Path $bulkRoot 'runtime\integrity-logs\full-cache-validation-v2.stdout.log'
$driverRecoveryManifest = Join-Path $bulkRoot 'runtime\driver-recovery\driver_recovery_manifest.json'
$recoveryGate = Join-Path $bulkRoot 'runtime\driver-recovery\post-recovery-gate-r8-20260827.json'
$userConfirmation = Join-Path $bulkRoot 'runtime\driver-recovery\r8-explicit-user-launch-confirmation-20260827.json'
$sourceThreadId = '01a014bc-7bc1-7590-bd2b-029c8a84285b'
$diagnosis = Join-Path $bulkRoot 'runtime\driver-recovery\r5-stage3-failure-diagnosis-20260826.json'
$r6Diagnosis = Join-Path $bulkRoot 'runtime\driver-recovery\r6-preflight-failure-diagnosis-20260826.json'
$r7Diagnosis = Join-Path $bulkRoot 'runtime\driver-recovery\r7-critical-battery-interruption-diagnosis-20260827.json'
$testEvidence = Join-Path $bulkRoot 'runtime\driver-recovery\r5-gradient-accumulation-test-evidence-20260826.json'
$stage3Diagnostic = Join-Path $bulkRoot 'runtime\diagnostics\paper-text-v1-stage3-accumulation-r5ckpt-20260826-v2.json'
$r5Execution = Join-Path $bulkRoot 'runs\paper-text-v1-pilot-cap128-seed42-r5-20260826\execution.json'
$r5Stage2Checkpoint = Join-Path $bulkRoot 'runs\paper-text-v1-pilot-cap128-seed42-r5-20260826\stage2.weights.h5'
$logRoot = Join-Path $bulkRoot 'runtime\training-logs'
$runId = 'paper-text-v1-pilot-cap128-seed42-r8-20260827'
$runDirectory = Join-Path (Join-Path $bulkRoot 'runs') $runId
$stdout = Join-Path $logRoot "$runId.stdout.log"
$stderr = Join-Path $logRoot "$runId.stderr.log"
$lifecycle = Join-Path $logRoot "$runId.lifecycle.jsonl"
$launchLock = Join-Path $logRoot "$runId.launch.lock"
$runner = Join-Path $PSScriptRoot 'run_paper_text_pilot_r8.sh'
$cli = Join-Path $PSScriptRoot 'cli.py'
$trainer = Join-Path $PSScriptRoot 'trainer.py'
$metrics = Join-Path $PSScriptRoot 'metrics.py'
$models = Join-Path $PSScriptRoot 'models.py'
$splits = Join-Path $PSScriptRoot 'splits.py'
$readme = Join-Path $PSScriptRoot 'README.md'
$diagnosticSource = Join-Path $PSScriptRoot 'stage3_stability_smoke.py'
$testExecution = Join-Path $PSScriptRoot 'tests\test_execution_corrections.py'
$testTrainer = Join-Path $PSScriptRoot 'tests\test_trainer_contract.py'
$testScaffold = Join-Path $PSScriptRoot 'tests\test_training_scaffold.py'
$r8PowerGateSmoke = Join-Path $PSScriptRoot 'tests\r8_power_gate_smoke.ps1'
$r8ReviewBindingSmoke = Join-Path $PSScriptRoot 'tests\r8_review_binding_smoke.ps1'
$r8LivePowerGateProbe = Join-Path $PSScriptRoot 'tests\r8_live_power_gate_probe.ps1'
$r8UserConfirmationGateSmoke = Join-Path $PSScriptRoot 'tests\r8_user_confirmation_gate_smoke.ps1'
$r8RecoveryTestEvidence = Join-Path $bulkRoot 'runtime\driver-recovery\r8-power-gate-test-evidence-20260827-v3.json'
$contract = Join-Path $projectRoot 'lean_team_contract.json'
$sourceManifest = Join-Path $projectRoot 'paper_faithful\manifests\source_manifest.json'
$environmentManifest = Join-Path $projectRoot 'paper_faithful\environment\results\wsl_tf24_probe.json'
$failedR5Lifecycle = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r5-20260826.lifecycle.jsonl'
$failedR6LauncherStdout = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r6-20260826.launcher.stdout.log'
$failedR6LauncherStderr = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r6-20260826.launcher.stderr.log'
$failedR6LaunchLock = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r6-20260826.launch.lock'
$forbiddenR6Lifecycle = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r6-20260826.lifecycle.jsonl'
$forbiddenR6RunDirectory = Join-Path (Join-Path $bulkRoot 'runs') 'paper-text-v1-pilot-cap128-seed42-r6-20260826'
$failedR7PilotStdout = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r7-20260826.stdout.log'
$failedR7PilotStderr = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r7-20260826.stderr.log'
$failedR7LauncherStdout = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r7-20260826.launcher.stdout.log'
$failedR7LauncherStderr = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r7-20260826.launcher.stderr.log'
$failedR7Lifecycle = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r7-20260826.lifecycle.jsonl'
$failedR7LaunchLock = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r7-20260826.launch.lock'
$forbiddenR7RunDirectory = Join-Path (Join-Path $bulkRoot 'runs') 'paper-text-v1-pilot-cap128-seed42-r7-20260826'

function Get-Sha256([string]$Path) {
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try { $sha = [System.Security.Cryptography.SHA256]::Create(); try { $digest = $sha.ComputeHash($stream) } finally { $sha.Dispose() } } finally { $stream.Dispose() }
    return -join ($digest | ForEach-Object { $_.ToString('x2') })
}

function Write-LifecycleEvent([hashtable]$Payload) {
    $Payload.timestamp = (Get-Date).ToString('o')
    Add-Content -LiteralPath $lifecycle -Value ($Payload | ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}

function Get-StableAcPowerFacts {
    $batteryStatus = @(Get-CimInstance -Namespace 'root\wmi' -ClassName 'BatteryStatus' -ErrorAction Stop)
    if ($batteryStatus.Count -eq 0) { throw 'BatteryStatus is unavailable; refusing launch without stable AC evidence' }
    $activeBatteryStatus = @($batteryStatus | Where-Object { $_.Active -eq $true })
    if ($activeBatteryStatus.Count -eq 0) { throw 'No active BatteryStatus instance is available; refusing launch without stable AC evidence' }
    foreach ($battery in $activeBatteryStatus) {
        if ($battery.PowerOnline -ne $true -or $battery.Critical -ne $false) { throw 'Active battery is not online and noncritical; refusing launch' }
    }
    $win32Batteries = @(Get-CimInstance -ClassName 'Win32_Battery' -ErrorAction Stop)
    if ($win32Batteries.Count -eq 0) { throw 'Win32_Battery is unavailable; refusing launch without usable-charge evidence' }
    $acCompatibleBatteryStatuses = @(2, 3, 6, 7, 8, 11)
    foreach ($battery in $win32Batteries) {
        if ($null -eq $battery.EstimatedChargeRemaining -or [double]$battery.EstimatedChargeRemaining -le 0 -or $null -eq $battery.BatteryStatus -or $acCompatibleBatteryStatuses -notcontains [int]$battery.BatteryStatus) { throw 'Win32_Battery does not report AC-compatible noncritical usable charge; refusing launch' }
    }
    return [pscustomobject]@{
        battery_status = @($batteryStatus | ForEach-Object { [pscustomobject]@{ instance_name = $_.InstanceName; active = $_.Active; power_online = $_.PowerOnline; critical = $_.Critical; remaining_capacity = $_.RemainingCapacity } })
        win32_battery = @($win32Batteries | ForEach-Object { [pscustomobject]@{ device_id = $_.DeviceID; battery_status = $_.BatteryStatus; estimated_charge_remaining = $_.EstimatedChargeRemaining } })
    }
}

function Assert-R8ReviewBindings {
    param(
        [Parameter(Mandatory = $true)]$Gate,
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][string]$R7DiagnosisSha256,
        [Parameter(Mandatory = $true)][string]$LauncherSha256,
        [Parameter(Mandatory = $true)][string]$RunnerSha256,
        [Parameter(Mandatory = $true)][string]$ContractSha256
    )

    $recoveryReview = $Gate.power_interruption_recovery.independent_review
    $launchReview = $Gate.launch_review
    if ($null -eq $recoveryReview -or [string]::IsNullOrWhiteSpace([string]$recoveryReview.review_id) -or [string]::IsNullOrWhiteSpace([string]$recoveryReview.agent_id) -or $recoveryReview.status -ne 'no_material_finding' -or $recoveryReview.reviewed_run_id -ne $RunId -or $recoveryReview.r7_diagnosis_sha256 -ne $R7DiagnosisSha256 -or $recoveryReview.reviewed_source_sha256.launcher_ps1 -ne $LauncherSha256 -or $recoveryReview.reviewed_source_sha256.runner_sh -ne $RunnerSha256 -or $recoveryReview.reviewed_source_sha256.lean_team_contract_json -ne $ContractSha256 -or -not $recoveryReview.all_prior_findings_closed -or -not $recoveryReview.r8_gate_creation_authorized) {
        throw 'r8-specific interruption-recovery review binding failed'
    }
    if ($null -eq $launchReview -or [string]::IsNullOrWhiteSpace([string]$launchReview.review_id) -or [string]::IsNullOrWhiteSpace([string]$launchReview.agent_id) -or $launchReview.status -ne 'no_material_finding' -or $launchReview.reviewed_run_id -ne $RunId -or $launchReview.r7_diagnosis_sha256 -ne $R7DiagnosisSha256 -or $launchReview.reviewed_source_sha256.launcher_ps1 -ne $LauncherSha256 -or $launchReview.reviewed_source_sha256.runner_sh -ne $RunnerSha256 -or $launchReview.reviewed_source_sha256.lean_team_contract_json -ne $ContractSha256 -or -not $launchReview.all_prior_findings_closed -or -not $launchReview.stable_ac_power_gate_reviewed -or -not $launchReview.r7_interruption_evidence_reviewed -or -not $launchReview.operator_trust_anchor_and_exclusive_lock_reviewed -or -not $launchReview.permanent_create_new_attempt_marker_reviewed -or -not $launchReview.fresh_run_authorized) {
        throw 'r8-specific launch review binding failed'
    }
}

function Assert-R8UserConfirmation {
    param(
        [Parameter(Mandatory = $true)]$Confirmation,
        [Parameter(Mandatory = $true)][string]$RunId,
        [Parameter(Mandatory = $true)][string]$SourceThreadId,
        [Parameter(Mandatory = $true)][string]$RecoveryGateSha256,
        [Parameter(Mandatory = $true)][string]$LauncherSha256,
        [Parameter(Mandatory = $true)][string]$RunnerSha256,
        [Parameter(Mandatory = $true)][string]$ContractSha256
    )

    $messageBytes = [System.Text.Encoding]::UTF8.GetBytes([string]$Confirmation.exact_user_excerpt)
    $messageSha = [System.Security.Cryptography.SHA256]::Create()
    try { $computedMessageSha256 = -join ($messageSha.ComputeHash($messageBytes) | ForEach-Object { $_.ToString('x2') }) } finally { $messageSha.Dispose() }
    if ($Confirmation.schema_version -ne 1 -or $Confirmation.status -ne 'confirmed' -or [string]::IsNullOrWhiteSpace([string]$Confirmation.confirmation_id) -or $Confirmation.run_id -ne $RunId -or $Confirmation.source_thread_id -ne $SourceThreadId -or [string]::IsNullOrWhiteSpace([string]$Confirmation.received_at) -or [string]::IsNullOrWhiteSpace([string]$Confirmation.exact_user_excerpt) -or $Confirmation.user_message_hash_encoding -ne 'utf-8-no-bom-of-json-decoded-exact_user_excerpt' -or [string]$Confirmation.user_message_sha256 -notmatch '^[0-9a-f]{64}$' -or $Confirmation.user_message_sha256 -ne $computedMessageSha256 -or $Confirmation.recovery_gate_sha256 -ne $RecoveryGateSha256 -or $Confirmation.source_sha256.launcher_ps1 -ne $LauncherSha256 -or $Confirmation.source_sha256.runner_sh -ne $RunnerSha256 -or $Confirmation.source_sha256.lean_team_contract_json -ne $ContractSha256 -or -not $Confirmation.user_explicitly_requested_fresh_r8_exactly_once -or -not $Confirmation.exactly_once_launch_authorized -or -not $Confirmation.no_resume_or_reuse -or $Confirmation.confirmation_revoked -ne $false) {
        throw 'Explicit user confirmation artifact does not authorize this exact fresh r8 launch'
    }
}

# A valid user-confirmation artifact is required before the permanent r8 attempt marker can be created.
# Both caller-provided digests are external trust anchors; no gate or confirmation field is read first.
$gateHash = Get-Sha256 $recoveryGate
if ($gateHash -ne $ExpectedRecoveryGateSha256.ToLowerInvariant()) { throw 'Canonical recovery gate does not match the operator-supplied reviewed SHA-256' }
$confirmationHash = Get-Sha256 $userConfirmation
if ($confirmationHash -ne $ExpectedUserConfirmationSha256.ToLowerInvariant()) { throw 'User confirmation artifact does not match the operator-supplied SHA-256' }
$gate = Get-Content -LiteralPath $recoveryGate -Raw | ConvertFrom-Json
$confirmation = Get-Content -LiteralPath $userConfirmation -Raw | ConvertFrom-Json
if ($gate.status -ne 'pass' -or -not $gate.fresh_launch_authorized -or $gate.run_id -ne $runId) { throw 'Recovery gate does not authorize this fresh launch' }
if (-not $gate.explicit_user_launch_confirmation.required -or $gate.explicit_user_launch_confirmation.canonical_path -ne $userConfirmation -or $gate.explicit_user_launch_confirmation.source_thread_id -ne $sourceThreadId -or -not $gate.explicit_user_launch_confirmation.operator_supplied_sha256_required -or -not $gate.explicit_user_launch_confirmation.bind_recovery_gate_and_source_hashes) { throw 'Recovery gate does not require the canonical explicit user confirmation contract' }
$authorizationLauncherHash = Get-Sha256 $PSCommandPath
$authorizationRunnerHash = Get-Sha256 $runner
$authorizationContractHash = Get-Sha256 $contract
Assert-R8UserConfirmation -Confirmation $confirmation -RunId $runId -SourceThreadId $sourceThreadId -RecoveryGateSha256 $gateHash -LauncherSha256 $authorizationLauncherHash -RunnerSha256 $authorizationRunnerHash -ContractSha256 $authorizationContractHash

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$launchLockStream = $null
try { $launchLockStream = [System.IO.File]::Open($launchLock, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None) } catch [System.IO.IOException] { throw 'An r8 launch attempt marker already exists; refusing every later invocation' }

try {
    foreach ($path in @($stdout, $stderr, $lifecycle)) { if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite pilot evidence: $path" } }
    if (Test-Path -LiteralPath $runDirectory) { throw "Refusing to reuse pilot run directory: $runDirectory" }
    if ($gate.failed_predecessor.run_id -ne 'paper-text-v1-pilot-cap128-seed42-r5-20260826' -or -not $gate.failed_predecessor.relaunch_forbidden) { throw 'Recovery gate does not preserve the r5 no-relaunch rule' }
    if ($gate.failed_preflight_predecessor.run_id -ne 'paper-text-v1-pilot-cap128-seed42-r6-20260826' -or -not $gate.failed_preflight_predecessor.relaunch_forbidden) { throw 'Recovery gate does not preserve the r6 no-relaunch rule' }
    if ($gate.interrupted_predecessor.run_id -ne 'paper-text-v1-pilot-cap128-seed42-r7-20260826' -or -not $gate.interrupted_predecessor.relaunch_forbidden) { throw 'Recovery gate does not preserve the r7 no-relaunch rule' }
    foreach ($forbidden in @('paper-text-v1-pilot-cap128-seed42-20260824','paper-text-v1-pilot-cap128-seed42-r2-20260824','paper-text-v1-pilot-cap128-seed42-r3-20260825','paper-text-v1-pilot-cap128-seed42-r4-20260825','paper-text-v1-pilot-cap128-seed42-r5-20260826','paper-text-v1-pilot-cap128-seed42-r6-20260826','paper-text-v1-pilot-cap128-seed42-r7-20260826')) { if (@($gate.resume_forbidden) -notcontains $forbidden) { throw "Recovery gate omits forbidden predecessor: $forbidden" } }

    if ((Get-Sha256 $r7Diagnosis) -ne $gate.interrupted_predecessor.diagnosis_sha256 -or (Get-Sha256 $failedR7PilotStdout) -ne $gate.interrupted_predecessor.pilot_stdout_sha256 -or (Get-Sha256 $failedR7PilotStderr) -ne $gate.interrupted_predecessor.pilot_stderr_sha256 -or (Get-Sha256 $failedR7LauncherStdout) -ne $gate.interrupted_predecessor.launcher_stdout_sha256 -or (Get-Sha256 $failedR7LauncherStderr) -ne $gate.interrupted_predecessor.launcher_stderr_sha256 -or (Get-Sha256 $failedR7Lifecycle) -ne $gate.interrupted_predecessor.lifecycle_sha256 -or (Get-Sha256 $failedR7LaunchLock) -ne $gate.interrupted_predecessor.launch_lock_sha256) { throw 'r7 interruption evidence changed after gate publication' }
    foreach ($emptyLog in @($failedR7PilotStdout, $failedR7PilotStderr, $failedR7LauncherStdout, $failedR7LauncherStderr)) { if ((Get-Item -LiteralPath $emptyLog).Length -ne 0) { throw 'An r7 stdout/stderr log is no longer the recorded empty interruption evidence' } }
    $r7DiagnosisData = Get-Content -LiteralPath $r7Diagnosis -Raw | ConvertFrom-Json
    if ($r7DiagnosisData.status -ne 'confirmed' -or $r7DiagnosisData.attempted_run_id -ne $gate.interrupted_predecessor.run_id -or $r7DiagnosisData.interruption.classification -ne 'orderly_windows_critical_battery_shutdown' -or -not $r7DiagnosisData.attempt_reuse_forbidden) { throw 'r7 interruption diagnosis contract failed' }
    $r7Events = @(Get-Content -LiteralPath $failedR7Lifecycle | ForEach-Object { $_ | ConvertFrom-Json })
    $r7LaunchRequested = @($r7Events | Where-Object { $_.event -eq 'launch_requested' -and $_.run_id -eq $gate.interrupted_predecessor.run_id })
    $r7ProcessStarted = @($r7Events | Where-Object { $_.event -eq 'process_started' -and $_.run_id -eq $gate.interrupted_predecessor.run_id })
    $r7ProcessExited = @($r7Events | Where-Object { $_.event -eq 'process_exited' })
    if ($r7Events.Count -ne 2 -or $r7LaunchRequested.Count -ne 1 -or $r7ProcessStarted.Count -ne 1 -or $r7ProcessExited.Count -ne 0 -or [int]$r7ProcessStarted[0].process_id -ne [int]$gate.interrupted_predecessor.process_id -or $r7LaunchRequested[0].timestamp -ne $gate.interrupted_predecessor.launch_requested_at -or $r7ProcessStarted[0].timestamp -ne $gate.interrupted_predecessor.process_started_at) { throw 'r7 lifecycle is not the recorded strict-scan interruption evidence' }
    if (Test-Path -LiteralPath $forbiddenR7RunDirectory) { throw 'Unauthorized r7 run directory appeared after the no-relaunch decision' }
    if ((Get-Sha256 $r6Diagnosis) -ne $gate.failed_preflight_predecessor.diagnosis_sha256) { throw 'r6 preflight diagnosis changed after gate publication' }
    if ((Get-Sha256 $failedR6LauncherStdout) -ne $gate.failed_preflight_predecessor.launcher_stdout_sha256 -or (Get-Sha256 $failedR6LauncherStderr) -ne $gate.failed_preflight_predecessor.launcher_stderr_sha256 -or (Get-Sha256 $failedR6LaunchLock) -ne $gate.failed_preflight_predecessor.launch_lock_sha256) { throw 'r6 preflight evidence changed after gate publication' }
    if ((Test-Path -LiteralPath $forbiddenR6Lifecycle) -or (Test-Path -LiteralPath $forbiddenR6RunDirectory)) { throw 'Unauthorized r6 evidence appeared after the no-relaunch decision' }
    if ((Get-Sha256 $failedR5Lifecycle) -ne $gate.failed_predecessor.lifecycle_sha256 -or (Get-Sha256 $r5Execution) -ne $gate.failed_predecessor.execution_sha256 -or (Get-Sha256 $diagnosis) -ne $gate.failed_predecessor.diagnosis_sha256 -or (Get-Sha256 $r5Stage2Checkpoint) -ne $gate.failed_predecessor.stage2_checkpoint_sha256) { throw 'r5 evidence changed after gate publication' }
    $r5Exit = Get-Content -LiteralPath $failedR5Lifecycle | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object event -eq 'process_exited' | Select-Object -Last 1
    $execution = Get-Content -LiteralPath $r5Execution -Raw | ConvertFrom-Json
    if (-not $r5Exit -or $r5Exit.exit_code -ne 2 -or $r5Exit.run_id -ne $gate.failed_predecessor.run_id -or $r5Exit.timestamp -ne $gate.failed_predecessor.exit_timestamp -or $execution.status -ne 'failed' -or $execution.failure.fingerprint -ne $gate.failed_predecessor.failure_fingerprint) { throw 'r5 failure evidence changed or is absent' }
    if ((Get-Sha256 $stage3Diagnostic) -ne $gate.gradient_accumulation_recovery.real_data_diagnostic_sha256 -or (Get-Sha256 $testEvidence) -ne $gate.gradient_accumulation_recovery.test_evidence_sha256) { throw 'Gradient-accumulation recovery evidence changed after gate publication' }
    $diagnostic = Get-Content -LiteralPath $stage3Diagnostic -Raw | ConvertFrom-Json; $tests = Get-Content -LiteralPath $testEvidence -Raw | ConvertFrom-Json
    if ($diagnostic.status -ne 'pass' -or -not $diagnostic.not_a_training_run -or $diagnostic.failed_run_id -ne $gate.failed_predecessor.run_id -or $diagnostic.failed_execution.sha256 -ne $gate.failed_predecessor.execution_sha256 -or $diagnostic.strategy.effective_batch -ne 128 -or $diagnostic.strategy.gradient_accumulation_steps -ne 128 -or $diagnostic.strategy.optimizer_iterations_before -ne 0 -or $diagnostic.strategy.optimizer_iterations_after -ne 1 -or -not $diagnostic.train.all_results_finite -or -not $diagnostic.validation.all_results_finite -or -not $diagnostic.model.frozen_non_trainable_weights_unchanged -or $diagnostic.stage2_checkpoint.sha256_before -ne $gate.failed_predecessor.stage2_checkpoint_sha256 -or $diagnostic.stage2_checkpoint.sha256_after -ne $gate.failed_predecessor.stage2_checkpoint_sha256) { throw 'Stage3 diagnostic recovery contract failed' }
    if ($tests.status -ne 'pass' -or $tests.host_full_suite.tests_run -ne 45 -or $tests.host_full_suite.tests_skipped -ne 4 -or $tests.locked_wsl_tf24_focused_suite.tests_run -ne 31 -or $tests.locked_wsl_tf24_focused_suite.tests_skipped -ne 0) { throw 'Required recovery tests are not all recorded as passing' }

    $actualCliHash = Get-Sha256 $cli; $actualTrainerHash = Get-Sha256 $trainer; $actualMetricsHash = Get-Sha256 $metrics; $actualModelsHash = Get-Sha256 $models; $actualSplitsHash = Get-Sha256 $splits; $actualReadmeHash = Get-Sha256 $readme; $actualDiagnosticSourceHash = Get-Sha256 $diagnosticSource; $actualExecutionTestHash = Get-Sha256 $testExecution; $actualTrainerTestHash = Get-Sha256 $testTrainer; $actualScaffoldTestHash = Get-Sha256 $testScaffold; $actualPowerGateSmokeHash = Get-Sha256 $r8PowerGateSmoke; $actualReviewBindingSmokeHash = Get-Sha256 $r8ReviewBindingSmoke; $actualLivePowerGateProbeHash = Get-Sha256 $r8LivePowerGateProbe; $actualUserConfirmationGateSmokeHash = Get-Sha256 $r8UserConfirmationGateSmoke; $actualRunnerHash = Get-Sha256 $runner; $actualLauncherHash = Get-Sha256 $PSCommandPath; $actualContractHash = Get-Sha256 $contract
    $source = $gate.gradient_accumulation_recovery.source_sha256
    if ($actualCliHash -ne $source.cli_py -or $actualTrainerHash -ne $source.trainer_py -or $actualMetricsHash -ne $source.metrics_py -or $actualModelsHash -ne $source.models_py -or $actualSplitsHash -ne $source.splits_py -or $actualReadmeHash -ne $source.readme_md -or $actualDiagnosticSourceHash -ne $source.stage3_stability_smoke_py -or $actualExecutionTestHash -ne $source.test_execution_corrections_py -or $actualTrainerTestHash -ne $source.test_trainer_contract_py -or $actualScaffoldTestHash -ne $source.test_training_scaffold_py) { throw 'Reviewed gradient-accumulation recovery source changed after gate publication' }
    if ((Get-Sha256 $sourceManifest) -ne $gate.source_and_environment.source_manifest_sha256 -or (Get-Sha256 $environmentManifest) -ne $gate.source_and_environment.environment_manifest_sha256 -or (Get-Sha256 $driverRecoveryManifest) -ne $gate.driver_recovery_manifest.sha256 -or (Get-Sha256 $validationLog) -ne $gate.cache_gate.validator_v2_log_sha256) { throw 'Source, environment, driver, or validator evidence changed after gate publication' }
    if ($actualRunnerHash -ne $gate.runner.sha256 -or $actualLauncherHash -ne $gate.launcher.sha256 -or $actualContractHash -ne $gate.contract_gate.contract_sha256) { throw 'Reviewed runner, launcher, or contract changed after gate publication' }
    if ($gate.gradient_accumulation_recovery.independent_review.status -ne 'no_material_finding' -or -not $gate.gradient_accumulation_recovery.independent_review.r6_gate_creation_authorized) { throw 'Historical gradient-accumulation recovery review gate failed' }
    if ((Get-Sha256 $r8RecoveryTestEvidence) -ne $gate.power_interruption_recovery.test_evidence_sha256 -or $actualPowerGateSmokeHash -ne $gate.power_interruption_recovery.source_sha256.r8_power_gate_smoke_ps1 -or $actualReviewBindingSmokeHash -ne $gate.power_interruption_recovery.source_sha256.r8_review_binding_smoke_ps1 -or $actualLivePowerGateProbeHash -ne $gate.power_interruption_recovery.source_sha256.r8_live_power_gate_probe_ps1 -or $actualUserConfirmationGateSmokeHash -ne $gate.power_interruption_recovery.source_sha256.r8_user_confirmation_gate_smoke_ps1) { throw 'r8 interruption-recovery test evidence or smoke source changed after gate publication' }
    $r8Tests = Get-Content -LiteralPath $r8RecoveryTestEvidence -Raw | ConvertFrom-Json
    if ($r8Tests.status -ne 'pass' -or -not $r8Tests.not_a_training_run -or $r8Tests.pilot_launched -ne $false -or $r8Tests.run_id -ne $runId -or $r8Tests.r7_diagnosis_sha256 -ne $gate.interrupted_predecessor.diagnosis_sha256 -or $r8Tests.source_sha256.launcher_ps1 -ne $actualLauncherHash -or $r8Tests.source_sha256.runner_sh -ne $actualRunnerHash -or $r8Tests.source_sha256.lean_team_contract_json -ne $actualContractHash -or $r8Tests.source_sha256.r8_power_gate_smoke_ps1 -ne $actualPowerGateSmokeHash -or $r8Tests.source_sha256.r8_review_binding_smoke_ps1 -ne $actualReviewBindingSmokeHash -or $r8Tests.source_sha256.r8_live_power_gate_probe_ps1 -ne $actualLivePowerGateProbeHash -or $r8Tests.source_sha256.r8_user_confirmation_gate_smoke_ps1 -ne $actualUserConfirmationGateSmokeHash -or $r8Tests.power_gate_smoke.status -ne 'pass' -or $r8Tests.review_binding_smoke.status -ne 'pass' -or $r8Tests.user_confirmation_gate_smoke.status -ne 'pass' -or $r8Tests.powershell_parser.status -ne 'pass' -or $r8Tests.bash_syntax.status -ne 'pass' -or $r8Tests.live_offline_refusal.status -ne 'pass' -or $r8Tests.hidden_host_offline_refusal.status -ne 'pass') { throw 'r8 interruption-recovery test evidence contract failed' }
    Assert-R8ReviewBindings -Gate $gate -RunId $runId -R7DiagnosisSha256 $gate.interrupted_predecessor.diagnosis_sha256 -LauncherSha256 $actualLauncherHash -RunnerSha256 $actualRunnerHash -ContractSha256 $actualContractHash
    $gpu = Get-CimInstance Win32_VideoController | Where-Object Name -match 'NVIDIA' | Select-Object -First 1
    if (-not $gpu -or $gpu.DriverVersion -ne '32.0.16.1047' -or $gpu.Status -ne 'OK') { throw 'NVIDIA 610.47 driver gate failed immediately before launch' }
    $cFreeGiB = (Get-PSDrive C).Free / 1GB; $eFreeGiB = (Get-PSDrive E).Free / 1GB
    if ($cFreeGiB -lt [double]$gate.storage_gate.c_minimum_gib -or $eFreeGiB -lt [double]$gate.storage_gate.e_minimum_gib) { throw 'Free-space gate failed immediately before launch' }
    $events = foreach ($line in Get-Content -LiteralPath $validationLog -ErrorAction Stop) { if (-not [string]::IsNullOrWhiteSpace($line)) { try { $line | ConvertFrom-Json -ErrorAction Stop } catch { continue } } }; $validation = $events | Where-Object { $_.status } | Select-Object -Last 1; $actualManifestHash = Get-Sha256 $cacheManifest
    if (-not $validation -or $validation.status -ne 'valid' -or $validation.cache_manifest_sha256 -ne $actualManifestHash -or $gate.cache_gate.sha256 -ne $actualManifestHash) { throw 'Cache manifest changed after validation/recovery gate' }
    $existingWindows = Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and ($_.CommandLine -match 'run_paper_text_pilot_r[0-9]+\.sh' -or $_.CommandLine -match 'paper_faithful\.training\.cli pilot') }; $existingWsl = @(& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "pgrep -af '[p]aper_faithful.training.cli pilot' || true")
    if ($existingWindows -or $existingWsl) { throw "Another pilot is already running. Windows=$(@($existingWindows.ProcessId) -join ',') WSL=$($existingWsl -join ';')" }
    $powerFacts = Get-StableAcPowerFacts
    Write-LifecycleEvent @{ event = 'launch_requested'; run_id = $runId; failed_predecessor_run_id = $gate.failed_predecessor.run_id; failed_preflight_predecessor_run_id = $gate.failed_preflight_predecessor.run_id; interrupted_predecessor_run_id = $gate.interrupted_predecessor.run_id; recovery_gate_sha256 = $gateHash; user_confirmation_sha256 = $confirmationHash; user_confirmation_id = $confirmation.confirmation_id; diagnosis_sha256 = $gate.failed_predecessor.diagnosis_sha256; preflight_diagnosis_sha256 = $gate.failed_preflight_predecessor.diagnosis_sha256; interruption_diagnosis_sha256 = $gate.interrupted_predecessor.diagnosis_sha256; test_evidence_sha256 = $gate.gradient_accumulation_recovery.test_evidence_sha256; stage3_diagnostic_sha256 = $gate.gradient_accumulation_recovery.real_data_diagnostic_sha256; validated_cache_manifest_sha256 = $actualManifestHash; cli_sha256 = $actualCliHash; trainer_sha256 = $actualTrainerHash; metrics_sha256 = $actualMetricsHash; runner_sha256 = $actualRunnerHash; launcher_sha256 = $actualLauncherHash; contract_sha256 = $actualContractHash; independent_review = $gate.gradient_accumulation_recovery.independent_review.status; launch_review = $gate.launch_review.status; nvidia_driver = '610.47'; c_free_gib = [Math]::Round($cFreeGiB, 3); e_free_gib = [Math]::Round($eFreeGiB, 3); stable_ac_power = $powerFacts }
    $arguments = @('-d', 'Ubuntu', '-e', 'bash', '--noprofile', '--norc', './paper_faithful/training/run_paper_text_pilot_r8.sh'); $pilot = Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe" -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    Write-LifecycleEvent @{ event = 'process_started'; run_id = $runId; process_id = $pilot.Id }; $pilot.WaitForExit(); $scriptExitCode = $pilot.ExitCode
    Write-LifecycleEvent @{ event = 'process_exited'; run_id = $runId; process_id = $pilot.Id; exit_code = $scriptExitCode; stdout_bytes = if (Test-Path -LiteralPath $stdout) { (Get-Item -LiteralPath $stdout).Length } else { $null }; stderr_bytes = if (Test-Path -LiteralPath $stderr) { (Get-Item -LiteralPath $stderr).Length } else { $null }; run_directory_exists = Test-Path -LiteralPath $runDirectory; execution_manifest_exists = Test-Path -LiteralPath (Join-Path $runDirectory 'execution.json') }
} finally { if ($null -ne $launchLockStream) { $launchLockStream.Dispose() } }
exit $scriptExitCode
