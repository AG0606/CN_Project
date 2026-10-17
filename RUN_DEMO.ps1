param([switch]$Rebuild)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$reportPath = Join-Path $PSScriptRoot 'results\demo\index.html'
if ((Test-Path -LiteralPath $reportPath) -and -not $Rebuild) {
    Start-Process -FilePath $reportPath
    exit 0
}
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw 'Run SETUP.ps1 first, or open DEMO.html for the saved offline demonstration.' }
& $projectPython -m carbonroute demo --overwrite --open
if ($LASTEXITCODE -ne 0) { throw 'Demo failed. Read the error above; no result should be inferred from a failed run.' }
