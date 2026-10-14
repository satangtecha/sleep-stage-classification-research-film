$ErrorActionPreference = 'Stop'

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -ne $Expected) {
        throw "$Message (actual=$Actual expected=$Expected)"
    }
}

function Get-RelativePathCompat([string]$Root, [string]$Path) {
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $pathFull = [IO.Path]::GetFullPath($Path)
    $prefix = $rootFull + [IO.Path]::DirectorySeparatorChar
    if (-not $pathFull.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "path is outside source tree: $pathFull"
    }
    return $pathFull.Substring($prefix.Length).Replace('\', '/')
}

function Get-SourceTreeRecord([string]$Root) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    $paths = [Collections.Generic.List[string]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $rootFull -Recurse -File -Force) {
        $relative = Get-RelativePathCompat $rootFull $file.FullName
        if (("/$relative/") -match '/__pycache__/' -or $relative.EndsWith('.pyc', [StringComparison]::OrdinalIgnoreCase)) { continue }
        [void]$paths.Add($relative)
    }
    $paths.Sort([StringComparer]::Ordinal)
    $manifest = [Text.StringBuilder]::new()
    foreach ($relative in $paths) {
        $fullPath = Join-Path $rootFull $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
        $sha = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash.ToLowerInvariant()
        [void]$manifest.Append($relative).Append("`t").Append($sha).Append("`n")
    }
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($manifest.ToString())
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $treeSha = ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() } finally { $hasher.Dispose() }
    return [pscustomobject]@{ sha256=$treeSha; file_count=$paths.Count }
}

