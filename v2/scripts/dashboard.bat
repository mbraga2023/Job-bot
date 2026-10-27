@echo off
setlocal
cd /d "%~dp0\..\.."

set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -c "import ollama" >nul 2>nul
if errorlevel 1 (
    echo [!] The Python Ollama client is missing from "%PYTHON%".
    echo Install the project dependencies with:
    echo   "%PYTHON%" -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo Launching Job-bot v2.0 Dashboard...
"%PYTHON%" v2\main.py dashboard
pause
