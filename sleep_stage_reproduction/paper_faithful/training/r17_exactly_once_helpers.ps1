function New-R17MarkerRefusalException([string]$Message) {
    $exception = New-Object System.InvalidOperationException($Message)
    $exception.Data['r17_exit_code'] = 91
    $exception
}

function Assert-R17MarkerAvailable([string]$Path, [string]$Label) {
    if (Test-Path -LiteralPath $Path) { throw (New-R17MarkerRefusalException "r17 $Label marker is already consumed: $Path") }
}

function Open-R17PermanentMarker([string]$Path, [string]$Label) {
    Assert-R17MarkerAvailable $Path $Label
    try {
        [IO.File]::Open([IO.Path]::GetFullPath($Path), [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    }
    catch [IO.IOException] {
        if (Test-Path -LiteralPath $Path) { throw (New-R17MarkerRefusalException "r17 $Label marker was consumed by a concurrent invocation: $Path") }
        throw
    }
}

function Assert-R17OwnedLifecycleAvailable([string]$LifecyclePath, [string]$MarkerPath, [string]$Label) {
    if (-not (Test-Path -LiteralPath $LifecyclePath)) { return }
    if (Test-Path -LiteralPath $MarkerPath) { throw (New-R17MarkerRefusalException "r17 $Label lifecycle belongs to an invocation that consumed its permanent marker: $LifecyclePath") }
    throw "r17 $Label lifecycle exists without its permanent marker: $LifecyclePath"
}

function Get-R17FailureExitCode([Exception]$Exception) {
    if ($null -ne $Exception -and $Exception.Data.Contains('r17_exit_code') -and [int]$Exception.Data['r17_exit_code'] -eq 91) { return 91 }
    92
}

$r17NativeAssemblyPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'r17_native_probe.dll'))
if (-not ('SleepStageR17.NativeMethods' -as [type])) {
    if (-not (Test-Path -LiteralPath $r17NativeAssemblyPath -PathType Leaf)) { throw "r17 precompiled native probe assembly is absent: $r17NativeAssemblyPath" }
    [void][Reflection.Assembly]::LoadFrom($r17NativeAssemblyPath)
}
if (-not ('SleepStageR17.NativeMethods' -as [type])) { throw 'r17 precompiled native probe type did not load' }

function Get-R17NativeParentProcessId {
    [SleepStageR17.NativeMethods]::GetCurrentParentProcessId()
}

function Get-R17NativePowerStatus {
    $status = [SleepStageR17.NativeMethods]::GetPowerStatus()
    [pscustomobject]@{
        power_online = ([int]$status.ACLineStatus -eq 1)
        ac_line_status = [int]$status.ACLineStatus
        battery_flag = [int]$status.BatteryFlag
        battery_percent = [int]$status.BatteryLifePercent
        critical = (([int]$status.BatteryFlag -band 4) -ne 0)
        unknown = ([int]$status.ACLineStatus -eq 255 -or [int]$status.BatteryFlag -eq 255)
    }
}

function Get-R17NativeDriveFreeGiB([ValidatePattern('^[A-Za-z]:\\$')][string]$RootPath) {
    [double]([SleepStageR17.NativeMethods]::GetFreeBytesAvailable($RootPath)) / 1GB
}

function Read-R17RedirectedProcessText([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return '' }
    $bytes = [IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -eq 0) { return '' }
    if ($bytes.Length -ge 2 -and $bytes[0] -eq 0xff -and $bytes[1] -eq 0xfe) {
        return [Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2)
    }
    $sampleLength = [Math]::Min($bytes.Length, 256)
    $oddPositions = 0
    $oddZeros = 0
    for ($index = 1; $index -lt $sampleLength; $index += 2) {
        $oddPositions++
        if ($bytes[$index] -eq 0) { $oddZeros++ }
    }
    if ($oddPositions -gt 0 -and $oddZeros -ge [Math]::Ceiling($oddPositions * 0.75)) {
        return [Text.Encoding]::Unicode.GetString($bytes)
    }
    [Text.UTF8Encoding]::new($false, $true).GetString($bytes)
}

