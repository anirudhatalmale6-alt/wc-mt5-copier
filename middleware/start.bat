@echo off
title WC-MT5 Trade Copier
echo ============================================================
echo   WealthCharts - MT5 Trade Copier
echo ============================================================
echo.

:: Change to the directory where this batch file is located
cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please install Python 3.10+ from python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Create venv if it doesn't exist
if not exist "venv\Scripts\activate.bat" (
    echo [SETUP] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
)

:: Activate venv
call "venv\Scripts\activate.bat"

:: Always check if flask is installed, install deps if missing
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing dependencies...
    pip install flask==3.1.0 flask-cors==5.0.1 python-dotenv==1.1.0
    if errorlevel 1 (
        echo [WARNING] Some packages failed to install. Trying individually...
        pip install flask
        pip install flask-cors
        pip install python-dotenv
    )
    echo [SETUP] Installing MetaTrader5 library...
    pip install MetaTrader5==5.0.4621
    if errorlevel 1 (
        echo [WARNING] MetaTrader5 package failed. Will try alternative...
        pip install MetaTrader5
        if errorlevel 1 (
            echo [WARNING] MetaTrader5 not available for your Python version.
            echo [WARNING] The dashboard will work but MT5 connection requires Python 3.8-3.12.
        )
    )
    pip install python-telegram-bot==21.10
)

echo.
echo [INFO] Starting middleware server on http://127.0.0.1:5000
echo [INFO] Open your browser to http://127.0.0.1:5000 for the dashboard
echo [INFO] Press Ctrl+C to stop
echo.
python server.py
pause
