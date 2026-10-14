$ErrorActionPreference = 'Stop'

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -ne $Expected) { throw "$Message (actual=$Actual expected=$Expected)" }
}

function Value-After([object[]]$Command, [string]$Flag) {
    $index = [Array]::IndexOf($Command, $Flag)
    if ($index -lt 0 -or $index + 1 -ge $Command.Count) { throw "missing command flag or value: $Flag" }
    return [string]$Command[$index + 1]
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testRoot = [IO.Path]::GetFullPath((Join-Path $tempBase ("sleep-stage-plan16-supervisor-v2-seed-" + [Guid]::NewGuid().ToString('N'))))
if (-not $testRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) { throw "unsafe test root: $testRoot" }

try {
    New-Item -ItemType Directory -Path $testRoot -Force:$false | Out-Null
    $result = & (Join-Path $PSScriptRoot '..\native_cache_subject_supervisor_v2.ps1') `
        -RunPrefix 'plan16-supervisor-v2-seed-evidence-test' `
        -WslProjectRoot '/mnt/c/test' `
        -WslPythonSourceRoot '/mnt/c/test/snapshot' `
        -PythonSourceSnapshotWindows $testRoot `
        -ApprovedSourceTreeSha256 ('a' * 64) `
        -ApprovedSourceTreeFileCount 1 `
        -WslBulkRoot '/mnt/e/test' `
        -WslCacheManifest '/mnt/e/test/cache-manifest.json' `
        -WslSourceManifest '/mnt/c/test/source-manifest.json' `
        -WslEnvironmentManifest '/mnt/c/test/environment.json' `
        -WslRuntimeRoot '/mnt/e/test/runtime' `
        -WslProtocolOutput '/mnt/e/test/protocol.json' `
        -WslResourceEvidence '/mnt/e/test/resource.json' `
        -ApprovedResourceEvidenceSha256 ('b' * 64) `
        -WslReceipt '/mnt/e/test/receipt.json' `
        -NativeStageWsl '/home/test/native-stage' `
        -CacheMountTargetWsl '/mnt/e/test/cache-target' `
        -ApprovedProtocolSha256 ('c' * 64) `
        -ResourceProfile 'QUALITY_BALANCED_CAP64_E12_TEST' `
        -LauncherRoot $testRoot `
        -Cap 64 `
        -Epochs 12 `
        -SelectionSeed 43 `
        -ModelSeed 43 `
        -CommandEvidenceOnly

    $summary = $result | ConvertFrom-Json
    Assert-Equal $summary.status 'validated_no_execution' 'unexpected summary status'
    $evidence = Get-Content -LiteralPath (Join-Path $testRoot 'command-evidence.json') -Raw | ConvertFrom-Json
    Assert-Equal $evidence.selection_seed 43 'evidence did not record selection seed'
    Assert-Equal $evidence.model_seed 43 'evidence did not record model seed'
    Assert-Equal (Value-After $evidence.command '--selection-seed') '43' 'selection seed was not forwarded'
    Assert-Equal (Value-After $evidence.command '--model-seed') '43' 'model seed was not forwarded'
    Assert-Equal $evidence.no_training_started $true 'command evidence started training'
    Assert-Equal $evidence.no_mount_started $true 'command evidence started a mount'
    [pscustomobject]@{
        status = 'pass'
        selection_seed = $evidence.selection_seed
        model_seed = $evidence.model_seed
        no_training_started = $evidence.no_training_started
        no_mount_started = $evidence.no_mount_started
    } | ConvertTo-Json -Compress
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = [IO.Path]::GetFullPath($testRoot)
        if (-not $resolved.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) { throw "unsafe cleanup: $resolved" }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
