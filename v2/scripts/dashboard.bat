@echo off
setlocal
cd /d "%~dp0\..\.."

echo Launching Job-bot v2.0 Dashboard...
python v2\main.py dashboard
pause
