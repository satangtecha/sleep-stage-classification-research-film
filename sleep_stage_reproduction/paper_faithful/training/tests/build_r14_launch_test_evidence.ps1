param(
    [string]$LocalPath = (Join-Path $PSScriptRoot '..\r14_scalar_action_launch_test_evidence_20260831_v2.json'),
    [string]$CanonicalPath = 'E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-scalar-action-launch-test-evidence-20260831-v2.json',
    [ValidatePattern('^[0-9a-f]{32}$')][string]$CanaryCaseId = '8fd0ceb068d2454980bb0379fab13a77'
)

$ErrorActionPreference='Stop'
$prefix='paper-text-v1-multiseed-cap128-r14-20260831'
$children=@("$prefix-split42-model42","$prefix-split43-model43")
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$trainingRoot=Join-Path $projectRoot 'paper_faithful\training'
$bulkRoot='E:\blp\sleep_stage_reproduction'
$runtimeRoot=Join-Path $bulkRoot 'runtime'
$logRoot=Join-Path $runtimeRoot 'training-logs'
$driverRoot=Join-Path $runtimeRoot 'driver-recovery'
$ps51="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$lockedPython='/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
$wslProjectRoot='/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction'

function Get-Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Invoke-External([string]$FilePath,[string[]]$Arguments){
    $prior=$ErrorActionPreference
    try{$ErrorActionPreference='Continue';$output=@(& $FilePath @Arguments 2>&1|%{[string]$_});$code=[int]$LASTEXITCODE}
    finally{$ErrorActionPreference=$prior}
    [pscustomobject]@{exit_code=$code;output=($output-join[Environment]::NewLine)}
}
function Read-Json([string]$Text,[string]$Label){try{$Text.Trim()|ConvertFrom-Json -ErrorAction Stop}catch{throw "$Label did not emit valid JSON: $($_.Exception.Message)"}}
function Assert-NoProductionNamespace {
    $paths=@(
        (Join-Path $driverRoot 'canonical-r14-multiseed-launch-gate-20260831.json'),
        (Join-Path $driverRoot 'r14-explicit-user-launch-confirmation-20260831.json'),
        (Join-Path $logRoot "$prefix.dispatch.lock"),(Join-Path $logRoot "$prefix.launch.lock"),
        (Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.dispatch.json"),
        (Join-Path $logRoot "$prefix.lifecycle.jsonl"),(Join-Path $logRoot "$prefix.stdout.log"),
        (Join-Path $logRoot "$prefix.stderr.log"),(Join-Path $logRoot "$prefix.workload-exit-code.txt")
    )+@($children|%{Join-Path (Join-Path $bulkRoot 'runs') $_})
    $present=@($paths|?{Test-Path -LiteralPath $_});if($present.Count){throw "r14 production namespace exists: $($present-join', ')"}
    $svc=New-Object -ComObject 'Schedule.Service';$svc.Connect();$tasks=@($svc.GetFolder('\').GetTasks(1)|?{$_.Name-match'^SleepStagePaper-r14-(?:COM|Canary)-'});if($tasks.Count){throw "r14 Scheduler namespace is not empty: $($tasks.Name-join', ')"}
    $windows=@(Get-WmiObject -Class Win32_Process|?{$_.CommandLine-and$_.CommandLine-match'paper_faithful\.training\.cli (pilot|multi-seed-pilot)'});if($windows.Count){throw 'Windows training process exists'}
    $wsl=Invoke-External 'wsl.exe' @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',"pgrep -af '[p]aper_faithful.training.cli (pilot|multi-seed-pilot)' || true")
    if($wsl.exit_code-ne0-or-not[string]::IsNullOrWhiteSpace($wsl.output)){throw 'WSL training process exists or probe failed'}
}

if(Test-Path -LiteralPath $LocalPath){throw "Local immutable evidence exists: $LocalPath"}
if(Test-Path -LiteralPath $CanonicalPath){throw "Canonical immutable evidence exists: $CanonicalPath"}
Assert-NoProductionNamespace

$focused=[ordered]@{}
foreach($test in @(
    'r14_static_fail_closed_smoke.ps1','r14_task_scheduler_com_preflight_smoke.ps1',
    'r14_exactly_once_refusal_smoke.ps1','r14_gpu_compute_refusal_smoke.ps1',
    'r14_supervisor_semantic_diff_smoke.ps1','r14_delegated_authorization_refusal_smoke.ps1'
)){
    $run=Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot $test))
    if($run.exit_code-ne0){throw "Focused r14 test failed: $test :: $($run.output)"}
    $document=Read-Json $run.output $test;if($document.status-ne'pass'-or$document.pilot_launched-ne$false){throw "Focused r14 test status failed: $test"}
    $focused[$test]=$document
}

$canaryTask="SleepStagePaper-r14-Canary-$CanaryCaseId"
$canaryRoot=Join-Path (Join-Path $driverRoot 'r14-production-action-canaries') $canaryTask
$canaryResultPath=Join-Path $canaryRoot 'result.json';$canaryHandshakePath=Join-Path $canaryRoot 'handshake.json';$canaryControlPath=Join-Path $canaryRoot 'test-control.json'
foreach($path in @($canaryResultPath,$canaryHandshakePath,$canaryControlPath)){if(!(Test-Path -LiteralPath $path -PathType Leaf)){throw "Canary artifact absent: $path"}}
$canary=Get-Content -LiteralPath $canaryResultPath -Raw|ConvertFrom-Json -ErrorAction Stop
$handshake=Get-Content -LiteralPath $canaryHandshakePath -Raw|ConvertFrom-Json -ErrorAction Stop
$control=Get-Content -LiteralPath $canaryControlPath -Raw|ConvertFrom-Json -ErrorAction Stop
if($canary.status-ne'pass'-or$canary.pilot_launched-ne$false-or$canary.task_name-ne$canaryTask-or$canary.persisted_arguments_exact-ne$true-or$canary.serialized_object_refused-ne$true-or$canary.bound_handshake_validated-ne$true-or$canary.task_scheduler_parent-ne'svchost.exe'-or$canary.production_markers_created-ne$false-or[int]$canary.production_arguments_length-gt1024){throw 'Selected r14 production-shape canary is invalid'}
if($handshake.status-ne'bound_handshake'-or$handshake.task_name-ne$canaryTask-or$handshake.parent_process-ne'svchost.exe'-or$control.task_name-ne$canaryTask){throw 'r14 canary handshake/control binding failed'}
if((Get-Sha ([string]$canary.canary_source_path))-ne[string]$canary.canary_source_sha256-or(Get-Sha ([string]$canary.canary_path))-ne[string]$canary.canary_staged_sha256-or[string]$canary.canary_source_sha256-ne[string]$canary.canary_staged_sha256){throw 'r14 canary source/staged hash failed'}

$hostUnit=Invoke-External 'python' @('-m','unittest','paper_faithful.training.tests.test_multi_seed')
$wslUnit=Invoke-External 'wsl.exe' @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',"cd '$wslProjectRoot' && PYTHONDONTWRITEBYTECODE=1 $lockedPython -m unittest paper_faithful.training.tests.test_multi_seed")
foreach($unit in @($hostUnit,$wslUnit)){if($unit.exit_code-ne0-or$unit.output-notmatch'Ran 10 tests'-or$unit.output-notmatch'(?m)^OK\s*$'){throw "multi-seed regression failed: $($unit.output)"}}

$hostImportRun=Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'r14_import_closure_smoke.ps1'))
if($hostImportRun.exit_code-ne0){throw "Host import closure failed: $($hostImportRun.output)"};$hostImport=Read-Json $hostImportRun.output 'host import closure'
$wslImportRun=Invoke-External 'wsl.exe' @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',"cd '$wslProjectRoot' && bash -n paper_faithful/training/run_paper_text_multiseed_smoke_r14.sh && PYTHONDONTWRITEBYTECODE=1 $lockedPython paper_faithful/training/tests/r14_import_closure_probe.py")
if($wslImportRun.exit_code-ne0){throw "WSL import closure failed: $($wslImportRun.output)"};$wslImportDocument=Read-Json $wslImportRun.output 'WSL import closure';$wslImport=@();foreach($entry in $wslImportDocument){$wslImport+=$entry}
$hostReachable=@($hostImport.source_bindings|%{([IO.Path]::GetFullPath([string]$_.path).Substring($projectRoot.Length+1)).Replace('\','/')}|Sort-Object -Unique)
$wslReachable=@($wslImport|%{[string]$_.path}|Sort-Object -Unique);$diff=@(Compare-Object $hostReachable $wslReachable -CaseSensitive)
if($hostImport.status-ne'pass'-or[int]$hostImport.reachable_repository_modules-ne18-or$hostReachable.Count-ne18-or$wslReachable.Count-ne18-or$diff.Count){throw "Host/WSL import closure differs: status=$($hostImport.status) reported=$($hostImport.reachable_repository_modules) host=$($hostReachable.Count) wsl=$($wslReachable.Count) diff=$($diff|ConvertTo-Json -Compress)"}

$stagedSupervisor='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-production-supervisor-v3.ps1'
$templateSupervisor=Join-Path $trainingRoot 'supervise_paper_text_multiseed_smoke_r14.ps1'
$rejectedSupervisorV1='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-production-supervisor.ps1';$rejectedSupervisorV2='E:\blp\sleep_stage_reproduction\runtime\driver-recovery\r14-production-supervisor-v2.ps1'
foreach($path in @($stagedSupervisor,$templateSupervisor,$rejectedSupervisorV1,$rejectedSupervisorV2)){if(!(Test-Path -LiteralPath $path -PathType Leaf)){throw "Supervisor engineering artifact absent: $path"}}
$stagedSha=Get-Sha $stagedSupervisor;$templateSha=Get-Sha $templateSupervisor;if($stagedSha-ne$templateSha-or-not[Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($stagedSupervisor),[IO.File]::ReadAllBytes($templateSupervisor))){throw 'r14 staged v2 supervisor differs from template'}

$sourceMap=[ordered]@{
    dispatcher_ps1=(Join-Path $trainingRoot 'launch_paper_text_multiseed_smoke_r14.ps1')
    supervisor_ps1=$stagedSupervisor
    supervisor_template_ps1=$templateSupervisor
    rejected_supervisor_v1_ps1=$rejectedSupervisorV1
    rejected_supervisor_v2_ps1=$rejectedSupervisorV2
    runner_sh=(Join-Path $trainingRoot 'run_paper_text_multiseed_smoke_r14.sh')
    r14_exactly_once_helpers_ps1=(Join-Path $trainingRoot 'r14_exactly_once_helpers.ps1')
    r14_protocol_json=(Join-Path $trainingRoot 'r14_windows_task_scheduler_scalar_action_protocol_20260831.json')
    lean_team_contract_json=(Join-Path $projectRoot 'r14_scalar_taskdef_run_contract.json')
    r13_failure_evidence_json=(Join-Path $trainingRoot 'r13_infrastructure_failure_evidence_20260831.json')
    r14_static_smoke_ps1=(Join-Path $PSScriptRoot 'r14_static_fail_closed_smoke.ps1')
    r14_preflight_smoke_ps1=(Join-Path $PSScriptRoot 'r14_task_scheduler_com_preflight_smoke.ps1')
    r14_production_action_smoke_ps1=(Join-Path $PSScriptRoot 'r14_task_scheduler_production_action_smoke.ps1')
    r14_canary_target_ps1=(Join-Path $PSScriptRoot 'r14_task_scheduler_bound_handshake_canary.ps1')
    r14_exactly_once_refusal_smoke_ps1=(Join-Path $PSScriptRoot 'r14_exactly_once_refusal_smoke.ps1')
    r14_gpu_compute_refusal_smoke_ps1=(Join-Path $PSScriptRoot 'r14_gpu_compute_refusal_smoke.ps1')
    r14_supervisor_semantic_diff_smoke_ps1=(Join-Path $PSScriptRoot 'r14_supervisor_semantic_diff_smoke.ps1')
    r14_delegated_authorization_refusal_smoke_ps1=(Join-Path $PSScriptRoot 'r14_delegated_authorization_refusal_smoke.ps1')
    r14_import_closure_smoke_ps1=(Join-Path $PSScriptRoot 'r14_import_closure_smoke.ps1')
    r14_import_closure_probe_py=(Join-Path $PSScriptRoot 'r14_import_closure_probe.py')
    r14_launch_test_evidence_smoke_ps1=(Join-Path $PSScriptRoot 'r14_launch_test_evidence_smoke.ps1')
    r14_launch_test_evidence_builder_ps1=$PSCommandPath
    test_multi_seed_py=(Join-Path $PSScriptRoot 'test_multi_seed.py')
    source_manifest_json=(Join-Path $projectRoot 'paper_faithful\manifests\source_manifest.json')
    environment_manifest_json=(Join-Path $projectRoot 'paper_faithful\environment\results\wsl_tf24_probe.json')
    cache_manifest_json=(Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json')
    cache_validator_log=(Join-Path $runtimeRoot 'integrity-logs\full-cache-validation-v2.stdout.log')
    canary_result_json=$canaryResultPath
    canary_handshake_json=$canaryHandshakePath
    canary_control_json=$canaryControlPath
}
foreach($binding in @($hostImport.source_bindings)){$sourceMap[[string]$binding.name]=[string]$binding.path}
$sourceBindings=@($sourceMap.GetEnumerator()|%{$resolved=(Resolve-Path -LiteralPath ([string]$_.Value)).Path;[ordered]@{name=[string]$_.Key;path=$resolved;sha256=(Get-Sha $resolved)}})

$r13Sha=Get-Sha $sourceMap.r13_failure_evidence_json;if($r13Sha-ne'24e10314118e17d6a116906583f0cea1766d0eb686960e4d0b36209506d489af'){throw 'r13 failure evidence changed'}
$protocol=Get-Content -LiteralPath $sourceMap.r14_protocol_json -Raw|ConvertFrom-Json -ErrorAction Stop;if($protocol.design_id-ne'R14_WINDOWS_TASK_SCHEDULER_SCALAR_ACTION_E_STAGED_V1'-or$protocol.run_id_prefix-ne$prefix){throw 'r14 protocol identity failed'}
$cacheHash=Get-Sha $sourceMap.cache_manifest_json;$validatorHash=Get-Sha $sourceMap.cache_validator_log;$events=@(Get-Content -LiteralPath $sourceMap.cache_validator_log|%{if($_){try{$_|ConvertFrom-Json}catch{}}}|?{$_.status});if(!$events-or$events[-1].status-ne'valid'-or$events[-1].cache_manifest_sha256-ne$cacheHash){throw 'cache validator evidence failed'}

$batteries=@(Get-WmiObject -Namespace root\wmi -Class BatteryStatus|?{$_.Active-eq$true});if(!$batteries.Count-or@($batteries|?{$_.PowerOnline-ne$true-or$_.Critical-ne$false}).Count){throw 'power gate failed'}
$gpu=Get-WmiObject -Class Win32_VideoController|?{$_.Name-match'NVIDIA'}|Select-Object -First 1;if(!$gpu-or$gpu.Status-ne'OK'){throw 'Windows GPU gate failed'}
$gpuCompute=Invoke-External 'wsl.exe' @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',"set -o pipefail; nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^[[:space:]]*$/d'");if($gpuCompute.exit_code-ne0-or-not[string]::IsNullOrWhiteSpace($gpuCompute.output)){throw 'GPU compute process gate failed'}
$cFree=[Math]::Round((Get-PSDrive C).Free/1GB,3);$eFree=[Math]::Round((Get-PSDrive E).Free/1GB,3);if($cFree-lt10-or$eFree-lt100){throw "Storage gate failed: C=$cFree E=$eFree"}

Assert-NoProductionNamespace
$failClosed=Invoke-External $ps51 @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',(Join-Path $trainingRoot 'launch_paper_text_multiseed_smoke_r14.ps1'),'-ExpectedCanonicalGateSha256',('0'*64),'-ExpectedUserConfirmationSha256',('0'*64))
if($failClosed.exit_code-ne92){throw "Absent-gate launcher did not fail closed with 92: $($failClosed.output)"}
Assert-NoProductionNamespace

$evidence=[ordered]@{
    schema_version=2;artifact_type='r14_scalar_action_launch_test_evidence_v2';status='pass';run_id_prefix=$prefix;seeds=@(42,43);expected_children=$children
    pilot_launched=$false;production_markers_created=$false;production_task_registered=$false;validated_by_windows_powershell_5_1=$true
    protocol=[ordered]@{design_id=$protocol.design_id;scientific_protocol=$protocol.scientific_protocol;exactly_once=$protocol.exactly_once}
    predecessor=[ordered]@{run_id_prefix='paper-text-v1-multiseed-cap128-r13-20260830';status='failed_before_supervisor';training_launched=$false;retriable=$false;sha256=$r13Sha}
    focused_tests=$focused
    registered_production_shape_canary=[ordered]@{case_id=$CanaryCaseId;task_name=$canaryTask;status='pass';persisted_arguments_exact=$true;production_arguments_length=[int]$canary.production_arguments_length;maximum_arguments_length=1024;scalar_gate_sha_exactly_once=$true;scalar_confirmation_sha_exactly_once=$true;serialized_object_refused=$true;svchost_owned_bound_handshake=$true;pilot_launched=$false;production_markers_created=$false;result_path=$canaryResultPath;result_sha256=(Get-Sha $canaryResultPath)}
    scheduler_query_compatibility=[ordered]@{rejected_v1_path=$rejectedSupervisorV1;rejected_v1_sha256=(Get-Sha $rejectedSupervisorV1);rejection_reason='Task Scheduler-owned Get-CimInstance Win32_Process did not return within the 300-second canary bound';rejected_v2_path=$rejectedSupervisorV2;rejected_v2_sha256=(Get-Sha $rejectedSupervisorV2);rejected_v2_reason='Superseded before launch by delegated-authorization provenance schema v2';production_v3_path=$stagedSupervisor;production_v3_sha256=$stagedSha;template_path=$templateSupervisor;template_sha256=$templateSha;v3_uses_windows_powershell_5_1_get_wmi_object=$true;v3_template_byte_identical=$true}
    authorization_provenance=[ordered]@{schema_version=2;artifact_type='delegated_user_launch_authorization';required_exact_excerpt_count=2;combined_excerpt_sha256='1acefb63aa855c34e9fa1163d5818bac6f5ee80cbdbe406cf9058a4eba2c639e';user_directly_requested_exact_r14_identity=$false;agent_interpretation_label='agent_interpretation_not_user_quote';negative_refusal_test_status='pass'}
    unit_tests=[ordered]@{host=[ordered]@{status='pass';tests=10};locked_wsl_tf24=[ordered]@{status='pass';tests=10;python=$lockedPython}}
    import_closure=[ordered]@{host_status='pass';locked_wsl_status='pass';reachable_repository_modules=18;bound_repository_modules=18;host_wsl_paths_identical=$true;omission_refused=$true}
    cache_gate=[ordered]@{path=(Resolve-Path -LiteralPath $sourceMap.cache_manifest_json).Path;sha256=$cacheHash;validator_log_path=(Resolve-Path -LiteralPath $sourceMap.cache_validator_log).Path;validator_log_sha256=$validatorHash;status='valid'}
    resource_gate=[ordered]@{power_online=$true;critical=$false;c_free_gib=$cFree;e_free_gib=$eFree;gpu_name=[string]$gpu.Name;gpu_driver=[string]$gpu.DriverVersion;gpu_status=[string]$gpu.Status;gpu_compute_process_count=0}
    fail_closed_absent_gate_exit_code=92
    source_bindings=$sourceBindings
    created_at=(Get-Date).ToString('o')
}
$json=$evidence|ConvertTo-Json -Depth 14;$bytes=[Text.UTF8Encoding]::new($false).GetBytes($json+[Environment]::NewLine)
foreach($path in @($LocalPath,$CanonicalPath)){$full=[IO.Path]::GetFullPath($path);[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($full))|Out-Null;$stream=[IO.File]::Open($full,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}}
if(-not[Linq.Enumerable]::SequenceEqual([IO.File]::ReadAllBytes($LocalPath),[IO.File]::ReadAllBytes($CanonicalPath))){throw 'Launch evidence copies differ'}
[ordered]@{status='pass';pilot_launched=$false;local_path=[IO.Path]::GetFullPath($LocalPath);canonical_path=[IO.Path]::GetFullPath($CanonicalPath);sha256=(Get-Sha $LocalPath);source_bindings=$sourceBindings.Count;canary_case_id=$CanaryCaseId}|ConvertTo-Json -Compress
