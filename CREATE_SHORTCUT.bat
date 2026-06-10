@echo off
REM ============================================================
REM  Cree un raccourci "Controle Agences" sur le Bureau
REM ============================================================
title Controle Agences - Creation du raccourci

REM --- Refuser les chemins reseau / WSL (\\serveur\... ou \\wsl$\...) ---
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~0,2%"=="\\" (
    echo [ERREUR] Ce script est lance depuis un chemin reseau ou WSL :
    echo     %SCRIPT_DIR%
    echo.
    echo Copiez d'abord le dossier complet de l'application sur le disque
    echo local de ce PC, puis relancez ce script depuis le dossier local.
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"

echo Creation du raccourci sur le Bureau...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$desktop = [Environment]::GetFolderPath('Desktop');" ^
  "$lnk = Join-Path $desktop 'Controle Agences.lnk';" ^
  "$sc = $ws.CreateShortcut($lnk);" ^
  "$sc.TargetPath = Join-Path '%~dp0' 'RUN_APP.bat';" ^
  "$sc.WorkingDirectory = '%~dp0';" ^
  "$sc.IconLocation = 'shell32.dll,167';" ^
  "$sc.Description = 'Application de controle agences - Controle niveau 1';" ^
  "$sc.Save()"

if errorlevel 1 (
    echo [ERREUR] Impossible de creer le raccourci.
    pause
    exit /b 1
)

echo.
echo Raccourci cree sur le Bureau : "Controle Agences"
echo Vous pouvez maintenant lancer l'application en double-cliquant
echo sur cette icone.
echo.
pause
