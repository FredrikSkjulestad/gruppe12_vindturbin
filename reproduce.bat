@echo off
rem Reproduces the whole blade selection: UIUC database -> screening -> XFOIL check -> final blade.
rem First run: creates the virtual environment, installs the pinned packages and downloads XFOIL
rem (needs internet). Takes about 10 to 15 minutes. See README.md, "Reproduce the result".
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
%PY% reproduce.py %*
echo.
pause
