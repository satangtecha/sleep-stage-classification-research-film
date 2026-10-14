param(
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = 'Stop'
$helperPath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\r14_exactly_once_helpers.ps1')).Path
$productionSupervisorPath = [IO.Path]::GetFullPath('E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-production-supervisor-v3.ps1')
$canarySourcePath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'r14_task_scheduler_bound_handshake_canary.ps1')).Path
$prefix = 'paper-text-v1-multiseed-cap128-r14-20260831'
$productionDispatchMarker = "E:\blp\sleep_stage_reproduction\runtime\training-logs\$prefix.dispatch.lock"
$productionAttemptMarker = "E:\blp\sleep_stage_reproduction\runtime\training-logs\$prefix.launch.lock"
$caseId = [Guid]::NewGuid().ToString('N')
$taskName = "SleepStagePaper-r14-Canary-$caseId"
$productionTaskName = "SleepStagePaper-r14-COM-$caseId"
$stagedCanaryRoot = Join-Path 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-production-action-canary-staged' $caseId
$canaryPath = Join-Path $stagedCanaryRoot 'r14_task_scheduler_bound_handshake_canary.ps1'
$gateSha = 'a' * 64
$confirmationSha = 'b' * 64
$root = Join-Path 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-production-action-canaries' $taskName
$handshakePath = Join-Path $root 'handshake.json'
$resultPath = Join-Path $root 'result.json'
$controlPath = Join-Path $root 'test-control.json'
$registered = $false
$instance = $null

function Read-StableJson([string]$Path, [datetime]$Deadline) {
    do {
        $stream = $null
        try {
            $stream = [IO.File]::Open([IO.Path]::GetFullPath($Path), [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
            $memory = New-Object IO.MemoryStream
            try { $stream.CopyTo($memory); $bytes = $memory.ToArray() }
            finally { $memory.Dispose() }
            $text = [Text.UTF8Encoding]::new($false, $true).GetString($bytes)
            return ($text | ConvertFrom-Json -ErrorAction Stop)
        }
        catch [IO.IOException] {
            Start-Sleep -Milliseconds 100
        }
        finally {
            if ($null -ne $stream) { $stream.Dispose() }
        }
    } while ((Get-Date) -lt $Deadline)
    throw 'r14 canary handshake never became stably readable'
}

if ((Test-Path -LiteralPath $productionDispatchMarker) -or (Test-Path -LiteralPath $productionAttemptMarker)) { throw 'r14 production marker exists before non-training action smoke' }
. $helperPath

New-Item -ItemType Directory -Path $stagedCanaryRoot -Force | Out-Null
if (Test-Path -LiteralPath $canaryPath) { throw 'r14 staged canary path already exists' }
$canaryBytes = [IO.File]::ReadAllBytes($canarySourcePath)
$canaryStream = [IO.File]::Open($canaryPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $canaryStream.Write($canaryBytes, 0, $canaryBytes.Length); $canaryStream.Flush($true) }
finally { $canaryStream.Dispose() }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $canarySourcePath).Hash -ne (Get-FileHash -Algorithm SHA256 -LiteralPath $canaryPath).Hash) { throw 'r14 staged canary is not byte-identical to its source' }

$gateLockShape = [pscustomobject]@{ stream = 'fake-stream'; sha256 = $gateSha; text = ('gate-json-' * 4096) }
$confirmationLockShape = [pscustomobject]@{ stream = 'fake-stream'; sha256 = $confirmationSha; text = ('confirmation-json-' * 4096) }
$gateShaScalar = [string]$gateLockShape.sha256
$confirmationShaScalar = [string]$confirmationLockShape.sha256
$canaryArguments = New-R14SupervisorActionArguments $canaryPath $gateShaScalar $confirmationShaScalar $taskName
$productionArguments = New-R14SupervisorActionArguments $productionSupervisorPath $gateShaScalar $confirmationShaScalar $productionTaskName
Assert-R14SupervisorActionArguments $canaryArguments $canaryPath $gateShaScalar $confirmationShaScalar $taskName | Out-Null
Assert-R14SupervisorActionArguments $productionArguments $productionSupervisorPath $gateShaScalar $confirmationShaScalar $productionTaskName | Out-Null
if ($canaryArguments.Length -lt $productionArguments.Length) { throw 'r14 canary action is shorter than the production action' }

