param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedDispatcherSha256,
    [Parameter(Mandatory = $true)][string]$LaunchBindingPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedLaunchBindingSha256,
    [Parameter(Mandatory = $true)][string]$IndependentReviewPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedIndependentReviewSha256,
    [switch]$ValidateStaticOnly
)

$ErrorActionPreference = 'Stop'
$runPrefix = 'subject-generalization-quality-plan16-v7-cap64-e12-seed43-20261006'
$protocolSha256 = '03a9db76d7fedd14083a14b431321aa7ff829a22a14f919be18a4c4355bf7c8f'
$launcherSha256 = '98c691a1d0f25b0827a5b8a1842cef73314ec86d8583703896d0f19996862361'
$supervisorSha256 = '90cb819366fa4b9977d3307ab09f765dd1655140bb5460ea8e54a68cb0de8b93'
$resourceBuilderSha256 = 'c8e26cbc3e7cd416bc0034d4870ffb830e82ad33ac24b8b237dee90a18d7cf0f'
$launcherIdPrefix = 'subject-generalization-plan16-quality-native-cache'
$resourceProfile = 'QUALITY_BALANCED_CAP64_E12_V1_FRESH_STAGE_WAIT_DRAIN'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$bulkRoot = 'E:\blp\sleep_stage_reproduction'
$launcherPath = Join-Path $PSScriptRoot 'launch_native_cache_subject_run_v5.ps1'
$supervisorPath = Join-Path $PSScriptRoot 'native_cache_subject_supervisor.ps1'
$resourceBuilder = Join-Path $PSScriptRoot 'tests\build_subject_generalization_resource_evidence.ps1'
$protocolPath = Join-Path $bulkRoot "runtime\protocols\$runPrefix.json"
$resourcePath = Join-Path $bulkRoot 'runtime\resource-preflight\plan16-v7-dispatch-preflight-v1-20261006.json'
$launchEvidencePath = Join-Path $bulkRoot 'runtime\reviews\plan16-v7-launch-evidence-v1-20261006.json'
$canonicalGatePath = Join-Path $bulkRoot 'runtime\reviews\plan16-v7-canonical-gate-v1-20261006.json'
$launcherRoot = Join-Path $bulkRoot "runtime\driver-recovery\$launcherIdPrefix-$runPrefix"
$runtimeRoot = Join-Path $bulkRoot "runtime\$runPrefix"
$labelReceiptWsl = '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/full-cache-validation-receipt-plan2c-prior-20261005.json'
$nativeStageWsl = '/home/techatat/subject-generalization-plan16-quality-cap64-native-cache-v2-20261006'
$cacheMountTargetWsl = '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-DeterministicSourceTree([string]$Root) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $rootFull -PathType Container)) { throw "source tree root missing: $rootFull" }
    $relativePaths = [Collections.Generic.List[string]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $rootFull -Recurse -File -Force) {
        $relative = [IO.Path]::GetRelativePath($rootFull, $file.FullName).Replace('\', '/')
        if (("/$relative/") -match '/__pycache__/' -or $relative.EndsWith('.pyc', [StringComparison]::OrdinalIgnoreCase)) { continue }
        [void]$relativePaths.Add($relative)
    }
    $relativePaths.Sort([StringComparer]::Ordinal)
    $manifest = [Text.StringBuilder]::new()
    foreach ($relative in $relativePaths) {
        $fullPath = Join-Path $rootFull $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
        [void]$manifest.Append($relative).Append("`t").Append((Get-Sha256 $fullPath)).Append("`n")
    }
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($manifest.ToString())
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $treeSha256 = ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() } finally { $hasher.Dispose() }
    return [pscustomobject]@{ root=$rootFull; file_count=$relativePaths.Count; sha256=$treeSha256 }
}

