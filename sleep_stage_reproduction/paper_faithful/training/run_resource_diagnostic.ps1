param(
    [Parameter(Mandatory=$true)][ValidateSet('stage1','stage2','stage3')][string]$Mode,
    [ValidateRange(1,3)][int]$Steps = 2
)
# Short diagnostics only. Kernel memory limits apply to this scope, not other apps.
$ErrorActionPreference = 'Stop'
$bulk = 'E:\blp\sleep_stage_reproduction\runtime\resource-profile-20260909'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$repoWsl = '/mnt/' + $repo.Substring(0,1).ToLowerInvariant() + $repo.Substring(2).Replace('\','/')
$name = 'gpu-' + $Mode + '-compact-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$unit = 'sleep-resource-' + $name
$output = Join-Path $bulk $name
$outputWsl = '/mnt/e/blp/sleep_stage_reproduction/runtime/resource-profile-20260909/' + $name
$python = '/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
if (-not (Test-Path -LiteralPath $bulk -PathType Container)) { throw 'Diagnostic runtime folder is unavailable' }
if (Test-Path -LiteralPath $output) { throw 'Diagnostic output already exists' }

function Write-OnceJson([string]$Path, $Value) {
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($Value | ConvertTo-Json -Depth 10))
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
}

$argsWsl = @('-d','Ubuntu','-u','root','--cd',$repoWsl,'-e','systemd-run','--scope',('--unit='+$unit),'--quiet',
    '-p','MemoryMax=2G','-p','MemoryHigh=2G','-p','MemorySwapMax=2G',
    '/usr/bin/timeout','--signal=TERM','--kill-after=15s','600s',
    '/usr/sbin/runuser','-u','techatat','--','/usr/bin/env','-u','TF_FORCE_GPU_ALLOW_GROWTH','-u','CUDA_VISIBLE_DEVICES',
    'LD_LIBRARY_PATH=/home/techatat/.local/share/sleep-stage-paper/envs/tf24/lib:/usr/lib/wsl/lib',
    'TF_CPP_MIN_LOG_LEVEL=1','OMP_NUM_THREADS=2','OPENBLAS_NUM_THREADS=2','PYTHONDONTWRITEBYTECODE=1',
    'TF_CUDNN_USE_AUTOTUNE=0','TF_CUDNN_RNN_USE_AUTOTUNE=0','TF_CUDNN_WORKSPACE_LIMIT_IN_MB=256',
    $python,'-u','-m','paper_faithful.training.resource_diagnostic','--mode',$Mode,'--steps',[string]$Steps,
    '--compact','--output-dir',$outputWsl)
# Bring up WSL first; after a completed GPU process, host page reporting may lag.
# This waits for resources before dispatch. It never retries the workload.
& wsl.exe -d Ubuntu -e /usr/bin/true
if ($LASTEXITCODE -ne 0) { throw 'WSL startup failed before diagnostic dispatch' }
$prepareClock = [System.Diagnostics.Stopwatch]::StartNew()
do {
    $hostFreeMiB = [double](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024
    if ($hostFreeMiB -ge 3072) { break }
    if ($prepareClock.Elapsed.TotalSeconds -ge 60) {
        throw ('Host memory did not settle within 60 seconds; available MiB=' + $hostFreeMiB + '. No diagnostic was dispatched.')
    }
    Start-Sleep -Seconds 1
} while ($true)
Write-OnceJson ($output + '.launch.json') ([ordered]@{time=(Get-Date -Format o);mode=$Mode;steps=$Steps;unit=$unit;output=$output;arguments=$argsWsl;research_run=$false})
$nativeExit = $null
$launchError = $null
try {
    & wsl.exe @argsWsl
    $nativeExit = $LASTEXITCODE
} catch { $launchError = $_.Exception.Message }
$resultPath = Join-Path $output 'result.json'
$resultStatus = $null
if (Test-Path -LiteralPath $resultPath) {
    try { $resultStatus = (Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json).status }
    catch { $launchError = 'Unreadable diagnostic result: ' + $_.Exception.Message }
}
$success = ($null -eq $launchError -and $nativeExit -eq 0 -and $resultStatus -eq 'pass')
Write-OnceJson ($output + '.exit.json') ([ordered]@{time=(Get-Date -Format o);native_exit=$nativeExit;error=$launchError;result_status=$resultStatus;success=$success;unit=$unit;output=$output;research_run=$false})
Write-Output ('Diagnostic evidence: ' + $output)
if (-not $success) { throw 'Diagnostic did not pass; inspect the fresh result and exit receipt. No retry was performed.' }
