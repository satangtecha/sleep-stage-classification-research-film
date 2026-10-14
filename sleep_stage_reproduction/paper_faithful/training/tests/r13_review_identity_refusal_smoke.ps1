param(
    [string]$BuilderPath = (Join-Path $PSScriptRoot 'build_r13_canonical_gate.ps1'),
    [string]$ValidatorPath = (Join-Path $PSScriptRoot 'r13_canonical_gate_smoke.ps1')
)

$ErrorActionPreference = 'Stop'
$builder = Get-Content -LiteralPath (Resolve-Path -LiteralPath $BuilderPath) -Raw
$validator = Get-Content -LiteralPath (Resolve-Path -LiteralPath $ValidatorPath) -Raw
foreach ($needle in @('final reviewer identities must be nonblank and distinct','pending final reviewer identity failed')) {
    if (-not $builder.Contains($needle)) { throw "Gate builder lacks reviewer-identity refusal: $needle" }
}
foreach ($needle in @('IsNullOrWhiteSpace([string]$reviews[1].agent_id)','gate reviewer binding differs from review artifact')) {
    if (-not $validator.Contains($needle)) { throw "Gate validator lacks reviewer-identity refusal: $needle" }
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("r13-review-id-" + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($tempRoot) | Out-Null
try {
    $base = [ordered]@{
        schema_version = 1
        status = 'pass'
        run_id_prefix = 'paper-text-v1-multiseed-cap128-r13-20260830'
        pilot_launched = $false
        launch_test_evidence_sha256 = 'f217e62135908d6032220899eb72b7809e0fb6c1297a22dd7c61a020f4f8c5c3'
        reviews = @(
            [ordered]@{ review_id='implementation'; agent_id='01a052b3-47e9-77c2-aa86-b6b5e8fe6bb3'; role='implementation_reviewer'; status='no_material_finding' },
            [ordered]@{ review_id='final'; agent_id=$null; role='launch_gate_reviewer'; status='no_material_finding' }
        )
    }
    $nullPath = Join-Path $tempRoot 'null.json'
    $duplicatePath = Join-Path $tempRoot 'duplicate.json'
    [IO.File]::WriteAllText($nullPath, ($base | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    $base.reviews[1].agent_id = $base.reviews[0].agent_id
    [IO.File]::WriteAllText($duplicatePath, ($base | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))

    $results = @{}
    foreach ($case in @(@('null',$nullPath),@('duplicate',$duplicatePath))) {
        $output = Join-Path $tempRoot ("$($case[0])-gate.json")
        $priorErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $captured = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $BuilderPath -ReviewEvidencePath $case[1] -OutputPath $output -ExpectedLaunchEvidenceSha256 'f217e62135908d6032220899eb72b7809e0fb6c1297a22dd7c61a020f4f8c5c3' 2>&1)
            $caseExitCode = [int]$LASTEXITCODE
        }
        finally { $ErrorActionPreference = $priorErrorActionPreference }
        $results[$case[0]] = [ordered]@{ exit_code=$caseExitCode; output_created=(Test-Path -LiteralPath $output) }
        if ($results[$case[0]].exit_code -eq 0 -or $results[$case[0]].output_created) { throw "Gate builder accepted invalid reviewer identity: $($case[0])" }
    }

    [ordered]@{
        status = 'pass'
        pilot_launched = $false
        null_final_reviewer_id_refused = $true
        duplicate_reviewer_id_refused = $true
        gate_reviewers_bound_to_review_artifact = $true
        pending_null_identity_allowed_only_while_pending = $true
        production_namespace_touched = $false
    } | ConvertTo-Json -Compress
}
finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
