$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'

if (-not (Test-Path -LiteralPath $python)) {
    throw "ไม่พบ Python environment: $python"
}

& $python (Join-Path $PSScriptRoot 'execute_walkthrough.py')
if ($LASTEXITCODE -ne 0) {
    throw "Walkthrough execution failed with exit code $LASTEXITCODE"
}
