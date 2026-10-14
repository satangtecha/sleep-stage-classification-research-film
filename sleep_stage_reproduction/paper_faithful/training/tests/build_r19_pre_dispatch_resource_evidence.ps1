param(
    [string]$LocalPath = (Join-Path $PSScriptRoot '..\r19_pre_dispatch_resource_evidence_20260905.json'),
    [string]$CanonicalPath = 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r19-pre-dispatch-resource-evidence-20260905.json'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\r19_exactly_once_helpers.ps1')

$prefix = 'paper-text-v1-multiseed-cap128-r19-20260905'
$children = @("$prefix-split42-model42", "$prefix-split43-model43")
$bulk = 'E:\blp\sleep_stage_reproduction'
$logs = Join-Path $bulk 'runtime\training-logs'
$runs = Join-Path $bulk 'runs'
$requiredFree = [ordered]@{ c_minimum_gib = 10.0; e_minimum_gib = 100.0 }
$thresholds = [ordered]@{
    available_physical_memory_mb_min = 2048.0
    commit_headroom_mb_min = 4096.0
    c_free_gib_min = $requiredFree.c_minimum_gib
    e_free_gib_min = $requiredFree.e_minimum_gib
    power_online_required = $true
    power_critical_forbidden = $true
    gpu_windows_compute_process_count_required = 0
    wsl_compute_process_count_required = 0
}

function Get-CounterValue([string]$Path) {
    $counter = Get-Counter -Counter $Path -ErrorAction Stop
    [double]$counter.CounterSamples[0].CookedValue
}

function Get-MemorySnapshot {
    $available = Get-CounterValue '\Memory\Available MBytes'
    $commitLimit = Get-CounterValue '\Memory\Commit Limit' / 1MB
    $committed = Get-CounterValue '\Memory\Committed Bytes' / 1MB
    [pscustomobject]@{
        available_physical_memory_mb = [Math]::Round($available, 1)
        commit_limit_mb = [Math]::Round($commitLimit, 1)
        committed_mb = [Math]::Round($committed, 1)
        commit_headroom_mb = [Math]::Round($commitLimit - $committed, 1)
    }
}

function Get-GpuIdentity {
    $nvidia = (Get-Command nvidia-smi.exe -ErrorAction Stop).Source
    $result = Invoke-R17BoundedProcess $nvidia @('--query-gpu=name,driver_version', '--format=csv,noheader') 30 'r19-pre-dispatch-windows-gpu'
    if ([int]$result.exit_code -ne 0) { throw 'r19 pre-dispatch Windows GPU identity probe failed' }
    $line = @([string]$result.stdout -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) | Select-Object -First 1
    if (-not $line -or $line -notmatch '^\s*(?<name>.+?),\s*(?<driver>[0-9.]+)\s*$') { throw 'r19 pre-dispatch Windows GPU identity output malformed' }
    [pscustomobject]@{ name = [string]$Matches.name.Trim(); driver_version = [string]$Matches.driver.Trim() }
}

