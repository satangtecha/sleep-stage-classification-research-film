$ErrorActionPreference = 'Stop'

$sourcePath = Join-Path $PSScriptRoot 'plan16_quality_native_loader_canary.ps1'
$source = Get-Content -LiteralPath $sourcePath -Raw

foreach ($needle in @(
    '[Parameter(Mandatory = $true)][ValidateRange(0, 2147483647)][int]$SelectionSeed',
    '[Parameter(Mandatory = $true)][ValidateRange(0, 2147483647)][int]$ModelSeed',
    "if ([int]`$protocolRecord.selection_seed -ne `$SelectionSeed)",
    "if ([int]`$protocolRecord.model_seed -ne `$ModelSeed)",
    'run_prefix=''$RunPrefix'', selection_seed=$SelectionSeed, subject_count=6, model_seed=$ModelSeed, cap=64,'
)) {
    if (-not $source.Contains($needle)) { throw "loader canary is missing seed binding: $needle" }
}

$regressed = $source.Replace('selection_seed=$SelectionSeed', 'selection_seed=42').Replace('model_seed=$ModelSeed', 'model_seed=42')
if ($regressed.Contains('run_prefix=''$RunPrefix'', selection_seed=$SelectionSeed, subject_count=6, model_seed=$ModelSeed, cap=64,')) {
    throw 'seed forwarding regression was not rejected by the test oracle'
}

Write-Output 'PASS: Plan16 loader canary binds selection/model seeds to the reviewed protocol.'
