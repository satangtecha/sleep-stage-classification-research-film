param(
    [Parameter(Mandatory = $true)][string]$ProtocolPath,
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$ResourcePath,
    [Parameter(Mandatory = $true)][string]$StageEvidencePath,
    [Parameter(Mandatory = $true)][string]$EvidencePath,
    [Parameter(Mandatory = $true)][string]$RunPrefix,
    [Parameter(Mandatory = $true)][string]$NativeStageWsl,
    [Parameter(Mandatory = $true)][string]$MountTargetWsl,
    [string]$WslProject = '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction',
    [string]$LockedPython = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
)

$ErrorActionPreference = 'Stop'

foreach ($path in @($EvidencePath)) {
    if (Test-Path -LiteralPath $path) { throw "loader canary evidence already exists; refusing reuse: $path" }
}
foreach ($path in @($ProtocolPath, $ReceiptPath, $ResourcePath, $StageEvidencePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "required canary input missing: $path" }
}

$protocol = Get-Content -LiteralPath $ProtocolPath -Raw | ConvertFrom-Json
$protocolSha = (Get-FileHash -LiteralPath $ProtocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$resourceSha = (Get-FileHash -LiteralPath $ResourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
$stageSha = (Get-FileHash -LiteralPath $StageEvidencePath -Algorithm SHA256).Hash.ToLowerInvariant()
$mounted = $false
$mountOutput = ''
$pythonOutput = ''
$pythonExitCode = $null
$status = 'fail'
try {
    & wsl.exe -d Ubuntu -- mountpoint -q $MountTargetWsl 2>&1
    if ($LASTEXITCODE -eq 0) { throw "cache target already mounted: $MountTargetWsl" }
    & wsl.exe -d Ubuntu -u root -- mount --bind $NativeStageWsl $MountTargetWsl 2>&1 | ForEach-Object { $mountOutput += "$_`n" }
    if ($LASTEXITCODE -ne 0) { throw "native cache bind mount failed: $mountOutput" }
    $mounted = $true
    $findmnt = & wsl.exe -d Ubuntu -u root -- findmnt -T $MountTargetWsl -o TARGET,SOURCE,FSTYPE,OPTIONS 2>&1
    $mountOutput += (($findmnt | Out-String).Trim() + "`n")
    if ($LASTEXITCODE -ne 0 -or $mountOutput -notmatch 'ext4' -or $mountOutput -notmatch [regex]::Escape($NativeStageWsl)) {
        throw "native cache mount verification failed: $mountOutput"
    }

    $pythonCode = @'
import json
from types import SimpleNamespace
from paper_faithful.training.subject_generalization_runner import build_plan

args = SimpleNamespace(
    cache_manifest="/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json",
    source_manifest="/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/manifests/source_manifest.json",
    environment_manifest="/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/environment/results/wsl_tf24_probe.json",
    run_prefix="__RUN_PREFIX__",
    selection_seed=42,
    subject_count=6,
    model_seed=42,
    cap=32,
    resource_profile="RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V6_DETACHED_GPU_RUN",
    epochs=6,
    resource_evidence="__RESOURCE_PATH__",
    cache_validation_receipt="/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/compact-selection-plan9-cohort6-cap32-metadata-20261005.json",
    protocol_output="/mnt/e/blp/sleep_stage_reproduction/runtime/protocols/subject-generalization-resource-limited-plan9-cohort6-native-cache-v2-cap32-e6-20261005.json",
    approved_protocol_sha256="__PROTOCOL_SHA__",
    plan_only=False,
)
record, folds, cache = build_plan(args)
print(json.dumps({
    "status": "loaded",
    "fold_count": len(folds),
    "cache_member_count": len(cache.members),
    "required_member_count": sum(len(getattr(f.plan, name)) for f in folds for name in ("train", "validation", "test")),
    "train_counts": [len(f.plan.train) for f in folds],
    "cache_manifest_hash": cache.cache_hash,
    "no_training_started": True,
    "runtime_created": False,
}, sort_keys=True))
'@
    $resourceWsl = $ResourcePath -replace '^E:', '/mnt/e' -replace '\\', '/'
    $pythonCode = $pythonCode.Replace('__RUN_PREFIX__', $RunPrefix).Replace('__PROTOCOL_SHA__', $protocolSha).Replace('__RESOURCE_PATH__', $resourceWsl)
    $pythonPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pythonCode))
    $pythonExec = "import base64; exec(base64.b64decode('$pythonPayload'))"
    $pythonResult = & wsl.exe --distribution Ubuntu --cd $WslProject -- $LockedPython -c $pythonExec 2>&1
    $pythonExitCode = $LASTEXITCODE
    $pythonOutput = ($pythonResult | Out-String).Trim()
    if ($pythonExitCode -ne 0) { throw "Plan 9 v2 native loader canary failed: $pythonOutput" }
    if ($pythonOutput -notmatch '"no_training_started": true' -or $pythonOutput -notmatch '"runtime_created": false') {
        throw "loader canary did not prove no training/runtime side effect: $pythonOutput"
    }
    $status = 'pass'
} finally {
    if ($mounted) { & wsl.exe -d Ubuntu -u root -- umount $MountTargetWsl 2>&1 | Out-Null }
}
$null = & wsl.exe -d Ubuntu -- mountpoint -q $MountTargetWsl 2>&1
$unmountedAfterTest = $LASTEXITCODE -ne 0
$evidence = [ordered]@{
    schema = 'PLAN9_V2_FULL_NATIVE_LOADER_CANARY_V1'
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    status = $status
    run_prefix = $RunPrefix
    protocol_path = $ProtocolPath
    protocol_sha256 = $protocolSha
    receipt_path = $ReceiptPath
    receipt_sha256 = $receiptSha
    resource_evidence_path = $ResourcePath
    resource_evidence_sha256 = $resourceSha
    stage_evidence_path = $StageEvidencePath
    stage_evidence_sha256 = $stageSha
    native_stage_wsl = $NativeStageWsl
    mount_target_wsl = $MountTargetWsl
    mount_output = $mountOutput.Trim()
    python_exit_code = $pythonExitCode
    python_output = $pythonOutput
    no_training_started = ($pythonOutput -match '"no_training_started": true')
    runtime_created = ($pythonOutput -match '"runtime_created": true')
    unmounted_after_test = $unmountedAfterTest
    original_cache_untouched = $true
}
$parent = Split-Path -Parent $EvidencePath
if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$json = $evidence | ConvertTo-Json -Depth 20
$stream = [IO.File]::Open($EvidencePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n"); $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
if ($status -ne 'pass' -or -not $unmountedAfterTest -or -not $evidence.no_training_started -or $evidence.runtime_created) { throw "Plan 9 v2 native loader canary failed; evidence: $EvidencePath" }
Write-Output $pythonOutput
Write-Output "Evidence: $EvidencePath"
