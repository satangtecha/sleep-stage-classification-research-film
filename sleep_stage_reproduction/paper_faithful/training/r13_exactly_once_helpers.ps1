function New-R13MarkerRefusalException([string]$Message) {
    $exception = New-Object System.InvalidOperationException($Message)
    $exception.Data['r13_exit_code'] = 91
    $exception
}

function Assert-R13MarkerAvailable([string]$Path, [string]$Label) {
    if (Test-Path -LiteralPath $Path) { throw (New-R13MarkerRefusalException "r13 $Label marker is already consumed: $Path") }
}

function Open-R13PermanentMarker([string]$Path, [string]$Label) {
    Assert-R13MarkerAvailable $Path $Label
    try {
        [IO.File]::Open([IO.Path]::GetFullPath($Path), [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    }
    catch [IO.IOException] {
        if (Test-Path -LiteralPath $Path) { throw (New-R13MarkerRefusalException "r13 $Label marker was consumed by a concurrent invocation: $Path") }
        throw
    }
}

function Assert-R13OwnedLifecycleAvailable([string]$LifecyclePath, [string]$MarkerPath, [string]$Label) {
    if (-not (Test-Path -LiteralPath $LifecyclePath)) { return }
    if (Test-Path -LiteralPath $MarkerPath) { throw (New-R13MarkerRefusalException "r13 $Label lifecycle belongs to an invocation that consumed its permanent marker: $LifecyclePath") }
    throw "r13 $Label lifecycle exists without its permanent marker: $LifecyclePath"
}

function Get-R13FailureExitCode([Exception]$Exception) {
    if ($null -ne $Exception -and $Exception.Data.Contains('r13_exit_code') -and [int]$Exception.Data['r13_exit_code'] -eq 91) { return 91 }
    92
}

function Assert-R13GpuComputeProbeResult([int]$ExitCode, [object[]]$Output, [string]$Boundary) {
    if ($ExitCode -ne 0) { throw "r13 GPU compute-process probe failed at $Boundary" }
    $active = @($Output | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($active.Count) { throw "r13 GPU compute process collision at ${Boundary}: $($active -join ',')" }
}

function Assert-R13GpuComputeIdle([string]$Boundary) {
    $output = @(& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "set -o pipefail; nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d'")
    $exitCode = [int]$LASTEXITCODE
    Assert-R13GpuComputeProbeResult $exitCode $output $Boundary
}

function Assert-R13BoundDispatchRecord(
    [string]$DispatchMarkerPath,
    [string]$DispatchLifecyclePath,
    [string]$RunIdPrefix,
    [string]$TaskName,
    [string]$CanonicalGateSha256,
    [string]$UserConfirmationSha256
) {
    if (-not (Test-Path -LiteralPath $DispatchMarkerPath -PathType Leaf)) { throw 'r13 dispatch marker is absent before attempt-marker creation' }
    if ((Get-Item -LiteralPath $DispatchMarkerPath).Length -ne 0) { throw 'r13 dispatch marker content changed' }
    if (-not (Test-Path -LiteralPath $DispatchLifecyclePath -PathType Leaf)) { throw 'r13 dispatch lifecycle is absent before attempt-marker creation' }

    $probe = $null
    $exclusivelyHeld = $false
    try { $probe = [IO.File]::Open([IO.Path]::GetFullPath($DispatchMarkerPath), [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite) }
    catch [IO.IOException] { $exclusivelyHeld = $true }
    finally { if ($null -ne $probe) { $probe.Dispose() } }
    if (-not $exclusivelyHeld) { throw 'r13 dispatch marker is not exclusively held by the live dispatcher' }

    $matches = @()
    foreach ($line in @(Get-Content -LiteralPath $DispatchLifecyclePath -ErrorAction Stop)) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $event = $line | ConvertFrom-Json -ErrorAction Stop }
        catch { throw 'r13 dispatch lifecycle contains malformed JSON' }
        if ($event.event -eq 'dispatch_created' -and $event.run_id_prefix -eq $RunIdPrefix -and $event.task_name -eq $TaskName -and $event.canonical_gate_sha256 -eq $CanonicalGateSha256 -and $event.user_confirmation_sha256 -eq $UserConfirmationSha256) { $matches += @($event) }
    }
    if ($matches.Count -ne 1) { throw "r13 requires exactly one bound dispatch_created event; found $($matches.Count)" }
    $matches[0]
}
