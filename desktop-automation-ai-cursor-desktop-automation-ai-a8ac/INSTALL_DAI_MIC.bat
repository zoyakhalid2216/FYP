@echo off
REM Install only the DAI offline microphone packages, then you can reopen the app.
setlocal EnableExtensions
cd /d "%~dp0"
title Automate AI - Install DAI mic
if not exist ".venv\Scripts\python.exe" (
  echo Run INSTALL_ON_YOUR_WINDOWS_PC.bat first.
  pause
  exit /b 1
)
echo Installing vosk + sounddevice into this app...
".venv\Scripts\python.exe" -m pip install vosk sounddevice
if errorlevel 1 (
  echo Install failed. Stay online and try again.
  pause
  exit /b 1
)
echo.
echo OK. Close Automate AI and open it again. DAI sleeps until you say DAI wakeup.
pause