function Resolve-LogicalSourcePath([string]$LogicalPath) {
    if ([string]::IsNullOrWhiteSpace($LogicalPath) -or $LogicalPath.Contains('\\') -or $LogicalPath.StartsWith('/')) {
        throw "invalid logical source path: $LogicalPath"
    }
    $parts = @($LogicalPath.Split('/'))
    if ($parts.Count -lt 3 -or $parts[0] -ne 'paper_faithful' -or $parts[1] -ne 'training' -or -not $LogicalPath.EndsWith('.py', [StringComparison]::Ordinal)) {
        throw "logical source path is outside paper_faithful/training: $LogicalPath"
    }
    if (@($parts | Where-Object { [string]::IsNullOrWhiteSpace($_) -or $_ -eq '.' -or $_ -eq '..' }).Count) {
        throw "logical source path contains unsafe components: $LogicalPath"
    }
    $candidate = [IO.Path]::GetFullPath((Join-Path $projectRoot $LogicalPath.Replace('/', [IO.Path]::DirectorySeparatorChar)))
    $rootPrefix = $projectRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "logical source path escaped project root: $LogicalPath"
    }
    return $candidate
}

function Write-JsonCreateOnly([string]$Path, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 20
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}

$dispatcherPath = [IO.Path]::GetFullPath($PSCommandPath)
if ((Get-Sha256 $dispatcherPath) -ne $ApprovedDispatcherSha256.ToLowerInvariant()) { throw 'atomic dispatcher SHA-256 mismatch' }
if ((Get-Sha256 $launcherPath) -ne $launcherSha256) { throw 'launcher SHA-256 changed after review' }
if ((Get-Sha256 $supervisorPath) -ne $supervisorSha256) { throw 'supervisor SHA-256 changed after review' }
if ((Get-Sha256 $protocolPath) -ne $protocolSha256) { throw 'Plan16 v7 protocol SHA-256 mismatch' }
if ((Get-Sha256 $resourceBuilder) -ne $resourceBuilderSha256) { throw 'resource-evidence builder SHA-256 changed after review' }
$protocol = Get-Content -LiteralPath $protocolPath -Raw | ConvertFrom-Json
$sourceTree = Get-DeterministicSourceTree (Join-Path $projectRoot 'paper_faithful')
$pythonSourceBindings = @($protocol.source_code_binding.PSObject.Properties)
if ($pythonSourceBindings.Count -ne 7) { throw "expected seven Python source bindings; got $($pythonSourceBindings.Count)" }
$pythonSourceResults = @()
foreach ($bindingProperty in $pythonSourceBindings) {
    $propertyNames = @($bindingProperty.Value.PSObject.Properties.Name)
    if ($propertyNames.Count -ne 2 -or $propertyNames -notcontains 'logical_path' -or $propertyNames -notcontains 'sha256') {
        throw "bound Python source schema mismatch: $($bindingProperty.Name)"
    }
    $logicalPath = [string]$bindingProperty.Value.logical_path
    $windowsSource = Resolve-LogicalSourcePath $logicalPath
    if (-not (Test-Path -LiteralPath $windowsSource -PathType Leaf)) { throw "bound Python source is missing: $windowsSource" }
    $actualSourceSha256 = Get-Sha256 $windowsSource
    if ($actualSourceSha256 -ne [string]$bindingProperty.Value.sha256) { throw "bound Python source SHA-256 mismatch: $($bindingProperty.Name)" }
    $pythonSourceResults += [ordered]@{ name=$bindingProperty.Name; logical_path=$logicalPath; path=$windowsSource; sha256=$actualSourceSha256 }
}
$launchBindingFullPath = [IO.Path]::GetFullPath($LaunchBindingPath)
$actualLaunchBindingSha256 = Get-Sha256 $launchBindingFullPath
if ($actualLaunchBindingSha256 -ne $ApprovedLaunchBindingSha256.ToLowerInvariant()) { throw 'launch-binding SHA-256 mismatch' }
$reviewFullPath = [IO.Path]::GetFullPath($IndependentReviewPath)
$actualIndependentReviewSha256 = Get-Sha256 $reviewFullPath
if ($actualIndependentReviewSha256 -ne $ApprovedIndependentReviewSha256.ToLowerInvariant()) { throw 'independent-review SHA-256 mismatch' }
$binding = Get-Content -LiteralPath $launchBindingFullPath -Raw | ConvertFrom-Json
$review = Get-Content -LiteralPath $reviewFullPath -Raw | ConvertFrom-Json
if ([string]$binding.run_prefix -ne $runPrefix -or [string]$binding.protocol_sha256 -ne $protocolSha256) { throw 'launch-binding run/protocol mismatch' }
if ([string]$binding.dispatcher_sha256 -ne $ApprovedDispatcherSha256.ToLowerInvariant()) { throw 'launch-binding dispatcher SHA-256 mismatch' }
if ([string]$binding.resource_builder_sha256 -ne $resourceBuilderSha256) { throw 'launch-binding resource-builder SHA-256 mismatch' }
if ([string]$binding.source_tree_sha256 -ne $sourceTree.sha256 -or [int]$binding.source_tree_file_count -ne $sourceTree.file_count) { throw 'launch-binding source-tree mismatch' }
if ([string]$binding.expected_canonical_gate_artifact_type -ne 'PLAN16_V7_ATOMIC_CANONICAL_LAUNCH_GATE_V1') { throw 'launch-binding expected canonical-gate artifact type mismatch' }
if ([string]$review.status -ne 'pass' -or @($review.findings.P0).Count -or @($review.findings.P1).Count -or @($review.findings.P2).Count) { throw 'independent review is not launch-approved' }
if ([string]$review.run_prefix -ne $runPrefix) { throw 'independent-review run_prefix mismatch' }
if ([string]$review.protocol_sha256 -ne $protocolSha256) { throw 'independent-review protocol SHA-256 mismatch' }
if ([string]$review.launch_binding_sha256 -ne $actualLaunchBindingSha256) { throw 'independent-review launch-binding SHA-256 mismatch' }
if ([string]$review.dispatcher_sha256 -ne $ApprovedDispatcherSha256.ToLowerInvariant()) { throw 'independent-review dispatcher SHA-256 mismatch' }
if ($ValidateStaticOnly) {
    if ([string]$review.authorization.authorized_action -ne 'validate_static_only_exactly_once' -or
        $review.authorization.production_dispatch_authorized -ne $false -or
        $review.authorization.no_training_authorized -ne $true) {
        throw 'independent review does not authorize static-only validation'
    }
} else {
    if ([string]$review.authorization.authorized_action -ne 'dispatch_exactly_once' -or
        $review.authorization.production_dispatch_authorized -ne $true -or
        $review.authorization.exactly_one_production_invocation -ne $true) {
        throw 'independent review does not authorize exactly-one production dispatch'
    }
}

