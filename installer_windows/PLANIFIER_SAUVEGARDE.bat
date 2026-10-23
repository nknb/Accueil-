@echo off
:: ============================================================
::  CNPS Accueil — Planification de la sauvegarde nocturne
::  A executer en ADMINISTRATEUR (double-clic > Executer en tant qu'administrateur)
::  sur UN poste ou le serveur: une seule tache suffit pour toute l'agence.
::
::  Usage:  PLANIFIER_SAUVEGARDE.bat [HH:MM] [NOMBRE_A_GARDER]
::  Exemple: PLANIFIER_SAUVEGARDE.bat 22:00 30
:: ============================================================
chcp 65001 > nul
title Planification de la sauvegarde CNPS Accueil
setlocal

set TACHE=CNPS Accueil sauvegarde
set INSTALL_DIR=C:\CNPS\AccueilCNPS
set EXE=%INSTALL_DIR%\AccueilCNPS.exe
set HEURE=%~1
if "%HEURE%"=="" set HEURE=22:00
set GARDER=%~2
if "%GARDER%"=="" set GARDER=30

echo.
echo  ====================================================
echo    CNPS Accueil - Sauvegarde automatique de la base
echo  ====================================================
echo.

:: --- Droits d'administrateur ---
net session > nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERREUR] Lancez ce script en ADMINISTRATEUR.
    pause
    exit /b 1
)

:: --- Application installee ? ---
if not exist "%EXE%" (
    echo  [ERREUR] Application introuvable: %EXE%
    echo           Installez d'abord l'application avec INSTALLER_PC.bat.
    pause
    exit /b 1
)

echo  Tache      : %TACHE%
echo  Heure      : tous les jours a %HEURE%
echo  Conservees : les %GARDER% dernieres sauvegardes
echo  Dossier    : "sauvegardes" a cote de la base de donnees
echo.
echo  La tache s'execute avec VOTRE compte Windows (%USERDOMAIN%\%USERNAME%): il doit avoir
echo  acces en ecriture au partage de la base. Le mot de passe va vous etre demande.
echo.

:: --- Creation (ou remplacement) de la tache ---
schtasks /Create /F /SC DAILY /ST %HEURE% /TN "%TACHE%" /TR "\"%EXE%\" --sauvegarde --garder %GARDER%" /RU "%USERDOMAIN%\%USERNAME%" /RP *
if %errorlevel% neq 0 (
    echo.
    echo  [ERREUR] La tache n'a pas pu etre creee.
    pause
    exit /b 1
)
echo.
echo  [OK] Tache planifiee.

:: --- Essai immediat ---
choice /C ON /M "Lancer une sauvegarde de test maintenant"
if %errorlevel% equ 1 (
    echo  Sauvegarde en cours...
    start "" /wait "%EXE%" --sauvegarde --garder %GARDER%
    if errorlevel 1 (
        echo  [ERREUR] La sauvegarde a echoue. Voir le fichier logs\app.log dans %INSTALL_DIR%
    ) else (
        echo  [OK] Sauvegarde reussie: voir le dossier "sauvegardes" a cote de la base.
    )
)

echo.
echo  Pour verifier plus tard: planificateur de taches Windows ^> "%TACHE%".
echo  Pour supprimer la tache: DESINSTALLER.bat ou  schtasks /Delete /TN "%TACHE%" /F
echo.
pause
