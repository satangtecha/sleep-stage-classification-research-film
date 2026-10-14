param(
    [string]$HelperPath = (Join-Path $PSScriptRoot '..\r13_exactly_once_helpers.ps1')
)

$ErrorActionPreference = 'Stop'
$helper = (Resolve-Path -LiteralPath $HelperPath).Path
. $helper
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("r13-exactly-once-" + [Guid]::NewGuid().ToString('N'))
$marker = Join-Path $testRoot 'dispatch.lock'
$lifecycle = Join-Path $testRoot 'dispatch.lifecycle.jsonl'
$orphanMarker = Join-Path $testRoot 'orphan.lock'
$orphanLifecycle = Join-Path $testRoot 'orphan.lifecycle.jsonl'
$stream = $null
$prefix = 'paper-text-v1-multiseed-cap128-r13-20260830'
$taskName = 'SleepStagePaper-r13-COM-00000000000000000000000000000000'
$gateSha = 'a' * 64
$confirmationSha = 'b' * 64

try {
    [IO.Directory]::CreateDirectory($testRoot) | Out-Null
    Assert-R13MarkerAvailable $marker 'dispatch'
    $stream = Open-R13PermanentMarker $marker 'dispatch'

    $secondCode = $null
    try { $second = Open-R13PermanentMarker $marker 'dispatch'; $second.Dispose() }
    catch { $secondCode = Get-R13FailureExitCode $_.Exception }
    if ($secondCode -ne 91) { throw 'Concurrent/permanent marker collision did not map to exit 91' }
    if ((Get-R13FailureExitCode (New-Object InvalidOperationException('ordinary failure'))) -ne 92) { throw 'Ordinary failure did not map to exit 92' }

    $mismatch = [ordered]@{event='dispatch_created';run_id_prefix=$prefix;task_name=$taskName;canonical_gate_sha256=('c'*64);user_confirmation_sha256=$confirmationSha;timestamp=(Get-Date).ToString('o')} | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($lifecycle, $mismatch + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $mismatchRefused = $false
    try { Assert-R13BoundDispatchRecord $marker $lifecycle $prefix $taskName $gateSha $confirmationSha | Out-Null }
    catch { $mismatchRefused = $true }
    if (-not $mismatchRefused) { throw 'Mismatched dispatch record was accepted' }

    $exact = [ordered]@{event='dispatch_created';run_id_prefix=$prefix;task_name=$taskName;canonical_gate_sha256=$gateSha;user_confirmation_sha256=$confirmationSha;timestamp=(Get-Date).ToString('o')} | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($lifecycle, $exact + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $bound = Assert-R13BoundDispatchRecord $marker $lifecycle $prefix $taskName $gateSha $confirmationSha
    if ($bound.task_name -ne $taskName) { throw 'Exact dispatch record result changed' }
    $lifecycleRaceCode = $null
    try { Assert-R13OwnedLifecycleAvailable $lifecycle $marker 'dispatch' }
    catch { $lifecycleRaceCode = Get-R13FailureExitCode $_.Exception }
    if ($lifecycleRaceCode -ne 91) { throw 'Marker-plus-lifecycle race did not map to exit 91' }
    [IO.File]::WriteAllText($orphanLifecycle, $exact + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $orphanLifecycleCode = $null
    try { Assert-R13OwnedLifecycleAvailable $orphanLifecycle $orphanMarker 'dispatch' }
    catch { $orphanLifecycleCode = Get-R13FailureExitCode $_.Exception }
    if ($orphanLifecycleCode -ne 92) { throw 'Lifecycle-without-marker inconsistency did not map to exit 92' }

    [IO.File]::AppendAllText($lifecycle, $exact + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $duplicateRefused = $false
    try { Assert-R13BoundDispatchRecord $marker $lifecycle $prefix $taskName $gateSha $confirmationSha | Out-Null }
    catch { $duplicateRefused = $true }
    if (-not $duplicateRefused) { throw 'Duplicated dispatch record was accepted' }

    [IO.File]::WriteAllText($lifecycle, $exact + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
    $stream.Dispose(); $stream = $null
    $unheldRefused = $false
    try { Assert-R13BoundDispatchRecord $marker $lifecycle $prefix $taskName $gateSha $confirmationSha | Out-Null }
    catch { $unheldRefused = $true }
    if (-not $unheldRefused) { throw 'Unlocked dispatch marker was accepted' }

    [ordered]@{
        status = 'pass'; pilot_launched = $false; production_namespace_touched = $false
        second_marker_exit_code = 91; marker_plus_lifecycle_race_exit_code = 91; lifecycle_without_marker_exit_code = 92; ordinary_failure_exit_code = 92
        mismatched_dispatch_refused = $true; duplicated_dispatch_refused = $true; unlocked_dispatch_refused = $true
        exact_bound_dispatch_accepted_while_exclusively_held = $true
    } | ConvertTo-Json -Compress
}
finally {
    if ($null -ne $stream) { $stream.Dispose() }
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = [IO.Path]::GetFullPath($testRoot)
        $temp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $resolved.StartsWith($temp, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path -Leaf $resolved) -notmatch '^r13-exactly-once-[0-9a-f]{32}$') { throw 'Refusing unsafe test cleanup' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
