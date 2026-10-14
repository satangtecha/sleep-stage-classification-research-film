param(
    [switch]$DispatchChild,
    [string]$EvidenceRoot,
    [string]$InvocationName,
    [ValidateSet('success','failure')][string]$Mode='success',
    [ValidateRange(2,60)][int]$SleepSeconds=12
)

$ErrorActionPreference='Stop'
$worker=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'r11_wmi_supervisor_canary_worker.ps1')).Path
$powershell51="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$testBase='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r11-wmi-survival-tests'
$expectedIdentity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$expectedSessionId=(Get-Process -Id $PID).SessionId

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

function Quote-CommandLineArgument([string]$Value) {
    if($Value -notmatch '[\s"]'){return $Value}
    return '"'+$Value.Replace('"','\"')+'"'
}

if($DispatchChild) {
    if([string]::IsNullOrWhiteSpace($EvidenceRoot) -or [string]::IsNullOrWhiteSpace($InvocationName)){throw 'DispatchChild requires EvidenceRoot and InvocationName'}
    Assert-TestRoot $EvidenceRoot
    $dispatchMarker=Join-Path $EvidenceRoot 'dispatch.lock'
    $dispatchStream=$null
    try {
        try {
            $dispatchStream=[IO.File]::Open($dispatchMarker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        } catch [IO.IOException] {
            exit 91
        }
        $arguments=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$worker,'-EvidenceRoot',[IO.Path]::GetFullPath($EvidenceRoot),'-InvocationName',$InvocationName,'-Mode',$Mode,'-SleepSeconds',[string]$SleepSeconds)
        $commandLine=((Quote-CommandLineArgument $powershell51)+' '+(($arguments|ForEach-Object{Quote-CommandLineArgument ([string]$_)}) -join ' '))
        $created=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$commandLine;CurrentDirectory=(Split-Path -Parent $worker)}
        if([int]$created.ReturnValue -ne 0){throw "Win32_Process.Create failed with return value $($created.ReturnValue)"}
        Wait-Until { @((Read-Events $EvidenceRoot)|Where-Object{$_.event -eq 'supervisor_started'}).Count -eq 1 } 60 'WMI supervisor did not publish its handshake'
        [ordered]@{status='dispatched';invocation_name=$InvocationName;mode=$Mode;dispatcher_pid=$PID;supervisor_pid=[int]$created.ProcessId;timestamp=(Get-Date).ToString('o')}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $EvidenceRoot 'dispatch.json') -Encoding UTF8
        exit 0
    } finally {
        if($dispatchStream){$dispatchStream.Dispose()}
    }
}

New-Item -ItemType Directory -Path $testBase -Force|Out-Null
$caseId=[Guid]::NewGuid().ToString('N')
$successRoot=Join-Path $testBase "wmi-success-$caseId"
$failureRoot=Join-Path $testBase "wmi-failure-$caseId"
$successInvocation="r11-wmi-success-$caseId"
$failureInvocation="r11-wmi-failure-$caseId"
$roots=@($successRoot,$failureRoot)
$completed=$false

