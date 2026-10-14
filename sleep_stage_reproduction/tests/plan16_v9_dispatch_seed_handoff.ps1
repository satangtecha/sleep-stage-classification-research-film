$ErrorActionPreference = 'Stop'

$dispatcher = Join-Path $PSScriptRoot '..\paper_faithful\training\dispatch_plan16_v9_atomic.ps1'
$source = Get-Content -LiteralPath $dispatcher -Raw
$beginMarker = '$launchResult = & $launcherPath'
$endMarker = "if (`$LASTEXITCODE -ne 0) { throw 'Plan16 v9 launcher failed' }"

function Test-ExactSeedAndEvidenceHandoff([string]$Text) {
    $begin = $Text.IndexOf($beginMarker, [StringComparison]::Ordinal)
    $end = $Text.IndexOf($endMarker, [StringComparison]::Ordinal)
    if ($begin -lt 0 -or $end -le $begin) { return $false }
    $invocation = $Text.Substring($begin, $end - $begin)
    $selection = [regex]::Matches($invocation, '(?m)^\s+-SelectionSeed\s+43\s*`?\s*$')
    $model = [regex]::Matches($invocation, '(?m)^\s+-ModelSeed\s+43\s*`?\s*$')
    $receipt = [regex]::Matches($invocation, '(?m)^\s+-WslReceipt\s+\$compactReceiptWsl\s*`?\s*$')
    $evidencePatterns = @(
        '\$compactReceiptSha256\s*=\s*''4960d33b64a1acaefd44de99047c4a6180c1b475ebac07b4abb5eddb86ec0613''',
        '\$nativeStageEvidenceSha256\s*=\s*''0f153cc1e5ed03b49f0ca367550dba74bd8bee9800cf240c35fae565563366d1''',
        '\$loaderCanarySha256\s*=\s*''ab7c3e99399a7f46da7f1e54d70a3d77e26bfc852188a42bd5157ebd59c9f711''',
        '\(Get-Sha256\s+\$compactReceiptPath\)\s*-ne\s*\$compactReceiptSha256',
        '\(Get-Sha256\s+\$nativeStageEvidencePath\)\s*-ne\s*\$nativeStageEvidenceSha256',
        '\(Get-Sha256\s+\$loaderCanaryPath\)\s*-ne\s*\$loaderCanarySha256'
    )
    return $selection.Count -eq 1 -and $model.Count -eq 1 -and $receipt.Count -eq 1 -and @($evidencePatterns | Where-Object { -not [regex]::IsMatch($Text, $_) }).Count -eq 0
}

if (-not (Test-ExactSeedAndEvidenceHandoff $source)) { throw 'dispatcher does not hand off both reviewed seed-43 values and hash-pinned cache evidence' }
$mutatedSelection = $source.Replace('-SelectionSeed 43', '-SelectionSeed 42')
$mutatedModel = $source.Replace('-ModelSeed 43', '-ModelSeed 42')
$mutatedReceipt = $source.Replace('-WslReceipt $compactReceiptWsl', "-WslReceipt '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/stale-receipt.json'")
$mutatedReceiptHash = $source.Replace('4960d33b64a1acaefd44de99047c4a6180c1b475ebac07b4abb5eddb86ec0613', '0000000000000000000000000000000000000000000000000000000000000000')
$mutatedStageHash = $source.Replace('0f153cc1e5ed03b49f0ca367550dba74bd8bee9800cf240c35fae565563366d1', '0000000000000000000000000000000000000000000000000000000000000000')
$mutatedCanaryHash = $source.Replace('ab7c3e99399a7f46da7f1e54d70a3d77e26bfc852188a42bd5157ebd59c9f711', '0000000000000000000000000000000000000000000000000000000000000000')
if (Test-ExactSeedAndEvidenceHandoff $mutatedSelection) { throw 'test failed to reject selection-seed regression' }
if (Test-ExactSeedAndEvidenceHandoff $mutatedModel) { throw 'test failed to reject model-seed regression' }
if (Test-ExactSeedAndEvidenceHandoff $mutatedReceipt) { throw 'test failed to reject stale-receipt handoff' }
if (Test-ExactSeedAndEvidenceHandoff $mutatedReceiptHash) { throw 'test failed to reject compact-receipt hash regression' }
if (Test-ExactSeedAndEvidenceHandoff $mutatedStageHash) { throw 'test failed to reject native-stage hash regression' }
if (Test-ExactSeedAndEvidenceHandoff $mutatedCanaryHash) { throw 'test failed to reject loader-canary hash regression' }

[pscustomobject]@{
    status = 'pass'
    selection_seed = 43
    model_seed = 43
    selection_seed_42_mutation_rejected = $true
    model_seed_42_mutation_rejected = $true
    stale_receipt_mutation_rejected = $true
    compact_receipt_hash_mutation_rejected = $true
    native_stage_hash_mutation_rejected = $true
    loader_canary_hash_mutation_rejected = $true
    no_dispatch = $true
    no_training = $true
} | ConvertTo-Json -Compress
