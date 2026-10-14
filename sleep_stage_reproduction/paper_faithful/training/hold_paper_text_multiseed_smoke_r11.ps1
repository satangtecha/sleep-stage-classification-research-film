param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedCanonicalGateSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedUserConfirmationSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedDispatchNonce
)

$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$bulkRoot='E:\blp\sleep_stage_reproduction'
$prefix='paper-text-v1-multiseed-cap128-r11-20260830'
$seeds=@(42,43)
$children=@("$prefix-split42-model42","$prefix-split43-model43")
$sourceThreadId='01a014bc-7bc1-7590-bd2b-029c8a84285b'
$runtime=Join-Path $bulkRoot 'runtime'
$logRoot=Join-Path $runtime 'training-logs'
$gatePath=Join-Path $runtime 'driver-recovery\canonical-r11-multiseed-launch-gate-20260830.json'
$confirmationPath=Join-Path $runtime 'driver-recovery\r11-explicit-user-launch-confirmation-20260830.json'
$dispatchMarker=Join-Path $logRoot "$prefix.dispatch.lock"
$dispatchCapability=Join-Path $logRoot "$prefix.dispatch-capability.json"
$attemptMarker=Join-Path $logRoot "$prefix.launch.lock"
$stdout=Join-Path $logRoot "$prefix.stdout.log"
$stderr=Join-Path $logRoot "$prefix.stderr.log"
$lifecycle=Join-Path $logRoot "$prefix.lifecycle.jsonl"
$ready=Join-Path $logRoot "$prefix.lockholder-ready.json"
$workloadExitEvidence=Join-Path $logRoot "$prefix.workload-exit-code.txt"
$cacheManifest=Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'
$validatorLog=Join-Path $runtime 'integrity-logs\full-cache-validation-v2.stdout.log'
$heldReadLocks=@()
$lockedFiles=@{}
$attemptStream=$null

function Get-Sha256FromBytes([byte[]]$Bytes) {
    $hash=[Security.Cryptography.SHA256]::Create()
    try {return -join($hash.ComputeHash($Bytes)|ForEach-Object{$_.ToString('x2')})} finally {$hash.Dispose()}
}

function Open-StableReadLock([string]$Path) {
    $full=[IO.Path]::GetFullPath($Path)
    $stream=[IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
        $memory=New-Object IO.MemoryStream
        try {$stream.CopyTo($memory);$bytes=$memory.ToArray()} finally {$memory.Dispose()}
        $utf8=[Text.UTF8Encoding]::new($false,$true)
        $text=$utf8.GetString($bytes)
        if($text.Length -gt 0 -and $text[0] -eq [char]0xfeff){$text=$text.Substring(1)}
        return [pscustomobject]@{path=$full;stream=$stream;bytes=$bytes;sha256=(Get-Sha256FromBytes $bytes);text=$text}
    } catch {$stream.Dispose();throw}
}

function Open-StableJsonLock([string]$Path,[string]$ExpectedSha,[string]$Label) {
    $locked=Open-StableReadLock $Path
    try {
        if($locked.sha256 -ne $ExpectedSha.ToLowerInvariant()){throw "$Label does not match the operator-supplied SHA-256"}
        $data=$locked.text|ConvertFrom-Json -ErrorAction Stop
        $locked|Add-Member -NotePropertyName data -NotePropertyValue $data
        return $locked
    } catch {$locked.stream.Dispose();throw}
}

function Write-Lifecycle([hashtable]$Event) {
    $Event.timestamp=(Get-Date).ToString('o')
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Event|ConvertTo-Json -Compress -Depth 12)+[Environment]::NewLine)
    for($attempt=1;$attempt -le 50;$attempt++){
        $stream=$null
        try {
            $stream=[IO.File]::Open($lifecycle,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::Read)
            $stream.Write($bytes,0,$bytes.Length)
            $stream.Flush($true)
            return
        } catch [IO.IOException] {
            if($attempt -eq 50){throw}
            Start-Sleep -Milliseconds 100
        } finally {
            if($null -ne $stream){$stream.Dispose()}
        }
    }
}