function Invoke-R17BoundedProcess(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$ArgumentList = @(),
    [ValidateRange(1, 120)][int]$TimeoutSeconds = 30,
    [Parameter(Mandatory = $true)][string]$Boundary
) {
    $probeRoot = 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r17-probe-temp'
    [IO.Directory]::CreateDirectory($probeRoot) | Out-Null
    $probeId = [Guid]::NewGuid().ToString('N')
    $stdoutPath = Join-Path $probeRoot "$probeId.stdout.txt"
    $stderrPath = Join-Path $probeRoot "$probeId.stderr.txt"
    $process = $null
    try {
        $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            try { $process.Kill() } catch {}
            try { $process.WaitForExit(10000) | Out-Null } catch {}
            throw "r17 bounded process timed out at ${Boundary}: $FilePath"
        }
        $process.WaitForExit()
        $stdout = Read-R17RedirectedProcessText $stdoutPath
        $stderr = Read-R17RedirectedProcessText $stderrPath
        [pscustomobject]@{
            exit_code = [int]$process.ExitCode
            stdout = $stdout
            stderr = $stderr
            boundary = $Boundary
            timed_out = $false
        }
    }
    finally {
        if ($null -ne $process) { $process.Dispose() }
        foreach ($path in @($stdoutPath, $stderrPath)) {
            if (Test-Path -LiteralPath $path) { [IO.File]::Delete($path) }
        }
    }
}

