@echo off
setlocal

cd /d "%~dp0"

set "EXE_PATH=%~dp0dist\CNPSAccueil.exe"

if not exist "%EXE_PATH%" (
  echo [ERREUR] Executable introuvable: %EXE_PATH%
  exit /b 1
)

echo ==============================================
echo Simulation 2 postes (2 exe) - meme base reseau
if "%CNPS_DB_PATH%"=="" (
  echo CNPS_DB_PATH non defini ^(mode base persistante locale active^)
) else (
  echo CNPS_DB_PATH=%CNPS_DB_PATH%
)
echo ==============================================

echo Lancement Poste A...
start "Poste A - CNPS EXE" "%EXE_PATH%"

timeout /t 1 /nobreak >nul

echo Lancement Poste B...
start "Poste B - CNPS EXE" "%EXE_PATH%"

timeout /t 2 /nobreak >nul

echo.
echo Instances CNPSAccueil detectees:
powershell -NoProfile -Command "Get-Process CNPSAccueil -ErrorAction SilentlyContinue | Select-Object Name,Id,StartTime | Format-Table -AutoSize | Out-String"

endlocal
