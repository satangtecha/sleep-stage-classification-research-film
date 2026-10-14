param(
    [Parameter(Mandatory = $true)][string]$ProtocolPath,
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$EvidencePath,
    [Parameter(Mandatory = $true)][string]$ExpectedRunPrefix
)

$ErrorActionPreference = 'Stop'
$expectedProfile = 'RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V7_FRESH_PROCESS_PER_FOLD'
$protocol = Get-Content -LiteralPath $ProtocolPath -Raw | ConvertFrom-Json
$protocolSha = (Get-FileHash -LiteralPath $ProtocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ([string]$protocol.run_prefix -ne $ExpectedRunPrefix) { throw 'protocol run prefix differs' }
if ([string]$protocol.resource_profile -ne $expectedProfile) { throw 'protocol resource profile differs' }
if ([string]$protocol.execution_strategy -ne 'fresh_locked_tf24_process_per_fold') { throw 'protocol execution strategy differs' }
if ($protocol.fresh_process_per_fold -ne $true) { throw 'protocol does not require fresh process per fold' }
if ([int]$protocol.cap -ne 32 -or [int]$protocol.stage_epochs -ne 6) { throw 'protocol cap or epoch policy differs' }
$folds = @($protocol.folds)
if ($folds.Count -ne 6) { throw 'protocol does not contain six folds' }
foreach ($fold in $folds) {
    if ([int]$fold.train_subject_count -ne 4 -or [int]$fold.capped_train_subject_count -ne 4) { throw 'fold train subject count differs' }
    if ([int]$fold.train_epoch_count -ne 128) { throw 'fold train cap differs' }
}
if ([int]$protocol.stage_specs.stage1.epochs -ne 6 -or [int]$protocol.stage_specs.stage1.microbatch -ne 16) { throw 'stage1 compute profile differs' }
if ([int]$protocol.stage_specs.stage2.epochs -ne 6 -or [int]$protocol.stage_specs.stage2.microbatch -ne 128) { throw 'stage2 compute profile differs' }
if ([int]$protocol.stage_specs.stage3.epochs -ne 6 -or [int]$protocol.stage_specs.stage3.microbatch -ne 1) { throw 'stage3 compute profile differs' }
if ([string]$protocol.cache_validation_receipt_sha256 -ne $receiptSha) { throw 'receipt binding differs' }
$runtimeRoot = Join-Path 'E:\blp\sleep_stage_reproduction\runtime' $ExpectedRunPrefix
if (Test-Path -LiteralPath $runtimeRoot) { throw 'fresh runtime namespace already exists before dispatch' }
$childRoot = 'E:\blp\sleep_stage_reproduction\runs'
$children = @(Get-ChildItem -LiteralPath $childRoot -Directory -Filter "$ExpectedRunPrefix*" -ErrorAction SilentlyContinue)
if ($children.Count -ne 0) { throw 'fresh child namespace already exists before dispatch' }
if (Test-Path -LiteralPath $EvidencePath) { throw 'review evidence already exists; refusing overwrite' }
$evidence = [ordered]@{
    schema_version = 1
    artifact_type = 'plan10_fresh_process_independent_protocol_review'
    status = 'pass'
    protocol_path = [IO.Path]::GetFullPath($ProtocolPath)
    protocol_sha256 = $protocolSha
    receipt_path = [IO.Path]::GetFullPath($ReceiptPath)
    receipt_sha256 = $receiptSha
    run_prefix = $ExpectedRunPrefix
    resource_profile = $expectedProfile
    execution_strategy = 'fresh_locked_tf24_process_per_fold'
    fold_count = $folds.Count
    train_subject_count = 4
    train_epoch_cap = 128
    stage1_microbatch = 16
    stage2_microbatch = 128
    stage3_microbatch = 1
    pre_dispatch_runtime_absent = $true
    pre_dispatch_children_absent = $true
    no_retry = $true
    no_resume = $true
    no_reuse = $true
    reviewed_at = (Get-Date).ToUniversalTime().ToString('o')
}
$parent = Split-Path -Parent $EvidencePath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$json = $evidence | ConvertTo-Json -Depth 16
$stream = [IO.File]::Open($EvidencePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n"); $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
Write-Output ($evidence | ConvertTo-Json -Compress)