function Get-StableAcPowerFacts {
    $batteryStatus=@(Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction Stop)
    $active=@($batteryStatus|Where-Object{$_.Active -eq $true})
    if(!$active){throw 'No active battery'}
    foreach($item in $active){if($item.PowerOnline -ne $true -or $item.Critical -ne $false){throw 'Battery is not stable AC/noncritical'}}
    $win32=@(Get-CimInstance Win32_Battery -ErrorAction Stop)
    if(!$win32){throw 'Win32_Battery unavailable'}
    foreach($item in $win32){if($null -eq $item.EstimatedChargeRemaining -or [double]$item.EstimatedChargeRemaining -le 0 -or @(2,3,6,7,8,11) -notcontains [int]$item.BatteryStatus){throw 'Battery charge status is not AC-compatible'}}
    return [pscustomobject]@{battery_status=$batteryStatus;win32_battery=$win32}
}

function Get-ObservedChildState {
    return @($children|ForEach-Object{
        $execution=Join-Path (Join-Path (Join-Path $bulkRoot 'runs') $_) 'execution.json'
        [pscustomobject]@{run_id=$_;run_directory_exists=(Test-Path -LiteralPath (Split-Path -Parent $execution));execution_exists=(Test-Path -LiteralPath $execution)}
    })
}

function Assert-Gate($Gate) {
    if($Gate.schema_version -ne 1 -or $Gate.status -ne 'pass' -or $Gate.fresh_launch_authorized -ne $true -or $Gate.publication_is_not_launch -ne $true){throw 'Canonical r11 gate status failed'}
    if($Gate.run_id_prefix -ne $prefix -or (@($Gate.seeds) -join '|') -ne ($seeds -join '|') -or (@($Gate.expected_children) -join '|') -ne ($children -join '|')){throw 'Canonical r11 identity binding failed'}
    $protocol=$Gate.protocol
    if($protocol.protocol_id -ne 'PAPER_TEXT_V1' -or $protocol.stage3_stability_adaptation_id -ne 'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1' -or [double]$protocol.stage3_gradient_clip_norm -ne 1.0 -or $protocol.stage3_gradient_clip_application_point -ne 'after_effective_batch_average_before_optimizer_step' -or [int]$protocol.stage3_gradient_accumulation_steps -ne 128 -or [int]$protocol.stage3_effective_batch -ne 128 -or [int]$protocol.stage3_hardware_microbatch -ne 1 -or [double]$protocol.stage3_learning_rate -ne 0.1){throw 'Canonical r11 protocol binding failed'}
    $durable=$Gate.durable_supervisor
    if($durable.design_id -ne 'R11_SYSTEMD_WINDOWS_LOCKHOLDER_V1' -or $durable.systemd_restart -ne 'no' -or $durable.systemd_collect -ne $true -or $durable.windows_lockholder_required -ne $true -or $durable.atomic_wsl_exit_evidence_required -ne $true){throw 'Canonical r11 durable-supervisor binding failed'}
    if($Gate.exactly_once.dispatch_marker -ne $dispatchMarker -or $Gate.exactly_once.attempt_marker -ne $attemptMarker -or $Gate.exactly_once.file_mode -ne 'CreateNew' -or $Gate.exactly_once.file_share -ne 'None' -or $Gate.exactly_once.no_retry_resume_reuse -ne $true){throw 'Canonical r11 exactly-once binding failed'}
    if($Gate.launch_test_evidence.status -ne 'pass' -or $Gate.launch_test_evidence.pilot_launched -ne $false -or [string]$Gate.launch_test_evidence.sha256 -notmatch '^[0-9a-f]{64}$'){throw 'Canonical r11 launch-test evidence failed'}
    $reviews=@($Gate.reviewer_bindings)
    if($reviews.Count -ne 2 -or $reviews[0].status -ne 'no_material_finding' -or $reviews[1].status -ne 'no_material_finding' -or $reviews[0].review_id -eq $reviews[1].review_id -or $reviews[0].agent_id -eq $reviews[1].agent_id){throw 'Canonical r11 distinct review binding failed'}
}

