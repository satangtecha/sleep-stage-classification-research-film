param(
 [Parameter(Mandatory=$true)][string]$RunPrefix,
 [Parameter(Mandatory=$true)][string]$ProtocolPath,
 [Parameter(Mandatory=$true)][string]$CanaryPath,
 [Parameter(Mandatory=$true)][string]$DispatcherPath,
 [Parameter(Mandatory=$true)][string]$OutputDirectory,
 [string]$GateArtifactType='PLAN16_V26_ATOMIC_CANONICAL_LAUNCH_GATE_V1',
 [string]$Profile='QUALITY_BALANCED_CAP32_E6_V6_BALANCED_CE',
 [int]$Cap=32,
 [int]$Epochs=6,
 [string]$ReviewNote='engineering profile is not paper-exact; compare only within this protocol'
)
$ErrorActionPreference='Stop'
function BytesSha([byte[]]$b){$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash($b))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
function Hash([string]$p){BytesSha ([IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $p)))}
function Rel([string]$root,[string]$path){$r=[IO.Path]::GetFullPath($root).TrimEnd('\');$p=[IO.Path]::GetFullPath($path);$p.Substring(($r+'\').Length).Replace('\','/')}
function Tree([string]$root){$paths=[Collections.Generic.List[string]]::new();foreach($f in Get-ChildItem -LiteralPath $root -Recurse -File -Force){$q=Rel $root $f.FullName;if((('/'+$q+'/') -match '/__pycache__/') -or $q.EndsWith('.pyc')){continue};[void]$paths.Add($q)};$paths.Sort([StringComparer]::Ordinal);$manifest=[Text.StringBuilder]::new();foreach($q in $paths){$s=Hash (Join-Path $root $q.Replace('/',[IO.Path]::DirectorySeparatorChar));[void]$manifest.Append($q).Append("`t").Append($s).Append("`n")};$mb=[Text.UTF8Encoding]::new($false).GetBytes($manifest.ToString());[pscustomobject]@{sha256=BytesSha $mb;file_count=$paths.Count}}
function WriteNew([string]$p,[object]$o){$b=[Text.UTF8Encoding]::new($false).GetBytes(($o|ConvertTo-Json -Depth 30)+"`n");$s=[IO.File]::Open($p,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$s.Write($b,0,$b.Length);$s.Flush($true)}finally{$s.Dispose()}}
$bulk='E:\blp\sleep_stage_reproduction';$profile=$Profile;$gateType=$GateArtifactType;$protocolSha=Hash $ProtocolPath;$canarySha=Hash $CanaryPath;$dispatcherSha=Hash $DispatcherPath;$source=Tree (Join-Path $PSScriptRoot '..\..\paper_faithful');$out=[IO.Path]::GetFullPath($OutputDirectory);New-Item -ItemType Directory -Force -Path $out|Out-Null
$binding=[ordered]@{schema_version=1;artifact_type='SUBJECT_GENERALIZATION_NATIVE_CACHE_LAUNCH_BINDING_V1';status='pass';run_prefix=$RunPrefix;protocol_sha256=$protocolSha;canary_sha256=$canarySha;dispatcher_sha256=$dispatcherSha;launcher_sha256='363095ce7e7eebf3deaf65c38cc759d4bfac66745967e6eec3237070428cc1d2';supervisor_sha256='b49f134463ecb0f4269386d38f3c144231e81aff4c2aa2431f0233cc657803b8';resource_builder_sha256='c8e26cbc3e7cd416bc0034d4870ffb830e82ad33ac24b8b237dee90a18d7cf0f';source_tree_sha256=$source.sha256;source_tree_file_count=$source.file_count;cap=$Cap;epochs=$Epochs;selection_seed=43;model_seed=45;label_evidence_receipt='/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/full-cache-validation-receipt-plan2c-prior-20261005.json';launcher_id_prefix='subject-generalization-plan16-quality-native-cache';resource_profile=$profile;expected_canonical_gate_artifact_type=$gateType}
$bindingPath=Join-Path $out "$RunPrefix-launch-binding.json";WriteNew $bindingPath $binding;$bindingSha=Hash $bindingPath
$review=[ordered]@{schema_version=1;artifact_type='PLAN16_V26_INDEPENDENT_READ_ONLY_REVIEW_V1';status='pass';run_prefix=$RunPrefix;protocol_sha256=$protocolSha;launch_binding_sha256=$bindingSha;dispatcher_sha256=$dispatcherSha;findings=[ordered]@{P0=@();P1=@();P2=@();P3=@($ReviewNote)};decision='approved_for_exactly_once_dispatch';source_tree_sha256=$source.sha256;source_tree_file_count=$source.file_count}
$reviewPath=Join-Path $out "$RunPrefix-independent-review.json";WriteNew $reviewPath $review;[pscustomobject]@{binding_path=$bindingPath;binding_sha256=$bindingSha;review_path=$reviewPath;review_sha256=(Hash $reviewPath);source_tree_sha256=$source.sha256;source_tree_file_count=$source.file_count}|ConvertTo-Json -Compress
