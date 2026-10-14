param(
    [Parameter(Mandatory = $true)]
    [int]$ValidatorProcessId,
    [Parameter(Mandatory = $true)]
    [string]$ValidationLog
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$cacheManifest = 'E:\blp\sleep_stage_reproduction\sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
$logRoot = 'E:\blp\sleep_stage_reproduction\runtime\training-logs'
$runId = 'paper-text-v1-pilot-cap128-seed42-20260824'

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

$validator = Get-Process -Id $ValidatorProcessId -ErrorAction SilentlyContinue
if ($validator) {
    Wait-Process -Id $ValidatorProcessId
}

$events = foreach ($line in Get-Content -LiteralPath $ValidationLog -ErrorAction Stop) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    try { $line | ConvertFrom-Json -ErrorAction Stop } catch { continue }
}
$result = $events | Where-Object { $_.status } | Select-Object -Last 1
if (-not $result -or $result.status -ne 'valid') {
    [pscustomobject]@{ status = 'refused'; reason = 'validator_v2_did_not_publish_valid' } | ConvertTo-Json -Compress
    exit 2
}

$actualManifestHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $cacheManifest).Hash.ToLowerInvariant()
if ($result.cache_manifest_sha256 -ne $actualManifestHash) {
    [pscustomobject]@{ status = 'refused'; reason = 'cache_manifest_hash_changed_after_validation' } | ConvertTo-Json -Compress
    exit 2
}

$existing = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match [regex]::Escape($runId) -and
    $_.CommandLine -match 'paper_faithful.training.cli'
}
if ($existing) {
    [pscustomobject]@{ status = 'refused'; reason = 'pilot_already_running'; process_ids = @($existing.ProcessId) } | ConvertTo-Json -Compress
    exit 2
}

$stdout = Join-Path $logRoot "$runId.stdout.log"
$stderr = Join-Path $logRoot "$runId.stderr.log"
$arguments = @('-d', 'Ubuntu', '-e', 'bash', '-lc', './paper_faithful/training/run_paper_text_pilot.sh')
$pilot = Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe" -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru

[pscustomobject]@{
    status = 'launched'
    run_id = $runId
    process_id = $pilot.Id
    validated_cache_manifest_sha256 = $actualManifestHash
    stdout = $stdout
    stderr = $stderr
} | ConvertTo-Json -Compress
