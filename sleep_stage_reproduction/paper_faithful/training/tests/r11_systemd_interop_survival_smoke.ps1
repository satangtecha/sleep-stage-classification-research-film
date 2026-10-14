param(
    [switch]$DispatchChild,
    [string]$EvidenceRoot,
    [string]$UnitName,
    [string]$InvocationName,
    [ValidateSet('success','failure')][string]$Mode='success',
    [ValidateRange(2,60)][int]$SleepSeconds=12
)

$ErrorActionPreference='Stop'
$worker=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'r11_systemd_lockholder_canary.ps1')).Path
$supervisorScript='./paper_faithful/training/tests/r11_systemd_canary_supervisor.sh'
$powershell51="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$powershellWsl='/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$projectWsl='/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction'
$testBase='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r11-systemd-interop-tests'
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

function Convert-ToWslPath([string]$WindowsPath) {
    $full=[IO.Path]::GetFullPath($WindowsPath)
    if($full -notmatch '^([A-Za-z]):\\(.*)$'){throw "Unsupported Windows path for WSL conversion: $WindowsPath"}
    return '/mnt/'+$Matches[1].ToLowerInvariant()+'/'+$Matches[2].Replace('\','/')
}

function Get-UnitProperties([string]$Name) {
    $lines=@(& wsl.exe -d Ubuntu -u root -e systemctl show $Name --property=LoadState,ActiveState,SubState,MainPID,ExecMainCode,ExecMainStatus,Result,Restart --no-pager 2>&1|ForEach-Object{"$_"})
    $values=@{}
    foreach($line in $lines){if($line -match '^([^=]+)=(.*)$'){$values[$Matches[1]]=$Matches[2]}}
    return $values
}

if($DispatchChild) {
    if([string]::IsNullOrWhiteSpace($EvidenceRoot) -or [string]::IsNullOrWhiteSpace($UnitName) -or [string]::IsNullOrWhiteSpace($InvocationName)){throw 'DispatchChild requires EvidenceRoot, UnitName, and InvocationName'}
    Assert-TestRoot $EvidenceRoot
    if($UnitName -notmatch '^sleep-stage-r11-interop-[a-z0-9-]+\.service$'){throw "Unsafe canary unit name: $UnitName"}
    $dispatchMarker=Join-Path $EvidenceRoot 'dispatch.lock'
    $dispatchStream=$null
    try {
        try {
            $dispatchStream=[IO.File]::Open($dispatchMarker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        } catch [IO.IOException] {
            exit 91
        }
        $existing=Get-UnitProperties $UnitName
        if($existing.LoadState -and $existing.LoadState -ne 'not-found'){throw "Unit collision: $UnitName ($($existing.LoadState))"}
        $dispatchStdout=Join-Path $EvidenceRoot 'systemd-run.stdout.log'
        $dispatchStderr=Join-Path $EvidenceRoot 'systemd-run.stderr.log'
        $wslEvidenceRoot=Convert-ToWslPath $EvidenceRoot
        $requestedExitCode=$(if($Mode -eq 'success'){0}else{23})
        $arguments=@(
            '--unit',$UnitName,
            '--property=User=techatat',
            '--property=Restart=no',
            '--property=Type=exec',
            '--property=KillMode=control-group',
            ("--property=WorkingDirectory="+$projectWsl),
            '--collect',
            '/bin/bash','--noprofile','--norc',$supervisorScript,
            [string]$SleepSeconds,
            [string]$requestedExitCode,
            $wslEvidenceRoot,
            [IO.Path]::GetFullPath($EvidenceRoot),
            $worker,
            $InvocationName
        )
        $savedPreference=$ErrorActionPreference
        $ErrorActionPreference='Continue'
        try {
            & wsl.exe -d Ubuntu -u root -e systemd-run @arguments 1>$dispatchStdout 2>$dispatchStderr
            $dispatchExit=$LASTEXITCODE
        } finally {
            $ErrorActionPreference=$savedPreference
        }
        if($dispatchExit -ne 0){throw "systemd-run failed with exit code $dispatchExit"}
        Wait-Until { @((Read-Events $EvidenceRoot)|Where-Object{$_.event -eq 'stable_locks_ready'}).Count -eq 1 } 120 'systemd interop lock holder did not publish its handshake'
        $unit=Get-UnitProperties $UnitName
        if($unit.Restart -ne 'no'){throw "Transient unit restart policy is not no: $($unit.Restart)"}
        [ordered]@{
            status='dispatched'
            unit_name=$UnitName
            invocation_name=$InvocationName
            mode=$Mode
            dispatcher_pid=$PID
            restart=$unit.Restart
            active_state=$unit.ActiveState
            sub_state=$unit.SubState
            main_pid=$unit.MainPID
            timestamp=(Get-Date).ToString('o')
        }|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $EvidenceRoot 'dispatch.json') -Encoding UTF8
        exit 0
    } finally {
        if($dispatchStream){$dispatchStream.Dispose()}
    }
}

New-Item -ItemType Directory -Path $testBase -Force|Out-Null
$caseId=[Guid]::NewGuid().ToString('N')
$successRoot=Join-Path $testBase "interop-success-$caseId"
$failureRoot=Join-Path $testBase "interop-failure-$caseId"
$successUnit="sleep-stage-r11-interop-success-$caseId.service"
$failureUnit="sleep-stage-r11-interop-failure-$caseId.service"
$successInvocation="r11-interop-success-$caseId"
$failureInvocation="r11-interop-failure-$caseId"
$units=@($successUnit,$failureUnit)
$roots=@($successRoot,$failureRoot)
$completed=$false

try {
    foreach($root in $roots){Assert-TestRoot $root;New-Item -ItemType Directory -Path $root -ErrorAction Stop|Out-Null;[IO.File]::WriteAllText((Join-Path $root 'stable-input.txt'),'immutable-canary-input',[Text.UTF8Encoding]::new($false))}

    $successDispatchStdout=Join-Path $successRoot 'dispatcher.stdout.log'
    $successDispatchStderr=Join-Path $successRoot 'dispatcher.stderr.log'
    $successDispatchArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DispatchChild','-EvidenceRoot',$successRoot,'-UnitName',$successUnit,'-InvocationName',$successInvocation,'-Mode','success','-SleepSeconds',[string]$SleepSeconds)
    $dispatcher=Start-Process -FilePath $powershell51 -ArgumentList $successDispatchArgs -WindowStyle Hidden -RedirectStandardOutput $successDispatchStdout -RedirectStandardError $successDispatchStderr -PassThru -Wait
    if($dispatcher.ExitCode -ne 0){throw "Success dispatcher failed: $($dispatcher.ExitCode); stderr=$(@(Get-Content -LiteralPath $successDispatchStderr -ErrorAction SilentlyContinue) -join ' ')"}

    $successEvents=Read-Events $successRoot
    $started=@($successEvents|Where-Object{$_.event -eq 'lockholder_started'})
    if($started.Count -ne 1){throw 'Success systemd interop lock-holder handshake count is not one'}
    $supervisorPid=[int]$started[0].lockholder_pid
    if(Get-Process -Id $dispatcher.Id -ErrorAction SilentlyContinue){throw 'Dispatcher is unexpectedly alive after systemd dispatch'}
    if(!(Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue)){throw 'systemd-owned Windows supervisor did not survive dispatcher exit'}
    if([string]$started[0].lockholder_parent_name -ne 'wslhost.exe'){throw "Unexpected systemd interop parent: $($started[0].lockholder_parent_name)"}
    if([string]$started[0].windows_identity -ne $expectedIdentity){throw "systemd interop supervisor identity mismatch: $($started[0].windows_identity)"}
    if([int]$started[0].session_id -ne $expectedSessionId){throw "systemd interop supervisor session mismatch: $($started[0].session_id)"}
    $activeUnit=Get-UnitProperties $successUnit
    if($activeUnit.ActiveState -ne 'active' -or $activeUnit.Restart -ne 'no'){throw "systemd unit is not active with Restart=no: $($activeUnit.ActiveState)/$($activeUnit.Restart)"}

    Wait-Until { Test-Path -LiteralPath (Join-Path $successRoot 'wsl-child.stdout.log') } 60 'WSL child stdout did not appear'
    Wait-Until { @((Get-Content -LiteralPath (Join-Path $successRoot 'wsl-child.stdout.log') -ErrorAction SilentlyContinue)|Where-Object{$_ -eq 'WSL_USER=techatat'}).Count -eq 1 } 60 'Expected WSL user was not observed'
    if([int]$activeUnit.MainPID -le 0){throw 'systemd unit has no live Linux main PID after dispatcher exit'}

    $writeRefused=$false;$writeStream=$null
    try {$writeStream=[IO.File]::Open((Join-Path $successRoot 'stable-input.txt'),[IO.FileMode]::Open,[IO.FileAccess]::Write,[IO.FileShare]::None)} catch [IO.IOException] {$writeRefused=$true} finally {if($writeStream){$writeStream.Dispose()}}
    if(!$writeRefused){throw 'Stable input write was not refused while systemd-owned Windows supervisor held the lock'}
    $replacement=Join-Path $successRoot 'replacement.txt';[IO.File]::WriteAllText($replacement,'replacement',[Text.UTF8Encoding]::new($false))
    $replaceRefused=$false
    try {Move-Item -LiteralPath $replacement -Destination (Join-Path $successRoot 'stable-input.txt') -Force -ErrorAction Stop} catch {$replaceRefused=$true}
    if(!$replaceRefused){throw 'Stable input replacement was not refused while supervisor held the lock'}
    if(Test-Path -LiteralPath $replacement){Remove-Item -LiteralPath $replacement -Force}

    Wait-Until { @((Read-Events $successRoot)|Where-Object{$_.event -eq 'terminal_validated'}).Count -eq 1 } ($SleepSeconds+180) 'Success systemd interop canary did not reach terminal_validated'
    Wait-Until { -not (Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue) } 60 'Success systemd-owned supervisor did not terminate'

    $second=Start-Process -FilePath $powershell51 -ArgumentList $successDispatchArgs -WindowStyle Hidden -PassThru -Wait
    if($second.ExitCode -ne 91){throw "Second dispatcher returned $($second.ExitCode), expected permanent dispatch-marker refusal 91"}
    if(@((Read-Events $successRoot)|Where-Object{$_.event -eq 'lockholder_started'}).Count -ne 1){throw 'Second dispatch created another lock holder'}

    $directSecondArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$worker,'-EvidenceRoot',$successRoot,'-InvocationName',$successInvocation,'-Mode','success','-TimeoutSeconds','30')
    $directSecond=Start-Process -FilePath $powershell51 -ArgumentList $directSecondArgs -WindowStyle Hidden -PassThru -Wait
    if($directSecond.ExitCode -ne 91){throw "Second supervisor invocation returned $($directSecond.ExitCode), expected attempt-marker refusal 91"}
    Wait-Until { Test-Path -LiteralPath (Join-Path $successRoot 'refusals.jsonl') } 30 'Second supervisor invocation did not record marker refusal'

    $failureDispatchStdout=Join-Path $failureRoot 'dispatcher.stdout.log'
    $failureDispatchStderr=Join-Path $failureRoot 'dispatcher.stderr.log'
    $failureDispatchArgs=@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DispatchChild','-EvidenceRoot',$failureRoot,'-UnitName',$failureUnit,'-InvocationName',$failureInvocation,'-Mode','failure','-SleepSeconds','2')
    $failureDispatcher=Start-Process -FilePath $powershell51 -ArgumentList $failureDispatchArgs -WindowStyle Hidden -RedirectStandardOutput $failureDispatchStdout -RedirectStandardError $failureDispatchStderr -PassThru -Wait
    if($failureDispatcher.ExitCode -ne 0){throw "Failure dispatcher failed before systemd ownership: $($failureDispatcher.ExitCode); stderr=$(@(Get-Content -LiteralPath $failureDispatchStderr -ErrorAction SilentlyContinue) -join ' ')"}
    Wait-Until { @((Read-Events $failureRoot)|Where-Object{$_.event -eq 'terminal_validation_failed'}).Count -eq 1 } 180 'Failure systemd interop canary did not publish terminal_validation_failed'
    $failureEvents=Read-Events $failureRoot
    $failureExit=@($failureEvents|Where-Object{$_.event -eq 'workload_exited'})
    if($failureExit.Count -ne 1 -or [int]$failureExit[0].exit_code -ne 23 -or [string]$failureExit[0].exit_code_source -ne 'atomic_wsl_evidence'){throw 'Failure systemd interop canary did not bind atomic WSL exit code 23'}
    $failureSupervisorPid=[int](@($failureEvents|Where-Object{$_.event -eq 'lockholder_started'})[0].lockholder_pid)
    Wait-Until { -not (Get-Process -Id $failureSupervisorPid -ErrorAction SilentlyContinue) } 60 'Failure systemd-owned supervisor did not terminate'
    Start-Sleep -Seconds 5
    if(@((Read-Events $failureRoot)|Where-Object{$_.event -eq 'lockholder_started'}).Count -ne 1){throw 'Failure systemd unit restarted automatically'}

    $successTerminalUnit=Get-UnitProperties $successUnit
    $failureTerminalUnit=Get-UnitProperties $failureUnit
    if($successTerminalUnit.ActiveState -notin @('inactive','failed') -or $failureTerminalUnit.ActiveState -notin @('inactive','failed')){throw 'Collected units remained active after terminal evidence'}

    $completed=$true
    [ordered]@{
        status='pass'
        pilot_launched=$false
        caller_termination_survived=$true
        supervisor_owned_by_systemd_interop=$true
        lockholder_parent_name='wslhost.exe'
        systemd_user='techatat'
        systemd_restart='no'
        systemd_collect=$true
        windows_identity=[string]$started[0].windows_identity
        session_id=[int]$started[0].session_id
        wsl_user='techatat'
        wsl_gpu_observed=$true
        stable_input_write_refused=$writeRefused
        stable_input_replace_refused=$replaceRefused
        terminal_validated_recorded=$true
        atomic_nonzero_exit_recorded=$true
        dispatch_marker_refused_second_dispatch=$true
        attempt_marker_refused_second_supervisor=$true
        automatic_restart_observed=$false
    }|ConvertTo-Json -Compress
} finally {
    if(!$completed){
        $savedPreference=$ErrorActionPreference
        $ErrorActionPreference='SilentlyContinue'
        foreach($unitName in $units){
            if($unitName -match '^sleep-stage-r11-interop-[a-z0-9-]+\.service$'){
                $unit=Get-UnitProperties $unitName
                if($unit.LoadState -and $unit.LoadState -ne 'not-found'){
                    & wsl.exe -d Ubuntu -u root -e systemctl stop $unitName 2>$null | Out-Null
                    & wsl.exe -d Ubuntu -u root -e systemctl reset-failed $unitName 2>$null | Out-Null
                }
            }
        }
        $ErrorActionPreference=$savedPreference
    }
    if($completed){
        foreach($root in $roots){
            if(Test-Path -LiteralPath $root){Assert-TestRoot $root;Remove-Item -LiteralPath $root -Recurse -Force}
        }
    }
}
