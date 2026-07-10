@echo off
cd /d "%~dp0"
title Deploy Saury Forecast System to GitHub
echo ============================================================
echo   Deploy to GitHub
echo ============================================================
echo.
where git >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Git not found. Install Git for Windows first:
  echo   https://git-scm.com/download/win
  pause
  exit /b 1
)
echo Cleaning old repo metadata (if any)...
if exist ".git" rmdir /s /q ".git"
echo.
echo [1/5] git init
git init
git config core.autocrlf true
echo [2/5] add files (large data files are excluded by .gitignore)
git add -A
echo [3/5] commit
git commit -m "Saury fishing-ground forecast system (Leaflet v3.0)"
git branch -M main
echo.
echo [4/5] Enter your GitHub repository URL.
echo   Create an EMPTY repo first at https://github.com/new (no README).
set /p REPO="Repo URL (e.g. https://github.com/USER/REPO.git): "
git remote remove origin >nul 2>&1
git remote add origin %REPO%
echo [5/5] push
git push -u origin main
echo.
if errorlevel 1 (
  echo [!] Push failed. Check the URL and your GitHub login/token.
) else (
  echo [OK] Pushed successfully.
)
pause