function Invoke-R17BoundedWslScript(
    [Parameter(Mandatory = $true)][string]$ScriptText,
    [ValidateRange(2, 120)][int]$TimeoutSeconds = 30,
    [Parameter(Mandatory = $true)][string]$Boundary
) {
    $probeRoot = 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r17-probe-temp'
    [IO.Directory]::CreateDirectory($probeRoot) | Out-Null
    $probeId = [Guid]::NewGuid().ToString('N')
    $scriptPath = Join-Path $probeRoot "$probeId.sh"
    $successSentinel = '__R17_WSL_PROBE_OK__'
    $scriptBytes = [Text.UTF8Encoding]::new($false).GetBytes("#!/usr/bin/env bash`nset -euo pipefail`n$ScriptText`nprintf '$successSentinel\n'`n")
    $stream = [IO.File]::Open($scriptPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($scriptBytes, 0, $scriptBytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    $wslPath = '/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/r17-probe-temp/' + [IO.Path]::GetFileName($scriptPath)
    $linuxTimeoutSeconds = [Math]::Max(1, $TimeoutSeconds - 5)
    try {
        $result = Invoke-R17BoundedProcess 'wsl.exe' @('-d', 'Ubuntu', '-e', 'timeout', '--signal=KILL', "${linuxTimeoutSeconds}s", 'bash', '--noprofile', '--norc', $wslPath) $TimeoutSeconds $Boundary
        $combined = ([string]$result.stdout) + "`n" + ([string]$result.stderr)
        if ([int]$result.exit_code -ne 0 -or $combined -match '(?i)Error code:\s*Wsl/|Wsl/Service/|CreateVm/|0x800705aa|Insufficient system resources' -or $result.stdout -notmatch "(?m)^$([regex]::Escape($successSentinel))\r?$" ) {
            throw "r17 WSL probe failed at ${Boundary}: exit=$($result.exit_code) output=$($combined.Trim())"
        }
        $cleaned = (($result.stdout -split '\r?\n') | Where-Object { $_ -cne $successSentinel }) -join "`n"
        [pscustomobject]@{exit_code=0;stdout=$cleaned;stderr=[string]$result.stderr;boundary=$Boundary;timed_out=$false;success_sentinel_validated=$true}
    }
    finally {
        if (Test-Path -LiteralPath $scriptPath) { [IO.File]::Delete($scriptPath) }
    }
}

function Assert-R17GpuComputeProbeResult([int]$ExitCode, [object[]]$Output, [string]$Boundary) {
    if ($ExitCode -ne 0) { throw "r17 GPU compute-process probe failed at $Boundary" }
    $active = @($Output | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($active.Count) { throw "r17 GPU compute process collision at ${Boundary}: $($active -join ',')" }
}

function Assert-R17GpuComputeIdle([string]$Boundary) {
    $result = Invoke-R17BoundedWslScript "nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d'" 30 $Boundary
    $output = @($result.stdout -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    Assert-R17GpuComputeProbeResult ([int]$result.exit_code) $output $Boundary
}

function Get-R17WindowsGpuProcessSnapshot([string]$Boundary) {
    $nvidia = (Get-Command nvidia-smi.exe -ErrorAction Stop).Source
    $result = Invoke-R17BoundedProcess $nvidia @('--query-compute-apps=pid,process_name,used_gpu_memory', '--format=csv,noheader,nounits') 30 $Boundary
    if ([int]$result.exit_code -ne 0) { throw "r17 Windows GPU process probe failed at $Boundary" }
    $entries = @()
    foreach ($line in @([string]$result.stdout -split '\r?\n')) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line -notmatch '^\s*(?<pid>[0-9]+)\s*,\s*(?<name>.*?)\s*,\s*(?<memory>.*?)\s*$') { throw "r17 Windows GPU process output is malformed at ${Boundary}: $line" }
        $entries += [pscustomobject]@{pid=[int]$Matches.pid;process_name=[string]$Matches.name;used_gpu_memory=[string]$Matches.memory;raw=[string]$line.Trim()}
    }
    $pids = @($entries | ForEach-Object { [int]$_.pid } | Sort-Object -Unique)
    [pscustomobject]@{boundary=$Boundary;pids=$pids;entries=$entries;captured_at=(Get-Date).ToString('o')}
}

function Assert-R17ObservedIdleGpuAdmission(
    [Parameter(Mandatory=$true)]$Request,
    [Parameter(Mandatory=$true)]$BaselineSnapshot,
    [Parameter(Mandatory=$true)]$CurrentSnapshot,
    [Parameter(Mandatory=$true)][string]$ExpectedPrefix,
    [Parameter(Mandatory=$true)][string]$ExpectedRunId,
    [Parameter(Mandatory=$true)][ValidateSet('stage1','stage2','stage3')][string]$ExpectedStage
) {
    $design = 'R17_DEDICATED_HOST_OBSERVED_IDLE_GPU_ADMISSION_V1'
    $requiredFields = @('schema_version','design_id','run_id_prefix','run_id','stage','nonce','linux_pid','device','context_acquired')
    $actualFields = @($Request.PSObject.Properties.Name)
    if ($actualFields.Count -ne $requiredFields.Count -or @($requiredFields | Where-Object { $actualFields -notcontains $_ }).Count -or [int]$Request.schema_version -ne 1 -or [string]$Request.design_id -ne $design -or [string]$Request.run_id_prefix -ne $ExpectedPrefix -or [string]$Request.run_id -ne $ExpectedRunId -or [string]$Request.stage -ne $ExpectedStage -or $Request.context_acquired -ne $true -or [string]$Request.device -ne '/GPU:0' -or [int]$Request.linux_pid -lt 1 -or [string]$Request.nonce -notmatch '^[0-9a-f]{32}$') { throw 'r17 GPU admission request identity is invalid' }
    $baseline = @($BaselineSnapshot.pids | ForEach-Object { [int]$_ } | Sort-Object -Unique)
    $current = @($CurrentSnapshot.pids | ForEach-Object { [int]$_ } | Sort-Object -Unique)
    if ($baseline -contains 4) { throw 'r17 GPU baseline already contains the WSL CUDA system context' }
    foreach ($pidValue in $baseline) { if ($current -notcontains $pidValue) { throw "r17 GPU baseline process disappeared during admission: $pidValue" } }
    $extra = @($current | Where-Object { $baseline -notcontains $_ })
    if ($extra.Count -ne 1 -or [int]$extra[0] -ne 4) { throw "r17 GPU admission observed an unexpected post-context process set: $($extra -join ',')" }
    [pscustomobject]@{status='approved';design_id=$design;baseline_pids=$baseline;current_pids=$current;expected_wsl_system_pid=4;observability_limit='WDDM exposes the admitted WSL CUDA context as Windows System PID 4 and does not expose Linux guest PIDs';absolute_third_party_exclusivity_claimed=$false}
}

function Write-R17ImmutableJson([string]$Path, $Value) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Compress -Depth 12) + [Environment]::NewLine)
    $stream = [IO.File]::Open([IO.Path]::GetFullPath($Path), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

function Assert-R17BoundDispatchRecord(
    [string]$DispatchMarkerPath,
    [string]$DispatchLifecyclePath,
    [string]$RunIdPrefix,
    [string]$TaskName,
    [string]$CanonicalGateSha256,
    [string]$UserConfirmationSha256
) {
    if (-not (Test-Path -LiteralPath $DispatchMarkerPath -PathType Leaf)) { throw 'r17 dispatch marker is absent before attempt-marker creation' }
    if ((Get-Item -LiteralPath $DispatchMarkerPath).Length -ne 0) { throw 'r17 dispatch marker content changed' }
    if (-not (Test-Path -LiteralPath $DispatchLifecyclePath -PathType Leaf)) { throw 'r17 dispatch lifecycle is absent before attempt-marker creation' }

    $probe = $null
    $exclusivelyHeld = $false
    try { $probe = [IO.File]::Open([IO.Path]::GetFullPath($DispatchMarkerPath), [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite) }
    catch [IO.IOException] { $exclusivelyHeld = $true }
    finally { if ($null -ne $probe) { $probe.Dispose() } }
    if (-not $exclusivelyHeld) { throw 'r17 dispatch marker is not exclusively held by the live dispatcher' }

    $matches = @()
    foreach ($line in @(Get-Content -LiteralPath $DispatchLifecyclePath -ErrorAction Stop)) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $event = $line | ConvertFrom-Json -ErrorAction Stop }
        catch { throw 'r17 dispatch lifecycle contains malformed JSON' }
        if ($event.event -eq 'dispatch_created' -and $event.run_id_prefix -eq $RunIdPrefix -and $event.task_name -eq $TaskName -and $event.canonical_gate_sha256 -eq $CanonicalGateSha256 -and $event.user_confirmation_sha256 -eq $UserConfirmationSha256) { $matches += @($event) }
    }
    if ($matches.Count -ne 1) { throw "r17 requires exactly one bound dispatch_created event; found $($matches.Count)" }
    $matches[0]
}

