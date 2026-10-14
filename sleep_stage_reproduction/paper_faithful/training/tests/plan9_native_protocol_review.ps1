param(
    [Parameter(Mandatory = $true)][string]$ProtocolPath,
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$ReviewPath,
    [Parameter(Mandatory = $true)][string]$RunPrefix,
    [string]$BulkRoot = 'E:\blp\sleep_stage_reproduction'
)

$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $ReviewPath) { throw "review already exists; refusing overwrite: $ReviewPath" }
$protocol = Get-Content -LiteralPath $ProtocolPath -Raw | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
$protocolSha = (Get-FileHash -LiteralPath $ProtocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$folds = @($protocol.folds)
$pilot = @($protocol.pilot_subjects)
$tests = @($folds | ForEach-Object { [string]$_.test_subject })
$validations = @($folds | ForEach-Object { [string]$_.validation_subject })
$runtimePath = Join-Path (Join-Path $BulkRoot 'runtime') $RunPrefix
$childrenPath = Join-Path $BulkRoot 'runs'
$checks = [ordered]@{
    protocol_identity = ($protocol.run_prefix -eq $RunPrefix -and $protocol.cap -eq 32 -and $protocol.stage_epochs -eq 6)
    pilot_cohort_is_six = ($pilot.Count -eq 6)
    six_folds = ($folds.Count -eq 6)
    held_out_subjects_are_unique = (($tests | Sort-Object -Unique).Count -eq 6)
    held_out_pairs_are_disjoint = (@($folds | Where-Object { $_.test_subject -eq $_.validation_subject }).Count -eq 0)
    bounded_train_counts = (@($folds | Where-Object { $_.train_subject_count -ne 4 -or $_.capped_train_subject_count -ne 4 -or $_.train_epoch_count -ne 128 }).Count -eq 0)
    bounded_validation_test_counts = (@($folds | Where-Object { $_.validation_epoch_count -ne 32 -or $_.test_epoch_count -ne 32 }).Count -eq 0)
    stage1_effective_batch = ($protocol.stage_specs.stage1.microbatch -eq 16 -and $protocol.stage_specs.stage1.gradient_accumulation_steps -eq 8 -and $protocol.stage_specs.stage1.effective_batch -eq 128)
    stage2_preserved = ($protocol.stage_specs.stage2.microbatch -eq 128)
    stage3_global_clip = ($protocol.stage_specs.stage3.microbatch -eq 1 -and $protocol.stage_specs.stage3.gradient_accumulation_steps -eq 128 -and $protocol.stage_specs.stage3.gradient_clip_norm -eq 1 -and $protocol.stage_specs.stage3.stage3_stability_adaptation_id -eq 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1')
    receipt_type = ($receipt.receipt_type -eq 'FULL_CACHE_VALIDATION_RECEIPT_V1_COMPACT_SELECTION_METADATA')
    receipt_binding = ($protocol.cache_validation_receipt_sha256 -eq $receiptSha -and @($receipt.chunks).Count -gt 0)
    fresh_runtime_absent = (-not (Test-Path -LiteralPath $runtimePath))
    fresh_children_absent = (@(Get-ChildItem -LiteralPath $childrenPath -Directory -Filter "$RunPrefix*" -ErrorAction SilentlyContinue).Count -eq 0)
}
$status = if (@($checks.Values | Where-Object { -not $_ }).Count -eq 0) { 'pass' } else { 'fail' }
$review = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_plan9_independent_protocol_review'
    status = $status
    run_prefix = $RunPrefix
    protocol_path = $ProtocolPath
    protocol_sha256 = $protocolSha
    receipt_path = $ReceiptPath
    receipt_sha256 = $receiptSha
    checks = $checks
    source_change = 'selected six-subject pilot is the training cohort; full cache subjects are excluded from fold train sets'
    no_training_dispatched = $true
    no_retry = $true
    no_resume = $true
    no_reuse = $true
    reviewed_at = (Get-Date).ToUniversalTime().ToString('o')
}
$parent = Split-Path -Parent $ReviewPath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$text = $review | ConvertTo-Json -Depth 20
$stream = [IO.File]::Open($ReviewPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $bytes = [Text.Encoding]::UTF8.GetBytes($text + "`n"); $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
if ($status -ne 'pass') { throw "Plan 9 protocol review failed: $ReviewPath" }
Write-Output $text
