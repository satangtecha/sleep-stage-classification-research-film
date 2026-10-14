param(
    [Parameter(Mandatory = $true)][string]$RunPrefix,
    [Parameter(Mandatory = $true)][string]$WslProjectRoot,
    [Parameter(Mandatory = $true)][string]$WslBulkRoot,
    [Parameter(Mandatory = $true)][string]$WslCacheManifest,
    [Parameter(Mandatory = $true)][string]$WslSourceManifest,
    [Parameter(Mandatory = $true)][string]$WslEnvironmentManifest,
    [Parameter(Mandatory = $true)][string]$WslRuntimeRoot,
    [Parameter(Mandatory = $true)][string]$WslProtocolOutput,
    [Parameter(Mandatory = $true)][string]$WslResourceEvidence,
    [Parameter(Mandatory = $true)][string]$WslReceipt,
    [Parameter(Mandatory = $true)][string]$ApprovedProtocolSha256,
    [Parameter(Mandatory = $true)][string]$ResourceProfile,
    [string]$WslDistribution = 'Ubuntu',
    [string]$BulkRoot = 'E:\blp\sleep_stage_reproduction'
)

$ErrorActionPreference = 'Stop'
$launcherId = "subject-generalization-plan7-detached-$RunPrefix"
$launcherRoot = Join-Path (Join-Path $BulkRoot 'runtime\driver-recovery') $launcherId
$runRuntimeWindows = Join-Path (Join-Path $BulkRoot 'runtime') $RunPrefix
$runChildGlob = Join-Path (Join-Path $BulkRoot 'runs') "$RunPrefix*"

if (Test-Path -LiteralPath $launcherRoot) {
    throw "detached launcher namespace already exists; refusing reuse: $launcherRoot"
}
if (Test-Path -LiteralPath $runRuntimeWindows) {
    throw "run runtime namespace already exists; refusing reuse: $runRuntimeWindows"
}
if (@(Get-ChildItem -LiteralPath (Split-Path -Parent $runChildGlob) -Directory -Filter "$RunPrefix*" -ErrorAction SilentlyContinue).Count -gt 0) {
    throw "run child namespace already exists; refusing reuse: $runChildGlob"
}
if ($ApprovedProtocolSha256 -notmatch '^[0-9a-fA-F]{64}$') {
    throw 'approved protocol SHA-256 must be 64 hexadecimal characters'
}

New-Item -ItemType Directory -Path $launcherRoot -Force:$false | Out-Null
$dispatchLock = Join-Path $launcherRoot "$RunPrefix.dispatch.lock"
$attemptLock = Join-Path $launcherRoot "$RunPrefix.attempt.lock"
$dispatchStream = [IO.File]::Open($dispatchLock, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
$dispatchStream.Dispose()
$attemptStream = [IO.File]::Open($attemptLock, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
$attemptStream.Dispose()

function Write-JsonCreateOnly([string]$Path, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 12
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
}

$stdoutPath = Join-Path $launcherRoot 'wsl.stdout.log'
$stderrPath = Join-Path $launcherRoot 'wsl.stderr.log'
$dispatch = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_detached_dispatch'
    status = 'dispatched'
    run_prefix = $RunPrefix
    resource_profile = $ResourceProfile
    project_root = $WslProjectRoot
    bulk_root = $WslBulkRoot
    runtime_root = $WslRuntimeRoot
    protocol_output = $WslProtocolOutput
    resource_evidence = $WslResourceEvidence
    cache_validation_receipt = $WslReceipt
    approved_protocol_sha256 = $ApprovedProtocolSha256.ToLowerInvariant()
    distribution = $WslDistribution
    host_pid = $null
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    stdout_path = $stdoutPath
    stderr_path = $stderrPath
}
Write-JsonCreateOnly (Join-Path $launcherRoot 'dispatch.json') $dispatch

$python = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
$arguments = @(
    '--distribution', $WslDistribution, '--cd', $WslProjectRoot, '--', $python,
    '-m', 'paper_faithful.training.subject_generalization_runner',
    '--cache-manifest', $WslCacheManifest,
    '--source-manifest', $WslSourceManifest,
    '--environment-manifest', $WslEnvironmentManifest,
    '--bulk-root', $WslBulkRoot,
    '--runtime-root', $WslRuntimeRoot,
    '--run-prefix', $RunPrefix,
    '--selection-seed', '42',
    '--subject-count', '6',
    '--model-seed', '42',
    '--cap', '32',
    '--resource-profile', $ResourceProfile,
    '--epochs', '6',
    '--protocol-output', $WslProtocolOutput,
    '--resource-evidence', $WslResourceEvidence,
    '--approved-protocol-sha256', $ApprovedProtocolSha256.ToLowerInvariant(),
    '--cache-validation-receipt', $WslReceipt
)

try {
    $process = Start-Process -FilePath 'wsl.exe' -ArgumentList $arguments -WorkingDirectory (Join-Path $env:SystemRoot 'System32') -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
} catch {
    $failure = [ordered]@{
        schema_version = 1
        artifact_type = 'subject_generalization_detached_dispatch'
        status = 'launch_failed'
        run_prefix = $RunPrefix
        error = $_.Exception.Message
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
    }
    Write-JsonCreateOnly (Join-Path $launcherRoot 'launch-failure.json') $failure
    throw
}

$processEvidence = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_detached_process'
    status = 'started'
    run_prefix = $RunPrefix
    host_pid = $process.Id
    command = @('wsl.exe') + $arguments
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    detached = $true
    terminal_independent = $true
    stdout_path = $stdoutPath
    stderr_path = $stderrPath
}
Write-JsonCreateOnly (Join-Path $launcherRoot 'process.json') $processEvidence
Write-Output (([ordered]@{status='started';run_prefix=$RunPrefix;host_pid=$process.Id;launcher_root=$launcherRoot;stdout=$stdoutPath;stderr=$stderrPath} | ConvertTo-Json -Compress))
