$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$helper = Join-Path $root 'paper_faithful\training\r18_exactly_once_helpers.ps1'
$supervisor = Join-Path $root 'paper_faithful\training\supervise_paper_text_multiseed_smoke_r18.ps1'
$runner = Join-Path $root 'paper_faithful\training\run_paper_text_multiseed_smoke_r18.sh'
$trainer = Join-Path $root 'paper_faithful\training\trainer.py'
. $helper

$prefix = 'paper-text-v1-multiseed-cap128-r18-20260902'
$runId = "$prefix-split42-model42"
$request = [pscustomobject][ordered]@{
    schema_version = 1
    design_id = 'R17_DEDICATED_HOST_OBSERVED_IDLE_GPU_ADMISSION_V1'
    run_id_prefix = $prefix
    run_id = $runId
    stage = 'stage1'
    nonce = '0123456789abcdef0123456789abcdef'
    linux_pid = 4242
    device = '/GPU:0'
    context_acquired = $true
}
$baseline = [pscustomobject]@{pids=@(2140)}
$admitted = [pscustomobject]@{pids=@(4,2140)}
$decision = Assert-R17ObservedIdleGpuAdmission $request $baseline $admitted $prefix $runId 'stage1'
if ($decision.status -ne 'approved' -or $decision.absolute_third_party_exclusivity_claimed -ne $false) { throw 'r18 bounded observed-idle admission pass case failed' }

$peerRefused = $false
try { Assert-R17ObservedIdleGpuAdmission $request $baseline ([pscustomobject]@{pids=@(4,2140,999)}) $prefix $runId 'stage1' | Out-Null }
catch { $peerRefused = $_.Exception.Message -like '*unexpected post-context process set*' }
if (-not $peerRefused) { throw 'r18 injected concurrent peer was not refused' }

$staleContextRefused = $false
try { Assert-R17ObservedIdleGpuAdmission $request ([pscustomobject]@{pids=@(4,2140)}) $admitted $prefix $runId 'stage1' | Out-Null }
catch { $staleContextRefused = $_.Exception.Message -like '*baseline already contains*' }
if (-not $staleContextRefused) { throw 'r18 stale WSL CUDA context was not refused' }

$disappearedBaselineRefused = $false
try { Assert-R17ObservedIdleGpuAdmission $request $baseline ([pscustomobject]@{pids=@(4)}) $prefix $runId 'stage1' | Out-Null }
catch { $disappearedBaselineRefused = $_.Exception.Message -like '*baseline process disappeared*' }
if (-not $disappearedBaselineRefused) { throw 'r18 changed baseline process set was not refused' }

$texts = [ordered]@{
    supervisor = Get-Content -LiteralPath $supervisor -Raw
    runner = Get-Content -LiteralPath $runner -Raw
    trainer = Get-Content -LiteralPath $trainer -Raw
}
foreach ($required in @('Process-R17GpuAdmissionRequests','Assert-R17ObservedIdleGpuAdmission','gpu_admission_refused','absolute_third_party_exclusivity_claimed=$false')) {
    if ($texts.supervisor.IndexOf($required,[StringComparison]::Ordinal) -lt 0) { throw "r18 supervisor admission binding absent: $required" }
}
foreach ($required in @('PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT','PAPER_FAITHFUL_R17_RUN_PREFIX','PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS')) {
    if ($texts.runner.IndexOf($required,[StringComparison]::Ordinal) -lt 0) { throw "r18 runner admission binding absent: $required" }
}
foreach ($required in @('R17_DEDICATED_HOST_OBSERVED_IDLE_GPU_ADMISSION_V1','_r17_gpu_admission(tf,run_dir,stage)','exact r18 run identity requires GPU admission environment')) {
    if ($texts.trainer.IndexOf($required,[StringComparison]::Ordinal) -lt 0) { throw "r18 trainer admission binding absent: $required" }
}

[ordered]@{
    status = 'pass'
    design_id = 'R17_DEDICATED_HOST_OBSERVED_IDLE_GPU_ADMISSION_V1'
    context_then_observed_idle_approved = $true
    injected_concurrent_peer_refused = $true
    stale_context_refused = $true
    changed_baseline_refused = $true
    workload_approval_required_before_fit = $true
    refusal_prevents_fit_covered_by_python_test = $true
    absolute_third_party_exclusivity_claimed = $false
    pilot_launched = $false
} | ConvertTo-Json -Compress
