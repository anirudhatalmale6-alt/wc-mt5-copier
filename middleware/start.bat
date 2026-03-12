@echo off
title WC-MT5 Trade Copier
echo ============================================================
echo   WealthCharts - MT5 Trade Copier
echo ============================================================
echo.

:: Change to the directory where this batch file is located
cd /d "%~dp0"

:: Auto-update code from GitHub
echo [UPDATE] Scaricamento aggiornamenti...
powershell -Command "try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/anirudhatalmale6-alt/wc-mt5-copier/main/middleware/server.py' -OutFile 'server.py' -ErrorAction Stop; Write-Host '[UPDATE] server.py aggiornato' } catch { Write-Host '[UPDATE] Aggiornamento non riuscito, uso versione locale' }"
powershell -Command "try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/anirudhatalmale6-alt/wc-mt5-copier/main/middleware/config.py' -OutFile 'config.py' -ErrorAction Stop } catch {}"
powershell -Command "try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/anirudhatalmale6-alt/wc-mt5-copier/main/middleware/mt5_bridge.py' -OutFile 'mt5_bridge.py' -ErrorAction Stop } catch {}"
powershell -Command "try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/anirudhatalmale6-alt/wc-mt5-copier/main/middleware/telegram_notifier.py' -OutFile 'telegram_notifier.py' -ErrorAction Stop } catch {}"
if not exist "templates" mkdir templates
powershell -Command "try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/anirudhatalmale6-alt/wc-mt5-copier/main/middleware/templates/dashboard.html' -OutFile 'templates\dashboard.html' -ErrorAction Stop } catch {}"
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python non trovato! Installa Python 3.10+ da python.org
    pause
    exit /b 1
)

:: Create venv if it doesn't exist
if not exist "venv\Scripts\activate.bat" (
    echo [SETUP] Creazione ambiente virtuale...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Impossibile creare l'ambiente virtuale!
        pause
        exit /b 1
    )
)

:: Activate venv
call "venv\Scripts\activate.bat"

:: Always check if flask is installed, install deps if missing
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installazione dipendenze...
    pip install flask==3.1.0 flask-cors==5.0.1 python-dotenv==1.1.0
    echo [SETUP] Installazione MetaTrader5...
    pip install MetaTrader5 2>nul
    pip install python-telegram-bot==21.10
)

echo.
echo ============================================================
echo   SERVER IN AVVIO...
echo   Apri Chrome su: http://localhost:5000
echo   NON chiudere questa finestra!
echo   Premi Ctrl+C per fermare
echo ============================================================
echo.
python server.py
echo.
echo [!] Il server si e' fermato.
pause
