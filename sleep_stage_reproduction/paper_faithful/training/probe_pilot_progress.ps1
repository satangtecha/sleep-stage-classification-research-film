param(
    [Parameter(Mandatory = $true)]
    [string]$RunId,
    [string]$Distro = 'Ubuntu',
    [string]$ProjectRoot,
    [string]$CacheManifest = 'E:\blp\sleep_stage_reproduction\sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json',
    [string]$RuntimeRoot = 'E:\blp\sleep_stage_reproduction'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
}

$logRoot = Join-Path $RuntimeRoot 'runtime\training-logs'
$runRoot = Join-Path (Join-Path $RuntimeRoot 'runs') $RunId
$stdoutPath = Join-Path $logRoot "$RunId.stdout.log"
$stderrPath = Join-Path $logRoot "$RunId.stderr.log"
$lifecyclePath = Join-Path $logRoot "$RunId.lifecycle.jsonl"
$executionPath = Join-Path $runRoot 'execution.json'
$isMultiSeed = $RunId -like 'paper-text-v1-multiseed-*'
$childIds = if ($isMultiSeed) { @("$RunId-split42-model42", "$RunId-split43-model43") } else { @() }
$childRuns = @($childIds | ForEach-Object {
    $childRoot = Join-Path (Join-Path $RuntimeRoot 'runs') $_
    $childExecutionPath = Join-Path $childRoot 'execution.json'
    $childExecutionExists = Test-Path -LiteralPath $childExecutionPath
    $childExecution = if ($childExecutionExists) { Get-Content -LiteralPath $childExecutionPath -Raw | ConvertFrom-Json } else { $null }
    [pscustomobject]@{
        run_id = $_
        run_directory = $childRoot
        run_directory_exists = Test-Path -LiteralPath $childRoot
        execution_path = $childExecutionPath
        execution_exists = $childExecutionExists
        execution_status = if ($childExecutionExists) { $childExecution.status } else { $null }
        execution = $childExecution
    }
})

