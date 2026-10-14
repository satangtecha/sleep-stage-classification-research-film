param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedCanonicalGateSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{64}$')][string]$ExpectedUserConfirmationSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^SleepStagePaper-r14-Canary-[0-9a-f]{32}$')][string]$TaskName
)

$ErrorActionPreference = 'Stop'
$root = Join-Path 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-production-action-canaries' $TaskName
$handshake = Join-Path $root 'handshake.json'

New-Item -ItemType Directory -Path $root -Force | Out-Null
if (Test-Path -LiteralPath $handshake) { throw 'r14 canary handshake already exists' }

$self = Get-WmiObject -Class Win32_Process -Filter "ProcessId=$PID" -ErrorAction Stop
$parent = Get-Process -Id ([int]$self.ParentProcessId) -ErrorAction Stop
if (($parent.ProcessName + '.exe') -ne 'svchost.exe') { throw 'r14 canary is not Task Scheduler-owned' }

$record = [ordered]@{
    schema_version = 1
    status = 'bound_handshake'
    pilot_launched = $false
    task_name = $TaskName
    canonical_gate_sha256 = $ExpectedCanonicalGateSha256.ToLowerInvariant()
    user_confirmation_sha256 = $ExpectedUserConfirmationSha256.ToLowerInvariant()
    canary_pid = $PID
    parent_process = 'svchost.exe'
    timestamp = (Get-Date).ToString('o')
}
$bytes = [Text.UTF8Encoding]::new($false).GetBytes(($record | ConvertTo-Json -Compress))
$stream = [IO.File]::Open($handshake, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
}
finally {
    $stream.Dispose()
}
