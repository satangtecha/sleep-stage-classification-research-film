param(
    [Parameter(Mandatory=$true)][string]$EvidenceRoot,
    [Parameter(Mandatory=$true)][string]$InvocationName,
    [ValidateSet('success','failure')][string]$Mode='success',
    [ValidateRange(30,600)][int]$TimeoutSeconds=180
)

$ErrorActionPreference='Stop'
$marker=Join-Path $EvidenceRoot 'attempt.lock'
$input=Join-Path $EvidenceRoot 'stable-input.txt'
$lifecycle=Join-Path $EvidenceRoot 'lifecycle.jsonl'
$refusals=Join-Path $EvidenceRoot 'refusals.jsonl'
$ready=Join-Path $EvidenceRoot 'lockholder-ready.json'
$childStdout=Join-Path $EvidenceRoot 'wsl-child.stdout.log'
$childExitEvidence=Join-Path $EvidenceRoot 'wsl-child.exit-code.txt'
$markerStream=$null
$inputStream=$null

function Write-JsonLine([string]$Path,[hashtable]$Event) {
    $Event.timestamp=(Get-Date).ToString('o')
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Event|ConvertTo-Json -Compress -Depth 8)+[Environment]::NewLine)
    for($attempt=1;$attempt -le 50;$attempt++){
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

try {
    try {
        $markerStream=[IO.File]::Open($marker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    } catch [IO.IOException] {
        Write-JsonLine $refusals @{event='marker_collision_refused';invocation_name=$InvocationName;lockholder_pid=$PID}
        exit 91
    }
    $inputStream=[IO.File]::Open($input,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    $self=Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
    $parent=Get-CimInstance Win32_Process -Filter ("ProcessId="+$self.ParentProcessId) -ErrorAction SilentlyContinue
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
    Write-JsonLine $lifecycle @{
        event='lockholder_started'
        invocation_name=$InvocationName
        lockholder_pid=$PID
        lockholder_parent_pid=[int]$self.ParentProcessId
        lockholder_parent_name=$(if($parent){$parent.Name}else{$null})
        windows_identity=$identity
        session_id=[int]$self.SessionId
        mode=$Mode
    }
    $readyTemp=$ready+'.tmp'
    [IO.File]::WriteAllText($readyTemp,(@{status='ready';invocation_name=$InvocationName;lockholder_pid=$PID;timestamp=(Get-Date).ToString('o')}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $readyTemp -Destination $ready -ErrorAction Stop
    Write-JsonLine $lifecycle @{event='stable_locks_ready';invocation_name=$InvocationName;lockholder_pid=$PID}

    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    while(!(Test-Path -LiteralPath $childExitEvidence) -and (Get-Date) -lt $deadline){Start-Sleep -Milliseconds 200}
    if(!(Test-Path -LiteralPath $childExitEvidence)){
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;lockholder_pid=$PID;exit_code=96;reason='atomic WSL exit-code evidence absent'}
        exit 96
    }
    $exitText=(Get-Content -LiteralPath $childExitEvidence -Raw).Trim()
    $observedExitCode=0
    if(![int]::TryParse($exitText,[ref]$observedExitCode)){
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;lockholder_pid=$PID;exit_code=97;reason='atomic WSL exit-code evidence invalid'}
        exit 97
    }
    $wslOutput=@(Get-Content -LiteralPath $childStdout -ErrorAction SilentlyContinue)
    $wslUserLine=@($wslOutput|Where-Object{$_ -like 'WSL_USER=*'}|Select-Object -First 1)
    $wslGpuLine=@($wslOutput|Where-Object{$_ -match 'NVIDIA|RTX'}|Select-Object -First 1)
    Write-JsonLine $lifecycle @{
        event='workload_exited'
        invocation_name=$InvocationName
        lockholder_pid=$PID
        exit_code=$observedExitCode
        exit_code_source='atomic_wsl_evidence'
        wsl_user_line=$(if($wslUserLine.Count){[string]$wslUserLine[0]}else{$null})
        wsl_gpu_line=$(if($wslGpuLine.Count){[string]$wslGpuLine[0]}else{$null})
    }
    if($observedExitCode -ne 0){
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;lockholder_pid=$PID;exit_code=$observedExitCode;reason='canary systemd workload returned nonzero'}
        exit $observedExitCode
    }
    if($wslUserLine.Count -ne 1 -or [string]$wslUserLine[0] -ne 'WSL_USER=techatat'){
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;lockholder_pid=$PID;exit_code=93;reason='unexpected WSL identity'}
        exit 93
    }
    if($wslGpuLine.Count -ne 1){
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';invocation_name=$InvocationName;lockholder_pid=$PID;exit_code=94;reason='WSL GPU probe unavailable'}
        exit 94
    }
    Write-JsonLine $lifecycle @{event='terminal_validated';invocation_name=$InvocationName;lockholder_pid=$PID;exit_code=0}
    exit 0
} catch {
    try {Write-JsonLine $lifecycle @{event='lockholder_failed';invocation_name=$InvocationName;lockholder_pid=$PID;reason=$_.Exception.Message}} catch {}
    exit 92
} finally {
    if($null -ne $inputStream){$inputStream.Dispose()}
    if($null -ne $markerStream){$markerStream.Dispose()}
}
