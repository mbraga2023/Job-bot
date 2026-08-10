@echo off

call .venv\Scripts\activate

echo =====================================
echo Stage 1 - Collect Telegram Jobs
echo =====================================
python src/main.py collect

echo.
echo =====================================
echo Stage 2 - Validate Job Pages
echo =====================================
python src/main.py validate

echo.
echo =====================================
echo Stage 2.5 - Check LinkedIn Status
echo =====================================
python src/main.py linkedin

echo.
echo =====================================
echo Stage 3 - Job Analysis
echo =====================================
python src/main.py analyse

echo.
echo =====================================
echo Stage 4 - Generate Report
echo =====================================
python src/main.py report

echo.
echo =====================================
echo Finished
echo =====================================

pause