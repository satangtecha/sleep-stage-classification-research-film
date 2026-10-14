param(
    [Parameter(Mandatory=$true)][string]$GatePath,
    [Parameter(Mandatory=$true)][string]$LocalPath,
    [Parameter(Mandatory=$true)][string]$CanonicalPath,
    [ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedAuthorizationSha256
)

$ErrorActionPreference='Stop';$prefix='paper-text-v1-multiseed-cap128-r14-20260831';$seeds=@(42,43);$children=@("$prefix-split42-model42","$prefix-split43-model43");$bulkRoot='E:\blp\sleep_stage_reproduction';$dispatch=Join-Path $bulkRoot "runtime\training-logs\$prefix.dispatch.lock";$attempt=Join-Path $bulkRoot "runtime\training-logs\$prefix.launch.lock"
function Get-Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
$gateResolved=(Resolve-Path -LiteralPath $GatePath).Path;$gateSha=Get-Sha $gateResolved;$gate=Get-Content -LiteralPath $gateResolved -Raw|ConvertFrom-Json -ErrorAction Stop
$local=(Resolve-Path -LiteralPath $LocalPath).Path;$canonical=(Resolve-Path -LiteralPath $CanonicalPath).Path;$localSha=Get-Sha $local;$canonicalSha=Get-Sha $canonical
if($localSha-ne$canonicalSha-or(-not[string]::IsNullOrWhiteSpace($ExpectedAuthorizationSha256)-and$localSha-ne$ExpectedAuthorizationSha256.ToLowerInvariant())-or-not[Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($local),[IO.File]::ReadAllBytes($canonical))){throw 'r14 delegated authorization hash/byte identity failed'}
$authorization=Get-Content -LiteralPath $local -Raw|ConvertFrom-Json -ErrorAction Stop
$bindings=@{};foreach($binding in @($gate.source_bindings)){$name=[string]$binding.name;$path=(Resolve-Path -LiteralPath ([string]$binding.path)).Path;if($bindings.ContainsKey($name)-or(Get-Sha $path)-ne[string]$binding.sha256){throw "r14 gate source binding invalid or changed: $name"};$bindings[$name]=$binding}
if(!$bindings.ContainsKey('r14_exactly_once_helpers_ps1')){throw 'r14 helper gate binding absent'};. ([string]$bindings.r14_exactly_once_helpers_ps1.path)
$authorizationSources=@{};foreach($property in $authorization.source_sha256.PSObject.Properties){if($authorizationSources.ContainsKey($property.Name)){throw 'r14 authorization source binding duplicated'};$authorizationSources[$property.Name]=[string]$property.Value}
if($authorizationSources.Count-ne$bindings.Count){throw 'r14 authorization source closure count differs'};foreach($name in $bindings.Keys){if(!$authorizationSources.ContainsKey($name)-or$authorizationSources[$name]-ne[string]$bindings[$name].sha256){throw "r14 authorization source closure differs: $name"}}
Assert-R14DelegatedAuthorization $authorization $prefix $seeds $children $gateSha $dispatch $attempt|Out-Null
$paths=@($dispatch,$attempt,(Join-Path $bulkRoot "runtime\training-logs\$prefix.dispatch.lifecycle.jsonl"),(Join-Path $bulkRoot "runtime\training-logs\$prefix.lifecycle.jsonl"))+@($children|%{Join-Path (Join-Path $bulkRoot 'runs') $_});$present=@($paths|?{Test-Path -LiteralPath $_});if($present.Count){throw "r14 production namespace appeared before launch: $($present-join', ')"}
[ordered]@{status='pass';artifact_type='delegated_user_launch_authorization';sha256=$localSha;gate_sha256=$gateSha;byte_identical=$true;exact_user_excerpts=2;user_directly_requested_exact_r14_identity=$false;agent_interpretation_not_user_quote=$true;source_bindings=$bindings.Count;pilot_launched=$false}|ConvertTo-Json -Compress
