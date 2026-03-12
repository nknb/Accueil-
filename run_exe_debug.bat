@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

set "EXE_PATH=%~dp0dist\CNPSAccueil.exe"
set "LOG_DIR=%~dp0logs"
set "LOG_FILE=%LOG_DIR%\exe_debug.log"

if not exist "%EXE_PATH%" (
  echo [ERREUR] Executable introuvable: %EXE_PATH%
  exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================== > "%LOG_FILE%"
echo Lancement debug: %date% %time% >> "%LOG_FILE%"
echo EXE: %EXE_PATH% >> "%LOG_FILE%"
echo CNPS_DB_PATH=%CNPS_DB_PATH% >> "%LOG_FILE%"
echo ============================================== >> "%LOG_FILE%"

echo Lancement de l'exe en mode debug...
"%EXE_PATH%" 1>> "%LOG_FILE%" 2>>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo.>> "%LOG_FILE%"
echo Exit code: %EXIT_CODE% >> "%LOG_FILE%"

echo Execution terminee. Exit code=%EXIT_CODE%
echo Log: %LOG_FILE%

endlocal
