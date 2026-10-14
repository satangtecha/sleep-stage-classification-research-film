param([string]$Story = "$PSScriptRoot\story.json", [string]$OnlyId = '')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$filmStory = Get-Content -LiteralPath $Story -Raw -Encoding UTF8 | ConvertFrom-Json
$filmAudioRoot = Join-Path $PSScriptRoot 'audio'
New-Item -ItemType Directory -Path $filmAudioRoot -Force | Out-Null
$filmSpeaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
$filmSpeaker.SelectVoice('Microsoft Pattara')
$filmSpeaker.Rate = 0
$filmSpeaker.Volume = 100
try {
    foreach ($filmChapter in $filmStory.chapters) {
        foreach ($filmScene in $filmChapter.scenes) {
            if ($OnlyId -and $filmScene.id -ne $OnlyId) { continue }
            $filmAudioStem = if ($filmScene.audio_stem) { $filmScene.audio_stem } else { $filmScene.id }
            $filmAudioPath = Join-Path $filmAudioRoot ($filmAudioStem + '.wav')
            if (Test-Path -LiteralPath $filmAudioPath) { throw "Refusing to overwrite $filmAudioPath" }
            $filmSpeaker.SetOutputToWaveFile($filmAudioPath)
            $filmSpeaker.Speak([string]$filmScene.narration)
            $filmSpeaker.SetOutputToNull()
            Write-Output ($filmScene.id + ' generated')
        }
    }
} finally { $filmSpeaker.Dispose() }
