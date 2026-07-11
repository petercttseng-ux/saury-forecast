@echo off
cd /d "%~dp0"
title Deploy static site to GitHub Pages
echo ============================================================
echo   Deploy static frontend (docs/) to GitHub Pages
echo ============================================================
where git >nul 2>&1 || (echo [ERROR] Git not found. & pause & exit /b 1)
echo [1/4] Remove legacy files, stage changes...
git rm --ignore-unmatch main_gui.py visualizer.py run.bat generate_demos.py >nul 2>&1
git add -A
echo [2/4] Commit...
git commit -m "Update site (docs/ static frontend)"
echo [3/4] Pull remote changes (auto-merge)...
git pull origin main --no-edit
echo [4/4] Push...
git push -u origin main
echo.
echo ============================================================
echo If first time: enable Pages at
echo   https://github.com/petercttseng-ux/saury-forecast/settings/pages
echo   Source=Deploy from a branch, Branch=main, Folder=/docs, Save
echo Site: https://petercttseng-ux.github.io/saury-forecast/
echo ============================================================
pause
