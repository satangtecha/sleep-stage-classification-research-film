param(
    [string]$CanaryCaseId = ([Guid]::NewGuid().ToString('N')),
    [int]$TimeoutSeconds = 180
)
$ErrorActionPreference='Stop'
$helper=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\r19_exactly_once_helpers.ps1')).Path
. $helper
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$driver='E:\blp\sleep_stage_reproduction\runtime\driver-recovery'
$root=Join-Path (Join-Path $driver 'r19-live-gpu-admission-canaries') $CanaryCaseId
$admission=Join-Path $root 'admission'
$stdout=Join-Path $root 'wsl.stdout.log'
$stderr=Join-Path $root 'wsl.stderr.log'
$resultPath=Join-Path $root 'result.json'
 $prefix='paper-text-v1-multiseed-cap128-r19-20260905'
 $runId="$prefix-split42-model42"
$requestPath=Join-Path $admission "$runId.stage1.request.json"
 $approvalPath=Join-Path $admission "$runId.stage1.approval.json"
 $bindingPath=Join-Path $root 'supervisor-binding.json'
 $bindingLockPath=Join-Path $root 'supervisor-binding.lock'
 $canaryGatePath=Join-Path $root 'canary-gate.json'
 $canaryConfirmationPath=Join-Path $root 'canary-confirmation.json'
 $canaryDispatchPath=Join-Path $root 'dispatch.lock'
 $canaryAttemptPath=Join-Path $root 'attempt.lock'
$wslRoot='/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction'
 $wslAdmission="/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/r19-live-gpu-admission-canaries/$CanaryCaseId/admission"
 $wslBinding="/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/r19-live-gpu-admission-canaries/$CanaryCaseId/supervisor-binding.json"
 $wslBindingLock="/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/r19-live-gpu-admission-canaries/$CanaryCaseId/supervisor-binding.lock"
 $wslCanaryGate="/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/r19-live-gpu-admission-canaries/$CanaryCaseId/canary-gate.json"
 $wslCanaryConfirmation="/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/r19-live-gpu-admission-canaries/$CanaryCaseId/canary-confirmation.json"
 $wslCanaryDispatch="/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/r19-live-gpu-admission-canaries/$CanaryCaseId/dispatch.lock"
 $wslCanaryAttempt="/mnt/e/blp/sleep_stage_reproduction/runtime/driver-recovery/r19-live-gpu-admission-canaries/$CanaryCaseId/attempt.lock"
$python='/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python'
if(Test-Path -LiteralPath $root){throw "r19 live canary namespace collision: $root"}
[IO.Directory]::CreateDirectory($admission)|Out-Null
$oldRoot=$env:PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT;$oldPrefix=$env:PAPER_FAITHFUL_R17_RUN_PREFIX;$oldTimeout=$env:PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS
 $process=$null;$bindingLockStream=$null;$dispatchMarkerStream=$null;$attemptMarkerStream=$null
