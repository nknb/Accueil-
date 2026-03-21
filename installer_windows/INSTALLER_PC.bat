@echo off
:: ============================================================
::  CNPS Accueil — Script d'installation automatique
::  A exécuter en ADMINISTRATEUR sur chaque poste Windows
:: ============================================================
chcp 65001 > nul
title Installation CNPS Accueil

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║        CNPS — Installation Accueil+             ║
echo  ║        Caisse Nationale de Prevoyance Sociale   ║
echo  ╚══════════════════════════════════════════════════╝
echo.

:: --- Dossier d'installation ---
set INSTALL_DIR=C:\CNPS\AccueilCNPS
echo  [1/5] Dossier d installation : %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: --- Copier les fichiers de l'application ---
echo  [2/5] Copie des fichiers de l application...
set SCRIPT_DIR=%~dp0
xcopy /E /Y /Q "%SCRIPT_DIR%AccueilCNPS\*" "%INSTALL_DIR%\" > nul
if %errorlevel% neq 0 (
    echo  [ERREUR] Impossible de copier les fichiers.
    pause
    exit /b 1
)
echo        OK

:: --- Configurer la base de données reseau ---
echo  [3/5] Configuration base de donnees reseau...
set DB_CONFIG=%INSTALL_DIR%\db_config.json
echo {"custom_db_path": "\\\\srvgagnoa\\prod\\datagagnoa\\accueil\\db.sqlite3"} > "%DB_CONFIG%"
echo        OK - Pointe vers \\srvgagnoa\prod\datagagnoa\accueil\db.sqlite3

:: --- Creer le raccourci Bureau ---
echo  [4/5] Creation du raccourci sur le Bureau...
set SHORTCUT_PATH=%PUBLIC%\Desktop\CNPS Accueil.lnk
set EXE_PATH=%INSTALL_DIR%\AccueilCNPS.exe

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $sc = $ws.CreateShortcut('%SHORTCUT_PATH%'); ^
   $sc.TargetPath = '%EXE_PATH%'; ^
   $sc.WorkingDirectory = '%INSTALL_DIR%'; ^
   $sc.Description = 'CNPS Gestion Accueil'; ^
   $sc.Save()"
echo        OK

:: --- Creer raccourci demarrage automatique (optionnel) ---
echo  [5/5] Ajout au menu Demarrer...
set START_DIR=%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\CNPS
if not exist "%START_DIR%" mkdir "%START_DIR%"
set START_SHORTCUT=%START_DIR%\CNPS Accueil.lnk

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $sc = $ws.CreateShortcut('%START_SHORTCUT%'); ^
   $sc.TargetPath = '%EXE_PATH%'; ^
   $sc.WorkingDirectory = '%INSTALL_DIR%'; ^
   $sc.Description = 'CNPS Gestion Accueil'; ^
   $sc.Save()"
echo        OK

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║  Installation terminee avec succes !            ║
echo  ║                                                  ║
echo  ║  Raccourci cree sur le Bureau                   ║
echo  ║  Base de donnees : reseau CNPS                  ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  Appuyez sur une touche pour fermer...
pause > nul
