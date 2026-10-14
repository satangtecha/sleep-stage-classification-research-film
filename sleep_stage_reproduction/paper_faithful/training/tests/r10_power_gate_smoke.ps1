param([string]$LauncherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r10.ps1'))
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'r10 launcher does not parse'}
$powerFunction=$ast.Find({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-StableAcPowerFacts'},$true)
if(!$powerFunction){throw 'r10 stable power gate missing'}
function Get-CimInstance {
 param([string]$Namespace,[string]$ClassName)
 if($ClassName -eq 'BatteryStatus'){
  switch($script:Scenario){
   'missing' {return @()}; 'inactive' {return [pscustomobject]@{Active=$false;PowerOnline=$true;Critical=$false}}
   'offline' {return [pscustomobject]@{Active=$true;PowerOnline=$false;Critical=$false}}; 'critical' {return [pscustomobject]@{Active=$true;PowerOnline=$true;Critical=$true}}
   default {return [pscustomobject]@{Active=$true;PowerOnline=$true;Critical=$false}}
  }
 }
 if($ClassName -eq 'Win32_Battery'){
  switch($script:Scenario){
   'win32missing' {return @()}; 'win32discharging' {return [pscustomobject]@{BatteryStatus=1;EstimatedChargeRemaining=80}}
   'win32low' {return [pscustomobject]@{BatteryStatus=4;EstimatedChargeRemaining=10}}; 'win32critical' {return [pscustomobject]@{BatteryStatus=5;EstimatedChargeRemaining=80}}
   'win32chargingcritical' {return [pscustomobject]@{BatteryStatus=9;EstimatedChargeRemaining=1}}; 'win32undefined' {return [pscustomobject]@{BatteryStatus=10;EstimatedChargeRemaining=80}}
   'win32unexpected' {return [pscustomobject]@{BatteryStatus=99;EstimatedChargeRemaining=80}}; 'win32statusmissing' {return [pscustomobject]@{BatteryStatus=$null;EstimatedChargeRemaining=80}}
   'win32chargemissing' {return [pscustomobject]@{BatteryStatus=2;EstimatedChargeRemaining=$null}}; 'win32zerocharge' {return [pscustomobject]@{BatteryStatus=2;EstimatedChargeRemaining=0}}
   default {if($script:Scenario -match '^valid(?<Code>\d+)$'){return [pscustomobject]@{BatteryStatus=[int]$Matches.Code;EstimatedChargeRemaining=80}};return [pscustomobject]@{BatteryStatus=2;EstimatedChargeRemaining=80}}
  }
 }
 throw "unexpected CIM class $ClassName"
}
Invoke-Expression $powerFunction.Extent.Text
$refusalCases=@('missing','inactive','offline','critical','win32missing','win32discharging','win32low','win32critical','win32chargingcritical','win32undefined','win32unexpected','win32statusmissing','win32chargemissing','win32zerocharge')
foreach($case in $refusalCases){$script:Scenario=$case;$refused=$false;try{Get-StableAcPowerFacts|Out-Null}catch{$refused=$true};if(!$refused){throw "power failure class accepted: $case"}}
$acceptedStatuses=@(2,3,6,7,8,11)
foreach($status in $acceptedStatuses){$script:Scenario="valid$status";$facts=Get-StableAcPowerFacts;if(@($facts.battery_status).Count -ne 1 -or @($facts.win32_battery).Count -ne 1 -or [int]$facts.win32_battery[0].BatteryStatus -ne $status){throw "valid AC status refused: $status"}}
[pscustomobject]@{status='pass';refused_failure_classes=$refusalCases.Count;accepted_statuses=$acceptedStatuses;pilot_launched=$false}|ConvertTo-Json -Compress
