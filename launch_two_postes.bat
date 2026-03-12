@echo off
setlocal

cd /d "%~dp0"

rem Base partagee (meme DB pour les 2 instances)
if "%CNPS_DB_PATH%"=="" (
  echo CNPS_DB_PATH non defini ^(mode base persistante locale active^)
) else (
  echo CNPS_DB_PATH=%CNPS_DB_PATH%
)
echo Ouverture de 2 instances: Poste A et Poste B...

rem Poste A
if "%CNPS_DB_PATH%"=="" (
  start "Poste A - CNPS" cmd /k "cd /d "%~dp0" && C:/Users/m9700/AppData/Local/Programs/Python/Python311/python.exe main.py"
) else (
  start "Poste A - CNPS" cmd /k "cd /d "%~dp0" && set CNPS_DB_PATH=%CNPS_DB_PATH% && C:/Users/m9700/AppData/Local/Programs/Python/Python311/python.exe main.py"
)

rem Petite pause
timeout /t 1 /nobreak >nul

rem Poste B
if "%CNPS_DB_PATH%"=="" (
  start "Poste B - CNPS" cmd /k "cd /d "%~dp0" && C:/Users/m9700/AppData/Local/Programs/Python/Python311/python.exe main.py"
) else (
  start "Poste B - CNPS" cmd /k "cd /d "%~dp0" && set CNPS_DB_PATH=%CNPS_DB_PATH% && C:/Users/m9700/AppData/Local/Programs/Python/Python311/python.exe main.py"
)

echo.
echo 2 fenetres ont ete lancees.
echo Connecte-toi avec 2 profils differents pour tester le mode simultane.

endlocal
