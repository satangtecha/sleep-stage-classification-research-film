function New-R14MarkerRefusalException([string]$Message) {
    $exception = New-Object System.InvalidOperationException($Message)
    $exception.Data['r14_exit_code'] = 91
    $exception
}

function Assert-R14MarkerAvailable([string]$Path, [string]$Label) {
    if (Test-Path -LiteralPath $Path) { throw (New-R14MarkerRefusalException "r14 $Label marker is already consumed: $Path") }
}

function Open-R14PermanentMarker([string]$Path, [string]$Label) {
    Assert-R14MarkerAvailable $Path $Label
    try {
        [IO.File]::Open([IO.Path]::GetFullPath($Path), [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    }
    catch [IO.IOException] {
        if (Test-Path -LiteralPath $Path) { throw (New-R14MarkerRefusalException "r14 $Label marker was consumed by a concurrent invocation: $Path") }
        throw
    }
}

function Assert-R14OwnedLifecycleAvailable([string]$LifecyclePath, [string]$MarkerPath, [string]$Label) {
    if (-not (Test-Path -LiteralPath $LifecyclePath)) { return }
    if (Test-Path -LiteralPath $MarkerPath) { throw (New-R14MarkerRefusalException "r14 $Label lifecycle belongs to an invocation that consumed its permanent marker: $LifecyclePath") }
    throw "r14 $Label lifecycle exists without its permanent marker: $LifecyclePath"
}

function Get-R14FailureExitCode([Exception]$Exception) {
    if ($null -ne $Exception -and $Exception.Data.Contains('r14_exit_code') -and [int]$Exception.Data['r14_exit_code'] -eq 91) { return 91 }
    92
}

function Assert-R14GpuComputeProbeResult([int]$ExitCode, [object[]]$Output, [string]$Boundary) {
    if ($ExitCode -ne 0) { throw "r14 GPU compute-process probe failed at $Boundary" }
    $active = @($Output | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($active.Count) { throw "r14 GPU compute process collision at ${Boundary}: $($active -join ',')" }
}

function Assert-R14GpuComputeIdle([string]$Boundary) {
    $output = @(& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "set -o pipefail; nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d'")
    $exitCode = [int]$LASTEXITCODE
    Assert-R14GpuComputeProbeResult $exitCode $output $Boundary
}

function Assert-R14BoundDispatchRecord(
    [string]$DispatchMarkerPath,
    [string]$DispatchLifecyclePath,
    [string]$RunIdPrefix,
    [string]$TaskName,
    [string]$CanonicalGateSha256,
    [string]$UserConfirmationSha256
) {
    if (-not (Test-Path -LiteralPath $DispatchMarkerPath -PathType Leaf)) { throw 'r14 dispatch marker is absent before attempt-marker creation' }
    if ((Get-Item -LiteralPath $DispatchMarkerPath).Length -ne 0) { throw 'r14 dispatch marker content changed' }
    if (-not (Test-Path -LiteralPath $DispatchLifecyclePath -PathType Leaf)) { throw 'r14 dispatch lifecycle is absent before attempt-marker creation' }

    $probe = $null
    $exclusivelyHeld = $false
    try { $probe = [IO.File]::Open([IO.Path]::GetFullPath($DispatchMarkerPath), [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite) }
    catch [IO.IOException] { $exclusivelyHeld = $true }
    finally { if ($null -ne $probe) { $probe.Dispose() } }
    if (-not $exclusivelyHeld) { throw 'r14 dispatch marker is not exclusively held by the live dispatcher' }

    $matches = @()
    foreach ($line in @(Get-Content -LiteralPath $DispatchLifecyclePath -ErrorAction Stop)) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $event = $line | ConvertFrom-Json -ErrorAction Stop }
        catch { throw 'r14 dispatch lifecycle contains malformed JSON' }
        if ($event.event -eq 'dispatch_created' -and $event.run_id_prefix -eq $RunIdPrefix -and $event.task_name -eq $TaskName -and $event.canonical_gate_sha256 -eq $CanonicalGateSha256 -and $event.user_confirmation_sha256 -eq $UserConfirmationSha256) { $matches += @($event) }
    }
    if ($matches.Count -ne 1) { throw "r14 requires exactly one bound dispatch_created event; found $($matches.Count)" }
    $matches[0]
}

function Get-R14ExpectedSupervisorActionArguments(
    [Parameter(Mandatory = $true)][string]$SupervisorPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$CanonicalGateSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$UserConfirmationSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^SleepStagePaper-r14-(?:COM|Canary)-[0-9a-f]{32}$')][string]$TaskName
) {
    $fullSupervisorPath = [IO.Path]::GetFullPath($SupervisorPath)
    if ($fullSupervisorPath.IndexOfAny([char[]]@('"', "`r", "`n")) -ge 0) { throw 'r14 supervisor path contains an unsafe command-line character' }
    $quotedSupervisorPath = '"' + $fullSupervisorPath.Replace('"', '\"') + '"'
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File {0} -ExpectedCanonicalGateSha256 {1} -ExpectedUserConfirmationSha256 {2} -TaskName {3}' -f $quotedSupervisorPath, $CanonicalGateSha256.ToLowerInvariant(), $UserConfirmationSha256.ToLowerInvariant(), $TaskName
}

function Assert-R14SupervisorActionArguments(
    [Parameter(Mandatory = $true)][string]$Arguments,
    [Parameter(Mandatory = $true)][string]$SupervisorPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$CanonicalGateSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$UserConfirmationSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^SleepStagePaper-r14-(?:COM|Canary)-[0-9a-f]{32}$')][string]$TaskName
) {
    $expected = Get-R14ExpectedSupervisorActionArguments $SupervisorPath $CanonicalGateSha256 $UserConfirmationSha256 $TaskName
    if ($Arguments -cne $expected) { throw 'r14 Task Scheduler action arguments differ from the exact scalar construction' }
    if ($Arguments.Length -gt 1024) { throw "r14 Task Scheduler action arguments exceed the 1024-character fail-closed bound: $($Arguments.Length)" }
    if ($Arguments -match '@\{' -or $Arguments -match '(?m)[\r\n]' -or $Arguments.Contains('.sha256')) { throw 'r14 Task Scheduler action arguments contain object serialization or an unsafe token' }
    foreach ($sha in @($CanonicalGateSha256.ToLowerInvariant(), $UserConfirmationSha256.ToLowerInvariant())) {
        if ([regex]::Matches($Arguments, [regex]::Escape($sha)).Count -ne 1) { throw "r14 Task Scheduler action does not bind SHA exactly once: $sha" }
    }
    if ([regex]::Matches($Arguments, [regex]::Escape($TaskName)).Count -ne 1) { throw 'r14 Task Scheduler action does not bind the task name exactly once' }
    $true
}

function New-R14SupervisorActionArguments(
    [Parameter(Mandatory = $true)][string]$SupervisorPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$CanonicalGateSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$UserConfirmationSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^SleepStagePaper-r14-(?:COM|Canary)-[0-9a-f]{32}$')][string]$TaskName
) {
    $arguments = Get-R14ExpectedSupervisorActionArguments $SupervisorPath $CanonicalGateSha256 $UserConfirmationSha256 $TaskName
    Assert-R14SupervisorActionArguments $arguments $SupervisorPath $CanonicalGateSha256 $UserConfirmationSha256 $TaskName | Out-Null
    $arguments
}

function Get-R14TextSha256([string]$Text) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Text)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { -join ($hasher.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) }
    finally { $hasher.Dispose() }
}

