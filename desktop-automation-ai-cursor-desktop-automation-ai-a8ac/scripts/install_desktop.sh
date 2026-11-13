#!/usr/bin/env bash
# One-click setup + desktop shortcut for Automate AI (Linux / macOS)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "══════════════════════════════════════════════"
echo " Automate AI — Desktop Installer"
echo "══════════════════════════════════════════════"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10+ first."
  exit 1
fi

# Linux system deps (best-effort)
if command -v apt-get >/dev/null 2>&1; then
  echo "==> Installing Linux packages (needs sudo once)…"
  sudo apt-get update -qq || true
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-venv python3-pip python3-dev python3-tk \
    tesseract-ocr libportaudio2 portaudio19-dev scrot \
    libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-cursor0 \
    || echo "WARNING: some apt packages failed — continuing"
fi

echo "==> Creating virtual environment"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm || true
python - <<'PY'
import nltk
for pkg in ("punkt", "punkt_tab", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"):
    try:
        nltk.download(pkg, quiet=True)
    except Exception as exc:
        print("NLTK note:", pkg, exc)
PY

mkdir -p data/captures data/logs assets/templates
python - <<'PY'
from src.config import load_config, ensure_runtime_dirs, resolve_path
from src.db.database import get_database
from src.vision.templates_seed import ensure_template_assets
cfg = load_config()
ensure_runtime_dirs(cfg)
ensure_template_assets(resolve_path(cfg["paths"]["templates_dir"]))
db = get_database(cfg)
print("DB ready:", db.db_path)
print("Create your account in the app with Sign Up Now")
PY

# Launch scripts
cat > "$ROOT/run_automate_ai.sh" <<EOF
#!/usr/bin/env bash
cd "$ROOT"
source "$ROOT/.venv/bin/activate"
exec python "$ROOT/main.py"
EOF
chmod +x "$ROOT/run_automate_ai.sh" "$ROOT/scripts/install_desktop.sh" "$ROOT/scripts/setup_env.sh" 2>/dev/null || true

# Linux .desktop shortcut on user Desktop + apps menu
if [[ "$(uname -s)" == "Linux" ]]; then
  DESKTOP_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
  mkdir -p "$DESKTOP_DIR" "$HOME/.local/share/applications"
  ICON_PATH="$ROOT/assets/templates/icon_chrome.png"
  for TARGET in "$DESKTOP_DIR/Automate AI.desktop" "$HOME/.local/share/applications/automate-ai.desktop"; do
    cat > "$TARGET" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Automate AI
Comment=AI Desktop Automation (S26CS089)
Exec=$ROOT/run_automate_ai.sh
Path=$ROOT
Icon=$ICON_PATH
Terminal=false
Categories=Utility;Development;
StartupNotify=true
EOF
    chmod +x "$TARGET" || true
  done
  echo "==> Desktop shortcut: $DESKTOP_DIR/Automate AI.desktop"
fi

# macOS: create a double-clickable .command on Desktop
if [[ "$(uname -s)" == "Darwin" ]]; then
  CMD="$HOME/Desktop/Automate AI.command"
  cat > "$CMD" <<EOF
#!/bin/bash
cd "$ROOT"
source "$ROOT/.venv/bin/activate"
exec python "$ROOT/main.py"
EOF
  chmod +x "$CMD"
  echo "==> Desktop shortcut: $CMD"
fi

echo ""
echo "Install complete."
echo "  Create your account in the app (Sign Up Now)."
echo "  Run:    ./run_automate_ai.sh"
echo "  Or double-click the Automate AI icon on your Desktop."
