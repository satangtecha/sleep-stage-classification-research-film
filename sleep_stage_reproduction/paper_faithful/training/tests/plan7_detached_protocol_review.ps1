param(
    [Parameter(Mandatory = $true)][string]$ProtocolPath,
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$LauncherPath,
    [Parameter(Mandatory = $true)][string]$BulkRoot,
    [Parameter(Mandatory = $true)][string]$ReviewPath
)

$ErrorActionPreference = 'Stop'
$protocol = Get-Content -LiteralPath $ProtocolPath -Raw | ConvertFrom-Json
$receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
$launcher = Get-Content -LiteralPath $LauncherPath -Raw
$protocolSha = (Get-FileHash -LiteralPath $ProtocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$receiptSha = (Get-FileHash -LiteralPath $ReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$launcherSha = (Get-FileHash -LiteralPath $LauncherPath -Algorithm SHA256).Hash.ToLowerInvariant()
$folds = @($protocol.folds)
$testSubjects = @($folds | ForEach-Object { [string]$_.test_subject })
$validationSubjects = @($folds | ForEach-Object { [string]$_.validation_subject })
$allHeldOut = @($testSubjects + $validationSubjects)
$assertions = [ordered]@{
    protocol_sha_matches_disk = ($protocolSha -eq '4040c1a7915376c3d6ab65e7d570f137de15ebc30076c0e3268d28e6b4237d7c')
    protocol_identity = ($protocol.run_prefix -eq 'subject-generalization-resource-limited-plan7-detached-v1-cap32-e6-20261005' -and $protocol.resource_profile -eq 'RESOURCE_LIMITED_COMPACT_OFFLINE_CAP32_E6_V6_DETACHED_GPU_RUN')
    six_folds = ($folds.Count -eq 6)
    held_out_subjects_disjoint = (($testSubjects | Sort-Object -Unique).Count -eq 6 -and ($validationSubjects | Sort-Object -Unique).Count -eq 6 -and (@($folds | Where-Object { $_.test_subject -eq $_.validation_subject }).Count -eq 0) -and ($allHeldOut | Sort-Object -Unique).Count -eq 6)
    cap_and_epochs = ($protocol.cap -eq 32 -and $protocol.stage_epochs -eq 6)
    stage1_effective_batch = ($protocol.stage_specs.stage1.microbatch -eq 16 -and $protocol.stage_specs.stage1.gradient_accumulation_steps -eq 8 -and $protocol.stage_specs.stage1.effective_batch -eq 128)
    stage2_preserved = ($protocol.stage_specs.stage2.microbatch -eq 128)
    stage3_protocol = ($protocol.stage_specs.stage3.microbatch -eq 1 -and $protocol.stage_specs.stage3.gradient_accumulation_steps -eq 128 -and $protocol.stage_specs.stage3.gradient_clip_norm -eq 1 -and $protocol.stage_specs.stage3.stage3_stability_adaptation_id -eq 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1')
    receipt_binding = ($protocol.cache_validation_receipt_sha256 -eq $receiptSha -and $receiptSha -eq 'c31eea4d496dcfe0c6e7cb21f3c2d0f5d9a7ac7f69741af6d24f6e057bcacc95')
    launcher_has_detached_start = ($launcher.Contains('Start-Process') -and $launcher.Contains('-WindowStyle Hidden') -and $launcher.Contains('terminal_independent'))
    launcher_has_create_only_guards = ($launcher.Contains('[IO.FileMode]::CreateNew') -and $launcher.Contains('refusing reuse'))
    fresh_runtime_absent = (!(Test-Path -LiteralPath (Join-Path (Join-Path $BulkRoot 'runtime') $protocol.run_prefix)))
    fresh_children_absent = (@(Get-ChildItem -LiteralPath (Join-Path $BulkRoot 'runs') -Directory -Filter "$($protocol.run_prefix)*" -ErrorAction SilentlyContinue).Count -eq 0)
}
$status = if (@($assertions.Values | Where-Object { $_ -ne $true }).Count -eq 0) { 'pass' } else { 'fail' }
$review = [ordered]@{
    schema_version = 1
    artifact_type = 'subject_generalization_plan7_detached_independent_review'
    status = $status
    reviewed_at = (Get-Date).ToUniversalTime().ToString('o')
    protocol_path = $ProtocolPath
    protocol_sha256 = $protocolSha
    receipt_path = $ReceiptPath
    receipt_sha256 = $receiptSha
    launcher_path = $LauncherPath
    launcher_sha256 = $launcherSha
    assertions = $assertions
}
$parent = Split-Path -Parent $ReviewPath
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$temp = "$ReviewPath.$PID.tmp"
$review | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temp -Encoding UTF8
Move-Item -LiteralPath $temp -Destination $ReviewPath -Force
$review | ConvertTo-Json -Depth 12
if ($status -ne 'pass') { exit 2 }
