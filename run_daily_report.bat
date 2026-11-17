@echo off
REM Started by Windows Task Scheduler every day at 6 PM (created by setup.bat).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% daily_sales_report.py --scheduled
if %errorlevel%==9009 (
  echo %date% ^| %time:~0,8% ^| ERROR   ^|   0 rows ^| scheduled ^| Python was not found on this computer>> run_log.txt
)
