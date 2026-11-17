@echo off
title Daily Sales Email - Test
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% daily_sales_report.py
echo.
echo  Check the inbox. Every run is recorded in run_log.txt.
pause
