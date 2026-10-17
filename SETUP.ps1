param([string]$PythonExe = "")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Invoke-CheckedPython {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python step failed (exit $LASTEXITCODE): $Arguments" }
}

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if ($PythonExe) {
        $candidatePython = $PythonExe
    } else {
        $candidatePython = $null
        if (Get-Command py -ErrorAction SilentlyContinue) {
            $candidatePython = & py -3.12 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -ne 0) { $candidatePython = $null }
        }
        if (-not $candidatePython -and (Get-Command python -ErrorAction SilentlyContinue)) {
            $candidatePython = & python -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -ne 0) { $candidatePython = $null }
        }
        if (-not $candidatePython) {
            throw 'Install free 64-bit Python 3.12 from python.org, then run SETUP.ps1 again. Or pass -PythonExe with its full path.'
        }
    }
    Invoke-CheckedPython $candidatePython @('-c', 'import sys; assert sys.version_info[:2] == (3,12), "Use Python 3.12 for the tested dependency lock"')
    Invoke-CheckedPython $candidatePython @('-m', 'venv', '.venv')
}
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Invoke-CheckedPython $projectPython @('-m','pip','install','-r','requirements-lock.txt')
Invoke-CheckedPython $projectPython @('-m','pip','install','-r','requirements-torch.txt','--index-url','https://download.pytorch.org/whl/cpu')
Invoke-CheckedPython $projectPython @('-m','pip','install','-e','.','--no-deps','--no-build-isolation')
Invoke-CheckedPython $projectPython @('-m','carbonroute','doctor')
Write-Host 'Ready. Run RUN_DEMO.ps1 to open the demo, or RUN_DEMO.ps1 -Rebuild to reproduce it.'
