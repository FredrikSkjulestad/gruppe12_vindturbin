@echo off
rem Runs the lambda 5.4 study (config.yaml) from this folder. Results go to results_lambda54\
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
for %%s in (01_polars.py 02_design.py 03_performance.py 04_report.py 05_plots.py) do (
  echo.
  echo ===== %%s =====
  ".venv\Scripts\python.exe" %%s || (echo %%s failed & pause & exit /b 1)
)
echo.
echo Done. Results are in the results_lambda54 folder.
pause
