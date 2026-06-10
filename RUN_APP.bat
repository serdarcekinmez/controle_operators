@echo off
REM ============================================================
REM  Controle Agences - Lancement de l'application
REM ============================================================
setlocal
title Controle Agences

REM --- Refuser les chemins reseau / WSL (\\serveur\... ou \\wsl$\...) ---
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

REM --- Verifier la presence de app.py ---
if not exist "app.py" (
    echo [ERREUR] Le fichier app.py est introuvable dans ce dossier.
    echo Verifiez que vous lancez bien RUN_APP.bat depuis le dossier
    echo de l'application.
    echo.
    pause
    exit /b 1
)

REM --- Verifier que Streamlit est installe ---
".venv\Scripts\python.exe" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Streamlit n'est pas installe dans l'environnement.
    echo Veuillez relancer SETUP.bat.
    echo.
    pause
    exit /b 1
)

REM --- Verifier si le port 8501 est deja utilise ---
set "PORT_BUSY="
netstat -ano | findstr ":8501" | findstr /i "LISTENING" >nul 2>&1
if not errorlevel 1 set "PORT_BUSY=1"

if defined PORT_BUSY (
    echo ============================================================
    echo   ATTENTION : le port 8501 est deja utilise.
    echo   Une instance de l'application est peut-etre deja ouverte.
    echo.
    echo   Ouverture de la page existante dans le navigateur...
    echo   Adresse : http://localhost:8501
    echo ============================================================
    start "" http://localhost:8501
    echo.
    echo Si la page ne s'ouvre pas, ouvrez manuellement : http://localhost:8501
    echo.
    pause
    exit /b 0
)

echo ============================================================
echo   Demarrage de l'application Controle Agences...
echo.
echo   Le navigateur va s'ouvrir automatiquement dans quelques secondes.
echo.
echo   Si le navigateur ne s'ouvre pas automatiquement, ouvrez manuellement :
echo   http://localhost:8501
echo.
echo   NE FERMEZ PAS cette fenetre tant que vous utilisez l'application.
echo   Pour quitter : fermez cette fenetre noire.
echo ============================================================
echo.

REM --- Ouverture differee du navigateur (independante de Streamlit) ---
REM Une fenetre minimisee attend 3 secondes (le temps que le serveur demarre)
REM puis ouvre la page dans le navigateur par defaut.
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8501"

REM --- Lancement de Streamlit (headless + port fixe) via le Python du venv ---
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless=true --server.port=8501

if errorlevel 1 (
    echo.
    echo [ERREUR] L'application n'a pas pu demarrer correctement.
    echo  - Le port 8501 est peut-etre deja utilise par une autre instance.
    echo  - Essayez d'ouvrir manuellement : http://localhost:8501
    echo  - Consultez le dossier "logs" (fichier app.log) pour le detail.
    echo.
    pause
)
endlocal