function Get-R14ExpectedAgentInterpretationText(
    [string]$RunIdPrefix,
    [int[]]$Seeds,
    [string[]]$ExpectedChildren,
    [string]$CanonicalGateSha256
) {
    "Standing authorization is applied by the agent to fresh r14 exactly once: prefix $RunIdPrefix, ordered seeds $($Seeds -join ','), children $($ExpectedChildren[0]) and $($ExpectedChildren[1]), canonical gate SHA-256 $CanonicalGateSha256; protocol PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1 global norm 1.0 after averaging 128 gradients; permanent CreateNew+FileShare.None dispatch and attempt markers; no retry, no resume, no reuse. This sentence is an agent interpretation, not a user quote."
}

function Assert-R14DelegatedAuthorization(
    [object]$Confirmation,
    [string]$RunIdPrefix,
    [int[]]$Seeds,
    [string[]]$ExpectedChildren,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$CanonicalGateSha256,
    [string]$DispatchMarkerPath,
    [string]$AttemptMarkerPath
) {
    if ($Confirmation.schema_version -ne 2 -or $Confirmation.artifact_type -ne 'delegated_user_launch_authorization' -or $Confirmation.status -ne 'confirmed' -or $Confirmation.authorization_mode -ne 'standing_user_authorization_with_agent_bound_scope') { throw 'r14 delegated authorization schema/status failed' }
    if ($Confirmation.run_id_prefix -ne $RunIdPrefix -or (@($Confirmation.seeds) -join '|') -ne (@($Seeds) -join '|') -or (@($Confirmation.expected_children) -join '|') -ne (@($ExpectedChildren) -join '|') -or $Confirmation.canonical_gate_sha256 -ne $CanonicalGateSha256) { throw 'r14 delegated authorization identity failed' }
    if ($Confirmation.user_directly_requested_exact_r14_identity -ne $false -or $Confirmation.standing_authorization_applied_to_r14 -ne $true -or $Confirmation.confirmation_revoked -ne $false) { throw 'r14 delegated authorization claim boundary failed' }

    $expectedExcerpts = @(
        [pscustomobject]@{ ordinal = 1; exact_excerpt = 'เอางี้หลังจากนี้ให้ทำไปเลย ฉันอนุญาต ไม่ต้องรอฉันทำไปได้เลย'; sha256 = '4541f3398d3f87ea7db0571fe551794078e2d43f62880b887cd669da181dfb4b' },
        [pscustomobject]@{ ordinal = 2; exact_excerpt = 'ฉันบอกว่าไม่ต้องสนกฎอื่นก่อนหน้านี้ ฉันบกอว่าให้สิทธิคุณทำได้เลย'; sha256 = '7460c25fec0865b3f9e200b1b8e734392f526fbb349305a4895b7391ea96100b' }
    )
    $actualExcerpts = @($Confirmation.user_authorization_excerpts)
    if ($actualExcerpts.Count -ne 2) { throw 'r14 delegated authorization requires both exact user excerpts' }
    for ($index = 0; $index -lt 2; $index++) {
        $actual = $actualExcerpts[$index]
        $expected = $expectedExcerpts[$index]
        if ([int]$actual.ordinal -ne [int]$expected.ordinal -or [string]$actual.role -ne 'user' -or [string]$actual.source_thread_id -ne '01a014bc-7bc1-7590-bd2b-029c8a84285b' -or [string]$actual.exact_excerpt -cne [string]$expected.exact_excerpt -or [string]$actual.sha256 -ne [string]$expected.sha256 -or (Get-R14TextSha256 ([string]$actual.exact_excerpt)) -ne [string]$expected.sha256) { throw "r14 delegated authorization user excerpt mismatch at ordinal $($index + 1)" }
    }
    $combined = [string]$actualExcerpts[0].exact_excerpt + "`n" + [string]$actualExcerpts[1].exact_excerpt
    if ($Confirmation.user_authorization_combined_encoding -ne 'utf-8-no-bom-excerpt1-lf-excerpt2' -or $Confirmation.user_authorization_combined_sha256 -ne '1acefb63aa855c34e9fa1163d5818bac6f5ee80cbdbe406cf9058a4eba2c639e' -or (Get-R14TextSha256 $combined) -ne [string]$Confirmation.user_authorization_combined_sha256) { throw 'r14 delegated authorization combined provenance failed' }

    $interpretation = $Confirmation.agent_interpretation
    $expectedText = Get-R14ExpectedAgentInterpretationText $RunIdPrefix $Seeds $ExpectedChildren $CanonicalGateSha256
    if ($interpretation.label -ne 'agent_interpretation_not_user_quote' -or $interpretation.authored_by -ne 'codex_agent' -or $interpretation.is_user_quote -ne $false -or $interpretation.standing_authorization_applied_to_r14 -ne $true -or $interpretation.interpretation_text -cne $expectedText -or $interpretation.interpretation_sha256 -ne (Get-R14TextSha256 $expectedText)) { throw 'r14 agent interpretation label/text binding failed' }
    if ($interpretation.run_id_prefix -ne $RunIdPrefix -or (@($interpretation.seeds) -join '|') -ne (@($Seeds) -join '|') -or (@($interpretation.expected_children) -join '|') -ne (@($ExpectedChildren) -join '|') -or $interpretation.canonical_gate_sha256 -ne $CanonicalGateSha256) { throw 'r14 agent interpretation identity binding failed' }
    if ($interpretation.stage3_stability_adaptation_id -ne 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1' -or [double]$interpretation.stage3_gradient_clip_norm -ne 1.0 -or [int]$interpretation.stage3_gradient_accumulation_steps -ne 128 -or $interpretation.dispatch_marker_path -ne [IO.Path]::GetFullPath($DispatchMarkerPath) -or $interpretation.attempt_marker_path -ne [IO.Path]::GetFullPath($AttemptMarkerPath) -or $interpretation.marker_file_mode -ne 'CreateNew' -or $interpretation.marker_file_share -ne 'None' -or $interpretation.no_retry_after_marker_consumption -ne $true -or $interpretation.no_resume -ne $true -or $interpretation.no_reuse -ne $true -or $interpretation.exactly_once_launch_authorized -ne $true) { throw 'r14 agent interpretation protocol/marker boundary failed' }
    $true
}
