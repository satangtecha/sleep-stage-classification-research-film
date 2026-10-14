param(
    [Parameter(Mandatory = $true)][string]$RunPrefix,
    [Parameter(Mandatory = $true)][string]$LauncherRoot,
    [Parameter(Mandatory = $true)][string]$BulkRoot,
    [Parameter(Mandatory = $true)][long]$ReadBytesBefore,
    [Parameter(Mandatory = $true)][long]$ReadBytesAfter,
    [Parameter(Mandatory = $true)][string]$ObservedState,
    [Parameter(Mandatory = $true)][string]$ObservedWchan,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$runtime = Join-Path (Join-Path $BulkRoot 'runtime') $RunPrefix
$children = @(Get-ChildItem -LiteralPath (Join-Path $BulkRoot 'runs') -Directory -Filter "$RunPrefix*" -ErrorAction SilentlyContinue)
$evidence = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_plan7_terminal_blocker'
    status = 'terminal_blocker'
    run_prefix = $RunPrefix
    phase = 'pre_runtime_cache_load'
    reason = 'WSL_DrvFS_9p_read_stall'
    observation = [ordered]@{
        read_bytes_before = $ReadBytesBefore
        read_bytes_after = $ReadBytesAfter
        read_bytes_delta = ($ReadBytesAfter - $ReadBytesBefore)
        process_state = $ObservedState
        wait_channel = $ObservedWchan
        runtime_created = (Test-Path -LiteralPath $runtime)
        child_namespaces_created = ($children.Count -gt 0)
        training_started = $false
        gpu_fit_started = $false
        process_terminated_after_observation = $true
    }
    launcher_root = $LauncherRoot
    dispatch_evidence = Join-Path $LauncherRoot 'dispatch.json'
    process_evidence = Join-Path $LauncherRoot 'process.json'
    no_retry = $true
    no_resume = $true
    no_reuse = $true
    recorded_at = (Get-Date).ToUniversalTime().ToString('o')
}
$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$bytes = [Text.UTF8Encoding]::new($false).GetBytes(($evidence | ConvertTo-Json -Depth 12) + "`n")
$stream = [IO.File]::Open($OutputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
$evidence | ConvertTo-Json -Depth 12
