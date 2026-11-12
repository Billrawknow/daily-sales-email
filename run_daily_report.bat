@echo off
REM Used by Windows Task Scheduler to send the daily sales email at 6 PM.
cd /d "%~dp0"
python daily_sales_report.py
