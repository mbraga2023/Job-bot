@echo off

cd /d "%~dp0\..\.."
call .venv\Scripts\activate

python v1\src\main.py open-jobs %*

pause
