$ErrorActionPreference = 'Stop'

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -ne $Expected) {
        throw "$Message (actual=$Actual expected=$Expected)"
    }
}

function Value-After([object[]]$Command, [string]$Flag) {
    $index = [Array]::IndexOf($Command, $Flag)
    if ($index -lt 0 -or $index + 1 -ge $Command.Count) {
        throw "missing command flag or value: $Flag"
    }
    return [string]$Command[$index + 1]
}

function Convert-WindowsPathToWsl([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    return "/mnt/$($root.Substring(0,1).ToLowerInvariant())/$($full.Substring($root.Length).Replace('\','/'))"
}

function Get-SourceTreeRecord([string]$Root) {
    $paths = [Collections.Generic.List[string]]::new()
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force) {
        $relative = [IO.Path]::GetRelativePath($Root, $file.FullName).Replace('\', '/')
        if (("/$relative/") -match '/__pycache__/' -or $relative.EndsWith('.pyc', [StringComparison]::OrdinalIgnoreCase)) { continue }
        [void]$paths.Add($relative)
    }
    $paths.Sort([StringComparer]::Ordinal)
    $manifest = [Text.StringBuilder]::new()
    foreach ($relative in $paths) {
        $fullPath = Join-Path $Root $relative.Replace('/', [IO.Path]::DirectorySeparatorChar)
        $sha = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash.ToLowerInvariant()
        [void]$manifest.Append($relative).Append("`t").Append($sha).Append("`n")
    }
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($manifest.ToString())
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $sha256 = ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() } finally { $hasher.Dispose() }
    return [pscustomobject]@{ sha256=$sha256; file_count=$paths.Count }
}

function Set-TestReadOnlyTreeAcl([string]$Root) {
    $account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $output = & icacls.exe ([IO.Path]::GetFullPath($Root)) '/inheritance:r' '/grant:r' "${account}:(OI)(CI)(RX)" '/Q' 2>&1
    if ($LASTEXITCODE -ne 0) { throw "test ACL hardening failed: $($output | Out-String)" }
}

