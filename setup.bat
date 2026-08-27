@echo off
rem Setup script for Windows — creates venv, installs deps, installs browser.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [setup] Creating virtualenv ^(.venv^)...
  python -m venv .venv
)

echo [setup] Installing requirements into .venv...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

echo [setup] Installing Chromium browser for patchright...
.venv\Scripts\patchright.exe install chromium

echo.
echo [setup] Done!
echo   Next: copy .secret.example to .secret and fill in your 2captcha key,
echo   then run: run.bat --target 1000 --parallel 10
endlocal