try {
     $baseline=Get-R17WindowsGpuProcessSnapshot 'r19-live-gpu-baseline'
     $bindingId=([Guid]::NewGuid().ToString('N'));$taskName="SleepStagePaper-r19-Canary-$CanaryCaseId"
     $dispatchMarkerStream=[IO.File]::Open([IO.Path]::GetFullPath($canaryDispatchPath),[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
     $attemptMarkerStream=[IO.File]::Open([IO.Path]::GetFullPath($canaryAttemptPath),[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
     Write-R17ImmutableJson $canaryGatePath ([ordered]@{schema_version=1;artifact_type='r19_live_canary_gate';case_id=$CanaryCaseId})
     Write-R17ImmutableJson $canaryConfirmationPath ([ordered]@{schema_version=1;artifact_type='r19_live_canary_confirmation';case_id=$CanaryCaseId})
     $gateSha=(Get-FileHash -LiteralPath $canaryGatePath -Algorithm SHA256).Hash.ToLowerInvariant();$confirmationSha=(Get-FileHash -LiteralPath $canaryConfirmationPath -Algorithm SHA256).Hash.ToLowerInvariant()
     $capabilityToken=New-R19SupervisorCapabilityToken;$material=$bindingId+"`0"+$gateSha+"`0"+$confirmationSha+"`0"+$taskName+"`0"+$PID+"`0"+$wslCanaryDispatch+"`0"+$wslCanaryAttempt+"`0"+$wslBindingLock+"`0"+$capabilityToken;$capabilitySha=Get-R17TextSha256 $material
     $binding=[ordered]@{schema_version=2;binding_id=$bindingId;run_id_prefix=$prefix;expected_children=@("$prefix-split42-model42","$prefix-split43-model43");canonical_gate_sha256=$gateSha;user_confirmation_sha256=$confirmationSha;canonical_gate_path=$wslCanaryGate;user_confirmation_path=$wslCanaryConfirmation;task_name=$taskName;dispatch_marker_path=$wslCanaryDispatch;attempt_marker_path=$wslCanaryAttempt;lock_path=$wslBindingLock;capability_token_sha256=(Get-R17TextSha256 $capabilityToken);capability_sha256=$capabilitySha;supervisor_pid=[int]$PID;created_at=(Get-Date).ToString('o')}
     Write-R17ImmutableJson $bindingPath $binding
     $bindingLockStream=[IO.File]::Open([IO.Path]::GetFullPath($bindingLockPath),[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
     $command="export PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT='$wslAdmission'; export PAPER_FAITHFUL_R17_RUN_PREFIX='$prefix'; export PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS='240'; export PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_PATH='$wslBinding'; export PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_LOCK_PATH='$wslBindingLock'; IFS= read -r PAPER_FAITHFUL_R19_SUPERVISOR_CAPABILITY_TOKEN; export PAPER_FAITHFUL_R19_SUPERVISOR_CAPABILITY_TOKEN; cd '$wslRoot'; exec $python -u -m paper_faithful.training.tests.r19_live_gpu_admission_canary"
    $psi=New-Object Diagnostics.ProcessStartInfo
    $psi.FileName="$env:SystemRoot\System32\wsl.exe"
    $psi.Arguments=('-d Ubuntu -e bash --noprofile --norc -lc "'+$command.Replace('"','\"')+'"')
    $psi.WorkingDirectory="$env:SystemRoot\System32";$psi.UseShellExecute=$false;$psi.CreateNoWindow=$true;$psi.RedirectStandardInput=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true
    $process=New-Object Diagnostics.Process;$process.StartInfo=$psi
    if(!$process.Start()){throw 'r19 live GPU canary could not start locked TF2.4 process'}
    if($process.StartInfo.Arguments -match [regex]::Escape($capabilityToken)){throw 'r19 live GPU capability token appeared in WSL command line'}
    $process.StandardInput.Write($capabilityToken+[char]10);$process.StandardInput.Close()
    $outTask=$process.StandardOutput.ReadToEndAsync();$errTask=$process.StandardError.ReadToEndAsync()
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    while(!(Test-Path -LiteralPath $requestPath)-and(Get-Date)-lt$deadline){Start-Sleep -Milliseconds 250;$process.Refresh()}
    if(!(Test-Path -LiteralPath $requestPath)){throw "r19 live GPU admission request timed out: $requestPath"}
    $request=Get-Content -LiteralPath $requestPath -Raw|ConvertFrom-Json
    $requestSha=(Get-FileHash -LiteralPath $requestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $current=$null;$decision=$null;$admissionDeadline=(Get-Date).AddSeconds(60)
    while($null-eq$decision-and(Get-Date)-lt$admissionDeadline){$current=Get-R17WindowsGpuProcessSnapshot 'r19-live-gpu-post-context';try{$decision=Assert-R17ObservedIdleGpuAdmission $request $baseline $current $prefix $runId 'stage1'}catch{$decision=$null;Start-Sleep -Milliseconds 250}}
    if($null-eq$decision){throw 'r19 live GPU admission did not reach the bounded observed-idle approval state'}
    $approval=[ordered]@{schema_version=1;design_id=[string]$decision.design_id;status='approved';run_id_prefix=[string]$request.run_id_prefix;run_id=[string]$request.run_id;stage=[string]$request.stage;nonce=[string]$request.nonce;request_sha256=$requestSha;baseline_pids=@($decision.baseline_pids);current_pids=@($decision.current_pids);expected_wsl_system_pid=4;observability_limit=[string]$decision.observability_limit;absolute_third_party_exclusivity_claimed=$false;approved_at=(Get-Date).ToString('o')}
    Write-R17ImmutableJson $approvalPath $approval
    while(!$process.HasExited-and(Get-Date)-lt$deadline){Start-Sleep -Milliseconds 250;$process.Refresh()}
    if(!$process.HasExited){try{$process.Kill()}catch{};throw 'r19 live GPU canary locked TF2.4 process timed out after approval'}
    $process.WaitForExit();$process.Refresh();$wslOut=[string]$outTask.GetAwaiter().GetResult();$wslErr=[string]$errTask.GetAwaiter().GetResult()
    [IO.File]::WriteAllText($stdout,$wslOut,[Text.UTF8Encoding]::new($false));[IO.File]::WriteAllText($stderr,$wslErr,[Text.UTF8Encoding]::new($false))
    if([int]$process.ExitCode-ne0){throw "r19 live GPU canary exited $($process.ExitCode): $wslErr"}
    $trainer=(Join-Path $projectRoot 'paper_faithful\training\trainer.py');$helperFile=(Join-Path $projectRoot 'paper_faithful\training\r19_exactly_once_helpers.ps1')
     $result=[ordered]@{schema_version=1;status='pass';pilot_launched=$false;training_started=$false;supervisor_bound_admission=$true;supervisor_authenticated_token=$true;supervisor_capability_token_random_256=$true;supervisor_capability_token_not_persisted=$true;capability_token_transport='stdin_pipe';capability_token_not_in_wsl_command_line=$true;forged_public_binding_with_independent_lease_refused=$true;design_id='R17_DEDICATED_HOST_OBSERVED_IDLE_GPU_ADMISSION_V1';case_id=$CanaryCaseId;locked_tf24_python=$python;real_tensorflow_gpu_context_acquired=$true;request_sha256=$requestSha;approval_sha256=(Get-FileHash -LiteralPath $approvalPath -Algorithm SHA256).Hash.ToLowerInvariant();baseline_pids=@($baseline.pids);post_context_pids=@($current.pids);expected_wsl_windows_system_pid=4;absolute_third_party_exclusivity_claimed=$false;drvfs_request_and_approval=$true;process_exit_code=[int]$process.ExitCode;trainer_sha256=(Get-FileHash -LiteralPath $trainer -Algorithm SHA256).Hash.ToLowerInvariant();helper_sha256=(Get-FileHash -LiteralPath $helperFile -Algorithm SHA256).Hash.ToLowerInvariant();binding_path=$bindingPath;binding_sha256=(Get-FileHash -LiteralPath $bindingPath -Algorithm SHA256).Hash.ToLowerInvariant();binding_lock_path=$bindingLockPath;request_path=$requestPath;approval_path=$approvalPath;stdout_path=$stdout;stderr_path=$stderr;created_at=(Get-Date).ToString('o')}
    Write-R17ImmutableJson $resultPath $result
    $result|Add-Member result_path $resultPath -PassThru|ConvertTo-Json -Compress
 } finally {
     if($process-and-not$process.HasExited){try{$process.Kill()}catch{}}
     if($bindingLockStream){$bindingLockStream.Dispose()}
     if($attemptMarkerStream){$attemptMarkerStream.Dispose()}
     if($dispatchMarkerStream){$dispatchMarkerStream.Dispose()}
    if($null-eq$oldRoot){Remove-Item Env:PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT -ErrorAction SilentlyContinue}else{$env:PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT=$oldRoot}
    if($null-eq$oldPrefix){Remove-Item Env:PAPER_FAITHFUL_R17_RUN_PREFIX -ErrorAction SilentlyContinue}else{$env:PAPER_FAITHFUL_R17_RUN_PREFIX=$oldPrefix}
    if($null-eq$oldTimeout){Remove-Item Env:PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS -ErrorAction SilentlyContinue}else{$env:PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS=$oldTimeout}
}
