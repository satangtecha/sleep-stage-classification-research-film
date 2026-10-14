$ErrorActionPreference = 'Stop'

$dispatcher = Join-Path $PSScriptRoot '..\paper_faithful\training\dispatch_plan16_v8_atomic.ps1'
$source = Get-Content -LiteralPath $dispatcher -Raw
$beginMarker = '$launchResult = & $launcherPath'
$endMarker = "if (`$LASTEXITCODE -ne 0) { throw 'Plan16 v8 launcher failed' }"

function Test-ExactSeedHandoff([string]$Text) {
    $begin = $Text.IndexOf($beginMarker, [StringComparison]::Ordinal)
    $end = $Text.IndexOf($endMarker, [StringComparison]::Ordinal)
    if ($begin -lt 0 -or $end -le $begin) { return $false }
    $invocation = $Text.Substring($begin, $end - $begin)
    $selection = [regex]::Matches($invocation, '(?m)^\s+-SelectionSeed\s+43\s*`?\s*$')
    $model = [regex]::Matches($invocation, '(?m)^\s+-ModelSeed\s+43\s*`?\s*$')
    return $selection.Count -eq 1 -and $model.Count -eq 1
}

if (-not (Test-ExactSeedHandoff $source)) { throw 'dispatcher does not hand off both reviewed seed-43 values' }
$mutatedSelection = $source.Replace('-SelectionSeed 43', '-SelectionSeed 42')
$mutatedModel = $source.Replace('-ModelSeed 43', '-ModelSeed 42')
if (Test-ExactSeedHandoff $mutatedSelection) { throw 'test failed to reject selection-seed regression' }
if (Test-ExactSeedHandoff $mutatedModel) { throw 'test failed to reject model-seed regression' }

[pscustomobject]@{
    status = 'pass'
    selection_seed = 43
    model_seed = 43
    selection_seed_42_mutation_rejected = $true
    model_seed_42_mutation_rejected = $true
    no_dispatch = $true
    no_training = $true
} | ConvertTo-Json -Compress
