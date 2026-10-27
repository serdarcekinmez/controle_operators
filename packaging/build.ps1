param([switch]$Release)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
function Run($Program, $Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed ($LASTEXITCODE)" }
}
Run "py" @("-3.12", "-m", "venv", ".venv-package")
$Python = ".venv-package\Scripts\python.exe"
Run $Python @("-m", "pip", "install", "-r", "packaging/requirements.txt")
Push-Location frontend
try {
    Run "npm.cmd" @("ci")
    Run "npm.cmd" @("run", "build")
} finally { Pop-Location }
$Mode = "--onedir"
$Console = "--console"
if ($Release) { $Mode = "--onefile"; $Console = "--windowed" }
Run $Python @("-m", "PyInstaller", "--noconfirm", "--clean", $Mode, $Console, "--name", "ControleAgences", "--add-data", "frontend/dist;frontend/dist", "--collect-all", "reportlab", "server.py")
Run $Python @("-m", "pip", "freeze")
