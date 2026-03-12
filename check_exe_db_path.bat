@echo off
setlocal

cd /d "%~dp0"

set "EXE_PATH=%~dp0dist\CNPSAccueil.exe"
set "RUNTIME_LOG=%~dp0dist\logs\runtime_db_path.log"

if not exist "%EXE_PATH%" (
  echo [ERREUR] Executable introuvable: %EXE_PATH%
  echo Lance d'abord build_windows.bat
  exit /b 1
)

echo ==============================================
echo Verification du chemin DB utilise par l'exe
echo ==============================================
if not "%CNPS_DB_PATH%"=="" (
  echo CNPS_DB_PATH courant: %CNPS_DB_PATH%
) else (
  echo CNPS_DB_PATH non defini.
)

echo.
if exist "%RUNTIME_LOG%" del /q "%RUNTIME_LOG%"

echo Lancement de l'executable...
start "CNPSAccueil" "%EXE_PATH%"

set "WAIT_SEC=10"
:wait_loop
if exist "%RUNTIME_LOG%" goto show_log
if %WAIT_SEC% LEQ 0 goto no_log
timeout /t 1 /nobreak >nul
set /a WAIT_SEC-=1
goto wait_loop

 :show_log
echo.
echo ===== runtime_db_path.log =====
type "%RUNTIME_LOG%"
echo ===============================
goto end

:no_log
echo.
echo [WARN] Log non trouve: %RUNTIME_LOG%
echo Verifie que l'exe demarre correctement puis relance ce script.

:end

endlocal
