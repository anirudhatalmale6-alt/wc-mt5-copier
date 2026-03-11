@echo off
title WC-MT5 Trade Copier
echo ============================================================
echo   WealthCharts → MT5 Trade Copier
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.10+ from python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Install dependencies if needed
if not exist "venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [SETUP] Installing dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo [INFO] Starting middleware server on http://127.0.0.1:5000
echo [INFO] Open your browser to http://127.0.0.1:5000 for the dashboard
echo [INFO] Press Ctrl+C to stop
echo.
python server.py
pause
