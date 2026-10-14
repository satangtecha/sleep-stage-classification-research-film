param(
    [string]$BuilderPath=(Join-Path $PSScriptRoot 'build_r14_canonical_gate.ps1')
)

$ErrorActionPreference='Stop'
$builderResolved=(Resolve-Path -LiteralPath $BuilderPath).Path
$tokens=$null;$parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($builderResolved,[ref]$tokens,[ref]$parseErrors)
if(@($parseErrors).Count){throw 'r14 gate builder parse failed'}
$launchParam=@($ast.ParamBlock.Parameters|Where-Object{$_.Name.VariablePath.UserPath-eq'LaunchEvidencePath'})
if($launchParam.Count-ne1){throw 'r14 LaunchEvidencePath parameter identity failed'}
if($null-ne$launchParam[0].DefaultValue){throw 'r14 LaunchEvidencePath must not use a parameter default'}
$mandatory=$false
foreach($attribute in @($launchParam[0].Attributes)){
    if($attribute.TypeName.FullName-eq'Parameter'){
        foreach($named in @($attribute.NamedArguments)){
            if($named.ArgumentName-eq'Mandatory'-and$named.Argument.Extent.Text-match'^\$true$'){$mandatory=$true}
        }
    }
}
if(!$mandatory){throw 'r14 LaunchEvidencePath must be mandatory'}

$outputPath=Join-Path ([IO.Path]::GetTempPath()) ("r14-gate-missing-launch-evidence-{0}.json"-f[guid]::NewGuid().ToString('N'))
$powershell="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$savedErrorActionPreference=$ErrorActionPreference
$ErrorActionPreference='Continue'
$failureText=& $powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $builderResolved -ReviewEvidencePath $builderResolved -ExpectedLaunchEvidenceSha256 ('0'*64) -OutputPath $outputPath 2>&1|Out-String
$exitCode=$LASTEXITCODE
$ErrorActionPreference=$savedErrorActionPreference
if($exitCode-eq0){throw 'r14 gate builder accepted missing LaunchEvidencePath'}
if(Test-Path -LiteralPath $outputPath){throw 'r14 gate builder wrote output after missing LaunchEvidencePath'}
if($failureText-notmatch'LaunchEvidencePath'){throw 'r14 gate builder missing-parameter failure did not identify LaunchEvidencePath'}

[ordered]@{
    status='pass'
    validated_by_windows_powershell_5_1=$true
    launch_evidence_path_mandatory=$true
    launch_evidence_parameter_default_absent=$true
    missing_parameter_exit_code=$exitCode
    missing_parameter_refused=$true
    output_created=$false
    production_namespace_touched=$false
}|ConvertTo-Json -Compress
