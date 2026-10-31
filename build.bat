@echo off
setlocal
cd /d "%~dp0"

for /f %%v in ('python -c "from app_core import CURRENT_VERSION as v;print(v)"') do set VER=%%v
echo === Build v%VER% ===

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [1/2] PyInstaller
python -m PyInstaller --noconfirm app.spec
if errorlevel 1 goto :err

echo [2/2] Inno Setup
set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
%ISCC% /DAppVersion=%VER% installer.iss
if errorlevel 1 goto :err

echo.
echo DONE: installer_output\HarmonyElixirSetup.exe  (v%VER%)
exit /b 0

:err
echo BUILD FAILED
exit /b 1