function Assert-R19NamespaceAbsent {
    $paths = @(
        (Join-Path $logs "$prefix.dispatch.lock"),
        (Join-Path $logs "$prefix.launch.lock"),
        (Join-Path $logs "$prefix.dispatch.lifecycle.jsonl"),
        (Join-Path $logs "$prefix.dispatch.json"),
        (Join-Path $logs "$prefix.supervisor-preflight.jsonl"),
        (Join-Path $logs "$prefix.lifecycle.jsonl"),
        (Join-Path $logs "$prefix.wsl-host.stdout.log"),
        (Join-Path $logs "$prefix.wsl-host.stderr.log"),
        (Join-Path $logs "$prefix.workload-exit.json"),
        (Join-Path $logs "$prefix.supervisor-binding.json"),
        (Join-Path $logs "$prefix.supervisor-binding.lock"),
        (Join-Path $logs "$prefix.gpu-admission"),
        (Join-Path $logs "$prefix.gpu-admission-summary.json")
    ) + @($children | ForEach-Object { Join-Path $runs $_ })
    $present = @($paths | Where-Object { Test-Path -LiteralPath $_ })
    if ($present.Count) { throw "r19 pre-dispatch namespace collision: $($present -join '; ')" }
    $svc = New-Object -ComObject 'Schedule.Service'
    $svc.Connect()
    $folder = $svc.GetFolder('\')
    $tasks = @($folder.GetTasks(1) | Where-Object { $_.Name -match '^SleepStagePaper-r19-' })
    if ($tasks.Count) { throw "r19 Task Scheduler namespace collision: $((@($tasks | ForEach-Object { $_.Name })) -join ',')" }
    [pscustomobject]@{ paths = $paths; scheduled_tasks = @() }
}

$namespace = Assert-R19NamespaceAbsent
$power = Get-R17NativePowerStatus
$memory = Get-MemorySnapshot
$cFree = Get-R17NativeDriveFreeGiB 'C:\'
$eFree = Get-R17NativeDriveFreeGiB 'E:\'
$gpu = Get-GpuIdentity
$windowsGpu = Get-R17WindowsGpuProcessSnapshot 'r19-pre-dispatch-windows-gpu-compute'
# WDDM can report the Windows Desktop Window Manager as a pseudo compute app
# with [Insufficient Permissions]/[N/A] telemetry. It is display composition,
# not a training or CUDA workload; record it explicitly and reject everything
# else. WSL CUDA compute remains a strict empty-set gate below.
$windowsDisplayCompositor = @($windowsGpu.entries | Where-Object {
    [string]$_.process_name -eq '[Insufficient Permissions]' -and
    [string]$_.used_gpu_memory -eq '[N/A]'
})
$windowsCompute = @($windowsGpu.entries | Where-Object {
    -not (
        [string]$_.process_name -eq '[Insufficient Permissions]' -and
        [string]$_.used_gpu_memory -eq '[N/A]'
    )
})
if ($windowsCompute.Count) {
    throw "r19 GPU compute process collision at r19-pre-dispatch-windows-gpu-compute: $((@($windowsCompute | ForEach-Object { $_.pid })) -join ',')"
}
$wslGpu = Invoke-R17BoundedWslScript "nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d'" 30 'r19-pre-dispatch-wsl-gpu-compute'
$wslGpuPids = @([string]$wslGpu.stdout -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
Assert-R17GpuComputeProbeResult ([int]$wslGpu.exit_code) $wslGpuPids 'r19-pre-dispatch-wsl-gpu-compute'
$wslTraining = Invoke-R17BoundedWslScript "pgrep -af '[p]aper_faithful.training.cli (pilot|multi-seed-pilot)' || true" 30 'r19-pre-dispatch-wsl-training-collision'
if (-not [string]::IsNullOrWhiteSpace([string]$wslTraining.stdout)) { throw "r19 WSL training process collision: $($wslTraining.stdout.Trim())" }

$ready = $power.power_online -and -not $power.critical -and -not $power.unknown -and
    $memory.available_physical_memory_mb -ge $thresholds.available_physical_memory_mb_min -and
    $memory.commit_headroom_mb -ge $thresholds.commit_headroom_mb_min -and
    $cFree -ge $thresholds.c_free_gib_min -and $eFree -ge $thresholds.e_free_gib_min -and
    @($windowsCompute).Count -eq $thresholds.gpu_windows_compute_process_count_required -and
    $wslGpuPids.Count -eq $thresholds.wsl_compute_process_count_required

$artifact = [ordered]@{
    schema_version = 1
    artifact_type = 'r19_pre_dispatch_resource_evidence'
    status = if ($ready) { 'pass' } else { 'refused' }
    run_id_prefix = $prefix
    expected_children = $children
    power = [ordered]@{
        power_online = [bool]$power.power_online
        ac_line_status = [int]$power.ac_line_status
        battery_flag = [int]$power.battery_flag
        battery_percent = [int]$power.battery_percent
        critical = [bool]$power.critical
        unknown = [bool]$power.unknown
    }
    memory = $memory
    storage = [ordered]@{ c_free_gib = [Math]::Round($cFree, 3); e_free_gib = [Math]::Round($eFree, 3) }
    gpu = [ordered]@{
        name = $gpu.name
        nvidia_smi_driver_version = $gpu.driver_version
        windows_compute_process_pids = @($windowsCompute | ForEach-Object { [int]$_.pid })
        windows_display_compositor_pids = @($windowsDisplayCompositor | ForEach-Object { [int]$_.pid })
        wsl_compute_process_pids = @($wslGpuPids)
        windows_compute_process_count = @($windowsCompute).Count
        windows_display_compositor_count = @($windowsDisplayCompositor).Count
        wsl_compute_process_count = $wslGpuPids.Count
        wsl_training_processes = @()
    }
    namespace = [ordered]@{
        exact_r19_paths_absent = $true
        scheduled_r19_tasks = @($namespace.scheduled_tasks)
        windows_process_count = @([Diagnostics.Process]::GetProcesses()).Count
        wsl_training_processes_absent = $true
    }
    thresholds = $thresholds
    ready = [bool]$ready
    created_at = (Get-Date).ToString('o')
}

$bytes = [Text.UTF8Encoding]::new($false).GetBytes(($artifact | ConvertTo-Json -Compress -Depth 12) + [Environment]::NewLine)
foreach ($path in @($LocalPath, $CanonicalPath)) {
    if (Test-Path -LiteralPath $path) { throw "immutable r19 resource evidence exists: $path" }
    $full = [IO.Path]::GetFullPath($path)
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($full)) | Out-Null
    $stream = [IO.File]::Open($full, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
}
if (-not [Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($LocalPath), [IO.File]::ReadAllBytes($CanonicalPath))) { throw 'r19 resource evidence copies differ' }
if (-not $ready) { throw 'r19 pre-dispatch resource gate refused dispatch' }
[ordered]@{ status = 'pass'; local_path = [IO.Path]::GetFullPath($LocalPath); canonical_path = [IO.Path]::GetFullPath($CanonicalPath); sha256 = (Get-FileHash -LiteralPath $LocalPath -Algorithm SHA256).Hash.ToLowerInvariant(); ready = $true } | ConvertTo-Json -Compress