function Get-R17ExpectedSupervisorActionArguments(
    [Parameter(Mandatory = $true)][string]$SupervisorPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$CanonicalGateSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$UserConfirmationSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^SleepStagePaper-r17-(?:COM|Canary)-[0-9a-f]{32}$')][string]$TaskName,
    [string]$CanaryRoot
) {
    $fullSupervisorPath = [IO.Path]::GetFullPath($SupervisorPath)
    if ($fullSupervisorPath.IndexOfAny([char[]]@('"', "`r", "`n")) -ge 0) { throw 'r17 supervisor path contains an unsafe command-line character' }
    $quotedSupervisorPath = '"' + $fullSupervisorPath.Replace('"', '\"') + '"'
    $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File {0} -ExpectedCanonicalGateSha256 {1} -ExpectedUserConfirmationSha256 {2} -TaskName {3}' -f $quotedSupervisorPath, $CanonicalGateSha256.ToLowerInvariant(), $UserConfirmationSha256.ToLowerInvariant(), $TaskName
    $isCanary = $TaskName -match '^SleepStagePaper-r17-Canary-(?<case>[0-9a-f]{32})$'
    if ($isCanary) {
        if ([string]::IsNullOrWhiteSpace($CanaryRoot)) { throw 'r17 canary action requires CanaryRoot' }
        $fullCanaryRoot = [IO.Path]::GetFullPath($CanaryRoot)
        $expectedCanaryRoot = "E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r17-supervisor-canaries\$($Matches.case)"
        if (-not $fullCanaryRoot.Equals($expectedCanaryRoot, [StringComparison]::OrdinalIgnoreCase) -or $fullCanaryRoot.IndexOfAny([char[]]@('"', "'", ' ', "`t", "`r", "`n")) -ge 0) { throw 'r17 CanaryRoot is outside its exact bounded namespace' }
        $arguments += ' -CanaryRoot "' + $fullCanaryRoot + '"'
    }
    elseif (-not [string]::IsNullOrWhiteSpace($CanaryRoot)) { throw 'r17 production action cannot carry CanaryRoot' }
    $arguments
}

