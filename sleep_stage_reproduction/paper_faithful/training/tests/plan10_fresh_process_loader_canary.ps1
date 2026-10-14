param(
    [Parameter(Mandatory = $true)][string]$ProtocolPath,
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$ResourcePath,
    [Parameter(Mandatory = $true)][string]$StageEvidencePath,
    [Parameter(Mandatory = $true)][string]$EvidencePath,
    [Parameter(Mandatory = $true)][string]$RunPrefix,
    [Parameter(Mandatory = $true)][string]$NativeStageWsl,
    [Parameter(Mandatory = $true)][string]$MountTargetWsl,
    [string]$ResourceProfile = 'RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V7_FRESH_PROCESS_PER_FOLD',
    [string]$ExpectedExecutionStrategy = 'fresh_locked_tf24_process_per_fold',
    [int]$Cap = 32,
    [string]$WslProject = '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction',
    [string]$LockedPython = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
)

$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $EvidencePath) { throw "loader canary evidence already exists: $EvidencePath" }
foreach ($path in @($ProtocolPath, $ReceiptPath, $ResourcePath, $StageEvidencePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "required canary input missing: $path" }
}
$protocol = Get-Content -LiteralPath $ProtocolPath -Raw | ConvertFrom-Json
$protocolSha = (Get-FileHash -LiteralPath $ProtocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$resourceSha = (Get-FileHash -LiteralPath $ResourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
$stageSha = (Get-FileHash -LiteralPath $StageEvidencePath -Algorithm SHA256).Hash.ToLowerInvariant()
$runRuntime = Join-Path 'E:\blp\sleep_stage_reproduction\runtime' $RunPrefix
$childRoot = 'E:\blp\sleep_stage_reproduction\runs'
if (Test-Path -LiteralPath $runRuntime) { throw 'runtime namespace exists before canary' }
if (@(Get-ChildItem -LiteralPath $childRoot -Directory -Filter "$RunPrefix*" -ErrorAction SilentlyContinue).Count -ne 0) { throw 'child namespace exists before canary' }
$mounted = $false
$mountOutput = ''
$pythonOutput = ''
$pythonExitCode = $null
$status = 'fail'
try {
    & wsl.exe -d Ubuntu -- mountpoint -q $MountTargetWsl 2>&1
    if ($LASTEXITCODE -eq 0) { throw "cache target already mounted: $MountTargetWsl" }
    & wsl.exe -d Ubuntu -u root -- mount --bind $NativeStageWsl $MountTargetWsl 2>&1 | ForEach-Object { $mountOutput += "$_`n" }
    if ($LASTEXITCODE -ne 0) { throw "cache bind mount failed: $mountOutput" }
    $mounted = $true
    $findmnt = & wsl.exe -d Ubuntu -u root -- findmnt -T $MountTargetWsl -o TARGET,SOURCE,FSTYPE,OPTIONS 2>&1
    $mountOutput += (($findmnt | Out-String).Trim() + "`n")
    if ($LASTEXITCODE -ne 0 -or $mountOutput -notmatch 'ext4' -or $mountOutput -notmatch [regex]::Escape($NativeStageWsl)) {
        throw "native cache mount verification failed: $mountOutput"
    }
    $protocolWsl = $ProtocolPath -replace '^E:', '/mnt/e' -replace '\\', '/'
    $receiptWsl = $ReceiptPath -replace '^E:', '/mnt/e' -replace '\\', '/'
    $resourceWsl = $ResourcePath -replace '^E:', '/mnt/e' -replace '\\', '/'
    $pythonCode = @'
import json
from types import SimpleNamespace
from paper_faithful.training.subject_generalization_runner import build_plan
args = SimpleNamespace(
    cache_manifest="/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json",
    source_manifest="/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/manifests/source_manifest.json",
    environment_manifest="/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/environment/results/wsl_tf24_probe.json",
    run_prefix="__RUN_PREFIX__", selection_seed=42, subject_count=6, model_seed=42, cap=__CAP__,
    resource_profile="__RESOURCE_PROFILE__", epochs=6,
    resource_evidence="__RESOURCE__", cache_validation_receipt="__RECEIPT__",
    protocol_output="__PROTOCOL__", approved_protocol_sha256="__PROTOCOL_SHA__", plan_only=False,
)
record, folds, cache = build_plan(args)
try:
    print(json.dumps({
        "status":"loaded", "fold_count":len(folds), "cache_member_count":len(cache.members),
        "required_member_count":sum(len(getattr(f.plan, n)) for f in folds for n in ("train","validation","test")),
        "train_counts":[len(f.plan.train) for f in folds], "fresh_process_per_fold":record["fresh_process_per_fold"],
        "execution_strategy":record["execution_strategy"], "no_training_started":True, "runtime_created":False,
    }, sort_keys=True))
finally:
    cache.close()
'@
    $pythonCode = $pythonCode.Replace('__RUN_PREFIX__', $RunPrefix).Replace('__RESOURCE__', $resourceWsl).Replace('__RECEIPT__', $receiptWsl).Replace('__PROTOCOL__', $protocolWsl).Replace('__PROTOCOL_SHA__', $protocolSha).Replace('__RESOURCE_PROFILE__', $ResourceProfile).Replace('__CAP__', [string]$Cap)
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pythonCode))
    $execCode = "import base64; exec(base64.b64decode('$payload'))"
    $result = & wsl.exe --distribution Ubuntu --cd $WslProject -- $LockedPython -c $execCode 2>&1
    $pythonExitCode = $LASTEXITCODE
    $pythonOutput = ($result | Out-String).Trim()
    if ($pythonExitCode -ne 0 -or $pythonOutput -notmatch '"no_training_started": true' -or $pythonOutput -notmatch '"runtime_created": false' -or $pythonOutput -notmatch [regex]::Escape($ExpectedExecutionStrategy)) {
        throw "Plan 10 loader canary failed: $pythonOutput"
    }
    $status = 'pass'
} finally {
    if ($mounted) { & wsl.exe -d Ubuntu -u root -- umount $MountTargetWsl 2>&1 | Out-Null }
}
$null = & wsl.exe -d Ubuntu -- mountpoint -q $MountTargetWsl 2>&1
$unmounted = $LASTEXITCODE -ne 0
$evidence = [ordered]@{
    schema = 'PLAN10_FRESH_PROCESS_NATIVE_LOADER_CANARY_V1'
    created_at = (Get-Date).ToUniversalTime().ToString('o')
    status = $status
    run_prefix = $RunPrefix
    protocol_path = [IO.Path]::GetFullPath($ProtocolPath)
    protocol_sha256 = $protocolSha
    receipt_sha256 = $receiptSha
    resource_evidence_sha256 = $resourceSha
    stage_evidence_sha256 = $stageSha
    native_stage_wsl = $NativeStageWsl
    mount_target_wsl = $MountTargetWsl
    mount_output = $mountOutput.Trim()
    python_output = $pythonOutput
    python_exit_code = $pythonExitCode
    runtime_created = (Test-Path -LiteralPath $runRuntime)
    child_namespace_count = @(Get-ChildItem -LiteralPath $childRoot -Directory -Filter "$RunPrefix*" -ErrorAction SilentlyContinue).Count
    cache_mount_unmounted = $unmounted
    no_training_started = $true
    no_retry = $true
    no_resume = $true
    no_reuse = $true
}
$parent = Split-Path -Parent $EvidencePath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$stream = [IO.File]::Open($EvidencePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $bytes = [Text.Encoding]::UTF8.GetBytes(($evidence | ConvertTo-Json -Depth 16) + "`n"); $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
Write-Output ($evidence | ConvertTo-Json -Compress)
if ($status -ne 'pass' -or -not $unmounted -or [bool]$evidence.runtime_created -or $evidence.child_namespace_count -ne 0) { exit 2 }
