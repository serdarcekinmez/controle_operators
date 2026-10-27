# Construction de Controle Agences pour Windows (x64, Python 3.12, Node 22.12+).
#   powershell -ExecutionPolicy Bypass -File packaging/build.ps1            -> dist\ControleAgences\ (dossier, console)
#   powershell -ExecutionPolicy Bypass -File packaging/build.ps1 -Release   -> dist\ControleAgences.exe (fichier unique, sans console)
# Le script s'arrete a la premiere erreur.
param(
    [switch]$Release,
    [switch]$SkipTests,
    # Python 3.12 x64 de base ; par defaut le lanceur "py -3.12-64".
    [string]$BasePython = ""
)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $Root
try {
    function Run($Program, $Arguments) {
        & $Program @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$Program $($Arguments -join ' ') a echoue (code $LASTEXITCODE)" }
    }

    # 1. Environnement Python propre et fige
    if ($BasePython) { Run $BasePython @("-m", "venv", "--clear", ".venv-package") }
    else { Run "py" @("-3.12-64", "-m", "venv", "--clear", ".venv-package") }
    $Python = Join-Path $Root ".venv-package\Scripts\python.exe"
    Run $Python @("-c", "import sys, struct; assert sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8, 'Python 3.12 x64 requis'")
    Run $Python @("-m", "pip", "install", "--disable-pip-version-check", "-r", "packaging/requirements.txt")

    # 2. Interface React reconstruite depuis les sources
    Push-Location frontend
    try {
        Run "npm.cmd" @("ci")
        Run "npm.cmd" @("run", "build")
    } finally { Pop-Location }
    Run $Python @("packaging/check_frontend.py", "frontend/dist")

    # 3. Tests (avec les versions exactes qui seront empaquetees)
    if (-not $SkipTests) { Run $Python @("-m", "unittest", "discover", "-s", "tests", "-v") }

    # 4. Executable
    Run $Python @("packaging/make_version_info.py", "build/version_info.txt")
    if ($Release) { $Mode = "--onefile"; $Console = "--windowed" }
    else { $Mode = "--onedir"; $Console = "--console" }
    Run $Python @("-m", "PyInstaller", "--noconfirm", "--clean", "--noupx", $Mode, $Console,
        "--name", "ControleAgences", "--version-file", "build/version_info.txt",
        "--add-data", "frontend/dist;frontend/dist", "--collect-all", "reportlab",
        "--hidden-import", "waitress", "launcher.py")

    if ($Release) {
        $Exe = Join-Path $Root "dist\ControleAgences.exe"
    } else {
        $Exe = Join-Path $Root "dist\ControleAgences\ControleAgences.exe"
        Run $Python @("packaging/check_frontend.py", "dist/ControleAgences/_internal/frontend/dist")
    }
    if (-not (Test-Path $Exe)) { throw "Executable introuvable : $Exe" }

    # 5. Tracabilite de la livraison
    $Kind = if ($Release) { "onefile" } else { "onedir" }
    $Info = Join-Path $Root "dist\build-info-$Kind.txt"
    $Commit = "inconnu"; $Dirty = $null
    try { $Commit = (& git rev-parse HEAD); $Dirty = (& git status --porcelain) } catch { }
    @(
        "Executable : $Exe",
        "SHA256     : $((Get-FileHash -Algorithm SHA256 $Exe).Hash)",
        "Commit     : $Commit$(if ($Dirty) { ' (copie de travail modifiee)' })",
        "Python     : $(& $Python --version)",
        "Node       : $(& node --version)",
        "Date       : $(Get-Date -Format s)",
        "",
        "pip freeze :"
    ) + (& $Python -m pip freeze) | Set-Content -Encoding UTF8 $Info
    Get-Content $Info
} finally {
    Pop-Location
}
