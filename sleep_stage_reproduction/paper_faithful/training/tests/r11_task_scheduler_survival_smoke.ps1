param(
    [switch]$DispatchChild,
    [string]$EvidenceRoot,
    [string]$TaskName,
    [ValidateSet('success','failure')][string]$Mode='success',
    [ValidateRange(2,60)][int]$SleepSeconds=12
)

$ErrorActionPreference='Stop'
$worker=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'r11_task_scheduler_canary_worker.ps1')).Path
$powershell51="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$testBase='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r11-task-scheduler-tests'

function Read-Events([string]$Root) {
    $path=Join-Path $Root 'lifecycle.jsonl'
    if(!(Test-Path -LiteralPath $path)){return @()}
    try {
        return @(Get-Content -LiteralPath $path -ErrorAction Stop|ForEach-Object{if(-not [string]::IsNullOrWhiteSpace($_)){$_|ConvertFrom-Json -ErrorAction Stop}})
    } catch [IO.IOException] {
        return @()
    } catch [System.Management.Automation.RuntimeException] {
        return @()
    }
}

function Wait-Until([scriptblock]$Condition,[int]$TimeoutSeconds,[string]$Failure) {
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if(& $Condition){return}
        Start-Sleep -Milliseconds 200
    } while((Get-Date) -lt $deadline)
    throw $Failure
}

