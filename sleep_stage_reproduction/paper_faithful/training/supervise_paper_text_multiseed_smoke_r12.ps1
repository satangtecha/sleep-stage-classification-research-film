param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedCanonicalGateSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedUserConfirmationSha256,
    [Parameter(Mandatory=$true)][ValidatePattern('^SleepStagePaper-r12-COM-[0-9a-f]{32}$')][string]$TaskName
)

$ErrorActionPreference='Stop'
$bulkRoot='E:\blp\sleep_stage_reproduction'; $prefix='paper-text-v1-multiseed-cap128-r12-20260830'
$seeds=@(42,43); $children=@("$prefix-split42-model42","$prefix-split43-model43")
$runtime=Join-Path $bulkRoot 'runtime'; $logRoot=Join-Path $runtime 'training-logs'
$gatePath=Join-Path $runtime 'driver-recovery\canonical-r12-multiseed-launch-gate-20260830.json'
$confirmationPath=Join-Path $runtime 'driver-recovery\r12-explicit-user-launch-confirmation-20260830.json'
$dispatchMarker=Join-Path $logRoot "$prefix.dispatch.lock"; $attemptMarker=Join-Path $logRoot "$prefix.launch.lock"
$lifecycle=Join-Path $logRoot "$prefix.lifecycle.jsonl"; $stdout=Join-Path $logRoot "$prefix.stdout.log"; $stderr=Join-Path $logRoot "$prefix.stderr.log"
$exitEvidence=Join-Path $logRoot "$prefix.workload-exit-code.txt"; $runnerWsl='./paper_faithful/training/run_paper_text_multiseed_smoke_r12.sh'
$dispatcherPath=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'launch_paper_text_multiseed_smoke_r12.ps1'))
$supervisorPath=[IO.Path]::GetFullPath($PSCommandPath)
$runnerPath=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'run_paper_text_multiseed_smoke_r12.sh'))
$cacheManifestPath=[IO.Path]::GetFullPath((Join-Path $bulkRoot 'sst_cache\paper_faithful_v3_full_20260820\sst_full_cohort_run_manifest.json'))
$cacheValidatorPath=[IO.Path]::GetFullPath((Join-Path $runtime 'integrity-logs\full-cache-validation-v2.stdout.log'))
$held=@(); $attemptStream=$null

