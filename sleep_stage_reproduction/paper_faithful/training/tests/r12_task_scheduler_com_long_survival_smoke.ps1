param(
    [switch]$DispatchChild,
    [string]$EvidenceRoot,
    [string]$TaskName,
    [string]$InvocationName,
    [ValidateSet('success','failure')][string]$Mode='success',
    [int]$SleepSeconds=210,
    [switch]$DebugShortSuccess
)

$ErrorActionPreference='Stop'
$worker=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'r12_task_scheduler_com_long_worker.ps1')).Path
$powershell51="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$testBase='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r12-task-scheduler-com-long-tests'
$expectedIdentity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$expectedSessionId=(Get-Process -Id $PID).SessionId
if($Mode -eq 'success' -and !$DebugShortSuccess -and ($SleepSeconds -lt 180 -or $SleepSeconds -gt 300)){throw 'Success duration must be in the accepted range 180..300 seconds'}
if($Mode -eq 'success' -and $DebugShortSuccess -and ($SleepSeconds -lt 2 -or $SleepSeconds -gt 30)){throw 'Debug success duration must be in the range 2..30 seconds'}
if($Mode -eq 'failure' -and ($SleepSeconds -lt 2 -or $SleepSeconds -gt 300)){throw 'Failure duration must be in the range 2..300 seconds'}

