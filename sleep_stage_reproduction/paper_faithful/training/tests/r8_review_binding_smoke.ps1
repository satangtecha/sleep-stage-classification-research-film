param(
    [string]$LauncherPath = (Join-Path $PSScriptRoot '..\launch_paper_text_pilot_r8.ps1')
)

$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath), [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw 'r8 launcher does not parse' }
$reviewFunction = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-R8ReviewBindings' }, $true)
if (-not $reviewFunction) { throw 'r8 launcher has no r8-specific review binding gate' }
Invoke-Expression $reviewFunction.Extent.Text

$runId = 'paper-text-v1-pilot-cap128-seed42-r8-20260827'
$diagnosisHash = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
$launcherHash = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
$runnerHash = 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
$contractHash = 'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'

function New-ValidGate {
    $source = [pscustomobject]@{ launcher_ps1 = $launcherHash; runner_sh = $runnerHash; lean_team_contract_json = $contractHash }
    return [pscustomobject]@{
        power_interruption_recovery = [pscustomobject]@{
            independent_review = [pscustomobject]@{
                review_id = 'r8-power-recovery-review-1'
                agent_id = 'reviewer-a'
                status = 'no_material_finding'
                reviewed_run_id = $runId
                r7_diagnosis_sha256 = $diagnosisHash
                reviewed_source_sha256 = $source
                all_prior_findings_closed = $true
                r8_gate_creation_authorized = $true
            }
        }
        launch_review = [pscustomobject]@{
            review_id = 'r8-launch-review-1'
            agent_id = 'reviewer-b'
            status = 'no_material_finding'
            reviewed_run_id = $runId
            r7_diagnosis_sha256 = $diagnosisHash
            reviewed_source_sha256 = $source
            all_prior_findings_closed = $true
            stable_ac_power_gate_reviewed = $true
            r7_interruption_evidence_reviewed = $true
            operator_trust_anchor_and_exclusive_lock_reviewed = $true
            permanent_create_new_attempt_marker_reviewed = $true
            fresh_run_authorized = $true
        }
    }
}

function Assert-Refused([string]$Name, [scriptblock]$Mutate) {
    $gate = New-ValidGate
    & $Mutate $gate
    $refused = $false
    try { Assert-R8ReviewBindings -Gate $gate -RunId $runId -R7DiagnosisSha256 $diagnosisHash -LauncherSha256 $launcherHash -RunnerSha256 $runnerHash -ContractSha256 $contractHash } catch { $refused = $true }
    if (-not $refused) { throw "Review binding gate accepted invalid case: $Name" }
}

Assert-Refused 'copied_r7_review_shape' { param($g) $g.power_interruption_recovery.independent_review = [pscustomobject]@{ status = 'no_material_finding'; r6_gate_creation_authorized = $true }; $g.launch_review = [pscustomobject]@{ status = 'no_material_finding'; operator_trust_anchor_and_exclusive_lock_reviewed = $true; fresh_run_authorized = $true } }
Assert-Refused 'wrong_recovery_run_id' { param($g) $g.power_interruption_recovery.independent_review.reviewed_run_id = 'paper-text-v1-pilot-cap128-seed42-r7-20260826' }
Assert-Refused 'wrong_launch_run_id' { param($g) $g.launch_review.reviewed_run_id = 'paper-text-v1-pilot-cap128-seed42-r7-20260826' }
Assert-Refused 'diagnosis_hash_mismatch' { param($g) $g.launch_review.r7_diagnosis_sha256 = ('e' * 64) }
Assert-Refused 'launcher_hash_mismatch' { param($g) $g.power_interruption_recovery.independent_review.reviewed_source_sha256.launcher_ps1 = ('e' * 64) }
Assert-Refused 'runner_hash_mismatch' { param($g) $g.launch_review.reviewed_source_sha256.runner_sh = ('e' * 64) }
Assert-Refused 'contract_hash_mismatch' { param($g) $g.launch_review.reviewed_source_sha256.lean_team_contract_json = ('e' * 64) }
Assert-Refused 'missing_recovery_review_id' { param($g) $g.power_interruption_recovery.independent_review.review_id = '' }
Assert-Refused 'missing_launch_agent_id' { param($g) $g.launch_review.agent_id = '' }
Assert-Refused 'prior_findings_open' { param($g) $g.power_interruption_recovery.independent_review.all_prior_findings_closed = $false }
Assert-Refused 'power_gate_not_reviewed' { param($g) $g.launch_review.stable_ac_power_gate_reviewed = $false }
Assert-Refused 'attempt_marker_not_reviewed' { param($g) $g.launch_review.permanent_create_new_attempt_marker_reviewed = $false }

$validGate = New-ValidGate
Assert-R8ReviewBindings -Gate $validGate -RunId $runId -R7DiagnosisSha256 $diagnosisHash -LauncherSha256 $launcherHash -RunnerSha256 $runnerHash -ContractSha256 $contractHash
[pscustomobject]@{ status = 'pass'; refused_invalid_cases = 12; accepted_valid_r8_bindings = $true; pilot_launched = $false } | ConvertTo-Json -Compress
