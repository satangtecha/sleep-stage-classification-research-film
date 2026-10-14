param([string]$HelperPath=(Join-Path $PSScriptRoot '..\r15_exactly_once_helpers.ps1'))
$ErrorActionPreference='Stop'
. (Resolve-Path -LiteralPath $HelperPath).Path
$root=Join-Path ([IO.Path]::GetTempPath()) ('r15-exactly-once-'+[Guid]::NewGuid().ToString('N'))
$marker=Join-Path $root 'dispatch.lock';$lifecycle=Join-Path $root 'dispatch.lifecycle.jsonl';$orphanMarker=Join-Path $root 'orphan.lock';$orphanLifecycle=Join-Path $root 'orphan.lifecycle.jsonl';$stream=$null
$prefix='paper-text-v1-multiseed-cap128-r15-20260831';$task='SleepStagePaper-r15-COM-'+('0'*32);$gate='a'*64;$confirmation='b'*64
try{
 [IO.Directory]::CreateDirectory($root)|Out-Null;$stream=Open-R15PermanentMarker $marker 'dispatch'
 $second=$null;try{$s=Open-R15PermanentMarker $marker 'dispatch';$s.Dispose()}catch{$second=Get-R15FailureExitCode $_.Exception};if($second-ne91){throw 'second marker did not map to 91'}
 $bad=[ordered]@{event='dispatch_created';run_id_prefix=$prefix;task_name=$task;canonical_gate_sha256=('c'*64);user_confirmation_sha256=$confirmation;timestamp=(Get-Date).ToString('o')}|ConvertTo-Json -Compress
 [IO.File]::WriteAllText($lifecycle,$bad+[Environment]::NewLine,[Text.UTF8Encoding]::new($false));$refused=$false;try{Assert-R15BoundDispatchRecord $marker $lifecycle $prefix $task $gate $confirmation|Out-Null}catch{$refused=$true};if(!$refused){throw 'mismatch accepted'}
 $exact=[ordered]@{event='dispatch_created';run_id_prefix=$prefix;task_name=$task;canonical_gate_sha256=$gate;user_confirmation_sha256=$confirmation;timestamp=(Get-Date).ToString('o')}|ConvertTo-Json -Compress
 [IO.File]::WriteAllText($lifecycle,$exact+[Environment]::NewLine,[Text.UTF8Encoding]::new($false));Assert-R15BoundDispatchRecord $marker $lifecycle $prefix $task $gate $confirmation|Out-Null
 $race=$null;try{Assert-R15OwnedLifecycleAvailable $lifecycle $marker 'dispatch'}catch{$race=Get-R15FailureExitCode $_.Exception};if($race-ne91){throw 'marker+lifecycle did not map to 91'}
 [IO.File]::WriteAllText($orphanLifecycle,$exact+[Environment]::NewLine,[Text.UTF8Encoding]::new($false));$orphan=$null;try{Assert-R15OwnedLifecycleAvailable $orphanLifecycle $orphanMarker 'dispatch'}catch{$orphan=Get-R15FailureExitCode $_.Exception};if($orphan-ne92){throw 'orphan lifecycle did not map to 92'}
 [IO.File]::AppendAllText($lifecycle,$exact+[Environment]::NewLine,[Text.UTF8Encoding]::new($false));$duplicate=$false;try{Assert-R15BoundDispatchRecord $marker $lifecycle $prefix $task $gate $confirmation|Out-Null}catch{$duplicate=$true};if(!$duplicate){throw 'duplicate accepted'}
 [IO.File]::WriteAllText($lifecycle,$exact+[Environment]::NewLine,[Text.UTF8Encoding]::new($false));$stream.Dispose();$stream=$null;$unheld=$false;try{Assert-R15BoundDispatchRecord $marker $lifecycle $prefix $task $gate $confirmation|Out-Null}catch{$unheld=$true};if(!$unheld){throw 'unheld marker accepted'}
 [ordered]@{status='pass';pilot_launched=$false;second_marker_exit_code=91;marker_lifecycle_exit_code=91;orphan_lifecycle_exit_code=92;mismatch_refused=$true;duplicate_refused=$true;unheld_refused=$true}|ConvertTo-Json -Compress
}finally{if($stream){$stream.Dispose()};if(Test-Path -LiteralPath $root){$full=[IO.Path]::GetFullPath($root);$temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath());if(!$full.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase)-or(Split-Path -Leaf $full)-notmatch'^r15-exactly-once-[0-9a-f]{32}$'){throw 'unsafe cleanup refused'};Remove-Item -LiteralPath $full -Recurse -Force}}
