@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment missing. Run scripts\install_desktop.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python main.py
if errorlevel 1 pause
