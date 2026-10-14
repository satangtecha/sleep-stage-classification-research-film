param(
    [Parameter(Mandatory = $true)][string]$ProtocolPath,
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$EvidencePath,
    [Parameter(Mandatory = $true)][string]$ExpectedRunPrefix
)
$ErrorActionPreference = 'Stop'
$expectedProfile = 'RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V10_MICROBATCH8_PER_STAGE'
$protocol = Get-Content -LiteralPath $ProtocolPath -Raw | ConvertFrom-Json
$protocolSha = (Get-FileHash -LiteralPath $ProtocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ([string]$protocol.run_prefix -ne $ExpectedRunPrefix) { throw 'protocol run prefix differs' }
if ([string]$protocol.resource_profile -ne $expectedProfile) { throw 'protocol resource profile differs' }
if ([string]$protocol.execution_strategy -ne 'fresh_locked_tf24_process_per_stage_per_fold') { throw 'protocol execution strategy differs' }
if ($protocol.fresh_process_per_stage -ne $true) { throw 'protocol does not require fresh process per stage' }
if ([int]$protocol.cap -ne 32 -or [int]$protocol.stage_epochs -ne 6) { throw 'protocol cap or epoch policy differs' }
$folds = @($protocol.folds)
if ($folds.Count -ne 6) { throw 'protocol does not contain six folds' }
foreach ($fold in $folds) {
    if ([int]$fold.train_subject_count -ne 4 -or [int]$fold.capped_train_subject_count -ne 4 -or [int]$fold.train_epoch_count -ne 128) { throw 'fold train contract differs' }
}
if ([int]$protocol.stage_specs.stage1.microbatch -ne 8 -or [int]$protocol.stage_specs.stage2.microbatch -ne 128 -or [int]$protocol.stage_specs.stage3.microbatch -ne 1) { throw 'stage compute profile differs' }
if ([int]$protocol.stage_specs.stage1.gradient_accumulation_steps -ne 16 -or [int]$protocol.stage_specs.stage1.effective_batch -ne 128) { throw 'stage1 accumulation differs' }
if ([string]$protocol.cache_validation_receipt_sha256 -ne $receiptSha) { throw 'receipt binding differs' }
$runtimeRoot = Join-Path 'E:\blp\sleep_stage_reproduction\runtime' $ExpectedRunPrefix
if (Test-Path -LiteralPath $runtimeRoot) { throw 'fresh runtime namespace already exists before dispatch' }
if (@(Get-ChildItem -LiteralPath 'E:\blp\sleep_stage_reproduction\runs' -Directory -Filter "$ExpectedRunPrefix*" -ErrorAction SilentlyContinue).Count -ne 0) { throw 'fresh child namespace already exists before dispatch' }
if (Test-Path -LiteralPath $EvidencePath) { throw 'review evidence already exists; refusing overwrite' }
$evidence = [ordered]@{
    schema_version = 1
    artifact_type = 'plan13_micro_stage_independent_protocol_review'
    status = 'pass'
    protocol_path = [IO.Path]::GetFullPath($ProtocolPath)
    protocol_sha256 = $protocolSha
    receipt_path = [IO.Path]::GetFullPath($ReceiptPath)
    receipt_sha256 = $receiptSha
    run_prefix = $ExpectedRunPrefix
    resource_profile = $expectedProfile
    execution_strategy = 'fresh_locked_tf24_process_per_stage_per_fold'
    fold_count = $folds.Count
    cap = 32
    train_subject_count = 4
    train_epoch_cap = 128
    stage_microbatches = [ordered]@{ stage1 = 8; stage2 = 128; stage3 = 1 }
    stage1_gradient_accumulation_steps = 16
    stage2_loss_adaptation = $null
    stage3_global_norm_clip = 1.0
    paper_exact = $false
    pre_dispatch_runtime_absent = $true
    pre_dispatch_children_absent = $true
    no_retry = $true
    no_resume = $true
    no_reuse = $true
    reviewed_at = (Get-Date).ToUniversalTime().ToString('o')
}
$parent = Split-Path -Parent $EvidencePath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$stream = [IO.File]::Open($EvidencePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $bytes = [Text.Encoding]::UTF8.GetBytes(($evidence | ConvertTo-Json -Depth 16) + "`n"); $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
Write-Output ($evidence | ConvertTo-Json -Compress)
