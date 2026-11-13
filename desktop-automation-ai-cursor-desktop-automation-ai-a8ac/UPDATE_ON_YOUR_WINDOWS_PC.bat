@echo off
REM Keep this window open even if something fails. Double-click must show text.
if /I not "%~1"=="KEEPOPEN" (
  start "Automate AI Update" cmd /k "%~f0" KEEPOPEN
  exit /b
)

setlocal EnableExtensions
cd /d "%~dp0"
title Automate AI - Updating your laptop copy
color 0B

echo.
echo  ========================================================
echo   Automate AI updater
echo   If you can read this, the updater IS running.
echo   Folder:
echo   %CD%
echo  ========================================================
echo.

if not exist "%~dp0main.py" (
  echo ERROR: This file is not inside the Automate AI project folder.
  echo Put UPDATE_ON_YOUR_WINDOWS_PC.bat next to main.py, then double-click it.
  echo.
  pause
  exit /b 1
)

echo [1/3] Getting the latest code...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update_project.ps1"
if errorlevel 1 (
  echo.
  echo The automatic update did not finish.
  echo Download a ZIP while logged into GitHub, then run this file again.
  echo Branch page:
  echo   https://github.com/muneeb-267/desktop-automation-ai/tree/cursor/desktop-automation-ai-a8ac
  echo.
  pause
  exit /b 1
)

echo.
echo [2/3] Refreshing Python packages in .venv ...
if not exist ".venv\Scripts\python.exe" (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python not found. Install from https://www.python.org/downloads/
    echo Tick "Add python.exe to PATH", then run FIX_INSTALL.bat.
    pause
    exit /b 1
  )
  python -m venv .venv
)
set "PY=.venv\Scripts\python.exe"
"%PY%" -m pip install -U pip
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Retrying essential packages...
  "%PY%" -m pip install PyYAML PyQt5 Pillow numpy pyautogui pyperclip SpeechRecognition nltk pytest
  "%PY%" -m pip install opencv-python pytesseract mss openai google-genai spacy vosk sounddevice
)
"%PY%" -m pip install vosk sounddevice
"%PY%" -c "import yaml, PyQt5; print('OK: yaml and PyQt5')"

echo.
echo [3/3] Refreshing launcher...
> "%~dp0Run Automate AI.bat" (
  echo @echo off
  echo cd /d "%~dp0"
  echo if not exist ".venv\Scripts\activate.bat" ^(
  echo   echo Run FIX_INSTALL.bat first.
  echo   pause
  echo   exit /b 1
  echo ^)
  echo call .venv\Scripts\activate.bat
  echo python main.py
  echo if errorlevel 1 pause
)
REM Do not call CREATE_DESKTOP_ICON.bat here — it pauses and starts the app twice.

echo.
echo  ========================================================
echo   UPDATE FINISHED
echo   Close any old DAI window, then use the new one.
echo  ========================================================
echo.
echo Starting Automate AI now...
start "" "%~dp0Run Automate AI.bat"
echo.
echo This window will stay open. You can close it after the app starts.
pause
