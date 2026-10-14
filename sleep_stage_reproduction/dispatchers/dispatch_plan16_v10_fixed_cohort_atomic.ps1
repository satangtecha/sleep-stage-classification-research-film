param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedDispatcherSha256,
    [Parameter(Mandatory = $true)][string]$LaunchBindingPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedLaunchBindingSha256,
    [Parameter(Mandatory = $true)][string]$IndependentReviewPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedIndependentReviewSha256,
    [switch]$ValidateStaticOnly
)

$ErrorActionPreference = 'Stop'
$runPrefix = 'subject-generalization-quality-plan16-v10-cap64-e12-cohort43-model44-20261006'
$protocolSha256 = '54b5c0fadcb4697e4dd28e54d56af83a27f5741bab13c7b12ced9048c7faf23f'
$launcherSha256 = '0ce73695dc76c2e1083c8c53d0a1caebbea7db9b76c7c1697e6fd0c97b31b632'
$supervisorSha256 = 'c05bc3e3c6108a7559467a0dfa704031feda7cc2bdf657441fcd1794e4bf3b35'
$resourceBuilderSha256 = 'c8e26cbc3e7cd416bc0034d4870ffb830e82ad33ac24b8b237dee90a18d7cf0f'
$loaderCanarySha256 = '6425cc4a155a55000ff18328fafc1c3fdee40649cc3114350df95cec20c99d6c'
$compactReceiptSha256 = '4960d33b64a1acaefd44de99047c4a6180c1b475ebac07b4abb5eddb86ec0613'
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$trainingRoot = Join-Path $projectRoot 'paper_faithful\training'
$launcherPath = Join-Path $trainingRoot 'launch_native_cache_subject_run_v6.ps1'
$supervisorPath = Join-Path $trainingRoot 'native_cache_subject_supervisor_v2.ps1'
$resourceBuilder = Join-Path $trainingRoot 'tests\build_subject_generalization_resource_evidence.ps1'
$protocolPath = Join-Path $bulkRoot "runtime\protocols\$runPrefix.json"
$resourcePath = Join-Path $bulkRoot 'runtime\resource-preflight\plan16-v10-dispatch-preflight-v1-20261006.json'
$launchEvidencePath = Join-Path $bulkRoot 'runtime\reviews\plan16-v10-launch-evidence-v1-20261006.json'
$canonicalGatePath = Join-Path $bulkRoot 'runtime\reviews\plan16-v10-canonical-gate-v1-20261006.json'
$launcherIdPrefix = 'subject-generalization-plan16-quality-native-cache'
$launcherRoot = Join-Path $bulkRoot "runtime\driver-recovery\$launcherIdPrefix-$runPrefix"
$runtimeRoot = Join-Path $bulkRoot "runtime\$runPrefix"
$labelReceiptWsl = '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/full-cache-validation-receipt-plan2c-prior-20261005.json'
$compactReceiptPath = Join-Path $bulkRoot 'runtime\integrity-receipts\compact-selection-plan16-seed43-cohort6-cap64-balanced-v1-20261006.json'
$compactReceiptWsl = '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/compact-selection-plan16-seed43-cohort6-cap64-balanced-v1-20261006.json'
$loaderCanaryPath = Join-Path $bulkRoot 'runtime\validation\plan16-v10-cohort43-model44-native-loader-canary-v1-20261006.json'
$nativeStageWsl = '/home/techatat/subject-generalization-plan16-quality-cap64-native-cache-v3-seed43-20261006'
$cacheMountTargetWsl = '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820'
$gateType = 'PLAN16_V10_ATOMIC_CANONICAL_LAUNCH_GATE_V1'

