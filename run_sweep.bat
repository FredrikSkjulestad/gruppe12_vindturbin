@echo off
rem Reruns the earlier lambda 5.0..6.5 sweep (Part 2) with config_sweep.yaml. Results go to results\
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
%PY% reproduce.py --sweep-only %*
echo.
pause
