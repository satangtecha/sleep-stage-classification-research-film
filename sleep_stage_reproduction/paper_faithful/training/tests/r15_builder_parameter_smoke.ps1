param(
 [string]$GateBuilderPath=(Join-Path $PSScriptRoot 'build_r15_canonical_gate.ps1'),
 [string]$AuthorizationBuilderPath=(Join-Path $PSScriptRoot 'build_r15_delegated_authorization_confirmation.ps1')
)
$ErrorActionPreference='Stop';$ps51="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe";$prefix='paper-text-v1-multiseed-cap128-r15-20260831';$gateOutput=(Join-Path $PSScriptRoot '..\canonical_r15_multiseed_launch_gate_20260831.final.json');$authOutput=(Join-Path $PSScriptRoot '..\r15_delegated_user_launch_authorization_20260831.json')
foreach($p in @($gateOutput,$authOutput)){if(Test-Path -LiteralPath $p){throw "production output exists before parameter smoke: $p"}}
$prior=$ErrorActionPreference;try{$ErrorActionPreference='Continue';$gateText=@(& $ps51 -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Resolve-Path -LiteralPath $GateBuilderPath).Path 2>&1|%{[string]$_});$gateCode=[int]$LASTEXITCODE;$authText=@(& $ps51 -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Resolve-Path -LiteralPath $AuthorizationBuilderPath).Path 2>&1|%{[string]$_});$authCode=[int]$LASTEXITCODE}finally{$ErrorActionPreference=$prior}
if($gateCode-ne1-or$authCode-ne1-or(Test-Path -LiteralPath $gateOutput)-or(Test-Path -LiteralPath $authOutput)){throw 'r15 builder mandatory-parameter fail-closed behavior failed'}
if(($gateText-join"`n")-match'Cannot bind argument to parameter ''Path'' because it is an empty string'-or($authText-join"`n")-match'Cannot bind argument to parameter ''Path'' because it is an empty string'){throw 'r15 builder retained PS5.1 PSScriptRoot parameter-default bug'}
[ordered]@{status='pass';pilot_launched=$false;gate_builder_missing_parameter_exit=1;authorization_builder_missing_parameter_exit=1;psscriptroot_parameter_default_bug_absent=$true;production_outputs_created=$false}|ConvertTo-Json -Compress
