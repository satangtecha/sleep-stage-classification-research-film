param(
    [string]$LauncherPath = (Join-Path $PSScriptRoot '..\launch_paper_text_pilot_r8.ps1')
)

$ErrorActionPreference = 'Stop'
$launcherResolved = (Resolve-Path -LiteralPath $LauncherPath).Path
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($launcherResolved, [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw 'r8 launcher does not parse' }
$confirmationFunction = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-R8UserConfirmation' }, $true)
if (-not $confirmationFunction) { throw 'r8 launcher has no explicit user confirmation gate' }
Invoke-Expression $confirmationFunction.Extent.Text

$launcherText = Get-Content -LiteralPath $launcherResolved -Raw
$confirmationOffset = $launcherText.IndexOf('Assert-R8UserConfirmation -Confirmation')
$markerOffset = $launcherText.IndexOf('[System.IO.FileMode]::CreateNew')
if ($confirmationOffset -lt 0 -or $markerOffset -lt 0 -or $confirmationOffset -ge $markerOffset) { throw 'Explicit user confirmation is not enforced before permanent attempt-marker creation' }

$runId = 'paper-text-v1-pilot-cap128-seed42-r8-20260827'
$threadId = '01a014bc-7bc1-7590-bd2b-029c8a84285b'
$gateHash = ('a' * 64)
$launcherHash = ('b' * 64)
$runnerHash = ('c' * 64)
$contractHash = ('d' * 64)
function New-ValidConfirmation {
    $excerpt = 'Launch fresh r8 exactly once.'
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $excerptHash = -join ($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($excerpt)) | ForEach-Object { $_.ToString('x2') }) } finally { $sha.Dispose() }
    [pscustomobject]@{
        schema_version = 1
        confirmation_id = 'r8-user-confirmation-1'
        status = 'confirmed'
        run_id = $runId
        source_thread_id = $threadId
        received_at = '2026-08-27T13:00:00+07:00'
        exact_user_excerpt = $excerpt
        user_message_hash_encoding = 'utf-8-no-bom-of-json-decoded-exact_user_excerpt'
        user_message_sha256 = $excerptHash
        recovery_gate_sha256 = $gateHash
        source_sha256 = [pscustomobject]@{ launcher_ps1 = $launcherHash; runner_sh = $runnerHash; lean_team_contract_json = $contractHash }
        user_explicitly_requested_fresh_r8_exactly_once = $true
        exactly_once_launch_authorized = $true
        no_resume_or_reuse = $true
        confirmation_revoked = $false
    }
}
function Assert-Refused([string]$Name, [scriptblock]$Mutate) {
    $confirmation = New-ValidConfirmation
    & $Mutate $confirmation
    $refused = $false
    try { Assert-R8UserConfirmation -Confirmation $confirmation -RunId $runId -SourceThreadId $threadId -RecoveryGateSha256 $gateHash -LauncherSha256 $launcherHash -RunnerSha256 $runnerHash -ContractSha256 $contractHash } catch { $refused = $true }
    if (-not $refused) { throw "User confirmation gate accepted invalid case: $Name" }
}

Assert-Refused 'wrong_run_id' { param($c) $c.run_id = 'paper-text-v1-pilot-cap128-seed42-r7-20260826' }
Assert-Refused 'wrong_thread_id' { param($c) $c.source_thread_id = 'wrong-thread' }
Assert-Refused 'empty_excerpt' { param($c) $c.exact_user_excerpt = '' }
Assert-Refused 'invalid_user_message_hash' { param($c) $c.user_message_sha256 = 'not-a-hash' }
Assert-Refused 'different_message_digest' { param($c) $sha = [System.Security.Cryptography.SHA256]::Create(); try { $c.user_message_sha256 = -join ($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes('Different message.')) | ForEach-Object { $_.ToString('x2') }) } finally { $sha.Dispose() } }
Assert-Refused 'wrong_gate_hash' { param($c) $c.recovery_gate_sha256 = ('f' * 64) }
Assert-Refused 'wrong_launcher_hash' { param($c) $c.source_sha256.launcher_ps1 = ('f' * 64) }
Assert-Refused 'wrong_runner_hash' { param($c) $c.source_sha256.runner_sh = ('f' * 64) }
Assert-Refused 'wrong_contract_hash' { param($c) $c.source_sha256.lean_team_contract_json = ('f' * 64) }
Assert-Refused 'user_request_false' { param($c) $c.user_explicitly_requested_fresh_r8_exactly_once = $false }
Assert-Refused 'exactly_once_false' { param($c) $c.exactly_once_launch_authorized = $false }
Assert-Refused 'reuse_allowed' { param($c) $c.no_resume_or_reuse = $false }
Assert-Refused 'revoked' { param($c) $c.confirmation_revoked = $true }

$valid = New-ValidConfirmation
Assert-R8UserConfirmation -Confirmation $valid -RunId $runId -SourceThreadId $threadId -RecoveryGateSha256 $gateHash -LauncherSha256 $launcherHash -RunnerSha256 $runnerHash -ContractSha256 $contractHash
[pscustomobject]@{ status = 'pass'; refused_invalid_cases = 13; accepted_valid_confirmation = $true; exact_excerpt_digest_verified = $true; confirmation_precedes_attempt_marker = $true; pilot_launched = $false } | ConvertTo-Json -Compress
