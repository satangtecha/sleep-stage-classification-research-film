param(
    [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r16.ps1'),
    [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r16.ps1'),
    [string]$RunnerPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r16.sh'),
    [string]$WrapperPath=(Join-Path $PSScriptRoot '..\run_paper_text_multiseed_smoke_r16_wrapper.sh'),
    [string]$HelperPath=(Join-Path $PSScriptRoot '..\r16_exactly_once_helpers.ps1')
)
$ErrorActionPreference='Stop'
$dispatcher=Get-Content -LiteralPath (Resolve-Path -LiteralPath $DispatcherPath) -Raw
$supervisor=Get-Content -LiteralPath (Resolve-Path -LiteralPath $SupervisorPath) -Raw
$runner=Get-Content -LiteralPath (Resolve-Path -LiteralPath $RunnerPath) -Raw
$wrapper=Get-Content -LiteralPath (Resolve-Path -LiteralPath $WrapperPath) -Raw
$helper=Get-Content -LiteralPath (Resolve-Path -LiteralPath $HelperPath) -Raw
function Need([string]$Text,[string]$Needle,[string]$Label){if(!$Text.Contains($Needle)){throw "$Label missing: $Needle"}}
foreach($text in @($dispatcher,$supervisor,$runner)){Need $text 'paper-text-v1-multiseed-cap128-r16-20260901' 'r16 identity'}
foreach($needle in @('PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1','--seeds 42 43','--cap 128','--stage3-gradient-clip-norm 1.0')){Need $runner $needle 'r16 runner'}
if($dispatcher-match'--resume|--retry' -or $supervisor-match'--resume|--retry' -or $runner-match'--resume|--retry'){throw 'r16 sources contain retry/resume'}
if($dispatcher-match'Get-WmiObject|Get-CimInstance' -or $supervisor-match'Get-WmiObject|Get-CimInstance' -or $helper-match'Get-WmiObject|Get-CimInstance'){throw 'r16 WMI/CIM-free boundary failed'}
if($helper.Contains('Add-Type')){throw 'r16 scheduler helper retains runtime C# compilation'}
foreach($needle in @('Get-R16NativeParentProcessId','Get-R16NativePowerStatus','Get-R16NativeDriveFreeGiB','pre_attempt_deadline_seconds','supervisor-preflight.jsonl','Assert-PreflightDeadline','pre_attempt_failed')){Need $supervisor $needle 'r16 bounded supervisor'}
if($supervisor.Contains('Get-PSDrive')){throw 'r16 scheduler supervisor retains potentially blocking Get-PSDrive'}
foreach($needle in @('Invoke-R16BoundedWslScript','Invoke-R16BoundedProcess','Assert-R16GpuComputeIdle')){Need $dispatcher $needle 'r16 bounded dispatcher'}
foreach($text in @($dispatcher,$supervisor)){
    foreach($needle in @("[ValidateSet('utf8_text','binary')]","if(`$contentType-eq'utf8_text')","r16_native_probe_dll'){'binary'}else{'utf8_text'}")){Need $text $needle 'r16 content-type stable lock'}
    $branchAt=$text.IndexOf("if(`$contentType-eq'utf8_text')",[StringComparison]::Ordinal)
    $decodeAt=$text.IndexOf('GetString($b)',[StringComparison]::Ordinal)
    if($branchAt-lt0-or$decodeAt-le$branchAt){throw 'r16 strict UTF-8 decode is not guarded by utf8_text content type'}
}
foreach($needle in @('foreground_wrapper_sh=$wrapperPath','run_paper_text_multiseed_smoke_r16_wrapper.sh','Open-R16PermanentMarker $attemptMarker','Assert-R16BoundDispatchRecord')){Need $supervisor $needle 'r16 wrapper/exactly-once supervisor'}
foreach($needle in @('bash "$runner"','mv -f -- "$tmp" "$exit_path"','exit "$rc"')){Need $wrapper $needle 'r16 foreground wrapper'}
if($supervisor.Contains("'-lc',`$wrapper") -or $supervisor.Contains('$wrapper=(')){throw 'r16 retained dynamic shell command-line construction'}
if(([regex]::Matches($runner,'paper_faithful\.training\.cli multi-seed-pilot')).Count-ne1){throw 'r16 runner must invoke multi-seed-pilot once'}
$recordAt=$supervisor.IndexOf('Assert-R16BoundDispatchRecord',[StringComparison]::Ordinal)
$attemptAt=$supervisor.IndexOf('Open-R16PermanentMarker $attemptMarker',[StringComparison]::Ordinal)
$processAt=$supervisor.IndexOf('Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe"',[StringComparison]::Ordinal)
if($recordAt-lt0-or$attemptAt-le$recordAt-or$processAt-le$attemptAt){throw 'r16 dispatch/attempt/workload order failed'}
$deadlineAt=$supervisor.IndexOf("Assert-PreflightDeadline `$deadlineSeconds 'before-attempt'",[StringComparison]::Ordinal)
if($deadlineAt-lt0-or$attemptAt-le$deadlineAt){throw 'r16 deadline is not checked immediately before attempt'}
$gpuAt=$dispatcher.IndexOf("Assert-R16GpuComputeIdle 'dispatcher-pre-dispatch'",[StringComparison]::Ordinal)
$dispatchAt=$dispatcher.IndexOf("Open-R16PermanentMarker `$dispatch 'dispatch'",[StringComparison]::Ordinal)
if($gpuAt-lt0-or$dispatchAt-le$gpuAt){throw 'r16 GPU-idle gate is not before dispatch marker'}
foreach($needle in @("Data['r16_exit_code'] = 91",'[IO.FileMode]::CreateNew','[IO.FileShare]::None','Get-R16ExpectedSupervisorActionArguments','CanaryRoot is outside its exact bounded namespace','[Reflection.Assembly]::LoadFrom')){Need $helper $needle 'r16 helper'}
foreach($needle in @('r16_native_probe_cs=$nativeSourcePath','r16_native_probe_dll=$nativeAssemblyPath')){Need $supervisor $needle 'r16 native probe source binding'}
[ordered]@{status='pass';pilot_launched=$false;fresh_r16_identity=$true;binary_safe_source_lock=$true;wmi_cim_free_supervisor=$true;bounded_pre_attempt_deadline=$true;native_parent_power=$true;source_bound_foreground_wrapper=$true;dynamic_shell_command_absent=$true;dispatch_attempt_workload_order=$true;gpu_before_dispatch=$true;no_retry_resume=$true}|ConvertTo-Json -Compress