foreach ($path in @($resourcePath, $launchEvidencePath, $canonicalGatePath, $launcherRoot, $runtimeRoot)) {
    if (Test-Path -LiteralPath $path) { throw "Plan16 v7 namespace or evidence already exists: $path" }
}
$children = @(Get-ChildItem -LiteralPath (Join-Path $bulkRoot 'runs') -Directory -Filter "$runPrefix*" -ErrorAction SilentlyContinue)
if ($children.Count) { throw 'Plan16 v7 child namespace already exists' }
& wsl.exe -d Ubuntu -- mountpoint -q $cacheMountTargetWsl 2>&1
if ($LASTEXITCODE -eq 0) { throw 'cache mount target is already mounted' }
& wsl.exe -d Ubuntu -u root -- test -d $nativeStageWsl 2>&1
if ($LASTEXITCODE -ne 0) { throw 'native cache stage is unavailable' }
if ($ValidateStaticOnly) {
    [pscustomobject]@{
        status = 'validated_static_no_dispatch'
        run_prefix = $runPrefix
        protocol_sha256 = $protocolSha256
        dispatcher_sha256 = $ApprovedDispatcherSha256.ToLowerInvariant()
        launch_binding_sha256 = $ApprovedLaunchBindingSha256.ToLowerInvariant()
        independent_review_sha256 = $ApprovedIndependentReviewSha256.ToLowerInvariant()
        namespace_clear = $true
        resource_builder_sha256 = $resourceBuilderSha256
        python_source_binding_count = $pythonSourceResults.Count
        python_source_bindings_match = $true
        source_tree_sha256 = $sourceTree.sha256
        source_tree_file_count = $sourceTree.file_count
        no_resource_evidence_created = $true
        no_dispatch_marker_created = $true
        no_training_started = $true
    } | ConvertTo-Json -Compress
    exit 0
}

