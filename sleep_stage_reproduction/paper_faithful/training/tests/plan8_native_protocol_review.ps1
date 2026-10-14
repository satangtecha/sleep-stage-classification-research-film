param(
    [Parameter(Mandatory = $true)][string]$ProtocolPath,
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$StageEvidencePath,
    [Parameter(Mandatory = $true)][string]$LoaderEvidencePath,
    [Parameter(Mandatory = $true)][string]$LauncherPath,
    [Parameter(Mandatory = $true)][string]$SupervisorPath,
    [Parameter(Mandatory = $true)][string]$ReviewPath,
    [Parameter(Mandatory = $true)][string]$BulkRoot
)

$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $ReviewPath) { throw "review already exists; refusing reuse: $ReviewPath" }
$protocol = Get-Content -LiteralPath $ProtocolPath -Raw | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
$stage = Get-Content -LiteralPath $StageEvidencePath -Raw | ConvertFrom-Json
$loader = Get-Content -LiteralPath $LoaderEvidencePath -Raw | ConvertFrom-Json
$protocolSha = (Get-FileHash -LiteralPath $ProtocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$stageSha = (Get-FileHash -LiteralPath $StageEvidencePath -Algorithm SHA256).Hash.ToLowerInvariant()
$loaderSha = (Get-FileHash -LiteralPath $LoaderEvidencePath -Algorithm SHA256).Hash.ToLowerInvariant()
$launcher = Get-Content -LiteralPath $LauncherPath -Raw
$supervisor = Get-Content -LiteralPath $SupervisorPath -Raw
$folds = @($protocol.folds)
$testSubjects = @($folds | ForEach-Object { [string]$_.test_subject })
$validationSubjects = @($folds | ForEach-Object { [string]$_.validation_subject })
$heldOut = @($testSubjects + $validationSubjects)
$runtimePath = Join-Path (Join-Path $BulkRoot 'runtime') $protocol.run_prefix
$childrenPath = Join-Path $BulkRoot 'runs'
$assertions = [ordered]@{
    protocol_sha_matches_disk = ($protocolSha -eq 'fb1032eb88270e12d54ebf7a97341e9a6ae37586f7cf3b7ece2e49d8f1e8e100')
    protocol_identity = ($protocol.run_prefix -eq 'subject-generalization-resource-limited-plan8-native-cache-v1-cap32-e6-20261005' -and $protocol.resource_profile -eq 'RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V6_DETACHED_GPU_RUN')
    six_folds = ($folds.Count -eq 6)
    held_out_subjects_disjoint = (($testSubjects | Sort-Object -Unique).Count -eq 6 -and ($validationSubjects | Sort-Object -Unique).Count -eq 6 -and (@($folds | Where-Object { $_.test_subject -eq $_.validation_subject }).Count -eq 0) -and ($heldOut | Sort-Object -Unique).Count -eq 6)
    cap_and_epochs = ($protocol.cap -eq 32 -and $protocol.stage_epochs -eq 6)
    stage1_effective_batch = ($protocol.stage_specs.stage1.microbatch -eq 16 -and $protocol.stage_specs.stage1.gradient_accumulation_steps -eq 8 -and $protocol.stage_specs.stage1.effective_batch -eq 128)
    stage2_preserved = ($protocol.stage_specs.stage2.microbatch -eq 128)
    stage3_protocol = ($protocol.stage_specs.stage3.microbatch -eq 1 -and $protocol.stage_specs.stage3.gradient_accumulation_steps -eq 128 -and $protocol.stage_specs.stage3.gradient_clip_norm -eq 1 -and $protocol.stage_specs.stage3.stage3_stability_adaptation_id -eq 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1')
    receipt_binding = ($protocol.cache_validation_receipt_sha256 -eq $receiptSha -and $receiptSha -eq 'c31eea4d496dcfe0c6e7cb21f3c2d0f5d9a7ac7f69741af6d24f6e057bcacc95')
    stage_pass = ($stage.status -eq 'staged' -and $stage.selected_chunk_count -eq 6051 -and $stage.copied_files -eq 12103 -and $stage.copied_bytes -ge $stage.expected_tensor_bytes -and $stage.no_retry -eq $true -and $stage.no_resume -eq $true -and $stage.no_reuse -eq $true)
    loader_pass = ($loader.status -eq 'pass' -and $loader.python_exit_code -eq 0 -and $loader.no_training_started -eq $true -and $loader.runtime_created -eq $false -and $loader.unmounted_after_test -eq $true -and $loader.original_cache_untouched -eq $true -and $loader.mount_output -match 'ext4' -and $loader.python_output -match '"fold_count": 6' -and $loader.python_output -match '"cache_member_count": 64337')
    launcher_create_only = ($launcher.Contains('[IO.FileMode]::CreateNew') -and $launcher.Contains('refusing reuse') -and $launcher.Contains('Start-Process') -and $launcher.Contains('terminal_independent'))
    supervisor_mount_lifecycle = ($supervisor.Contains('mount --bind') -and $supervisor.Contains('umount') -and $supervisor.Contains('natural_workload_exit_required') -and $supervisor.Contains('windows_host_forced_cleanup = $false') -and $supervisor.Contains('[IO.FileMode]::CreateNew'))
    fresh_runtime_absent = (-not (Test-Path -LiteralPath $runtimePath))
    fresh_children_absent = (@(Get-ChildItem -LiteralPath $childrenPath -Directory -Filter "$($protocol.run_prefix)*" -ErrorAction SilentlyContinue).Count -eq 0)
}
$status = if (@($assertions.Values | Where-Object { $_ -ne $true }).Count -eq 0) { 'pass' } else { 'fail' }
$review = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_plan8_native_cache_independent_review'
    status = $status
    reviewed_at = (Get-Date).ToUniversalTime().ToString('o')
    protocol_path = $ProtocolPath
    protocol_sha256 = $protocolSha
    receipt_path = $ReceiptPath
    receipt_sha256 = $receiptSha
    stage_evidence_path = $StageEvidencePath
    stage_evidence_sha256 = $stageSha
    loader_evidence_path = $LoaderEvidencePath
    loader_evidence_sha256 = $loaderSha
    launcher_path = $LauncherPath
    supervisor_path = $SupervisorPath
    assertions = $assertions
    no_training_dispatched = $true
}
$parent = Split-Path -Parent $ReviewPath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$json = $review | ConvertTo-Json -Depth 20
$stream = [IO.File]::Open($ReviewPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n")
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
} finally { $stream.Dispose() }
$json
if ($status -ne 'pass') { exit 2 }
