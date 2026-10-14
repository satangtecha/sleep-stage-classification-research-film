param(
    [string]$WrapperPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r18_wrapper.sh'),
    [int]$TimeoutSeconds=120
)
$ErrorActionPreference='Stop'
$prefix='paper-text-v1-multiseed-cap128-r18-20260902'
$production=@(
    "E:\blp\sleep_stage_reproduction\runtime\training-logs\$prefix.dispatch.lock",
    "E:\blp\sleep_stage_reproduction\runtime\training-logs\$prefix.launch.lock"
)
if(@($production|Where-Object {Test-Path -LiteralPath $_}).Count){throw 'r18 production marker exists before failure-stage smoke'}

$id=[Guid]::NewGuid().ToString('N')
$root="E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r18-wrapper-failure-smokes\$id"
[IO.Directory]::CreateDirectory($root)|Out-Null
$runner=Join-Path $root 'runner.sh'
$stderr=Join-Path $root 'workload.stderr.log'
$hostStdout=Join-Path $root 'host.stdout.log'
$hostStderr=Join-Path $root 'host.stderr.log'
$exitFile=Join-Path $root 'exit.json'
$badStdout=Join-Path (Join-Path $root 'missing-parent') 'workload.stdout.log'
[IO.File]::WriteAllText($runner,"#!/usr/bin/env bash`nexit 0`n",[Text.UTF8Encoding]::new($false))

function Convert-ToWsl([string]$Path){
    $full=[IO.Path]::GetFullPath($Path)
    if($full-notmatch'^([A-Za-z]):\\(.*)$'){throw 'unsupported path'}
    '/mnt/'+$Matches[1].ToLowerInvariant()+'/'+$Matches[2].Replace('\','/')
}

$args=@(
    '-d','Ubuntu','-e','bash','--noprofile','--norc',
    (Convert-ToWsl (Resolve-Path -LiteralPath $WrapperPath).Path),
    (Convert-ToWsl $runner),
    (Convert-ToWsl $badStdout),
    (Convert-ToWsl $stderr),
    (Convert-ToWsl $exitFile)
)
foreach($arg in $args){if($arg-match'[\s"'']'){throw "unsafe smoke arg: $arg"}}
$psi=New-Object Diagnostics.ProcessStartInfo
$psi.FileName="$env:SystemRoot\System32\wsl.exe";$psi.Arguments=$args-join' ';$psi.WorkingDirectory="$env:SystemRoot\System32";$psi.UseShellExecute=$false;$psi.CreateNoWindow=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
$process=New-Object Diagnostics.Process;$process.StartInfo=$psi;if(!$process.Start()){throw 'r18 failure-stage smoke could not start WSL'};$hostOutTask=$process.StandardOutput.ReadToEndAsync();$hostErrTask=$process.StandardError.ReadToEndAsync()
$deadline=(Get-Date).AddSeconds($TimeoutSeconds)
while(!$process.HasExited-and(Get-Date)-lt$deadline){Start-Sleep -Milliseconds 250;$process.Refresh()}
if(!$process.HasExited){try{$process.Kill()}catch{};throw 'r18 wrapper failure-stage smoke timed out'}
$process.WaitForExit();[IO.File]::WriteAllText($hostStdout,[string]$hostOutTask.GetAwaiter().GetResult(),[Text.UTF8Encoding]::new($false));[IO.File]::WriteAllText($hostStderr,[string]$hostErrTask.GetAwaiter().GetResult(),[Text.UTF8Encoding]::new($false));$process.Refresh()
if(!(Test-Path -LiteralPath $exitFile)){throw 'r18 wrapper failure did not publish an atomic sidecar'}
$atomic=Get-Content -LiteralPath $exitFile -Raw|ConvertFrom-Json
if([int]$process.ExitCode-ne76-or[int]$atomic.schema_version-ne1-or[int]$atomic.exit_code-ne76-or[string]$atomic.stage-ne'stdout_open'){throw "r18 failure-stage mismatch host=$($process.ExitCode) atomic=$($atomic.exit_code) stage=$($atomic.stage)"}
if(Test-Path -LiteralPath $badStdout){throw 'r18 invalid stdout path unexpectedly exists'}
if(@($production|Where-Object {Test-Path -LiteralPath $_}).Count){throw 'r18 production marker appeared during failure-stage smoke'}

$result=[ordered]@{
    schema_version=1
    status='pass'
    pilot_launched=$false
    case_id=$id
    root=$root
    windows_host_exit_code=76
    atomic_exit_code=76
    atomic_stage='stdout_open'
    pre_runner_failure_captured=$true
    host_diagnostics_captured=$true
    neutral_windows_working_directory=$true
    production_markers_created=$false
    timestamp=(Get-Date).ToString('o')
}
$resultPath=Join-Path $root 'result.json'
$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($result|ConvertTo-Json -Compress))
$stream=[IO.File]::Open($resultPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
$result|Add-Member result_path $resultPath -PassThru|ConvertTo-Json -Compress
