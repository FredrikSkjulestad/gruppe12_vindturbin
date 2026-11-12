@echo off
rem Only the lambda 5.4 XFOIL study (steps 01 to 05), with the top 5 from the screening ranking
rem already in screening\results. Results go to results_lambda54\. Use reproduce.bat for everything.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=
for %%v in (3.13 3.12) do (
  if not defined PY (py -%%v -c "" >nul 2>&1 && set PY=py -%%v)
)
if not defined PY (python -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>&1 && set PY=python)
if not defined PY (
  echo Python 3.12 or 3.13 was not found. Install it, for example:
  echo   winget install --id Python.Python.3.13 --exact --scope machine
  pause
  exit /b 1
)
%PY% reproduce.py --xfoil-only %*
echo.
pause
