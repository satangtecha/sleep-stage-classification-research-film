param(
  [Parameter(Mandatory = $true)][string]$OutputPath,
  [int]$MinPhysicalMemoryMb = 4096,
  [int]$MinCommitHeadroomMb = 8192,
  [double]$MinCFreeGiB = 15.0,
  [double]$MinEFreeGiB = 15.0,
  [switch]$AllowOfflinePower
)

$ErrorActionPreference = 'Stop'
$output = [IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $output
if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
if (Test-Path -LiteralPath $output) { throw "resource evidence already exists: $output" }

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class SubjectPower {
  [StructLayout(LayoutKind.Sequential)]
  public struct STATUS { public byte ACLineStatus; public byte BatteryFlag; public byte BatteryLifePercent; public byte Reserved; public int BatteryLifeTime; public int BatteryFullLifeTime; }
  [DllImport("kernel32.dll")] public static extern bool GetSystemPowerStatus(out STATUS status);
}
'@

$os = Get-CimInstance Win32_OperatingSystem
$power = New-Object SubjectPower+STATUS
if (-not [SubjectPower]::GetSystemPowerStatus([ref]$power)) { throw 'GetSystemPowerStatus failed' }
$c = Get-PSDrive -Name C
$e = Get-PSDrive -Name E
$windowsGpu = & nvidia-smi.exe --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader,nounits 2>&1
$windowsGpuExit = $LASTEXITCODE
$wslGpu = & wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "nvidia-smi --query-compute-apps=pid,process_name,used_gpu_memory --format=csv,noheader,nounits" 2>&1
$wslGpuExit = $LASTEXITCODE
$windowsLines = @($windowsGpu | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
$wslLines = @($wslGpu | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
# WDDM display processes can appear as `process_name, [N/A]` while CUDA
# compute processes expose a numeric used-memory field.  Treat both the
# legacy insufficient-permissions form and the short N/A form as display-only;
# never claim GPU exclusivity from an unobservable numeric process.
$displayPattern = ',\s*(?:\[Insufficient Permissions\],\s*)?\[N/A\]\s*$'
$windowsDisplayLines = @($windowsLines | Where-Object { [string]$_ -match $displayPattern })
$windowsComputeLines = @($windowsLines | Where-Object { [string]$_ -notmatch $displayPattern })
$physicalMemoryMb = [math]::Round([double]$os.FreePhysicalMemory / 1024.0, 1)
$commitHeadroomMb = [math]::Round([double]$os.FreeVirtualMemory / 1024.0, 1)
$cFreeGiB = [math]::Round([double]$c.Free / 1GB, 3)
$eFreeGiB = [math]::Round([double]$e.Free / 1GB, 3)
$powerOnline = ([int]$power.ACLineStatus -eq 1)
$critical = ([int]$power.BatteryLifePercent -ge 0 -and [int]$power.BatteryLifePercent -le 5 -and -not $powerOnline)
$checks = [ordered]@{
  power_online = $powerOnline
  critical = $critical
  physical_memory_available_mb = $physicalMemoryMb
  commit_headroom_mb = $commitHeadroomMb
  c_free_gib = $cFreeGiB
  e_free_gib = $eFreeGiB
  windows_gpu_compute_process_count = $windowsComputeLines.Count
  wsl_gpu_compute_process_count = $wslLines.Count
  windows_gpu_probe_exit_code = [int]$windowsGpuExit
  wsl_gpu_probe_exit_code = [int]$wslGpuExit
  offline_power_authorized = [bool]$AllowOfflinePower
}
$powerGate = ($powerOnline -and -not $critical) -or ($AllowOfflinePower -and -not $powerOnline)
$ready = $powerGate -and $physicalMemoryMb -ge $MinPhysicalMemoryMb -and $commitHeadroomMb -ge $MinCommitHeadroomMb -and $cFreeGiB -ge $MinCFreeGiB -and $eFreeGiB -ge $MinEFreeGiB -and $windowsGpuExit -eq 0 -and $wslGpuExit -eq 0 -and $windowsComputeLines.Count -eq 0 -and $wslLines.Count -eq 0
$record = [ordered]@{
  schema_version = 1
  status = if ($ready) { 'pass' } else { 'refused' }
  ready = $ready
  protocol_id = 'SUBJECT_GENERALIZATION_V1'
  gate = 'subject-generalization-pre-dispatch-resource-v1'
  timestamp = (Get-Date).ToString('o')
  ac_line_status = [int]$power.ACLineStatus
  battery_life_percent = [int]$power.BatteryLifePercent
  battery_flag = [int]$power.BatteryFlag
  offline_power_authorized = [bool]$AllowOfflinePower
  process_count = @(Get-Process).Count
  thresholds = [ordered]@{ physical_memory_available_mb = $MinPhysicalMemoryMb; commit_headroom_mb = $MinCommitHeadroomMb; c_free_gib = $MinCFreeGiB; e_free_gib = $MinEFreeGiB }
  checks = $checks
  windows_gpu_lines = $windowsComputeLines
  windows_display_compositor_lines = $windowsDisplayLines
  wsl_gpu_lines = $wslLines
}
$json = $record | ConvertTo-Json -Depth 8 -Compress
$bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + "`n")
$stream = [IO.File]::Open($output, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
if (-not $ready) { exit 2 }
exit 0
