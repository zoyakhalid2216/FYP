"""PyAutoGUI wrappers — real OS mouse/keyboard/browser automation."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
import webbrowser
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

_CHROME_A11Y_FLAGS = (
    "--force-renderer-accessibility",
    "--remote-debugging-port=9222",
)


class AutomationEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        auto = (config or {}).get("automation", {})
        self.dry_run = bool(auto.get("dry_run", False))
        self.pause_seconds = float(auto.get("pause_seconds", 0.04))
        self.type_interval = float(auto.get("type_interval", 0.01))
        self.move_duration = float(auto.get("move_duration", 0.05))
        self.post_action_delay = float(auto.get("post_action_delay", 0.06))
        self.app_launch_wait = float(auto.get("app_launch_wait", 0.45))
        self.failsafe = bool(auto.get("failsafe", True))
        self._history: List[Dict[str, Any]] = []
        self._session: List[Dict[str, Any]] = []
        self._session_active = False
        self._pyautogui = None
        self._pyautogui_error = ""
        self._pyautogui = self._load_pyautogui()
        self.capture_region: Dict[str, Any] = {}

    def _load_pyautogui(self):
        """Import PyAutoGUI; tolerate missing tkinter/MouseInfo on some Linux setups."""
        try:
            import pyautogui

            pyautogui.FAILSAFE = self.failsafe
            pyautogui.PAUSE = self.pause_seconds
            return pyautogui
        except BaseException as first_exc:
            self._pyautogui_error = str(first_exc)
            # MouseInfo requires tkinter on Linux; stub it and retry once
            try:
                import sys
                import types

                if "mouseinfo" not in sys.modules:
                    stub = types.ModuleType("mouseinfo")
                    stub.MouseInfoWindow = object  # type: ignore[attr-defined]
                    sys.modules["mouseinfo"] = stub
                import pyautogui

                pyautogui.FAILSAFE = self.failsafe
                pyautogui.PAUSE = self.pause_seconds
                self._pyautogui_error = ""
                return pyautogui
            except BaseException as second_exc:
                self._pyautogui_error = str(second_exc)
                return None

    @property
    def mouse_ready(self) -> bool:
        return self._pyautogui is not None

    def set_dry_run(self, enabled: bool) -> None:
        self.dry_run = enabled
        if self._pyautogui is not None:
            self._pyautogui.PAUSE = self.pause_seconds

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    @property
    def session_history(self) -> List[Dict[str, Any]]:
        return list(self._session)

    @property
    def recording(self) -> bool:
        return self._session_active

    def clear_history(self) -> None:
        self._history.clear()

    def start_recording(self) -> None:
        """Begin accumulating actions for Save as Workflow."""
        self._session.clear()
        self._session_active = True

    def stop_recording(self) -> List[Dict[str, Any]]:
        self._session_active = False
        return list(self._session)

    def clear_session(self) -> None:
        self._session.clear()
        self._session_active = False

    def _record(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        entry = {"action": action, "dry_run": self.dry_run, **kwargs}
        self._history.append(entry)
        if self._session_active:
            self._session.append(entry)
        return entry

    def _sleep(self, seconds: Optional[float] = None) -> None:
        time.sleep(self.post_action_delay if seconds is None else max(0.0, seconds))

    def move_to(self, x: int, y: int) -> Dict[str, Any]:
        entry = self._record("move_to", x=x, y=y)
        if not self.dry_run and self._pyautogui:
            self._pyautogui.moveTo(x, y, duration=self.move_duration)
        return entry

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        clicks: int = 1,
        *,
        label: str = "",
    ) -> Dict[str, Any]:
        mapped_x, mapped_y = x, y
        if x is not None and y is not None and self._pyautogui is not None:
            mapped_x, mapped_y = self.map_capture_point(int(x), int(y))
        rec: Dict[str, Any] = {"x": mapped_x, "y": mapped_y, "button": button, "clicks": clicks}
        if label:
            rec["label"] = str(label)
        entry = self._record("click", **rec)
        if not self.dry_run and self._pyautogui:
            if mapped_x is not None and mapped_y is not None:
                self._pyautogui.click(mapped_x, mapped_y, clicks=clicks, button=button, interval=0.08)
            else:
                self._pyautogui.click(clicks=clicks, button=button)
            self._sleep()
        return entry

    def map_capture_point(self, x: int, y: int, region: Optional[Dict[str, Any]] = None) -> tuple:
        """Map screenshot pixels onto PyAutoGUI's logical screen (Windows DPI)."""
        if self._pyautogui is None:
            return x, y
        try:
            sw, sh = self._pyautogui.size()
        except Exception:
            return x, y
        info = region if isinstance(region, dict) else getattr(self, "capture_region", None)
        if not isinstance(info, dict):
            info = {}
        fw = int(info.get("width") or 0)
        fh = int(info.get("height") or 0)
        left = int(info.get("left") or 0)
        top = int(info.get("top") or 0)
        if fw > 0 and fh > 0 and sw > 0 and sh > 0 and (fw != sw or fh != sh):
            x = int(round(x * (sw / float(fw))))
            y = int(round(y * (sh / float(fh))))
        return x + left, y + top

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        return self.click(x=x, y=y, clicks=2)

    def type_text(self, text: str, *, paste: bool = True) -> Dict[str, Any]:
        """Type text. Uses clipboard paste for speed/unicode when possible."""
        entry = self._record("type_text", text=text, paste=paste)
        if self.dry_run or not self._pyautogui:
            return entry
        if paste and text:
            try:
                import pyperclip

                old = None
                try:
                    old = pyperclip.paste()
                except Exception:
                    old = None
                pyperclip.copy(text)
                system = platform.system().lower()
                if system == "darwin":
                    self._pyautogui.hotkey("command", "v")
                else:
                    self._pyautogui.hotkey("ctrl", "v")
                self._sleep(0.15)
                if old is not None:
                    try:
                        pyperclip.copy(old)
                    except Exception:
                        pass
                return entry
            except Exception:
                pass
        # Fallback character typing
        self._pyautogui.write(text, interval=self.type_interval)
        self._sleep()
        return entry

    def press(self, key: str) -> Dict[str, Any]:
        entry = self._record("press", key=key)
        if not self.dry_run and self._pyautogui:
            if "+" in key:
                parts = [p.strip() for p in key.split("+")]
                # Normalize common aliases
                parts = ["command" if p == "cmd" else p for p in parts]
                self._pyautogui.hotkey(*parts)
            else:
                self._pyautogui.press(key)
            self._sleep()
        return entry

    def scroll(self, direction: str = "down", amount: int = 3) -> Dict[str, Any]:
        clicks = amount * 120 if direction in ("up", "left") else -amount * 120
        # pyautogui.scroll uses "clicks" units; keep moderate values
        units = amount * 3 if direction in ("up", "left") else -amount * 3
        if direction in ("left", "right"):
            entry = self._record("hscroll", direction=direction, amount=amount)
            if not self.dry_run and self._pyautogui:
                try:
                    self._pyautogui.hscroll(units)
                except Exception:
                    self._pyautogui.scroll(units)
                self._sleep()
            return entry
        entry = self._record("scroll", direction=direction, amount=amount)
        if not self.dry_run and self._pyautogui:
            self._pyautogui.scroll(units)
            self._sleep()
        return entry

    def wait(self, seconds: float = 1.0) -> Dict[str, Any]:
        entry = self._record("wait", seconds=seconds)
        # Always wait a little even in dry-run for sequencing realism; shorter if dry
        delay = float(seconds)
        if self.dry_run:
            delay = min(delay, 0.15)
        time.sleep(max(0.0, delay))
        return entry

    def open_url(self, url: str) -> Dict[str, Any]:
        """Open a URL in the default/Chrome browser (real navigation)."""
        entry = self._record("open_url", url=url)
        if self.dry_run:
            return entry
        system = platform.system().lower()
        launched = False
        chrome = _chrome_executable()
        try:
            if chrome:
                cmd = [chrome, *_CHROME_A11Y_FLAGS, "--new-tab", url]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                launched = True
                entry["launched_with"] = chrome
            elif system == "windows":
                subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
                launched = True
            elif system == "darwin":
                subprocess.Popen(["open", url])
                launched = True
            else:
                subprocess.Popen(["xdg-open", url])
                launched = True
        except Exception as exc:
            entry["error"] = str(exc)
        if not launched:
            webbrowser.open(url)
            entry["launched_with"] = "webbrowser"
        self._sleep(self.app_launch_wait)
        return entry

    def search_google(self, query: str) -> Dict[str, Any]:
        """Open Google and run a search query directly."""
        q = (query or "").strip()
        url = f"https://www.google.com/search?q={quote_plus(q)}" if q else "https://www.google.com"
        entry = self._record("search_google", query=q, url=url)
        open_res = self.open_url(url)
        entry["open"] = open_res
        return entry

    def open_app(self, app: str) -> Dict[str, Any]:
        """Launch a common desktop application by friendly name."""
        app_l = (app or "").strip().lower()
        # Treat google as browser+google.com
        if app_l in ("google", "google.com"):
            return self.open_url("https://www.google.com")
        system = platform.system().lower()
        commands = self._resolve_launch_command(app_l, system)
        entry = self._record("open_app", app=app_l, commands=commands, system=system)
        if self.dry_run:
            return entry
        last_error: Optional[Exception] = None
        for cmd in commands:
            try:
                if isinstance(cmd, (list, tuple)):
                    subprocess.Popen(
                        list(cmd),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif system == "windows":
                    subprocess.Popen(cmd, shell=True)
                else:
                    subprocess.Popen(cmd, shell=True)
                self._sleep(self.app_launch_wait)
                entry["launched_with"] = cmd
                return entry
            except Exception as exc:
                last_error = exc
        # Fallback: treat as a file/folder name on the user's machine
        try:
            return self.find_and_open(app)
        except Exception:
            pass
        if last_error:
            entry["error"] = str(last_error)
            raise RuntimeError(f"Could not open app '{app}': {last_error}") from last_error
        raise RuntimeError(f"Could not open app '{app}'")

    def open_path(self, path: str, *, record: bool = True) -> Dict[str, Any]:
        """Open any file or folder with the OS default app."""
        from pathlib import Path

        p = Path(path).expanduser()
        entry: Dict[str, Any] = {"action": "open_path", "dry_run": self.dry_run, "path": str(p)}
        if record:
            entry = self._record("open_path", path=str(p))
        if self.dry_run:
            return entry
        if not p.exists():
            raise RuntimeError(f"Path not found: {p}")
        system = platform.system().lower()
        try:
            if system == "windows":
                os_start = getattr(__import__("os"), "startfile", None)
                if os_start:
                    os_start(str(p))  # type: ignore[misc]
                else:
                    subprocess.Popen(["cmd", "/c", "start", "", str(p)], shell=False)
            elif system == "darwin":
                subprocess.Popen(["open", str(p)])
            else:
                subprocess.Popen(["xdg-open", str(p)])
            entry["opened"] = str(p)
            self._sleep(self.app_launch_wait)
            return entry
        except Exception as exc:
            entry["error"] = str(exc)
            raise RuntimeError(f"Could not open '{p}': {exc}") from exc

    def resolve_path(self, query: str, *, kind: str = "any"):
        """Resolve a file/folder name or path under Desktop/Documents/Downloads/Home."""
        from pathlib import Path

        q = (query or "").strip().strip("\"'")
        if not q:
            raise RuntimeError("Missing file or folder name.")

        home = Path.home()
        specials = {
            "desktop": home / "Desktop",
            "downloads": home / "Downloads",
            "documents": home / "Documents",
            "docs": home / "Documents",
            "pictures": home / "Pictures",
            "music": home / "Music",
            "videos": home / "Videos",
            "home": home,
            "this pc": home,
        }
        onedrive = home / "OneDrive" / "Desktop"
        if onedrive.exists() and not (home / "Desktop").exists():
            specials["desktop"] = onedrive

        key = q.lower()
        if key in specials and specials[key].exists():
            return specials[key]

        direct = Path(q).expanduser()
        if direct.exists():
            return direct

        search_roots = [
            home / "Desktop",
            home / "OneDrive" / "Desktop",
            home / "Documents",
            home / "Downloads",
            home / "OneDrive" / "Documents",
            home,
        ]
        needle = key.replace("_", " ")
        candidates: List[Path] = []
        for root in search_roots:
            if not root.exists():
                continue
            try:
                for pattern in ("*", "*/*", "*/*/*"):
                    for hit in root.glob(pattern):
                        name = hit.name.lower()
                        stem = hit.stem.lower().replace("_", " ").replace("-", " ")
                        if kind == "folder" and not hit.is_dir():
                            continue
                        if kind == "file" and not hit.is_file():
                            continue
                        score_ok = (
                            needle in name
                            or needle in stem
                            or all(tok in stem for tok in needle.split() if len(tok) > 2)
                        )
                        if score_ok:
                            candidates.append(hit)
                    if candidates:
                        break
            except Exception:
                continue
            if candidates:
                break

        if not candidates:
            raise RuntimeError(
                f"Could not find “{q}” on Desktop/Documents/Downloads. "
                "Try the exact name, e.g. report.docx"
            )

        def rank(p: Path) -> tuple:
            stem = p.stem.lower().replace("_", " ").replace("-", " ")
            exact = 0 if stem == needle or p.name.lower() == needle else 1
            starts = 0 if stem.startswith(needle) or p.name.lower().startswith(needle) else 1
            is_dir = 0 if (kind == "folder" and p.is_dir()) or (kind != "folder" and p.is_file()) else 1
            return (exact, starts, is_dir, len(str(p)))

        return sorted(candidates, key=rank)[0]

    def copy_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Copy a file (or folder tree) to a destination path or folder."""
        from pathlib import Path

        src = self.resolve_path(source, kind="any")
        dest_query = (destination or "").strip().strip("\"'")
        entry = self._record(
            "copy_file", source=str(src), destination=dest_query, matched_source=str(src)
        )
        if not dest_query:
            raise RuntimeError("Say where to paste, e.g. Copy file report to Desktop")

        # Destination may be an existing folder name, a path, or a new file path
        try:
            dest = self.resolve_path(dest_query, kind="any")
        except RuntimeError:
            dest = Path(dest_query).expanduser()
            if not dest.is_absolute():
                # Prefer Desktop for relative new paths
                dest = Path.home() / "Desktop" / dest_query

        if self.dry_run:
            entry["dest_resolved"] = str(dest)
            return entry

        if dest.exists() and dest.is_dir():
            target = dest / src.name
        elif dest.suffix or not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            target = dest
        else:
            target = dest / src.name

        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        entry["copied_to"] = str(target)
        entry["dest_resolved"] = str(target)
        self._sleep(0.05)
        return entry

    def move_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Move a file/folder to a destination folder or path."""
        from pathlib import Path

        src = self.resolve_path(source, kind="any")
        dest_query = (destination or "").strip().strip("\"'")
        entry = self._record(
            "move_file", source=str(src), destination=dest_query, matched_source=str(src)
        )
        if not dest_query:
            raise RuntimeError("Say where to move it, e.g. Move file report to Documents")

        try:
            dest = self.resolve_path(dest_query, kind="any")
        except RuntimeError:
            dest = Path(dest_query).expanduser()
            if not dest.is_absolute():
                dest = Path.home() / "Desktop" / dest_query

        if self.dry_run:
            entry["dest_resolved"] = str(dest)
            return entry

        if dest.exists() and dest.is_dir():
            target = dest / src.name
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            target = dest

        shutil.move(str(src), str(target))
        entry["moved_to"] = str(target)
        entry["dest_resolved"] = str(target)
        self._sleep(0.05)
        return entry

    def find_and_open(self, query: str, *, kind: str = "any") -> Dict[str, Any]:
        """
        Find a file/folder by name under Desktop/Documents/Downloads/Home and open it.
        Also resolves well-known folders like Desktop, Downloads, Documents.
        """
        q = (query or "").strip().strip("\"'")
        entry = self._record("find_and_open", query=q, kind=kind)
        if not q:
            raise RuntimeError("Nothing to open — say a file or folder name.")

        try:
            best = self.resolve_path(q, kind=kind)
        except RuntimeError:
            system = platform.system().lower()
            if not self.dry_run and system == "windows":
                try:
                    subprocess.Popen(f'start "" "{q}"', shell=True)
                    entry["launched_with"] = "start"
                    return entry
                except Exception:
                    pass
            raise

        result = self.open_path(str(best), record=False)
        entry["matched"] = str(best)
        entry["open"] = result
        return entry

    def focus_address_bar_and_search(self, query: str) -> Dict[str, Any]:
        """Focus browser address bar and search (fallback path)."""
        entry = self._record("address_bar_search", query=query)
        self.press("ctrl+l")
        self.wait(0.25)
        self.type_text(query, paste=True)
        self.press("enter")
        self.wait(0.8)
        return entry

    def _resolve_launch_command(self, app: str, system: str) -> List[Any]:
        chrome_cmd = _browser_launch_command()
        mapping_win: Dict[str, List[Any]] = {
            "chrome": [chrome_cmd, "start chrome", "start msedge"] if chrome_cmd else ["start chrome", "start msedge"],
            "msedge": ["start msedge"],
            "firefox": ["start firefox"],
            "notepad": ["notepad"],
            "calculator": ["calc"],
            "explorer": ["explorer"],
            "cmd": ["start cmd"],
            "code": ["code"],
            "terminal": ["start wt", "start cmd"],
            "gmail": ["start https://mail.google.com"],
            "youtube": ["start https://www.youtube.com"],
        }
        chrome_bin = _chrome_executable()
        mapping_linux = {
            "chrome": [
                [chrome_bin, *_CHROME_A11Y_FLAGS] if chrome_bin else ["google-chrome", *_CHROME_A11Y_FLAGS],
                ["chromium"],
                ["firefox"],
            ],
            "firefox": [["firefox"]],
            "notepad": [["gedit"], ["xed"], ["mousepad"], ["xed"]],
            "calculator": [["gnome-calculator"], ["kcalc"], ["galculator"]],
            "explorer": [["thunar"], ["nautilus"], ["xdg-open", os_path_home()]],
            "terminal": [["x-terminal-emulator"], ["gnome-terminal"], ["xterm"]],
            "code": [["code"]],
            "cmd": [["x-terminal-emulator"]],
            "msedge": [["microsoft-edge"], ["microsoft-edge-stable"]],
            "gmail": [[chrome_bin, "https://mail.google.com"] if chrome_bin else ["xdg-open", "https://mail.google.com"]],
            "youtube": [[chrome_bin, "https://www.youtube.com"] if chrome_bin else ["xdg-open", "https://www.youtube.com"]],
        }
        mapping_mac = {
            "chrome": [["open", "-a", "Google Chrome"]],
            "firefox": [["open", "-a", "Firefox"]],
            "notepad": [["open", "-a", "TextEdit"]],
            "calculator": [["open", "-a", "Calculator"]],
            "explorer": [["open", "."]],
            "terminal": [["open", "-a", "Terminal"]],
            "code": [["open", "-a", "Visual Studio Code"], ["code"]],
            "gmail": [["open", "https://mail.google.com"]],
            "youtube": [["open", "https://www.youtube.com"]],
        }
        if system == "windows":
            cmds = mapping_win.get(app, [f"start {app}"])
            return [c for c in cmds if c]
        if system == "darwin":
            return mapping_mac.get(app, [["open", "-a", app]])
        cmds = mapping_linux.get(app)
        if not cmds:
            return [[app]]
        # Filter out None chrome paths
        cleaned = []
        for c in cmds:
            if c and c[0]:
                cleaned.append(c)
        return cleaned or [[app]]

    def get_active_window_title(self) -> str:
        """Get the title of the currently focused/active window."""
        sys_name = platform.system().lower()
        if sys_name == "windows":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        return buf.value
            except Exception:
                pass
        elif sys_name == "darwin":
            try:
                script = 'tell application "System Events" to get name of first process whose frontmost is true'
                res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2.0)
                return res.stdout.strip()
            except Exception:
                pass
        elif sys_name == "linux":
            try:
                res = subprocess.run(["xdotool", "getactivewindow", "getwindowname"], capture_output=True, text=True, timeout=2.0)
                return res.stdout.strip()
            except Exception:
                pass
        return ""

    def is_process_running(self, proc_name: str) -> bool:
        """Check whether a process is currently running."""
        sys_name = platform.system().lower()
        target = proc_name.lower().strip()
        if sys_name == "windows":
            try:
                res = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {proc_name}"],
                    capture_output=True,
                    text=True,
                    timeout=3.0,
                )
                return target in res.stdout.lower()
            except Exception:
                return False
        else:
            try:
                base = target.replace(".exe", "")
                res = subprocess.run(["pgrep", "-f", base], capture_output=True, timeout=3.0)
                return res.returncode == 0
            except Exception:
                return False

    def _resolve_process_names(self, app: str) -> List[str]:
        app_lower = app.lower().strip()
        if app_lower.endswith(".exe"):
            return [app_lower]
        mapping: Dict[str, List[str]] = {
            "chrome": ["chrome.exe"],
            "google chrome": ["chrome.exe"],
            "notepad": ["notepad.exe"],
            "edge": ["msedge.exe"],
            "msedge": ["msedge.exe"],
            "microsoft edge": ["msedge.exe"],
            "firefox": ["firefox.exe"],
            "calculator": ["CalculatorApp.exe", "calc.exe"],
            "calc": ["calc.exe", "CalculatorApp.exe"],
            "code": ["Code.exe"],
            "vscode": ["Code.exe"],
            "visual studio code": ["Code.exe"],
            "explorer": ["explorer.exe"],
            "cmd": ["cmd.exe"],
            "terminal": ["WindowsTerminal.exe", "cmd.exe"],
        }
        return mapping.get(app_lower, [f"{app_lower}.exe"])

    def close_focused_window(self) -> Dict[str, Any]:
        """Close the active window gracefully with a guard preventing Automate AI self-close."""
        active_title = self.get_active_window_title()
        title_l = (active_title or "").lower()
        # Self-close guard: prevent closing Automate AI window without confirmation
        is_self = any(k in title_l for k in ("automate ai", "automate-ai", "desktop-automation", "desktop automation"))
        if is_self:
            return {
                "action": "close_focused_window",
                "blocked": True,
                "needs_confirm": True,
                "confirm_prompt": "You are about to close the Automate AI window. Please confirm if you want to exit Automate AI.",
                "active_title": active_title,
                "success": False,
            }

        entry = self._record("close_focused_window", active_title=active_title)
        if self.dry_run:
            entry["dry_run"] = True
            entry["success"] = True
            return entry

        # Live graceful close via Alt+F4
        self.press("alt+f4")
        self.wait(0.5)
        new_title = self.get_active_window_title()
        entry["previous_title"] = active_title
        entry["current_title"] = new_title
        entry["success"] = (new_title != active_title) or (not active_title)
        return entry

    def close_app(self, app_name: str) -> Dict[str, Any]:
        """Close an application gracefully (pywinauto / WM_CLOSE / taskkill without /F)."""
        app_clean = (app_name or "").strip()
        entry = self._record("close_app", app=app_clean)
        if not app_clean:
            entry["success"] = False
            entry["error"] = "No application specified to close."
            return entry

        if self.dry_run:
            entry["dry_run"] = True
            entry["success"] = True
            entry["status"] = "dry_run"
            return entry

        sys_name = platform.system().lower()
        if sys_name == "windows":
            procs = self._resolve_process_names(app_clean)
            running_proc = None
            for p in procs:
                if self.is_process_running(p):
                    running_proc = p
                    break

            if not running_proc:
                entry["success"] = True
                entry["status"] = "not_running"
                entry["message"] = f"{app_clean} is not running."
                return entry

            # 1. Attempt pywinauto graceful close if available
            closed_via_pywinauto = False
            try:
                import pywinauto

                app_ctrl = pywinauto.Application().connect(path=running_proc, timeout=2.0)
                app_ctrl.top_window().close()
                closed_via_pywinauto = True
            except Exception:
                pass

            # 2. Send WM_CLOSE to matching windows
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.windll.user32
                WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                matched_hwnds = []

                def enum_proc(hwnd, lparam):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            if app_clean.lower() in buf.value.lower():
                                matched_hwnds.append(hwnd)
                    return True

                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
                for h in matched_hwnds:
                    user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE = 0x0010
            except Exception:
                pass

            # 3. Graceful taskkill (NO /F flag = graceful WM_CLOSE)
            try:
                subprocess.run(
                    ["taskkill", "/IM", running_proc],
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                )
            except Exception as exc:
                entry["taskkill_error"] = str(exc)

            # 4. Verification: wait up to 3.5s for process to exit
            time.sleep(0.4)
            for _ in range(11):
                if not self.is_process_running(running_proc):
                    entry["success"] = True
                    entry["status"] = "closed"
                    entry["proc"] = running_proc
                    return entry
                time.sleep(0.3)

            # If still running, the app likely has unsaved work prompting the user
            entry["success"] = False
            entry["status"] = "waiting_for_user"
            entry["proc"] = running_proc
            entry["message"] = f"{app_clean} did not exit — it may have unsaved changes or is waiting for user confirmation."
            return entry
        elif sys_name == "darwin":
            try:
                subprocess.run(["osascript", "-e", f'quit app "{app_clean}"'], capture_output=True, timeout=5.0)
                entry["success"] = True
                entry["status"] = "closed"
                return entry
            except Exception as exc:
                entry["success"] = False
                entry["error"] = str(exc)
                return entry
        else:
            try:
                subprocess.run(["pkill", "-15", "-f", app_clean], capture_output=True, timeout=5.0)
                entry["success"] = True
                entry["status"] = "closed"
                return entry
            except Exception as exc:
                entry["success"] = False
                entry["error"] = str(exc)
                return entry

    def minimize_window(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        """Minimize the active window or target app."""
        entry = self._record("minimize_window", app=app_name or "")
        if self.dry_run:
            entry["success"] = True
            entry["dry_run"] = True
            return entry
        sys_name = platform.system().lower()
        if sys_name == "windows":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
                    entry["success"] = True
                    return entry
            except Exception:
                pass
            self.press("win+down")
            entry["success"] = True
            return entry
        elif sys_name == "darwin":
            self.press("cmd+m")
            entry["success"] = True
            return entry
        else:
            self.press("alt+f9")
            entry["success"] = True
            return entry

    def restore_window(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        """Restore or maximize the active window or target app."""
        entry = self._record("restore_window", app=app_name or "")
        if self.dry_run:
            entry["success"] = True
            entry["dry_run"] = True
            return entry
        sys_name = platform.system().lower()
        if sys_name == "windows":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
                    entry["success"] = True
                    return entry
            except Exception:
                pass
            self.press("win+up")
            entry["success"] = True
            return entry
        elif sys_name == "darwin":
            self.press("cmd+ctrl+f")
            entry["success"] = True
            return entry
        else:
            self.press("alt+f10")
            entry["success"] = True
            return entry



def os_path_home() -> str:
    from pathlib import Path

    return str(Path.home())


def _chrome_executable() -> Optional[str]:
    """Prefer a real chrome.exe so we can pass accessibility / debug flags."""
    which = (
        shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("chrome")
        or shutil.which("msedge")
    )
    if which:
        return which
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _browser_launch_command(url: Optional[str] = None) -> Optional[List[str]]:
    exe = _chrome_executable()
    if not exe:
        return None
    cmd = [exe, *_CHROME_A11Y_FLAGS]
    if url:
        cmd.append(url)
    return cmd
