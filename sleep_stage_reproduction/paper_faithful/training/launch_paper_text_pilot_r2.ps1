$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$cacheManifest = Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
$validationLog = Join-Path $bulkRoot 'runtime\integrity-logs\full-cache-validation-v2.stdout.log'
$logRoot = Join-Path $bulkRoot 'runtime\training-logs'
$runId = 'paper-text-v1-pilot-cap128-seed42-r2-20260824'
$runDirectory = Join-Path (Join-Path $bulkRoot 'runs') $runId
$stdout = Join-Path $logRoot "$runId.stdout.log"
$stderr = Join-Path $logRoot "$runId.stderr.log"
$lifecycle = Join-Path $logRoot "$runId.lifecycle.jsonl"
$runner = Join-Path $PSScriptRoot 'run_paper_text_pilot_r2.sh'

function Write-LifecycleEvent([hashtable]$Payload) {
    $Payload.timestamp = (Get-Date).ToString('o')
    Add-Content -LiteralPath $lifecycle -Value ($Payload | ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
foreach ($path in @($stdout, $stderr, $lifecycle)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite pilot evidence: $path" }
}
if (Test-Path -LiteralPath $runDirectory) { throw "Refusing to reuse pilot run directory: $runDirectory" }

$events = foreach ($line in Get-Content -LiteralPath $validationLog -ErrorAction Stop) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    try { $line | ConvertFrom-Json -ErrorAction Stop } catch { continue }
}
$validation = $events | Where-Object { $_.status } | Select-Object -Last 1
if (-not $validation -or $validation.status -ne 'valid') { throw 'Validator v2 did not publish a valid terminal result' }
$actualManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $cacheManifest).Hash.ToLowerInvariant()
if ($validation.cache_manifest_sha256 -ne $actualManifestHash) { throw 'Cache manifest changed after validator v2' }

$existing = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match [regex]::Escape($runId) -and $_.CommandLine -match 'paper_faithful.training.cli'
}
if ($existing) { throw "Pilot is already running: $(@($existing.ProcessId) -join ',')" }

Write-LifecycleEvent @{
    event = 'launch_requested'
    run_id = $runId
    validated_cache_manifest_sha256 = $actualManifestHash
    cache_loader_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot 'cache_loader.py')).Hash.ToLowerInvariant()
    cli_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot 'cli.py')).Hash.ToLowerInvariant()
    runner_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $runner).Hash.ToLowerInvariant()
}

$arguments = @('-d', 'Ubuntu', '-e', 'bash', '--noprofile', '--norc', './paper_faithful/training/run_paper_text_pilot_r2.sh')
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
