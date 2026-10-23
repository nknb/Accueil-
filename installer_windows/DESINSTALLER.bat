@echo off
chcp 65001 > nul
title Désinstallation CNPS Accueil

echo.
echo  Desinstallation de CNPS Accueil...
echo.

set INSTALL_DIR=C:\CNPS\AccueilCNPS

:: Supprimer la tache planifiee de sauvegarde (si elle existe)
schtasks /Query /TN "CNPS Accueil sauvegarde" > nul 2>&1
if %errorlevel% equ 0 (
    schtasks /Delete /TN "CNPS Accueil sauvegarde" /F > nul
    echo  [OK] Tache planifiee de sauvegarde supprimee
)

:: Supprimer l'application
if exist "%INSTALL_DIR%" (
    rmdir /S /Q "%INSTALL_DIR%"
    echo  [OK] Dossier application supprime
)

:: Supprimer les raccourcis
if exist "%PUBLIC%\Desktop\CNPS Accueil.lnk" (
    del /Q "%PUBLIC%\Desktop\CNPS Accueil.lnk"
    echo  [OK] Raccourci Bureau supprime
)

if exist "%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\CNPS" (
    rmdir /S /Q "%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\CNPS"
    echo  [OK] Raccourci menu Demarrer supprime
)

echo.
echo  Desinstallation terminee.
pause > nul