function Grant-TestTreeFullControl([string]$Root) {
    if (-not (Test-Path -LiteralPath $Root)) { return }
    $account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe ([IO.Path]::GetFullPath($Root)) '/inheritance:e' '/grant:r' "${account}:(OI)(CI)(F)" '/Q' | Out-Null
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testRoot = [IO.Path]::GetFullPath((Join-Path $tempBase ("sleep-stage-plan16-launch-forwarding-" + [Guid]::NewGuid().ToString('N'))))
if (-not $testRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
    throw "unsafe test root: $testRoot"
}

try {
    New-Item -ItemType Directory -Path $testRoot -Force:$false | Out-Null
    $stub = Join-Path $testRoot 'stub-supervisor.ps1'
    @'
param(
    [string]$RunPrefix,
    [string]$WslProjectRoot,
    [string]$WslPythonSourceRoot,
    [string]$PythonSourceSnapshotWindows,
    [string]$ApprovedSourceTreeSha256,
    [int]$ApprovedSourceTreeFileCount,
    [string]$WslBulkRoot,
    [string]$WslCacheManifest,
    [string]$WslSourceManifest,
    [string]$WslEnvironmentManifest,
    [string]$WslRuntimeRoot,
    [string]$WslProtocolOutput,
    [string]$WslResourceEvidence,
    [string]$ApprovedResourceEvidenceSha256,
    [string]$WslReceipt,
    [string]$NativeStageWsl,
    [string]$CacheMountTargetWsl,
    [string]$ApprovedProtocolSha256,
    [string]$ResourceProfile,
    [string]$LauncherRoot,
    [string]$WslDistribution,
    [string]$BulkRoot,
    [int]$Cap,
    [int]$Epochs,
    [int]$SelectionSeed,
    [int]$ModelSeed,
    [string]$WslLabelEvidenceReceipt,
    [int]$MaxResourceAgeAtHandoffSeconds
)
$record = [ordered]@{
    run_prefix = $RunPrefix
    cap = $Cap
    epochs = $Epochs
    selection_seed = $SelectionSeed
    model_seed = $ModelSeed
    label_evidence_receipt = $WslLabelEvidenceReceipt
    python_source_root = $WslPythonSourceRoot
    python_source_snapshot_windows = $PythonSourceSnapshotWindows
    approved_source_tree_sha256 = $ApprovedSourceTreeSha256
    approved_source_tree_file_count = $ApprovedSourceTreeFileCount
    resource_evidence = $WslResourceEvidence
    approved_resource_evidence_sha256 = $ApprovedResourceEvidenceSha256
}
$bytes = [Text.UTF8Encoding]::new($false).GetBytes(($record | ConvertTo-Json -Compress) + "`n")
$path = Join-Path $LauncherRoot 'forwarded-parameters.json'
$stream = [IO.File]::Open($path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
'@ | Set-Content -LiteralPath $stub -Encoding UTF8

    $runPrefix = 'plan16-v6-seed-forwarding-test'
    $launcherPrefix = 'plan16-v6-seed-forwarding'
    $labelReceipt = '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/full-cache-validation-receipt-plan2c-prior-20261005.json'
    $launcherPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\launch_native_cache_subject_run_v6.ps1'))
    $launcherSha256 = (Get-FileHash -LiteralPath $launcherPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $supervisorSha256 = (Get-FileHash -LiteralPath $stub -Algorithm SHA256).Hash.ToLowerInvariant()
    $protocolSha256 = 'a' * 64
    $dispatcherSha256 = 'c' * 64
    $resourceBuilderSha256 = 'd' * 64
    $sourceTree = Get-SourceTreeRecord ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')))
    $resourcePath = Join-Path $testRoot 'resource.json'
    ([ordered]@{status='pass';ready=$true;timestamp=[DateTimeOffset]::UtcNow.ToString('o')} | ConvertTo-Json -Compress) | Set-Content -LiteralPath $resourcePath -Encoding UTF8
    $resourceSha256 = (Get-FileHash -LiteralPath $resourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $drive = ([IO.Path]::GetPathRoot($resourcePath)).Substring(0, 1).ToLowerInvariant()
    $resourceRelative = $resourcePath.Substring(3).Replace('\', '/')
    $resourceWsl = "/mnt/$drive/$resourceRelative"
    $launchBindingPath = Join-Path $testRoot 'launch-binding.json'
    [ordered]@{
        schema_version = 1
        artifact_type = 'SUBJECT_GENERALIZATION_NATIVE_CACHE_LAUNCH_BINDING_V1'
        status = 'pass'
        run_prefix = $runPrefix
        protocol_sha256 = $protocolSha256
        launcher_sha256 = $launcherSha256
        supervisor_sha256 = $supervisorSha256
        dispatcher_sha256 = $dispatcherSha256
        resource_builder_sha256 = $resourceBuilderSha256
        expected_canonical_gate_artifact_type = 'PLAN16_V8_ATOMIC_CANONICAL_LAUNCH_GATE_V1'
        source_tree_sha256 = $sourceTree.sha256
        source_tree_file_count = $sourceTree.file_count
        cap = 64
        epochs = 12
        selection_seed = 43
        model_seed = 43
        label_evidence_receipt = $labelReceipt
        launcher_id_prefix = $launcherPrefix
        resource_profile = 'QUALITY_BALANCED_CAP64_E12_TEST'
    } | ConvertTo-Json | Set-Content -LiteralPath $launchBindingPath -Encoding UTF8
    $launchBindingSha256 = (Get-FileHash -LiteralPath $launchBindingPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $reviewPath = Join-Path $testRoot 'independent-review.json'
    [ordered]@{
        schema_version = 1
        artifact_type = 'TEST_INDEPENDENT_REVIEW'
        status = 'pass'
        run_prefix = $runPrefix
        protocol_sha256 = $protocolSha256
        launch_binding_sha256 = $launchBindingSha256
        dispatcher_sha256 = $dispatcherSha256
        findings = [ordered]@{ P0=@(); P1=@(); P2=@(); P3=@() }
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reviewPath -Encoding UTF8
    $reviewSha256 = (Get-FileHash -LiteralPath $reviewPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $canonicalGatePath = Join-Path $testRoot 'canonical-gate.json'
    [ordered]@{
        schema_version = 1
        artifact_type = 'PLAN16_V8_ATOMIC_CANONICAL_LAUNCH_GATE_V1'
        status = 'pass'
        authorized_action = 'dispatch_exactly_once'
        run_prefix = $runPrefix
        protocol_sha256 = $protocolSha256
        launch_binding_sha256 = $launchBindingSha256
        independent_review_sha256 = $reviewSha256
        dispatcher_sha256 = $dispatcherSha256
        resource_builder_sha256 = $resourceBuilderSha256
        resource_evidence_path = $resourcePath
        resource_evidence_sha256 = $resourceSha256
        python_source_binding_count = 7
        python_source_bindings_match = $true
        source_tree_sha256 = $sourceTree.sha256
        source_tree_file_count = $sourceTree.file_count
        cap = 64
        epochs = 12
        selection_seed = 43
        model_seed = 43
    } | ConvertTo-Json | Set-Content -LiteralPath $canonicalGatePath -Encoding UTF8
    $canonicalGateSha256 = (Get-FileHash -LiteralPath $canonicalGatePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $common = @{
        RunPrefix = $runPrefix
        WslProjectRoot = '/mnt/c/test'
        WslBulkRoot = '/mnt/e/test'
        WslCacheManifest = '/mnt/e/test/cache-manifest.json'
        WslSourceManifest = '/mnt/c/test/source-manifest.json'
        WslEnvironmentManifest = '/mnt/c/test/environment.json'
        WslRuntimeRoot = '/mnt/e/test/runtime'
        WslProtocolOutput = '/mnt/e/test/protocol.json'
        WslResourceEvidence = $resourceWsl
        WslReceipt = '/mnt/e/test/receipt.json'
        NativeStageWsl = '/home/techatat/subject-generalization-plan16-quality-cap64-native-cache-v2-20261006'
        CacheMountTargetWsl = '/mnt/e/blp/sleep_stage_reproduction/sst_cache/paper_faithful_v3_full_20260820'
        ApprovedProtocolSha256 = $protocolSha256
        ResourceProfile = 'QUALITY_BALANCED_CAP64_E12_TEST'
        SupervisorPath = $stub
        BulkRoot = $testRoot
        LauncherIdPrefix = $launcherPrefix
        Cap = 64
        Epochs = 12
        SelectionSeed = 43
        ModelSeed = 43
        WslLabelEvidenceReceipt = $labelReceipt
        ApprovedLauncherSha256 = $launcherSha256
        ApprovedSupervisorSha256 = $supervisorSha256
        LaunchBindingPath = $launchBindingPath
        ApprovedLaunchBindingSha256 = $launchBindingSha256
        CanonicalGatePath = $canonicalGatePath
        ExpectedCanonicalGateArtifactType = 'PLAN16_V8_ATOMIC_CANONICAL_LAUNCH_GATE_V1'
        ApprovedCanonicalGateSha256 = $canonicalGateSha256
        IndependentReviewPath = $reviewPath
        ApprovedIndependentReviewSha256 = $reviewSha256
        ApprovedDispatcherSha256 = $dispatcherSha256
        ApprovedResourceBuilderSha256 = $resourceBuilderSha256
    }

    $badGateType = $common.Clone()
    $badGateType.ExpectedCanonicalGateArtifactType = 'PLAN16_V4_ATOMIC_CANONICAL_LAUNCH_GATE_V1'
    try {
        & $launcherPath @badGateType | Out-Null
        throw 'mismatched expected canonical gate type was accepted'
    } catch {
        if ($_.Exception.Message -notmatch 'launch binding expected canonical-gate artifact type mismatch') { throw }
    }
    $badGateTypeRoot = Join-Path $testRoot "runtime\driver-recovery\$launcherPrefix-$($badGateType.RunPrefix)"
    if (Test-Path -LiteralPath $badGateTypeRoot) { throw 'canonical-gate type mismatch created a namespace' }

    $alternateGatePath = Join-Path $testRoot 'canonical-gate-alternate-type.json'
    $alternateGate = Get-Content -LiteralPath $canonicalGatePath -Raw | ConvertFrom-Json
    $alternateGate.artifact_type = 'PLAN16_V4_ATOMIC_CANONICAL_LAUNCH_GATE_V1'
    $alternateGate | ConvertTo-Json | Set-Content -LiteralPath $alternateGatePath -Encoding UTF8
    $alternateGateSha256 = (Get-FileHash -LiteralPath $alternateGatePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $badBindingType = $common.Clone()
    $badBindingType.CanonicalGatePath = $alternateGatePath
    $badBindingType.ExpectedCanonicalGateArtifactType = 'PLAN16_V4_ATOMIC_CANONICAL_LAUNCH_GATE_V1'
    $badBindingType.ApprovedCanonicalGateSha256 = $alternateGateSha256
    try {
        & $launcherPath @badBindingType | Out-Null
        throw 'matching alternate gate and parameter bypassed the reviewed launch binding'
    } catch {
        if ($_.Exception.Message -notmatch 'launch binding expected canonical-gate artifact type mismatch') { throw }
    }
    if (Test-Path -LiteralPath $badGateTypeRoot) { throw 'launch-binding gate-type mismatch created a namespace' }

    $badLauncher = $common.Clone()
    $badLauncher.RunPrefix = 'plan16-launch-negative-launcher-hash'
    $badLauncher.ApprovedLauncherSha256 = '0' * 64
    try {
        & $launcherPath @badLauncher | Out-Null
        throw 'mismatched launcher hash was accepted'
    } catch {
        if ($_.Exception.Message -notmatch 'launcher SHA-256 mismatch') { throw }
    }
    $badLauncherRoot = Join-Path $testRoot "runtime\driver-recovery\$launcherPrefix-$($badLauncher.RunPrefix)"
    if (Test-Path -LiteralPath $badLauncherRoot) { throw 'launcher mismatch created a namespace' }

    $badSupervisor = $common.Clone()
    $badSupervisor.RunPrefix = 'plan16-launch-negative-supervisor-hash'
    $badSupervisor.ApprovedSupervisorSha256 = '1' * 64
    try {
        & $launcherPath @badSupervisor | Out-Null
        throw 'mismatched supervisor hash was accepted'
    } catch {
        if ($_.Exception.Message -notmatch 'supervisor SHA-256 mismatch') { throw }
    }
    $badSupervisorRoot = Join-Path $testRoot "runtime\driver-recovery\$launcherPrefix-$($badSupervisor.RunPrefix)"
    if (Test-Path -LiteralPath $badSupervisorRoot) { throw 'supervisor mismatch created a namespace' }

    $badPrefix = $common.Clone()
    $badPrefix.LauncherIdPrefix = 'unauthorized-launcher-prefix'
    try {
        & $launcherPath @badPrefix | Out-Null
        throw 'mismatched launcher prefix was accepted'
    } catch {
        if ($_.Exception.Message -notmatch 'launcher_id_prefix mismatch') { throw }
    }
    $badPrefixRoot = Join-Path $testRoot "runtime\driver-recovery\$($badPrefix.LauncherIdPrefix)-$runPrefix"
    if (Test-Path -LiteralPath $badPrefixRoot) { throw 'launcher-prefix mismatch created a namespace' }

    $badProfile = $common.Clone()
    $badProfile.ResourceProfile = 'UNAUTHORIZED_RESOURCE_PROFILE'
    try {
        & $launcherPath @badProfile | Out-Null
        throw 'mismatched resource profile was accepted'
    } catch {
        if ($_.Exception.Message -notmatch 'resource_profile mismatch') { throw }
    }
    $authorizedRootBeforePositive = Join-Path $testRoot "runtime\driver-recovery\$launcherPrefix-$runPrefix"
    if (Test-Path -LiteralPath $authorizedRootBeforePositive) { throw 'resource-profile mismatch created a namespace' }

    $resourceOriginalBytes = [IO.File]::ReadAllBytes($resourcePath)
    '{"status":"pass","ready":true,"timestamp":"mutated"}' | Set-Content -LiteralPath $resourcePath -Encoding UTF8
    try {
        & $launcherPath @common | Out-Null
        throw 'mutated resource evidence was accepted'
    } catch {
        if ($_.Exception.Message -notmatch 'resource-evidence SHA-256 mismatch') { throw }
    } finally {
        [IO.File]::WriteAllBytes($resourcePath, $resourceOriginalBytes)
    }
    if (Test-Path -LiteralPath $authorizedRootBeforePositive) { throw 'resource hash mismatch created a namespace' }

    $launchOutput = & $launcherPath @common

    $started = $launchOutput | ConvertFrom-Json
    $launcherRoot = [string]$started.launcher_root
    $forwardedPath = Join-Path $launcherRoot 'forwarded-parameters.json'
    $deadline = (Get-Date).AddSeconds(20)
    while (
        (-not (Test-Path -LiteralPath $forwardedPath) -or
         (Get-Process -Id ([int]$started.supervisor_pid) -ErrorAction SilentlyContinue)) -and
        (Get-Date) -lt $deadline
    ) {
        Start-Sleep -Milliseconds 100
    }
    if (-not (Test-Path -LiteralPath $forwardedPath)) {
        throw 'stub supervisor did not persist forwarded parameters'
    }
    if (Get-Process -Id ([int]$started.supervisor_pid) -ErrorAction SilentlyContinue) {
        throw 'stub supervisor did not exit naturally before evidence read'
    }

    $forwarded = Get-Content -LiteralPath $forwardedPath -Raw | ConvertFrom-Json
    $dispatch = Get-Content -LiteralPath (Join-Path $launcherRoot 'dispatch.json') -Raw | ConvertFrom-Json
    Assert-Equal $forwarded.cap 64 'launcher did not forward cap'
    Assert-Equal $forwarded.epochs 12 'launcher did not forward epochs'
    Assert-Equal $forwarded.selection_seed 43 'launcher did not forward selection seed'
    Assert-Equal $forwarded.model_seed 43 'launcher did not forward model seed'
    Assert-Equal $forwarded.label_evidence_receipt $labelReceipt 'launcher did not forward label receipt'
    Assert-Equal $forwarded.approved_source_tree_sha256 $sourceTree.sha256 'launcher did not forward approved source-tree hash'
    Assert-Equal $forwarded.approved_source_tree_file_count $sourceTree.file_count 'launcher did not forward approved source-tree file count'
    Assert-Equal $forwarded.approved_resource_evidence_sha256 $resourceSha256 'launcher did not forward approved resource hash'
    Assert-Equal $dispatch.cap 64 'dispatch evidence did not record cap'
    Assert-Equal $dispatch.epochs 12 'dispatch evidence did not record epochs'
    Assert-Equal $dispatch.selection_seed 43 'dispatch evidence did not record selection seed'
    Assert-Equal $dispatch.model_seed 43 'dispatch evidence did not record model seed'
    Assert-Equal $dispatch.label_evidence_receipt $labelReceipt 'dispatch evidence did not record label receipt'
    Assert-Equal $dispatch.actual_launcher_sha256 $launcherSha256 'dispatch evidence did not bind launcher hash'
    Assert-Equal $dispatch.approved_launcher_sha256 $launcherSha256 'dispatch evidence did not record approved launcher hash'
    Assert-Equal $dispatch.actual_supervisor_sha256 $supervisorSha256 'dispatch evidence did not bind supervisor source hash'
    Assert-Equal $dispatch.bound_supervisor_sha256 $supervisorSha256 'dispatch evidence did not bind executed supervisor snapshot hash'
    Assert-Equal $dispatch.actual_launch_binding_sha256 $launchBindingSha256 'dispatch evidence did not bind launch authority artifact'
    Assert-Equal $dispatch.approved_launch_binding_sha256 $launchBindingSha256 'dispatch evidence did not record approved launch authority hash'
    Assert-Equal $dispatch.expected_canonical_gate_artifact_type 'PLAN16_V8_ATOMIC_CANONICAL_LAUNCH_GATE_V1' 'dispatch evidence did not record expected canonical-gate type'
    Assert-Equal $dispatch.source_tree_sha256 $sourceTree.sha256 'dispatch evidence did not bind source snapshot tree hash'
    Assert-Equal $dispatch.source_tree_file_count $sourceTree.file_count 'dispatch evidence did not bind source snapshot file count'
    Assert-Equal $dispatch.source_snapshot_root_shape_validated $true 'dispatch evidence did not prove exact snapshot-root shape'
    Assert-Equal $dispatch.resource_evidence_sha256 $resourceSha256 'dispatch evidence did not bind resource snapshot hash'
    if ($forwarded.resource_evidence -eq $resourceWsl) { throw 'launcher forwarded mutable resource path instead of bound snapshot' }
    if (-not (Test-Path -LiteralPath $forwarded.python_source_snapshot_windows -PathType Container)) { throw 'Python source snapshot is missing' }
    $injectionPath = Join-Path $forwarded.python_source_snapshot_windows 'sitecustomize.py'
    try {
        [IO.File]::WriteAllText($injectionPath, 'raise RuntimeError("injected")')
        throw 'source snapshot root accepted executable injection'
    } catch [UnauthorizedAccessException] {
    } catch [IO.IOException] {
    }
    if (-not (Test-Path -LiteralPath (Join-Path $launcherRoot 'resource-evidence.bound.json') -PathType Leaf)) { throw 'bound resource evidence is missing' }
    if (-not (Test-Path -LiteralPath (Join-Path $launcherRoot 'python-source-snapshot.manifest.json') -PathType Leaf)) { throw 'source snapshot manifest is missing' }
    if (-not (Test-Path -LiteralPath $dispatch.supervisor_bound_path -PathType Leaf)) {
        throw 'bound supervisor snapshot is missing'
    }
    [pscustomobject]@{status='pass';cap=$forwarded.cap;epochs=$forwarded.epochs;selection_seed=$forwarded.selection_seed;model_seed=$forwarded.model_seed;label_evidence_receipt=$forwarded.label_evidence_receipt} | ConvertTo-Json -Compress
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = [IO.Path]::GetFullPath($testRoot)
        if (-not $resolved.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
            throw "refusing unsafe cleanup: $resolved"
        }
        $snapshotForCleanup = Get-ChildItem -LiteralPath $resolved -Directory -Recurse -Filter 'python-source-snapshot' -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($snapshotForCleanup) { Grant-TestTreeFullControl $snapshotForCleanup.FullName }
        $removed = $false
        foreach ($attempt in 1..20) {
            try {
                Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop
                $removed = $true
                break
            } catch {
                if ($attempt -eq 20) { throw }
                Start-Sleep -Milliseconds 100
            }
        }
        if (-not $removed -and (Test-Path -LiteralPath $resolved)) {
            throw "temporary test root was not removed: $resolved"
        }
    }
}