function Assert-TestRoot([string]$Path) {
    $base=[IO.Path]::GetFullPath($testBase).TrimEnd('\')+'\'
    $full=[IO.Path]::GetFullPath($Path).TrimEnd('\')+'\'
    if(!$full.StartsWith($base,[StringComparison]::OrdinalIgnoreCase)){throw "Unsafe test root: $Path"}
}

if($DispatchChild) {
    if([string]::IsNullOrWhiteSpace($EvidenceRoot) -or [string]::IsNullOrWhiteSpace($TaskName)){throw 'DispatchChild requires EvidenceRoot and TaskName'}
    Assert-TestRoot $EvidenceRoot
    if(Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue){throw "Task collision: $TaskName"}

    $quotedWorker='"'+$worker.Replace('"','\"')+'"'
    $quotedRoot='"'+([IO.Path]::GetFullPath($EvidenceRoot)).Replace('"','\"')+'"'
    $arguments="-NoProfile -NonInteractive -ExecutionPolicy Bypass -File $quotedWorker -EvidenceRoot $quotedRoot -TaskName $TaskName -Mode $Mode -SleepSeconds $SleepSeconds"
    $action=New-ScheduledTaskAction -Execute $powershell51 -Argument $arguments -WorkingDirectory (Split-Path -Parent $worker)
    $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 0 -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $definition=New-ScheduledTask -Action $action -Principal $principal -Settings $settings
    Register-ScheduledTask -TaskName $TaskName -InputObject $definition -ErrorAction Stop|Out-Null
    Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Wait-Until { @((Read-Events $EvidenceRoot)|Where-Object{$_.event -eq 'supervisor_started'}).Count -eq 1 } 180 'Task supervisor did not publish its handshake'
    [ordered]@{status='dispatched';task_name=$TaskName;mode=$Mode;dispatcher_pid=$PID;timestamp=(Get-Date).ToString('o')}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $EvidenceRoot 'dispatch.json') -Encoding UTF8
    exit 0
}

New-Item -ItemType Directory -Path $testBase -Force|Out-Null
$caseId=[Guid]::NewGuid().ToString('N')
$successRoot=Join-Path $testBase "success-$caseId"
$failureRoot=Join-Path $testBase "failure-$caseId"
$successTask="SleepStagePaper-R11-Survival-$caseId"
$failureTask="SleepStagePaper-R11-Failure-$caseId"
$registered=@()
$roots=@($successRoot,$failureRoot)
$completed=$false

try {
    foreach($root in $roots){Assert-TestRoot $root;New-Item -ItemType Directory -Path $root -ErrorAction Stop|Out-Null;[IO.File]::WriteAllText((Join-Path $root 'stable-input.txt'),'immutable-canary-input',[Text.UTF8Encoding]::new($false))}

    $dispatchArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DispatchChild','-EvidenceRoot',$successRoot,'-TaskName',$successTask,'-Mode','success','-SleepSeconds',$SleepSeconds)
    $registered+=@($successTask)
    $successDispatchStdout=Join-Path $successRoot 'dispatcher.stdout.log';$successDispatchStderr=Join-Path $successRoot 'dispatcher.stderr.log'
    $dispatcher=Start-Process -FilePath $powershell51 -ArgumentList $dispatchArgs -WindowStyle Hidden -RedirectStandardOutput $successDispatchStdout -RedirectStandardError $successDispatchStderr -PassThru -Wait
    if($dispatcher.ExitCode -ne 0){throw "Success dispatcher failed: $($dispatcher.ExitCode); stderr=$(@(Get-Content -LiteralPath $successDispatchStderr -ErrorAction SilentlyContinue) -join ' ')"}

    $successEvents=Read-Events $successRoot
    $supervisorPid=[int](@($successEvents|Where-Object{$_.event -eq 'supervisor_started'})[0].supervisor_pid)
    if(Get-Process -Id $dispatcher.Id -ErrorAction SilentlyContinue){throw 'Dispatcher is unexpectedly alive after dispatch'}
    if(!(Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue)){throw 'Task-owned supervisor did not survive dispatcher exit'}
    if((Get-ScheduledTask -TaskName $successTask).State -ne 'Running'){throw 'Scheduled task is not running after dispatcher exit'}

    $writeRefused=$false;$writeStream=$null
    try {$writeStream=[IO.File]::Open((Join-Path $successRoot 'stable-input.txt'),[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::None)} catch [IO.IOException] {$writeRefused=$true} finally {if($writeStream){$writeStream.Dispose()}}
    if(!$writeRefused){throw 'Stable input write was not refused while supervisor held the lock'}

    $replacement=Join-Path $successRoot 'replacement.txt';[IO.File]::WriteAllText($replacement,'replacement',[Text.UTF8Encoding]::new($false))
    $replaceRefused=$false
    try {Move-Item -LiteralPath $replacement -Destination (Join-Path $successRoot 'stable-input.txt') -Force -ErrorAction Stop} catch {$replaceRefused=$true}
    if(!$replaceRefused){throw 'Stable input replacement was not refused while supervisor held the lock'}
    if(Test-Path -LiteralPath $replacement){Remove-Item -LiteralPath $replacement -Force}

    Wait-Until { @((Read-Events $successRoot)|Where-Object{$_.event -eq 'terminal_validated'}).Count -eq 1 } ($SleepSeconds+60) 'Success canary did not reach terminal_validated'
    Wait-Until { -not (Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue) } 60 'Success supervisor process did not terminate'
    $successTaskSnapshot=Get-ScheduledTask -TaskName $successTask
    $successInfo=Get-ScheduledTaskInfo -TaskName $successTask

    $secondArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$worker,'-EvidenceRoot',$successRoot,'-TaskName',$successTask,'-Mode','success','-SleepSeconds',2)
    $second=Start-Process -FilePath $powershell51 -ArgumentList $secondArgs -WindowStyle Hidden -PassThru -Wait
    if($second.ExitCode -ne 91){throw "Second supervisor invocation returned $($second.ExitCode), expected marker refusal 91"}
    Wait-Until { Test-Path -LiteralPath (Join-Path $successRoot 'refusals.jsonl') } 30 'Second supervisor invocation was not refused by marker collision'
    $afterSecond=Read-Events $successRoot
    if(@($afterSecond|Where-Object{$_.event -eq 'process_started'}).Count -ne 1){throw 'Second task start created another child process'}

    $dispatchFailureArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DispatchChild','-EvidenceRoot',$failureRoot,'-TaskName',$failureTask,'-Mode','failure','-SleepSeconds',2)
    $registered+=@($failureTask)
    $failureDispatchStdout=Join-Path $failureRoot 'dispatcher.stdout.log';$failureDispatchStderr=Join-Path $failureRoot 'dispatcher.stderr.log'
    $failureDispatcher=Start-Process -FilePath $powershell51 -ArgumentList $dispatchFailureArgs -WindowStyle Hidden -RedirectStandardOutput $failureDispatchStdout -RedirectStandardError $failureDispatchStderr -PassThru -Wait
    if($failureDispatcher.ExitCode -ne 0){throw "Failure dispatcher failed before task ownership: $($failureDispatcher.ExitCode); stderr=$(@(Get-Content -LiteralPath $failureDispatchStderr -ErrorAction SilentlyContinue) -join ' ')"}
    Wait-Until { @((Read-Events $failureRoot)|Where-Object{$_.event -eq 'terminal_validation_failed'}).Count -eq 1 } 180 'Failure canary did not publish terminal_validation_failed'
    $failureEvents=Read-Events $failureRoot
    $failureSupervisorPid=[int](@($failureEvents|Where-Object{$_.event -eq 'supervisor_started'})[0].supervisor_pid)
    $failureExit=@($failureEvents|Where-Object{$_.event -eq 'process_exited'})
    if($failureExit.Count -ne 1 -or [int]$failureExit[0].exit_code -ne 23){throw 'Failure canary did not bind child exit code 23'}
    Wait-Until { -not (Get-Process -Id $failureSupervisorPid -ErrorAction SilentlyContinue) } 60 'Failure supervisor process did not terminate'
    $failureTaskSnapshot=Get-ScheduledTask -TaskName $failureTask
    $failureInfo=Get-ScheduledTaskInfo -TaskName $failureTask
    Start-Sleep -Seconds 10
    if(@((Read-Events $failureRoot)|Where-Object{$_.event -eq 'supervisor_started'}).Count -ne 1){throw 'Failure task restarted automatically'}

    $task=Get-ScheduledTask -TaskName $successTask
    if(@($task.Triggers).Count -ne 0){throw 'Canary task unexpectedly has a trigger'}
    if([string]$task.Settings.MultipleInstances -ne 'IgnoreNew'){throw 'Canary task does not use IgnoreNew'}
    if([int]$task.Settings.RestartCount -ne 0){throw 'Canary task restart count is nonzero'}

    $completed=$true
    [ordered]@{
        status='pass'
        pilot_launched=$false
        caller_termination_survived=$true
        supervisor_owned_by_task_scheduler=$true
        stable_input_write_refused=$writeRefused
        stable_input_replace_refused=$replaceRefused
        terminal_validated_recorded=$true
        nonzero_exit_recorded=$true
        marker_refused_second_start=$true
        automatic_restart_observed=$false
        triggers=0
        multiple_instances='IgnoreNew'
        restart_count=0
        success_scheduler_state_at_observation=[string]$successTaskSnapshot.State
        success_last_task_result_at_observation=$successInfo.LastTaskResult
        failure_scheduler_state_at_observation=[string]$failureTaskSnapshot.State
        failure_last_task_result_at_observation=$failureInfo.LastTaskResult
    }|ConvertTo-Json -Compress
} finally {
    foreach($taskName in $registered){
        $existingTask=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if($existingTask){
            if($existingTask.State -eq 'Running'){Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue;Start-Sleep -Milliseconds 500}
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
        }
    }
    if($completed){foreach($root in $roots){if(Test-Path -LiteralPath $root){Assert-TestRoot $root;Remove-Item -LiteralPath $root -Recurse -Force}}}
}
