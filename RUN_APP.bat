@echo off
REM ============================================================
REM  Controle Agences - Lancement de l'application
REM ============================================================
setlocal
title Controle Agences

REM --- Refuser les chemins reseau / WSL (\serveur\... ou \wsl$\...) ---
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~0,2%"=="\\" (
    echo [ERREUR] Ce script est lance depuis un chemin reseau ou WSL :
    echo     %SCRIPT_DIR%
    echo.
    echo Copiez d'abord le dossier complet de l'application sur le disque
    echo local de ce PC, par exemple :
    echo     C:\Users\%USERNAME%\ControleAgences
    echo puis relancez les scripts depuis ce dossier local.
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

REM --- Verifier l'environnement virtuel ---
if not exist ".venv\Scripts\python.exe" (
    echo [ERREUR] L'environnement n'est pas installe.
    echo Veuillez lancer SETUP.bat d'abord.
    echo.
    pause
    exit /b 1
)

REM --- Verifier les fichiers de l'application ---
if not exist "server.py" (
    echo [ERREUR] Le fichier server.py est introuvable dans ce dossier.
    echo Verifiez que vous lancez bien RUN_APP.bat depuis le dossier
    echo de l'application.
    echo.
    pause
    exit /b 1
)
if not exist "frontend\dist\index.html" (
    echo [ERREUR] L'interface de l'application est introuvable
    echo     ^(dossier frontend\dist^).
    echo Recuperez la version complete du dossier de l'application.
    echo.
    pause
    exit /b 1
)

REM --- Verifier les dependances (installe celles d'une nouvelle version) ---
".venv\Scripts\python.exe" -c "import flask, waitress, openpyxl, reportlab, pypdf, PIL" >nul 2>&1
if errorlevel 1 (
    echo Installation des composants manquants, patientez...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" -c "import flask, waitress, openpyxl, reportlab, pypdf, PIL" >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Les composants de l'application ne sont pas installes.
    echo Veuillez relancer SETUP.bat.
    echo.
    pause
    exit /b 1
)

echo ============================================================
echo   Demarrage de l'application Controle Agences...
echo.
echo   Le navigateur va s'ouvrir automatiquement.
echo   Sinon, ouvrez manuellement : http://127.0.0.1:8600
echo.
echo   NE FERMEZ PAS cette fenetre tant que vous utilisez l'application.
echo   Pour quitter : bouton "Quitter l'application" (ou fermez cette fenetre).
echo ============================================================
echo.

REM Le serveur ouvre lui-meme le navigateur. Si l'application est deja
REM ouverte, il affiche simplement la page existante.
".venv\Scripts\python.exe" server.py

if errorlevel 1 (
    echo.
    echo [ERREUR] L'application n'a pas pu demarrer correctement.
    echo  - Essayez d'ouvrir manuellement : http://127.0.0.1:8600
    echo  - Consultez le dossier "logs" ^(fichier app.log^) pour le detail.
    echo.
    pause
)
endlocal
