param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{64}$')]
    [string]$ExpectedRecoveryGateSha256
)

$ErrorActionPreference = 'Stop'
$scriptExitCode = 1

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$cacheManifest = Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
$validationLog = Join-Path $bulkRoot 'runtime\integrity-logs\full-cache-validation-v2.stdout.log'
$driverRecoveryManifest = Join-Path $bulkRoot 'runtime\driver-recovery\driver_recovery_manifest.json'
$recoveryGate = Join-Path $bulkRoot 'runtime\driver-recovery\post-recovery-gate-r6-20260826.json'
$diagnosis = Join-Path $bulkRoot 'runtime\driver-recovery\r5-stage3-failure-diagnosis-20260826.json'
$testEvidence = Join-Path $bulkRoot 'runtime\driver-recovery\r5-gradient-accumulation-test-evidence-20260826.json'
$stage3Diagnostic = Join-Path $bulkRoot 'runtime\diagnostics\paper-text-v1-stage3-accumulation-r5ckpt-20260826-v2.json'
$r5Execution = Join-Path $bulkRoot 'runs\paper-text-v1-pilot-cap128-seed42-r5-20260826\execution.json'
$r5Stage2Checkpoint = Join-Path $bulkRoot 'runs\paper-text-v1-pilot-cap128-seed42-r5-20260826\stage2.weights.h5'
$logRoot = Join-Path $bulkRoot 'runtime\training-logs'
$runId = 'paper-text-v1-pilot-cap128-seed42-r6-20260826'
$runDirectory = Join-Path (Join-Path $bulkRoot 'runs') $runId
$stdout = Join-Path $logRoot "$runId.stdout.log"
$stderr = Join-Path $logRoot "$runId.stderr.log"
$lifecycle = Join-Path $logRoot "$runId.lifecycle.jsonl"
$launchLock = Join-Path $logRoot "$runId.launch.lock"
$runner = Join-Path $PSScriptRoot 'run_paper_text_pilot_r6.sh'
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
$contract = Join-Path $projectRoot 'lean_team_contract.json'
$sourceManifest = Join-Path $projectRoot 'paper_faithful\manifests\source_manifest.json'
$environmentManifest = Join-Path $projectRoot 'paper_faithful\environment\results\wsl_tf24_probe.json'
$failedR5Lifecycle = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r5-20260826.lifecycle.jsonl'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Write-LifecycleEvent([hashtable]$Payload) {
    $Payload.timestamp = (Get-Date).ToString('o')
    Add-Content -LiteralPath $lifecycle -Value ($Payload | ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$launchLockStream = $null
try {
    $launchLockStream = [System.IO.File]::Open($launchLock, [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
} catch [System.IO.IOException] {
    throw 'Exclusive r6 launch lock is already held'
}

try {
    foreach ($path in @($stdout, $stderr, $lifecycle)) {
        if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite pilot evidence: $path" }
    }
    if (Test-Path -LiteralPath $runDirectory) { throw "Refusing to reuse pilot run directory: $runDirectory" }

    # The caller-provided digest is the trust anchor. No gate field is read until
    # the canonical file has matched this independently supplied SHA-256.
    $gateHash = Get-Sha256 $recoveryGate
    if ($gateHash -ne $ExpectedRecoveryGateSha256.ToLowerInvariant()) {
        throw 'Canonical recovery gate does not match the operator-supplied reviewed SHA-256'
    }
    $gate = Get-Content -LiteralPath $recoveryGate -Raw | ConvertFrom-Json
    if ($gate.status -ne 'pass' -or -not $gate.fresh_launch_authorized) { throw 'Recovery gate does not authorize a fresh launch' }
    if ($gate.run_id -ne $runId) { throw 'Recovery gate is bound to a different run ID' }
    if ($gate.failed_predecessor.run_id -ne 'paper-text-v1-pilot-cap128-seed42-r5-20260826' -or -not $gate.failed_predecessor.relaunch_forbidden) {
        throw 'Recovery gate does not preserve the r5 no-relaunch rule'
    }
    foreach ($forbidden in @(
        'paper-text-v1-pilot-cap128-seed42-20260824',
        'paper-text-v1-pilot-cap128-seed42-r2-20260824',
        'paper-text-v1-pilot-cap128-seed42-r3-20260825',
        'paper-text-v1-pilot-cap128-seed42-r4-20260825',
        'paper-text-v1-pilot-cap128-seed42-r5-20260826'
    )) {
        if (@($gate.resume_forbidden) -notcontains $forbidden) { throw "Recovery gate omits forbidden predecessor: $forbidden" }
    }

    if ((Get-Sha256 $failedR5Lifecycle) -ne $gate.failed_predecessor.lifecycle_sha256) { throw 'r5 lifecycle evidence changed after gate publication' }
    $r5Exit = Get-Content -LiteralPath $failedR5Lifecycle | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object event -eq 'process_exited' | Select-Object -Last 1
    if (-not $r5Exit -or $r5Exit.exit_code -ne 2 -or $r5Exit.run_id -ne $gate.failed_predecessor.run_id -or $r5Exit.timestamp -ne $gate.failed_predecessor.exit_timestamp) { throw 'r5 failure evidence changed or is absent' }
    if ((Get-Sha256 $r5Execution) -ne $gate.failed_predecessor.execution_sha256) { throw 'r5 execution evidence changed after gate publication' }
    $execution = Get-Content -LiteralPath $r5Execution -Raw | ConvertFrom-Json
    if ($execution.status -ne 'failed' -or $execution.failure.fingerprint -ne $gate.failed_predecessor.failure_fingerprint) {
        throw 'r5 execution status or failure fingerprint changed'
    }
    if ((Get-Sha256 $diagnosis) -ne $gate.failed_predecessor.diagnosis_sha256) { throw 'r5 diagnosis changed after gate publication' }
    if ((Get-Sha256 $r5Stage2Checkpoint) -ne $gate.failed_predecessor.stage2_checkpoint_sha256) { throw 'r5 Stage2 checkpoint changed after gate publication' }

    if ((Get-Sha256 $stage3Diagnostic) -ne $gate.gradient_accumulation_recovery.real_data_diagnostic_sha256) { throw 'Stage3 diagnostic changed after gate publication' }
    $diagnostic = Get-Content -LiteralPath $stage3Diagnostic -Raw | ConvertFrom-Json
    if ($diagnostic.status -ne 'pass' -or -not $diagnostic.not_a_training_run) { throw 'Stage3 diagnostic status is invalid' }
    if ($diagnostic.failed_run_id -ne $gate.failed_predecessor.run_id -or $diagnostic.failed_execution.sha256 -ne $gate.failed_predecessor.execution_sha256) { throw 'Stage3 diagnostic is not bound to failed r5' }
    if ($diagnostic.strategy.effective_batch -ne 128 -or $diagnostic.strategy.gradient_accumulation_steps -ne 128 -or $diagnostic.strategy.optimizer_iterations_before -ne 0 -or $diagnostic.strategy.optimizer_iterations_after -ne 1) { throw 'Stage3 diagnostic accumulation contract failed' }
    if (-not $diagnostic.train.all_results_finite -or -not $diagnostic.validation.all_results_finite -or -not $diagnostic.model.frozen_non_trainable_weights_unchanged) { throw 'Stage3 diagnostic stability contract failed' }
    if ($diagnostic.stage2_checkpoint.sha256_before -ne $gate.failed_predecessor.stage2_checkpoint_sha256 -or $diagnostic.stage2_checkpoint.sha256_after -ne $gate.failed_predecessor.stage2_checkpoint_sha256) { throw 'Stage3 diagnostic did not preserve the r5 Stage2 checkpoint' }

    if ((Get-Sha256 $testEvidence) -ne $gate.gradient_accumulation_recovery.test_evidence_sha256) { throw 'Gradient-accumulation test evidence changed after gate publication' }
    $tests = Get-Content -LiteralPath $testEvidence -Raw | ConvertFrom-Json
    if ($tests.status -ne 'pass' -or $tests.host_full_suite.tests_run -ne 45 -or $tests.host_full_suite.tests_skipped -ne 4 -or $tests.locked_wsl_tf24_focused_suite.tests_run -ne 31 -or $tests.locked_wsl_tf24_focused_suite.tests_skipped -ne 0) { throw 'Required recovery tests are not all recorded as passing' }

    $actualCliHash = Get-Sha256 $cli
    $actualTrainerHash = Get-Sha256 $trainer
    $actualMetricsHash = Get-Sha256 $metrics
    $actualModelsHash = Get-Sha256 $models
    $actualSplitsHash = Get-Sha256 $splits
    $actualReadmeHash = Get-Sha256 $readme
    $actualDiagnosticSourceHash = Get-Sha256 $diagnosticSource
    $actualExecutionTestHash = Get-Sha256 $testExecution
    $actualTrainerTestHash = Get-Sha256 $testTrainer
    $actualScaffoldTestHash = Get-Sha256 $testScaffold
    $actualRunnerHash = Get-Sha256 $runner
    $actualLauncherHash = Get-Sha256 $PSCommandPath
    $actualContractHash = Get-Sha256 $contract
    $source = $gate.gradient_accumulation_recovery.source_sha256
    if ($actualCliHash -ne $source.cli_py -or $actualTrainerHash -ne $source.trainer_py -or $actualMetricsHash -ne $source.metrics_py -or $actualModelsHash -ne $source.models_py -or $actualSplitsHash -ne $source.splits_py -or $actualReadmeHash -ne $source.readme_md -or $actualDiagnosticSourceHash -ne $source.stage3_stability_smoke_py -or $actualExecutionTestHash -ne $source.test_execution_corrections_py -or $actualTrainerTestHash -ne $source.test_trainer_contract_py -or $actualScaffoldTestHash -ne $source.test_training_scaffold_py) {
        throw 'Reviewed gradient-accumulation recovery source changed after gate publication'
    }
    if ((Get-Sha256 $sourceManifest) -ne $gate.source_and_environment.source_manifest_sha256 -or (Get-Sha256 $environmentManifest) -ne $gate.source_and_environment.environment_manifest_sha256) { throw 'Source or environment manifest changed after gate publication' }
    if ((Get-Sha256 $driverRecoveryManifest) -ne $gate.driver_recovery_manifest.sha256) { throw 'Driver recovery manifest changed after gate publication' }
    if ((Get-Sha256 $validationLog) -ne $gate.cache_gate.validator_v2_log_sha256) { throw 'Validator v2 evidence changed after gate publication' }
    if ($actualRunnerHash -ne $gate.runner.sha256) { throw 'r6 runner changed after gate publication' }
    if ($actualLauncherHash -ne $gate.launcher.sha256) { throw 'r6 launcher changed after gate publication' }
    if ($actualContractHash -ne $gate.contract_gate.contract_sha256) { throw 'Lean-team contract changed after gate publication' }
    if ($gate.gradient_accumulation_recovery.independent_review.status -ne 'no_material_finding' -or -not $gate.gradient_accumulation_recovery.independent_review.r6_gate_creation_authorized) { throw 'Independent recovery review gate failed' }
    if ($gate.launch_review.status -ne 'no_material_finding' -or -not $gate.launch_review.operator_trust_anchor_and_exclusive_lock_reviewed -or -not $gate.launch_review.fresh_run_authorized) { throw 'Independent launch-gate review failed' }

    $gpu = Get-CimInstance Win32_VideoController | Where-Object Name -match 'NVIDIA' | Select-Object -First 1
    if (-not $gpu -or $gpu.DriverVersion -ne '32.0.16.1047' -or $gpu.Status -ne 'OK') { throw 'NVIDIA 610.47 driver gate failed immediately before launch' }
    $cFreeGiB = (Get-PSDrive C).Free / 1GB
    $eFreeGiB = (Get-PSDrive E).Free / 1GB
    if ($cFreeGiB -lt [double]$gate.storage_gate.c_minimum_gib -or $eFreeGiB -lt [double]$gate.storage_gate.e_minimum_gib) { throw 'Free-space gate failed immediately before launch' }

    $events = foreach ($line in Get-Content -LiteralPath $validationLog -ErrorAction Stop) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $line | ConvertFrom-Json -ErrorAction Stop } catch { continue }
    }
    $validation = $events | Where-Object { $_.status } | Select-Object -Last 1
    if (-not $validation -or $validation.status -ne 'valid') { throw 'Validator v2 did not publish a valid terminal result' }
    $actualManifestHash = Get-Sha256 $cacheManifest
    if ($validation.cache_manifest_sha256 -ne $actualManifestHash -or $gate.cache_gate.sha256 -ne $actualManifestHash) { throw 'Cache manifest changed after validation/recovery gate' }

    $existingWindows = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and $_.CommandLine -and
        ($_.CommandLine -match 'run_paper_text_pilot_r[0-9]+\.sh' -or $_.CommandLine -match 'paper_faithful\.training\.cli pilot')
    }
    $existingWsl = @(& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "pgrep -af '[p]aper_faithful.training.cli pilot' || true")
    if ($existingWindows -or $existingWsl) { throw "Another pilot is already running. Windows=$(@($existingWindows.ProcessId) -join ',') WSL=$($existingWsl -join ';')" }

    Write-LifecycleEvent @{
        event = 'launch_requested'
        run_id = $runId
        failed_predecessor_run_id = $gate.failed_predecessor.run_id
        recovery_gate_sha256 = $gateHash
        diagnosis_sha256 = $gate.failed_predecessor.diagnosis_sha256
        test_evidence_sha256 = $gate.gradient_accumulation_recovery.test_evidence_sha256
        stage3_diagnostic_sha256 = $gate.gradient_accumulation_recovery.real_data_diagnostic_sha256
        validated_cache_manifest_sha256 = $actualManifestHash
        cli_sha256 = $actualCliHash
        trainer_sha256 = $actualTrainerHash
        metrics_sha256 = $actualMetricsHash
        runner_sha256 = $actualRunnerHash
        launcher_sha256 = $actualLauncherHash
        contract_sha256 = $actualContractHash
        independent_review = $gate.gradient_accumulation_recovery.independent_review.status
        launch_review = $gate.launch_review.status
        nvidia_driver = '610.47'
        c_free_gib = [Math]::Round($cFreeGiB, 3)
        e_free_gib = [Math]::Round($eFreeGiB, 3)
    }

    $arguments = @('-d', 'Ubuntu', '-e', 'bash', '--noprofile', '--norc', './paper_faithful/training/run_paper_text_pilot_r6.sh')
    $pilot = Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe" -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    Write-LifecycleEvent @{ event = 'process_started'; run_id = $runId; process_id = $pilot.Id }

    $pilot.WaitForExit()
    $scriptExitCode = $pilot.ExitCode
    Write-LifecycleEvent @{
        event = 'process_exited'
        run_id = $runId
        process_id = $pilot.Id
        exit_code = $scriptExitCode
        stdout_bytes = if (Test-Path -LiteralPath $stdout) { (Get-Item -LiteralPath $stdout).Length } else { $null }
        stderr_bytes = if (Test-Path -LiteralPath $stderr) { (Get-Item -LiteralPath $stderr).Length } else { $null }
        run_directory_exists = Test-Path -LiteralPath $runDirectory
        execution_manifest_exists = Test-Path -LiteralPath (Join-Path $runDirectory 'execution.json')
    }
} finally {
    if ($null -ne $launchLockStream) { $launchLockStream.Dispose() }
}
exit $scriptExitCode
