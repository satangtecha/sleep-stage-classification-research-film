param(
    [Parameter(Mandatory=$true)][string]$GatePath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedGateSha256,
    [string]$LocalPath=(Join-Path $PSScriptRoot '..\r14_delegated_user_launch_authorization_20260831.json'),
    [string]$CanonicalPath='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-explicit-user-launch-confirmation-20260831.json'
)

$ErrorActionPreference='Stop'
$prefix='paper-text-v1-multiseed-cap128-r14-20260831';$seeds=@(42,43);$children=@("$prefix-split42-model42","$prefix-split43-model43")
$bulkRoot='E:\blp\sleep_stage_reproduction';$dispatch=Join-Path $bulkRoot "runtime\training-logs\$prefix.dispatch.lock";$attempt=Join-Path $bulkRoot "runtime\training-logs\$prefix.launch.lock"
function Get-Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
$gateResolved=(Resolve-Path -LiteralPath $GatePath).Path;$gateSha=Get-Sha $gateResolved;if($gateSha-ne$ExpectedGateSha256.ToLowerInvariant()){throw 'r14 delegated authorization gate SHA mismatch'}
$gate=Get-Content -LiteralPath $gateResolved -Raw|ConvertFrom-Json -ErrorAction Stop
if($gate.status-ne'pass'-or$gate.fresh_launch_authorized-ne$true-or$gate.run_id_prefix-ne$prefix-or(@($gate.seeds)-join'|')-ne'42|43'-or(@($gate.expected_children)-join'|')-ne($children-join'|')){throw 'r14 delegated authorization gate identity/status failed'}
$bindings=@{};foreach($binding in @($gate.source_bindings)){$name=[string]$binding.name;if([string]::IsNullOrWhiteSpace($name)-or$bindings.ContainsKey($name)-or[string]$binding.sha256-notmatch'^[0-9a-f]{64}$'){throw 'r14 gate source binding invalid'};$path=(Resolve-Path -LiteralPath ([string]$binding.path)).Path;if((Get-Sha $path)-ne[string]$binding.sha256){throw "r14 gate source changed: $name"};$bindings[$name]=$binding}
foreach($name in @('r14_exactly_once_helpers_ps1','r14_confirmation_builder_ps1','r14_confirmation_smoke_ps1')){if(!$bindings.ContainsKey($name)){throw "r14 confirmation source binding absent: $name"}}
if(-not[IO.Path]::GetFullPath([string]$bindings.r14_confirmation_builder_ps1.path).Equals([IO.Path]::GetFullPath($PSCommandPath),[StringComparison]::OrdinalIgnoreCase)){throw 'r14 confirmation builder path binding failed'}
. ([string]$bindings.r14_exactly_once_helpers_ps1.path)

$excerpt1='เอางี้หลังจากนี้ให้ทำไปเลย ฉันอนุญาต ไม่ต้องรอฉันทำไปได้เลย';$excerpt2='ฉันบอกว่าไม่ต้องสนกฎอื่นก่อนหน้านี้ ฉันบกอว่าให้สิทธิคุณทำได้เลย'
$interpretationText=Get-R14ExpectedAgentInterpretationText $prefix $seeds $children $gateSha
$sourceSha=[ordered]@{};foreach($binding in @($gate.source_bindings)){$sourceSha[[string]$binding.name]=[string]$binding.sha256}
$artifact=[ordered]@{
    schema_version=2;artifact_type='delegated_user_launch_authorization';status='confirmed';authorization_mode='standing_user_authorization_with_agent_bound_scope'
    run_id_prefix=$prefix;seeds=$seeds;expected_children=$children;canonical_gate_sha256=$gateSha
    user_directly_requested_exact_r14_identity=$false;standing_authorization_applied_to_r14=$true;confirmation_revoked=$false
    user_authorization_excerpts=@(
        [ordered]@{ordinal=1;role='user';source_thread_id='01a014bc-7bc1-7590-bd2b-029c8a84285b';exact_excerpt=$excerpt1;sha256=(Get-R14TextSha256 $excerpt1)},
        [ordered]@{ordinal=2;role='user';source_thread_id='01a014bc-7bc1-7590-bd2b-029c8a84285b';exact_excerpt=$excerpt2;sha256=(Get-R14TextSha256 $excerpt2)}
    )
    user_authorization_combined_encoding='utf-8-no-bom-excerpt1-lf-excerpt2';user_authorization_combined_sha256=(Get-R14TextSha256 ($excerpt1+"`n"+$excerpt2))
    agent_interpretation=[ordered]@{
        label='agent_interpretation_not_user_quote';authored_by='codex_agent';is_user_quote=$false;standing_authorization_applied_to_r14=$true
        interpretation_text=$interpretationText;interpretation_sha256=(Get-R14TextSha256 $interpretationText)
        run_id_prefix=$prefix;seeds=$seeds;expected_children=$children;canonical_gate_sha256=$gateSha
        stage3_stability_adaptation_id='PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1';stage3_gradient_clip_norm=1.0;stage3_gradient_accumulation_steps=128
        dispatch_marker_path=[IO.Path]::GetFullPath($dispatch);attempt_marker_path=[IO.Path]::GetFullPath($attempt);marker_file_mode='CreateNew';marker_file_share='None'
        no_retry_after_marker_consumption=$true;no_resume=$true;no_reuse=$true;exactly_once_launch_authorized=$true
    }
    source_sha256=$sourceSha
    created_at=(Get-Date).ToString('o')
}
Assert-R14DelegatedAuthorization ([pscustomobject]($artifact|ConvertTo-Json -Depth 14|ConvertFrom-Json)) $prefix $seeds $children $gateSha $dispatch $attempt|Out-Null
foreach($path in @($LocalPath,$CanonicalPath)){if(Test-Path -LiteralPath $path){throw "Immutable r14 delegated authorization already exists: $path"}}
$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($artifact|ConvertTo-Json -Depth 14)+[Environment]::NewLine)
foreach($path in @($LocalPath,$CanonicalPath)){$full=[IO.Path]::GetFullPath($path);[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($full))|Out-Null;$stream=[IO.File]::Open($full,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}}
if(-not[Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($LocalPath),[IO.File]::ReadAllBytes($CanonicalPath))){throw 'r14 delegated authorization copies differ'}
[ordered]@{status='pass';artifact_type='delegated_user_launch_authorization';local_path=[IO.Path]::GetFullPath($LocalPath);canonical_path=[IO.Path]::GetFullPath($CanonicalPath);sha256=(Get-Sha $LocalPath);gate_sha256=$gateSha;exact_user_excerpts=2;user_directly_requested_exact_r14_identity=$false;agent_interpretation_not_user_quote=$true}|ConvertTo-Json -Compress
