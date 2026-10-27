@echo off
setlocal
cd /d "%~dp0\..\.."

set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo =======================================================
echo  Running Job-bot v2.0 Company Career Pages Flow
echo =======================================================

echo [1/3] Scanning active company career pages...
"%PYTHON%" v2\main.py careers scan
if errorlevel 1 goto error

echo [2/3] Validating career jobs via Ollama AI...
"%PYTHON%" v2\main.py careers validate
if errorlevel 1 goto error

echo [3/3] Opening eligible career jobs in Google Chrome...
"%PYTHON%" v2\main.py careers open

echo =======================================================
echo  Career Pages Flow Completed Successfully!
echo =======================================================
goto end

:error
echo [!] Career Flow encountered an error.

:end
pause