function Read-Events([string]$Root) {
    $path=Join-Path $Root 'lifecycle.jsonl'
    if(!(Test-Path -LiteralPath $path)){return @()}
    try { return @(Get-Content -LiteralPath $path -ErrorAction Stop|ForEach-Object{if(-not [string]::IsNullOrWhiteSpace($_)){$_|ConvertFrom-Json -ErrorAction Stop}}) } catch { return @() }
}
function Wait-Until([scriptblock]$Condition,[int]$TimeoutSeconds,[string]$Failure) {
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    do {if(& $Condition){return};Start-Sleep -Milliseconds 250} while((Get-Date) -lt $deadline)
    throw $Failure
}
function Assert-TestRoot([string]$Path) {
    $base=[IO.Path]::GetFullPath($testBase).TrimEnd('\')+'\'
    $full=[IO.Path]::GetFullPath($Path).TrimEnd('\')+'\'
    if(!$full.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)){throw "Unsafe test root: $Path"}
}
function Assert-TaskPolicy([string]$Name) {
    $task=Get-ScheduledTask -TaskName $Name -ErrorAction Stop
    $xml=[xml](Export-ScheduledTask -TaskName $Name)
    if(-not [string]::IsNullOrWhiteSpace([string]$xml.Task.Triggers.InnerXml)){throw "Task $Name unexpectedly has a trigger"}
    if([string]$task.Settings.MultipleInstances -ne 'IgnoreNew'){throw "Task $Name does not use IgnoreNew"}
    if([int]$task.Settings.RestartCount -ne 0){throw "Task $Name restart count is nonzero"}
    if([string]$xml.Task.Settings.ExecutionTimeLimit -ne 'PT0S'){throw "Task $Name has a nonzero execution time limit"}
}

if($DispatchChild) {
    if([string]::IsNullOrWhiteSpace($EvidenceRoot) -or [string]::IsNullOrWhiteSpace($TaskName) -or [string]::IsNullOrWhiteSpace($InvocationName)){throw 'DispatchChild requires EvidenceRoot, TaskName, and InvocationName'}
    Assert-TestRoot $EvidenceRoot
    $dispatchStream=$null
    try {
        try {$dispatchStream=[IO.File]::Open((Join-Path $EvidenceRoot 'dispatch.lock'),[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)} catch [IO.IOException] {exit 91}
        if(Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue){throw "Task collision: $TaskName"}
        $quotedWorker='"'+$worker.Replace('"','\"')+'"'
        $quotedRoot='"'+([IO.Path]::GetFullPath($EvidenceRoot)).Replace('"','\"')+'"'
        $arguments="-NoProfile -NonInteractive -ExecutionPolicy Bypass -File $quotedWorker -EvidenceRoot $quotedRoot -InvocationName $InvocationName -Mode $Mode -SleepSeconds $SleepSeconds"
        $action=New-ScheduledTaskAction -Execute $powershell51 -Argument $arguments -WorkingDirectory (Split-Path -Parent $worker)
        $principal=New-ScheduledTaskPrincipal -UserId $expectedIdentity -LogonType Interactive -RunLevel Limited
        $settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 0 -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $TaskName -InputObject (New-ScheduledTask -Action $action -Principal $principal -Settings $settings) -ErrorAction Stop|Out-Null
        $scheduler=New-Object -ComObject 'Schedule.Service';$scheduler.Connect()
        $running=$scheduler.GetFolder('\').GetTask('\'+$TaskName).RunEx($null,0,0,$null)
        Wait-Until { @((Read-Events $EvidenceRoot)|Where-Object{$_.event -eq 'supervisor_started'}).Count -eq 1 } 300 'Task Scheduler COM supervisor did not publish its handshake'
        [ordered]@{status='dispatched';task_name=$TaskName;invocation_name=$InvocationName;mode=$Mode;dispatcher_pid=$PID;running_task_instance_guid=[string]$running.InstanceGuid;timestamp=(Get-Date).ToString('o')}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $EvidenceRoot 'dispatch.json') -Encoding UTF8
        exit 0
    } finally {if($dispatchStream){$dispatchStream.Dispose()}}
}

New-Item -ItemType Directory -Path $testBase -Force|Out-Null
$caseId=[Guid]::NewGuid().ToString('N')
$successRoot=Join-Path $testBase "com-long-success-$caseId";$failureRoot=Join-Path $testBase "com-long-failure-$caseId"
$successTask="SleepStagePaper-R12-COM-Long-Success-$caseId";$failureTask="SleepStagePaper-R12-COM-Long-Failure-$caseId"
$successInvocation="r12-com-long-success-$caseId";$failureInvocation="r12-com-long-failure-$caseId"
$tasks=@($successTask,$failureTask)

try {
    foreach($root in @($successRoot,$failureRoot)){Assert-TestRoot $root;New-Item -ItemType Directory -Path $root -ErrorAction Stop|Out-Null;[IO.File]::WriteAllText((Join-Path $root 'stable-input.txt'),'immutable-canary-input',[Text.UTF8Encoding]::new($false))}
    $successArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DispatchChild','-EvidenceRoot',$successRoot,'-TaskName',$successTask,'-InvocationName',$successInvocation,'-Mode','success','-SleepSeconds',[string]$SleepSeconds)
    if($DebugShortSuccess){$successArgs+='-DebugShortSuccess'}
    $dispatcher=Start-Process -FilePath $powershell51 -ArgumentList $successArgs -WindowStyle Hidden -PassThru -Wait
    if($dispatcher.ExitCode -ne 0){throw "Success dispatcher failed: $($dispatcher.ExitCode)"}
    $started=@((Read-Events $successRoot)|Where-Object{$_.event -eq 'supervisor_started'})
    if($started.Count -ne 1){throw 'Success Scheduler supervisor handshake count is not one'}
    $supervisorPid=[int]$started[0].supervisor_pid
    if(Get-Process -Id $dispatcher.Id -ErrorAction SilentlyContinue){throw 'Dispatcher is unexpectedly alive after Scheduler dispatch'}
    $dispatcherExitProbe=[ordered]@{name='dispatcher_exit';observed_at=(Get-Date).ToString('o');dispatcher_pid=[int]$dispatcher.Id;exited=$true;exit_code=[int]$dispatcher.ExitCode}
    if(!(Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue)){throw 'Scheduler-owned supervisor did not survive dispatcher exit'}
    $supervisorSurvivalProbe=[ordered]@{name='supervisor_alive_after_dispatcher_exit';observed_at=(Get-Date).ToString('o');dispatcher_pid=[int]$dispatcher.Id;supervisor_pid=$supervisorPid;alive=$true}
    $supervisorCim=Get-CimInstance Win32_Process -Filter "ProcessId=$supervisorPid" -ErrorAction Stop
    $supervisorParent=Get-Process -Id ([int]$supervisorCim.ParentProcessId) -ErrorAction Stop
    $supervisorParentName=$supervisorParent.ProcessName+'.exe'
    if($supervisorParentName -ne 'svchost.exe'){throw "Supervisor parent is not svchost.exe: $supervisorParentName"}
    if([string]$started[0].windows_identity -ne $expectedIdentity -or [int]$started[0].session_id -ne $expectedSessionId){throw 'Scheduler supervisor Windows identity or session mismatched'}
    $parentObservation=[ordered]@{supervisor_pid=$supervisorPid;supervisor_parent_pid=[int]$supervisorCim.ParentProcessId;supervisor_parent_name=$supervisorParentName;windows_identity=[string]$started[0].windows_identity;session_id=[int]$started[0].session_id;ownership_claim=[string]$started[0].ownership_claim;observed_at=(Get-Date).ToString('o')}
    [IO.File]::WriteAllText((Join-Path $successRoot 'supervisor-parent.json'),($parentObservation|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    Wait-Until {Test-Path -LiteralPath (Join-Path $successRoot 'wsl-child.heartbeats.jsonl')} 45 'WSL heartbeat stream did not appear'
    $processStarted=@((Read-Events $successRoot)|Where-Object{$_.event -eq 'process_started'})
    if($processStarted.Count -ne 1){throw 'Success canary process_started count is not one'}
    $wslPid=[int]$processStarted[0].child_pid
    if(!(Get-Process -Id $wslPid -ErrorAction SilentlyContinue)){throw 'Foreground wsl.exe was not alive after dispatcher exit'}
    $wslSurvivalProbe=[ordered]@{name='wsl_alive_after_dispatcher_exit';observed_at=(Get-Date).ToString('o');dispatcher_pid=[int]$dispatcher.Id;supervisor_pid=$supervisorPid;wsl_pid=$wslPid;alive=$true}
    if(!(Test-Path -LiteralPath (Join-Path $successRoot 'dispatch.lock'))){throw 'Permanent dispatch marker is absent'}
    if(!(Test-Path -LiteralPath (Join-Path $successRoot 'attempt.lock'))){throw 'Permanent attempt marker is absent'}
    $attemptLockRefused=$false;$attemptProbe=$null;$attemptRefusalException=$null
    try {$attemptProbe=[IO.File]::Open((Join-Path $successRoot 'attempt.lock'),[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)} catch [IO.IOException] {$attemptLockRefused=$true;$attemptRefusalException=$_.Exception.GetType().FullName} finally {if($attemptProbe){$attemptProbe.Dispose()}}
    if(!$attemptLockRefused){throw 'Attempt marker was not exclusively held by the Scheduler supervisor'}
    $attemptLockProbe=[ordered]@{name='attempt_marker_exclusive_open';observed_at=(Get-Date).ToString('o');path=(Join-Path $successRoot 'attempt.lock');open_refused=$attemptLockRefused;exception_type=$attemptRefusalException}
    $stableWriteRefused=$false;$stableProbe=$null;$stableWriteRefusalException=$null
    try {$stableProbe=[IO.File]::Open((Join-Path $successRoot 'stable-input.txt'),[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::None)} catch [IO.IOException] {$stableWriteRefused=$true;$stableWriteRefusalException=$_.Exception.GetType().FullName} finally {if($stableProbe){$stableProbe.Dispose()}}
    if(!$stableWriteRefused){throw 'Stable input write was not refused while the Scheduler supervisor held its read lock'}
    $stableWriteProbe=[ordered]@{name='stable_input_write_open';observed_at=(Get-Date).ToString('o');path=(Join-Path $successRoot 'stable-input.txt');open_refused=$stableWriteRefused;exception_type=$stableWriteRefusalException}
    $replacement=Join-Path $successRoot 'stable-input.replacement.txt'
    [IO.File]::WriteAllText($replacement,'replacement',[Text.UTF8Encoding]::new($false))
    $stableReplaceRefused=$false;$stableReplaceRefusalException=$null
    try {Move-Item -LiteralPath $replacement -Destination (Join-Path $successRoot 'stable-input.txt') -Force -ErrorAction Stop} catch {$stableReplaceRefused=$true;$stableReplaceRefusalException=$_.Exception.GetType().FullName}
    if(!$stableReplaceRefused){throw 'Stable input replacement was not refused while the Scheduler supervisor held its read lock'}
    if(Test-Path -LiteralPath $replacement){Remove-Item -LiteralPath $replacement -Force}
    $stableReplaceProbe=[ordered]@{name='stable_input_replace';observed_at=(Get-Date).ToString('o');path=(Join-Path $successRoot 'stable-input.txt');replace_refused=$stableReplaceRefused;exception_type=$stableReplaceRefusalException}
    $runtimeProbes=[ordered]@{schema_version=1;case_id=$caseId;probes=@($dispatcherExitProbe,$supervisorSurvivalProbe,$wslSurvivalProbe,$attemptLockProbe,$stableWriteProbe,$stableReplaceProbe)}
    [IO.File]::WriteAllText((Join-Path $successRoot 'runtime-probes.json'),($runtimeProbes|ConvertTo-Json -Depth 6 -Compress),[Text.UTF8Encoding]::new($false))
    Wait-Until {(@(Get-Content -LiteralPath (Join-Path $successRoot 'wsl-child.heartbeats.jsonl') -ErrorAction SilentlyContinue)).Count -ge 3} 35 'Long canary did not publish periodic heartbeats'
    $heartbeatLines=@(Get-Content -LiteralPath (Join-Path $successRoot 'wsl-child.heartbeats.jsonl'))
    $heartbeats=@($heartbeatLines|ForEach-Object{$_|ConvertFrom-Json})
    $heartbeatEpochs=@($heartbeats|ForEach-Object{[int64]$_.epoch_seconds})
    for($i=1;$i -lt $heartbeatEpochs.Count;$i++){if(($heartbeatEpochs[$i]-$heartbeatEpochs[$i-1]) -gt 10){throw 'WSL heartbeat interval exceeded 10 seconds'}}
    if(@($heartbeats|Select-Object -ExpandProperty boot_id -Unique).Count -ne 1){throw 'WSL boot_id changed across heartbeats'}
    Wait-Until {@((Read-Events $successRoot)|Where-Object{$_.event -eq 'terminal_validated'}).Count -eq 1} ([math]::Max(($SleepSeconds+90),300)) 'Success long canary did not reach terminal_validated'
    $successEvents=Read-Events $successRoot;$successExit=@($successEvents|Where-Object{$_.event -eq 'process_exited'})
    if($successExit.Count -ne 1 -or [int]$successExit[0].exit_code -ne 0){throw 'Success long canary exit evidence is not zero'}
    $finalHeartbeatLines=@(Get-Content -LiteralPath (Join-Path $successRoot 'wsl-child.heartbeats.jsonl') -ErrorAction Stop)
    $finalHeartbeats=@($finalHeartbeatLines|ForEach-Object{$_|ConvertFrom-Json -ErrorAction Stop})
    if($finalHeartbeats.Count -lt ([math]::Floor($SleepSeconds/10)+1)){throw 'Final heartbeat evidence is too sparse for the accepted duration'}
    $finalEpochs=@($finalHeartbeats|ForEach-Object{[int64]$_.epoch_seconds})
    for($i=1;$i -lt $finalEpochs.Count;$i++){if(($finalEpochs[$i]-$finalEpochs[$i-1]) -gt 10){throw 'Final WSL heartbeat interval exceeded 10 seconds'}}
    if(@($finalHeartbeats|Select-Object -ExpandProperty boot_id -Unique).Count -ne 1){throw 'Final WSL boot_id evidence is not continuous'}
    $heartbeatSpanSeconds=$finalEpochs[-1]-$finalEpochs[0]
    if($heartbeatSpanSeconds -lt ($SleepSeconds-1)){throw "Final WSL heartbeat span $heartbeatSpanSeconds is shorter than the requested duration $SleepSeconds"}
    Wait-Until {-not (Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue)} 60 'Success supervisor did not terminate'
    $second=Start-Process -FilePath $powershell51 -ArgumentList $successArgs -WindowStyle Hidden -PassThru -Wait
    if($second.ExitCode -ne 91){throw "Second dispatcher returned $($second.ExitCode), expected 91"}
    $directSecond=Start-Process -FilePath $powershell51 -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$worker,'-EvidenceRoot',$successRoot,'-InvocationName',$successInvocation,'-Mode','success','-SleepSeconds','2') -WindowStyle Hidden -PassThru -Wait
    if($directSecond.ExitCode -ne 91){throw "Second supervisor returned $($directSecond.ExitCode), expected 91"}
    $failureArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DispatchChild','-EvidenceRoot',$failureRoot,'-TaskName',$failureTask,'-InvocationName',$failureInvocation,'-Mode','failure','-SleepSeconds','2')
    $failureDispatcher=Start-Process -FilePath $powershell51 -ArgumentList $failureArgs -WindowStyle Hidden -PassThru -Wait
    if($failureDispatcher.ExitCode -ne 0){throw "Failure dispatcher failed: $($failureDispatcher.ExitCode)"}
    Wait-Until {@((Read-Events $failureRoot)|Where-Object{$_.event -eq 'terminal_validation_failed'}).Count -eq 1} 300 'Failure canary did not fail closed'
    $failureExit=@((Read-Events $failureRoot)|Where-Object{$_.event -eq 'process_exited'})
    if($failureExit.Count -ne 1 -or [int]$failureExit[0].exit_code -ne 23){throw 'Failure canary did not bind exit code 23'}
    Start-Sleep -Seconds 5
    if(@((Read-Events $failureRoot)|Where-Object{$_.event -eq 'supervisor_started'}).Count -ne 1){throw 'Failure supervisor restarted automatically'}
    foreach($taskName in $tasks){Assert-TaskPolicy $taskName}
    $policy=@();foreach($taskName in $tasks){$task=Get-ScheduledTask -TaskName $taskName -ErrorAction Stop;$xml=[xml](Export-ScheduledTask -TaskName $taskName);$triggerElements=@($xml.Task.Triggers.ChildNodes|Where-Object{$_.NodeType-eq[Xml.XmlNodeType]::Element});$policy+=@([ordered]@{task_name=$taskName;trigger_element_count=$triggerElements.Count;triggers_inner_xml=[string]$xml.Task.Triggers.InnerXml;multiple_instances=[string]$task.Settings.MultipleInstances;restart_count=[int]$task.Settings.RestartCount;execution_time_limit=[string]$xml.Task.Settings.ExecutionTimeLimit})}
    [IO.File]::WriteAllText((Join-Path $successRoot 'task-policy.json'),($policy|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $successRoot 'refusal-results.json'),([ordered]@{second_dispatch_exit_code=[int]$second.ExitCode;second_supervisor_exit_code=[int]$directSecond.ExitCode;observed_at=(Get-Date).ToString('o')}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    $heartbeatIntervalMax=0;for($i=1;$i-lt$finalEpochs.Count;$i++){$delta=$finalEpochs[$i]-$finalEpochs[$i-1];if($delta-gt$heartbeatIntervalMax){$heartbeatIntervalMax=$delta}}
    $acceptance=[ordered]@{status='pass';acceptance_evidence=(!$DebugShortSuccess);debug_short_success=[bool]$DebugShortSuccess;pilot_launched=$false;success_duration_seconds=$SleepSeconds;dispatcher_exited=$true;supervisor_parent=$supervisorParentName;wsl_alive_after_dispatcher_exit=$true;attempt_marker_exclusively_held=$attemptLockRefused;stable_input_write_refused=$stableWriteRefused;stable_input_replace_refused=$stableReplaceRefused;heartbeat_count=$finalHeartbeats.Count;heartbeat_span_seconds=$heartbeatSpanSeconds;heartbeat_interval_seconds_max=$heartbeatIntervalMax;boot_id_continuous=$true;atomic_exit_evidence=$true;success_exit_code=0;failure_exit_code=23;second_dispatch_refused=91;second_supervisor_refused=91;triggers=0;multiple_instances='IgnoreNew';restart_count=0;execution_time_limit='PT0S';evidence_roots=@($successRoot,$failureRoot)}
    [IO.File]::WriteAllText((Join-Path $successRoot 'acceptance.json'),($acceptance|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    $acceptance|ConvertTo-Json -Compress
} finally {
    foreach($taskName in $tasks){$task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue;if($task){if($task.State -eq 'Running'){Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue;Start-Sleep -Milliseconds 500};Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue}}
}
