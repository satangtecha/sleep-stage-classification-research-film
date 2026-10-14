param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F]{64}$')]
    [string]$ExpectedSha256
)

$ErrorActionPreference = 'Stop'

function Get-Sha256([string]$Path) {
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $digest = $sha.ComputeHash($stream)
        } finally {
            $sha.Dispose()
        }
    } finally {
        $stream.Dispose()
    }
    return -join ($digest | ForEach-Object { $_.ToString('x2') })
}

$actual = Get-Sha256 $InputPath
if ($actual -ne $ExpectedSha256.ToLowerInvariant()) {
    throw 'Module-independent SHA-256 did not match the operator-supplied digest'
}

[pscustomobject]@{
    status = 'pass'
    powershell_version = $PSVersionTable.PSVersion.ToString()
    hidden_host = $true
    implementation = 'System.Security.Cryptography.SHA256'
    input_path = $InputPath
    sha256 = $actual
} | ConvertTo-Json -Compress
