@echo off

call .venv\Scripts\activate

python src\main.py open-jobs %*

pause