& $resourceBuilder -OutputPath $resourcePath -MinPhysicalMemoryMb 1024 -MinCommitHeadroomMb 2048 -MinCFreeGiB 15 -MinEFreeGiB 15
if ($LASTEXITCODE -ne 0) { throw 'fresh resource gate refused dispatch' }
$resource = Get-Content -LiteralPath $resourcePath -Raw | ConvertFrom-Json
if ([string]$resource.status -ne 'pass' -or $resource.ready -ne $true) { throw 'fresh resource evidence is not passing' }
$resourceSha256 = Get-Sha256 $resourcePath
$resourceCaptured = [DateTimeOffset]::Parse([string]$resource.timestamp)
$resourceAgeSeconds = ([DateTimeOffset]::UtcNow - $resourceCaptured.ToUniversalTime()).TotalSeconds
if ($resourceAgeSeconds -lt 0 -or $resourceAgeSeconds -gt 30) { throw "fresh resource evidence already too old: $resourceAgeSeconds seconds" }

$launchEvidence = [ordered]@{
    schema_version = 1
    artifact_type = 'PLAN16_V7_ATOMIC_PRE_DISPATCH_LAUNCH_EVIDENCE_V1'
    status = 'pass'
    created_at_utc = [DateTime]::UtcNow.ToString('o')
    run_prefix = $runPrefix
    protocol_sha256 = $protocolSha256
    dispatcher_sha256 = $ApprovedDispatcherSha256.ToLowerInvariant()
    launch_binding_sha256 = $ApprovedLaunchBindingSha256.ToLowerInvariant()
    independent_review_sha256 = $ApprovedIndependentReviewSha256.ToLowerInvariant()
    resource_builder_sha256 = $resourceBuilderSha256
    resource_evidence_path = $resourcePath
    resource_evidence_sha256 = $resourceSha256
    resource_age_seconds = $resourceAgeSeconds
    namespace_clear = $true
    python_source_binding_count = $pythonSourceResults.Count
    python_source_bindings_match = $true
    source_tree_sha256 = $sourceTree.sha256
    source_tree_file_count = $sourceTree.file_count
    cap = 64
    epochs = 12
    launcher_id_prefix = $launcherIdPrefix
    resource_profile = $resourceProfile
    no_retry = $true
    no_resume = $true
    no_reuse = $true
}
Write-JsonCreateOnly $launchEvidencePath $launchEvidence
$launchEvidenceSha256 = Get-Sha256 $launchEvidencePath
$canonicalGate = [ordered]@{
    schema_version = 1
    artifact_type = 'PLAN16_V7_ATOMIC_CANONICAL_LAUNCH_GATE_V1'
    status = 'pass'
    authorized_action = 'dispatch_exactly_once'
    created_at_utc = [DateTime]::UtcNow.ToString('o')
    run_prefix = $runPrefix
    protocol_sha256 = $protocolSha256
    dispatcher_sha256 = $ApprovedDispatcherSha256.ToLowerInvariant()
    launch_binding_sha256 = $ApprovedLaunchBindingSha256.ToLowerInvariant()
    independent_review_sha256 = $ApprovedIndependentReviewSha256.ToLowerInvariant()
    resource_builder_sha256 = $resourceBuilderSha256
    resource_evidence_sha256 = $resourceSha256
    resource_evidence_path = $resourcePath
    launch_evidence_sha256 = $launchEvidenceSha256
    resource_age_limit_seconds = 120
    resource_age_at_gate_seconds = $resourceAgeSeconds
    python_source_binding_count = $pythonSourceResults.Count
    python_source_bindings_match = $true
    source_tree_sha256 = $sourceTree.sha256
    source_tree_file_count = $sourceTree.file_count
    cap = 64
    epochs = 12
    no_retry = $true
    no_resume = $true
    no_reuse = $true
}
Write-JsonCreateOnly $canonicalGatePath $canonicalGate
$canonicalGateSha256 = Get-Sha256 $canonicalGatePath
$resourceAgeBeforeDispatch = ([DateTimeOffset]::UtcNow - $resourceCaptured.ToUniversalTime()).TotalSeconds
if ($resourceAgeBeforeDispatch -gt 45) { throw "resource evidence too old before dispatch: $resourceAgeBeforeDispatch seconds" }

