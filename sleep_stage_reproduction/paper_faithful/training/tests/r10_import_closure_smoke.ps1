param(
 [string]$LauncherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r10.ps1'),
 [string]$Python='python'
)
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'r10 launcher does not parse'}
$launcherText=Get-Content -LiteralPath $LauncherPath -Raw
$cliText=Get-Content -LiteralPath (Join-Path $projectRoot 'paper_faithful\training\cli.py') -Raw
$trainerText=Get-Content -LiteralPath (Join-Path $projectRoot 'paper_faithful\training\trainer.py') -Raw
if($cliText.IndexOf('paper_faithful.training.verify_run') -lt 0 -or $cliText.IndexOf('_run_multi_seed_pilot') -lt 0 -or $trainerText.IndexOf('from .models import') -lt 0){throw 'multi-seed or standalone-verifier import route changed'}

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
$pythonScript=@'
import importlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
for name in ('paper_faithful.training.cli','paper_faithful.training.models','paper_faithful.training.verify_run'):
    importlib.import_module(name)
paths={}
for name,module in tuple(sys.modules.items()):
    value=getattr(module,'__file__',None)
    if not value:
        continue
    path=pathlib.Path(value).resolve()
    try:
        relative=path.relative_to(root)
    except ValueError:
        continue
    if relative.suffix=='.py' and relative.parts and relative.parts[0]=='paper_faithful':
        paths[relative.as_posix()]=name
print(json.dumps([{'path':path,'module':paths[path]} for path in sorted(paths)]))
'@
$priorNoBytecode=$env:PYTHONDONTWRITEBYTECODE
try {
 $env:PYTHONDONTWRITEBYTECODE='1'
 $pythonOutput=@(& $Python -c $pythonScript $projectRoot)
 if($LASTEXITCODE -ne 0){throw 'repository import-closure discovery failed'}
} finally {
 if($null -eq $priorNoBytecode){Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue}else{$env:PYTHONDONTWRITEBYTECODE=$priorNoBytecode}
}
$parsedDiscovery=($pythonOutput -join "`n")|ConvertFrom-Json
$discovered=@($parsedDiscovery|ForEach-Object{$_})

function Assert-ExactClosure([string[]]$Reachable,[string[]]$Bound) {
 $reachableSorted=@($Reachable|Sort-Object -Unique);$boundSorted=@($Bound|Sort-Object -Unique)
 if(($reachableSorted -join '|') -ne ($boundSorted -join '|')){throw 'reachable repository import closure is not exactly bound'}
}
$reachablePaths=@($discovered|%{[string]$_.path})
Assert-ExactClosure $expected.Keys $reachablePaths

$mapping=[regex]::Match($launcherText,'(?s)\$repositoryPythonSourcePaths=\[ordered\]@\{(?<body>.*?)\r?\n\}')
if(!$mapping.Success){throw 'launcher repository Python source map is missing'}
$boundByPath=@{}
foreach($match in [regex]::Matches($mapping.Groups['body'].Value,'(?m)^\s*(?<field>[a-z0-9_]+)=\(Join-Path \$projectRoot ''(?<path>[^'']+\.py)''\)\s*$')){
 $boundByPath[$match.Groups['path'].Value.Replace('\','/')]=$match.Groups['field'].Value
}
Assert-ExactClosure $expected.Keys $boundByPath.Keys
foreach($path in $expected.Keys){if($boundByPath[$path] -ne $expected[$path]){throw "repository import hash field mismatch: $path"}}

$evidenceFunction=$ast.Find({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-R10LaunchTestEvidence'},$true)
$gateFunction=$ast.Find({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Assert-R10Gate'},$true)
if(!$evidenceFunction -or !$gateFunction){throw 'r10 gate or evidence helper is missing'}
foreach($field in $expected.Values){if($evidenceFunction.Extent.Text.IndexOf("'$field'") -lt 0){throw "launch-test evidence omits reachable source hash: $field"}}
if(([regex]::Matches($gateFunction.Extent.Text,'foreach\(\$name in \$repositoryPythonSourcePaths\.Keys\)')).Count -lt 2 -or $launcherText.IndexOf('@($repositoryPythonSourcePaths.Values)') -lt 0){throw 'repository import closure is not hash-checked, evidence-bound, and protected by stable locks'}

$omissionRefused=$false
$omitted=@($reachablePaths|Select-Object -Skip 1)
try{Assert-ExactClosure $expected.Keys $omitted}catch{$omissionRefused=$true}
if(!$omissionRefused){throw 'reachable repository module omission was accepted'}
[pscustomobject]@{status='pass';entry_modules=@('paper_faithful.training.cli','paper_faithful.training.verify_run');reachable_repository_modules=$reachablePaths.Count;bound_repository_modules=$boundByPath.Count;omission_refused=$omissionRefused;pilot_launched=$false}|ConvertTo-Json -Compress
