param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedDispatcherSha256,
    [Parameter(Mandatory = $true)][string]$LaunchBindingPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedLaunchBindingSha256,
    [Parameter(Mandatory = $true)][string]$IndependentReviewPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedIndependentReviewSha256,
    [switch]$ValidateStaticOnly
)

$ErrorActionPreference = 'Stop'
$runPrefix = 'subject-generalization-quality-plan16-v13-cap64-e12-cohort43-model45-20261006'
$protocolSha256 = '17132e5fd9b619bc98f9bed9c3c8da6c5728fe00a36cb8d4e57b5064235dec92'
$launcherSha256 = '0ce73695dc76c2e1083c8c53d0a1caebbea7db9b76c7c1697e6fd0c97b31b632'
$supervisorSha256 = 'c05bc3e3c6108a7559467a0dfa704031feda7cc2bdf657441fcd1794e4bf3b35'
$resourceBuilderSha256 = 'c8e26cbc3e7cd416bc0034d4870ffb830e82ad33ac24b8b237dee90a18d7cf0f'
$resourceProfile = 'QUALITY_BALANCED_CAP64_E12_V2_CONSERVATIVE_STAGE3_SGD'
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$launcherPath = Join-Path $PSScriptRoot 'launch_native_cache_subject_run_v6.ps1'
$supervisorPath = Join-Path $PSScriptRoot 'native_cache_subject_supervisor_v2.ps1'
$resourceBuilder = Join-Path $PSScriptRoot 'tests\build_subject_generalization_resource_evidence.ps1'
$protocolPath = Join-Path $bulkRoot "runtime\protocols\$runPrefix.json"
$resourcePath = Join-Path $bulkRoot 'runtime\resource-preflight\plan16-v13-dispatch-preflight-v1-c12gib-20261006.json'
$launchEvidencePath = Join-Path $bulkRoot 'runtime\reviews\plan16-v13-launch-evidence-v1-20261006.json'
$canonicalGatePath = Join-Path $bulkRoot 'runtime\reviews\plan16-v13-canonical-gate-v1-20261006.json'
$launcherIdPrefix = 'subject-generalization-plan16-quality-native-cache'
$launcherRoot = Join-Path $bulkRoot "runtime\driver-recovery\$launcherIdPrefix-$runPrefix"
$runtimeRoot = Join-Path $bulkRoot "runtime\$runPrefix"
$compactReceiptPath = Join-Path $bulkRoot 'runtime\integrity-receipts\compact-selection-plan16-seed43-cohort6-cap64-balanced-v1-20261006.json'
$compactReceiptWsl = '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/compact-selection-plan16-seed43-cohort6-cap64-balanced-v1-20261006.json'
$compactReceiptSha256 = '4960d33b64a1acaefd44de99047c4a6180c1b475ebac07b4abb5eddb86ec0613'
$labelReceiptWsl = '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/full-cache-validation-receipt-plan2c-prior-20261005.json'
$nativeStageEvidencePath = Join-Path $bulkRoot 'runtime\integrity-receipts\plan16-seed43-native-stage-v3-20261006.json'
$nativeStageEvidenceSha256 = '0f153cc1e5ed03b49f0ca367550dba74bd8bee9800cf240c35fae565563366d1'
$loaderCanaryPath = Join-Path $bulkRoot 'runtime\validation\plan16-v13-seed43-model45-native-loader-canary-v1-20261006.json'
$loaderCanarySha256 = 'c2611e2317411364e737c3d0acf642ff02ff1f485090274133ae233daf59b290'
$nativeStageWsl = '/home/techatat/subject-generalization-plan16-quality-cap64-native-cache-v3-seed43-20261006'
$cacheMountTargetWsl = '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820'

