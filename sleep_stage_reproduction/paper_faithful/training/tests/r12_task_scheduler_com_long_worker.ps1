param(
    [Parameter(Mandatory=$true)][string]$EvidenceRoot,
    [Parameter(Mandatory=$true)][string]$InvocationName,
    [ValidateSet('success','failure')][string]$Mode='success',
    [ValidateRange(2,300)][int]$SleepSeconds=210,
    [string]$Distro='Ubuntu'
)

$ErrorActionPreference='Stop'
$marker=Join-Path $EvidenceRoot 'attempt.lock'
$input=Join-Path $EvidenceRoot 'stable-input.txt'
$lifecycle=Join-Path $EvidenceRoot 'lifecycle.jsonl'
$refusals=Join-Path $EvidenceRoot 'refusals.jsonl'
$childStdout=Join-Path $EvidenceRoot 'wsl-child.stdout.log'
$childExitEvidence=Join-Path $EvidenceRoot 'wsl-child.exit-code.txt'
$heartbeats=Join-Path $EvidenceRoot 'wsl-child.heartbeats.jsonl'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$childScript='./paper_faithful/training/tests/r12_task_scheduler_com_long_child.sh'
$markerStream=$null
$inputStream=$null
$child=$null

function Write-JsonLine([string]$Path,[hashtable]$Event) {
    $Event.timestamp=(Get-Date).ToString('o')
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Event|ConvertTo-Json -Compress -Depth 8)+[Environment]::NewLine)
    for($attempt=1;$attempt -le 50;$attempt++) {
        $stream=$null
        try {
            $stream=[IO.File]::Open($Path,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::Read)
            $stream.Write($bytes,0,$bytes.Length)
            $stream.Flush($true)
            return
        } catch [IO.IOException] {
            if($attempt -eq 50){throw}
            Start-Sleep -Milliseconds 100
        } finally {
            if($null -ne $stream){$stream.Dispose()}
        }
    }
}

