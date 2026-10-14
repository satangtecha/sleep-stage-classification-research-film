param(
    [Parameter(Mandatory=$true)][string]$EvidenceRoot,
    [Parameter(Mandatory=$true)][string]$TaskName,
    [ValidateSet('success','failure')][string]$Mode='success',
    [ValidateRange(2,60)][int]$SleepSeconds=12
)

$ErrorActionPreference='Stop'
$marker=Join-Path $EvidenceRoot 'attempt.lock'
$input=Join-Path $EvidenceRoot 'stable-input.txt'
$lifecycle=Join-Path $EvidenceRoot 'lifecycle.jsonl'
$refusals=Join-Path $EvidenceRoot 'refusals.jsonl'
$markerStream=$null
$inputStream=$null

function Write-JsonLine([string]$Path,[hashtable]$Event) {
    $Event.timestamp=(Get-Date).ToString('o')
    Add-Content -LiteralPath $Path -Value ($Event|ConvertTo-Json -Compress -Depth 8) -Encoding UTF8
}

function Write-Step([string]$Name) {
    [IO.File]::WriteAllText((Join-Path $EvidenceRoot $Name),(Get-Date).ToString('o'),[Text.UTF8Encoding]::new($false))
}

try {
    try {
        $markerStream=[IO.File]::Open($marker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    } catch [IO.IOException] {
        Write-JsonLine $refusals @{event='marker_collision_refused';task_name=$TaskName;supervisor_pid=$PID}
        exit 91
    }
    Write-Step 'step-1-marker-created.txt'

    $inputStream=[IO.File]::Open($input,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    Write-Step 'step-2-input-locked.txt'
    Write-JsonLine $lifecycle @{event='supervisor_started';task_name=$TaskName;supervisor_pid=$PID;mode=$Mode}
    Write-Step 'step-3-lifecycle-written.txt'

    $childExitCode=$(if($Mode -eq 'success'){0}else{23})
    $pingCount=$SleepSeconds+1
    $childCommand="ping.exe -n $pingCount 127.0.0.1 >nul & exit /b $childExitCode"
    $child=Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList @('/d','/s','/c',('"'+$childCommand+'"')) -WindowStyle Hidden -PassThru
    Write-JsonLine $lifecycle @{event='process_started';task_name=$TaskName;supervisor_pid=$PID;child_pid=$child.Id}
    $child.WaitForExit()
    $observedExitCode=$child.ExitCode
    Write-JsonLine $lifecycle @{event='process_exited';task_name=$TaskName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=$observedExitCode}

    if($observedExitCode -ne 0) {
        Write-JsonLine $lifecycle @{event='terminal_validation_failed';task_name=$TaskName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=$observedExitCode;reason='canary child returned nonzero'}
        exit $observedExitCode
    }

    Write-JsonLine $lifecycle @{event='terminal_validated';task_name=$TaskName;supervisor_pid=$PID;child_pid=$child.Id;exit_code=$observedExitCode}
    exit 0
} catch {
    try {Write-JsonLine $lifecycle @{event='supervisor_failed';task_name=$TaskName;supervisor_pid=$PID;reason=$_.Exception.Message}} catch {}
    exit 92
} finally {
    if($null -ne $inputStream){$inputStream.Dispose()}
    if($null -ne $markerStream){$markerStream.Dispose()}
}
