@echo off

call .venv\Scripts\activate

python src\main.py collect
python src\main.py validate
python src\main.py report

pause