param(
    [Parameter(Mandatory = $true)][string]$RunPrefix,
    [Parameter(Mandatory = $true)][string]$WslProjectRoot,
    [Parameter(Mandatory = $true)][string]$WslPythonSourceRoot,
    [Parameter(Mandatory = $true)][string]$PythonSourceSnapshotWindows,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedSourceTreeSha256,
    [Parameter(Mandatory = $true)][ValidateRange(1, 1000000)][int]$ApprovedSourceTreeFileCount,
    [Parameter(Mandatory = $true)][string]$WslBulkRoot,
    [Parameter(Mandatory = $true)][string]$WslCacheManifest,
    [Parameter(Mandatory = $true)][string]$WslSourceManifest,
    [Parameter(Mandatory = $true)][string]$WslEnvironmentManifest,
    [Parameter(Mandatory = $true)][string]$WslRuntimeRoot,
    [Parameter(Mandatory = $true)][string]$WslProtocolOutput,
    [Parameter(Mandatory = $true)][string]$WslResourceEvidence,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ApprovedResourceEvidenceSha256,
    [Parameter(Mandatory = $true)][string]$WslReceipt,
    [Parameter(Mandatory = $true)][string]$NativeStageWsl,
    [Parameter(Mandatory = $true)][string]$CacheMountTargetWsl,
    [Parameter(Mandatory = $true)][string]$ApprovedProtocolSha256,
    [Parameter(Mandatory = $true)][string]$ResourceProfile,
    [Parameter(Mandatory = $true)][string]$LauncherRoot,
    [string]$WslDistribution = 'Ubuntu',
    [string]$BulkRoot = 'E:\blp\sleep_stage_reproduction',
    [ValidateRange(1, 1000000)][int]$Cap = 32,
    [ValidateRange(1, 10000)][int]$Epochs = 6,
    [string]$WslLabelEvidenceReceipt,
    [switch]$CommandEvidenceOnly,
    [switch]$ValidateHandoffOnly,
    [switch]$ProbeMutationLocks,
    [ValidateRange(1, 120)][int]$MaxResourceAgeAtHandoffSeconds = 30
)

$ErrorActionPreference = 'Stop'
$mounted = $false
$runner = $null
$runnerExitCode = $null
$mountOutput = ''
$mountVerification = ''
$errorMessage = $null
$startedAt = Get-Date
$handoffLocks = @()
$handoffLocksReleased = $false

function Write-JsonCreateOnly([string]$Path, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 20
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}

function Get-BytesSha256([byte[]]$Bytes) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($hasher.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    } finally { $hasher.Dispose() }
}

function Get-DeterministicSourceTree([string]$Root) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    if (-not (Test-Path -LiteralPath $rootFull -PathType Container)) { throw "source snapshot root missing: $rootFull" }
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
        $fileSha256 = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash.ToLowerInvariant()
        [void]$manifest.Append($relative).Append("`t").Append($fileSha256).Append("`n")
    }
    $manifestBytes = [Text.UTF8Encoding]::new($false).GetBytes($manifest.ToString())
    return [pscustomobject]@{ root=$rootFull; file_count=$relativePaths.Count; sha256=(Get-BytesSha256 $manifestBytes) }
}

