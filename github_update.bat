@echo off
cd /d "%~dp0"
title Update GitHub - cleanup + LICENSE
echo ============================================================
echo   Update repo: remove legacy desktop files + add LICENSE
echo ============================================================
echo.
where git >nul 2>&1 || (echo [ERROR] Git not found. & pause & exit /b 1)
echo [1/4] Removing legacy desktop-version files...
git rm --ignore-unmatch main_gui.py visualizer.py run.bat generate_demos.py
echo [2/4] Staging LICENSE and other changes...
git add -A
echo [3/4] Commit...
git commit -m "Remove legacy desktop version; add MIT LICENSE"
echo [4/4] Push...
git push
echo.
echo Optional: set repository description (requires GitHub CLI ^"gh^").
where gh >nul 2>&1
if not errorlevel 1 (
  gh repo edit petercttseng-ux/saury-forecast --description "西北太平洋秋刀魚漁場速預報系統（Leaflet）· 農業部水產試驗所 漁海況研究小組" --add-topic saury --add-topic fisheries --add-topic oceanography --add-topic leaflet --add-topic flask
  echo Description and topics set via gh.
) else (
  echo [i] gh not installed - set description manually on GitHub ^(see instructions^).
)
echo.
echo Done.
pause
