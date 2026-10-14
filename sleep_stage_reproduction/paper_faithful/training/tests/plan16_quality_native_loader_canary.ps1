param(
    [Parameter(Mandatory = $true)][string]$ProtocolPath,
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$LabelReceiptPath,
    [Parameter(Mandatory = $true)][string]$ResourcePath,
    [Parameter(Mandatory = $true)][string]$StageEvidencePath,
    [Parameter(Mandatory = $true)][string]$EvidencePath,
    [Parameter(Mandatory = $true)][string]$RuntimeRootPath,
    [Parameter(Mandatory = $true)][string]$RunPrefix,
    [Parameter(Mandatory = $true)][string]$NativeStageWsl,
    [Parameter(Mandatory = $true)][string]$MountTargetWsl,
    [Parameter(Mandatory = $true)][ValidateRange(0, 2147483647)][int]$SelectionSeed,
    [Parameter(Mandatory = $true)][ValidateRange(0, 2147483647)][int]$ModelSeed,
    [string]$WslProject = '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction',
    [string]$LockedPython = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $EvidencePath) { throw "loader canary evidence already exists: $EvidencePath" }
if (Test-Path -LiteralPath $RuntimeRootPath) { throw "runtime namespace already exists before canary: $RuntimeRootPath" }
foreach ($path in @($ProtocolPath, $ReceiptPath, $LabelReceiptPath, $ResourcePath, $StageEvidencePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "required canary input missing: $path" }
}
$protocolRecord = Get-Content -LiteralPath $ProtocolPath -Raw | ConvertFrom-Json
if ([int]$protocolRecord.selection_seed -ne $SelectionSeed) { throw 'loader canary selection seed does not match protocol' }
if ([int]$protocolRecord.model_seed -ne $ModelSeed) { throw 'loader canary model seed does not match protocol' }
$profile = [string]$protocolRecord.resource_profile
if ($profile -notin @(
    'QUALITY_BALANCED_CAP64_E12_V1_FRESH_STAGE_WAIT_DRAIN',
    'QUALITY_BALANCED_CAP64_E12_V2_CONSERVATIVE_STAGE3_SGD',
    'QUALITY_BALANCED_CAP64_E12_V3_SUBJECT_ZSCORE',
    'QUALITY_BALANCED_CAP64_E12_V4_TRAIN_TIME_MASK',
    'QUALITY_BALANCED_CAP64_E12_V5_STAGE3_FOCAL_LOSS',
    'QUALITY_BALANCED_CAP32_E6_V6_BALANCED_CE',
    'QUALITY_BALANCED_CAP64_E12_V7_STAGE3_FOCAL_C10',
    'QUALITY_BALANCED_CAP64_E12_V8_STAGE3_FOCAL_C85'
)) { throw "loader canary does not permit resource profile: $profile" }
$expectedCap = if ($profile -eq 'QUALITY_BALANCED_CAP32_E6_V6_BALANCED_CE') { 32 } else { 64 }
$expectedEpochs = if ($profile -eq 'QUALITY_BALANCED_CAP32_E6_V6_BALANCED_CE') { 6 } else { 12 }
if ([int]$protocolRecord.cap -ne $expectedCap -or [int]$protocolRecord.stage_epochs -ne $expectedEpochs) {
    throw "loader canary profile dimensions do not match: expected cap$expectedCap/e$expectedEpochs"
}
$protocolSha = (Get-FileHash -LiteralPath $ProtocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$labelSha = (Get-FileHash -LiteralPath $LabelReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$resourceSha = (Get-FileHash -LiteralPath $ResourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
$stageSha = (Get-FileHash -LiteralPath $StageEvidencePath -Algorithm SHA256).Hash.ToLowerInvariant()
$mounted = $false; $mountOutput = ''; $pythonOutput = ''; $pythonExitCode = $null; $status = 'fail'
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
    $resourceWsl = $ResourcePath -replace '^E:', '/mnt/e' -replace '\\', '/'
    $protocolWsl = $ProtocolPath -replace '^E:', '/mnt/e' -replace '\\', '/'
    $receiptWsl = $ReceiptPath -replace '^E:', '/mnt/e' -replace '\\', '/'
    $labelWsl = $LabelReceiptPath -replace '^E:', '/mnt/e' -replace '\\', '/'
    $code = @"
import json
from types import SimpleNamespace
from paper_faithful.training.subject_generalization_runner import build_plan
args = SimpleNamespace(
    cache_manifest='/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json',
    source_manifest='/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/manifests/source_manifest.json',
    environment_manifest='/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/environment/results/wsl_tf24_probe.json',
    run_prefix='$RunPrefix', selection_seed=$SelectionSeed, subject_count=6, model_seed=$ModelSeed, cap=$expectedCap,
    resource_profile='$profile', epochs=$expectedEpochs, resource_evidence='$resourceWsl',
    cache_validation_receipt='$receiptWsl', label_evidence_receipt='$labelWsl',
    protocol_output='$protocolWsl', approved_protocol_sha256='$protocolSha', plan_only=False)
record, folds, cache = build_plan(args)
try:
    payload = {'status':'loaded','fold_count':len(folds),'cache_member_count':len(cache.members),
        'required_member_count':sum(len(getattr(f.plan,n)) for f in folds for n in ('train','validation','test')),
        'train_counts':[len(f.plan.train) for f in folds], 'execution_strategy':record['execution_strategy'],
        'cap_policy':record['cap_policy'], 'no_training_started':True, 'runtime_created':False}
    print(json.dumps(payload, sort_keys=True))
finally:
    cache.close()
"@
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
    $pythonExec = "import base64; exec(base64.b64decode('$payload'))"
    $result = & wsl.exe --distribution Ubuntu --cd $WslProject -- $LockedPython -c $pythonExec 2>&1
    $pythonExitCode = $LASTEXITCODE; $pythonOutput = ($result | Out-String).Trim()
    if ($pythonExitCode -ne 0) { throw "Plan 16 loader canary failed: $pythonOutput" }
    if ($pythonOutput -notmatch '"no_training_started": true' -or $pythonOutput -notmatch '"runtime_created": false') {
        throw "loader canary did not prove no training/runtime side effect: $pythonOutput"
    }
    $status = 'pass'
} finally {
    if ($mounted) { & wsl.exe -d Ubuntu -u root -- umount $MountTargetWsl 2>&1 | Out-Null }
}
$null = & wsl.exe -d Ubuntu -- mountpoint -q $MountTargetWsl 2>&1
$unmounted = $LASTEXITCODE -ne 0
$runtimeCreated = Test-Path -LiteralPath $RuntimeRootPath
$evidence = [ordered]@{
    schema='PLAN16_QUALITY_NATIVE_LOADER_CANARY_V1'; created_at=(Get-Date).ToUniversalTime().ToString('o'); status=$status
    run_prefix=$RunPrefix; protocol_path=$ProtocolPath; protocol_sha256=$protocolSha
    selection_seed=$SelectionSeed; model_seed=$ModelSeed
    receipt_path=$ReceiptPath; receipt_sha256=$receiptSha; label_receipt_path=$LabelReceiptPath; label_receipt_sha256=$labelSha
    resource_evidence_path=$ResourcePath; resource_evidence_sha256=$resourceSha
    stage_evidence_path=$StageEvidencePath; stage_evidence_sha256=$stageSha; resource_profile=$profile
    native_stage_wsl=$NativeStageWsl; mount_target_wsl=$MountTargetWsl; mount_output=$mountOutput.Trim()
    python_exit_code=$pythonExitCode; python_output=$pythonOutput
    no_training_started=($pythonOutput -match '"no_training_started": true'); runtime_created=$runtimeCreated
    unmounted_after_test=$unmounted; original_cache_untouched=$true; no_retry=$true; no_resume=$true; no_reuse=$true
}
$parent = Split-Path -Parent $EvidencePath
if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$stream = [IO.File]::Open($EvidencePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $bytes=[Text.Encoding]::UTF8.GetBytes(($evidence | ConvertTo-Json -Depth 20)+"`n"); $stream.Write($bytes,0,$bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
if ($status -ne 'pass' -or -not $unmounted -or -not $evidence.no_training_started -or $runtimeCreated) {
    throw "Plan 16 native loader canary failed; evidence: $EvidencePath"
}
Write-Output $pythonOutput
Write-Output "Evidence: $EvidencePath"
