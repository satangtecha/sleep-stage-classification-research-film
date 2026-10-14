param(
    [Parameter(Mandatory = $true)][string]$RunPrefix,
    [Parameter(Mandatory = $true)][string]$WslProjectRoot,
    [Parameter(Mandatory = $true)][string]$WslBulkRoot,
    [Parameter(Mandatory = $true)][string]$WslCacheManifest,
    [Parameter(Mandatory = $true)][string]$WslSourceManifest,
    [Parameter(Mandatory = $true)][string]$WslEnvironmentManifest,
    [Parameter(Mandatory = $true)][string]$WslRuntimeRoot,
    [Parameter(Mandatory = $true)][string]$WslProtocolOutput,
    [Parameter(Mandatory = $true)][string]$WslResourceEvidence,
    [Parameter(Mandatory = $true)][string]$WslReceipt,
    [Parameter(Mandatory = $true)][string]$NativeStageWsl,
    [Parameter(Mandatory = $true)][string]$CacheMountTargetWsl,
    [Parameter(Mandatory = $true)][string]$ApprovedProtocolSha256,
    [Parameter(Mandatory = $true)][string]$ResourceProfile,
    [Parameter(Mandatory = $true)][string]$SupervisorPath,
    [string]$WslDistribution = 'Ubuntu',
    [string]$BulkRoot = 'E:\blp\sleep_stage_reproduction',
    [string]$LauncherIdPrefix = 'subject-generalization-plan16-quality-native-cache',
    [ValidateRange(1, 1000000)][int]$Cap = 32,
    [ValidateRange(1, 10000)][int]$Epochs = 6,
    [string]$WslLabelEvidenceReceipt,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedLauncherSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedSupervisorSha256,
    [Parameter(Mandatory = $true)][string]$LaunchBindingPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedLaunchBindingSha256,
    [Parameter(Mandatory = $true)][string]$CanonicalGatePath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedCanonicalGateSha256,
    [Parameter(Mandatory = $true)][string]$IndependentReviewPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedIndependentReviewSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedDispatcherSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedResourceBuilderSha256
)

$ErrorActionPreference = 'Stop'

function Get-BytesSha256([byte[]]$Bytes) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($hasher.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    } finally { $hasher.Dispose() }
}