function Convert-ToWslPath([string]$WindowsPath) {
    $full=[IO.Path]::GetFullPath($WindowsPath)
    if($full -notmatch '^([A-Za-z]):\\(.*)$'){throw "Unsupported Windows path for WSL conversion: $WindowsPath"}
    return '/mnt/'+$Matches[1].ToLowerInvariant()+'/'+$Matches[2].Replace('\','/')
}

function Write-Step([string]$Name) {
    [IO.File]::WriteAllText((Join-Path $EvidenceRoot $Name),(Get-Date).ToString('o'),[Text.UTF8Encoding]::new($false))
}

function Get-Heartbeat([string]$Path) {
    if(!(Test-Path -LiteralPath $Path)){return $null}
    try {
        $lines=@(Get-Content -LiteralPath $Path -Tail 1 -ErrorAction Stop)
        if($lines.Count -ne 1){return $null}
        $line=[string]$lines[0]
        if([string]::IsNullOrWhiteSpace($line)){return $null}
        $parsed=$line|ConvertFrom-Json -ErrorAction Stop
        if([string]$parsed.event -ne 'heartbeat' -or [string]::IsNullOrWhiteSpace([string]$parsed.boot_id)){return $null}
        return $parsed
    } catch { return $null }
}

try {
    try {$markerStream=[IO.File]::Open($marker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
    catch [IO.IOException] { Write-JsonLine $refusals @{event='marker_collision_refused';invocation_name=$InvocationName;supervisor_pid=$PID}; exit 91 }
    Write-Step 'step-1-attempt-marker-created.txt'

    $self=Get-Process -Id $PID -ErrorAction Stop
    Write-JsonLine $lifecycle @{event='supervisor_started';invocation_name=$InvocationName;supervisor_pid=$PID;windows_identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name;session_id=[int]$self.SessionId;mode=$Mode;ownership_claim='task_scheduler_com'}
    Write-Step 'step-2-supervisor-handshake-written.txt'

    $inputStream=[IO.File]::Open($input,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    Write-JsonLine $lifecycle @{event='stable_input_locked';invocation_name=$InvocationName;supervisor_pid=$PID;input_path=$input}
    Write-Step 'step-3-stable-input-locked.txt'

    $requestedExitCode=$(if($Mode -eq 'success'){0}else{23})
    $wslEvidenceRoot=Convert-ToWslPath $EvidenceRoot
    $arguments=@('-d',$Distro,'-e','bash','--noprofile','--norc',$childScript,[string]$SleepSeconds,[string]$requestedExitCode,$wslEvidenceRoot)
    $child=Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe" -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
    Write-JsonLine $lifecycle @{event='process_started';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;child_kind='wsl'}

    $exitDeadline=(Get-Date).AddSeconds($SleepSeconds+120)
    $heartbeatDeadline=(Get-Date).AddSeconds(20)
    $initialBootId=$null;$atomicSeenAt=$null;$hostGoneAt=$null
    $lastValidHeartbeatReadAt=$null
    while((Get-Date) -lt $exitDeadline) {
        $now=Get-Date;$hostPresent=[bool](Get-Process -Id $child.Id -ErrorAction SilentlyContinue);$atomicPresent=Test-Path -LiteralPath $childExitEvidence
        if($atomicPresent -and $null-eq$atomicSeenAt){$atomicSeenAt=$now}
        if(-not$hostPresent -and $null-eq$hostGoneAt){$hostGoneAt=$now}
        if($atomicPresent -and -not$hostPresent){break}
        if(-not$atomicPresent){
            $heartbeat=Get-Heartbeat $heartbeats
            if($heartbeat) {
                $lastValidHeartbeatReadAt=$now
                if($null -eq $initialBootId){$initialBootId=[string]$heartbeat.boot_id}
                if([string]$heartbeat.boot_id -ne $initialBootId){throw 'WSL boot_id changed during child execution'}
                $age=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-[int64]$heartbeat.epoch_seconds
                if($age -gt 15){throw "WSL heartbeat stale for $age seconds"}
            } elseif($hostPresent) {
                if($null -eq $initialBootId -and $now-gt$heartbeatDeadline){throw 'WSL heartbeat evidence absent'}
                if($null-ne$lastValidHeartbeatReadAt -and $now-gt$lastValidHeartbeatReadAt.AddSeconds(15)){throw 'WSL heartbeat evidence unreadable for 15 seconds'}
            }
        }
        if($null-ne$hostGoneAt -and $now-gt$hostGoneAt.AddSeconds(60)){throw 'Atomic WSL exit evidence absent after Windows host exit'}
        if($null-ne$atomicSeenAt -and $now-gt$atomicSeenAt.AddSeconds(60)){throw 'Windows WSL host remained after atomic exit evidence'}
        Start-Sleep -Seconds 1
    }
    if($null -eq $initialBootId){throw 'WSL heartbeat evidence was never observed'}
    if(!(Test-Path -LiteralPath $childExitEvidence)){throw 'Atomic WSL exit-code evidence absent'}
    $exitText=(Get-Content -LiteralPath $childExitEvidence -Raw -ErrorAction Stop).Trim()
    $observedExitCode=0
    if(![int]::TryParse($exitText,[ref]$observedExitCode)){throw 'Atomic WSL exit-code evidence invalid'}
    if(Get-Process -Id $child.Id -ErrorAction SilentlyContinue){throw 'Windows WSL host did not exit before terminal barrier'}
    $child.Refresh();$windowsHostExited=$child.HasExited
    if(!$windowsHostExited){throw 'Windows WSL host absence could not be confirmed'}
    try {$windowsHostExitCode=[int]$child.ExitCode} catch {throw 'Windows WSL host exit code unavailable'}
    $wslOutput=@(Get-Content -LiteralPath $childStdout -ErrorAction Stop)
    $wslUserLine=@($wslOutput|Where-Object{$_ -like 'WSL_USER=*'}|Select-Object -First 1)
    $wslGpuLine=@($wslOutput|Where-Object{$_ -like 'WSL_GPU=*'}|Select-Object -First 1)
    $wslBootLine=@($wslOutput|Where-Object{$_ -like 'WSL_BOOT_ID=*'}|Select-Object -First 1)
    Write-JsonLine $lifecycle @{event='process_exited';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=$observedExitCode;exit_code_source='atomic_wsl_evidence';windows_host_exited=$windowsHostExited;windows_host_exit_code=$windowsHostExitCode;atomic_seen_at=$atomicSeenAt.ToString('o');windows_host_gone_at=$hostGoneAt.ToString('o');wsl_user_line=$(if($wslUserLine.Count){[string]$wslUserLine[0]}else{$null});wsl_gpu_line=$(if($wslGpuLine.Count){[string]$wslGpuLine[0]}else{$null});wsl_boot_id=$initialBootId}

    if($windowsHostExitCode-ne$observedExitCode){throw "Canary atomic/Windows host exit mismatch: atomic=$observedExitCode host=$windowsHostExitCode"}
    if($observedExitCode -ne 0){throw "Canary WSL child returned nonzero exit $observedExitCode"}
    if($wslUserLine.Count -ne 1 -or [string]$wslUserLine[0] -ne 'WSL_USER=techatat'){throw 'Unexpected WSL identity'}
    if($wslGpuLine.Count -ne 1){throw 'WSL GPU probe unavailable'}
    if($wslBootLine.Count -ne 1 -or [string]$wslBootLine[0] -ne ('WSL_BOOT_ID='+$initialBootId)){throw 'WSL boot_id identity evidence mismatched'}
    Write-JsonLine $lifecycle @{event='terminal_validated';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=$observedExitCode;boot_id=$initialBootId}
    exit 0
} catch {
    try {Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;supervisor_pid=$PID;reason=$_.Exception.Message}} catch {}
    if($Mode -eq 'failure'){exit 23}
    exit 92
} finally {
    if($null -ne $child) {
        try {
            $child.Refresh()
            if(!$child.HasExited) {
                $child.Kill()
                [void]$child.WaitForExit(10000)
            }
        } catch {}
    }
    if($null -ne $inputStream){$inputStream.Dispose()}
    if($null -ne $markerStream){$markerStream.Dispose()}
}