function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Write-JsonCreateOnly([string]$Path, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 20
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + "`n"); $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
}
function Get-SourceTree([string]$Root) {
    $items = Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Where-Object {
        $r = [IO.Path]::GetRelativePath($Root, $_.FullName).Replace('\', '/')
        $r -notmatch '(^|/)__pycache__(/|$)' -and -not $r.EndsWith('.pyc')
    } | Sort-Object { [IO.Path]::GetRelativePath($Root, $_.FullName).Replace('\', '/') }
    $sb = [Text.StringBuilder]::new()
    foreach ($item in $items) {
        $relative = [IO.Path]::GetRelativePath($Root, $item.FullName).Replace('\', '/')
        [void]$sb.Append($relative).Append("`t").Append((Get-Sha256 $item.FullName)).Append("`n")
    }
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($sb.ToString())
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $digest = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() } finally { $sha.Dispose() }
    [pscustomobject]@{ sha256=$digest; file_count=@($items).Count }
}
function Require([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }

$dispatcherPath = [IO.Path]::GetFullPath($PSCommandPath)
Require ((Get-Sha256 $dispatcherPath) -eq $ApprovedDispatcherSha256.ToLowerInvariant()) 'dispatcher SHA-256 mismatch'
Require ((Get-Sha256 $launcherPath) -eq $launcherSha256) 'launcher changed after review'
Require ((Get-Sha256 $supervisorPath) -eq $supervisorSha256) 'supervisor changed after review'
Require ((Get-Sha256 $resourceBuilder) -eq $resourceBuilderSha256) 'resource builder changed after review'
Require ((Get-Sha256 $protocolPath) -eq $protocolSha256) 'v10 protocol SHA-256 mismatch'
Require ((Get-Sha256 $compactReceiptPath) -eq $compactReceiptSha256) 'compact selection receipt SHA-256 mismatch'
Require ((Get-Sha256 $loaderCanaryPath) -eq $loaderCanarySha256) 'v10 native loader canary SHA-256 mismatch'
$protocol = Get-Content -LiteralPath $protocolPath -Raw | ConvertFrom-Json
Require ([string]$protocol.run_prefix -eq $runPrefix) 'protocol run prefix mismatch'
Require ([int]$protocol.selection_seed -eq 43 -and [int]$protocol.model_seed -eq 44) 'protocol seed binding mismatch'
Require ([int]$protocol.cap -eq 64 -and [int]$protocol.stage_epochs -eq 12) 'protocol cap or epochs mismatch'
Require ([string]$protocol.cache_validation_receipt -eq $compactReceiptWsl -and [string]$protocol.cache_validation_receipt_sha256 -eq $compactReceiptSha256) 'protocol compact receipt mismatch'
Require ([string]$protocol.resource_profile -eq 'QUALITY_BALANCED_CAP64_E12_V1_FRESH_STAGE_WAIT_DRAIN') 'protocol resource profile mismatch'
$canary = Get-Content -LiteralPath $loaderCanaryPath -Raw | ConvertFrom-Json
Require ([string]$canary.status -eq 'pass' -and [string]$canary.run_prefix -eq $runPrefix -and [string]$canary.protocol_sha256 -eq $protocolSha256) 'loader canary content mismatch'
Require ($canary.no_training_started -eq $true -and $canary.runtime_created -eq $false -and $canary.unmounted_after_test -eq $true) 'loader canary safety invariant mismatch'
$sourceTree = Get-SourceTree (Join-Path $projectRoot 'paper_faithful')
$sourceBindings = @($protocol.source_code_binding.PSObject.Properties)
Require ($sourceBindings.Count -eq 7) 'expected exactly seven Python source bindings'
foreach ($binding in $sourceBindings) {
    $logical = [string]$binding.Value.logical_path
    Require ($logical -match '^paper_faithful/training/[A-Za-z0-9_]+\.py$') "unsafe bound source path: $logical"
    $source = Join-Path $projectRoot $logical.Replace('/', [IO.Path]::DirectorySeparatorChar)
    Require ((Get-Sha256 $source) -eq [string]$binding.Value.sha256) "bound source changed: $logical"
}
$bindingFull = [IO.Path]::GetFullPath($LaunchBindingPath)
$reviewFull = [IO.Path]::GetFullPath($IndependentReviewPath)
Require ((Get-Sha256 $bindingFull) -eq $ApprovedLaunchBindingSha256.ToLowerInvariant()) 'launch binding SHA-256 mismatch'
Require ((Get-Sha256 $reviewFull) -eq $ApprovedIndependentReviewSha256.ToLowerInvariant()) 'independent review SHA-256 mismatch'
$binding = Get-Content -LiteralPath $bindingFull -Raw | ConvertFrom-Json
$review = Get-Content -LiteralPath $reviewFull -Raw | ConvertFrom-Json
Require ([string]$binding.artifact_type -eq 'SUBJECT_GENERALIZATION_NATIVE_CACHE_LAUNCH_BINDING_V1' -and [string]$binding.status -eq 'pass') 'launch binding not passing'
Require ([string]$binding.run_prefix -eq $runPrefix -and [string]$binding.protocol_sha256 -eq $protocolSha256) 'launch binding run/protocol mismatch'
Require ([int]$binding.selection_seed -eq 43 -and [int]$binding.model_seed -eq 44 -and [int]$binding.cap -eq 64 -and [int]$binding.epochs -eq 12) 'launch binding parameters mismatch'
Require ([string]$binding.dispatcher_sha256 -eq $ApprovedDispatcherSha256.ToLowerInvariant()) 'launch binding dispatcher mismatch'
Require ([string]$binding.launcher_sha256 -eq $launcherSha256 -and [string]$binding.supervisor_sha256 -eq $supervisorSha256 -and [string]$binding.resource_builder_sha256 -eq $resourceBuilderSha256) 'launch binding component mismatch'
Require ([string]$binding.source_tree_sha256 -eq $sourceTree.sha256 -and [int]$binding.source_tree_file_count -eq $sourceTree.file_count) 'launch binding source tree mismatch'
Require ([string]$binding.expected_canonical_gate_artifact_type -eq $gateType) 'launch binding canonical gate mismatch'
Require ([string]$review.status -eq 'pass' -and @($review.findings.P0).Count -eq 0 -and @($review.findings.P1).Count -eq 0 -and @($review.findings.P2).Count -eq 0) 'independent review not launch approved'
Require ([string]$review.run_prefix -eq $runPrefix -and [string]$review.protocol_sha256 -eq $protocolSha256 -and [string]$review.launch_binding_sha256 -eq $ApprovedLaunchBindingSha256.ToLowerInvariant() -and [string]$review.dispatcher_sha256 -eq $ApprovedDispatcherSha256.ToLowerInvariant()) 'independent review binding mismatch'
if ($ValidateStaticOnly) { Require ($review.authorization.static_validation_authorized -eq $true) 'review does not authorize static validation' }
else { Require ($review.authorization.production_dispatch_authorized -eq $true -and $review.authorization.exactly_one_production_invocation -eq $true) 'review does not authorize exactly-once production dispatch' }
foreach ($path in @($resourcePath, $launchEvidencePath, $canonicalGatePath, $launcherRoot, $runtimeRoot)) { Require (-not (Test-Path -LiteralPath $path)) "v10 namespace/evidence already exists: $path" }
Require (@(Get-ChildItem -LiteralPath (Join-Path $bulkRoot 'runs') -Directory -Filter "$runPrefix*" -ErrorAction SilentlyContinue).Count -eq 0) 'v10 child namespace already exists'
& wsl.exe -d Ubuntu -- mountpoint -q $cacheMountTargetWsl 2>$null
Require ($LASTEXITCODE -ne 0) 'cache mount target is already mounted'
& wsl.exe -d Ubuntu -u root -- test -d $nativeStageWsl 2>$null
Require ($LASTEXITCODE -eq 0) 'native staged cache unavailable'
if ($ValidateStaticOnly) {
    [ordered]@{ status='validated_static_no_dispatch'; run_prefix=$runPrefix; protocol_sha256=$protocolSha256; dispatcher_sha256=$ApprovedDispatcherSha256.ToLowerInvariant(); launch_binding_sha256=$ApprovedLaunchBindingSha256.ToLowerInvariant(); independent_review_sha256=$ApprovedIndependentReviewSha256.ToLowerInvariant(); source_tree_sha256=$sourceTree.sha256; source_tree_file_count=$sourceTree.file_count; no_dispatch_marker_created=$true; no_training_started=$true } | ConvertTo-Json -Compress
    exit 0
}
& $resourceBuilder -OutputPath $resourcePath -MinPhysicalMemoryMb 1024 -MinCommitHeadroomMb 2048 -MinCFreeGiB 15 -MinEFreeGiB 15
Require ($LASTEXITCODE -eq 0) 'fresh resource gate refused dispatch'
$resource = Get-Content -LiteralPath $resourcePath -Raw | ConvertFrom-Json
Require ([string]$resource.status -eq 'pass' -and $resource.ready -eq $true) 'fresh resource evidence not passing'
$resourceSha = Get-Sha256 $resourcePath
$resourceAge = ([DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse([string]$resource.timestamp).ToUniversalTime()).TotalSeconds
Require ($resourceAge -ge 0 -and $resourceAge -le 30) 'fresh resource evidence too old'
$launchEvidence = [ordered]@{ schema_version=1; artifact_type='PLAN16_V10_ATOMIC_PRE_DISPATCH_LAUNCH_EVIDENCE_V1'; status='pass'; created_at_utc=[DateTime]::UtcNow.ToString('o'); run_prefix=$runPrefix; protocol_sha256=$protocolSha256; dispatcher_sha256=$ApprovedDispatcherSha256.ToLowerInvariant(); launch_binding_sha256=$ApprovedLaunchBindingSha256.ToLowerInvariant(); independent_review_sha256=$ApprovedIndependentReviewSha256.ToLowerInvariant(); resource_evidence_path=$resourcePath; resource_evidence_sha256=$resourceSha; resource_age_seconds=$resourceAge; source_tree_sha256=$sourceTree.sha256; source_tree_file_count=$sourceTree.file_count; python_source_binding_count=$sourceBindings.Count; python_source_bindings_match=$true; cap=64; epochs=12; selection_seed=43; model_seed=44; no_retry=$true; no_resume=$true; no_reuse=$true }
Write-JsonCreateOnly $launchEvidencePath $launchEvidence
$launchEvidenceSha = Get-Sha256 $launchEvidencePath
$gate = [ordered]@{ schema_version=1; artifact_type=$gateType; status='pass'; authorized_action='dispatch_exactly_once'; created_at_utc=[DateTime]::UtcNow.ToString('o'); run_prefix=$runPrefix; protocol_sha256=$protocolSha256; dispatcher_sha256=$ApprovedDispatcherSha256.ToLowerInvariant(); launch_binding_sha256=$ApprovedLaunchBindingSha256.ToLowerInvariant(); independent_review_sha256=$ApprovedIndependentReviewSha256.ToLowerInvariant(); resource_builder_sha256=$resourceBuilderSha256; resource_evidence_path=$resourcePath; resource_evidence_sha256=$resourceSha; launch_evidence_sha256=$launchEvidenceSha; resource_age_seconds=$resourceAge; source_tree_sha256=$sourceTree.sha256; source_tree_file_count=$sourceTree.file_count; python_source_binding_count=$sourceBindings.Count; python_source_bindings_match=$true; cap=64; epochs=12; selection_seed=43; model_seed=44; no_retry=$true; no_resume=$true; no_reuse=$true }
Write-JsonCreateOnly $canonicalGatePath $gate
$gateSha = Get-Sha256 $canonicalGatePath
$launchResult = & $launcherPath -RunPrefix $runPrefix -WslProjectRoot '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction' -WslBulkRoot '/mnt/e/blp/sleep_stage_reproduction' -WslCacheManifest '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json' -WslSourceManifest '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/manifests/source_manifest.json' -WslEnvironmentManifest '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/environment/results/wsl_tf24_probe.json' -WslRuntimeRoot "/mnt/e/blp/sleep_stage_reproduction/runtime/$runPrefix" -WslProtocolOutput "/mnt/e/blp/sleep_stage_reproduction/runtime/protocols/$runPrefix.json" -WslResourceEvidence '/mnt/e/blp/sleep_stage_reproduction/runtime/resource-preflight/plan16-v10-dispatch-preflight-v1-20261006.json' -WslReceipt $compactReceiptWsl -NativeStageWsl $nativeStageWsl -CacheMountTargetWsl $cacheMountTargetWsl -ApprovedProtocolSha256 $protocolSha256 -ResourceProfile 'QUALITY_BALANCED_CAP64_E12_V1_FRESH_STAGE_WAIT_DRAIN' -SupervisorPath $supervisorPath -WslDistribution 'Ubuntu' -BulkRoot $bulkRoot -LauncherIdPrefix $launcherIdPrefix -Cap 64 -Epochs 12 -SelectionSeed 43 -ModelSeed 44 -WslLabelEvidenceReceipt $labelReceiptWsl -ApprovedLauncherSha256 $launcherSha256 -ApprovedSupervisorSha256 $supervisorSha256 -LaunchBindingPath $bindingFull -ApprovedLaunchBindingSha256 $ApprovedLaunchBindingSha256.ToLowerInvariant() -CanonicalGatePath $canonicalGatePath -ExpectedCanonicalGateArtifactType $gateType -ApprovedCanonicalGateSha256 $gateSha -IndependentReviewPath $reviewFull -ApprovedIndependentReviewSha256 $ApprovedIndependentReviewSha256.ToLowerInvariant() -ApprovedDispatcherSha256 $ApprovedDispatcherSha256.ToLowerInvariant() -ApprovedResourceBuilderSha256 $resourceBuilderSha256
Require ($LASTEXITCODE -eq 0) 'v10 launcher refused or failed'
[ordered]@{ status='started'; run_prefix=$runPrefix; resource_evidence_sha256=$resourceSha; launch_evidence_sha256=$launchEvidenceSha; canonical_gate_sha256=$gateSha; launcher_output=($launchResult | Out-String).Trim() } | ConvertTo-Json -Compress
