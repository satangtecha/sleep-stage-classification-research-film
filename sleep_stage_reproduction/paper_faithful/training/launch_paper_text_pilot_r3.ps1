$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$cacheManifest = Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
$validationLog = Join-Path $bulkRoot 'runtime\integrity-logs\full-cache-validation-v2.stdout.log'
$recoveryManifest = Join-Path $bulkRoot 'runtime\driver-recovery\driver_recovery_manifest.json'
$postRebootGate = Join-Path $bulkRoot 'runtime\driver-recovery\post-reboot-gate-r3-20260825.json'
$logRoot = Join-Path $bulkRoot 'runtime\training-logs'
$runId = 'paper-text-v1-pilot-cap128-seed42-r3-20260825'
$runDirectory = Join-Path (Join-Path $bulkRoot 'runs') $runId
$stdout = Join-Path $logRoot "$runId.stdout.log"
$stderr = Join-Path $logRoot "$runId.stderr.log"
$lifecycle = Join-Path $logRoot "$runId.lifecycle.jsonl"
$runner = Join-Path $PSScriptRoot 'run_paper_text_pilot_r3.sh'

function Write-LifecycleEvent([hashtable]$Payload) {
    $Payload.timestamp = (Get-Date).ToString('o')
    Add-Content -LiteralPath $lifecycle -Value ($Payload | ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
foreach ($path in @($stdout, $stderr, $lifecycle)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite pilot evidence: $path" }
}
if (Test-Path -LiteralPath $runDirectory) { throw "Refusing to reuse pilot run directory: $runDirectory" }

$recovery = Get-Content -LiteralPath $recoveryManifest -Raw | ConvertFrom-Json
$gate = Get-Content -LiteralPath $postRebootGate -Raw | ConvertFrom-Json
$recoveryHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $recoveryManifest).Hash.ToLowerInvariant()
$gateHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $postRebootGate).Hash.ToLowerInvariant()
$boot = [DateTimeOffset](Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$recoveryTimestamp = [DateTimeOffset]$recovery.timestamp
if ($boot -le $recoveryTimestamp) { throw 'Windows reboot gate is not satisfied' }
if ($gate.status -ne 'pass' -or -not $gate.pilot_relaunch_authorized) { throw 'Post-reboot gate does not authorize pilot relaunch' }
if ($gate.run_id -ne $runId) { throw 'Post-reboot gate is bound to a different run ID' }
if ($gate.recovery_manifest.sha256 -ne $recoveryHash) { throw 'Recovery manifest changed after post-reboot validation' }

$gpu = Get-CimInstance Win32_VideoController | Where-Object Name -match 'NVIDIA' | Select-Object -First 1
if (-not $gpu -or $gpu.DriverVersion -ne '32.0.16.1047' -or $gpu.Status -ne 'OK') {
    throw 'NVIDIA 610.47 driver gate failed immediately before launch'
}

$events = foreach ($line in Get-Content -LiteralPath $validationLog -ErrorAction Stop) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    try { $line | ConvertFrom-Json -ErrorAction Stop } catch { continue }
}
$validation = $events | Where-Object { $_.status } | Select-Object -Last 1
if (-not $validation -or $validation.status -ne 'valid') { throw 'Validator v2 did not publish a valid terminal result' }
$actualManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $cacheManifest).Hash.ToLowerInvariant()
if ($validation.cache_manifest_sha256 -ne $actualManifestHash) { throw 'Cache manifest changed after validator v2' }

$existingWindows = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -and
    ($_.CommandLine -match 'run_paper_text_pilot_r[123]\.sh' -or $_.CommandLine -match 'paper_faithful\.training\.cli pilot')
}
$existingWsl = @(& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "pgrep -af '[p]aper_faithful.training.cli pilot' || true")
if ($existingWindows -or $existingWsl) {
    throw "Another pilot is already running. Windows=$(@($existingWindows.ProcessId) -join ',') WSL=$($existingWsl -join ';')"
}

Write-LifecycleEvent @{
    event = 'launch_requested'
    run_id = $runId
    windows_last_boot = $boot.ToString('o')
    nvidia_driver = '610.47'
    recovery_manifest_sha256 = $recoveryHash
    post_reboot_gate_sha256 = $gateHash
    validated_cache_manifest_sha256 = $actualManifestHash
    cache_loader_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot 'cache_loader.py')).Hash.ToLowerInvariant()
    cli_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot 'cli.py')).Hash.ToLowerInvariant()
    runner_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLowerInvariant()
}

$arguments = @('-d', 'Ubuntu', '-e', 'bash', '--noprofile', '--norc', './paper_faithful/training/run_paper_text_pilot_r3.sh')
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
