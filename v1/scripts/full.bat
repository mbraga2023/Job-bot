@echo off

cd /d "%~dp0\..\.."
call .venv\Scripts\activate

echo =====================================
echo Stage 1 - Collect Telegram Jobs
echo =====================================
python v1\src\main.py collect

echo.
echo =====================================
echo Stage 2 - Validate Job Pages
echo =====================================
python v1\src\main.py validate

echo.
echo =====================================
echo Stage 2.5 - Check LinkedIn Status
echo =====================================
python v1\src\main.py linkedin

echo.
echo =====================================
echo Stage 3 - Job Analysis
echo =====================================
python v1\src\main.py analyse

echo.
echo =====================================
echo Stage 4 - Generate Report
echo =====================================
python v1\src\main.py report

echo.
echo =====================================
echo Finished
echo =====================================

pause