@echo off
cd /d "%~dp0"
title Deploy static site to GitHub Pages
echo ============================================================
echo   Deploy static frontend (docs/) to GitHub Pages
echo ============================================================
where git >nul 2>&1 || (echo [ERROR] Git not found. & pause & exit /b 1)
echo [1/3] Staging changes (docs/, LICENSE, remove legacy)...
git rm --ignore-unmatch main_gui.py visualizer.py run.bat generate_demos.py >nul 2>&1
git add -A
echo [2/3] Commit...
git commit -m "Add static client-side frontend for GitHub Pages (docs/)"
echo [3/3] Push...
git push
echo.
echo ============================================================
echo NEXT: enable GitHub Pages (one time):
echo   1. Open https://github.com/petercttseng-ux/saury-forecast/settings/pages
echo   2. Source = Deploy from a branch
echo   3. Branch = main   Folder = /docs   then Save
echo   4. Wait ~1 min, site: https://petercttseng-ux.github.io/saury-forecast/
echo ============================================================
pause
