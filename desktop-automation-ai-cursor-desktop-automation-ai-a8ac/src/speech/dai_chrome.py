"""Always-on Google/Chrome Web Speech listener for DAI (does not close after each phrase)."""

from __future__ import annotations

import json
import queue
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from PyQt5.QtCore import QThread, pyqtSignal

from src.speech.browser_bridge import find_chromium_browser

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DAI Google Mic</title>
  <style>
    :root { color-scheme: light; }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
      background: #0f172a; color: #e2e8f0;
      min-height: 100vh; display: grid; place-items: center;
    }
    .card { padding: 12px 14px; text-align: center; width: 100%; }
    h1 { font-size: 15px; margin: 0 0 4px; }
    p, #status { font-size: 12px; margin: 0; color: #94a3b8; }
    #heard { margin-top: 8px; font-size: 13px; color: #f8fafc; min-height: 1.3em; }
    button {
      margin-top: 10px; border: 0; border-radius: 8px; padding: 8px 12px;
      background: #4f46e5; color: #fff; font-weight: 700; cursor: pointer;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>AI · Google mic</h1>
    <p>Keep this window open. Chrome hears you while AI sleeps and after wakeup.</p>
    <div id="status">Starting…</div>
    <div id="heard">Say “AI” or “AI, open Chrome”</div>
    <button id="retry" type="button">Start mic</button>
  </div>
  <script>
    const statusEl = document.getElementById("status");
    const heardEl = document.getElementById("heard");
    const retryBtn = document.getElementById("retry");
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let stopped = false;
    let lastPartialAt = 0;

    async function post(payload) {
      try {
        await fetch("/event", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
      } catch (err) {}
    }

    function startRec() {
      if (!SpeechRec) {
        statusEl.textContent = "This browser has no Web Speech API. Use Chrome.";
        post({kind: "error", error: "no-speech-api"});
        return;
      }
      if (recognition) {
        try { recognition.onend = null; recognition.stop(); } catch (e) {}
      }
      const rec = new SpeechRec();
      recognition = rec;
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 5;
      rec.lang = "en-US";
      rec.onstart = function () {
        statusEl.textContent = "Google mic is on";
        post({kind: "ready"});
      };
      rec.onresult = function (event) {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const text = (result[0] && result[0].transcript || "").trim();
          if (result.isFinal) {
            const alts = [];
            for (let j = 0; j < result.length; j++) {
              const piece = (result[j].transcript || "").trim();
              if (piece) alts.push(piece);
            }
            heardEl.textContent = text || "…";
            post({kind: "final", text: text, alternatives: alts});
          } else if (text) {
            interim = text;
          }
        }
        if (interim) {
          const now = Date.now();
          if (now - lastPartialAt > 160) {
            lastPartialAt = now;
            heardEl.textContent = interim;
            post({kind: "partial", text: interim});
          }
        }
      };
      rec.onerror = function (event) {
        const err = (event && event.error) || "error";
        statusEl.textContent = "Mic: " + err;
        if (err === "not-allowed" || err === "service-not-allowed") {
          post({kind: "error", error: err});
        }
      };
      rec.onend = function () {
        if (stopped) return;
        statusEl.textContent = "Restarting Google mic…";
        setTimeout(function () {
          if (!stopped) {
            try { rec.start(); } catch (e) {
              setTimeout(startRec, 400);
            }
          }
        }, 180);
      };
      try {
        rec.start();
      } catch (e) {
        statusEl.textContent = "Click Start mic, then Allow";
      }
    }

    retryBtn.addEventListener("click", function () {
      stopped = false;
      startRec();
    });
    startRec();
    setInterval(function () { post({kind: "ping"}); }, 5000);
  </script>
</body>
</html>
"""


def chrome_available() -> bool:
    return bool(find_chromium_browser())


class DaiChromeThread(QThread):
    """Persistent Chrome page posting partial/final transcripts to a local server."""

    heard_final = pyqtSignal(str, list)
    heard_partial = pyqtSignal(str)
    engine_ready = pyqtSignal()
    failed = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, parent=None, host: str = "127.0.0.1", port: int = 8766) -> None:
        super().__init__(parent)
        self.host = host
        self.port = port
        self._stop = False
        self._session_active = False
        self._q: queue.Queue = queue.Queue()
        self._server: Optional[ThreadingHTTPServer] = None
        self._proc: Optional[subprocess.Popen] = None
        self._ready_emitted = False

    def stop(self) -> None:
        self._stop = True
        self._q.put({"kind": "stop"})
        self._kill_chrome()
        server = self._server
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass

    def set_session_active(self, active: bool) -> None:
        self._session_active = bool(active)

    def _kill_chrome(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
        self._proc = None

    def run(self) -> None:
        chrome = find_chromium_browser()
        if not chrome:
            self.failed.emit(
                "Google Chrome / Edge not found. Install Chrome for DAI listening."
            )
            return
        try:
            self._start_server()
        except Exception as exc:
            self.failed.emit(f"Could not start DAI Google mic server: {exc}")
            return
        self.status.emit("Opening Google mic in Chrome…")
        try:
            self._start_chrome(chrome)
        except Exception as exc:
            self.failed.emit(str(exc))
            self._shutdown_server()
            return

        deadline = time.monotonic() + 18
        last_ping = time.monotonic()
        while not self._stop:
            try:
                item = self._q.get(timeout=0.25)
            except queue.Empty:
                if self._proc is not None and self._proc.poll() is not None:
                    self.failed.emit("Chrome Google-mic window closed.")
                    break
                if not self._ready_emitted and time.monotonic() > deadline:
                    self.failed.emit(
                        "Chrome did not start the Google mic. Click Allow, or Start mic."
                    )
                    break
                continue
            kind = str(item.get("kind") or "")
            if kind == "stop":
                break
            if kind == "error":
                err = str(item.get("error") or "error")
                if err in ("not-allowed", "service-not-allowed"):
                    self.failed.emit(
                        "Chrome blocked the mic. Allow microphone for localhost, then retry."
                    )
                    break
                if err == "no-speech-api":
                    self.failed.emit("This browser cannot use Google speech. Install Chrome.")
                    break
                continue
            if kind in ("ready", "ping"):
                last_ping = time.monotonic()
                if kind == "ready" and not self._ready_emitted:
                    self._ready_emitted = True
                    self.engine_ready.emit()
                    self.status.emit("Google mic ready — say AI, then speak your command")
                continue
            if kind == "partial":
                text = " ".join(str(item.get("text") or "").split())
                if text:
                    self.heard_partial.emit(text)
                continue
            if kind == "final":
                text = " ".join(str(item.get("text") or "").split())
                alts = []
                for piece in item.get("alternatives") or []:
                    cleaned = " ".join(str(piece or "").split())
                    if cleaned:
                        alts.append(cleaned)
                if text:
                    self.heard_final.emit(text, alts)
                continue
            _ = last_ping

        self._kill_chrome()
        self._shutdown_server()

    def _start_server(self) -> None:
        html = _HTML.encode("utf-8")
        q = self._q
        thread = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # noqa: A003
                return

            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path in ("/", "/index.html"):
                    body = html
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if path == "/health":
                    body = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

            def do_POST(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b"{}"
                if path == "/event":
                    try:
                        payload = json.loads(raw.decode("utf-8") or "{}")
                    except Exception:
                        payload = {}
                    if not thread._stop:
                        q.put(payload)
                    body = b'{"ok":true}'
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

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
            raise RuntimeError(f"Could not bind DAI Google mic port ({last_exc})")
        self._server = server
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

    def _shutdown_server(self) -> None:
        server = self._server
        self._server = None
        if server is None:
            return
        try:
            server.shutdown()
        except Exception:
            pass
        try:
            server.server_close()
        except Exception:
            pass

    def _chrome_corner(self) -> tuple:
        try:
            import ctypes

            height = int(ctypes.windll.user32.GetSystemMetrics(1))
            return 12, max(48, height - 168)
        except Exception:
            return 12, 720

    def _start_chrome(self, chrome: str) -> None:
        profile = Path(tempfile.gettempdir()) / "automate-ai-dai-chrome"
        profile.mkdir(parents=True, exist_ok=True)
        url = f"http://{self.host}:{self.port}/"
        pos_x, pos_y = self._chrome_corner()
        self._proc = subprocess.Popen(
            [
                chrome,
                "--new-window",
                f"--app={url}",
                "--disable-features=TranslateUI",
                "--autoplay-policy=no-user-gesture-required",
                "--use-fake-ui-for-media-stream",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
                "--window-size=320,120",
                f"--window-position={pos_x},{pos_y}",
                f"--user-data-dir={profile}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


_DAI_CHROME_RECTS = {}


def set_dai_chrome_minimized(minimized: bool) -> int:
    """Park the DAI Google Mic window off-screen so Web Speech keeps running."""
    if platform_name() != "windows":
        return 0
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return 0

    user32 = ctypes.windll.user32
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    RECT = wintypes.RECT
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd, _lp):
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""
        if "DAI Google Mic" in title or "AI Google Mic" in title:
            found.append(hwnd)
        return True

    user32.EnumWindows(_enum, 0)
    for hwnd in found:
        if minimized:
            rect = RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                _DAI_CHROME_RECTS[int(hwnd)] = (rect.left, rect.top)
            user32.SetWindowPos(hwnd, 0, -640, -360, 0, 0, SWP_NOSIZE | SWP_NOZORDER)
        else:
            pos = _DAI_CHROME_RECTS.pop(int(hwnd), (12, 720))
            user32.SetWindowPos(hwnd, 0, int(pos[0]), int(pos[1]), 0, 0, SWP_NOSIZE | SWP_NOZORDER)
    return len(found)


def platform_name() -> str:
    import sys

    return "windows" if sys.platform == "win32" else sys.platform
