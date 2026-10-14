param(
    [string]$LauncherPath = (Join-Path $PSScriptRoot '..\launch_paper_text_pilot_r8.ps1')
)

$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath), [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw 'r8 launcher does not parse' }
$powerFunction = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-StableAcPowerFacts' }, $true)
if (-not $powerFunction) { throw 'r8 launcher has no stable-AC power gate' }

function Get-CimInstance {
    param([string]$Namespace, [string]$ClassName)
    if ($ClassName -eq 'BatteryStatus') {
        switch ($script:Scenario) {
            'missing' { return @() }
            'inactive' { return [pscustomobject]@{ InstanceName = 'BAT0'; Active = $false; PowerOnline = $true; Critical = $false; RemainingCapacity = 80 } }
            'offline' { return [pscustomobject]@{ InstanceName = 'BAT0'; Active = $true; PowerOnline = $false; Critical = $false; RemainingCapacity = 80 } }
            'critical' { return [pscustomobject]@{ InstanceName = 'BAT0'; Active = $true; PowerOnline = $true; Critical = $true; RemainingCapacity = 80 } }
            default { return [pscustomobject]@{ InstanceName = 'BAT0'; Active = $true; PowerOnline = $true; Critical = $false; RemainingCapacity = 80 } }
        }
    }
    if ($ClassName -eq 'Win32_Battery') {
        if ($script:Scenario -eq 'win32missing') { return @() }
        if ($script:Scenario -eq 'win32discharging') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 1; EstimatedChargeRemaining = 80 } }
        if ($script:Scenario -eq 'win32low') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 4; EstimatedChargeRemaining = 10 } }
        if ($script:Scenario -eq 'win32critical') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 5; EstimatedChargeRemaining = 80 } }
        if ($script:Scenario -eq 'win32chargingcritical') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 9; EstimatedChargeRemaining = 1 } }
        if ($script:Scenario -eq 'win32undefined') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 10; EstimatedChargeRemaining = 80 } }
        if ($script:Scenario -eq 'win32unexpected') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 99; EstimatedChargeRemaining = 80 } }
        if ($script:Scenario -eq 'win32statusmissing') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = $null; EstimatedChargeRemaining = 80 } }
        if ($script:Scenario -eq 'win32chargemissing') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 2; EstimatedChargeRemaining = $null } }
        if ($script:Scenario -eq 'win32zerocharge') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 2; EstimatedChargeRemaining = 0 } }
        if ($script:Scenario -match '^validstatus(?<Code>\d+)$') { return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = [int]$Matches.Code; EstimatedChargeRemaining = 80 } }
        return [pscustomobject]@{ DeviceID = 'BAT0'; BatteryStatus = 2; EstimatedChargeRemaining = 80 }
    }
    throw "Unexpected CIM class: $ClassName"
}

Invoke-Expression $powerFunction.Extent.Text

$refusedCases = @('missing', 'inactive', 'offline', 'critical', 'win32missing', 'win32discharging', 'win32low', 'win32critical', 'win32chargingcritical', 'win32undefined', 'win32unexpected', 'win32statusmissing', 'win32chargemissing', 'win32zerocharge')
foreach ($case in $refusedCases) {
    $script:Scenario = $case
    $refused = $false
    try { Get-StableAcPowerFacts | Out-Null } catch { $refused = $true }
    if (-not $refused) { throw "Power gate accepted $case power" }
}
$acceptedStatuses = @(2, 3, 6, 7, 8, 11)
foreach ($status in $acceptedStatuses) {
    $script:Scenario = "validstatus$status"
    $facts = Get-StableAcPowerFacts
    if ($facts.battery_status.Count -ne 1 -or $facts.battery_status[0].power_online -ne $true -or $facts.battery_status[0].critical -ne $false -or $facts.win32_battery.Count -ne 1 -or $facts.win32_battery[0].estimated_charge_remaining -ne 80 -or $facts.win32_battery[0].battery_status -ne $status) { throw "Power gate did not capture accepted AC-compatible status $status facts" }
}

[pscustomobject]@{ status = 'pass'; refused = $refusedCases; accepted_battery_statuses = $acceptedStatuses; pilot_launched = $false } | ConvertTo-Json -Compress
