@echo off
title Saury Fishing Ground Information System

cd /d "%~dp0"

cls
echo.
echo  ============================================================
echo   Saury Fishing Ground Information System
echo   TFRI - Fish & Oceanography Research Group
echo  ============================================================
echo.

:: --- 1. Check Python ---
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  [ERROR] Python not found.
    echo          Please install Python 3.9+: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  [OK] %PY_VER%
echo.

:: --- 2. Check required packages ---
echo  Checking packages...
set PKG_OK=1

python -c "import numpy"      >nul 2>&1 || set PKG_OK=0
python -c "import pandas"     >nul 2>&1 || set PKG_OK=0
python -c "import matplotlib" >nul 2>&1 || set PKG_OK=0
python -c "import requests"   >nul 2>&1 || set PKG_OK=0
python -c "import bs4"        >nul 2>&1 || set PKG_OK=0
python -c "import scipy"      >nul 2>&1 || set PKG_OK=0
python -c "import cartopy"    >nul 2>&1 || set PKG_OK=0

if %PKG_OK%==1 (
    echo  [OK] All packages installed.
    echo.
    goto :RUN
)

:: --- 3. Install missing packages ---
echo.
echo  Some packages are missing.
set /p ANS="  Auto-install now? [Y/N] (default Y): "
if /i "%ANS%"=="" set ANS=Y
if /i not "%ANS%"=="Y" (
    echo  Please run manually: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo  [ERROR] Installation failed.
    echo          Try running as Administrator, or:
    echo            pip install -r requirements.txt
    pause
    exit /b 1
)
echo  [OK] Packages installed.
echo.

:: --- 4. Launch application ---
:RUN
echo  Starting application...
echo  (The window will appear shortly. First run downloads JMA data.)
echo.

python -u main_gui.py

:: --- 5. Error handler ---
if %ERRORLEVEL% neq 0 (
    echo.
    echo  ============================================================
    echo  [ERROR] Application exited with error code %ERRORLEVEL%
    echo.
    echo  Troubleshooting:
    echo    1. Missing packages  : pip install -r requirements.txt
    echo    2. cartopy issue     : conda install -c conda-forge cartopy
    echo    3. Network error     : check connection to data.jma.go.jp
    echo  ============================================================
    echo.
    pause
)