function Assert-R17SupervisorActionArguments(
    [Parameter(Mandatory = $true)][string]$Arguments,
    [Parameter(Mandatory = $true)][string]$SupervisorPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$CanonicalGateSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$UserConfirmationSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^SleepStagePaper-r17-(?:COM|Canary)-[0-9a-f]{32}$')][string]$TaskName,
    [string]$CanaryRoot
) {
    $expected = Get-R17ExpectedSupervisorActionArguments $SupervisorPath $CanonicalGateSha256 $UserConfirmationSha256 $TaskName $CanaryRoot
    if ($Arguments -cne $expected) { throw 'r17 Task Scheduler action arguments differ from the exact scalar construction' }
    if ($Arguments.Length -gt 1024) { throw "r17 Task Scheduler action arguments exceed the 1024-character fail-closed bound: $($Arguments.Length)" }
    if ($Arguments -match '@\{' -or $Arguments -match '(?m)[\r\n]' -or $Arguments.Contains('.sha256')) { throw 'r17 Task Scheduler action arguments contain object serialization or an unsafe token' }
    foreach ($sha in @($CanonicalGateSha256.ToLowerInvariant(), $UserConfirmationSha256.ToLowerInvariant())) {
        if ([regex]::Matches($Arguments, [regex]::Escape($sha)).Count -ne 1) { throw "r17 Task Scheduler action does not bind SHA exactly once: $sha" }
    }
    if ([regex]::Matches($Arguments, [regex]::Escape($TaskName)).Count -ne 1) { throw 'r17 Task Scheduler action does not bind the task name exactly once' }
    if ($TaskName -match '^SleepStagePaper-r17-Canary-') {
        if ([regex]::Matches($Arguments, [regex]::Escape([IO.Path]::GetFullPath($CanaryRoot))).Count -ne 1) { throw 'r17 canary action does not bind CanaryRoot exactly once' }
    }
    elseif ($Arguments -match '(?:^|\s)-CanaryRoot(?:\s|$)') { throw 'r17 production action unexpectedly contains CanaryRoot' }
    $true
}

function New-R17SupervisorActionArguments(
    [Parameter(Mandatory = $true)][string]$SupervisorPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$CanonicalGateSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$UserConfirmationSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^SleepStagePaper-r17-(?:COM|Canary)-[0-9a-f]{32}$')][string]$TaskName,
    [string]$CanaryRoot
) {
    $arguments = Get-R17ExpectedSupervisorActionArguments $SupervisorPath $CanonicalGateSha256 $UserConfirmationSha256 $TaskName $CanaryRoot
    Assert-R17SupervisorActionArguments $arguments $SupervisorPath $CanonicalGateSha256 $UserConfirmationSha256 $TaskName $CanaryRoot | Out-Null
    $arguments
}

function Get-R17TextSha256([string]$Text) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Text)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { -join ($hasher.ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) }
    finally { $hasher.Dispose() }
}

function Get-R17ExpectedAgentInterpretationText(
    [string]$RunIdPrefix,
    [int[]]$Seeds,
    [string[]]$ExpectedChildren,
    [string]$CanonicalGateSha256
) {
    "Standing authorization is applied by the agent to fresh r17 exactly once: prefix $RunIdPrefix, ordered seeds $($Seeds -join ','), children $($ExpectedChildren[0]) and $($ExpectedChildren[1]), canonical gate SHA-256 $CanonicalGateSha256; protocol PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1 global norm 1.0 after averaging 128 gradients; permanent CreateNew+FileShare.None dispatch and attempt markers; no retry, no resume, no reuse. This sentence is an agent interpretation, not a user quote."
}

