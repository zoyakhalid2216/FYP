"""Chrome Web Speech bridge — voice without USB mic / PyAudio drivers."""

from __future__ import annotations

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import urlparse


_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Automate AI · Voice</title>
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; display: grid; place-items: center;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: radial-gradient(1200px 600px at 20% 0%, #dce9ff, transparent),
                  linear-gradient(160deg, #f4f7fb, #e8eef7 55%, #dfe7f3);
      color: #122033;
    }
    .card {
      width: min(440px, 92vw); padding: 28px 26px 22px; border-radius: 18px;
      background: rgba(255,255,255,.92); border: 1px solid #d7e0ec;
      box-shadow: 0 18px 50px rgba(18,32,51,.12);
      text-align: center;
    }
    .pulse {
      width: 84px; height: 84px; margin: 8px auto 18px; border-radius: 50%;
      display: grid; place-items: center; font-size: 34px;
      background: #122033; color: #fff;
      animation: pulse 1.1s ease-in-out infinite;
    }
    @keyframes pulse {
      0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(18,32,51,.35); }
      50% { transform: scale(1.05); box-shadow: 0 0 0 16px rgba(18,32,51,0); }
    }
    h1 { font-size: 22px; margin: 0 0 6px; }
    p { margin: 0 0 10px; color: #516173; line-height: 1.4; }
    #status { font-weight: 700; color: #122033; min-height: 1.4em; }
    #heard {
      margin-top: 14px; padding: 12px; border-radius: 10px; background: #f0f4f9;
      font-size: 15px; min-height: 48px; color: #122033;
    }
    button {
      margin-top: 14px; border: 0; border-radius: 10px; padding: 10px 16px;
      background: #122033; color: #fff; font-weight: 700; cursor: pointer;
    }
    .hint { font-size: 12px; color: #7a8796; margin-top: 12px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="pulse">🎙</div>
    <h1>Speak your command</h1>
    <p>Uses Chrome voice recognition — laptop mic is fine, no USB mic needed.</p>
    <div id="status">Starting…</div>
    <div id="heard">Listening…</div>
    <button id="retry" type="button">Try again</button>
    <div class="hint">This window closes automatically when your command is captured.</div>
  </div>
  <script>
    const statusEl = document.getElementById("status");
    const heardEl = document.getElementById("heard");
    const retryBtn = document.getElementById("retry");
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    let sent = false;
    let recognition = null;
    let speechStarted = false;
    let silenceTimer = null;
    let startTimer = null;
    let maxPhraseTimer = null;
    let accumulatedFinal = "";
    let lastInterim = "";

    async function postResult(payload) {
      if (sent) return;
      sent = true;
      if (silenceTimer) clearTimeout(silenceTimer);
      if (startTimer) clearTimeout(startTimer);
      if (maxPhraseTimer) clearTimeout(maxPhraseTimer);
      try {
        await fetch("/result", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } catch (e) {}
      statusEl.textContent = payload.ok ? "Got it — returning…" : "Could not hear you";
      setTimeout(() => { try { window.close(); } catch (e) {} }, 450);
    }

    async function postInterim(text) {
      try {
        await fetch("/interim", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text }),
        });
      } catch (e) {}
    }

    function start() {
      sent = false;
      speechStarted = false;
      accumulatedFinal = "";
      lastInterim = "";

      if (!SpeechRec) {
        statusEl.textContent = "Speech API unavailable in this browser";
        heardEl.textContent = "Open this page in Google Chrome.";
        postResult({ ok: false, error: "SpeechRecognition unsupported" });
        return;
      }
      recognition = new SpeechRec();
      recognition.lang = "en-US";
      recognition.interimResults = true;
      recognition.maxAlternatives = 3;
      recognition.continuous = true;

      // Start timeout: if user says nothing within 8s
      startTimer = setTimeout(() => {
        if (!speechStarted && !sent) {
          postResult({ ok: false, error: "no-speech" });
        }
      }, 8000);

      // Max phrase limit: 30s
      maxPhraseTimer = setTimeout(() => {
        if (!sent) {
          const full = (accumulatedFinal + " " + lastInterim).trim();
          if (full) postResult({ ok: true, text: full });
          else postResult({ ok: false, error: "timeout" });
        }
      }, 30000);

      recognition.onstart = () => {
        statusEl.textContent = "Speak now… (listening)";
        heardEl.textContent = "Listening…";
      };
      recognition.onresult = (event) => {
        speechStarted = true;
        if (startTimer) { clearTimeout(startTimer); startTimer = null; }

        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const res = event.results[i];
          const t = res[0] ? res[0].transcript : "";
          if (res.isFinal) {
            accumulatedFinal += (accumulatedFinal ? " " : "") + t.trim();
          } else {
            interim += t;
          }
        }
        lastInterim = interim;
        const currentDisplay = (accumulatedFinal + " " + interim).trim();
        heardEl.textContent = currentDisplay || "Listening…";
        if (currentDisplay) {
          postInterim(currentDisplay);
        }

        // Reset silence timer on every speech event — wait 1.8s of silence after speech before closing
        if (silenceTimer) clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => {
          const finalCandidate = (accumulatedFinal + " " + lastInterim).trim();
          if (finalCandidate) {
            statusEl.textContent = "Transcribed";
            postResult({ ok: true, text: finalCandidate });
          }
        }, 1800);
      };
      recognition.onerror = (event) => {
        const err = event.error || "error";
        statusEl.textContent = "Mic issue: " + err;
        heardEl.textContent = "You can type the command in Automate AI instead.";
        if (err === "not-allowed" || err === "service-not-allowed") {
          postResult({ ok: false, error: err });
        }
      };
      recognition.onend = () => {
        if (sent) return;
        const currentText = (accumulatedFinal + " " + lastInterim).trim();
        if (currentText && speechStarted) {
          postResult({ ok: true, text: currentText });
        } else if (!speechStarted) {
          // Auto-restart if browser unexpectedly ended before speech
          try { recognition.start(); } catch (e) {}
        }
      };
      try {
        recognition.start();
      } catch (e) {
        postResult({ ok: false, error: String(e) });
      }
    }

    retryBtn.addEventListener("click", () => {
      sent = false;
      try { recognition && recognition.stop(); } catch (e) {}
      setTimeout(start, 200);
    });
    start();
  </script>