function Assert-Confirmation($Confirmation,[string]$GateSha) {
    $excerptBytes=[Text.Encoding]::UTF8.GetBytes([string]$Confirmation.exact_user_excerpt)
    $digest=Get-Sha256FromBytes $excerptBytes
    if($Confirmation.schema_version -ne 1 -or $Confirmation.status -ne 'confirmed' -or $Confirmation.run_id_prefix -ne $prefix -or $Confirmation.source_thread_id -ne $sourceThreadId){throw 'r11 confirmation identity failed'}
    if((@($Confirmation.seeds) -join '|') -ne ($seeds -join '|') -or (@($Confirmation.expected_children) -join '|') -ne ($children -join '|')){throw 'r11 confirmation seeds or children failed'}
    if($Confirmation.user_message_hash_encoding -ne 'utf-8-no-bom-of-json-decoded-exact_user_excerpt' -or $Confirmation.user_message_sha256 -ne $digest -or $Confirmation.canonical_gate_sha256 -ne $GateSha){throw 'r11 confirmation digest or gate binding failed'}
    if($Confirmation.user_explicitly_requested_fresh_r11_exactly_once -ne $true -or $Confirmation.exactly_once_launch_authorized -ne $true -or $Confirmation.permanent_dispatch_marker_consumption_accepted -ne $true -or $Confirmation.permanent_attempt_marker_consumption_accepted -ne $true -or $Confirmation.no_retry_after_marker_consumption_accepted -ne $true -or $Confirmation.no_resume_or_reuse -ne $true -or $Confirmation.confirmation_revoked -ne $false){throw 'r11 confirmation semantics failed'}
}

