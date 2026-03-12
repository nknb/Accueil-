@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

set "DIST_DIR=%~dp0dist"
set "EXE_SOURCE=%DIST_DIR%\CNPSAccueil.exe"
set "INTERNAL_SOURCE=%DIST_DIR%\_internal"
set "INSTALL_DIR=%LOCALAPPDATA%\CNPSAccueil"
set "EXE_TARGET=%INSTALL_DIR%\CNPSAccueil.exe"
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\CNPS Accueil.lnk"

if not exist "%EXE_SOURCE%" (
    echo [ERREUR] Executable introuvable: %EXE_SOURCE%
    echo Lance d'abord le build avec build_windows.bat
    exit /b 1
)

if not exist "%INTERNAL_SOURCE%" (
    echo [ERREUR] Dossier runtime introuvable: %INTERNAL_SOURCE%
    echo Le dossier dist\_internal est obligatoire pour executer l'application.
    exit /b 1
)

echo.
echo ==============================================
echo   Installation Client CNPS Accueil

echo ==============================================
echo.

set /p DB_PATH=Entrez le chemin DB partage (ex: \\serveur\partage\cnps\db.sqlite3) : 

if "%DB_PATH%"=="" (
    echo [ERREUR] Le chemin DB est obligatoire.
    exit /b 1
)

if not exist "%DB_PATH%" (
    echo [ERREUR] Le fichier DB n'existe pas: %DB_PATH%
    exit /b 1
)

echo [1/4] Copie des fichiers...
if exist "%INSTALL_DIR%" rmdir /s /q "%INSTALL_DIR%"
mkdir "%INSTALL_DIR%"
copy /Y "%EXE_SOURCE%" "%EXE_TARGET%" >nul
xcopy "%INTERNAL_SOURCE%\*" "%INSTALL_DIR%\_internal\" /E /I /Y >nul

if errorlevel 1 (
    echo [ERREUR] Echec de copie des fichiers.
    exit /b 1
)

echo [2/4] Configuration variable CNPS_DB_PATH...
setx CNPS_DB_PATH "%DB_PATH%" >nul
if errorlevel 1 (
    echo [ERREUR] Impossible de definir CNPS_DB_PATH.
    exit /b 1
)

echo [3/4] Creation raccourci Bureau...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); $Shortcut.TargetPath = '%EXE_TARGET%'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.IconLocation = '%EXE_TARGET%,0'; $Shortcut.Save()"

if errorlevel 1 (
    echo [ERREUR] Impossible de creer le raccourci Bureau.
    exit /b 1
)

echo [4/4] Test de presence executable cible...
if not exist "%EXE_TARGET%" (
    echo [ERREUR] Executable cible introuvable: %EXE_TARGET%
    exit /b 1
)

echo.
echo ==============================================
echo Installation terminee avec succes.
echo - Application: %EXE_TARGET%
echo - Raccourci: %SHORTCUT_PATH%
echo - Base partagee: %DB_PATH%
echo ==============================================
echo.
echo Tu peux lancer l'application via le raccourci Bureau.

echo.
pause
endlocal
