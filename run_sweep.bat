@echo off
rem Reruns the earlier lambda 5.0..6.5 sweep (Part 2) with config_sweep.yaml. Results go to results\
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set WIND_BLADE_CONFIG=config_sweep.yaml
for %%s in (01_polars.py 02_design.py 03_performance.py 04_report.py 05_plots.py) do (
  echo.
  echo ===== %%s =====
  ".venv\Scripts\python.exe" %%s || (echo %%s failed & pause & exit /b 1)
)
echo.
echo Done. Results are in the results folder.
pause
