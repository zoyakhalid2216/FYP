#!/usr/bin/env bash
# Setup for Desktop Automation Using AI (project stack)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Creating Python virtual environment (.venv)"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Upgrading pip"
python -m pip install --upgrade pip

echo "==> Installing project packages (PyQt5, OpenCV, Tesseract bindings, PyAutoGUI, spaCy, NLTK, SpeechRecognition, PyAudio)"
pip install -r requirements.txt

echo "==> Downloading spaCy English model (NLP Engine)"
python -m spacy download en_core_web_sm || echo "WARNING: spaCy model download failed — NLTK fallback still works"

echo "==> Preparing NLTK data (NLP Engine)"
python - <<'PY'
import nltk
for pkg in ("punkt", "punkt_tab", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"):
    try:
        nltk.download(pkg, quiet=True)
    except Exception as exc:
        print("NLTK download note:", pkg, exc)
print("NLTK ready")
PY

echo "==> Optional system packages (Linux)"
if command -v apt-get >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
      python3-tk tesseract-ocr libportaudio2 portaudio19-dev scrot \
      libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
      libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-cursor0 \
      || echo "WARNING: apt install had issues — try manually"
  else
    echo "Recommended:"
    echo "  sudo apt-get install -y python3-tk tesseract-ocr libportaudio2 portaudio19-dev scrot"
  fi
fi

echo "==> Creating data folders"
mkdir -p data/captures data/logs assets/templates
python - <<'PY'
from src.config import load_config, ensure_runtime_dirs, resolve_path
from src.db.database import get_database
from src.vision.templates_seed import ensure_template_assets
cfg = load_config()
ensure_runtime_dirs(cfg)
ensure_template_assets(resolve_path(cfg.get("paths", {}).get("templates_dir", "assets/templates")))
db = get_database(cfg)
print("Database ready at", db.db_path)
print("Create your account in the app with Sign Up Now")
PY

echo ""
echo "Setup complete."
echo "Activate:  source .venv/bin/activate"
echo "Run app:   python main.py   OR   ./run_automate_ai.sh"
echo "Desktop:   ./scripts/install_desktop.sh"