$badArguments = "-NoProfile -File `"$canaryPath`" -ExpectedCanonicalGateSha256 $gateLockShape.sha256 -ExpectedUserConfirmationSha256 $confirmationLockShape.sha256 -TaskName $taskName"
$negativeRefused = $false
try { Assert-R14SupervisorActionArguments $badArguments $canaryPath $gateShaScalar $confirmationShaScalar $taskName | Out-Null }
catch { $negativeRefused = $true }
if (-not $negativeRefused) { throw 'r14 serialized-object action was not refused' }

New-Item -ItemType Directory -Path $root -Force | Out-Null
[IO.File]::WriteAllText($controlPath, ([ordered]@{ task_name = $taskName; canary_path = $canaryPath; action_arguments = $canaryArguments; action_arguments_length = $canaryArguments.Length; created_at = (Get-Date).ToString('o') } | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))

$service = New-Object -ComObject 'Schedule.Service'
$service.Connect()
$folder = $service.GetFolder('\')
if (@($folder.GetTasks(1) | Where-Object { $_.Name -eq $taskName }).Count) { throw 'r14 canary task namespace collision' }

try {
    $definition = $service.NewTask(0)
    $definition.RegistrationInfo.Description = 'r14 production-shape bound-handshake canary; no training'
    $definition.Principal.UserId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $definition.Principal.LogonType = 3
    $definition.Settings.MultipleInstances = 2
    $definition.Settings.RestartCount = 0
    $definition.Settings.ExecutionTimeLimit = 'PT0S'
    $definition.Settings.AllowDemandStart = $true
    $action = $definition.Actions.Create(0)
    $action.Path = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $action.Arguments = $canaryArguments
    $action.WorkingDirectory = (Split-Path -Parent $canaryPath)
    if ([string]$definition.Actions.Item(1).Arguments -cne $canaryArguments) { throw 'r14 canary TaskDefinition action changed before registration' }

    $task = $folder.RegisterTaskDefinition($taskName, $definition, 2, $null, $null, 3, $null)
    $registered = $true
    if ([string]$task.Definition.Actions.Item(1).Arguments -cne $canaryArguments) { throw 'r14 persisted canary action arguments changed' }
    $instance = $task.RunEx($null, 0, 0, $null)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-Path -LiteralPath $handshakePath) { break }
        $current = $folder.GetTask($taskName)
        if ([int]$current.State -ne 4 -and [int]$current.LastTaskResult -lt 0) {
            $unsigned = [uint32]([int64]$current.LastTaskResult -band 0xffffffffL)
            throw "r14 canary Task Scheduler action failed: 0x$('{0:X8}' -f $unsigned)"
        }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    if (-not (Test-Path -LiteralPath $handshakePath)) { throw 'r14 production-shape canary did not publish its bound handshake' }

    $handshake = Read-StableJson $handshakePath $deadline
    if ($handshake.status -ne 'bound_handshake' -or $handshake.pilot_launched -ne $false -or $handshake.task_name -ne $taskName -or $handshake.canonical_gate_sha256 -ne $gateSha -or $handshake.user_confirmation_sha256 -ne $confirmationSha -or $handshake.parent_process -ne 'svchost.exe') { throw 'r14 canary handshake binding failed' }
    if (@(Get-Content -LiteralPath $handshakePath | ForEach-Object { $_ | ConvertFrom-Json }).Count -ne 1) { throw 'r14 canary handshake is not singular' }

    $result = [ordered]@{
        schema_version = 1
        status = 'pass'
        pilot_launched = $false
        case_id = $caseId
        task_name = $taskName
        instance_guid = [string]$instance.InstanceGuid
        helper_path = $helperPath
        canary_source_path = $canarySourcePath
        canary_path = $canaryPath
        canary_source_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $canarySourcePath).Hash.ToLowerInvariant()
        canary_staged_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $canaryPath).Hash.ToLowerInvariant()
        production_supervisor_path = $productionSupervisorPath
        canary_arguments_length = $canaryArguments.Length
        production_arguments_length = $productionArguments.Length
        persisted_arguments_exact = $true
        scalar_gate_sha_exactly_once = ([regex]::Matches($canaryArguments, $gateSha).Count -eq 1)
        scalar_confirmation_sha_exactly_once = ([regex]::Matches($canaryArguments, $confirmationSha).Count -eq 1)
        serialized_object_refused = $negativeRefused
        bound_handshake_validated = $true
        task_scheduler_parent = 'svchost.exe'
        production_markers_created = $false
        timestamp = (Get-Date).ToString('o')
    }
    [IO.File]::WriteAllText($resultPath, ($result | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    $result | ConvertTo-Json -Compress
}
finally {
    if ($null -ne $instance) { try { if ([int]$instance.State -eq 4) { $instance.Stop() } } catch {} }
    if ($registered) { try { $folder.DeleteTask($taskName, 0) } catch {} }
    if ((Test-Path -LiteralPath $productionDispatchMarker) -or (Test-Path -LiteralPath $productionAttemptMarker)) { throw 'r14 production marker appeared during non-training action smoke' }
}
