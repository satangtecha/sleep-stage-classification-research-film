param([string]$WrapperPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r16_wrapper.sh'),[int]$TimeoutSeconds=120)
$ErrorActionPreference='Stop'
$prefix='paper-text-v1-multiseed-cap128-r16-20260901';$production=@("E:\blp\sleep_stage_reproduction\runtime\training-logs\$prefix.dispatch.lock","E:\blp\sleep_stage_reproduction\runtime\training-logs\$prefix.launch.lock")
if(@($production|?{Test-Path -LiteralPath $_}).Count){throw 'r16 production marker exists before wrapper smoke'}
$id=[Guid]::NewGuid().ToString('N');$root="E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r16-wrapper-smokes\$id";[IO.Directory]::CreateDirectory($root)|Out-Null
$runner=Join-Path $root 'runner.sh';$stdout=Join-Path $root 'stdout.log';$stderr=Join-Path $root 'stderr.log';$exitFile=Join-Path $root 'exit.txt'
$runnerText=@'
#!/usr/bin/env bash
printf '{"status":"canary"}\n'
printf 'canary-stderr\n' >&2
exit 17
'@
[IO.File]::WriteAllText($runner,$runnerText,[Text.UTF8Encoding]::new($false))
function Wsl([string]$p){$f=[IO.Path]::GetFullPath($p);if($f-notmatch'^([A-Za-z]):\\(.*)$'){throw 'unsupported path'};'/mnt/'+$Matches[1].ToLowerInvariant()+'/'+$Matches[2].Replace('\','/')}
$args=@('-d','Ubuntu','-e','bash','--noprofile','--norc',(Wsl (Resolve-Path -LiteralPath $WrapperPath).Path),(Wsl $runner),(Wsl $stdout),(Wsl $stderr),(Wsl $exitFile));foreach($arg in $args){if($arg-match'[\s"'']'){throw "unsafe smoke arg: $arg"}}
$p=Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe" -ArgumentList $args -WindowStyle Hidden -PassThru;$deadline=(Get-Date).AddSeconds($TimeoutSeconds);while(!$p.HasExited-and(Get-Date)-lt$deadline){Start-Sleep -Milliseconds 250;$p.Refresh()};if(!$p.HasExited){try{$p.Kill()}catch{};throw 'wrapper smoke timed out'}
if($p.ExitCode-ne17-or!(Test-Path -LiteralPath $exitFile)-or(Get-Content -LiteralPath $exitFile -Raw).Trim()-ne'17'){throw "wrapper exit mismatch host=$($p.ExitCode)"}
if((Get-Content -LiteralPath $stdout -Raw).Trim()-ne'{"status":"canary"}'-or(Get-Content -LiteralPath $stderr -Raw).Trim()-ne'canary-stderr'){throw 'wrapper redirection failed'}
if(@($production|?{Test-Path -LiteralPath $_}).Count){throw 'r16 production marker appeared during wrapper smoke'}
$result=[ordered]@{schema_version=1;status='pass';pilot_launched=$false;case_id=$id;wrapper_path=(Resolve-Path -LiteralPath $WrapperPath).Path;wrapper_sha256=(Get-FileHash -LiteralPath $WrapperPath -Algorithm SHA256).Hash.ToLowerInvariant();root=$root;windows_host_exit_code=17;atomic_exit_code=17;stdout_exact=$true;stderr_exact=$true;production_markers_created=$false;timestamp=(Get-Date).ToString('o')}
$resultPath=Join-Path $root 'result.json';$bytes=[Text.UTF8Encoding]::new($false).GetBytes(($result|ConvertTo-Json -Compress));$s=[IO.File]::Open($resultPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$s.Write($bytes,0,$bytes.Length);$s.Flush($true)}finally{$s.Dispose()};$result|Add-Member result_path $resultPath -PassThru|ConvertTo-Json -Compress
