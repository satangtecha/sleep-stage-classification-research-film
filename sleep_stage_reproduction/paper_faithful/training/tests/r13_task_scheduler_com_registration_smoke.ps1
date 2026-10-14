param(
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
$caseId = [Guid]::NewGuid().ToString('N')
$taskName = "SleepStagePaper-R13-TaskDef-Canary-$caseId"
$root = Join-Path 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r13-taskdef-registration-canaries' $caseId
$sentinel = Join-Path $root 'completed.txt'
$task = $null
$instance = $null
$registered = $false

New-Item -ItemType Directory -Path $root -Force | Out-Null
$service = New-Object -ComObject 'Schedule.Service'
$service.Connect()
$folder = $service.GetFolder('\')

try {
    $definition = $service.NewTask(0)
    $definition.RegistrationInfo.Description = 'r13 exact TaskDefinition non-training registration canary'
    $definition.Principal.UserId = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $definition.Principal.LogonType = 3
    $definition.Settings.MultipleInstances = 2
    $definition.Settings.RestartCount = 0
    $definition.Settings.ExecutionTimeLimit = 'PT0S'
    $definition.Settings.AllowDemandStart = $true

    $escapedSentinel = $sentinel.Replace("'", "''")
    $action = $definition.Actions.Create(0)
    $action.Path = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $command = "[IO.File]::WriteAllText('$escapedSentinel','ok'); exit 0"
    $action.Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "' + $command.Replace('"', '\"') + '"'
    $action.WorkingDirectory = $root

    $xml = [xml]$definition.XmlText
    if ($definition.Settings.AllowDemandStart -ne $true) { throw 'AllowDemandStart pre-registration mismatch' }
    if ([int]$definition.Settings.MultipleInstances -ne 2 -or [int]$definition.Settings.RestartCount -ne 0 -or $definition.Settings.ExecutionTimeLimit -ne 'PT0S') { throw 'TaskDefinition pre-registration policy mismatch' }
    if (@($xml.Task.Triggers.ChildNodes | Where-Object { $_.NodeType -eq [Xml.XmlNodeType]::Element }).Count -ne 0) { throw 'TaskDefinition unexpectedly contains a trigger' }

    $task = $folder.RegisterTaskDefinition($taskName, $definition, 2, $null, $null, 3, $null)
    $registered = $true
    $persisted = $task.Definition
    if ($persisted.Settings.AllowDemandStart -ne $true) { throw 'Persisted AllowDemandStart mismatch' }
    if ([int]$persisted.Settings.MultipleInstances -ne 2 -or [int]$persisted.Settings.RestartCount -ne 0 -or $persisted.Settings.ExecutionTimeLimit -ne 'PT0S') { throw 'Persisted TaskDefinition policy mismatch' }
    if (@($persisted.Triggers).Count -ne 0) { throw 'Persisted TaskDefinition unexpectedly contains a trigger' }
    [IO.File]::WriteAllText((Join-Path $root 'task-definition.xml'), [string]$persisted.XmlText, [Text.UTF8Encoding]::new($false))

    $instance = $task.RunEx($null, 0, 0, $null)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if (Test-Path -LiteralPath $sentinel) { break }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    if (-not (Test-Path -LiteralPath $sentinel)) { throw 'Harmless Task Scheduler action did not publish its sentinel' }
    $sentinelText = (Get-Content -LiteralPath $sentinel -Raw).Trim()
    if ($sentinelText -ne 'ok') { throw 'Harmless Task Scheduler sentinel content mismatch' }

    $result = [ordered]@{
        status = 'pass'
        pilot_launched = $false
        task_name = $taskName
        task_registered = $true
        task_runex_requested = $true
        instance_guid = [string]$instance.InstanceGuid
        allow_demand_start = $true
        multiple_instances = 'IgnoreNew'
        restart_count = 0
        execution_time_limit = 'PT0S'
        trigger_count = 0
        sentinel_path = $sentinel
        task_definition_xml_path = (Join-Path $root 'task-definition.xml')
    }
    $resultJson = $result | ConvertTo-Json -Compress
    [IO.File]::WriteAllText((Join-Path $root 'result.json'), $resultJson, [Text.UTF8Encoding]::new($false))
    $resultJson
}
finally {
    if ($null -ne $instance) {
        try { if ([int]$instance.State -eq 4) { $instance.Stop() } } catch {}
    }
    if ($registered) {
        try { $folder.DeleteTask($taskName, 0) } catch {}
    }
}
