param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedCanonicalGateSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedUserConfirmationSha256
)

$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$bulkRoot='E:\blp\sleep_stage_reproduction'
$prefix='paper-text-v1-multiseed-cap128-r11-20260830'
$seeds=@(42,43)
$children=@("$prefix-split42-model42","$prefix-split43-model43")
$sourceThreadId='01a014bc-7bc1-7590-bd2b-029c8a84285b'
$unitName='sleep-stage-r11-paper-text-multiseed-cap128-20260830.service'
$runtime=Join-Path $bulkRoot 'runtime'
$logRoot=Join-Path $runtime 'training-logs'
$gatePath=Join-Path $runtime 'driver-recovery\canonical-r11-multiseed-launch-gate-20260830.json'
$confirmationPath=Join-Path $runtime 'driver-recovery\r11-explicit-user-launch-confirmation-20260830.json'
$dispatchMarker=Join-Path $logRoot "$prefix.dispatch.lock"
$dispatchCapability=Join-Path $logRoot "$prefix.dispatch-capability.json"
$attemptMarker=Join-Path $logRoot "$prefix.launch.lock"
$dispatchLifecycle=Join-Path $logRoot "$prefix.dispatch.lifecycle.jsonl"
$dispatchEvidence=Join-Path $logRoot "$prefix.dispatch.json"
$lifecycle=Join-Path $logRoot "$prefix.lifecycle.jsonl"
$ready=Join-Path $logRoot "$prefix.lockholder-ready.json"
$stdout=Join-Path $logRoot "$prefix.stdout.log"
$stderr=Join-Path $logRoot "$prefix.stderr.log"
$workloadExitEvidence=Join-Path $logRoot "$prefix.workload-exit-code.txt"
$supervisorWsl='./paper_faithful/training/supervise_paper_text_multiseed_smoke_r11.sh'
$projectWsl='/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction'
$dispatchStream=$null
$heldReadLocks=@()

function Get-FileSha([string]$Path) {
    $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {$hash=[Security.Cryptography.SHA256]::Create();try{return -join($hash.ComputeHash($stream)|ForEach-Object{$_.ToString('x2')})}finally{$hash.Dispose()}}finally{$stream.Dispose()}
}

function Get-TextSha([string]$Text) {
    $bytes=[Text.Encoding]::UTF8.GetBytes($Text)
    $hash=[Security.Cryptography.SHA256]::Create()
    try {return -join($hash.ComputeHash($bytes)|ForEach-Object{$_.ToString('x2')})} finally {$hash.Dispose()}
}

function Open-StableReadLock([string]$Path) {
    $full=[IO.Path]::GetFullPath($Path)
    $stream=[IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
        $memory=New-Object IO.MemoryStream
        try {$stream.CopyTo($memory);$bytes=$memory.ToArray()} finally {$memory.Dispose()}
        $utf8=[Text.UTF8Encoding]::new($false,$true);$text=$utf8.GetString($bytes)
        if($text.Length -gt 0 -and $text[0] -eq [char]0xfeff){$text=$text.Substring(1)}
        $hash=[Security.Cryptography.SHA256]::Create();try{$sha=-join($hash.ComputeHash($bytes)|ForEach-Object{$_.ToString('x2')})}finally{$hash.Dispose()}
        return [pscustomobject]@{path=$full;stream=$stream;sha256=$sha;text=$text}
    } catch {$stream.Dispose();throw}
}