$launchResult = & $launcherPath `
    -RunPrefix $runPrefix `
    -WslProjectRoot '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction' `
    -WslBulkRoot '/mnt/e/blp/sleep_stage_reproduction' `
    -WslCacheManifest '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json' `
    -WslSourceManifest '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/manifests/source_manifest.json' `
    -WslEnvironmentManifest '/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction/paper_faithful/environment/results/wsl_tf24_probe.json' `
    -WslRuntimeRoot "/mnt/e/blp/sleep_stage_reproduction/runtime/$runPrefix" `
    -WslProtocolOutput "/mnt/e/blp/sleep_stage_reproduction/runtime/protocols/$runPrefix.json" `
    -WslResourceEvidence '/mnt/e/blp/sleep_stage_reproduction/runtime/resource-preflight/plan16-v7-dispatch-preflight-v1-20261006.json' `
    -WslReceipt '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/compact-selection-plan16-cohort6-cap64-balanced-metadata-20261005.json' `
    -NativeStageWsl $nativeStageWsl `
    -CacheMountTargetWsl $cacheMountTargetWsl `
    -ApprovedProtocolSha256 $protocolSha256 `
    -ResourceProfile $resourceProfile `
    -SupervisorPath $supervisorPath `
    -WslDistribution 'Ubuntu' `
    -BulkRoot $bulkRoot `
    -LauncherIdPrefix $launcherIdPrefix `
    -Cap 64 `
    -Epochs 12 `
    -WslLabelEvidenceReceipt $labelReceiptWsl `
    -ApprovedLauncherSha256 $launcherSha256 `
    -ApprovedSupervisorSha256 $supervisorSha256 `
    -LaunchBindingPath $launchBindingFullPath `
    -ApprovedLaunchBindingSha256 $ApprovedLaunchBindingSha256.ToLowerInvariant() `
    -CanonicalGatePath $canonicalGatePath `
    -ExpectedCanonicalGateArtifactType 'PLAN16_V7_ATOMIC_CANONICAL_LAUNCH_GATE_V1' `
    -ApprovedCanonicalGateSha256 $canonicalGateSha256 `
    -IndependentReviewPath $reviewFullPath `
    -ApprovedIndependentReviewSha256 $ApprovedIndependentReviewSha256.ToLowerInvariant() `
    -ApprovedDispatcherSha256 $ApprovedDispatcherSha256.ToLowerInvariant() `
    -ApprovedResourceBuilderSha256 $resourceBuilderSha256
if ($LASTEXITCODE -ne 0) { throw 'Plan16 v7 launcher failed' }
[pscustomobject]@{
    status = 'started'
    run_prefix = $runPrefix
    resource_evidence_sha256 = $resourceSha256
    resource_age_before_dispatch_seconds = $resourceAgeBeforeDispatch
    launch_evidence_sha256 = $launchEvidenceSha256
    canonical_gate_sha256 = $canonicalGateSha256
    launcher_output = ($launchResult | Out-String).Trim()
} | ConvertTo-Json -Compress