function Get-SourceSnapshotFilePaths([string]$Root) {
    $rootFull = [IO.Path]::GetFullPath($Root)
    $paths = [Collections.Generic.List[string]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $rootFull -Recurse -File -Force) {
        $relative = [IO.Path]::GetRelativePath($rootFull, $file.FullName).Replace('\', '/')
        if (("/$relative/") -match '/__pycache__/' -or $relative.EndsWith('.pyc', [StringComparison]::OrdinalIgnoreCase)) { continue }
        [void]$paths.Add([IO.Path]::GetFullPath($file.FullName))
    }
    $paths.Sort([StringComparer]::Ordinal)
    return @($paths)
}

function Get-ResourceEvidenceWindowsPath {
    if ($WslResourceEvidence -notmatch '^/mnt/([a-zA-Z])/(.+)$') { throw 'unsupported WSL resource-evidence path' }
    return [IO.Path]::GetFullPath($matches[1].ToUpperInvariant() + ':' + [IO.Path]::DirectorySeparatorChar + $matches[2].Replace('/', [IO.Path]::DirectorySeparatorChar))
}

function Open-HandoffReadLocks {
    $opened = [Collections.Generic.List[IO.FileStream]]::new()
    try {
        $resourcePath = Get-ResourceEvidenceWindowsPath
        [void]$opened.Add([IO.File]::Open($resourcePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read))
        $snapshotPackageRoot = Join-Path ([IO.Path]::GetFullPath($PythonSourceSnapshotWindows)) 'paper_faithful'
        $before = @(Get-SourceSnapshotFilePaths $snapshotPackageRoot)
        foreach ($path in $before) {
            [void]$opened.Add([IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read))
        }
        $after = @(Get-SourceSnapshotFilePaths $snapshotPackageRoot)
        if ($before.Count -ne $after.Count -or [string]::Join("`n", $before) -cne [string]::Join("`n", $after)) {
            throw 'Python source snapshot changed while read locks were acquired'
        }
        return @($opened)
    } catch {
        foreach ($stream in $opened) { try { $stream.Dispose() } catch { } }
        throw
    }
}

function Test-WriteLockRejected([string]$Path) {
    $probe = $null
    try {
        $probe = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite)
        return $false
    } catch [IO.IOException] {
        return $true
    } catch [UnauthorizedAccessException] {
        return $true
    } finally {
        if ($probe) { $probe.Dispose() }
    }
}

