param(
    [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r15.ps1'),
    [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r15.ps1'),
    [string]$RunnerPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r15.sh'),
    [string]$WrapperPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r15_wrapper.sh'),
    [string]$HelperPath=(Join-Path $PSScriptRoot '..\r15_exactly_once_helpers.ps1')
)
$ErrorActionPreference='Stop'
$dispatcher=Get-Content -LiteralPath (Resolve-Path -LiteralPath $DispatcherPath) -Raw
$supervisor=Get-Content -LiteralPath (Resolve-Path -LiteralPath $SupervisorPath) -Raw
$runner=Get-Content -LiteralPath (Resolve-Path -LiteralPath $RunnerPath) -Raw
$wrapper=Get-Content -LiteralPath (Resolve-Path -LiteralPath $WrapperPath) -Raw
$helper=Get-Content -LiteralPath (Resolve-Path -LiteralPath $HelperPath) -Raw
function Need([string]$Text,[string]$Needle,[string]$Label){if(!$Text.Contains($Needle)){throw "$Label missing: $Needle"}}
foreach($text in @($dispatcher,$supervisor,$runner)){Need $text 'paper-text-v1-multiseed-cap128-r15-20260831' 'r15 identity'}
foreach($needle in @('PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1','--seeds 42 43','--cap 128','--stage3-gradient-clip-norm 1.0')){Need $runner $needle 'r15 runner'}
if($dispatcher-match'--resume|--retry' -or $supervisor-match'--resume|--retry' -or $runner-match'--resume|--retry'){throw 'r15 sources contain retry/resume'}
if($dispatcher-match'Get-WmiObject|Get-CimInstance' -or $supervisor-match'Get-WmiObject|Get-CimInstance' -or $helper-match'Get-WmiObject|Get-CimInstance'){throw 'r15 WMI/CIM-free boundary failed'}
if($helper.Contains('Add-Type')){throw 'r15 scheduler helper retains runtime C# compilation'}
foreach($needle in @('Get-R15NativeParentProcessId','Get-R15NativePowerStatus','Get-R15NativeDriveFreeGiB','pre_attempt_deadline_seconds','supervisor-preflight.jsonl','Assert-PreflightDeadline','pre_attempt_failed')){Need $supervisor $needle 'r15 bounded supervisor'}
if($supervisor.Contains('Get-PSDrive')){throw 'r15 scheduler supervisor retains potentially blocking Get-PSDrive'}
foreach($needle in @('Invoke-R15BoundedWslScript','Invoke-R15BoundedProcess','Assert-R15GpuComputeIdle')){Need $dispatcher $needle 'r15 bounded dispatcher'}
foreach($needle in @('foreground_wrapper_sh=$wrapperPath','run_paper_text_multiseed_smoke_r15_wrapper.sh','Open-R15PermanentMarker $attemptMarker','Assert-R15BoundDispatchRecord')){Need $supervisor $needle 'r15 wrapper/exactly-once supervisor'}
foreach($needle in @('bash "$runner"','mv -f -- "$tmp" "$exit_path"','exit "$rc"')){Need $wrapper $needle 'r15 foreground wrapper'}
if($supervisor.Contains("'-lc',`$wrapper") -or $supervisor.Contains('$wrapper=(')){throw 'r15 retained dynamic shell command-line construction'}
if(([regex]::Matches($runner,'paper_faithful\.training\.cli multi-seed-pilot')).Count-ne1){throw 'r15 runner must invoke multi-seed-pilot once'}
$recordAt=$supervisor.IndexOf('Assert-R15BoundDispatchRecord',[StringComparison]::Ordinal)
$attemptAt=$supervisor.IndexOf('Open-R15PermanentMarker $attemptMarker',[StringComparison]::Ordinal)
$processAt=$supervisor.IndexOf('Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe"',[StringComparison]::Ordinal)
if($recordAt-lt0-or$attemptAt-le$recordAt-or$processAt-le$attemptAt){throw 'r15 dispatch/attempt/workload order failed'}
$deadlineAt=$supervisor.IndexOf("Assert-PreflightDeadline `$deadlineSeconds 'before-attempt'",[StringComparison]::Ordinal)
if($deadlineAt-lt0-or$attemptAt-le$deadlineAt){throw 'r15 deadline is not checked immediately before attempt'}
$gpuAt=$dispatcher.IndexOf("Assert-R15GpuComputeIdle 'dispatcher-pre-dispatch'",[StringComparison]::Ordinal)
$dispatchAt=$dispatcher.IndexOf("Open-R15PermanentMarker `$dispatch 'dispatch'",[StringComparison]::Ordinal)
if($gpuAt-lt0-or$dispatchAt-le$gpuAt){throw 'r15 GPU-idle gate is not before dispatch marker'}
foreach($needle in @("Data['r15_exit_code'] = 91",'[IO.FileMode]::CreateNew','[IO.FileShare]::None','Get-R15ExpectedSupervisorActionArguments','CanaryRoot is outside its exact bounded namespace','[Reflection.Assembly]::LoadFrom')){Need $helper $needle 'r15 helper'}
foreach($needle in @('r15_native_probe_cs=$nativeSourcePath','r15_native_probe_dll=$nativeAssemblyPath')){Need $supervisor $needle 'r15 native probe source binding'}
[ordered]@{status='pass';pilot_launched=$false;fresh_r15_identity=$true;wmi_cim_free_supervisor=$true;bounded_pre_attempt_deadline=$true;native_parent_power=$true;source_bound_foreground_wrapper=$true;dynamic_shell_command_absent=$true;dispatch_attempt_workload_order=$true;gpu_before_dispatch=$true;no_retry_resume=$true}|ConvertTo-Json -Compress
