@echo off
REM ============================================================
REM  Controle Agences - Installation (a executer UNE seule fois)
REM ============================================================
setlocal
title Controle Agences - Installation

REM --- Refuser les chemins reseau / WSL (\\serveur\... ou \\wsl$\...) ---
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~0,2%"=="\\" (
    echo [ERREUR] Ce script est lance depuis un chemin reseau ou WSL :
    echo     %SCRIPT_DIR%
    echo.
    echo Copiez d'abord le dossier complet de l'application sur le disque
    echo local de ce PC, par exemple :
    echo     C:\Users\%USERNAME%\ControleAgences
    echo puis relancez SETUP.bat depuis ce dossier local.
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERREUR] Impossible de se placer dans le dossier du script :
    echo     %SCRIPT_DIR%
    echo.
    pause
    exit /b 1
)

echo ============================================================
echo   Installation de l'application Controle Agences
echo ============================================================
echo.

REM --- Detection de Python : "py -3" en priorite, sinon "python" ---
set "PY_CMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"

if not defined PY_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [ERREUR] Python est introuvable sur cet ordinateur.
    echo.
    echo Installez Python 3.10 ou plus recent depuis :
    echo     https://www.python.org/downloads/
    echo IMPORTANT : pendant l'installation, cochez la case
    echo     "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo Python detecte via : %PY_CMD%
echo.

REM --- [1/3] Environnement virtuel ---
REM Un .venv cree sous Linux/WSL (dossier bin au lieu de Scripts) est
REM inutilisable sous Windows : on le supprime pour le recreer proprement.
if exist ".venv\bin\" if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Ancien environnement Linux detecte, suppression de .venv ...
    rmdir /s /q ".venv"
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creation de l'environnement virtuel .venv ...
    %PY_CMD% -m venv ".venv"
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement virtuel.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Environnement virtuel deja present, on le reutilise.
)

REM --- [2/3] Mise a jour de pip ---
echo [2/3] Mise a jour de pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERREUR] Mise a jour de pip impossible.
    pause
    exit /b 1
)

REM --- [3/3] Installation des dependances ---
echo [3/3] Installation des dependances (cela peut prendre 1 a 2 minutes) ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERREUR] L'installation des dependances a echoue.
    echo Verifiez votre connexion internet puis relancez SETUP.bat.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Installation terminee avec succes !
echo.
echo   ETAPE SUIVANTE :
echo     1) Copiez config.example.json en config.json
echo     2) Ouvrez config.json et renseignez l'adresse Gmail
echo        et le mot de passe d'application
echo     3) Double-cliquez ensuite sur RUN_APP.bat
echo ============================================================
echo.
pause
endlocal