function Test-RootInjectionRejected([string]$Root) {
    $probePath = Join-Path ([IO.Path]::GetFullPath($Root)) 'sitecustomize.py'
    if (Test-Path -LiteralPath $probePath) { throw 'unexpected root-level sitecustomize.py exists in Python source snapshot' }
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

function Get-ValidatedHandoffEvidence {
    $resourceEvidenceWindows = Get-ResourceEvidenceWindowsPath
    if (-not (Test-Path -LiteralPath $resourceEvidenceWindows -PathType Leaf)) { throw "resource evidence missing at handoff: $resourceEvidenceWindows" }
    $resourceEvidenceSha256 = (Get-FileHash -LiteralPath $resourceEvidenceWindows -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($resourceEvidenceSha256 -ne $ApprovedResourceEvidenceSha256.ToLowerInvariant()) { throw 'resource evidence SHA-256 mismatch at final handoff' }
    $resourceEvidence = Get-Content -LiteralPath $resourceEvidenceWindows -Raw | ConvertFrom-Json
    if ([string]$resourceEvidence.status -ne 'pass' -or $resourceEvidence.ready -ne $true) { throw 'resource evidence is not passing at handoff' }
    $resourceTimestamp = [DateTimeOffset]::Parse([string]$resourceEvidence.timestamp)
    $resourceAgeAtHandoffSeconds = ([DateTimeOffset]::UtcNow - $resourceTimestamp.ToUniversalTime()).TotalSeconds
    if ($resourceAgeAtHandoffSeconds -lt 0 -or $resourceAgeAtHandoffSeconds -gt $MaxResourceAgeAtHandoffSeconds) {
        throw "resource evidence outside final handoff age: $resourceAgeAtHandoffSeconds seconds"
    }
    $snapshotRootFull = [IO.Path]::GetFullPath($PythonSourceSnapshotWindows)
    $rootEntries = @(Get-ChildItem -LiteralPath $snapshotRootFull -Force)
    if ($rootEntries.Count -ne 1 -or -not $rootEntries[0].PSIsContainer -or $rootEntries[0].Name -cne 'paper_faithful') {
        $entryNames = @($rootEntries | ForEach-Object { $_.Name }) -join ', '
        throw "Python source snapshot root contains unexpected entries at final handoff: $entryNames"
    }
    $snapshotPackageRoot = Join-Path $snapshotRootFull 'paper_faithful'
    $sourceTree = Get-DeterministicSourceTree $snapshotPackageRoot
    if ($sourceTree.sha256 -ne $ApprovedSourceTreeSha256.ToLowerInvariant()) { throw 'Python source snapshot SHA-256 mismatch at final handoff' }
    if ($sourceTree.file_count -ne $ApprovedSourceTreeFileCount) { throw 'Python source snapshot file-count mismatch at final handoff' }
    return [pscustomobject]@{
        resource_evidence_windows_path = $resourceEvidenceWindows
        resource_evidence_sha256 = $resourceEvidenceSha256
        resource_evidence_age_at_handoff_seconds = $resourceAgeAtHandoffSeconds
        source_snapshot_windows_root = $snapshotRootFull
        source_snapshot_root_shape_validated = $true
        source_tree_sha256 = $sourceTree.sha256
        source_tree_file_count = $sourceTree.file_count
    }
}

$python = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
$wslArguments = @(
    '--distribution', $WslDistribution, '--cd', $WslPythonSourceRoot, '--', $python,
    '-m', 'paper_faithful.training.subject_generalization_runner',
    '--cache-manifest', $WslCacheManifest,
    '--source-manifest', $WslSourceManifest,
    '--environment-manifest', $WslEnvironmentManifest,
    '--bulk-root', $WslBulkRoot,
    '--runtime-root', $WslRuntimeRoot,
    '--run-prefix', $RunPrefix,
    '--selection-seed', '42',
    '--subject-count', '6',
    '--model-seed', '42',
    '--cap', [string]$Cap,
    '--resource-profile', $ResourceProfile,
    '--epochs', [string]$Epochs,
    '--protocol-output', $WslProtocolOutput,
    '--resource-evidence', $WslResourceEvidence,
    '--approved-protocol-sha256', $ApprovedProtocolSha256.ToLowerInvariant(),
    '--cache-validation-receipt', $WslReceipt
)
if (-not [string]::IsNullOrWhiteSpace($WslLabelEvidenceReceipt)) {
    $wslArguments += @('--label-evidence-receipt', $WslLabelEvidenceReceipt)
}
if ($CommandEvidenceOnly) {
    $commandEvidence = [ordered]@{
        schema_version = 1
        artifact_type = 'subject_generalization_native_cache_command_evidence'
        status = 'validated_no_execution'
        run_prefix = $RunPrefix
        cap = $Cap
        epochs = $Epochs
        python_source_root = $WslPythonSourceRoot
        approved_source_tree_sha256 = $ApprovedSourceTreeSha256.ToLowerInvariant()
        approved_resource_evidence_sha256 = $ApprovedResourceEvidenceSha256.ToLowerInvariant()
        label_evidence_receipt = if ([string]::IsNullOrWhiteSpace($WslLabelEvidenceReceipt)) { $null } else { $WslLabelEvidenceReceipt }
        command = @('wsl.exe') + $wslArguments
        no_training_started = $true
        no_mount_started = $true
        created_at = (Get-Date).ToUniversalTime().ToString('o')
    }
    $commandEvidencePath = Join-Path $LauncherRoot 'command-evidence.json'
    Write-JsonCreateOnly $commandEvidencePath $commandEvidence
    Write-Output (([ordered]@{status='validated_no_execution';path=$commandEvidencePath;cap=$Cap;epochs=$Epochs} | ConvertTo-Json -Compress))
    exit 0
}

if ($ValidateHandoffOnly) {
    try {
        $handoffLocks = @(Open-HandoffReadLocks)
        $handoff = Get-ValidatedHandoffEvidence
        $mutationProbePassed = $null
        if ($ProbeMutationLocks) {
            $sourcePaths = @(Get-SourceSnapshotFilePaths (Join-Path ([IO.Path]::GetFullPath($PythonSourceSnapshotWindows)) 'paper_faithful'))
            $rootInjectionProbePassed = Test-RootInjectionRejected $PythonSourceSnapshotWindows
            $mutationProbePassed = (Test-WriteLockRejected $handoff.resource_evidence_windows_path) -and (Test-WriteLockRejected $sourcePaths[0]) -and $rootInjectionProbePassed
            if (-not $mutationProbePassed) { throw 'handoff read locks did not reject post-validation mutation probe' }
        }
        $record = [ordered]@{
            schema_version = 1
            artifact_type = 'subject_generalization_native_cache_handoff_validation'
            status = 'validated_no_execution'
            run_prefix = $RunPrefix
            resource_evidence_windows_path = $handoff.resource_evidence_windows_path
            resource_evidence_sha256 = $handoff.resource_evidence_sha256
            resource_evidence_age_at_handoff_seconds = $handoff.resource_evidence_age_at_handoff_seconds
            source_snapshot_windows_root = $handoff.source_snapshot_windows_root
            source_tree_sha256 = $handoff.source_tree_sha256
            source_tree_file_count = $handoff.source_tree_file_count
            source_snapshot_root_shape_validated = $handoff.source_snapshot_root_shape_validated
            handoff_lock_count = $handoffLocks.Count
            mutation_probe_passed = $mutationProbePassed
            root_injection_probe_passed = $rootInjectionProbePassed
            locks_held_during_validation = $true
            no_training_started = $true
            no_mount_started = $true
        }
        $path = Join-Path $LauncherRoot 'handoff-validation.json'
        Write-JsonCreateOnly $path $record
        Write-Output (([ordered]@{status='validated_no_execution';path=$path} | ConvertTo-Json -Compress))
    } finally {
        foreach ($stream in $handoffLocks) { try { $stream.Dispose() } catch { } }
        $handoffLocksReleased = $true
    }
    exit 0
}

try {
    $sourceProbe = & wsl.exe -d $WslDistribution -u root -- test -d $NativeStageWsl 2>&1
    if ($LASTEXITCODE -ne 0) { throw "native stage directory unavailable: $NativeStageWsl" }
    $alreadyMounted = & wsl.exe -d $WslDistribution -- mountpoint -q $CacheMountTargetWsl 2>&1
    if ($LASTEXITCODE -eq 0) { throw "cache mount target already mounted: $CacheMountTargetWsl" }

    & wsl.exe -d $WslDistribution -u root -- mount --bind $NativeStageWsl $CacheMountTargetWsl 2>&1 | ForEach-Object { $mountOutput += "$_`n" }
    if ($LASTEXITCODE -ne 0) { throw "cache bind mount failed: $mountOutput" }
    $mounted = $true
    $findmnt = & wsl.exe -d $WslDistribution -u root -- findmnt -T $CacheMountTargetWsl -o TARGET,SOURCE,FSTYPE,OPTIONS 2>&1
    $mountVerification = ($findmnt | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $mountVerification -notmatch 'ext4' -or $mountVerification -notmatch [regex]::Escape($NativeStageWsl)) {
        throw "cache bind mount verification failed: $mountVerification"
    }
    $mountRecord = [ordered]@{
        schema_version = 1
        artifact_type = 'subject_generalization_native_cache_mount'
        status = 'mounted'
        run_prefix = $RunPrefix
        native_stage_wsl = $NativeStageWsl
        cache_mount_target_wsl = $CacheMountTargetWsl
        mount_output = $mountOutput.Trim()
        mount_verification = $mountVerification
        mounted_at = (Get-Date).ToUniversalTime().ToString('o')
        original_cache_untouched = $true
        unmount_policy = 'natural_workload_exit_then_exact_target_unmount'
    }
    Write-JsonCreateOnly (Join-Path $LauncherRoot 'mount.json') $mountRecord

    $handoffLocks = @(Open-HandoffReadLocks)
    $handoff = Get-ValidatedHandoffEvidence

    $workloadStdout = Join-Path $LauncherRoot 'wsl.stdout.log'
    $workloadStderr = Join-Path $LauncherRoot 'wsl.stderr.log'
    $runner = Start-Process -FilePath 'wsl.exe' -ArgumentList $wslArguments -WorkingDirectory (Join-Path $env:SystemRoot 'System32') -WindowStyle Hidden -RedirectStandardOutput $workloadStdout -RedirectStandardError $workloadStderr -PassThru
    $workloadRecord = [ordered]@{
        schema_version = 1
        artifact_type = 'subject_generalization_native_cache_workload'
        status = 'started'
        run_prefix = $RunPrefix
        host_pid = $runner.Id
        command = @('wsl.exe') + $wslArguments
        started_at = (Get-Date).ToUniversalTime().ToString('o')
        stdout_path = $workloadStdout
        stderr_path = $workloadStderr
        detached = $true
        cache_mount_held = $true
        resource_evidence_windows_path = $handoff.resource_evidence_windows_path
        resource_evidence_sha256 = $handoff.resource_evidence_sha256
        resource_evidence_age_at_handoff_seconds = $handoff.resource_evidence_age_at_handoff_seconds
        resource_evidence_max_age_at_handoff_seconds = $MaxResourceAgeAtHandoffSeconds
        source_snapshot_windows_root = $handoff.source_snapshot_windows_root
        source_tree_sha256 = $handoff.source_tree_sha256
        source_tree_file_count = $handoff.source_tree_file_count
        source_snapshot_root_shape_validated = $handoff.source_snapshot_root_shape_validated
        handoff_lock_count = $handoffLocks.Count
        handoff_locks_held_for_workload_lifetime = $true
        no_retry = $true
        no_resume = $true
        no_reuse = $true
    }
    Write-JsonCreateOnly (Join-Path $LauncherRoot 'workload.json') $workloadRecord
    $runner.WaitForExit()
    $runnerExitCode = [int]$runner.ExitCode
} catch {
    $errorMessage = $_.Exception.Message
} finally {
    $unmounted = $false
    if ($runner -ne $null -and -not $runner.HasExited) {
        $errorMessage = if ($errorMessage) { $errorMessage } else { 'workload process did not reach natural exit; cleanup deferred' }
    } elseif ($mounted) {
        & wsl.exe -d $WslDistribution -u root -- umount $CacheMountTargetWsl 2>&1 | Out-Null
        $unmounted = ($LASTEXITCODE -eq 0)
        if (-not $unmounted -and -not $errorMessage) { $errorMessage = "exact cache target unmount failed: $CacheMountTargetWsl" }
    } else {
        $unmounted = $true
    }
    foreach ($stream in $handoffLocks) { try { $stream.Dispose() } catch { } }
    $handoffLocksReleased = $true
    $terminalStatus = if ($errorMessage) { 'failed' } elseif ($runnerExitCode -eq 0) { 'workload_completed' } else { 'workload_failed' }
    $terminal = [ordered]@{
        schema_version = 1
        artifact_type = 'subject_generalization_native_cache_terminal'
        status = $terminalStatus
        run_prefix = $RunPrefix
        supervisor_pid = $PID
        workload_host_pid = if ($runner) { $runner.Id } else { $null }
        workload_exit_code = $runnerExitCode
        started_at = $startedAt.ToUniversalTime().ToString('o')
        finished_at = (Get-Date).ToUniversalTime().ToString('o')
        cache_mount_unmounted = $unmounted
        natural_workload_exit_required = $true
        windows_host_forced_cleanup = $false
        handoff_locks_released = $handoffLocksReleased
        error = $errorMessage
        no_retry = $true
        no_resume = $true
        no_reuse = $true
    }
    try { Write-JsonCreateOnly (Join-Path $LauncherRoot 'terminal.json') $terminal } catch { }
}
if ($errorMessage) { Write-Error $errorMessage; exit 2 }
if ($runnerExitCode -ne 0) { exit $runnerExitCode }
exit 0
