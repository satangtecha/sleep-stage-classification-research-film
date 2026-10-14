$ErrorActionPreference = 'Stop'

$receiptPath = 'E:\blp\sleep_stage_reproduction\runtime\integrity-receipts\compact-selection-plan4-low-compute-metadata-20261005.json'
$manifestPath = 'E:\blp\sleep_stage_reproduction\sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
$cacheRoot = 'E:\blp\sleep_stage_reproduction\sst_cache\paper_faithful_v3_full_20260820'
$evidencePath = 'E:\blp\sleep_stage_reproduction\runtime\reviews\plan8-cache-transport-canary-v3-20261005.json'
$oneChunkReceiptPath = 'E:\blp\sleep_stage_reproduction\runtime\reviews\plan8-one-chunk-receipt-v3-20261005.json'
$nativeStageWsl = '/home/techatat/plan8-cache-transport-canary-v3-20261005'
$nativeStageWindows = '\\wsl.localhost\Ubuntu\home\techatat\plan8-cache-transport-canary-v3-20261005'
$mountTargetWsl = '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820'
$wslProject = '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction'
$lockedPython = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'

foreach ($path in @($evidencePath, $oneChunkReceiptPath)) {
    if (Test-Path -LiteralPath $path) {
        throw "Canary evidence already exists; refusing reuse: $path"
    }
}

$receipt = Get-Content -Raw $receiptPath | ConvertFrom-Json
$chunk = $receipt.chunks[0]
$metadata = $receipt.selected_chunk_metadata[0]
$sidecarPayload = $metadata.sidecar_payload
$epoch = [int]$sidecarPayload.local_epoch_start
$requiredKey = '{0}/{1}/{2}' -f $sidecarPayload.subject_id, $sidecarPayload.record_id, $epoch.ToString('D8')
$selectionHashBytes = [Text.Encoding]::UTF8.GetBytes($requiredKey + "`n")
$sha = [Security.Cryptography.SHA256]::Create()
$selectionHash = ([BitConverter]::ToString($sha.ComputeHash($selectionHashBytes))).Replace('-', '').ToLowerInvariant()

$oneReceipt = $receipt | ConvertTo-Json -Depth 30 | ConvertFrom-Json
$oneReceipt.chunks = @($chunk)
$oneReceipt.selected_chunks = @($receipt.selected_chunks[0])
$oneReceipt.selected_chunk_metadata = @($metadata)
$oneReceipt.member_count = 1
$oneReceipt.selection_members_sha256 = $selectionHash
$oneReceiptJson = $oneReceipt | ConvertTo-Json -Depth 30
$receiptStream = [IO.File]::Open($oneChunkReceiptPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $receiptBytes = [Text.Encoding]::UTF8.GetBytes($oneReceiptJson + "`n")
    $receiptStream.Write($receiptBytes, 0, $receiptBytes.Length)
    $receiptStream.Flush($true)
} finally {
    $receiptStream.Dispose()
}