function Get-DeterministicSourceTree([string]$Root, [bool]$IncludeBytes) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $rootFull -PathType Container)) {
        throw "source tree root missing: $rootFull"
    }
    $relativePaths = [Collections.Generic.List[string]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $rootFull -Recurse -File -Force) {
        $relative = [IO.Path]::GetRelativePath($rootFull, $file.FullName).Replace('\', '/')
        if (("/$relative/") -match '/__pycache__/' -or $relative.EndsWith('.pyc', [StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        [void]$relativePaths.Add($relative)
    }
    $relativePaths.Sort([StringComparer]::Ordinal)
    $records = [Collections.Generic.List[object]]::new()
    $manifest = [Text.StringBuilder]::new()
    foreach ($relative in $relativePaths) {
        $fullPath = Join-Path $rootFull $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
        $bytes = [IO.File]::ReadAllBytes($fullPath)
        $fileSha256 = Get-BytesSha256 $bytes
        [void]$manifest.Append($relative).Append("`t").Append($fileSha256).Append("`n")
        $record = [ordered]@{
            relative_path = $relative
            sha256 = $fileSha256
            size_bytes = $bytes.Length
        }
        if ($IncludeBytes) { $record.bytes = $bytes }
        [void]$records.Add([pscustomobject]$record)
    }
    $manifestBytes = [Text.UTF8Encoding]::new($false).GetBytes($manifest.ToString())
    return [pscustomobject]@{
        root = $rootFull
        file_count = $records.Count
        sha256 = Get-BytesSha256 $manifestBytes
        files = @($records)
    }
}

function Convert-WindowsPathToWsl([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($fullPath)
    if ([string]::IsNullOrWhiteSpace($root) -or $root.Length -lt 2 -or $root[1] -ne ':') {
        throw "unsupported Windows path for WSL conversion: $fullPath"
    }
    $drive = $root.Substring(0, 1).ToLowerInvariant()
    $relative = $fullPath.Substring($root.Length).Replace('\', '/')
    return "/mnt/$drive/$relative"
}

function Write-BytesCreateOnly([string]$Path, [byte[]]$Bytes) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $stream.Write($Bytes, 0, $Bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}

function Write-JsonCreateOnly([string]$Path, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 20
    Write-BytesCreateOnly $Path ([Text.UTF8Encoding]::new($false).GetBytes($json + "`n"))
}

function Set-ReadOnlySnapshotAcl([string]$Root) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    $account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $aclOutput = & icacls.exe $rootFull '/inheritance:r' '/grant:r' "${account}:(OI)(CI)(RX)" '/Q' 2>&1
    if ($LASTEXITCODE -ne 0) { throw "failed to harden source snapshot ACL: $($aclOutput | Out-String)" }
    return (Get-Acl -LiteralPath $rootFull).Sddl
}

function Test-RootFileCreationDenied([string]$Root) {
    $probePath = Join-Path ([IO.Path]::GetFullPath($Root)) ('.write-denial-probe-' + [Guid]::NewGuid().ToString('N'))
    $probe = $null
    try {
        $probe = [IO.File]::Open($probePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        return $false
    } catch [UnauthorizedAccessException] {
        return $true
    } catch [IO.IOException] {
        return $true
    } finally {
        if ($probe) { $probe.Dispose() }
        if (Test-Path -LiteralPath $probePath) { Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue }
    }
}

function Assert-ExactSnapshotRootShape([string]$Root) {
    $entries = @(Get-ChildItem -LiteralPath ([IO.Path]::GetFullPath($Root)) -Force)
    if ($entries.Count -ne 1 -or -not $entries[0].PSIsContainer -or $entries[0].Name -cne 'paper_faithful') {
        $names = @($entries | ForEach-Object { $_.Name }) -join ', '
        throw "Python source snapshot root contains unexpected entries: $names"
    }
    return $true
}

$launcherPath = [IO.Path]::GetFullPath($PSCommandPath)
$supervisorSourcePath = [IO.Path]::GetFullPath($SupervisorPath)
$actualLauncherSha256 = (Get-FileHash -LiteralPath $launcherPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualLauncherSha256 -ne $ApprovedLauncherSha256.ToLowerInvariant()) {
    throw "launcher SHA-256 mismatch: actual=$actualLauncherSha256 approved=$($ApprovedLauncherSha256.ToLowerInvariant())"
}
if (-not (Test-Path -LiteralPath $supervisorSourcePath -PathType Leaf)) { throw "supervisor script missing: $supervisorSourcePath" }
$supervisorBytes = [IO.File]::ReadAllBytes($supervisorSourcePath)
$sha256 = [Security.Cryptography.SHA256]::Create()
try {
    $actualSupervisorSha256 = ([BitConverter]::ToString($sha256.ComputeHash($supervisorBytes))).Replace('-', '').ToLowerInvariant()
} finally { $sha256.Dispose() }
if ($actualSupervisorSha256 -ne $ApprovedSupervisorSha256.ToLowerInvariant()) {
    throw "supervisor SHA-256 mismatch: actual=$actualSupervisorSha256 approved=$($ApprovedSupervisorSha256.ToLowerInvariant())"
}
$launchBindingFullPath = [IO.Path]::GetFullPath($LaunchBindingPath)
if (-not (Test-Path -LiteralPath $launchBindingFullPath -PathType Leaf)) {
    throw "launch binding artifact missing: $launchBindingFullPath"
}
$actualLaunchBindingSha256 = (Get-FileHash -LiteralPath $launchBindingFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualLaunchBindingSha256 -ne $ApprovedLaunchBindingSha256.ToLowerInvariant()) {
    throw "launch binding SHA-256 mismatch: actual=$actualLaunchBindingSha256 approved=$($ApprovedLaunchBindingSha256.ToLowerInvariant())"
}
$launchBinding = Get-Content -LiteralPath $launchBindingFullPath -Raw | ConvertFrom-Json
if ([int]$launchBinding.schema_version -ne 1 -or [string]$launchBinding.artifact_type -ne 'SUBJECT_GENERALIZATION_NATIVE_CACHE_LAUNCH_BINDING_V1' -or [string]$launchBinding.status -ne 'pass') {
    throw 'launch binding schema, artifact type, or status is invalid'
}
if ([string]$launchBinding.run_prefix -ne $RunPrefix) { throw 'launch binding run_prefix mismatch' }
if ([string]$launchBinding.protocol_sha256 -ne $ApprovedProtocolSha256.ToLowerInvariant()) { throw 'launch binding protocol SHA-256 mismatch' }
if ([string]$launchBinding.launcher_sha256 -ne $actualLauncherSha256) { throw 'launch binding launcher SHA-256 mismatch' }
if ([string]$launchBinding.supervisor_sha256 -ne $actualSupervisorSha256) { throw 'launch binding supervisor SHA-256 mismatch' }
if ([int]$launchBinding.cap -ne $Cap) { throw 'launch binding cap mismatch' }
if ([int]$launchBinding.epochs -ne $Epochs) { throw 'launch binding epochs mismatch' }
if ([string]$launchBinding.label_evidence_receipt -ne [string]$WslLabelEvidenceReceipt) { throw 'launch binding label evidence receipt mismatch' }
if ([string]$launchBinding.launcher_id_prefix -ne $LauncherIdPrefix) { throw 'launch binding launcher_id_prefix mismatch' }
if ([string]$launchBinding.resource_profile -ne $ResourceProfile) { throw 'launch binding resource_profile mismatch' }
if ([string]$launchBinding.dispatcher_sha256 -ne $ApprovedDispatcherSha256.ToLowerInvariant()) { throw 'launch binding dispatcher SHA-256 mismatch' }
if ([string]$launchBinding.resource_builder_sha256 -ne $ApprovedResourceBuilderSha256.ToLowerInvariant()) { throw 'launch binding resource-builder SHA-256 mismatch' }
$projectRootWindows = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$sourcePackageRoot = Join-Path $projectRootWindows 'paper_faithful'
$sourceTree = Get-DeterministicSourceTree $sourcePackageRoot $true
if ([string]$launchBinding.source_tree_sha256 -ne $sourceTree.sha256) { throw 'launch binding source-tree SHA-256 mismatch' }
if ([int]$launchBinding.source_tree_file_count -ne $sourceTree.file_count) { throw 'launch binding source-tree file-count mismatch' }
$reviewFullPath = [IO.Path]::GetFullPath($IndependentReviewPath)
if ((Get-FileHash -LiteralPath $reviewFullPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ApprovedIndependentReviewSha256.ToLowerInvariant()) { throw 'independent-review SHA-256 mismatch' }
$review = Get-Content -LiteralPath $reviewFullPath -Raw | ConvertFrom-Json
if ([string]$review.status -ne 'pass' -or @($review.findings.P0).Count -or @($review.findings.P1).Count -or @($review.findings.P2).Count) { throw 'independent review is not launch-approved' }
if ([string]$review.run_prefix -ne $RunPrefix -or [string]$review.protocol_sha256 -ne $ApprovedProtocolSha256.ToLowerInvariant()) { throw 'independent-review run/protocol mismatch' }
if ([string]$review.launch_binding_sha256 -ne $actualLaunchBindingSha256 -or [string]$review.dispatcher_sha256 -ne $ApprovedDispatcherSha256.ToLowerInvariant()) { throw 'independent-review binding/dispatcher mismatch' }
$canonicalGateFullPath = [IO.Path]::GetFullPath($CanonicalGatePath)
$actualCanonicalGateSha256 = (Get-FileHash -LiteralPath $canonicalGateFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualCanonicalGateSha256 -ne $ApprovedCanonicalGateSha256.ToLowerInvariant()) { throw 'canonical-gate SHA-256 mismatch' }
$canonicalGate = Get-Content -LiteralPath $canonicalGateFullPath -Raw | ConvertFrom-Json
if ([int]$canonicalGate.schema_version -ne 1 -or [string]$canonicalGate.artifact_type -ne 'PLAN16_V3_ATOMIC_CANONICAL_LAUNCH_GATE_V1' -or [string]$canonicalGate.status -ne 'pass' -or [string]$canonicalGate.authorized_action -ne 'dispatch_exactly_once') { throw 'canonical gate schema, type, status, or action is invalid' }
if ([string]$canonicalGate.run_prefix -ne $RunPrefix -or [string]$canonicalGate.protocol_sha256 -ne $ApprovedProtocolSha256.ToLowerInvariant()) { throw 'canonical-gate run/protocol mismatch' }
if ([string]$canonicalGate.launch_binding_sha256 -ne $actualLaunchBindingSha256 -or [string]$canonicalGate.independent_review_sha256 -ne $ApprovedIndependentReviewSha256.ToLowerInvariant()) { throw 'canonical-gate binding/review mismatch' }
if ([string]$canonicalGate.dispatcher_sha256 -ne $ApprovedDispatcherSha256.ToLowerInvariant() -or [string]$canonicalGate.resource_builder_sha256 -ne $ApprovedResourceBuilderSha256.ToLowerInvariant()) { throw 'canonical-gate dispatcher/resource-builder mismatch' }
if ($canonicalGate.python_source_bindings_match -ne $true -or [int]$canonicalGate.python_source_binding_count -ne 7) { throw 'canonical-gate Python source binding failed' }
if ([string]$canonicalGate.source_tree_sha256 -ne $sourceTree.sha256 -or [int]$canonicalGate.source_tree_file_count -ne $sourceTree.file_count) { throw 'canonical-gate source-tree binding mismatch' }
if ([int]$canonicalGate.cap -ne $Cap -or [int]$canonicalGate.epochs -ne $Epochs) { throw 'canonical-gate cap/epochs mismatch' }
$resourceEvidenceWindows = if ($WslResourceEvidence -match '^/mnt/([a-zA-Z])/(.+)$') { $matches[1].ToUpperInvariant() + ':' + [IO.Path]::DirectorySeparatorChar + $matches[2].Replace('/', [IO.Path]::DirectorySeparatorChar) } else { throw 'unsupported WSL resource-evidence path' }
$resourceEvidenceWindows = [IO.Path]::GetFullPath($resourceEvidenceWindows)
if ([IO.Path]::GetFullPath([string]$canonicalGate.resource_evidence_path) -ne $resourceEvidenceWindows) { throw 'canonical-gate resource-evidence path mismatch' }
$resourceEvidenceBytes = [IO.File]::ReadAllBytes($resourceEvidenceWindows)
$resourceEvidenceSha256 = Get-BytesSha256 $resourceEvidenceBytes
if ($resourceEvidenceSha256 -ne [string]$canonicalGate.resource_evidence_sha256) { throw 'canonical-gate resource-evidence SHA-256 mismatch' }
$launcherId = "$LauncherIdPrefix-$RunPrefix"
$launcherRoot = Join-Path (Join-Path $BulkRoot 'runtime\driver-recovery') $launcherId
$runRuntimeWindows = Join-Path (Join-Path $BulkRoot 'runtime') $RunPrefix
$runChildRoot = Join-Path $BulkRoot 'runs'

if (Test-Path -LiteralPath $launcherRoot) { throw "launcher namespace already exists; refusing reuse: $launcherRoot" }
if (Test-Path -LiteralPath $runRuntimeWindows) { throw "run runtime namespace already exists; refusing reuse: $runRuntimeWindows" }
if (Test-Path -LiteralPath $runChildRoot) {
    if (@(Get-ChildItem -LiteralPath $runChildRoot -Directory -Filter "$RunPrefix*" -ErrorAction SilentlyContinue).Count -gt 0) {
        throw "run child namespace already exists; refusing reuse: $RunPrefix"
    }
}
if ($ApprovedProtocolSha256 -notmatch '^[0-9a-fA-F]{64}$') { throw 'approved protocol SHA-256 must be 64 hexadecimal characters' }
$mountProbe = & wsl.exe -d $WslDistribution -- mountpoint -q $CacheMountTargetWsl 2>&1
if ($LASTEXITCODE -eq 0) { throw "cache mount target is already mounted; refusing reuse: $CacheMountTargetWsl" }
$stageProbe = & wsl.exe -d $WslDistribution -u root -- test -d $NativeStageWsl 2>&1
if ($LASTEXITCODE -ne 0) { throw "native stage directory is unavailable: $NativeStageWsl" }

New-Item -ItemType Directory -Path $launcherRoot -Force:$false | Out-Null
$boundSupervisorPath = Join-Path $launcherRoot 'supervisor.bound.ps1'
Write-BytesCreateOnly $boundSupervisorPath $supervisorBytes
$boundSupervisorSha256 = (Get-FileHash -LiteralPath $boundSupervisorPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($boundSupervisorSha256 -ne $ApprovedSupervisorSha256.ToLowerInvariant()) {
    throw "bound supervisor SHA-256 mismatch: actual=$boundSupervisorSha256 approved=$($ApprovedSupervisorSha256.ToLowerInvariant())"
}

$boundResourceEvidencePath = Join-Path $launcherRoot 'resource-evidence.bound.json'
Write-BytesCreateOnly $boundResourceEvidencePath $resourceEvidenceBytes
$boundResourceEvidenceSha256 = (Get-FileHash -LiteralPath $boundResourceEvidencePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($boundResourceEvidenceSha256 -ne $resourceEvidenceSha256) {
    throw "bound resource-evidence SHA-256 mismatch: actual=$boundResourceEvidenceSha256 approved=$resourceEvidenceSha256"
}
$boundResourceEvidenceWsl = Convert-WindowsPathToWsl $boundResourceEvidencePath

$pythonSourceSnapshotWindows = Join-Path $launcherRoot 'python-source-snapshot'
$snapshotPackageRoot = Join-Path $pythonSourceSnapshotWindows 'paper_faithful'
New-Item -ItemType Directory -Path $snapshotPackageRoot -Force:$false | Out-Null
foreach ($file in $sourceTree.files) {
    $destination = Join-Path $snapshotPackageRoot ([string]$file.relative_path).Replace('/', [IO.Path]::DirectorySeparatorChar)
    $destinationDirectory = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $destinationDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    }
    Write-BytesCreateOnly $destination ([byte[]]$file.bytes)
}
$snapshotTree = Get-DeterministicSourceTree $snapshotPackageRoot $false
if ($snapshotTree.sha256 -ne $sourceTree.sha256 -or $snapshotTree.file_count -ne $sourceTree.file_count) {
    throw 'bound Python source snapshot does not match approved source tree'
}
$pythonSourceSnapshotWsl = Convert-WindowsPathToWsl $pythonSourceSnapshotWindows
$sourceManifestRecord = [ordered]@{
    schema_version = 1
    artifact_type = 'PLAN16_PYTHON_SOURCE_SNAPSHOT_MANIFEST_V1'
    status = 'verified'
    source_root = $sourcePackageRoot
    snapshot_root = $snapshotPackageRoot
    source_tree_sha256 = $sourceTree.sha256
    source_tree_file_count = $sourceTree.file_count
    files = @($sourceTree.files | ForEach-Object { [ordered]@{ relative_path=$_.relative_path; sha256=$_.sha256; size_bytes=$_.size_bytes } })
}
Write-JsonCreateOnly (Join-Path $launcherRoot 'python-source-snapshot.manifest.json') $sourceManifestRecord
$snapshotAclSddl = Set-ReadOnlySnapshotAcl $pythonSourceSnapshotWindows
$snapshotRootCreationDenied = Test-RootFileCreationDenied $pythonSourceSnapshotWindows
if (-not $snapshotRootCreationDenied) { throw 'Python source snapshot root remains writable after ACL hardening' }
$snapshotRootShapeValidated = Assert-ExactSnapshotRootShape $pythonSourceSnapshotWindows

$dispatchLock = Join-Path $launcherRoot "$RunPrefix.dispatch.lock"
$attemptLock = Join-Path $launcherRoot "$RunPrefix.attempt.lock"
$dispatchStream = [IO.File]::Open($dispatchLock, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
$dispatchStream.Dispose()
$attemptStream = [IO.File]::Open($attemptLock, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
$attemptStream.Dispose()

$stdoutPath = Join-Path $launcherRoot 'supervisor.stdout.log'
$stderrPath = Join-Path $launcherRoot 'supervisor.stderr.log'
$dispatch = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_native_cache_dispatch'
    status = 'dispatched'
    run_prefix = $RunPrefix
    resource_profile = $ResourceProfile
    project_root = $WslProjectRoot
    python_source_snapshot_windows = $pythonSourceSnapshotWindows
    python_source_snapshot_wsl = $pythonSourceSnapshotWsl
    source_tree_sha256 = $snapshotTree.sha256
    source_tree_file_count = $snapshotTree.file_count
    source_snapshot_acl_sddl = $snapshotAclSddl
    source_snapshot_root_creation_denied = $snapshotRootCreationDenied
    source_snapshot_root_shape_validated = $snapshotRootShapeValidated
    bulk_root = $WslBulkRoot
    runtime_root = $WslRuntimeRoot
    protocol_output = $WslProtocolOutput
    resource_evidence = $WslResourceEvidence
    bound_resource_evidence = $boundResourceEvidenceWsl
    resource_evidence_sha256 = $boundResourceEvidenceSha256
    cache_validation_receipt = $WslReceipt
    label_evidence_receipt = if ([string]::IsNullOrWhiteSpace($WslLabelEvidenceReceipt)) { $null } else { $WslLabelEvidenceReceipt }
    cap = $Cap
    epochs = $Epochs
    native_stage_wsl = $NativeStageWsl
    cache_mount_target_wsl = $CacheMountTargetWsl
    approved_protocol_sha256 = $ApprovedProtocolSha256.ToLowerInvariant()
    launcher_path = $launcherPath
    approved_launcher_sha256 = $ApprovedLauncherSha256.ToLowerInvariant()
    actual_launcher_sha256 = $actualLauncherSha256
    launch_binding_path = $launchBindingFullPath
    approved_launch_binding_sha256 = $ApprovedLaunchBindingSha256.ToLowerInvariant()
    actual_launch_binding_sha256 = $actualLaunchBindingSha256
    canonical_gate_path = $canonicalGateFullPath
    canonical_gate_sha256 = $actualCanonicalGateSha256
    independent_review_path = $reviewFullPath
    independent_review_sha256 = $ApprovedIndependentReviewSha256.ToLowerInvariant()
    dispatcher_sha256 = $ApprovedDispatcherSha256.ToLowerInvariant()
    resource_builder_sha256 = $ApprovedResourceBuilderSha256.ToLowerInvariant()
    resource_max_age_at_supervisor_handoff_seconds = 30
    distribution = $WslDistribution
    supervisor_source_path = $supervisorSourcePath
    supervisor_bound_path = $boundSupervisorPath
    approved_supervisor_sha256 = $ApprovedSupervisorSha256.ToLowerInvariant()
    actual_supervisor_sha256 = $actualSupervisorSha256
    bound_supervisor_sha256 = $boundSupervisorSha256
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    no_retry = $true
    no_resume = $true
    no_reuse = $true
    supervisor_stdout = $stdoutPath
    supervisor_stderr = $stderrPath
}
Write-JsonCreateOnly (Join-Path $launcherRoot 'dispatch.json') $dispatch

$supervisorArguments = @(
    '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $boundSupervisorPath,
    '-RunPrefix', $RunPrefix,
    '-WslProjectRoot', $WslProjectRoot,
    '-WslPythonSourceRoot', $pythonSourceSnapshotWsl,
    '-PythonSourceSnapshotWindows', $pythonSourceSnapshotWindows,
    '-ApprovedSourceTreeSha256', $snapshotTree.sha256,
    '-ApprovedSourceTreeFileCount', [string]$snapshotTree.file_count,
    '-WslBulkRoot', $WslBulkRoot,
    '-WslCacheManifest', $WslCacheManifest,
    '-WslSourceManifest', $WslSourceManifest,
    '-WslEnvironmentManifest', $WslEnvironmentManifest,
    '-WslRuntimeRoot', $WslRuntimeRoot,
    '-WslProtocolOutput', $WslProtocolOutput,
    '-WslResourceEvidence', $boundResourceEvidenceWsl,
    '-ApprovedResourceEvidenceSha256', $boundResourceEvidenceSha256,
    '-WslReceipt', $WslReceipt,
    '-NativeStageWsl', $NativeStageWsl,
    '-CacheMountTargetWsl', $CacheMountTargetWsl,
    '-ApprovedProtocolSha256', $ApprovedProtocolSha256.ToLowerInvariant(),
    '-ResourceProfile', $ResourceProfile,
    '-LauncherRoot', $launcherRoot,
    '-WslDistribution', $WslDistribution,
    '-BulkRoot', $BulkRoot,
    '-Cap', [string]$Cap,
    '-Epochs', [string]$Epochs,
    '-MaxResourceAgeAtHandoffSeconds', '30'
)
if (-not [string]::IsNullOrWhiteSpace($WslLabelEvidenceReceipt)) {
    $supervisorArguments += @('-WslLabelEvidenceReceipt', $WslLabelEvidenceReceipt)
}
$supervisorExecutable = (Get-Command pwsh.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
if ([string]::IsNullOrWhiteSpace($supervisorExecutable)) {
    $supervisorExecutable = (Get-Command powershell.exe -ErrorAction Stop | Select-Object -First 1 -ExpandProperty Source)
}
$supervisorProcess = Start-Process -FilePath $supervisorExecutable -ArgumentList $supervisorArguments -WorkingDirectory (Join-Path $env:SystemRoot 'System32') -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath -PassThru
$processEvidence = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_native_cache_supervisor_process'
    status = 'started'
    run_prefix = $RunPrefix
    supervisor_pid = $supervisorProcess.Id
    detached = $true
    terminal_independent = $true
    mount_lifetime_bound_to_supervisor = $true
    launcher_sha256 = $actualLauncherSha256
    supervisor_sha256 = $boundSupervisorSha256
    stdout_path = $stdoutPath
    stderr_path = $stderrPath
    started_at = (Get-Date).ToUniversalTime().ToString('o')
}
Write-JsonCreateOnly (Join-Path $launcherRoot 'process.json') $processEvidence
Write-Output (([ordered]@{status='started';run_prefix=$RunPrefix;supervisor_pid=$supervisorProcess.Id;launcher_root=$launcherRoot;stdout=$stdoutPath;stderr=$stderrPath} | ConvertTo-Json -Compress))