function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Write-JsonCreateOnly([string]$Path, [object]$Value) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Depth 20) + "`n")
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
}
function Get-SourceTree([string]$Root) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    $items = foreach ($file in Get-ChildItem -LiteralPath $rootFull -Recurse -File -Force) {
        $rel = [IO.Path]::GetRelativePath($rootFull, $file.FullName).Replace('\', '/')
        if (("/$rel/") -notmatch '/__pycache__/' -and -not $rel.EndsWith('.pyc')) {
            [pscustomobject]@{ rel=$rel; sha=(Get-Sha256 $file.FullName) }
        }
    }
    $items = @($items | Sort-Object rel)
    $text = (($items | ForEach-Object { "$($_.rel)`t$($_.sha)" }) -join "`n") + "`n"
    $hash = [Security.Cryptography.SHA256]::HashData([Text.UTF8Encoding]::new($false).GetBytes($text))
    [pscustomobject]@{ sha256=([Convert]::ToHexString($hash)).ToLowerInvariant(); file_count=$items.Count }
}

$dispatcherPath = [IO.Path]::GetFullPath($PSCommandPath)
if ((Get-Sha256 $dispatcherPath) -ne $ApprovedDispatcherSha256.ToLowerInvariant()) { throw 'dispatcher SHA-256 mismatch' }
foreach ($pair in @(@($launcherPath,$launcherSha256), @($supervisorPath,$supervisorSha256), @($resourceBuilder,$resourceBuilderSha256), @($protocolPath,$protocolSha256), @($compactReceiptPath,$compactReceiptSha256), @($nativeStageEvidencePath,$nativeStageEvidenceSha256), @($loaderCanaryPath,$loaderCanarySha256))) {
    if (-not (Test-Path -LiteralPath $pair[0] -PathType Leaf) -or (Get-Sha256 $pair[0]) -ne $pair[1]) { throw "reviewed input mismatch: $($pair[0])" }
}
$protocol = Get-Content -LiteralPath $protocolPath -Raw | ConvertFrom-Json
if ([string]$protocol.run_prefix -ne $runPrefix -or [string]$protocol.resource_profile -ne $resourceProfile -or [int]$protocol.selection_seed -ne 43 -or [int]$protocol.model_seed -ne 45 -or [int]$protocol.cap -ne 64 -or [int]$protocol.stage_epochs -ne 12) { throw 'protocol identity mismatch' }
if ([string]$protocol.cache_validation_receipt -ne $compactReceiptWsl) { throw 'protocol compact receipt binding mismatch' }
$canary = Get-Content -LiteralPath $loaderCanaryPath -Raw | ConvertFrom-Json
if ([string]$canary.status -ne 'pass' -or [string]$canary.run_prefix -ne $runPrefix -or [string]$canary.protocol_sha256 -ne $protocolSha256 -or [string]$canary.resource_profile -ne $resourceProfile -or $canary.no_training_started -ne $true -or $canary.runtime_created -ne $false -or $canary.unmounted_after_test -ne $true) { throw 'loader canary mismatch' }
$stageEvidence = Get-Content -LiteralPath $nativeStageEvidencePath -Raw | ConvertFrom-Json
if ([string]$stageEvidence.status -ne 'pass' -or $stageEvidence.all_digests_verified -ne $true -or $stageEvidence.source_cache_untouched -ne $true) { throw 'native cache stage evidence mismatch' }
$sourceTree = Get-SourceTree (Join-Path $projectRoot 'paper_faithful')
$bindings = @($protocol.source_code_binding.PSObject.Properties)
if ($bindings.Count -ne 7) { throw 'protocol source binding count mismatch' }
foreach ($entry in $bindings) {
    $path = Join-Path $projectRoot ([string]$entry.Value.logical_path).Replace('/', '\')
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Sha256 $path) -ne [string]$entry.Value.sha256) { throw "Python source binding mismatch: $($entry.Name)" }
}
$bindingSha = Get-Sha256 ([IO.Path]::GetFullPath($LaunchBindingPath))
$reviewSha = Get-Sha256 ([IO.Path]::GetFullPath($IndependentReviewPath))
if ($bindingSha -ne $ApprovedLaunchBindingSha256.ToLowerInvariant() -or $reviewSha -ne $ApprovedIndependentReviewSha256.ToLowerInvariant()) { throw 'review artifact SHA mismatch' }
$binding = Get-Content -LiteralPath $LaunchBindingPath -Raw | ConvertFrom-Json
$review = Get-Content -LiteralPath $IndependentReviewPath -Raw | ConvertFrom-Json
if ([string]$binding.status -ne 'pass' -or [string]$binding.run_prefix -ne $runPrefix -or [string]$binding.protocol_sha256 -ne $protocolSha256 -or [string]$binding.dispatcher_sha256 -ne $ApprovedDispatcherSha256.ToLowerInvariant() -or [string]$binding.resource_profile -ne $resourceProfile -or [string]$binding.source_tree_sha256 -ne $sourceTree.sha256 -or [int]$binding.source_tree_file_count -ne $sourceTree.file_count -or [string]$binding.expected_canonical_gate_artifact_type -ne 'PLAN16_V13_ATOMIC_CANONICAL_LAUNCH_GATE_V1') { throw 'launch binding content mismatch' }
if ([string]$review.status -ne 'pass' -or @($review.findings.P0).Count -or @($review.findings.P1).Count -or @($review.findings.P2).Count -or [string]$review.run_prefix -ne $runPrefix -or [string]$review.protocol_sha256 -ne $protocolSha256 -or [string]$review.launch_binding_sha256 -ne $bindingSha -or [string]$review.dispatcher_sha256 -ne $ApprovedDispatcherSha256.ToLowerInvariant()) { throw 'independent review content mismatch' }
foreach ($path in @($resourcePath,$launchEvidencePath,$canonicalGatePath,$launcherRoot,$runtimeRoot)) { if (Test-Path -LiteralPath $path) { throw "fresh namespace already exists: $path" } }
if (@(Get-ChildItem -LiteralPath (Join-Path $bulkRoot 'runs') -Directory -Filter "$runPrefix*" -ErrorAction SilentlyContinue).Count) { throw 'child namespace already exists' }
& wsl.exe -d Ubuntu -- mountpoint -q $cacheMountTargetWsl 2>&1
if ($LASTEXITCODE -eq 0) { throw 'cache mount target already mounted' }
& wsl.exe -d Ubuntu -u root -- test -d $nativeStageWsl 2>&1
if ($LASTEXITCODE -ne 0) { throw 'native cache stage unavailable' }
if ($ValidateStaticOnly) {
    [pscustomobject]@{status='validated_static_no_dispatch';run_prefix=$runPrefix;protocol_sha256=$protocolSha256;dispatcher_sha256=$ApprovedDispatcherSha256.ToLowerInvariant();launch_binding_sha256=$bindingSha;independent_review_sha256=$reviewSha;source_tree_sha256=$sourceTree.sha256;source_tree_file_count=$sourceTree.file_count;namespace_clear=$true;no_training_started=$true} | ConvertTo-Json -Compress
    exit 0
}
& $resourceBuilder -OutputPath $resourcePath -MinPhysicalMemoryMb 1024 -MinCommitHeadroomMb 2048 -MinCFreeGiB 12 -MinEFreeGiB 15
if ($LASTEXITCODE -ne 0) { throw 'fresh resource evidence builder failed' }
$resource = Get-Content -LiteralPath $resourcePath -Raw | ConvertFrom-Json
if ([string]$resource.status -ne 'pass' -or $resource.ready -ne $true) { throw 'fresh resource gate refused dispatch' }
$captured = [DateTimeOffset]::Parse([string]$resource.timestamp)
$age = ([DateTimeOffset]::UtcNow - $captured.ToUniversalTime()).TotalSeconds
if ($age -lt 0 -or $age -gt 30) { throw "resource evidence too old: $age" }
$resourceSha = Get-Sha256 $resourcePath
$launchEvidence = [ordered]@{schema_version=1;artifact_type='PLAN16_V13_ATOMIC_PRE_DISPATCH_LAUNCH_EVIDENCE_V1';status='pass';created_at_utc=[DateTime]::UtcNow.ToString('o');run_prefix=$runPrefix;protocol_sha256=$protocolSha256;dispatcher_sha256=$ApprovedDispatcherSha256.ToLowerInvariant();launch_binding_sha256=$bindingSha;independent_review_sha256=$reviewSha;resource_evidence_path=$resourcePath;resource_evidence_sha256=$resourceSha;resource_age_seconds=$age;source_tree_sha256=$sourceTree.sha256;source_tree_file_count=$sourceTree.file_count;cap=64;epochs=12;selection_seed=43;model_seed=45;resource_profile=$resourceProfile;no_retry=$true;no_resume=$true;no_reuse=$true}
Write-JsonCreateOnly $launchEvidencePath $launchEvidence
$launchEvidenceSha = Get-Sha256 $launchEvidencePath
$gate = [ordered]@{schema_version=1;artifact_type='PLAN16_V13_ATOMIC_CANONICAL_LAUNCH_GATE_V1';status='pass';authorized_action='dispatch_exactly_once';created_at_utc=[DateTime]::UtcNow.ToString('o');run_prefix=$runPrefix;protocol_sha256=$protocolSha256;dispatcher_sha256=$ApprovedDispatcherSha256.ToLowerInvariant();launch_binding_sha256=$bindingSha;independent_review_sha256=$reviewSha;resource_builder_sha256=$resourceBuilderSha256;resource_evidence_path=$resourcePath;resource_evidence_sha256=$resourceSha;launch_evidence_sha256=$launchEvidenceSha;python_source_binding_count=$bindings.Count;python_source_bindings_match=$true;source_tree_sha256=$sourceTree.sha256;source_tree_file_count=$sourceTree.file_count;cap=64;epochs=12;selection_seed=43;model_seed=45;resource_profile=$resourceProfile;no_retry=$true;no_resume=$true;no_reuse=$true}
Write-JsonCreateOnly $canonicalGatePath $gate
$gateSha = Get-Sha256 $canonicalGatePath
& $launcherPath -RunPrefix $runPrefix -WslProjectRoot '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction' -WslBulkRoot '/mnt/e/blp/sleep_stage_reproduction' -WslCacheManifest '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json' -WslSourceManifest '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/manifests/source_manifest.json' -WslEnvironmentManifest '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/environment/results/wsl_tf24_probe.json' -WslRuntimeRoot "/mnt/e/blp/sleep_stage_reproduction/runtime/$runPrefix" -WslProtocolOutput "/mnt/e/blp/sleep_stage_reproduction/runtime/protocols/$runPrefix.json" -WslResourceEvidence "/mnt/e/blp/sleep_stage_reproduction/runtime/resource-preflight/plan16-v13-dispatch-preflight-v1-c12gib-20261006.json" -WslReceipt $compactReceiptWsl -NativeStageWsl $nativeStageWsl -CacheMountTargetWsl $cacheMountTargetWsl -ApprovedProtocolSha256 $protocolSha256 -ResourceProfile $resourceProfile -SupervisorPath $supervisorPath -BulkRoot $bulkRoot -LauncherIdPrefix $launcherIdPrefix -Cap 64 -Epochs 12 -SelectionSeed 43 -ModelSeed 45 -WslLabelEvidenceReceipt $labelReceiptWsl -ApprovedLauncherSha256 $launcherSha256 -ApprovedSupervisorSha256 $supervisorSha256 -LaunchBindingPath $LaunchBindingPath -ApprovedLaunchBindingSha256 $bindingSha -CanonicalGatePath $canonicalGatePath -ExpectedCanonicalGateArtifactType 'PLAN16_V13_ATOMIC_CANONICAL_LAUNCH_GATE_V1' -ApprovedCanonicalGateSha256 $gateSha -IndependentReviewPath $IndependentReviewPath -ApprovedIndependentReviewSha256 $reviewSha -ApprovedDispatcherSha256 $ApprovedDispatcherSha256 -ApprovedResourceBuilderSha256 $resourceBuilderSha256
if ($LASTEXITCODE -ne 0) { throw 'v13 locked launcher failed' }
[pscustomobject]@{status='started';run_prefix=$runPrefix;launch_evidence_sha256=$launchEvidenceSha;canonical_gate_sha256=$gateSha} | ConvertTo-Json -Compress
