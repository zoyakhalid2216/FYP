@echo off
REM ============================================================
REM  Automate AI — REPAIR a broken Windows install
REM  Fixes: No module named 'yaml'  /  PyAudio build failure
REM  Double-click this in the project folder. Does NOT need C++ tools.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Automate AI - Repair install
color 0B

echo.
echo  ========================================================
echo   Automate AI repair  (v0.1.9)
echo   This ignores PyAudio. Chrome voice still works.
echo  ========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo Install Python from https://www.python.org/downloads/
    echo Tick "Add python.exe to PATH", then run this again.
    pause
    exit /b 1
  )
  python -m venv .venv
)

set "PY=.venv\Scripts\python.exe"
echo Using: %PY%
"%PY%" -m pip install -U pip

echo.
echo Installing required packages (PyYAML first)...
"%PY%" -m pip install PyYAML
"%PY%" -m pip install PyQt5 Pillow numpy pyautogui pyperclip SpeechRecognition nltk pytest
"%PY%" -m pip install opencv-python pytesseract mss openai google-genai spacy
echo.
echo Optional Windows accessibility (hybrid clicks — safe to skip on failure)...
"%PY%" -m pip install pywinauto
if errorlevel 1 (
  echo [i] pywinauto did not install. OCR/vision clicks still work.
)
if exist requirements.txt (
  echo Installing remaining requirements (no PyAudio)...
  "%PY%" -m pip install -r requirements.txt
)

echo.
echo Checking yaml / PyQt5...
"%PY%" -c "import yaml, PyQt5; print('OK: yaml and PyQt5 installed')"
if errorlevel 1 (
  echo.
  echo ERROR: yaml still missing. Close this window and try:
  echo   1. Open the project folder
  echo   2. Shift+right-click empty space - Open PowerShell
  echo   3. Run:  .\.venv\Scripts\python.exe -m pip install PyYAML
  pause
  exit /b 1
)

echo.
echo Offline speech (DAI listener — works without internet after this)...
"%PY%" -m pip install vosk sounddevice
if not exist data\models mkdir data\models
"%PY%" -c "from src.speech.offline_stt import ensure_model, default_model_dir; from src.config import load_config; print('Speech model:', ensure_model(default_model_dir(load_config())))"
if errorlevel 1 (
  echo [i] Speech model download skipped. Connect once, then run FIX_INSTALL.bat again.
)

echo.
"%PY%" -m spacy download en_core_web_sm
"%PY%" -c "import nltk; [nltk.download(p, quiet=True) for p in ('punkt','punkt_tab','averaged_perceptron_tagger','averaged_perceptron_tagger_eng')]"
if not exist data\captures mkdir data\captures
if not exist data\logs mkdir data\logs
if not exist assets\templates mkdir assets\templates
"%PY%" -c "from src.config import load_config, ensure_runtime_dirs, resolve_path; from src.db.database import get_database; from src.vision.templates_seed import ensure_template_assets; c=load_config(); ensure_runtime_dirs(c); ensure_template_assets(resolve_path(c['paths']['templates_dir'])); get_database(c); print('Database ready')"
if errorlevel 1 (
  echo Database setup had an error. See above.
  pause
  exit /b 1
)

echo.
echo  ========================================================
echo   REPAIR COMPLETE — yaml is installed. You can start the app.
echo  ========================================================
echo.
if exist "Run Automate AI.bat" (
  start "" "%~dp0Run Automate AI.bat"
) else (
  "%PY%" main.py
)
pause