try {
    foreach($root in $roots){Assert-TestRoot $root;New-Item -ItemType Directory -Path $root -ErrorAction Stop|Out-Null;[IO.File]::WriteAllText((Join-Path $root 'stable-input.txt'),'immutable-canary-input',[Text.UTF8Encoding]::new($false))}

    $successDispatchStdout=Join-Path $successRoot 'dispatcher.stdout.log'
    $successDispatchStderr=Join-Path $successRoot 'dispatcher.stderr.log'
    $dispatchArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DispatchChild','-EvidenceRoot',$successRoot,'-InvocationName',$successInvocation,'-Mode','success','-SleepSeconds',[string]$SleepSeconds)
    $dispatcher=Start-Process -FilePath $powershell51 -ArgumentList $dispatchArgs -WindowStyle Hidden -RedirectStandardOutput $successDispatchStdout -RedirectStandardError $successDispatchStderr -PassThru -Wait
    if($dispatcher.ExitCode -ne 0){throw "Success dispatcher failed: $($dispatcher.ExitCode); stderr=$(@(Get-Content -LiteralPath $successDispatchStderr -ErrorAction SilentlyContinue) -join ' ')"}

    $successEvents=Read-Events $successRoot
    $started=@($successEvents|Where-Object{$_.event -eq 'supervisor_started'})
    if($started.Count -ne 1){throw 'Success WMI supervisor handshake count is not one'}
    $supervisorPid=[int]$started[0].supervisor_pid
    if(Get-Process -Id $dispatcher.Id -ErrorAction SilentlyContinue){throw 'Dispatcher is unexpectedly alive after WMI dispatch'}
    if(!(Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue)){throw 'WMI-owned supervisor did not survive dispatcher exit'}
    if([string]$started[0].windows_identity -ne $expectedIdentity){throw "WMI supervisor identity mismatch: $($started[0].windows_identity)"}
    if([int]$started[0].session_id -ne $expectedSessionId){throw "WMI supervisor session mismatch: $($started[0].session_id)"}
    if([string]$started[0].supervisor_parent_name -notmatch '^WmiPrvSE\.exe$'){throw "Unexpected WMI supervisor parent: $($started[0].supervisor_parent_name)"}

    Wait-Until { Test-Path -LiteralPath (Join-Path $successRoot 'wsl-child.stdout.log') } 30 'WSL child stdout did not appear'
    Wait-Until { @((Get-Content -LiteralPath (Join-Path $successRoot 'wsl-child.stdout.log') -ErrorAction SilentlyContinue)|Where-Object{$_ -eq 'WSL_USER=techatat'}).Count -eq 1 } 30 'Expected WSL user was not observed'
    $liveEvents=Read-Events $successRoot
    $wslPid=[int](@($liveEvents|Where-Object{$_.event -eq 'process_started'})[0].child_pid)
    if(!(Get-Process -Id $wslPid -ErrorAction SilentlyContinue)){throw 'WSL host process was not alive after dispatcher exit'}

    $writeRefused=$false;$writeStream=$null
    try {$writeStream=[IO.File]::Open((Join-Path $successRoot 'stable-input.txt'),[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::None)} catch [IO.IOException] {$writeRefused=$true} finally {if($writeStream){$writeStream.Dispose()}}
    if(!$writeRefused){throw 'Stable input write was not refused while supervisor held the lock'}

    $replacement=Join-Path $successRoot 'replacement.txt';[IO.File]::WriteAllText($replacement,'replacement',[Text.UTF8Encoding]::new($false))
    $replaceRefused=$false
    try {Move-Item -LiteralPath $replacement -Destination (Join-Path $successRoot 'stable-input.txt') -Force -ErrorAction Stop} catch {$replaceRefused=$true}
    if(!$replaceRefused){throw 'Stable input replacement was not refused while supervisor held the lock'}
    if(Test-Path -LiteralPath $replacement){Remove-Item -LiteralPath $replacement -Force}

    Wait-Until { @((Read-Events $successRoot)|Where-Object{$_.event -eq 'terminal_validated'}).Count -eq 1 } ($SleepSeconds+60) 'Success WMI canary did not reach terminal_validated'
    Wait-Until { -not (Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue) } 60 'Success WMI supervisor did not terminate'

    $second=Start-Process -FilePath $powershell51 -ArgumentList $dispatchArgs -WindowStyle Hidden -PassThru -Wait
    if($second.ExitCode -ne 91){throw "Second dispatcher returned $($second.ExitCode), expected permanent dispatch-marker refusal 91"}
    $afterSecond=Read-Events $successRoot
    if(@($afterSecond|Where-Object{$_.event -eq 'supervisor_started'}).Count -ne 1){throw 'Second dispatch created another supervisor'}

    $directSecondArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$worker,'-EvidenceRoot',$successRoot,'-InvocationName',$successInvocation,'-Mode','success','-SleepSeconds','2')
    $directSecond=Start-Process -FilePath $powershell51 -ArgumentList $directSecondArgs -WindowStyle Hidden -PassThru -Wait
    if($directSecond.ExitCode -ne 91){throw "Second supervisor invocation returned $($directSecond.ExitCode), expected attempt-marker refusal 91"}
    Wait-Until { Test-Path -LiteralPath (Join-Path $successRoot 'refusals.jsonl') } 30 'Second supervisor invocation did not record marker refusal'

    $failureDispatchStdout=Join-Path $failureRoot 'dispatcher.stdout.log'
    $failureDispatchStderr=Join-Path $failureRoot 'dispatcher.stderr.log'
    $failureDispatchArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DispatchChild','-EvidenceRoot',$failureRoot,'-InvocationName',$failureInvocation,'-Mode','failure','-SleepSeconds','2')
    $failureDispatcher=Start-Process -FilePath $powershell51 -ArgumentList $failureDispatchArgs -WindowStyle Hidden -RedirectStandardOutput $failureDispatchStdout -RedirectStandardError $failureDispatchStderr -PassThru -Wait
    if($failureDispatcher.ExitCode -ne 0){throw "Failure dispatcher failed before WMI ownership: $($failureDispatcher.ExitCode); stderr=$(@(Get-Content -LiteralPath $failureDispatchStderr -ErrorAction SilentlyContinue) -join ' ')"}
    Wait-Until { @((Read-Events $failureRoot)|Where-Object{$_.event -eq 'terminal_validation_failed'}).Count -eq 1 } 90 'Failure WMI canary did not publish terminal_validation_failed'
    $failureEvents=Read-Events $failureRoot
    $failureExit=@($failureEvents|Where-Object{$_.event -eq 'process_exited'})
    if($failureExit.Count -ne 1 -or [int]$failureExit[0].exit_code -ne 23){throw 'Failure WMI canary did not bind child exit code 23'}
    $failureSupervisorPid=[int](@($failureEvents|Where-Object{$_.event -eq 'supervisor_started'})[0].supervisor_pid)
    Wait-Until { -not (Get-Process -Id $failureSupervisorPid -ErrorAction SilentlyContinue) } 60 'Failure WMI supervisor did not terminate'
    Start-Sleep -Seconds 5
    if(@((Read-Events $failureRoot)|Where-Object{$_.event -eq 'supervisor_started'}).Count -ne 1){throw 'Failure WMI supervisor restarted automatically'}

    $completed=$true
    [ordered]@{
        status='pass'
        pilot_launched=$false
        caller_termination_survived=$true
        supervisor_owned_by_wmi_service=$true
        supervisor_parent_name=[string]$started[0].supervisor_parent_name
        windows_identity=[string]$started[0].windows_identity
        session_id=[int]$started[0].session_id
        wsl_user='techatat'
        wsl_gpu_observed=$true
        stable_input_write_refused=$writeRefused
        stable_input_replace_refused=$replaceRefused
        terminal_validated_recorded=$true
        nonzero_exit_recorded=$true
        dispatch_marker_refused_second_dispatch=$true
        attempt_marker_refused_second_supervisor=$true
        automatic_restart_observed=$false
    }|ConvertTo-Json -Compress
} finally {
    if($completed){
        foreach($root in $roots){
            if(Test-Path -LiteralPath $root){Assert-TestRoot $root;Remove-Item -LiteralPath $root -Recurse -Force}
        }
    }
}
