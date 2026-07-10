@echo off
cd /d "%~dp0"
title Saury Fishing-Ground Forecast System
echo ============================================================
echo   Saury Fishing-Ground Forecast System (Leaflet)
echo   Fisheries Research Institute - Ocean Group
echo ============================================================
echo.
echo [1/3] Checking Python...
python --version
if errorlevel 1 (
  echo [ERROR] Python not found. Install Python 3.8+ and check "Add Python to PATH".
  echo Download: https://www.python.org/downloads/
  pause
  exit /b 1
)
echo.
echo [2/3] Installing dependencies (first run may take a few minutes)...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install packages. Check your internet connection.
  pause
  exit /b 1
)
echo.
echo [3/3] Starting server at http://localhost:5000
echo First launch parses data files, wait 30-90 seconds, then open the browser.
echo Keep this window open. Press Ctrl+C to stop.
echo ------------------------------------------------------------
start "" http://localhost:5000
python app.py
echo.
echo Server stopped. If you see errors above, take a screenshot.
pause
