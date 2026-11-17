@echo off
title Daily Sales Email - Setup
cd /d "%~dp0"
echo.
echo  Daily Sales Email - one-time setup
echo  ==================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo  Python is not installed. Install it from https://www.python.org/downloads/
  echo  ^(tick "Add python.exe to PATH" during installation^), then run this setup again.
  echo.
  pause
  exit /b 1
)

echo  [1/3] Installing what the report needs...
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo  Couldn't install the requirements. Check the internet connection and run setup again.
  pause
  exit /b 1
)

echo  [2/3] Email settings...
if not exist .env (
  copy /y .env.example .env >nul
  echo        Notepad will open. Fill in your Gmail address, App Password and who gets the report,
  echo        then SAVE and CLOSE Notepad to continue.
  start /wait notepad .env
) else (
  echo        .env already exists - keeping your settings.
)

echo  [3/3] Scheduling the report for 6:00 PM every day...
schtasks /Create /TN "Daily Sales Email" /TR "\"%~dp0run_daily_report.bat\"" /SC DAILY /ST 18:00 /F >nul
if errorlevel 1 (
  echo  Couldn't create the scheduled task. Right-click setup.bat and choose "Run as administrator".
  pause
  exit /b 1
)
REM Laptops: by default Windows only runs tasks on mains power. Allow it on battery too.
powershell -NoProfile -Command "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable; Set-ScheduledTask -TaskName 'Daily Sales Email' -Settings $s" >nul 2>nul

echo.
echo  Done! The sales summary will be emailed every day at 6:00 PM
echo  while this computer is on and you are logged in.
echo.
echo  Next: double-click "send_test_report.bat" to send one now and check it arrives.
echo.
pause