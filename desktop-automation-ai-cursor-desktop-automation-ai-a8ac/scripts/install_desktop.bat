@echo off
REM Automate AI — Windows desktop installer
setlocal EnableExtensions
cd /d "%~dp0\.."

echo ==============================================
echo  Automate AI - Desktop Installer (Windows)
echo ==============================================

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo Enable "Add python.exe to PATH" during setup.
  pause
  exit /b 1
)

echo ==^> Creating virtual environment
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -U pip
pip install -r requirements.txt
pip install pywinauto >nul 2>&1
pip install -r requirements-optional.txt
if errorlevel 1 echo [i] PyAudio optional — Chrome voice still works.
python -m pip install PyYAML >nul 2>&1
python -m spacy download en_core_web_sm
python -c "import nltk; [nltk.download(p, quiet=True) for p in ('punkt','punkt_tab','averaged_perceptron_tagger','averaged_perceptron_tagger_eng')]"

if not exist data\captures mkdir data\captures
if not exist data\logs mkdir data\logs
if not exist assets\templates mkdir assets\templates

python -c "from src.config import load_config, ensure_runtime_dirs, resolve_path; from src.db.database import get_database; from src.vision.templates_seed import ensure_template_assets; c=load_config(); ensure_runtime_dirs(c); ensure_template_assets(resolve_path(c['paths']['templates_dir'])); print('DB', get_database(c).db_path)"

REM Create Desktop + project launchers
set "LAUNCHER=%~dp0..\Run Automate AI.bat"
> "%LAUNCHER%" (
  echo @echo off
  echo cd /d "%~dp0"
  echo call .venv\Scripts\activate.bat
  echo python main.py
  echo if errorlevel 1 pause
)
copy /Y "%LAUNCHER%" "%USERPROFILE%\Desktop\Automate AI.bat" >nul 2>&1

echo.
echo Install complete.
echo   Create your account in the app with Sign Up Now.
echo   Double-click "Automate AI" on your Desktop, or "Run Automate AI.bat" in the project folder.
pause