function Get-Sha([byte[]]$Bytes) { $h=[Security.Cryptography.SHA256]::Create();try{return -join($h.ComputeHash($Bytes)|%{$_.ToString('x2')})}finally{$h.Dispose()} }
function Open-Stable([string]$Path) { $s=[IO.File]::Open([IO.Path]::GetFullPath($Path),[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read);try{$m=New-Object IO.MemoryStream;try{$s.CopyTo($m);$b=$m.ToArray()}finally{$m.Dispose()};$t=[Text.UTF8Encoding]::new($false,$true).GetString($b);if($t.Length -and $t[0]-eq[char]0xfeff){$t=$t.Substring(1)};[pscustomobject]@{stream=$s;sha256=(Get-Sha $b);text=$t;path=[IO.Path]::GetFullPath($Path)}}catch{$s.Dispose();throw} }
function Write-Life([hashtable]$Event) { $Event.timestamp=(Get-Date).ToString('o');$b=[Text.UTF8Encoding]::new($false).GetBytes(($Event|ConvertTo-Json -Compress -Depth 12)+[Environment]::NewLine);$s=[IO.File]::Open($lifecycle,[IO.FileMode]::Append,[IO.FileAccess]::Write,[IO.FileShare]::Read);try{$s.Write($b,0,$b.Length);$s.Flush($true)}finally{$s.Dispose()} }
function Read-Exit { if(!(Test-Path -LiteralPath $exitEvidence)){throw 'Atomic WSL exit evidence is absent'};$v=0;if(![int]::TryParse((Get-Content -LiteralPath $exitEvidence -Raw).Trim(),[ref]$v)){throw 'Atomic WSL exit evidence is invalid'};return $v }
function Wait-AtomicTerminal([Diagnostics.Process]$Process) {
    $hostGoneAt=$null;$atomicSeenAt=$null
    while($true){
        $now=Get-Date;$hostPresent=[bool](Get-Process -Id $Process.Id -ErrorAction SilentlyContinue);$atomicPresent=Test-Path -LiteralPath $exitEvidence
        if($atomicPresent -and $null-eq$atomicSeenAt){$atomicSeenAt=$now}
        if(-not$hostPresent -and $null-eq$hostGoneAt){$hostGoneAt=$now}
        if($atomicPresent -and -not$hostPresent){break}
        if($null-ne$hostGoneAt -and $now-gt$hostGoneAt.AddSeconds(60)){throw 'Atomic WSL exit evidence absent after Windows host exit'}
        if($null-ne$atomicSeenAt -and $now-gt$atomicSeenAt.AddSeconds(60)){throw 'Windows WSL host remained after atomic exit evidence'}
        Start-Sleep -Seconds 1
    }
    $Process.Refresh();if(-not$Process.HasExited){throw 'Windows WSL host absence could not be confirmed'}
    try {$hostExit=[int]$Process.ExitCode} catch {throw 'Windows WSL host exit code unavailable'}
    return [pscustomobject]@{windows_host_exited=$true;windows_host_exit_code=$hostExit;atomic_seen_at=$atomicSeenAt.ToString('o');host_gone_at=$hostGoneAt.ToString('o')}
}
function Child-State { @($children|%{$e=Join-Path (Join-Path (Join-Path $bulkRoot 'runs') $_) 'execution.json';[pscustomobject]@{run_id=$_;run_directory_exists=(Test-Path (Split-Path $e));execution_exists=(Test-Path $e) }}) }
function To-WslPath([string]$Path) { $full=[IO.Path]::GetFullPath($Path);if($full -notmatch '^([A-Za-z]):\\(.*)$'){throw "Unsupported Windows path: $Path"};return '/mnt/'+$Matches[1].ToLowerInvariant()+'/'+$Matches[2].Replace('\\','/') }
function Assert-Power { $b=@(Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus);$a=@($b|?{$_.Active -eq $true});if(!$a){throw 'No active battery'};foreach($x in $a){if($x.PowerOnline-ne$true -or $x.Critical-ne$false){throw 'Battery is not stable AC/noncritical'}} }
function Assert-Gpu { param($Gate);$g=Get-CimInstance Win32_VideoController|?{$_.Name-match'NVIDIA'}|Select-Object -First 1;if(!$g -or $g.Status-ne'OK' -or $g.DriverVersion-ne[string]$Gate.gpu_gate.windows_driver_version){throw 'Windows GPU gate failed'};$w=& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc 'nvidia-smi -L' 2>&1;if($LASTEXITCODE-ne 0 -or !$w){throw 'WSL GPU gate failed'};return $g }

try {
    $gateLock=Open-Stable $gatePath;$confirmationLock=Open-Stable $confirmationPath;$held+=@($gateLock.stream,$confirmationLock.stream)
    if($gateLock.sha256-ne$ExpectedCanonicalGateSha256.ToLowerInvariant() -or $confirmationLock.sha256-ne$ExpectedUserConfirmationSha256.ToLowerInvariant()){throw 'Operator-supplied gate or confirmation SHA mismatch'}
    $gate=$gateLock.text|ConvertFrom-Json;$confirmation=$confirmationLock.text|ConvertFrom-Json
    if($gate.status-ne'pass' -or $gate.fresh_launch_authorized-ne$true -or $gate.run_id_prefix-ne$prefix -or (@($gate.seeds)-join'|')-ne($seeds-join'|') -or (@($gate.expected_children)-join'|')-ne($children-join'|')){throw 'Canonical r12 gate identity failed'}
    if($gate.protocol.stage3_stability_adaptation_id-ne'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1' -or [double]$gate.protocol.stage3_gradient_clip_norm-ne1.0 -or [int]$gate.protocol.stage3_gradient_accumulation_steps-ne128 -or $gate.protocol.stage3_gradient_clip_application_point-ne'after_effective_batch_average_before_optimizer_step'){throw 'Canonical r12 protocol binding failed'}
    $excerptBytes=[Text.UTF8Encoding]::new($false).GetBytes([string]$confirmation.exact_user_excerpt)
    if($confirmation.schema_version-ne1 -or $confirmation.artifact_type-ne'explicit_user_launch_confirmation' -or $confirmation.status-ne'confirmed' -or $confirmation.run_id_prefix-ne$prefix -or (@($confirmation.seeds)-join'|')-ne($seeds-join'|') -or (@($confirmation.expected_children)-join'|')-ne($children-join'|') -or $confirmation.canonical_gate_sha256-ne$gateLock.sha256 -or $confirmation.user_message_hash_encoding-ne'utf-8-no-bom-of-json-decoded-exact_user_excerpt' -or $confirmation.user_message_sha256-ne(Get-Sha $excerptBytes) -or $confirmation.stage3_stability_adaptation_id-ne'PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1' -or [double]$confirmation.stage3_gradient_clip_norm-ne1.0 -or [int]$confirmation.stage3_gradient_accumulation_steps-ne128 -or $confirmation.user_explicitly_requested_fresh_r12_exactly_once-ne$true -or $confirmation.confirmation_revoked-ne$false -or $confirmation.exactly_once_launch_authorized-ne$true -or $confirmation.permanent_dispatch_marker_consumption_accepted-ne$true -or $confirmation.permanent_attempt_marker_consumption_accepted-ne$true -or $confirmation.no_retry_after_marker_consumption_accepted-ne$true -or $confirmation.no_resume_or_reuse-ne$true){throw 'r12 confirmation binding failed'}
    $expectedPaths=@{dispatcher_ps1=$dispatcherPath;supervisor_ps1=$supervisorPath;runner_sh=$runnerPath;cache_manifest_json=$cacheManifestPath;cache_validator_log=$cacheValidatorPath}
    $bindings=@{}
    foreach($b in @($gate.source_bindings)){
        $name=[string]$b.name;$path=[IO.Path]::GetFullPath([string]$b.path)
        if($bindings.ContainsKey($name) -or [string]$b.sha256-notmatch'^[0-9a-f]{64}$'){throw 'Invalid r12 source binding'}
        if($expectedPaths.ContainsKey($name) -and -not $path.Equals([string]$expectedPaths[$name],[StringComparison]::OrdinalIgnoreCase)){throw "Gate-bound source path changed: $name"}
        $l=Open-Stable $path;if($l.sha256-ne[string]$b.sha256){$l.stream.Dispose();throw "Gate-bound source changed: $name"};$held+=$l.stream;$bindings[$name]=$l
    }
    foreach($n in $expectedPaths.Keys){if(!$bindings.ContainsKey($n)){throw "Required r12 source binding absent: $n"}}
    $confirmationBindings=@{};foreach($p in $confirmation.source_sha256.PSObject.Properties){if($confirmationBindings.ContainsKey($p.Name) -or [string]$p.Value-notmatch'^[0-9a-f]{64}$'){throw 'Invalid confirmation source binding'};$confirmationBindings[$p.Name]=[string]$p.Value}
    if($confirmationBindings.Count-ne$bindings.Count){throw 'Confirmation source binding closure is incomplete'}
    foreach($name in $bindings.Keys){if(!$confirmationBindings.ContainsKey($name) -or $bindings[$name].sha256-ne$confirmationBindings[$name]){throw "Confirmation source binding failed: $name"}}
    if($bindings.cache_manifest_json.sha256-ne[string]$gate.cache_gate.sha256 -or $bindings.cache_validator_log.sha256-ne[string]$gate.cache_gate.validator_v2_log_sha256){throw 'Cache binding failed'}
    $events=@($bindings.cache_validator_log.text-split'\r?\n'|%{if($_){try{$_|ConvertFrom-Json}catch{}}}|?{$_.status});if(!$events -or $events[-1].status-ne'valid' -or $events[-1].cache_manifest_sha256-ne$bindings.cache_manifest_json.sha256){throw 'Cache validator evidence failed'}
    foreach($p in @($attemptMarker,$lifecycle,$stdout,$stderr,$exitEvidence)+($children|%{Join-Path (Join-Path $bulkRoot 'runs') $_})){if(Test-Path -LiteralPath $p){throw "r12 namespace collision: $p"}}
    $self=Get-CimInstance Win32_Process -Filter "ProcessId=$PID" -ErrorAction Stop;$parent=Get-Process -Id ([int]$self.ParentProcessId) -ErrorAction Stop;if(($parent.ProcessName+'.exe')-ne'svchost.exe'){throw 'r12 supervisor is not owned by Task Scheduler svchost.exe'}
    $existing=Get-CimInstance Win32_Process|?{$_.ProcessId-ne$PID -and $_.CommandLine -and $_.CommandLine-match'paper_faithful\.training\.cli (pilot|multi-seed-pilot)'};if($existing){throw 'Windows training process collision'}
    $native=& wsl.exe -d Ubuntu -e bash --noprofile --norc -lc "pgrep -af '[p]aper_faithful.training.cli (pilot|multi-seed-pilot)' || true";if($native){throw 'WSL training process collision'}
    Assert-Power;$gpu=Assert-Gpu $gate;if((Get-PSDrive C).Free/1GB-lt[double]$gate.storage_gate.c_minimum_gib -or (Get-PSDrive E).Free/1GB-lt[double]$gate.storage_gate.e_minimum_gib){throw 'Storage gate failed'}
    $attemptStream=[IO.File]::Open($attemptMarker,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    Write-Life @{event='supervisor_started';run_id_prefix=$prefix;task_name=$TaskName;supervisor_pid=$PID;parent_process='svchost.exe';canonical_gate_sha256=$gateLock.sha256;user_confirmation_sha256=$confirmationLock.sha256;gpu_name=$gpu.Name;gpu_driver=$gpu.DriverVersion}
    $stdoutWsl=To-WslPath $stdout;$stderrWsl=To-WslPath $stderr;$exitWsl=To-WslPath $exitEvidence
    $wrapper=('cd ''/mnt/c/Users/Acer/OneDrive/Documents/เป้าๆรวยๆๆๆ/sleep_stage_reproduction'' || exit 73; set +e; {0} > ''{1}'' 2> ''{2}''; rc=$?; tmp=''{3}.tmp.$$''; printf ''%s\n'' "$rc" > "$tmp"; mv -f -- "$tmp" ''{3}''; exit "$rc"' -f $runnerWsl,$stdoutWsl,$stderrWsl,$exitWsl)
    $child=Start-Process -FilePath "$env:SystemRoot\System32\wsl.exe" -ArgumentList @('-d','Ubuntu','-e','bash','--noprofile','--norc','-lc',$wrapper) -WorkingDirectory (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path -WindowStyle Hidden -PassThru
    Write-Life @{event='process_started';run_id_prefix=$prefix;supervisor_pid=$PID;child_pid=$child.Id;child_kind='wsl.exe'};$terminalBarrier=Wait-AtomicTerminal $child;$atomic=Read-Exit;Write-Life @{event='process_exited';run_id_prefix=$prefix;supervisor_pid=$PID;child_pid=$child.Id;exit_code=$atomic;exit_code_source='atomic_wsl_evidence';windows_host_exited=$terminalBarrier.windows_host_exited;windows_host_exit_code=$terminalBarrier.windows_host_exit_code;atomic_seen_at=$terminalBarrier.atomic_seen_at;windows_host_gone_at=$terminalBarrier.host_gone_at;child_state=(Child-State)}
    if($atomic-ne0-or[int]$terminalBarrier.windows_host_exit_code-ne$atomic){throw "Runner/Windows host exit mismatch: atomic=$atomic host=$($terminalBarrier.windows_host_exit_code)"};$terminal=$null;foreach($line in @(Get-Content -LiteralPath $stdout)){try{$x=$line|ConvertFrom-Json;if($x.status){$terminal=$x}}catch{}};if(!$terminal -or $terminal.status-ne'completed' -or $terminal.mode-ne'multi-seed-pilot' -or @($terminal.children).Count-ne2){throw 'Runner terminal JSON is invalid'};for($i=0;$i-lt2;$i++){if($terminal.children[$i].run_id-ne$children[$i] -or $terminal.children[$i].verification.status-ne'verified'){throw 'Terminal child binding failed'}};$state=Child-State;if(@($state|?{-not $_.execution_exists}).Count){throw 'Terminal child execution evidence missing'};Write-Life @{event='terminal_validated';run_id_prefix=$prefix;exit_code=0;terminal_children=$terminal.children;child_state=$state};exit 0
} catch { if($attemptStream){try{Write-Life @{event='terminal_validation_failed';run_id_prefix=$prefix;exit_code=92;reason=$_.Exception.Message;child_state=(Child-State)}}catch{}};exit 92
} finally {if($attemptStream){$attemptStream.Dispose()};for($i=$held.Count-1;$i-ge0;$i--){try{$held[$i].Dispose()}catch{}};try{$scheduler=New-Object -ComObject 'Schedule.Service';$scheduler.Connect();$scheduler.GetFolder('\').DeleteTask($TaskName,0)}catch{}}
