param(
    [Parameter(Mandatory=$true)][string]$EvidenceRoot,
    [Parameter(Mandatory=$true)][string]$InvocationName,
    [ValidateSet('success','failure')][string]$Mode='success',
    [ValidateRange(2,60)][int]$SleepSeconds=12,
    [string]$Distro='Ubuntu'
)

$ErrorActionPreference='Stop'
$marker=Join-Path $EvidenceRoot 'attempt.lock'
$input=Join-Path $EvidenceRoot 'stable-input.txt'
$lifecycle=Join-Path $EvidenceRoot 'lifecycle.jsonl'
$refusals=Join-Path $EvidenceRoot 'refusals.jsonl'
$childStdout=Join-Path $EvidenceRoot 'wsl-child.stdout.log'
$childStderr=Join-Path $EvidenceRoot 'wsl-child.stderr.log'
$childExitEvidence=Join-Path $EvidenceRoot 'wsl-child.exit-code.txt'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$childScript='./paper_faithful/training/tests/r11_wmi_canary_child.sh'
$markerStream=$null
$inputStream=$null

function Write-JsonLine([string]$Path,[hashtable]$Event) {
    $Event.timestamp=(Get-Date).ToString('o')
    Add-Content -LiteralPath $Path -Value ($Event|ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}

function Write-Step([string]$Name) {
    [IO.File]::WriteAllText((Join-Path $EvidenceRoot $Name),(Get-Date).ToString('o'),[Text.UTF8Encoding]::new($false))
}

function Convert-ToWslPath([string]$WindowsPath) {
    $full=[IO.Path]::GetFullPath($WindowsPath)
    if($full -notmatch '^([A-Za-z]):\\(.*)$'){throw "Unsupported Windows path for WSL conversion: $WindowsPath"}
    return '/mnt/'+$Matches[1].ToLowerInvariant()+'/'+$Matches[2].Replace('\','/')
}

try {
    try {
        $markerStream=[IO.File]::Open($marker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    } catch [IO.IOException] {
        Write-JsonLine $refusals @{event='marker_collision_refused';invocation_name=$InvocationName;supervisor_pid=$PID}
        exit 91
    }
    Write-Step 'step-1-marker-created.txt'

    $inputStream=[IO.File]::Open($input,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    Write-Step 'step-2-input-locked.txt'

    $self=Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
    $parent=Get-CimInstance Win32_Process -Filter ("ProcessId="+$self.ParentProcessId) -ErrorAction SilentlyContinue
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
    Write-JsonLine $lifecycle @{
        event='supervisor_started'
        invocation_name=$InvocationName
        supervisor_pid=$PID
        supervisor_parent_pid=[int]$self.ParentProcessId
        supervisor_parent_name=$(if($parent){$parent.Name}else{$null})
        windows_identity=$identity
        session_id=[int]$self.SessionId
        mode=$Mode
    }
    Write-Step 'step-3-lifecycle-written.txt'

    $childExitCode=$(if($Mode -eq 'success'){0}else{23})
    $wslEvidenceRoot=Convert-ToWslPath $EvidenceRoot
    $arguments=@('-d',$Distro,'-e','bash','--noprofile','--norc',$childScript,[string]$SleepSeconds,[string]$childExitCode,$wslEvidenceRoot)
    $child=Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe" -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
    Write-JsonLine $lifecycle @{event='process_started';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;child_kind='wsl'}
    $exitDeadline=(Get-Date).AddSeconds($SleepSeconds+120)
    while(!(Test-Path -LiteralPath $childExitEvidence) -and (Get-Date) -lt $exitDeadline){
        if($child.HasExited){break}
        Start-Sleep -Milliseconds 200
        $child.Refresh()
    }
    if(!(Test-Path -LiteralPath $childExitEvidence)){
        if(!$child.HasExited){try{$child.Kill()}catch{}}
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=96;reason='atomic WSL exit-code evidence absent'}
        exit 96
    }
    $exitText=(Get-Content -LiteralPath $childExitEvidence -Raw).Trim()
    $observedExitCode=0
    if(![int]::TryParse($exitText,[ref]$observedExitCode)){
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=97;reason='atomic WSL exit-code evidence invalid'}
        exit 97
    }
    $windowsHostExited=$child.WaitForExit(10000)
    if($windowsHostExited){$child.Refresh()}
    $windowsHostExitCode=$(if($windowsHostExited){$child.ExitCode}else{$null})
    $wslOutput=@(Get-Content -LiteralPath $childStdout -ErrorAction SilentlyContinue)
    $wslUserLine=@($wslOutput|Where-Object{$_ -like 'WSL_USER=*'}|Select-Object -First 1)
    $wslGpuLine=@($wslOutput|Where-Object{$_ -match 'NVIDIA|RTX'}|Select-Object -First 1)
    Write-JsonLine $lifecycle @{
        event='process_exited'
        invocation_name=$InvocationName
        supervisor_pid=$PID
        child_pid=$child.Id
        exit_code=$observedExitCode
        exit_code_source='atomic_wsl_evidence'
        windows_host_exited=$windowsHostExited
        windows_host_exit_code=$windowsHostExitCode
        wsl_user_line=$(if($wslUserLine.Count){[string]$wslUserLine[0]}else{$null})
        wsl_gpu_line=$(if($wslGpuLine.Count){[string]$wslGpuLine[0]}else{$null})
    }

    if($observedExitCode -ne 0) {
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=$observedExitCode;reason='canary WSL child returned nonzero'}
        exit $observedExitCode
    }
    if($wslUserLine.Count -ne 1 -or [string]$wslUserLine[0] -ne 'WSL_USER=techatat') {
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=93;reason='unexpected WSL identity'}
        exit 93
    }
    if($wslGpuLine.Count -ne 1) {
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=94;reason='WSL GPU probe unavailable'}
        exit 94
    }

    Write-JsonLine $lifecycle @{event='terminal_validated';invocation_name=$InvocationName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=$observedExitCode}
    exit 0
} catch {
    try {Write-JsonLine $lifecycle @{event='supervisor_failed';invocation_name=$InvocationName;supervisor_pid=$PID;reason=$_.Exception.Message}} catch {}
    exit 92
} finally {
    if($null -ne $inputStream){$inputStream.Dispose()}
    if($null -ne $markerStream){$markerStream.Dispose()}
}
