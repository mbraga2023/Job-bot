@echo off
setlocal
cd /d "%~dp0\..\.."

echo =======================================================
echo  Running Job-bot v2.0 Telegram & LinkedIn Flow
echo =======================================================

echo [1/4] Collecting new messages from Telegram...
python v2\main.py telegram collect
if errorlevel 1 goto error

echo [2/4] Validating Telegram jobs (MeuPadrinho)...
python v2\main.py telegram validate
if errorlevel 1 goto error

echo [3/4] Verifying LinkedIn application status...
python v2\main.py telegram linkedin
if errorlevel 1 goto error

echo [4/4] Opening eligible jobs in Google Chrome...
python v2\main.py telegram open

echo =======================================================
echo  Telegram Flow Completed Successfully!
echo =======================================================
goto end

:error
echo [!] Telegram Flow encountered an error.

:end
pause
