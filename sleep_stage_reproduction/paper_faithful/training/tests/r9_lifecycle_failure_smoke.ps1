param([string]$LauncherPath=(Join-Path $PSScriptRoot '..\launch_paper_text_multiseed_smoke_r9.ps1'))
$ErrorActionPreference='Stop';$tokens=$null;$errors=$null;$null=[Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $LauncherPath),[ref]$tokens,[ref]$errors);if($errors.Count){throw 'r9 launcher does not parse'}
$text=Get-Content -LiteralPath $LauncherPath -Raw
$collision=$text.IndexOf('Evidence, log, or child collision before marker');$marker=$text.IndexOf('[IO.FileMode]::CreateNew');$attempt=$text.IndexOf("event='attempt_created'");$preflight=$text.IndexOf("event='prelaunch_failed'");$processStart=$text.IndexOf('Start-Process -FilePath');$processExit=$text.IndexOf("event='process_exited'");$terminalCheck=$text.IndexOf('Runner did not return a completed two-child terminal JSON');$terminalFailure=$text.IndexOf("event='terminal_validation_failed'")
if($collision -lt 0 -or $marker -lt 0 -or $collision -ge $marker){throw 'static collisions are not checked before marker consumption'}
if($attempt -le $marker -or $attempt -ge $processStart){throw 'attempt lifecycle evidence is not immediate post-marker/pre-process evidence'}
if($preflight -lt 0 -or $preflight -le $attempt -or $preflight -le $processStart){throw 'prelaunch failure evidence is absent from the post-marker pre-process catch'}
if($processExit -le $processStart -or $processExit -ge $terminalCheck){throw 'raw process exit evidence is not written before terminal validation'}
if($terminalFailure -le $terminalCheck){throw 'terminal validation failure evidence is not appended before refusal'}
foreach($required in @('child_state','stdout_bytes','stderr_bytes','exit_code','process_id','canonical_gate_sha256','user_confirmation_sha256')){if($text.IndexOf($required) -lt 0){throw "lifecycle binding missing: $required"}}
if($text.IndexOf("paper_faithful\.training\.cli (pilot|multi-seed-pilot)") -lt 0 -or $text.IndexOf("run_paper_text_(pilot|multiseed)") -lt 0){throw 'concurrent single and multi-seed process refusal is incomplete'}
[pscustomobject]@{status='pass';static_collision_precedes_marker=$true;attempt_evidence_immediate=$true;prelaunch_failure_recorded=$true;raw_exit_precedes_validation=$true;terminal_failure_recorded=$true;pilot_launched=$false}|ConvertTo-Json -Compress
