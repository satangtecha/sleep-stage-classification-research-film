param(
    [string]$LauncherPath = (Join-Path $PSScriptRoot '..\launch_paper_text_pilot_r8.ps1'),
    [ValidateSet('refused', 'accepted')]
    [string]$Expected = 'refused'
)

$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath), [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw 'r8 launcher does not parse' }
$powerFunction = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-StableAcPowerFacts' }, $true)
if (-not $powerFunction) { throw 'r8 launcher has no stable-AC power gate' }
Invoke-Expression $powerFunction.Extent.Text

$accepted = $false
$facts = $null
$refusal = $null
try {
    $facts = Get-StableAcPowerFacts
    $accepted = $true
} catch {
    $refusal = $_.Exception.Message
}

if ($Expected -eq 'refused' -and $accepted) { throw 'Live power gate unexpectedly accepted the current host' }
if ($Expected -eq 'accepted' -and -not $accepted) { throw "Live power gate unexpectedly refused the current host: $refusal" }
[pscustomobject]@{ status = 'pass'; expected = $Expected; accepted = $accepted; refusal = $refusal; facts = $facts; pilot_launched = $false; observed_at = (Get-Date).ToString('o') } | ConvertTo-Json -Compress -Depth 8
