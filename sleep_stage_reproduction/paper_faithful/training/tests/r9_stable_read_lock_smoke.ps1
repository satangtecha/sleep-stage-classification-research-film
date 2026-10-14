param([string]$LauncherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r9.ps1'),[string]$Distro='Ubuntu')
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath),[ref]$tokens,[ref]$errors);if($errors.Count){throw 'r9 launcher does not parse'}
foreach($name in @('Open-StableReadLock','Open-StableJsonLock')){$functionAst=$ast.Find({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true);if(!$functionAst){throw "r9 launcher has no $name"};Invoke-Expression $functionAst.Extent.Text}
$launcherText=Get-Content -LiteralPath $LauncherPath -Raw
foreach($token in @('r9-launch-gate-test-evidence-20260828-v2.json','$PSCommandPath','$runner','$contract','$cacheManifest','$validatorLog','$sourceManifest','$environmentManifest','$r8Evidence','$multiSeedEvidence','$repositoryPythonSourcePaths.Values','$multiSeedTest','$powerGateTest','$confirmationGateTest','$reviewGateTest','$livePowerProbe','$lifecycleFailureTest','$probeProgressTest','$launchEvidenceTest','$stableReadRaceTest','$importClosureTest','$progressProbe','$processProbe','$launchTestEvidence')){if($launcherText.IndexOf($token) -lt 0){throw "protected launch input missing from stable-lock design: $token"}}
if($launcherText.IndexOf('$gate.cache_gate.validator_v2_log_sha256 -ne $validatorHash') -lt 0 -or $launcherText.LastIndexOf('$heldReadLocks[$index].Dispose()') -lt $launcherText.IndexOf("event='terminal_validated'")){throw 'stable locks are not hash-bound and retained through terminal validation'}

function New-ContainedFixture([string]$Base,[string]$Drive) {
 $driveRoot="${Drive}:\"
 if(!(Test-Path -LiteralPath $driveRoot -PathType Container)){throw "required race drive is absent: $Drive"}
 if(!(Test-Path -LiteralPath $Base -PathType Container)){throw "required race fixture root is absent: $Base"}
 $fullBase=[IO.Path]::GetFullPath($Base).TrimEnd('\')
 if([IO.Path]::GetPathRoot($fullBase) -ne $driveRoot){throw "race fixture root is not on $Drive drive"}
 $directory=[IO.Path]::GetFullPath((Join-Path $fullBase ('r9-stable-read-'+[Guid]::NewGuid().ToString('N'))))
 $containedPrefix=$fullBase+'\'
 if(!$directory.StartsWith($containedPrefix,[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetPathRoot($directory) -ne $driveRoot){throw "race fixture escaped the validated $Drive root"}
 [pscustomobject]@{drive=$Drive;base=$fullBase;directory=$directory}
}
function Convert-ToWslPath([string]$Path) {
 $full=[IO.Path]::GetFullPath($Path);$drive=[IO.Path]::GetPathRoot($full).Substring(0,1).ToLowerInvariant()
 '/mnt/'+$drive+'/'+$full.Substring(3).Replace('\','/')
}
function Test-DriveStableRead($Fixture) {
 $locked=$null
 try {
  New-Item -ItemType Directory -Path $Fixture.directory|Out-Null
  if((Split-Path -Parent ([IO.Path]::GetFullPath($Fixture.directory))) -ne $Fixture.base){throw "created race fixture is not directly contained on $($Fixture.drive)"}
  $target=Join-Path $Fixture.directory 'authorization.json';$windowsReplacement=Join-Path $Fixture.directory 'replacement-windows.json';$wslReplacement=Join-Path $Fixture.directory 'replacement-wsl.json';$backup=Join-Path $Fixture.directory 'backup.json'
  [IO.File]::WriteAllText($target,'{"sentinel":"original"}',[Text.UTF8Encoding]::new($false));[IO.File]::WriteAllText($windowsReplacement,'{"sentinel":"windows-replacement"}',[Text.UTF8Encoding]::new($false));[IO.File]::WriteAllText($wslReplacement,'{"sentinel":"wsl-replacement"}',[Text.UTF8Encoding]::new($false))
  $originalBytes=[IO.File]::ReadAllBytes($target);$sha=[Security.Cryptography.SHA256]::Create();try{$expectedSha=-join($sha.ComputeHash($originalBytes)|%{$_.ToString('x2')})}finally{$sha.Dispose()}
  $locked=Open-StableJsonLock $target $expectedSha "$($Fixture.drive) race fixture";$sameBytesHashedAndParsed=$locked.sha256 -eq $expectedSha -and $locked.data.sentinel -eq 'original'
  $windowsReadSucceeded=[IO.File]::ReadAllText($target) -match 'original'
  $windowsWriteRefused=$false;try{$writer=[IO.File]::Open($target,[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::ReadWrite);$writer.Dispose()}catch [IO.IOException]{$windowsWriteRefused=$true}catch [UnauthorizedAccessException]{$windowsWriteRefused=$true}
  $windowsReplaceRefused=$false;try{[IO.File]::Replace($windowsReplacement,$target,$backup)}catch [IO.IOException]{$windowsReplaceRefused=$true}catch [UnauthorizedAccessException]{$windowsReplaceRefused=$true}
  $wslTarget=Convert-ToWslPath $target;$wslReplacementPath=Convert-ToWslPath $wslReplacement
  & wsl.exe -d $Distro -e sh -c "cat -- '$wslTarget' >/dev/null";$wslReadSucceeded=$LASTEXITCODE -eq 0
  $savedErrorPreference=$ErrorActionPreference;$ErrorActionPreference='SilentlyContinue';try{& wsl.exe -d $Distro -e sh -c "printf '%s' replacement > '$wslTarget'" 2>$null;$wslWriteRefused=$LASTEXITCODE -ne 0;& wsl.exe -d $Distro -e sh -c "mv -f -- '$wslReplacementPath' '$wslTarget'" 2>$null;$wslReplaceRefused=$LASTEXITCODE -ne 0}finally{$ErrorActionPreference=$savedErrorPreference}
  $result=[pscustomobject]@{drive=$Fixture.drive;same_bytes_hashed_and_parsed=$sameBytesHashedAndParsed;windows_read_succeeded=$windowsReadSucceeded;windows_write_refused=$windowsWriteRefused;windows_replace_refused=$windowsReplaceRefused;wsl_read_succeeded=$wslReadSucceeded;wsl_write_refused=$wslWriteRefused;wsl_replace_refused=$wslReplaceRefused}
  foreach($property in @('same_bytes_hashed_and_parsed','windows_read_succeeded','windows_write_refused','windows_replace_refused','wsl_read_succeeded','wsl_write_refused','wsl_replace_refused')){if($result.$property -isnot [bool] -or $result.$property -ne $true){throw "$($Fixture.drive) stable-read result failed: $property"}}
  return $result
 } finally {
  if($null -ne $locked){$locked.stream.Dispose()}
  if((Test-Path -LiteralPath $Fixture.directory) -and [IO.Path]::GetFullPath($Fixture.directory).StartsWith(($Fixture.base+'\'),[StringComparison]::OrdinalIgnoreCase)){Remove-Item -LiteralPath $Fixture.directory -Recurse -Force}
  if(Test-Path -LiteralPath $Fixture.directory){throw "race fixture cleanup failed: $($Fixture.directory)"}
 }
}

if([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)){throw 'LOCALAPPDATA is unavailable for the explicit C-drive fixture'}
$cFixture=New-ContainedFixture (Join-Path $env:LOCALAPPDATA 'Temp') 'C'
$eFixture=New-ContainedFixture 'E:\blp\sleep_stage_reproduction\runtime' 'E'
$cResult=Test-DriveStableRead $cFixture
$eResult=Test-DriveStableRead $eFixture
[pscustomobject]@{status='pass';c_drive=$cResult;e_drive=$eResult;pilot_launched=$false}|ConvertTo-Json -Compress -Depth 5
