@echo off
setlocal

cd /d "%~dp0"

echo [1/4] Verification Python...
py -3.11 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 n'est pas detecte via le lanceur 'py'.
  echo Installe Python 3.11 puis relance ce script.
  exit /b 1
)

echo [2/4] Installation des dependances...
py -3.11 -m pip install --upgrade pip
py -3.11 -m pip install -r requirements.txt
py -3.11 -m pip install pyinstaller

echo [3/4] Nettoyage ancien build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/4] Build PyInstaller...
py -3.11 -m PyInstaller --noconfirm --clean windows_build.spec

if errorlevel 1 (
  echo Build echoue.
  exit /b 1
)

echo.
echo Build termine.
echo Executable: dist\CNPSAccueil.exe
echo IMPORTANT: Conserver aussi le dossier dist\_internal a cote de l'exe.
echo.
echo Base de donnees utilisee en mode EXE: dist\db.sqlite3
echo Pour deplacer les donnees vers un autre poste, copier tout le dossier dist.
endlocal
