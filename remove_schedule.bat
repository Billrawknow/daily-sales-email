@echo off
REM Stops the automatic 6 PM email (your files and settings are kept).
schtasks /Delete /TN "Daily Sales Email" /F
pause
