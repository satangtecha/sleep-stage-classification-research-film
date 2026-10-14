param(
    [string]$GatePath,
    [string]$Python='python'
)

$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$expected=[ordered]@{
    'paper_faithful/sst/__init__.py'='sst_init_py'
    'paper_faithful/sst/cache_manifest.py'='sst_cache_manifest_py'
    'paper_faithful/sst/cache_writer.py'='sst_cache_writer_py'
    'paper_faithful/sst/cohort_cache.py'='sst_cohort_cache_py'
    'paper_faithful/sst/storage.py'='sst_storage_py'
    'paper_faithful/sst/transform.py'='sst_transform_py'
    'paper_faithful/sst/windowing.py'='sst_windowing_py'
    'paper_faithful/training/__init__.py'='training_init_py'
    'paper_faithful/training/cache_loader.py'='training_cache_loader_py'
    'paper_faithful/training/cli.py'='cli_py'
    'paper_faithful/training/metrics.py'='training_metrics_py'
    'paper_faithful/training/models.py'='training_models_py'
    'paper_faithful/training/protocols.py'='training_protocols_py'
    'paper_faithful/training/run_manifest.py'='training_run_manifest_py'
    'paper_faithful/training/splits.py'='training_splits_py'
    'paper_faithful/training/storage.py'='training_storage_py'
    'paper_faithful/training/trainer.py'='trainer_py'
    'paper_faithful/training/verify_run.py'='verify_run_py'
}
$probe=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'r13_import_closure_probe.py')).Path
$priorNoBytecode=$env:PYTHONDONTWRITEBYTECODE
try {
    $env:PYTHONDONTWRITEBYTECODE='1'
    $output=@(& $Python $probe)
    if($LASTEXITCODE-ne0){throw 'repository import-closure discovery failed'}
} finally {
    if($null-eq$priorNoBytecode){Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue}else{$env:PYTHONDONTWRITEBYTECODE=$priorNoBytecode}
}
$discovered=@((($output-join"`n")|ConvertFrom-Json)|ForEach-Object{$_})
$reachable=@($discovered|ForEach-Object{[string]$_.path}|Sort-Object -Unique)
$expectedPaths=@($expected.Keys|Sort-Object -Unique)
if(($reachable-join'|')-ne($expectedPaths-join'|')){throw 'reachable repository import closure changed'}

$bindings=@()
foreach($path in $expected.Keys){
    $full=(Resolve-Path -LiteralPath (Join-Path $projectRoot $path.Replace('/','\'))).Path
    $bindings+=@([ordered]@{name=$expected[$path];path=$full;sha256=(Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()})
}

$gateValidated=$false
if(-not[string]::IsNullOrWhiteSpace($GatePath)){
    $gate=Get-Content -LiteralPath (Resolve-Path -LiteralPath $GatePath) -Raw|ConvertFrom-Json -ErrorAction Stop
    $byName=@{};foreach($binding in @($gate.source_bindings)){if($byName.ContainsKey([string]$binding.name)){throw 'duplicate gate source binding'};$byName[[string]$binding.name]=$binding}
    foreach($binding in $bindings){
        if(!$byName.ContainsKey($binding.name)){throw "gate omits reachable source: $($binding.name)"}
        $actual=$byName[$binding.name]
        if(-not[IO.Path]::GetFullPath([string]$actual.path).Equals($binding.path,[StringComparison]::OrdinalIgnoreCase)-or[string]$actual.sha256-ne$binding.sha256){throw "gate reachable source binding differs: $($binding.name)"}
    }
    $gateValidated=$true
}

$omissionRefused=$false
try {if((@($reachable|Select-Object -Skip 1)-join'|')-ne($expectedPaths-join'|')){throw 'omitted'}} catch {$omissionRefused=$true}
if(!$omissionRefused){throw 'reachable source omission was accepted'}

[ordered]@{
    status='pass'
    entry_modules=@('paper_faithful.training.cli','paper_faithful.training.models','paper_faithful.training.verify_run')
    reachable_repository_modules=$reachable.Count
    bound_repository_modules=$bindings.Count
    omission_refused=$true
    gate_validated=$gateValidated
    source_bindings=$bindings
    pilot_launched=$false
}|ConvertTo-Json -Depth 6 -Compress

