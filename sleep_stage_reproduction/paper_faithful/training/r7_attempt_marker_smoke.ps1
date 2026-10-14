param(
    [Parameter(Mandatory = $true)]
    [string]$MarkerPath
)

$ErrorActionPreference = 'Stop'

if (Test-Path -LiteralPath $MarkerPath) {
    throw 'Refusing to overwrite attempt-marker smoke evidence'
}

$first = [System.IO.File]::Open($MarkerPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
try {
    $concurrentRefused = $false
    try {
        $second = [System.IO.File]::Open($MarkerPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $second.Dispose()
    } catch [System.IO.IOException] {
        $concurrentRefused = $true
    }
} finally {
    $first.Dispose()
}

$laterRefused = $false
try {
    $later = [System.IO.File]::Open($MarkerPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    $later.Dispose()
} catch [System.IO.IOException] {
    $laterRefused = $true
}

if (-not $concurrentRefused -or -not $laterRefused) {
    throw 'CreateNew attempt marker did not refuse both concurrent and later invocations'
}

[pscustomobject]@{
    status = 'pass'
    implementation = 'FileMode.CreateNew + FileShare.None'
    marker_path = $MarkerPath
    concurrent_invocation_refused = $concurrentRefused
    later_invocation_refused_after_first_handle_closed = $laterRefused
    marker_remains = Test-Path -LiteralPath $MarkerPath
} | ConvertTo-Json -Compress