try {
    $gateLock=Open-StableJsonLock $gatePath $ExpectedCanonicalGateSha256 'Canonical r11 gate'
    $confirmationLock=Open-StableJsonLock $confirmationPath $ExpectedUserConfirmationSha256 'r11 confirmation'
    $heldReadLocks+=@($gateLock.stream,$confirmationLock.stream)
    $gate=$gateLock.data
    $confirmation=$confirmationLock.data
    Assert-Gate $gate
    Assert-Confirmation $confirmation $gateLock.sha256

    if(!(Test-Path -LiteralPath $dispatchCapability)){throw 'Immutable r11 dispatch capability is absent'}
    $capabilityLock=Open-StableReadLock $dispatchCapability;$heldReadLocks+=@($capabilityLock.stream)
    $capability=$capabilityLock.text|ConvertFrom-Json -ErrorAction Stop
    $nonceDigest=Get-Sha256FromBytes ([Text.Encoding]::UTF8.GetBytes($ExpectedDispatchNonce))
    if($capability.schema_version -ne 1 -or $capability.run_id_prefix -ne $prefix -or $capability.unit_name -ne [string]$gate.durable_supervisor.unit_name -or $capability.canonical_gate_sha256 -ne $gateLock.sha256 -or $capability.user_confirmation_sha256 -ne $confirmationLock.sha256 -or $capability.dispatch_nonce_sha256 -ne $nonceDigest){throw 'r11 dispatch capability validation failed'}

    $bindingNames=@{}
    foreach($binding in @($gate.source_bindings)){
        $name=[string]$binding.name
        $path=[string]$binding.path
        $expected=[string]$binding.sha256
        if([string]::IsNullOrWhiteSpace($name) -or $bindingNames.ContainsKey($name) -or $expected -notmatch '^[0-9a-f]{64}$'){throw 'Invalid or duplicate r11 source binding'}
        $bindingNames[$name]=$true
        $locked=Open-StableReadLock $path
        if($locked.sha256 -ne $expected){$locked.stream.Dispose();throw "Gate-bound source changed: $name"}
        $heldReadLocks+=@($locked.stream)
        $lockedFiles[$locked.path.ToLowerInvariant()]=$locked
    }
    $requiredBindings=@('dispatcher_ps1','lockholder_ps1','supervisor_sh','runner_sh','lean_team_contract_json','launch_test_evidence_json','review_evidence_json','r10_infrastructure_abort_evidence_json','r10_stability_protocol_json','r10_stability_implementation_evidence_json')
    foreach($name in $requiredBindings){if(!$bindingNames.ContainsKey($name)){throw "Required r11 binding absent: $name"}}
    foreach($property in $confirmation.source_sha256.PSObject.Properties){
        if(!$bindingNames.ContainsKey($property.Name)){throw "Confirmation source binding absent from gate: $($property.Name)"}
        $gateBinding=@($gate.source_bindings|Where-Object{$_.name -eq $property.Name})
        if($gateBinding.Count -ne 1 -or [string]$gateBinding[0].sha256 -ne [string]$property.Value){throw "Confirmation source hash mismatch: $($property.Name)"}
    }

    if(!(Test-Path -LiteralPath $dispatchMarker)){throw 'Permanent r11 dispatch marker is absent'}
    $self=Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
    $parent=Get-CimInstance Win32_Process -Filter ("ProcessId="+$self.ParentProcessId) -ErrorAction Stop
    if($parent.Name -ne 'wslhost.exe'){throw 'r11 lock holder is not owned by WSL systemd interop'}
    foreach($path in @($attemptMarker,$stdout,$stderr,$lifecycle,$ready,$workloadExitEvidence)+($children|ForEach-Object{Join-Path (Join-Path $bulkRoot 'runs') $_})){
        if(Test-Path -LiteralPath $path){throw "r11 evidence, log, marker, or child collision: $path"}
    }
    $gpu=Get-CimInstance Win32_VideoController|Where-Object{$_.Name -match 'NVIDIA'}|Select-Object -First 1
    if(!$gpu -or $gpu.DriverVersion -ne [string]$gate.gpu_gate.windows_driver_version -or $gpu.Status -ne 'OK'){throw 'r11 GPU gate failed'}
    if((Get-PSDrive C).Free/1GB -lt [double]$gate.storage_gate.c_minimum_gib -or (Get-PSDrive E).Free/1GB -lt [double]$gate.storage_gate.e_minimum_gib){throw 'r11 storage gate failed'}
    $cacheLocked=$lockedFiles[[IO.Path]::GetFullPath($cacheManifest).ToLowerInvariant()]
    $validatorLocked=$lockedFiles[[IO.Path]::GetFullPath($validatorLog).ToLowerInvariant()]
    if(!$cacheLocked -or !$validatorLocked -or $cacheLocked.sha256 -ne [string]$gate.cache_gate.sha256 -or $validatorLocked.sha256 -ne [string]$gate.cache_gate.validator_v2_log_sha256){throw 'r11 cache gate binding failed'}
    $validatorEvents=@($validatorLocked.text -split '\r?\n'|ForEach-Object{if(![string]::IsNullOrWhiteSpace($_)){try{$_|ConvertFrom-Json -ErrorAction Stop}catch{}}}|Where-Object{$_.status})
    if(!$validatorEvents -or $validatorEvents[-1].status -ne 'valid' -or $validatorEvents[-1].cache_manifest_sha256 -ne $cacheLocked.sha256){throw 'r11 cache validator status failed'}
    $existing=Get-CimInstance Win32_Process|Where-Object{$_.ProcessId -ne $PID -and $_.CommandLine -and ($_.CommandLine -match 'paper_faithful\.training\.cli (pilot|multi-seed-pilot)' -or $_.CommandLine -match 'run_paper_text_(pilot|multiseed)')}
    if($existing){throw 'A Windows single-pilot or multi-seed process already exists'}
    $power=Get-StableAcPowerFacts
    try {$attemptStream=[IO.File]::Open($attemptMarker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)} catch [IO.IOException] {throw 'Permanent r11 attempt marker collision'}
    Write-Lifecycle @{event='attempt_created';run_id_prefix=$prefix;children=$children;seeds=$seeds;canonical_gate_sha256=$gateLock.sha256;user_confirmation_sha256=$confirmationLock.sha256;dispatch_nonce_sha256=$nonceDigest;dispatch_capability=$dispatchCapability;dispatch_capability_sha256=$capabilityLock.sha256;dispatch_marker=$dispatchMarker;attempt_marker=$attemptMarker;lockholder_parent=$parent.Name;stable_ac_power=$power;gpu_name=$gpu.Name;gpu_driver=$gpu.DriverVersion}
    Write-Lifecycle @{event='launch_requested';run_id_prefix=$prefix;stable_ac_power=$power;gpu_name=$gpu.Name;gpu_driver=$gpu.DriverVersion}

    $readyTemp=$ready+'.tmp'
    [IO.File]::WriteAllText($readyTemp,(@{status='ready';run_id_prefix=$prefix;lockholder_pid=$PID;dispatch_nonce=$ExpectedDispatchNonce;timestamp=(Get-Date).ToString('o')}|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $readyTemp -Destination $ready -ErrorAction Stop
    Write-Lifecycle @{event='stable_locks_ready';run_id_prefix=$prefix;lockholder_pid=$PID}

    $deadline=(Get-Date).AddHours(48)
    while(!(Test-Path -LiteralPath $workloadExitEvidence) -and (Get-Date) -lt $deadline){Start-Sleep -Seconds 1}
    if(!(Test-Path -LiteralPath $workloadExitEvidence)){throw 'Atomic r11 workload exit evidence absent after timeout'}
    $exitText=(Get-Content -LiteralPath $workloadExitEvidence -Raw).Trim()
    $workloadExitCode=0
    if(![int]::TryParse($exitText,[ref]$workloadExitCode)){throw 'Atomic r11 workload exit evidence invalid'}
    Write-Lifecycle @{event='process_exited';run_id_prefix=$prefix;exit_code=$workloadExitCode;exit_code_source='atomic_wsl_evidence';stdout_bytes=$(if(Test-Path -LiteralPath $stdout){(Get-Item -LiteralPath $stdout).Length}else{$null});stderr_bytes=$(if(Test-Path -LiteralPath $stderr){(Get-Item -LiteralPath $stderr).Length}else{$null});child_state=(Get-ObservedChildState)}

    if($workloadExitCode -ne 0){Write-Lifecycle @{event='terminal_validation_failed';run_id_prefix=$prefix;exit_code=$workloadExitCode;reason='r11 workload returned nonzero';child_state=(Get-ObservedChildState)};exit $workloadExitCode}
    $terminal=$null
    foreach($line in @(Get-Content -LiteralPath $stdout -ErrorAction SilentlyContinue)){try{$candidate=$line|ConvertFrom-Json;if($candidate.status){$terminal=$candidate}}catch{}}
    if(!$terminal -or $terminal.status -ne 'completed' -or $terminal.mode -ne 'multi-seed-pilot' -or @($terminal.children).Count -ne 2){throw 'r11 runner did not return completed two-child terminal JSON'}
    for($index=0;$index -lt 2;$index++){
        if($terminal.children[$index].run_id -ne $children[$index] -or $terminal.children[$index].verification.status -ne 'verified'){throw 'r11 terminal child verification binding failed'}
    }
    $childState=Get-ObservedChildState
    if(@($childState|Where-Object{-not $_.execution_exists}).Count){throw 'An r11 terminal child is missing execution.json'}
    Write-Lifecycle @{event='terminal_validated';run_id_prefix=$prefix;exit_code=0;terminal_children=$terminal.children;child_state=$childState}
    exit 0
} catch {
    if($null -ne $attemptStream){try{Write-Lifecycle @{event='terminal_validation_failed';run_id_prefix=$prefix;exit_code=92;reason=$_.Exception.Message;child_state=(Get-ObservedChildState)}}catch{}}
    exit 92
} finally {
    if($null -ne $attemptStream){$attemptStream.Dispose()}
    for($index=$heldReadLocks.Count-1;$index -ge 0;$index--){try{$heldReadLocks[$index].Dispose()}catch{}}
}
