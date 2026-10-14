param(
    [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r18.ps1'),
    [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r18.ps1'),
    [string]$RunnerPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r18.sh'),
    [string]$WrapperPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r18_wrapper.sh'),
    [string]$HelperPath=(Join-Path $PSScriptRoot '..\r18_exactly_once_helpers.ps1'),
    [string]$TrainerPath=(Join-Path $PSScriptRoot '..\trainer.py')
)
$ErrorActionPreference='Stop'
$dispatcher=Get-Content -LiteralPath (Resolve-Path -LiteralPath $DispatcherPath) -Raw
$supervisor=Get-Content -LiteralPath (Resolve-Path -LiteralPath $SupervisorPath) -Raw
$runner=Get-Content -LiteralPath (Resolve-Path -LiteralPath $RunnerPath) -Raw
$wrapper=Get-Content -LiteralPath (Resolve-Path -LiteralPath $WrapperPath) -Raw
$helper=Get-Content -LiteralPath (Resolve-Path -LiteralPath $HelperPath) -Raw
$trainer=Get-Content -LiteralPath (Resolve-Path -LiteralPath $TrainerPath) -Raw
function Need([string]$Text,[string]$Needle,[string]$Label){if(!$Text.Contains($Needle)){throw "$Label missing: $Needle"}}
foreach($text in @($dispatcher,$supervisor,$runner)){Need $text 'paper-text-v1-multiseed-cap128-r18-20260902' 'r18 identity'}
foreach($needle in @('PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1','--seeds 42 43','--cap 128','--stage3-gradient-clip-norm 1.0')){Need $runner $needle 'r18 runner'}
foreach($needle in @('PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT','PAPER_FAITHFUL_R17_RUN_PREFIX','PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS')){Need $runner $needle 'r18 admission environment'}
if($dispatcher-match'--resume|--retry' -or $supervisor-match'--resume|--retry' -or $runner-match'--resume|--retry'){throw 'r18 sources contain retry/resume'}
if($dispatcher-match'Get-WmiObject|Get-CimInstance' -or $supervisor-match'Get-WmiObject|Get-CimInstance' -or $helper-match'Get-WmiObject|Get-CimInstance'){throw 'r18 WMI/CIM-free boundary failed'}
if($helper.Contains('Add-Type')){throw 'r18 scheduler helper retains runtime C# compilation'}
foreach($needle in @('Get-R17NativeParentProcessId','Get-R17NativePowerStatus','Get-R17NativeDriveFreeGiB','pre_attempt_deadline_seconds','supervisor-preflight.jsonl','Assert-PreflightDeadline','pre_attempt_failed')){Need $supervisor $needle 'r18 bounded supervisor'}
if($supervisor.Contains('Get-PSDrive')){throw 'r18 scheduler supervisor retains potentially blocking Get-PSDrive'}
foreach($needle in @('Invoke-R17BoundedWslScript','Invoke-R17BoundedProcess','Assert-R17GpuComputeIdle')){Need $dispatcher $needle 'r18 bounded dispatcher'}
foreach($needle in @('$dispatcherHandshakeDeadlineSeconds=600','[Diagnostics.Stopwatch]::StartNew()','handshake_wait_started','handshake_pending','handshake_observed','handshake_timed_out','$nextPendingAt+=10.0','dispatcher_handshake_deadline_seconds=$dispatcherHandshakeDeadlineSeconds')){Need $dispatcher $needle 'r18 scheduler handshake recovery'}
if(([regex]::Matches($dispatcher,'\.RunEx\(')).Count-ne1){throw 'r18 dispatcher must request one scheduler instance exactly once'}
foreach($text in @($dispatcher,$supervisor)){
    foreach($needle in @("[ValidateSet('utf8_text','binary')]","if(`$contentType-eq'utf8_text')","r18_native_probe_dll'){'binary'}else{'utf8_text'}")){Need $text $needle 'r18 content-type stable lock'}
    $branchAt=$text.IndexOf("if(`$contentType-eq'utf8_text')",[StringComparison]::Ordinal)
    $decodeAt=$text.IndexOf('GetString($b)',[StringComparison]::Ordinal)
    if($branchAt-lt0-or$decodeAt-le$branchAt){throw 'r18 strict UTF-8 decode is not guarded by utf8_text content type'}
}
foreach($needle in @('foreground_wrapper_sh=$wrapperPath','run_paper_text_multiseed_smoke_r18_wrapper.sh','Open-R17PermanentMarker $attemptMarker','Assert-R17BoundDispatchRecord')){Need $supervisor $needle 'r18 wrapper/exactly-once supervisor'}
foreach($needle in @('trap write_terminal_sidecar EXIT','stage=cwd','stage=stdout_open','stage=stderr_open','stage=runner_complete','"schema_version":1','mv -f -- "$tmp" "$exit_path"','exit "$rc"')){Need $wrapper $needle 'r18 foreground wrapper'}
foreach($needle in @('Start-R17WslForeground','$psi.WorkingDirectory="$env:SystemRoot\System32"','$psi.RedirectStandardOutput=$true','$psi.RedirectStandardError=$true','R17HostStdoutTask','Complete-R17HostCapture','scheduler_wsl_handoff','structured_atomic_sidecar','host_diagnostics_captured','windows_host_forced_cleanup','atomic_runner_complete_then_exact_pid_cleanup','Completed WSL host exact-PID cleanup failed','workload-exit.json')){Need $supervisor $needle 'r18 bootstrap diagnostics'}
foreach($needle in @('R17_DEDICATED_HOST_OBSERVED_IDLE_GPU_ADMISSION_V1','Get-R17WindowsGpuProcessSnapshot','Process-R17GpuAdmissionRequests','gpu_admission_approved','gpu_admission_refused','gpu-admission-summary.json','absolute_third_party_exclusivity_claimed=$false')){Need ($supervisor+$helper) $needle 'r18 observed-idle admission'}
if($supervisor.Contains("'-lc',`$wrapper") -or $supervisor.Contains('$wrapper=(')){throw 'r18 retained dynamic shell command-line construction'}
if(([regex]::Matches($runner,'paper_faithful\.training\.cli multi-seed-pilot')).Count-ne1){throw 'r18 runner must invoke multi-seed-pilot once'}
$recordAt=$supervisor.IndexOf('Assert-R17BoundDispatchRecord',[StringComparison]::Ordinal)
$attemptAt=$supervisor.IndexOf('Open-R17PermanentMarker $attemptMarker',[StringComparison]::Ordinal)
$supervisorGpuAt=$supervisor.IndexOf("Assert-R17GpuComputeIdle 'supervisor-post-attempt-pre-workload'",[StringComparison]::Ordinal)
$processAt=$supervisor.IndexOf('$child=Start-R17WslForeground',[StringComparison]::Ordinal)
if($recordAt-lt0-or$attemptAt-le$recordAt-or$supervisorGpuAt-le$attemptAt-or$processAt-le$supervisorGpuAt){throw 'r18 dispatch/attempt/GPU-recheck/workload order failed'}
$baselineAt=$supervisor.IndexOf("Get-R17WindowsGpuProcessSnapshot 'supervisor-pre-workload-windows-baseline'",[StringComparison]::Ordinal)
if($baselineAt-le$supervisorGpuAt-or$processAt-le$baselineAt){throw 'r18 Windows GPU baseline is not between idle recheck and workload start'}
$admissionAt=$trainer.LastIndexOf('_r17_gpu_admission(tf,run_dir,stage)',[StringComparison]::Ordinal)
$fitAt=$trainer.IndexOf('history=model.fit(',[StringComparison]::Ordinal)
if($admissionAt-lt0-or$fitAt-le$admissionAt){throw 'r18 workload admission does not precede model.fit'}
Need $trainer 'exact r18 run identity requires GPU admission environment' 'r18 exact identity no-environment refusal'
$deadlineAt=$supervisor.IndexOf("Assert-PreflightDeadline `$deadlineSeconds 'before-attempt'",[StringComparison]::Ordinal)
if($deadlineAt-lt0-or$attemptAt-le$deadlineAt){throw 'r18 deadline is not checked immediately before attempt'}
$gpuAt=$dispatcher.IndexOf("Assert-R17GpuComputeIdle 'dispatcher-pre-dispatch'",[StringComparison]::Ordinal)
$dispatchAt=$dispatcher.IndexOf("Open-R17PermanentMarker `$dispatch 'dispatch'",[StringComparison]::Ordinal)
if($gpuAt-lt0-or$dispatchAt-le$gpuAt){throw 'r18 GPU-idle gate is not before dispatch marker'}
foreach($needle in @("Data['r18_exit_code'] = 91",'[IO.FileMode]::CreateNew','[IO.FileShare]::None','Get-R17ExpectedSupervisorActionArguments','CanaryRoot is outside its exact bounded namespace','[Reflection.Assembly]::LoadFrom')){Need $helper $needle 'r18 helper'}
foreach($needle in @('r18_native_probe_cs=$nativeSourcePath','r18_native_probe_dll=$nativeAssemblyPath')){Need $supervisor $needle 'r18 native probe source binding'}
[ordered]@{status='pass';pilot_launched=$false;fresh_r18_identity=$true;binary_safe_source_lock=$true;bootstrap_diagnostics=$true;structured_atomic_sidecar=$true;scheduler_wsl_handoff_canary=$true;dispatcher_handshake_deadline_seconds=600;handshake_pending_interval_seconds=10;exclusive_dispatch_marker_held_through_bound_handshake=$true;handshake_timeout_terminal_without_retry=$true;single_scheduler_runex=$true;neutral_windows_working_directory=$true;host_diagnostics_captured=$true;atomic_then_exact_pid_cleanup=$true;wmi_cim_free_supervisor=$true;bounded_pre_attempt_deadline=$true;native_parent_power=$true;source_bound_foreground_wrapper=$true;dynamic_shell_command_absent=$true;dispatch_attempt_gpu_recheck_workload_order=$true;gpu_before_dispatch=$true;supervisor_gpu_recheck_after_attempt_before_workload=$true;windows_gpu_baseline_before_workload=$true;context_admission_before_model_fit=$true;exact_r18_no_environment_refused_before_fit=$true;absolute_third_party_exclusivity_claimed=$false;no_retry_resume=$true}|ConvertTo-Json -Compress
