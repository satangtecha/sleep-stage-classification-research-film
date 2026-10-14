param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{64}$')]
    [string]$ExpectedRecoveryGateSha256
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$cacheManifest = Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
$validationLog = Join-Path $bulkRoot 'runtime\integrity-logs\full-cache-validation-v2.stdout.log'
$recoveryManifest = Join-Path $bulkRoot 'runtime\driver-recovery\driver_recovery_manifest.json'
$recoveryGate = Join-Path $bulkRoot 'runtime\driver-recovery\post-recovery-gate-r4-20260825.json'
$logRoot = Join-Path $bulkRoot 'runtime\training-logs'
$runId = 'paper-text-v1-pilot-cap128-seed42-r4-20260825'
$runDirectory = Join-Path (Join-Path $bulkRoot 'runs') $runId
$stdout = Join-Path $logRoot "$runId.stdout.log"
$stderr = Join-Path $logRoot "$runId.stderr.log"
$lifecycle = Join-Path $logRoot "$runId.lifecycle.jsonl"
$runner = Join-Path $PSScriptRoot 'run_paper_text_pilot_r4.sh'
$cli = Join-Path $PSScriptRoot 'cli.py'
$trainer = Join-Path $PSScriptRoot 'trainer.py'
$regressionTest = Join-Path $PSScriptRoot 'tests\test_trainer_contract.py'
$contract = Join-Path $projectRoot 'lean_team_contract.json'
$failedR3Lifecycle = Join-Path $logRoot 'paper-text-v1-pilot-cap128-seed42-r3-20260825.lifecycle.jsonl'

function Write-LifecycleEvent([hashtable]$Payload) {
    $Payload.timestamp = (Get-Date).ToString('o')
    Add-Content -LiteralPath $lifecycle -Value ($Payload | ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
foreach ($path in @($stdout, $stderr, $lifecycle)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite pilot evidence: $path" }
}
if (Test-Path -LiteralPath $runDirectory) { throw "Refusing to reuse pilot run directory: $runDirectory" }

$recoveryHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $recoveryManifest).Hash.ToLowerInvariant()
$gateHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $recoveryGate).Hash.ToLowerInvariant()
if ($gateHash -ne $ExpectedRecoveryGateSha256.ToLowerInvariant()) { throw 'Canonical recovery gate does not match the operator-supplied reviewed SHA-256' }
$recovery = Get-Content -LiteralPath $recoveryManifest -Raw | ConvertFrom-Json
$gate = Get-Content -LiteralPath $recoveryGate -Raw | ConvertFrom-Json
$boot = [DateTimeOffset](Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$recoveryTimestamp = [DateTimeOffset]$recovery.timestamp
if ($boot -le $recoveryTimestamp) { throw 'Windows reboot gate is not satisfied' }
if ($gate.status -ne 'pass' -or -not $gate.fresh_launch_authorized) { throw 'Recovery gate does not authorize a fresh launch' }
if ($gate.run_id -ne $runId) { throw 'Recovery gate is bound to a different run ID' }
if ($gate.failed_predecessor.run_id -ne 'paper-text-v1-pilot-cap128-seed42-r3-20260825' -or -not $gate.failed_predecessor.relaunch_forbidden) { throw 'Recovery gate does not preserve the r3 no-relaunch rule' }
if ($gate.recovery_manifest.sha256 -ne $recoveryHash) { throw 'Recovery manifest changed after recovery validation' }

$r3Exit = Get-Content -LiteralPath $failedR3Lifecycle | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object event -eq 'process_exited' | Select-Object -Last 1
if (-not $r3Exit -or $r3Exit.exit_code -ne 1) { throw 'r3 failure evidence changed or is absent' }

$actualCliHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $cli).Hash.ToLowerInvariant()
$actualTrainerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $trainer).Hash.ToLowerInvariant()
$actualTestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $regressionTest).Hash.ToLowerInvariant()
$actualRunnerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLowerInvariant()
$actualLauncherHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $PSCommandPath).Hash.ToLowerInvariant()
$actualContractHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $contract).Hash.ToLowerInvariant()
if ($actualCliHash -ne $gate.serialization_recovery.cli_sha256 -or $actualTrainerHash -ne $gate.serialization_recovery.trainer_sha256 -or $actualTestHash -ne $gate.serialization_recovery.regression_test_sha256) { throw 'Reviewed serialization recovery source changed after gate publication' }
if ($actualRunnerHash -ne $gate.runner.sha256) { throw 'r4 runner changed after gate publication' }
if ($actualLauncherHash -ne $gate.launcher.sha256) { throw 'r4 launcher changed after gate publication' }
if ($actualContractHash -ne $gate.contract_gate.contract_sha256) { throw 'Lean-team contract changed after gate publication' }
if ($gate.serialization_recovery.independent_review.status -ne 'no_material_finding' -or -not $gate.serialization_recovery.independent_review.fresh_run_authorized) { throw 'Independent review gate failed' }

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
$actualManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $cacheManifest).Hash.ToLowerInvariant()
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
    windows_last_boot = $boot.ToString('o')
    nvidia_driver = '610.47'
    recovery_manifest_sha256 = $recoveryHash
    recovery_gate_sha256 = $gateHash
    validated_cache_manifest_sha256 = $actualManifestHash
    cli_sha256 = $actualCliHash
    trainer_sha256 = $actualTrainerHash
    regression_test_sha256 = $actualTestHash
    runner_sha256 = $actualRunnerHash
    launcher_sha256 = $actualLauncherHash
    contract_sha256 = $actualContractHash
    independent_review = $gate.serialization_recovery.independent_review.status
    c_free_gib = [Math]::Round($cFreeGiB, 3)
    e_free_gib = [Math]::Round($eFreeGiB, 3)
}

$arguments = @('-d', 'Ubuntu', '-e', 'bash', '--noprofile', '--norc', './paper_faithful/training/run_paper_text_pilot_r4.sh')
$pilot = Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe" -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
Write-LifecycleEvent @{ event = 'process_started'; run_id = $runId; process_id = $pilot.Id }

$pilot.WaitForExit()
$exitCode = $pilot.ExitCode
Write-LifecycleEvent @{
    event = 'process_exited'
    run_id = $runId
    process_id = $pilot.Id
    exit_code = $exitCode
    stdout_bytes = if (Test-Path -LiteralPath $stdout) { (Get-Item -LiteralPath $stdout).Length } else { $null }
    stderr_bytes = if (Test-Path -LiteralPath $stderr) { (Get-Item -LiteralPath $stderr).Length } else { $null }
    run_directory_exists = Test-Path -LiteralPath $runDirectory
    execution_manifest_exists = Test-Path -LiteralPath (Join-Path $runDirectory 'execution.json')
}
exit $exitCode
