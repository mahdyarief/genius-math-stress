@echo off
rem Launcher for the Indonesia Open batch runner (Windows).
rem Always boots under the project venv (which has patchright), so instances
rem spawned via sys.executable inherit the correct interpreter.
setlocal
cd /d "%~dp0"

set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Error: venv python not found at %PY%
  exit /b 1
)

"%PY%" -u run_batch_indo_open.py %*
exit /b %errorlevel%
