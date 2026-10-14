param(
    [string]$DispatcherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r17.ps1'),
    [string]$SupervisorPath=(Join-Path $PSScriptRoot '..\supervise_paper_text_multiseed_smoke_r17.ps1'),
    [string]$NativeDllPath=(Join-Path $PSScriptRoot '..\r17_native_probe.dll')
)
$ErrorActionPreference='Stop'
$prefix='paper-text-v1-multiseed-cap128-r17-20260901'
$bulk='E:\blp\sleep_stage_reproduction'
$logs=Join-Path $bulk 'runtime\training-logs'
$production=@(
    (Join-Path $logs "$prefix.dispatch.lock"),
    (Join-Path $logs "$prefix.dispatch.lifecycle.jsonl"),
    (Join-Path $logs "$prefix.dispatch.json"),
    (Join-Path $logs "$prefix.launch.lock"),
    (Join-Path $logs "$prefix.supervisor-preflight.jsonl"),
    (Join-Path $logs "$prefix.lifecycle.jsonl"),
    (Join-Path $logs "$prefix.stdout.log"),
    (Join-Path $logs "$prefix.stderr.log"),
    (Join-Path $logs "$prefix.wsl-host.stdout.log"),
    (Join-Path $logs "$prefix.wsl-host.stderr.log"),
    (Join-Path $logs "$prefix.workload-exit.json"),
    (Join-Path (Join-Path $bulk 'runs') "$prefix-split42-model42"),
    (Join-Path (Join-Path $bulk 'runs') "$prefix-split43-model43")
)
function Assert-NoProduction {
    $collision=@($production|Where-Object{Test-Path -LiteralPath $_})
    if($collision.Count){throw "r17 production namespace exists during binary-lock smoke: $($collision -join '; ')"}
    $svc=New-Object -ComObject 'Schedule.Service'
    $svc.Connect()
    if(@($svc.GetFolder('\').GetTasks(1)|Where-Object{$_.Name-match'^SleepStagePaper-r17-(?:COM|Canary)-'}).Count){throw 'r17 scheduler namespace is not empty during binary-lock smoke'}
}
function Import-ProductionFunctions([string]$Path,[string[]]$Names) {
    $tokens=$null
    $errors=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $Path).Path,[ref]$tokens,[ref]$errors)
    if(@($errors).Count){throw "r17 production parser error: $(@($errors|ForEach-Object{$_.Message}) -join '; ')"}
    foreach($name in $Names){
        $matches=@($ast.FindAll({param($node)$node -is[Management.Automation.Language.FunctionDefinitionAst] -and $node.Name-eq$name},$true))
        if($matches.Count-ne1){throw "r17 production function count invalid: $name=$($matches.Count)"}
        $parameters=@($matches[0].Parameters|ForEach-Object{$_.Extent.Text}) -join ','
        $body=$matches[0].Body.Extent.Text
        $body=$body.Substring(1,$body.Length-2)
        $scriptBlock=[scriptblock]::Create("param($parameters)`n$body")
        Set-Item -Path ("Function:\script:"+$name) -Value $scriptBlock -Force
    }
}
function Assert-LockBehavior([string]$FunctionName,[string]$Dll,[string]$Malformed) {
    $lock=& $FunctionName $Dll 'binary'
    try {
        if($lock.content_type-ne'binary'-or$lock.PSObject.Properties['text']){throw "$FunctionName decoded a binary binding"}
        if($lock.sha256-ne(Get-FileHash -LiteralPath $Dll -Algorithm SHA256).Hash.ToLowerInvariant()){throw "$FunctionName binary SHA mismatch"}
    }
    finally {$lock.stream.Dispose()}
    $binary=& $FunctionName $Malformed 'binary'
    try {
        if($binary.content_type-ne'binary'-or$binary.PSObject.Properties['text']){throw "$FunctionName malformed binary was decoded"}
    }
    finally {$binary.stream.Dispose()}
    $strictFailed=$false
    try {
        $unexpected=& $FunctionName $Malformed 'utf8_text'
        if($unexpected){$unexpected.stream.Dispose()}
    }
    catch {$strictFailed=$true}
    if(-not$strictFailed){throw "$FunctionName accepted malformed UTF-8 as utf8_text"}
}
Assert-NoProduction
$caseRoot=Join-Path ([IO.Path]::GetTempPath()) ("sleep-stage-r17-binary-lock-"+[Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($caseRoot)|Out-Null
$malformed=Join-Path $caseRoot 'malformed.bin'
[IO.File]::WriteAllBytes($malformed,[byte[]](0xff,0xfe,0xfd,0x90))
try {
    Import-ProductionFunctions $DispatcherPath @('Get-Sha','Lock')
    Assert-LockBehavior 'Lock' (Resolve-Path -LiteralPath $NativeDllPath).Path $malformed
    Remove-Item Function:\Lock -Force
    Remove-Item Function:\Get-Sha -Force
    Import-ProductionFunctions $SupervisorPath @('Get-Sha','Open-Stable')
    Assert-LockBehavior 'Open-Stable' (Resolve-Path -LiteralPath $NativeDllPath).Path $malformed
}
finally {
    if(Test-Path Function:\Open-Stable){Remove-Item Function:\Open-Stable -Force}
    if(Test-Path Function:\Get-Sha){Remove-Item Function:\Get-Sha -Force}
    if(Test-Path -LiteralPath $malformed){[IO.File]::Delete($malformed)}
    if(Test-Path -LiteralPath $caseRoot){[IO.Directory]::Delete($caseRoot,$false)}
}
Assert-NoProduction
[ordered]@{
    status='pass'
    pilot_launched=$false
    dispatcher_binary_lock=$true
    supervisor_binary_lock=$true
    native_dll_binary_not_decoded=$true
    malformed_binary_accepted_as_binary=$true
    malformed_utf8_refused=$true
    production_artifacts_created=$false
}|ConvertTo-Json -Compress
