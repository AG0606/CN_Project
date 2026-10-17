$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw 'Run SETUP.ps1 first.' }
$outputPath = Join-Path $PSScriptRoot ('results\paper-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
& $projectPython -m carbonroute run --paper --output $outputPath
if ($LASTEXITCODE -ne 0) { throw 'Experiment failed. See the error and run manifest.' }
Start-Process -FilePath (Join-Path $outputPath 'index.html')
