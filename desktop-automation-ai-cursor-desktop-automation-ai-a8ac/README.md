# Automate AI — AI Desktop Automation

**Group ID:** S26CS089  
**Product Owner:** Mam Saadia Aslam

A no-code, AI-driven desktop assistant (**Automate AI**) that runs **locally on your computer**. Speak or type plain English (for example: *Open Chrome and search weather*). The app understands the command, finds UI elements on screen, performs mouse/keyboard actions, saves multi-step workflows, and keeps full logs in SQLite.

---

## Technical stack (as specified)

| Layer | Technology | Role in this repo |
|------|------------|-------------------|
| Presentation | **PyQt5** | Login + dashboard UI (`src/gui/`) |
| Speech | **Microphone API + SpeechRecognition + PyAudio** | Voice capture & STT (`src/speech/`) |
| NLP | **spaCy + NLTK** | Intent classification & entity extraction (`src/nlp/`) |
| Computer Vision | **OpenCV + Tesseract OCR** | Screen capture, template match, text locate (`src/vision/`) |
| Automation | **PyAutoGUI** | Mouse, keyboard, scroll, app launch (`src/automation/`) |
| Data | **SQLite 3** | 8 SDS tables (`src/db/`) |

End-to-end flow is wired in [`src/pipeline.py`](src/pipeline.py) and started from [`main.py`](main.py):

**UI → Speech/Text → NLP → Vision → PyAutoGUI → Logger/SQLite → Dashboard feedback**

---

## What you need

- Windows 10/11 or Linux
- Python 3.10+ (3.12 recommended)
- A real microphone (for voice commands)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for on-screen text reading

---

## Quick start — put it on your Desktop

### Windows
1. Copy/clone this project folder to your PC.
2. Double-click `scripts\install_desktop.bat`
3. Double-click **Automate AI** on your Desktop (or `Run Automate AI.bat`)

### Linux / macOS
```bash
chmod +x scripts/install_desktop.sh run_automate_ai.sh
./scripts/install_desktop.sh
```
Then double-click **Automate AI** on your Desktop (or run `./run_automate_ai.sh`).

### Create your account
1. Open Automate AI
2. Enter **your** email/username and password
3. Click **Sign Up Now** (you’re signed in automatically)
4. Next time, use **Sign In** with the same credentials

There is **no demo account** by default.

### Manual setup (optional)

#### Linux / macOS
```bash
chmod +x scripts/setup_env.sh
./scripts/setup_env.sh
source .venv/bin/activate
python main.py
```

#### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python main.py
```

---

## Extra system installs

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr libportaudio2 portaudio19-dev python3-tk scrot \
  libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
  libxcb-render-util0 libxcb-xinerama0 libxcb-cursor0
```

### Windows

1. Install Python from python.org (tick “Add Python to PATH”).
2. Install Tesseract OCR.
3. Install a PyAudio wheel that matches your Python version if `pip install PyAudio` fails.

---

## UI screens (from project wireframes)

- Login / Landing (split brand + sign-in)
- System Dashboard
- Voice Command
- Execution History
- Workflow Management
- Settings

Navigation flow: Login → Dashboard → Voice / History / Workflows / Settings → Sign Out

## How to use

1. **Sign Up Now** with your own username/email and password (or Sign In later).
2. Type a command and press **Execute Command**, or click **Speak**.
3. Leave dry-run OFF in Settings for real mouse/keyboard/browser actions.
4. Use **Workflow Management** to save / edit / replay multi-step macros.
5. Check the live **Activity log** and **Execution History** (including Screen_capture clips).

### Example commands

- `Open notepad`
- `Open Chrome and search weather`
- `Type hello from my project`
- `Click button Login`
- `Fill username with alice`
- `Scroll down 5`
- `Wait 2 seconds`
- `Run workflow Open Notepad Demo`

---

## Project structure

```
main.py                 → start the PyQt5 app
config/default.yaml     → theme, mic, vision, automation settings
requirements.txt        → project stack packages
scripts/setup_env.sh    → create venv, install deps, seed DB
src/
  gui/                  → PyQt5 presentation layer
  speech/               → Microphone API + Speech-to-Text
  nlp/                  → spaCy / NLTK intent + entities
  agent/                → hybrid click resolver (accessibility / OCR / vision)
  vision/               → OpenCV + Tesseract
  automation/           → PyAutoGUI engine
  workflows/            → multi-step macros
  logging_audit/        → execution logs + screenshot records
  db/                   → SQLite schema + repositories
  pipeline.py           → end-to-end orchestration
tests/                  → unit/integration tests
data/                   → local DB + captures (created on first run)
assets/templates/       → template images for OpenCV matching
```

---

## Database tables (Phase 2 SDS)

`User`, `User_Conf`, `Workflow`, `AutomationRule`, `Task`, `NLP_Command`, `Execution_log`, `Screen_capture`

---

## Run tests

```bash
source .venv/bin/activate
pytest -q
```

---

## Safety notes

- Dry-run is ON by default (no real mouse/keyboard until you uncheck it).
- Fail-safe: move the mouse to a screen corner to abort live PyAutoGUI actions.
- Voice uses your system microphone through the Microphone API (PyAudio).

---

## Architecture

Local 3-tier design:

**Presentation (PyQt5) → Logic (Speech + NLP + Vision + Automation) → Data (SQLite)**

Clicks are **not** exact-text screenshot matches. The agent plans the instruction, then resolves the target in this order:

1. **Accessibility tree** (Windows UI Automation via optional `pywinauto`)
2. **OCR screen model** (case-insensitive / semantic text, e.g. “click Microsoft” → “login With Microsoft”)
3. **Vision** (Tesseract / template fallback)

After each click it verifies **PAGE_CHANGED** (pixel change, window title, or URL — including Microsoft login domains). If that fails it recovers with the next strategy before asking “What's next?”. Chrome launched by the app uses `--force-renderer-accessibility` and `--remote-debugging-port=9222` so the accessibility and page-URL layers can attach.