$probe = @(
    & wsl.exe -d $Distro --cd $ProjectRoot -e /bin/sh `
        ./paper_faithful/training/probe_pilot_process.sh $RunId 2>$null
)
$openPath = ($probe | Where-Object { $_ -like 'OPEN=*' } | Select-Object -Last 1) -replace '^OPEN=', ''
$missing = [bool]($probe | Where-Object { $_ -eq 'PILOT_MISSING=1' })

$manifest = Get-Content -LiteralPath $CacheManifest -Raw | ConvertFrom-Json
$chunks = @($manifest.chunks)
$totalChunks = $chunks.Count
$chunkIndex = $null
$recordRange = $null

if (-not [string]::IsNullOrWhiteSpace($openPath)) {
    $leaf = [IO.Path]::GetFileName($openPath)
    $tensorLeaf = $leaf
    if ($leaf.EndsWith('.json')) {
        $tensorLeaf = [IO.Path]::ChangeExtension($leaf, '.npy')
    }
    if ($tensorLeaf.EndsWith('.npy')) {
        for ($index = 0; $index -lt $totalChunks; $index++) {
            if ([IO.Path]::GetFileName([string]$chunks[$index].tensor) -eq $tensorLeaf) {
                $chunkIndex = $index + 1
                break
            }
        }
    }
    elseif ($leaf.EndsWith('.npz')) {
        $recordId = [IO.Path]::GetFileNameWithoutExtension($leaf)
        $first = $null
        $last = $null
        for ($index = 0; $index -lt $totalChunks; $index++) {
            if ([IO.Path]::GetFileName([string]$chunks[$index].tensor).StartsWith("$recordId.")) {
                if ($null -eq $first) {
                    $first = $index + 1
                }
                $last = $index + 1
            }
        }
        $recordRange = [ordered]@{
            record = $recordId
            first = $first
            last = $last
        }
    }
}

$percent = $null
if ($null -ne $chunkIndex) {
    $percent = [math]::Round(100 * $chunkIndex / $totalChunks, 3)
}
elseif ($null -ne $recordRange -and $null -ne $recordRange.first) {
    $percent = [math]::Round(100 * $recordRange.first / $totalChunks, 3)
}

$runExists = Test-Path -LiteralPath $runRoot
$executionExists = Test-Path -LiteralPath $executionPath
$childExecutions = @($childRuns | Where-Object { $_.execution_exists })
$multiSeedExecution = if ($isMultiSeed) {
    $aggregateStatus = if ($childExecutions.Count -eq 0) { 'not_started' } elseif (@($childExecutions | Where-Object { $_.execution_status -eq 'failed' }).Count -gt 0) { 'failed' } elseif ($childExecutions.Count -eq $childIds.Count -and @($childExecutions | Where-Object { $_.execution_status -eq 'completed' }).Count -eq $childIds.Count) { 'completed' } else { 'running' }
    [pscustomobject]@{ mode = 'multi-seed-pilot'; status = $aggregateStatus; children = $childRuns }
} else { $null }
$phase = 'strict_cache_scan'
if ($missing) {
    $phase = 'process_missing'
}
elseif (($isMultiSeed -and $childExecutions.Count -gt 0) -or (!$isMultiSeed -and $executionExists)) {
    $phase = 'training_or_evaluation'
}

$lifecycle = if (Test-Path -LiteralPath $lifecyclePath) {
    @(Get-Content -LiteralPath $lifecyclePath)
}
else {
    @()
}
$launchTimestamp = $null
foreach ($line in $lifecycle) {
    try {
        $event = $line | ConvertFrom-Json -ErrorAction Stop
        if ($event.event -eq 'launch_requested') {
            $launchTimestamp = [DateTimeOffset]::Parse([string]$event.timestamp)
            break
        }
    }
    catch {
        continue
    }
}

$averageChunksPerMinute = $null
$projectedScanCompletion = $null
if ($null -ne $launchTimestamp -and $null -ne $chunkIndex -and $chunkIndex -gt 0) {
    $now = [DateTimeOffset]::Now
    $elapsedMinutes = ($now - $launchTimestamp).TotalMinutes
    if ($elapsedMinutes -gt 0) {
        $averageChunksPerMinute = [math]::Round($chunkIndex / $elapsedMinutes, 3)
        $remainingMinutes = ($totalChunks - $chunkIndex) / $averageChunksPerMinute
        $projectedScanCompletion = $now.AddMinutes($remainingMinutes).ToString('o')
    }
}

[ordered]@{
    timestamp = (Get-Date).ToString('o')
    run_id = $RunId
    phase = $phase
    process_missing = $missing
    probe = $probe
    open_path = $openPath
    chunk = $chunkIndex
    record_range = $recordRange
    total_chunks = $totalChunks
    percent = $percent
    average_chunks_per_minute = $averageChunksPerMinute
    projected_scan_completion = $projectedScanCompletion
    lifecycle = $lifecycle
    stdout_bytes = if (Test-Path -LiteralPath $stdoutPath) { (Get-Item -LiteralPath $stdoutPath).Length } else { $null }
    stderr_bytes = if (Test-Path -LiteralPath $stderrPath) { (Get-Item -LiteralPath $stderrPath).Length } else { $null }
    stdout_tail = if (Test-Path -LiteralPath $stdoutPath) { @(Get-Content -LiteralPath $stdoutPath -Tail 30) } else { @() }
    stderr_tail = if (Test-Path -LiteralPath $stderrPath) { @(Get-Content -LiteralPath $stderrPath -Tail 30) } else { @() }
    run_directory_exists = $runExists
    run_files = if ($runExists) { @(Get-ChildItem -LiteralPath $runRoot -Recurse -File | Select-Object FullName, Length, LastWriteTime) } else { @() }
    execution = if ($isMultiSeed) { $multiSeedExecution } elseif ($executionExists) { Get-Content -LiteralPath $executionPath -Raw | ConvertFrom-Json } else { $null }
    child_runs = $childRuns
    gpu_processes = @(& nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>&1)
} | ConvertTo-Json -Depth 12