function Assert-R17DelegatedAuthorization(
    [object]$Confirmation,
    [string]$RunIdPrefix,
    [int[]]$Seeds,
    [string[]]$ExpectedChildren,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$CanonicalGateSha256,
    [string]$DispatchMarkerPath,
    [string]$AttemptMarkerPath
) {
    if ($Confirmation.schema_version -ne 2 -or $Confirmation.artifact_type -ne 'delegated_user_launch_authorization' -or $Confirmation.status -ne 'confirmed' -or $Confirmation.authorization_mode -ne 'standing_user_authorization_with_agent_bound_scope') { throw 'r17 delegated authorization schema/status failed' }
    if ($Confirmation.run_id_prefix -ne $RunIdPrefix -or (@($Confirmation.seeds) -join '|') -ne (@($Seeds) -join '|') -or (@($Confirmation.expected_children) -join '|') -ne (@($ExpectedChildren) -join '|') -or $Confirmation.canonical_gate_sha256 -ne $CanonicalGateSha256) { throw 'r17 delegated authorization identity failed' }
    if ($Confirmation.user_directly_requested_exact_r17_identity -ne $false -or $Confirmation.standing_authorization_applied_to_r17 -ne $true -or $Confirmation.confirmation_revoked -ne $false) { throw 'r17 delegated authorization claim boundary failed' }

    $expectedExcerpts = @(
        [pscustomobject]@{ ordinal = 1; exact_excerpt = 'เอางี้หลังจากนี้ให้ทำไปเลย ฉันอนุญาต ไม่ต้องรอฉันทำไปได้เลย'; sha256 = '4541f3398d3f87ea7db0571fe551794078e2d43f62880b887cd669da181dfb4b' },
        [pscustomobject]@{ ordinal = 2; exact_excerpt = 'ฉันบอกว่าไม่ต้องสนกฎอื่นก่อนหน้านี้ ฉันบกอว่าให้สิทธิคุณทำได้เลย'; sha256 = '7460c25fec0865b3f9e200b1b8e734392f526fbb349305a4895b7391ea96100b' }
    )
    $actualExcerpts = @($Confirmation.user_authorization_excerpts)
    if ($actualExcerpts.Count -ne 2) { throw 'r17 delegated authorization requires both exact user excerpts' }
    for ($index = 0; $index -lt 2; $index++) {
        $actual = $actualExcerpts[$index]
        $expected = $expectedExcerpts[$index]
        if ([int]$actual.ordinal -ne [int]$expected.ordinal -or [string]$actual.role -ne 'user' -or [string]$actual.source_thread_id -ne '01a014bc-7bc1-7590-bd2b-029c8a84285b' -or [string]$actual.exact_excerpt -cne [string]$expected.exact_excerpt -or [string]$actual.sha256 -ne [string]$expected.sha256 -or (Get-R17TextSha256 ([string]$actual.exact_excerpt)) -ne [string]$expected.sha256) { throw "r17 delegated authorization user excerpt mismatch at ordinal $($index + 1)" }
    }
    $combined = [string]$actualExcerpts[0].exact_excerpt + "`n" + [string]$actualExcerpts[1].exact_excerpt
    if ($Confirmation.user_authorization_combined_encoding -ne 'utf-8-no-bom-excerpt1-lf-excerpt2' -or $Confirmation.user_authorization_combined_sha256 -ne '1acefb63aa855c34e9fa1163d5818bac6f5ee80cbdbe406cf9058a4eba2c639e' -or (Get-R17TextSha256 $combined) -ne [string]$Confirmation.user_authorization_combined_sha256) { throw 'r17 delegated authorization combined provenance failed' }

    $interpretation = $Confirmation.agent_interpretation
    $expectedText = Get-R17ExpectedAgentInterpretationText $RunIdPrefix $Seeds $ExpectedChildren $CanonicalGateSha256
    if ($interpretation.label -ne 'agent_interpretation_not_user_quote' -or $interpretation.authored_by -ne 'codex_agent' -or $interpretation.is_user_quote -ne $false -or $interpretation.standing_authorization_applied_to_r17 -ne $true -or $interpretation.interpretation_text -cne $expectedText -or $interpretation.interpretation_sha256 -ne (Get-R17TextSha256 $expectedText)) { throw 'r17 agent interpretation label/text binding failed' }
    if ($interpretation.run_id_prefix -ne $RunIdPrefix -or (@($interpretation.seeds) -join '|') -ne (@($Seeds) -join '|') -or (@($interpretation.expected_children) -join '|') -ne (@($ExpectedChildren) -join '|') -or $interpretation.canonical_gate_sha256 -ne $CanonicalGateSha256) { throw 'r17 agent interpretation identity binding failed' }
    if ($interpretation.stage3_stability_adaptation_id -ne 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1' -or [double]$interpretation.stage3_gradient_clip_norm -ne 1.0 -or [int]$interpretation.stage3_gradient_accumulation_steps -ne 128 -or $interpretation.dispatch_marker_path -ne [IO.Path]::GetFullPath($DispatchMarkerPath) -or $interpretation.attempt_marker_path -ne [IO.Path]::GetFullPath($AttemptMarkerPath) -or $interpretation.marker_file_mode -ne 'CreateNew' -or $interpretation.marker_file_share -ne 'None' -or $interpretation.no_retry_after_marker_consumption -ne $true -or $interpretation.no_resume -ne $true -or $interpretation.no_reuse -ne $true -or $interpretation.exactly_once_launch_authorized -ne $true) { throw 'r17 agent interpretation protocol/marker boundary failed' }
    $true
}
