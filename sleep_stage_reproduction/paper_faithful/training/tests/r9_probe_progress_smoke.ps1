param([string]$ProbePath=(Join-Path $PSScriptRoot '..\probe_pilot_progress.ps1'))
$ErrorActionPreference='Stop'
function wsl.exe { 'PID=123'; 'CPU_TICKS=10' }
function nvidia-smi { @() }
function Test-Path {param([string]$LiteralPath) if($LiteralPath -eq 'C:\mock-bulk\runs\paper-text-v1-multiseed-cap128-r9-20260828-split42-model42'){return $true};if($LiteralPath -eq 'C:\mock-bulk\runs\paper-text-v1-multiseed-cap128-r9-20260828-split42-model42\execution.json'){return $true};return $false}
function Get-Content {param([string]$LiteralPath,[switch]$Raw,[int]$Tail,[string]$ErrorAction) if($LiteralPath -eq 'C:\mock\cache.json'){return '{"chunks":[]}'};if($LiteralPath -like '*split42-model42\execution.json'){return '{"status":"running","config":{"seed":42}}'};return @()}
$prefix='paper-text-v1-multiseed-cap128-r9-20260828'
$multi=& $ProbePath -RunId $prefix -Distro 'mock' -ProjectRoot 'C:\mock-project' -CacheManifest 'C:\mock\cache.json' -RuntimeRoot 'C:\mock-bulk'|ConvertFrom-Json
if($multi.phase -ne 'training_or_evaluation' -or $multi.execution.mode -ne 'multi-seed-pilot' -or $multi.execution.status -ne 'running' -or @($multi.execution.children).Count -ne 2 -or $multi.execution.children[0].execution.config.seed -ne 42){throw 'multi-seed child execution did not drive phase and aggregate execution'}
$single=& $ProbePath -RunId 'paper-text-v1-pilot-cap128-seed42-r8-20260827' -Distro 'mock' -ProjectRoot 'C:\mock-project' -CacheManifest 'C:\mock\cache.json' -RuntimeRoot 'C:\mock-bulk'|ConvertFrom-Json
if($single.phase -ne 'strict_cache_scan' -or $null -ne $single.execution -or @($single.child_runs).Count -ne 0){throw 'existing single-pilot probe behavior regressed'}
[pscustomobject]@{status='pass';multiseed_phase=$multi.phase;multiseed_execution_status=$multi.execution.status;single_pilot_phase=$single.phase;pilot_launched=$false}|ConvertTo-Json -Compress