$nativeCreated = $false
$mounted = $false
$mountOutput = ''
$pythonOutput = ''
$pythonExitCode = $null
$status = 'fail'
try {
    New-Item -ItemType Directory -Force -Path $nativeStageWindows | Out-Null
    $nativeCreated = $true

    $sourceManifestHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $sourceTensor = [string]$chunk.tensor
    $sourceSidecar = [string]$chunk.sidecar
    $destinationManifest = Join-Path $nativeStageWindows (Split-Path -Leaf $manifestPath)
    $destinationTensor = Join-Path $nativeStageWindows (Split-Path -Leaf $sourceTensor)
    $destinationSidecar = Join-Path $nativeStageWindows (Split-Path -Leaf $sourceSidecar)
    Copy-Item -LiteralPath $manifestPath -Destination $destinationManifest -Force
    Copy-Item -LiteralPath $sourceTensor -Destination $destinationTensor -Force
    Copy-Item -LiteralPath $sourceSidecar -Destination $destinationSidecar -Force

    $copyChecks = @(
        [ordered]@{name='manifest'; source=$manifestPath; destination=$destinationManifest; expected=$sourceManifestHash},
        [ordered]@{name='tensor'; source=$sourceTensor; destination=$destinationTensor; expected=([string]$chunk.tensor_sha256).ToLowerInvariant()},
        [ordered]@{name='sidecar'; source=$sourceSidecar; destination=$destinationSidecar; expected=([string]$chunk.sidecar_sha256).ToLowerInvariant()}
    ) | ForEach-Object {
        $actual = (Get-FileHash -LiteralPath $_.destination -Algorithm SHA256).Hash.ToLowerInvariant()
        [ordered]@{name=$_.name; bytes=(Get-Item -LiteralPath $_.destination).Length; expected_hash=$_.expected; actual_hash=$actual; hash_match=($actual -eq $_.expected)}
    }
    if (@($copyChecks | Where-Object { -not $_.hash_match }).Count -ne 0) {
        throw 'native cache copy hash check failed'
    }

    $mountCheck = & wsl.exe -d Ubuntu -- mountpoint -q $mountTargetWsl 2>&1
    if ($LASTEXITCODE -eq 0) {
        throw "cache mount target is already mounted: $mountTargetWsl"
    }
    & wsl.exe -d Ubuntu -u root -- mount --bind $nativeStageWsl $mountTargetWsl 2>&1 | ForEach-Object { $mountOutput += "$_`n" }
    if ($LASTEXITCODE -ne 0) {
        throw "bind mount failed: $mountOutput"
    }
    $mounted = $true
    $findmnt = & wsl.exe -d Ubuntu -u root -- findmnt -T $mountTargetWsl -o TARGET,SOURCE,FSTYPE,OPTIONS 2>&1
    $mountOutput += (($findmnt | Out-String).Trim() + "`n")
    if ($LASTEXITCODE -ne 0 -or $mountOutput -notmatch 'ext4') {
        throw "native mount verification failed: $mountOutput"
    }

    $pythonCode = @'
import json
from paper_faithful.training.cache_loader import load_canonical_cache

manifest = "/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json"
receipt = "/mnt/e/blp/sleep_stage_reproduction/runtime/reviews/plan8-one-chunk-receipt-v3-20261005.json"
required = "__REQUIRED_KEY__"
cache = load_canonical_cache(manifest, validated_receipt=receipt, required_members={required})
keys = {member.key for member in cache.members}
if required not in keys:
    raise RuntimeError("required member missing after native transport load")
print(json.dumps({"status": "loaded", "member_count": len(keys), "required_member": required, "manifest_sha256": cache.cache_hash}, sort_keys=True))
'@.Replace('__REQUIRED_KEY__', $requiredKey)
    $pythonPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pythonCode))
    $pythonExec = "import base64; exec(base64.b64decode('$pythonPayload'))"
    $pythonResult = & wsl.exe --distribution Ubuntu --cd $wslProject -- $lockedPython -c $pythonExec 2>&1
    $pythonExitCode = $LASTEXITCODE
    $pythonOutput = ($pythonResult | Out-String).Trim()
    if ($pythonExitCode -ne 0) {
        throw "native transport loader canary failed: $pythonOutput"
    }
    $status = 'pass'
} finally {
    if ($mounted) {
        & wsl.exe -d Ubuntu -u root -- umount $mountTargetWsl 2>&1 | Out-Null
    }
    if ($nativeCreated) {
        & wsl.exe -d Ubuntu -u root -- rm -rf $nativeStageWsl 2>&1 | Out-Null
    }
}
$null = & wsl.exe -d Ubuntu -- mountpoint -q $mountTargetWsl 2>&1
$unmountedAfterTest = $LASTEXITCODE -ne 0
$nativeStageRemovedAfterTest = -not (Test-Path -LiteralPath $nativeStageWindows)

$evidence = [ordered]@{
    schema = 'PLAN8_CACHE_TRANSPORT_CANARY_V1'
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    status = $status
    transport = 'WSL_native_ext4_bind_mount_over_original_E_cache_path'
    original_cache_untouched = $true
    source_manifest = $manifestPath
    source_receipt = $receiptPath
    one_chunk_receipt = $oneChunkReceiptPath
    required_member = $requiredKey
    staged_chunk_count = 1
    copy_checks = $copyChecks
    mount_target_wsl = $mountTargetWsl
    native_stage_wsl = $nativeStageWsl
    mount_output = $mountOutput.Trim()
    python_exit_code = $pythonExitCode
    python_output = $pythonOutput
    unmounted_after_test = $unmountedAfterTest
    native_stage_removed_after_test = $nativeStageRemovedAfterTest
}
$evidenceJson = $evidence | ConvertTo-Json -Depth 20
$evidenceStream = [IO.File]::Open($evidencePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $evidenceBytes = [Text.Encoding]::UTF8.GetBytes($evidenceJson + "`n")
    $evidenceStream.Write($evidenceBytes, 0, $evidenceBytes.Length)
    $evidenceStream.Flush($true)
} finally {
    $evidenceStream.Dispose()
}
if ($status -ne 'pass') {
    throw "cache transport canary failed; evidence: $evidencePath"
}
Write-Output $pythonOutput
Write-Output "Evidence: $evidencePath"
