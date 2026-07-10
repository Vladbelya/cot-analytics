@echo off
title COT Analytics - Update Data
echo [INFO] Starting background data update pipeline (COT & Market Prices)...

cd /d "%~dp0"
set PYTHONPATH=.

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe src/pipeline.py
) else (
    echo [ERROR] Virtual environment .venv not found!
    pause
    exit /b 1
)

echo [INFO] Data update finished successfully!
pause
