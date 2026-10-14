param(
 [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r14.ps1'),
 [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r14.ps1'),
 [string]$RunnerPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r14.sh'),
 [string]$HelperPath=(Join-Path $PSScriptRoot '..\r14_exactly_once_helpers.ps1')
)
$ErrorActionPreference='Stop'
$dispatcher=(Resolve-Path -LiteralPath $DispatcherPath).Path;$supervisor=(Resolve-Path -LiteralPath $SupervisorPath).Path;$runner=(Resolve-Path -LiteralPath $RunnerPath).Path;$helper=(Resolve-Path -LiteralPath $HelperPath).Path
$prefix='paper-text-v1-multiseed-cap128-r14-20260831';$bulkRoot='E:\blp\sleep_stage_reproduction';$logs=Join-Path $bulkRoot 'runtime\training-logs'
$productionSupervisor='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-production-supervisor-v3.ps1';$gateSha='a'*64;$confirmationSha='b'*64;$taskName='SleepStagePaper-r14-COM-00000000000000000000000000000000'
function Assert-Ordered([string]$Text,[string[]]$Needles,[string]$Label){$at=-1;foreach($needle in $Needles){$next=$Text.IndexOf($needle,$at+1,[StringComparison]::Ordinal);if($next-lt0){throw "${Label} is missing ordered token: $needle"};$at=$next}}
function Assert-NoParseErrors([string]$Path){$tokens=$null;$errors=$null;[void][Management.Automation.Language.Parser]::ParseFile($Path,[ref]$tokens,[ref]$errors);if($errors.Count){throw "Windows PowerShell parser rejected ${Path}: $($errors[0].Message)"}}
Assert-NoParseErrors $dispatcher;Assert-NoParseErrors $supervisor
. $helper
$text=Get-Content -LiteralPath $dispatcher -Raw
if($text-match'AllowStartOnDemand'){throw 'r14 dispatcher still references unsupported AllowStartOnDemand'}
Assert-Ordered $text @('$args=New-R14SupervisorActionArguments','$def=$svc.NewTask(0)','$def.Settings.AllowDemandStart=$true','Assert-R14SupervisorActionArguments $args','Assert-TaskDefinition $def $args $actionWorkingDirectory','Assert-R14GpuComputeIdle ''dispatcher-pre-dispatch''','$marker=Open-R14PermanentMarker $dispatch ''dispatch''','$task=$folder.RegisterTaskDefinition','$running=$task.RunEx') 'r14 COM pre-dispatch ordering'
$service=New-Object -ComObject 'Schedule.Service';$service.Connect();$definition=$service.NewTask(0)
$definition.RegistrationInfo.Description='r14 COM preflight only';$definition.Principal.UserId=[Security.Principal.WindowsIdentity]::GetCurrent().Name;$definition.Principal.LogonType=3;$definition.Settings.MultipleInstances=2;$definition.Settings.RestartCount=0;$definition.Settings.ExecutionTimeLimit='PT0S';$definition.Settings.AllowDemandStart=$true
$productionArguments=New-R14SupervisorActionArguments $productionSupervisor $gateSha $confirmationSha $taskName;Assert-R14SupervisorActionArguments $productionArguments $productionSupervisor $gateSha $confirmationSha $taskName|Out-Null
$action=$definition.Actions.Create(0);$action.Path="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe";$action.Arguments=$productionArguments;$action.WorkingDirectory=(Split-Path -Parent $productionSupervisor)
$xml=[xml]$definition.XmlText
if($definition.Settings.AllowDemandStart-ne$true-or[int]$definition.Settings.MultipleInstances-ne2-or[int]$definition.Settings.RestartCount-ne0-or$definition.Settings.ExecutionTimeLimit-ne'PT0S'){throw 'COM TaskDefinition settings preflight failed'}
if($definition.Principal.LogonType-ne3-or[string]::IsNullOrWhiteSpace([string]$definition.Principal.UserId)-or$definition.Actions.Count-ne1){throw 'COM TaskDefinition principal/action preflight failed'}
if([string]$definition.Actions.Item(1).Arguments-cne$productionArguments-or[IO.Path]::GetFullPath([string]$definition.Actions.Item(1).WorkingDirectory)-cne[IO.Path]::GetFullPath((Split-Path -Parent $productionSupervisor))){throw 'COM TaskDefinition production action binding failed'}
if(@($xml.Task.Triggers.ChildNodes|?{$_.NodeType-eq[Xml.XmlNodeType]::Element}).Count-ne0-or($xml.Task.Settings.AllowDemandStart-and$xml.Task.Settings.AllowDemandStart-ne'true')-or($xml.Task.Settings.MultipleInstances-and$xml.Task.Settings.MultipleInstances-ne'IgnoreNew')-or($xml.Task.Settings.RestartCount-and$xml.Task.Settings.RestartCount-ne'0')-or$xml.Task.Settings.ExecutionTimeLimit-ne'PT0S'){throw 'COM TaskDefinition XML policy preflight failed'}
$paths=@((Join-Path $logs "$prefix.dispatch.lock"),(Join-Path $logs "$prefix.launch.lock"),(Join-Path $logs "$prefix.dispatch.lifecycle.jsonl"),(Join-Path $logs "$prefix.dispatch.json"),(Join-Path $logs "$prefix.lifecycle.jsonl"),(Join-Path $logs "$prefix.stdout.log"),(Join-Path $logs "$prefix.stderr.log"),(Join-Path $logs "$prefix.workload-exit-code.txt"))+@("$bulkRoot\runs\$prefix-split42-model42","$bulkRoot\runs\$prefix-split43-model43")
$present=@($paths|?{Test-Path -LiteralPath $_});if($present.Count){throw ('Production r14 artifacts appeared: ' + ($present -join ', '))}
$tasks=@($service.GetFolder('\').GetTasks(1)|?{$_.Name-match'^SleepStagePaper-r14-COM-'});if($tasks.Count){throw ('Production r14 Scheduler task namespace is not empty: ' + ($tasks.Name -join ', '))}
[ordered]@{status='pass';pilot_launched=$false;task_registered=$false;task_runex_requested=$false;allow_demand_start=$true;multiple_instances='IgnoreNew';restart_count=0;execution_time_limit='PT0S';trigger_count=0;production_action_shape_validated=$true;production_action_arguments_length=$productionArguments.Length;production_artifacts_present=0}|ConvertTo-Json -Compress
