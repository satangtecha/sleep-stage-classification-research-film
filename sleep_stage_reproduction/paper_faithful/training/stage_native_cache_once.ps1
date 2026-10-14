param(
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$StageEvidencePath,
    [string]$WslDistribution = 'Ubuntu',
    [string]$NativeStageWsl = '/home/techatat/subject-generalization-plan8-native-cache-v1-20261005',
    [string]$NativeStageWindows = '\\wsl.localhost\Ubuntu\home\techatat\subject-generalization-plan8-native-cache-v1-20261005',
    [string]$StageNamespace = 'subject-generalization-plan8-native-cache-stage-v1-20261005',
    [string]$StageRoot = 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery'
)

$ErrorActionPreference = 'Stop'
$receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
$cacheRoot = [IO.Path]::GetFullPath((Split-Path -Parent ([string]$receipt.cache_manifest_path)))
$nativeStageWsl = $NativeStageWsl
$nativeStageWindows = $NativeStageWindows
$stageNamespace = $StageNamespace
$dispatchPath = Join-Path $stageRoot "$stageNamespace.dispatch.json"
$attemptPath = Join-Path $stageRoot "$stageNamespace.attempt.lock"

function Write-JsonCreateOnly([string]$Path, [object]$Value) {
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $json = $Value | ConvertTo-Json -Depth 20
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
}

foreach ($path in @($StageEvidencePath, $dispatchPath, $attemptPath)) {
    if (Test-Path -LiteralPath $path) {
        throw "native cache stage namespace already exists; refusing reuse: $path"
    }
}
if (Test-Path -LiteralPath $nativeStageWindows) {
    throw "native stage directory already exists; refusing reuse: $nativeStageWindows"
}

$dispatch = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_native_cache_stage_dispatch'
    status = 'started'
    stage_namespace = $stageNamespace
    receipt_path = $ReceiptPath
    receipt_sha256 = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
    cache_manifest_path = [string]$receipt.cache_manifest_path
    cache_manifest_sha256 = [string]$receipt.cache_manifest_sha256
    source_cache_root = $cacheRoot
    native_stage_wsl = $nativeStageWsl
    native_stage_windows = $nativeStageWindows
    selected_chunk_count = @($receipt.chunks).Count
    selected_tensor_bytes = [long](($receipt.chunks | ForEach-Object { [long]$_.tensor_byte_length } | Measure-Object -Sum).Sum)
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    no_retry = $true
    no_resume = $true
    no_reuse = $true
}
Write-JsonCreateOnly $dispatchPath $dispatch
$attemptStream = [IO.File]::Open($attemptPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
$attemptStream.Dispose()

$copiedFiles = 0
$copiedBytes = [long]0
$copyStarted = Get-Date
$status = 'failed'
$failureMessage = $null
try {
    New-Item -ItemType Directory -Force -Path $nativeStageWindows | Out-Null

    $manifestSource = [string]$receipt.cache_manifest_path
    $manifestDestination = Join-Path $nativeStageWindows (Split-Path -Leaf $manifestSource)
    Copy-Item -LiteralPath $manifestSource -Destination $manifestDestination
    $manifestHash = (Get-FileHash -LiteralPath $manifestDestination -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($manifestHash -ne ([string]$receipt.cache_manifest_sha256).ToLowerInvariant()) {
        throw 'staged cache manifest hash differs from receipt'
    }
    $copiedFiles++
    $copiedBytes += [long](Get-Item -LiteralPath $manifestDestination).Length

    $index = 0
    foreach ($chunk in @($receipt.chunks)) {
        $index++
        foreach ($kind in @('tensor', 'sidecar')) {
            $source = [string]$chunk.$kind
            $fullSource = [IO.Path]::GetFullPath($source)
            if (-not $fullSource.StartsWith($cacheRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
                throw "receipt artifact escaped cache root: $source"
            }
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
                throw "receipt artifact is missing: $source"
            }
            $destination = Join-Path $nativeStageWindows (Split-Path -Leaf $source)
            if (Test-Path -LiteralPath $destination) {
                throw "destination artifact collision: $destination"
            }
            Copy-Item -LiteralPath $source -Destination $destination
            $destinationInfo = Get-Item -LiteralPath $destination
            if ($kind -eq 'tensor' -and [long]$destinationInfo.Length -ne [long]$chunk.tensor_byte_length) {
                throw "staged tensor byte length differs: $source"
            }
            $copiedFiles++
            $copiedBytes += [long]$destinationInfo.Length
        }
        if (($index % 100) -eq 0) {
            Write-Output ("copied_chunks={0}/{1} copied_files={2} copied_gib={3:N2}" -f $index, @($receipt.chunks).Count, $copiedFiles, ($copiedBytes / 1GB))
        }
    }
    $status = 'staged'
} catch {
    $failureMessage = $_.Exception.Message
    throw
} finally {
    $finishedAt = Get-Date
    $evidence = [ordered]@{
        schema_version = 1
        artifact_type = 'subject_generalization_native_cache_stage'
        status = $status
        stage_namespace = $stageNamespace
        receipt_path = $ReceiptPath
        receipt_sha256 = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        native_stage_wsl = $nativeStageWsl
        native_stage_windows = $nativeStageWindows
        selected_chunk_count = @($receipt.chunks).Count
        copied_files = $copiedFiles
        copied_bytes = $copiedBytes
        expected_tensor_bytes = [long](($receipt.chunks | ForEach-Object { [long]$_.tensor_byte_length } | Measure-Object -Sum).Sum)
        started_at = $copyStarted.ToUniversalTime().ToString('o')
        finished_at = $finishedAt.ToUniversalTime().ToString('o')
        elapsed_seconds = [math]::Round(($finishedAt - $copyStarted).TotalSeconds, 2)
        failure = $failureMessage
        no_retry = $true
        no_resume = $true
        no_reuse = $true
        integrity = 'manifest_hash_and_tensor_byte_lengths_checked; sidecar_and_tensor_sha256_rechecked_by_locked_loader'
    }
    Write-JsonCreateOnly $StageEvidencePath $evidence
}
if ($status -ne 'staged') {
    throw "native cache stage failed; evidence: $StageEvidencePath"
}
Write-Output (Get-Content -LiteralPath $StageEvidencePath -Raw)
