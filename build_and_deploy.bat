@echo off
cd /d "%~dp0"
set LOG=build_deploy.log
echo ===== build+deploy %date% %time% ===== > %LOG%
where python >nul 2>&1 && (set PY=python) || (set PY=py)
echo [1/5] build_static.py >> %LOG%
%PY% build_static.py >> %LOG% 2>&1
if errorlevel 1 (echo BUILD_FAILED >> %LOG% & exit)
echo [2/5] git add >> %LOG%
git add -A >> %LOG% 2>&1
echo [3/5] git commit >> %LOG%
git commit -m "Add load-latest button; rebuild docs/data" >> %LOG% 2>&1
echo [4/5] git pull >> %LOG%
git pull origin main --no-edit >> %LOG% 2>&1
echo [5/5] git push >> %LOG%
git push -u origin main >> %LOG% 2>&1
echo ===== DONE ===== >> %LOG%
exit
