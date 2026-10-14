$ErrorActionPreference = 'Stop'

$protocolPath = 'E:\blp\sleep_stage_reproduction\runtime\protocols\subject-generalization-resource-limited-plan8-native-cache-v1-cap32-e6-20261005.json'
$receiptPath = 'E:\blp\sleep_stage_reproduction\runtime\integrity-receipts\compact-selection-plan4-low-compute-metadata-20261005.json'
$resourcePath = 'E:\blp\sleep_stage_reproduction\runtime\resource-preflight\plan8-native-cache-loader-preflight-v3-20261005.json'
$stageEvidencePath = 'E:\blp\sleep_stage_reproduction\runtime\reviews\plan8-native-cache-stage-v1-20261005.json'
$evidencePath = 'E:\blp\sleep_stage_reproduction\runtime\reviews\plan8-full-native-loader-canary-v5-20261005.json'
$nativeStageWsl = '/home/techatat/subject-generalization-plan8-native-cache-v1-20261005'
$mountTargetWsl = '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820'
$wslProject = '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction'
$lockedPython = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'

foreach ($path in @($evidencePath)) {
    if (Test-Path -LiteralPath $path) {
        throw "full native loader canary evidence already exists; refusing reuse: $path"
    }
}
if (-not (Test-Path -LiteralPath $protocolPath -PathType Leaf)) { throw "protocol missing: $protocolPath" }
if (-not (Test-Path -LiteralPath $resourcePath -PathType Leaf)) { throw "resource evidence missing: $resourcePath" }
if (-not (Test-Path -LiteralPath $stageEvidencePath -PathType Leaf)) { throw "stage evidence missing: $stageEvidencePath" }

$protocol = Get-Content -LiteralPath $protocolPath -Raw | ConvertFrom-Json
$protocolSha = (Get-FileHash -LiteralPath $protocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$resourceSha = (Get-FileHash -LiteralPath $resourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
$stageSha = (Get-FileHash -LiteralPath $stageEvidencePath -Algorithm SHA256).Hash.ToLowerInvariant()

$mounted = $false
$mountOutput = ''
$pythonOutput = ''
$pythonExitCode = $null
$status = 'fail'
try {
    & wsl.exe -d Ubuntu -- mountpoint -q $mountTargetWsl 2>&1
    if ($LASTEXITCODE -eq 0) { throw "cache target already mounted: $mountTargetWsl" }
    & wsl.exe -d Ubuntu -u root -- mount --bind $nativeStageWsl $mountTargetWsl 2>&1 | ForEach-Object { $mountOutput += "$_`n" }
    if ($LASTEXITCODE -ne 0) { throw "native cache bind mount failed: $mountOutput" }
    $mounted = $true
    $findmnt = & wsl.exe -d Ubuntu -u root -- findmnt -T $mountTargetWsl -o TARGET,SOURCE,FSTYPE,OPTIONS 2>&1
    $mountOutput += (($findmnt | Out-String).Trim() + "`n")
    if ($LASTEXITCODE -ne 0 -or $mountOutput -notmatch 'ext4') { throw "native cache mount verification failed: $mountOutput" }

    $pythonCode = @'
import json
from types import SimpleNamespace
from paper_faithful.training.subject_generalization_runner import build_plan

args = SimpleNamespace(
    cache_manifest="/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json",
    source_manifest="/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/manifests/source_manifest.json",
    environment_manifest="/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/environment/results/wsl_tf24_probe.json",
    run_prefix="subject-generalization-resource-limited-plan8-native-cache-v1-cap32-e6-20261005",
    selection_seed=42,
    subject_count=6,
    model_seed=42,
    cap=32,
    resource_profile="RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V6_DETACHED_GPU_RUN",
    epochs=6,
    resource_evidence="/mnt/e/blp/sleep_stage_reproduction/runtime/resource-preflight/plan8-native-cache-loader-preflight-v3-20261005.json",
    cache_validation_receipt="/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/compact-selection-plan4-low-compute-metadata-20261005.json",
    protocol_output="/mnt/e/blp/sleep_stage_reproduction/runtime/protocols/subject-generalization-resource-limited-plan8-native-cache-v1-cap32-e6-20261005.json",
    approved_protocol_sha256="__PROTOCOL_SHA__",
    plan_only=False,
)
record, folds, cache = build_plan(args)
print(json.dumps({
    "status": "loaded",
    "fold_count": len(folds),
    "cache_member_count": len(cache.members),
    "required_member_count": sum(len(getattr(f.plan, name)) for f in folds for name in ("train", "validation", "test")),
    "cache_manifest_hash": cache.cache_hash,
    "no_training_started": True,
    "runtime_created": False,
}, sort_keys=True))
'@.Replace('__PROTOCOL_SHA__', $protocolSha)
    $pythonPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pythonCode))
    $pythonExec = "import base64; exec(base64.b64decode('$pythonPayload'))"
    $pythonResult = & wsl.exe --distribution Ubuntu --cd $wslProject -- $lockedPython -c $pythonExec 2>&1
    $pythonExitCode = $LASTEXITCODE
    $pythonOutput = ($pythonResult | Out-String).Trim()
    if ($pythonExitCode -ne 0) { throw "full native loader canary failed: $pythonOutput" }
    $status = 'pass'
} finally {
    if ($mounted) { & wsl.exe -d Ubuntu -u root -- umount $mountTargetWsl 2>&1 | Out-Null }
}
$null = & wsl.exe -d Ubuntu -- mountpoint -q $mountTargetWsl 2>&1
$unmountedAfterTest = $LASTEXITCODE -ne 0
$evidence = [ordered]@{
    schema = 'PLAN8_FULL_NATIVE_LOADER_CANARY_V1'
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    status = $status
    protocol_path = $protocolPath
    protocol_sha256 = $protocolSha
    receipt_path = $receiptPath
    receipt_sha256 = $receiptSha
    resource_evidence_path = $resourcePath
    resource_evidence_sha256 = $resourceSha
    stage_evidence_path = $stageEvidencePath
    stage_evidence_sha256 = $stageSha
    native_stage_wsl = $nativeStageWsl
    mount_target_wsl = $mountTargetWsl
    mount_output = $mountOutput.Trim()
    python_exit_code = $pythonExitCode
    python_output = $pythonOutput
    no_training_started = ($pythonOutput -match '"no_training_started": true')
    runtime_created = ($pythonOutput -match '"runtime_created": false') -eq $false
    unmounted_after_test = $unmountedAfterTest
    original_cache_untouched = $true
}
$evidenceJson = $evidence | ConvertTo-Json -Depth 20
$stream = [IO.File]::Open($evidencePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $bytes = [Text.Encoding]::UTF8.GetBytes($evidenceJson + "`n")
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
} finally { $stream.Dispose() }
if ($status -ne 'pass' -or -not $unmountedAfterTest) { throw "full native loader canary failed; evidence: $evidencePath" }
Write-Output $pythonOutput
Write-Output "Evidence: $evidencePath"
