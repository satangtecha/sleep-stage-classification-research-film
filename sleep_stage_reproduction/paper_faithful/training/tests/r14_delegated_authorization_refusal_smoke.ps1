param(
    [string]$HelperPath=(Join-Path $PSScriptRoot '..\r14_exactly_once_helpers.ps1')
)

$ErrorActionPreference='Stop'
. (Resolve-Path -LiteralPath $HelperPath).Path
$prefix='paper-text-v1-multiseed-cap128-r14-20260831';$seeds=@(42,43);$children=@("$prefix-split42-model42","$prefix-split43-model43");$gateSha='a'*64
$dispatch='E:\blp\sleep_stage_reproduction\runtime\training-logs\paper-text-v1-multiseed-cap128-r14-20260831.dispatch.lock'
$attempt='E:\blp\sleep_stage_reproduction\runtime\training-logs\paper-text-v1-multiseed-cap128-r14-20260831.launch.lock'

function New-ValidAuthorization {
    $excerpt1='เอางี้หลังจากนี้ให้ทำไปเลย ฉันอนุญาต ไม่ต้องรอฉันทำไปได้เลย';$excerpt2='ฉันบอกว่าไม่ต้องสนกฎอื่นก่อนหน้านี้ ฉันบกอว่าให้สิทธิคุณทำได้เลย'
    $interpretationText=Get-R14ExpectedAgentInterpretationText $prefix $seeds $children $gateSha
    [pscustomobject]@{
        schema_version=2;artifact_type='delegated_user_launch_authorization';status='confirmed';authorization_mode='standing_user_authorization_with_agent_bound_scope'
        run_id_prefix=$prefix;seeds=$seeds;expected_children=$children;canonical_gate_sha256=$gateSha
        user_directly_requested_exact_r14_identity=$false;standing_authorization_applied_to_r14=$true;confirmation_revoked=$false
        user_authorization_excerpts=@(
            [pscustomobject]@{ordinal=1;role='user';source_thread_id='01a014bc-7bc1-7590-bd2b-029c8a84285b';exact_excerpt=$excerpt1;sha256=(Get-R14TextSha256 $excerpt1)},
            [pscustomobject]@{ordinal=2;role='user';source_thread_id='01a014bc-7bc1-7590-bd2b-029c8a84285b';exact_excerpt=$excerpt2;sha256=(Get-R14TextSha256 $excerpt2)}
        )
        user_authorization_combined_encoding='utf-8-no-bom-excerpt1-lf-excerpt2';user_authorization_combined_sha256=(Get-R14TextSha256 ($excerpt1+"`n"+$excerpt2))
        agent_interpretation=[pscustomobject]@{
            label='agent_interpretation_not_user_quote';authored_by='codex_agent';is_user_quote=$false;standing_authorization_applied_to_r14=$true
            interpretation_text=$interpretationText;interpretation_sha256=(Get-R14TextSha256 $interpretationText)
            run_id_prefix=$prefix;seeds=$seeds;expected_children=$children;canonical_gate_sha256=$gateSha
            stage3_stability_adaptation_id='PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1';stage3_gradient_clip_norm=1.0;stage3_gradient_accumulation_steps=128
            dispatch_marker_path=$dispatch;attempt_marker_path=$attempt;marker_file_mode='CreateNew';marker_file_share='None'
            no_retry_after_marker_consumption=$true;no_resume=$true;no_reuse=$true;exactly_once_launch_authorized=$true
        }
    }
}
function Clone([object]$Value){$Value|ConvertTo-Json -Depth 12|ConvertFrom-Json}
function Assert-Refused([object]$Value,[string]$Label){$refused=$false;try{Assert-R14DelegatedAuthorization $Value $prefix $seeds $children $gateSha $dispatch $attempt|Out-Null}catch{$refused=$true};if(!$refused){throw "Invalid delegated authorization accepted: $Label"}}

$valid=New-ValidAuthorization
Assert-R14DelegatedAuthorization $valid $prefix $seeds $children $gateSha $dispatch $attempt|Out-Null

$fabricated=Clone $valid;$fabricated.user_authorization_excerpts[0].exact_excerpt='fabricated standing authorization';$fabricated.user_authorization_excerpts[0].sha256=Get-R14TextSha256 ([string]$fabricated.user_authorization_excerpts[0].exact_excerpt);$fabricated.user_authorization_combined_sha256=Get-R14TextSha256 (([string]$fabricated.user_authorization_excerpts[0].exact_excerpt)+"`n"+([string]$fabricated.user_authorization_excerpts[1].exact_excerpt));Assert-Refused $fabricated 'self-consistent fabricated excerpt'
$missing=Clone $valid;$missing.user_authorization_excerpts=@($missing.user_authorization_excerpts[0]);Assert-Refused $missing 'missing second exact excerpt'
$unlabeled=Clone $valid;$unlabeled.agent_interpretation.label='';Assert-Refused $unlabeled 'missing agent interpretation label'
$misquoted=Clone $valid;$misquoted.agent_interpretation.is_user_quote=$true;Assert-Refused $misquoted 'agent interpretation labeled as user quote'
$directClaim=Clone $valid;$directClaim.user_directly_requested_exact_r14_identity=$true;Assert-Refused $directClaim 'fabricated direct r14 request claim'

[ordered]@{status='pass';pilot_launched=$false;valid_delegated_authorization_accepted=$true;fabricated_self_consistent_excerpt_refused=$true;missing_exact_excerpt_refused=$true;missing_agent_interpretation_label_refused=$true;agent_interpretation_as_user_quote_refused=$true;fabricated_direct_r14_claim_refused=$true;production_namespace_touched=$false}|ConvertTo-Json -Compress
