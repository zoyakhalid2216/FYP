@echo off
REM ============================================================
REM  Automate AI — ONE-CLICK install for a Windows PC
REM  Safe to re-run if a previous install showed yaml / PyAudio errors.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

title Automate AI - Installing on your PC...
color 0A
echo.
echo  ========================================================
echo   Automate AI installer  v0.1.9
echo   If this does NOT say v0.1.9 you have an OLD copy.
echo  ========================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [!] Python was not found on PATH.
  echo     Trying to install Python 3.12 with winget...
  where winget >nul 2>&1
  if errorlevel 1 (
    echo.
    echo ERROR: Install Python first:
    echo   1. Open https://www.python.org/downloads/
    echo   2. Download Python 3.12+
    echo   3. IMPORTANT: tick "Add python.exe to PATH"
    echo   4. Install, then double-click this file again.
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
  )
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo.
  echo Close this window, open a NEW Command Prompt, then run this file again.
  pause
  exit /b 1
)

echo [1/6] Python found
python --version

echo [2/6] Creating virtual environment (.venv)
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [3/6] Installing core packages (PyYAML, PyQt5, spaCy, ...)
python -m pip install -U pip
pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Core pip install reported errors — retrying essential packages...
  pip install PyYAML PyQt5 Pillow numpy pyautogui pyperclip SpeechRecognition nltk pytest
  pip install opencv-python pytesseract mss openai google-genai spacy
)
pip install pywinauto >nul 2>&1

echo [4/6] Optional microphone library (safe to skip — Chrome voice still works)
pip install -r requirements-optional.txt
if errorlevel 1 (
  echo.
  echo [i] PyAudio did not install. That is OK.
  echo     Voice will use Chrome on this PC. Continue...
)

echo [5/6] NLP model + folders + database + offline speech
python -m pip install PyYAML vosk sounddevice >nul 2>&1
python -m spacy download en_core_web_sm >nul 2>&1
python -c "import nltk; [nltk.download(p, quiet=True) for p in ('punkt','punkt_tab','averaged_perceptron_tagger','averaged_perceptron_tagger_eng')]" 2>nul
if not exist data\captures mkdir data\captures
if not exist data\logs mkdir data\logs
if not exist data\models mkdir data\models
if not exist assets\templates mkdir assets\templates

python -c "import yaml, PyQt5; print('Core imports OK')"
if errorlevel 1 (
  echo.
  echo ERROR: Core Python packages are still missing (yaml / PyQt5).
  echo Close other Python windows, then run this installer again.
  echo If it still fails, send a screenshot of this window.
  pause
  exit /b 1
)

python -c "from src.config import load_config, ensure_runtime_dirs, resolve_path; from src.db.database import get_database; from src.vision.templates_seed import ensure_template_assets; c=load_config(); ensure_runtime_dirs(c); ensure_template_assets(resolve_path(c['paths']['templates_dir'])); get_database(c); print('Database ready')"
if errorlevel 1 (
  echo.
  echo ERROR: Database setup failed. See the message above.
  pause
  exit /b 1
)

echo Downloading offline speech model (one-time ~40MB, then works without internet)...
python -c "from src.speech.offline_stt import ensure_model, default_model_dir; from src.config import load_config; print('Speech model:', ensure_model(default_model_dir(load_config())))"
if errorlevel 1 (
  echo [i] Could not download speech model now. Connect once and run FIX_INSTALL.bat.
)

echo [6/6] Creating Desktop icon
> "%~dp0Run Automate AI.bat" (
  echo @echo off
  echo cd /d "%~dp0"
  echo if not exist ".venv\Scripts\activate.bat" ^(
  echo   echo Run INSTALL_ON_YOUR_WINDOWS_PC.bat first.
  echo   pause
  echo   exit /b 1
  echo ^)
  echo call .venv\Scripts\activate.bat
  echo python main.py
  echo if errorlevel 1 pause
)

for %%D in ("%USERPROFILE%\Desktop" "%USERPROFILE%\OneDrive\Desktop" "%PUBLIC%\Desktop") do (
  if exist %%~D copy /Y "%~dp0Run Automate AI.bat" "%%~D\Automate AI.bat" >nul 2>&1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\make_desktop_shortcut.ps1" -ProjectRoot "%~dp0"
if errorlevel 1 (
  echo PowerShell shortcut helper had an issue — Desktop .bat copy was still attempted.
)

echo.
echo  ========================================================
echo   INSTALL COMPLETE
echo.
echo   Look on the Desktop for:  Automate AI   or   Automate AI.bat
echo   Press F5 on the Desktop if it does not appear yet.
echo.
echo   Voice: DAI sleeps until you say DAI wakeup. Google/Chrome mic is required.
echo   Half-heard speech asks Do you mean this? on the DAI window.
echo   Then Sign Up with a username + password on THIS PC.
echo  ========================================================
echo.
echo Starting Automate AI now...
start "" "%~dp0Run Automate AI.bat"
pause