</body>
</html>
"""


class BrowserSpeechBridge:
    """One-shot localhost page that captures Chrome Web Speech and returns text."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._result: Optional[dict] = None
        self._event = threading.Event()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def listen(
        self,
        *,
        timeout: float = 30.0,
        silence_seconds: float = 1.8,
        start_timeout: float = 8.0,
        status_cb: Optional[Callable[[str], None]] = None,
        open_browser: bool = True,
    ) -> str:
        self._status_cb = status_cb
        emit = status_cb or (lambda _m: None)
        self._result = None
        self._event.clear()

        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path in ("/", "/index.html", "/voice"):
                    body = _HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                if path == "/interim":
                    try:
                        payload = json.loads(raw.decode("utf-8") or "{}")
                    except Exception:
                        payload = {}
                    text = str(payload.get("text") or "").strip()
                    if text and bridge._status_cb:
                        bridge._status_cb(f"Listening: {text}")
                    body = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if path == "/result":
                    try:
                        payload = json.loads(raw.decode("utf-8") or "{}")
                    except Exception:
                        payload = {"ok": False, "error": "bad json"}
                    bridge._result = payload
                    bridge._event.set()
                    body = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

        # Bind — retry nearby ports if busy
        server = None
        last_exc = None
        for offset in range(0, 8):
            port = self.port + offset
            try:
                server = ThreadingHTTPServer((self.host, port), Handler)
                self.port = port
                break
            except OSError as exc:
                last_exc = exc
        if server is None:
            raise RuntimeError(f"Could not start voice bridge ({last_exc})")

        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

        try:
            emit("Opening Chrome voice…")
            if open_browser:
                self._open_browser(self.url)
            emit("Speak now in the Chrome voice window…")
            ok = self._event.wait(timeout=timeout)
            if not ok or not self._result:
                raise RuntimeError(
                    "No speech captured. A Chrome/Edge window should open — "
                    "click Allow for the microphone, then speak. Or type the command."
                )
            if not self._result.get("ok"):
                err = self._result.get("error") or "no-speech"
                if err in ("no-speech", "aborted"):
                    raise RuntimeError(
                        "Didn’t catch speech. Click Mic again and speak clearly."
                    )
                if err in ("not-allowed", "service-not-allowed"):
                    raise RuntimeError(
                        "Chrome blocked the mic. Allow microphone for localhost, then retry."
                    )
                raise RuntimeError(f"Voice error ({err}). Type your command instead.")
            text = " ".join(str(self._result.get("text") or "").split())
            if not text:
                raise RuntimeError("Empty transcription. Please try again.")
            return text
        finally:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
            self._server = None

    def _open_browser(self, url: str) -> None:
        import subprocess

        chrome = find_chromium_browser()
        if chrome:
            subprocess.Popen(
                [
                    chrome,
                    "--new-window",
                    f"--app={url}",
                    "--disable-features=TranslateUI",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        # Last resort: default browser (Edge on many Windows PCs — Web Speech works there too)
        webbrowser.open(url)


def find_chromium_browser() -> str:
    """Locate Chrome or Edge so voice works on Windows without PATH entries."""
    import os
    import shutil
    from pathlib import Path

    named = (
        shutil.which("chrome")
        or shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("msedge")
        or shutil.which("microsoft-edge")
    )
    if named:
        return named

    home = Path.home()
    candidates = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        home / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        home / "AppData" / "Local" / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/google-chrome-stable"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/microsoft-edge"),
    ]
    for path in candidates:
        try:
            if path.is_file():
                return str(path)
        except Exception:
            continue
    return ""