function Write-DispatchLifecycle([hashtable]$Event) {
    $Event.timestamp=(Get-Date).ToString('o')
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes(($Event|ConvertTo-Json -Compress -Depth 10)+[Environment]::NewLine)
    for($attempt=1;$attempt -le 50;$attempt++){
        $stream=$null
        try {
            $stream=[IO.File]::Open($dispatchLifecycle,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::Read)
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
    foreach($item in $win32){if($null -eq $item.EstimatedChargeRemaining -or [double]$item.EstimatedChargeRemaining -le 0 -or @(2,3,6,7,8,11) -notcontains [int]$item.BatteryStatus){throw 'Battery charge status is not AC-compatible'}}
    return [pscustomobject]@{battery_status=$batteryStatus;win32_battery=$win32}
}

function Get-UnitProperties {
    $saved=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    try {$lines=@(& wsl.exe -d Ubuntu -u root -e systemctl show $unitName --property=LoadState,ActiveState,SubState,MainPID,ExecMainCode,ExecMainStatus,Result,Restart --no-pager 2>&1|ForEach-Object{"$_"})} finally {$ErrorActionPreference=$saved}
    $values=@{}
    foreach($line in $lines){if($line -match '^([^=]+)=(.*)$'){$values[$Matches[1]]=$Matches[2]}}
    return $values
}

function Read-LifecycleEvents {
    if(!(Test-Path -LiteralPath $lifecycle)){return @()}
    try {return @(Get-Content -LiteralPath $lifecycle -ErrorAction Stop|ForEach-Object{if(![string]::IsNullOrWhiteSpace($_)){$_|ConvertFrom-Json -ErrorAction Stop}})} catch {return @()}
}

try {
    if(!(Test-Path -LiteralPath $gatePath)){throw 'Canonical r11 gate is absent'}
    if(!(Test-Path -LiteralPath $confirmationPath)){throw 'New r11 confirmation is absent'}
    $gateLock=Open-StableReadLock $gatePath;$confirmationLock=Open-StableReadLock $confirmationPath
    $heldReadLocks+=@($gateLock.stream,$confirmationLock.stream)
    $gateSha=$gateLock.sha256
    $confirmationSha=$confirmationLock.sha256
    if($gateSha -ne $ExpectedCanonicalGateSha256.ToLowerInvariant()){throw 'Canonical r11 gate SHA mismatch'}
    if($confirmationSha -ne $ExpectedUserConfirmationSha256.ToLowerInvariant()){throw 'r11 confirmation SHA mismatch'}
    $gate=$gateLock.text|ConvertFrom-Json -ErrorAction Stop
    $confirmation=$confirmationLock.text|ConvertFrom-Json -ErrorAction Stop
    if($gate.status -ne 'pass' -or $gate.fresh_launch_authorized -ne $true -or $gate.run_id_prefix -ne $prefix -or (@($gate.seeds)-join '|') -ne ($seeds-join '|') -or (@($gate.expected_children)-join '|') -ne ($children-join '|')){throw 'Canonical r11 gate identity failed'}
    if($gate.durable_supervisor.design_id -ne 'R11_SYSTEMD_WINDOWS_LOCKHOLDER_V1' -or $gate.durable_supervisor.systemd_restart -ne 'no'){throw 'Canonical r11 durable supervisor failed'}
    if($confirmation.status -ne 'confirmed' -or $confirmation.run_id_prefix -ne $prefix -or $confirmation.source_thread_id -ne $sourceThreadId -or (@($confirmation.seeds)-join '|') -ne ($seeds-join '|') -or (@($confirmation.expected_children)-join '|') -ne ($children-join '|')){throw 'r11 confirmation identity failed'}
    if($confirmation.canonical_gate_sha256 -ne $gateSha -or $confirmation.user_message_hash_encoding -ne 'utf-8-no-bom-of-json-decoded-exact_user_excerpt' -or $confirmation.user_message_sha256 -ne (Get-TextSha ([string]$confirmation.exact_user_excerpt))){throw 'r11 confirmation digest failed'}
    if($confirmation.user_explicitly_requested_fresh_r11_exactly_once -ne $true -or $confirmation.exactly_once_launch_authorized -ne $true -or $confirmation.permanent_dispatch_marker_consumption_accepted -ne $true -or $confirmation.permanent_attempt_marker_consumption_accepted -ne $true -or $confirmation.no_retry_after_marker_consumption_accepted -ne $true -or $confirmation.no_resume_or_reuse -ne $true -or $confirmation.confirmation_revoked -ne $false){throw 'r11 confirmation semantics failed'}
    foreach($property in $confirmation.source_sha256.PSObject.Properties){
        $binding=@($gate.source_bindings|Where-Object{$_.name -eq $property.Name})
        if($binding.Count -ne 1 -or [string]$binding[0].sha256 -ne [string]$property.Value){throw "r11 confirmation source binding failed: $($property.Name)"}
    }
    $sourceLocks=@{}
    foreach($binding in @($gate.source_bindings)){
        if([string]$binding.sha256 -notmatch '^[0-9a-f]{64}$' -or $sourceLocks.ContainsKey([string]$binding.name)){throw 'Invalid or duplicate r11 source binding before dispatch marker'}
        $locked=Open-StableReadLock ([string]$binding.path)
        if($locked.sha256 -ne [string]$binding.sha256){$locked.stream.Dispose();throw "Gate-bound source changed before dispatch marker: $($binding.name)"}
        $heldReadLocks+=@($locked.stream);$sourceLocks[[string]$binding.name]=$locked
    }
    foreach($required in @('dispatcher_ps1','lockholder_ps1','supervisor_sh','runner_sh','lean_team_contract_json','launch_test_evidence_json','review_evidence_json','cache_manifest_json','cache_validator_log')){if(!$sourceLocks.ContainsKey($required)){throw "Required pre-dispatch source binding absent: $required"}}
    if($sourceLocks.cache_manifest_json.sha256 -ne [string]$gate.cache_gate.sha256 -or $sourceLocks.cache_validator_log.sha256 -ne [string]$gate.cache_gate.validator_v2_log_sha256){throw 'Pre-dispatch cache hashes failed'}
    $validatorEvents=@($sourceLocks.cache_validator_log.text -split '\r?\n'|ForEach-Object{if(![string]::IsNullOrWhiteSpace($_)){try{$_|ConvertFrom-Json -ErrorAction Stop}catch{}}}|Where-Object{$_.status})
    if(!$validatorEvents -or $validatorEvents[-1].status -ne 'valid' -or $validatorEvents[-1].cache_manifest_sha256 -ne $sourceLocks.cache_manifest_json.sha256){throw 'Pre-dispatch cache validator failed'}

    foreach($path in @($dispatchMarker,$dispatchCapability,$attemptMarker,$dispatchLifecycle,$dispatchEvidence,$lifecycle,$ready,$stdout,$stderr,$workloadExitEvidence)+($children|ForEach-Object{Join-Path (Join-Path $bulkRoot 'runs') $_})){
        if(Test-Path -LiteralPath $path){throw "r11 dispatch collision: $path"}
    }
    $unit=Get-UnitProperties
    if($unit.LoadState -and $unit.LoadState -ne 'not-found'){throw "r11 systemd unit collision: $($unit.LoadState)/$($unit.ActiveState)"}
    $existing=Get-CimInstance Win32_Process|Where-Object{$_.ProcessId -ne $PID -and $_.CommandLine -and ($_.CommandLine -match 'paper_faithful\.training\.cli (pilot|multi-seed-pilot)' -or $_.CommandLine -match 'run_paper_text_(pilot|multiseed)')}
    if($existing){throw 'A Windows single-pilot or multi-seed process already exists'}
    $existingWsl=@(& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "pgrep -af '[p]aper_faithful.training.cli (pilot|multi-seed-pilot)' || true")
    if($existingWsl){throw 'A native WSL single-pilot or multi-seed process already exists'}
    $power=Get-StableAcPowerFacts
    $gpu=Get-CimInstance Win32_VideoController|Where-Object{$_.Name -match 'NVIDIA'}|Select-Object -First 1
    if(!$gpu -or $gpu.DriverVersion -ne [string]$gate.gpu_gate.windows_driver_version -or $gpu.Status -ne 'OK'){throw 'r11 dispatch GPU gate failed'}
    if((Get-PSDrive C).Free/1GB -lt [double]$gate.storage_gate.c_minimum_gib -or (Get-PSDrive E).Free/1GB -lt [double]$gate.storage_gate.e_minimum_gib){throw 'r11 dispatch storage gate failed'}

    New-Item -ItemType Directory -Path $logRoot -Force|Out-Null
    $nonceBytes=New-Object byte[] 32;$rng=[Security.Cryptography.RandomNumberGenerator]::Create();try{$rng.GetBytes($nonceBytes)}finally{$rng.Dispose()};$dispatchNonce=-join($nonceBytes|ForEach-Object{$_.ToString('x2')})
    $capability=[ordered]@{schema_version=1;run_id_prefix=$prefix;unit_name=$unitName;canonical_gate_sha256=$gateSha;user_confirmation_sha256=$confirmationSha;dispatch_nonce_sha256=(Get-TextSha $dispatchNonce);created_at=(Get-Date).ToString('o')}
    $capabilityBytes=[Text.UTF8Encoding]::new($false).GetBytes(($capability|ConvertTo-Json -Compress))
    $capabilityWrite=[IO.File]::Open($dispatchCapability,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);try{$capabilityWrite.Write($capabilityBytes,0,$capabilityBytes.Length);$capabilityWrite.Flush($true)}finally{$capabilityWrite.Dispose()}
    $capabilityLock=Open-StableReadLock $dispatchCapability;$heldReadLocks+=@($capabilityLock.stream)
    try {$dispatchStream=[IO.File]::Open($dispatchMarker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)} catch [IO.IOException] {throw 'Permanent r11 dispatch marker collision'}
    Write-DispatchLifecycle @{event='dispatch_created';run_id_prefix=$prefix;unit_name=$unitName;canonical_gate_sha256=$gateSha;user_confirmation_sha256=$confirmationSha;dispatch_nonce_sha256=(Get-TextSha $dispatchNonce);dispatch_capability=$dispatchCapability;dispatch_capability_sha256=$capabilityLock.sha256;dispatch_marker=$dispatchMarker;power=$power;gpu_name=$gpu.Name;gpu_driver=$gpu.DriverVersion}

    $systemdStdout=Join-Path $logRoot "$prefix.systemd-run.stdout.log"
    $systemdStderr=Join-Path $logRoot "$prefix.systemd-run.stderr.log"
    $arguments=@(
        '--unit',$unitName,
        '--property=User=techatat',
        '--property=Restart=no',
        '--property=Type=exec',
        '--property=KillMode=control-group',
        ("--property=WorkingDirectory="+$projectWsl),
        '--collect',
        '/bin/bash','--noprofile','--norc',$supervisorWsl,$gateSha,$confirmationSha,$dispatchNonce
    )
    $saved=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    try {& wsl.exe -d Ubuntu -u root -e systemd-run @arguments 1>$systemdStdout 2>$systemdStderr;$dispatchExit=$LASTEXITCODE} finally {$ErrorActionPreference=$saved}
    if($dispatchExit -ne 0){throw "systemd-run failed with exit code $dispatchExit"}
    Write-DispatchLifecycle @{event='systemd_dispatch_requested';run_id_prefix=$prefix;unit_name=$unitName;systemd_run_exit_code=$dispatchExit}

    $deadline=(Get-Date).AddMinutes(3)
    do {
        $readyEvents=@((Read-LifecycleEvents)|Where-Object{$_.event -eq 'stable_locks_ready'})
        if($readyEvents.Count -eq 1){break}
        Start-Sleep -Milliseconds 200
    } while((Get-Date) -lt $deadline)
    if($readyEvents.Count -ne 1){throw 'r11 lock holder did not publish stable_locks_ready'}
    $readyData=Get-Content -LiteralPath $ready -Raw|ConvertFrom-Json -ErrorAction Stop
    if($readyData.dispatch_nonce -ne $dispatchNonce){throw 'r11 lock-holder dispatch capability mismatch'}
    $activeUnit=Get-UnitProperties
    if($activeUnit.ActiveState -ne 'active' -or $activeUnit.Restart -ne 'no'){throw "r11 systemd unit is not active with Restart=no: $($activeUnit.ActiveState)/$($activeUnit.Restart)"}
    $evidence=[ordered]@{status='dispatched';run_id_prefix=$prefix;unit_name=$unitName;canonical_gate_sha256=$gateSha;user_confirmation_sha256=$confirmationSha;dispatch_marker=$dispatchMarker;attempt_marker=$attemptMarker;systemd_restart=$activeUnit.Restart;systemd_active_state=$activeUnit.ActiveState;systemd_main_pid=$activeUnit.MainPID;timestamp=(Get-Date).ToString('o')}
    [IO.File]::WriteAllText($dispatchEvidence,($evidence|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
    Write-DispatchLifecycle @{event='lockholder_handshake_validated';run_id_prefix=$prefix;unit_name=$unitName;lockholder_pid=$readyEvents[0].lockholder_pid}
    exit 0
} catch {
    if($null -ne $dispatchStream){try{Write-DispatchLifecycle @{event='dispatch_failed';run_id_prefix=$prefix;unit_name=$unitName;reason=$_.Exception.Message}}catch{}}
    exit 92
} finally {
    if($null -ne $dispatchStream){$dispatchStream.Dispose()}
    for($index=$heldReadLocks.Count-1;$index -ge 0;$index--){try{$heldReadLocks[$index].Dispose()}catch{}}
}