function Grant-TestTreeFullControl([string]$Root) {
    if (-not (Test-Path -LiteralPath $Root)) { return }
    $account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe ([IO.Path]::GetFullPath($Root)) '/inheritance:e' '/grant:r' "${account}:(OI)(CI)(F)" '/Q' | Out-Null
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testRoot = [IO.Path]::GetFullPath((Join-Path $tempBase ("sleep-stage-plan16-supervisor-command-" + [Guid]::NewGuid().ToString('N'))))
if (-not $testRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
    throw "unsafe test root: $testRoot"
}

try {
    New-Item -ItemType Directory -Path $testRoot -Force:$false | Out-Null
    $snapshotRoot = Join-Path $testRoot 'python-source-snapshot'
    $snapshotPackage = Join-Path $snapshotRoot 'paper_faithful'
    New-Item -ItemType Directory -Path $snapshotPackage -Force | Out-Null
    '' | Set-Content -LiteralPath (Join-Path $snapshotPackage '__init__.py') -Encoding UTF8
    'VALUE = 1' | Set-Content -LiteralPath (Join-Path $snapshotPackage 'module.py') -Encoding UTF8
    $sourceTree = Get-SourceTreeRecord $snapshotPackage
    Set-TestReadOnlyTreeAcl $snapshotRoot
    $snapshotWsl = Convert-WindowsPathToWsl $snapshotRoot
    $resourcePath = Join-Path $testRoot 'resource.json'
    ([ordered]@{status='pass';ready=$true;timestamp=[DateTimeOffset]::UtcNow.ToString('o')} | ConvertTo-Json -Compress) | Set-Content -LiteralPath $resourcePath -Encoding UTF8
    $resourceSha256 = (Get-FileHash -LiteralPath $resourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $resourceWsl = Convert-WindowsPathToWsl $resourcePath
    $labelReceipt = '/mnt/e/blp/sleep_stage_reproduction/runtime/integrity-receipts/full-cache-validation-receipt-plan2c-prior-20261005.json'
    $runtimeRoot = '/mnt/e/test/plan16-command-evidence-runtime-must-not-exist'
    $result = & (Join-Path $PSScriptRoot '..\native_cache_subject_supervisor.ps1') `
        -RunPrefix 'plan16-supervisor-command-evidence-test' `
        -WslProjectRoot '/mnt/c/test' `
        -WslPythonSourceRoot $snapshotWsl `
        -PythonSourceSnapshotWindows $snapshotRoot `
        -ApprovedSourceTreeSha256 $sourceTree.sha256 `
        -ApprovedSourceTreeFileCount $sourceTree.file_count `
        -WslBulkRoot '/mnt/e/test' `
        -WslCacheManifest '/mnt/e/test/cache-manifest.json' `
        -WslSourceManifest '/mnt/c/test/source-manifest.json' `
        -WslEnvironmentManifest '/mnt/c/test/environment.json' `
        -WslRuntimeRoot $runtimeRoot `
        -WslProtocolOutput '/mnt/e/test/protocol.json' `
        -WslResourceEvidence $resourceWsl `
        -ApprovedResourceEvidenceSha256 $resourceSha256 `
        -WslReceipt '/mnt/e/test/receipt.json' `
        -NativeStageWsl '/home/test/native-stage' `
        -CacheMountTargetWsl '/mnt/e/test/cache-target' `
        -ApprovedProtocolSha256 ('b' * 64) `
        -ResourceProfile 'QUALITY_BALANCED_CAP64_E12_TEST' `
        -LauncherRoot $testRoot `
        -Cap 64 `
        -Epochs 12 `
        -WslLabelEvidenceReceipt $labelReceipt `
        -CommandEvidenceOnly

    $summary = $result | ConvertFrom-Json
    Assert-Equal $summary.status 'validated_no_execution' 'unexpected command-evidence summary status'
    $evidencePath = Join-Path $testRoot 'command-evidence.json'
    $evidence = Get-Content -LiteralPath $evidencePath -Raw | ConvertFrom-Json
    Assert-Equal $evidence.status 'validated_no_execution' 'unexpected command-evidence status'
    Assert-Equal $evidence.cap 64 'supervisor evidence did not record cap'
    Assert-Equal $evidence.epochs 12 'supervisor evidence did not record epochs'
    Assert-Equal $evidence.label_evidence_receipt $labelReceipt 'supervisor evidence did not record label receipt'
    Assert-Equal (Value-After $evidence.command '--cap') '64' 'supervisor did not assemble cap argument'
    Assert-Equal (Value-After $evidence.command '--epochs') '12' 'supervisor did not assemble epochs argument'
    Assert-Equal (Value-After $evidence.command '--label-evidence-receipt') $labelReceipt 'supervisor did not assemble label-receipt argument'
    Assert-Equal (Value-After $evidence.command '--runtime-root') $runtimeRoot 'supervisor changed runtime root'
    Assert-Equal (Value-After $evidence.command '--cd') $snapshotWsl 'supervisor did not execute from immutable source snapshot'
    Assert-Equal $evidence.no_training_started $true 'command-evidence mode claimed training started'
    Assert-Equal $evidence.no_mount_started $true 'command-evidence mode claimed a mount started'

    $handoffRoot = Join-Path $testRoot 'handoff-positive'
    New-Item -ItemType Directory -Path $handoffRoot -Force:$false | Out-Null
    $handoffResult = & (Join-Path $PSScriptRoot '..\native_cache_subject_supervisor.ps1') `
        -RunPrefix 'plan16-supervisor-handoff-positive' -WslProjectRoot '/mnt/c/test' `
        -WslPythonSourceRoot $snapshotWsl -PythonSourceSnapshotWindows $snapshotRoot `
        -ApprovedSourceTreeSha256 $sourceTree.sha256 -ApprovedSourceTreeFileCount $sourceTree.file_count `
        -WslBulkRoot '/mnt/e/test' -WslCacheManifest '/mnt/e/test/cache-manifest.json' `
        -WslSourceManifest '/mnt/c/test/source-manifest.json' -WslEnvironmentManifest '/mnt/c/test/environment.json' `
        -WslRuntimeRoot '/mnt/e/test/runtime' -WslProtocolOutput '/mnt/e/test/protocol.json' `
        -WslResourceEvidence $resourceWsl -ApprovedResourceEvidenceSha256 $resourceSha256 `
        -WslReceipt '/mnt/e/test/receipt.json' -NativeStageWsl '/home/test/native-stage' `
        -CacheMountTargetWsl '/mnt/e/test/cache-target' -ApprovedProtocolSha256 ('b' * 64) `
        -ResourceProfile 'QUALITY_BALANCED_CAP64_E12_TEST' -LauncherRoot $handoffRoot `
        -Cap 64 -Epochs 12 -WslLabelEvidenceReceipt $labelReceipt -ValidateHandoffOnly -ProbeMutationLocks
    Assert-Equal (($handoffResult | ConvertFrom-Json).status) 'validated_no_execution' 'handoff validation did not pass'
    $handoffEvidence = Get-Content -LiteralPath (Join-Path $handoffRoot 'handoff-validation.json') -Raw | ConvertFrom-Json
    Assert-Equal $handoffEvidence.resource_evidence_sha256 $resourceSha256 'handoff validation did not bind resource hash'
    Assert-Equal $handoffEvidence.source_tree_sha256 $sourceTree.sha256 'handoff validation did not bind source tree hash'
    Assert-Equal $handoffEvidence.handoff_lock_count ($sourceTree.file_count + 1) 'handoff validation did not lock every source file and resource evidence'
    Assert-Equal $handoffEvidence.mutation_probe_passed $true 'post-validation mutation was not rejected by persistent read locks'
    Assert-Equal $handoffEvidence.root_injection_probe_passed $true 'root-level Python startup-hook injection was not rejected'

    $injectedSnapshotRoot = Join-Path $testRoot 'python-source-snapshot-pre-acl-injected'
    $injectedPackage = Join-Path $injectedSnapshotRoot 'paper_faithful'
    New-Item -ItemType Directory -Path $injectedPackage -Force | Out-Null
    '' | Set-Content -LiteralPath (Join-Path $injectedPackage '__init__.py') -Encoding UTF8
    'VALUE = 1' | Set-Content -LiteralPath (Join-Path $injectedPackage 'module.py') -Encoding UTF8
    'raise RuntimeError("injected")' | Set-Content -LiteralPath (Join-Path $injectedSnapshotRoot 'sitecustomize.py') -Encoding UTF8
    $injectedTree = Get-SourceTreeRecord $injectedPackage
    Set-TestReadOnlyTreeAcl $injectedSnapshotRoot
    $injectedRoot = Join-Path $testRoot 'handoff-pre-acl-injection'
    New-Item -ItemType Directory -Path $injectedRoot -Force:$false | Out-Null
    try {
        & (Join-Path $PSScriptRoot '..\native_cache_subject_supervisor.ps1') `
            -RunPrefix 'pre-acl-injection' -WslProjectRoot '/mnt/c/test' `
            -WslPythonSourceRoot (Convert-WindowsPathToWsl $injectedSnapshotRoot) `
            -PythonSourceSnapshotWindows $injectedSnapshotRoot -ApprovedSourceTreeSha256 $injectedTree.sha256 `
            -ApprovedSourceTreeFileCount $injectedTree.file_count -WslBulkRoot '/mnt/e/test' `
            -WslCacheManifest '/mnt/e/test/cache.json' -WslSourceManifest '/mnt/e/test/source.json' `
            -WslEnvironmentManifest '/mnt/e/test/env.json' -WslRuntimeRoot '/mnt/e/test/runtime' `
            -WslProtocolOutput '/mnt/e/test/protocol.json' -WslResourceEvidence $resourceWsl `
            -ApprovedResourceEvidenceSha256 $resourceSha256 -WslReceipt '/mnt/e/test/receipt.json' `
            -NativeStageWsl '/home/test/stage' -CacheMountTargetWsl '/mnt/e/test/cache-target' `
            -ApprovedProtocolSha256 ('b' * 64) -ResourceProfile 'TEST' -LauncherRoot $injectedRoot -ValidateHandoffOnly | Out-Null
        throw 'final handoff accepted a pre-ACL root-level sitecustomize.py injection'
    } catch {
        if ($_.Exception.Message -notmatch 'snapshot root contains unexpected entries at final handoff') { throw }
    }

    $badHashRoot = Join-Path $testRoot 'handoff-bad-resource-hash'
    New-Item -ItemType Directory -Path $badHashRoot -Force:$false | Out-Null
    try {
        & (Join-Path $PSScriptRoot '..\native_cache_subject_supervisor.ps1') `
            -RunPrefix 'bad-resource-hash' -WslProjectRoot '/mnt/c/test' -WslPythonSourceRoot $snapshotWsl `
            -PythonSourceSnapshotWindows $snapshotRoot -ApprovedSourceTreeSha256 $sourceTree.sha256 `
            -ApprovedSourceTreeFileCount $sourceTree.file_count -WslBulkRoot '/mnt/e/test' `
            -WslCacheManifest '/mnt/e/test/cache.json' -WslSourceManifest '/mnt/e/test/source.json' `
            -WslEnvironmentManifest '/mnt/e/test/env.json' -WslRuntimeRoot '/mnt/e/test/runtime' `
            -WslProtocolOutput '/mnt/e/test/protocol.json' -WslResourceEvidence $resourceWsl `
            -ApprovedResourceEvidenceSha256 ('0' * 64) -WslReceipt '/mnt/e/test/receipt.json' `
            -NativeStageWsl '/home/test/stage' -CacheMountTargetWsl '/mnt/e/test/cache-target' `
            -ApprovedProtocolSha256 ('b' * 64) -ResourceProfile 'TEST' -LauncherRoot $badHashRoot -ValidateHandoffOnly | Out-Null
        throw 'final handoff accepted mismatched resource hash'
    } catch {
        if ($_.Exception.Message -notmatch 'resource evidence SHA-256 mismatch at final handoff') { throw }
    }

    $stalePath = Join-Path $testRoot 'resource-stale.json'
    ([ordered]@{status='pass';ready=$true;timestamp=[DateTimeOffset]::UtcNow.AddMinutes(-10).ToString('o')} | ConvertTo-Json -Compress) | Set-Content -LiteralPath $stalePath -Encoding UTF8
    $staleSha = (Get-FileHash -LiteralPath $stalePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $staleWsl = Convert-WindowsPathToWsl $stalePath
    $staleRoot = Join-Path $testRoot 'handoff-stale-resource'
    New-Item -ItemType Directory -Path $staleRoot -Force:$false | Out-Null
    try {
        & (Join-Path $PSScriptRoot '..\native_cache_subject_supervisor.ps1') `
            -RunPrefix 'stale-resource' -WslProjectRoot '/mnt/c/test' -WslPythonSourceRoot $snapshotWsl `
            -PythonSourceSnapshotWindows $snapshotRoot -ApprovedSourceTreeSha256 $sourceTree.sha256 `
            -ApprovedSourceTreeFileCount $sourceTree.file_count -WslBulkRoot '/mnt/e/test' `
            -WslCacheManifest '/mnt/e/test/cache.json' -WslSourceManifest '/mnt/e/test/source.json' `
            -WslEnvironmentManifest '/mnt/e/test/env.json' -WslRuntimeRoot '/mnt/e/test/runtime' `
            -WslProtocolOutput '/mnt/e/test/protocol.json' -WslResourceEvidence $staleWsl `
            -ApprovedResourceEvidenceSha256 $staleSha -WslReceipt '/mnt/e/test/receipt.json' `
            -NativeStageWsl '/home/test/stage' -CacheMountTargetWsl '/mnt/e/test/cache-target' `
            -ApprovedProtocolSha256 ('b' * 64) -ResourceProfile 'TEST' -LauncherRoot $staleRoot -ValidateHandoffOnly | Out-Null
        throw 'final handoff accepted stale resource evidence'
    } catch {
        if ($_.Exception.Message -notmatch 'resource evidence outside final handoff age') { throw }
    }
    [pscustomobject]@{status='pass';cap=$evidence.cap;epochs=$evidence.epochs;label_evidence_receipt=$evidence.label_evidence_receipt;no_training_started=$evidence.no_training_started;no_mount_started=$evidence.no_mount_started} | ConvertTo-Json -Compress
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = [IO.Path]::GetFullPath($testRoot)
        if (-not $resolved.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
            throw "refusing unsafe cleanup: $resolved"
        }
        Grant-TestTreeFullControl $snapshotRoot
        Grant-TestTreeFullControl $injectedSnapshotRoot
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
