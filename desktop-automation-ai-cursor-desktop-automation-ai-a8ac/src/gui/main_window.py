"""Main shell with sidebar navigation matching app flow wireframe."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QLineEdit,
    QMessageBox,
    QFrame,
    QApplication,
    QShortcut,
    QInputDialog,
    QTextEdit,
    QDialog,
    QDialogButtonBox,
)

from src.db.repositories import (
    ExecutionLogRepository,
    NLPCommandRepository,
    ScreenCaptureRepository,
    TaskRepository,
    UserConfRepository,
)
from src.diagnostics import probe_all
from src.gui.dai_listener import DaiMicThread, DaiSetupThread
from src.gui.dai_overlay import DaiOverlay
from src.gui.components.toast import ToastHost
from src.gui.pages.agent_page import AgentPage
from src.gui.pages.dashboard_page import DashboardPage
from src.gui.pages.diagnostics_page import DiagnosticsPage
from src.gui.pages.history_page import HistoryPage
from src.gui.pages.settings_page import SettingsPage
from src.gui.pages.voice_page import VoiceCommandPage
from src.gui.pages.workflows_page import WorkflowsPage
from src.gui.setup_wizard import SetupWizard
from src.gui.styles import get_app_style
from src.gui.window_fit import apply_standard_window_chrome, fit_to_screen
from src.gui.workflow_editor import WorkflowEditorDialog
from src.gui.workers import CommandWorker, SpeechWorker, WorkflowWorker
from src.agent.finalizer import SpeechFinalizer
from src.agent.interpreter import CommandInterpreter
from src.agent.logs import agent_log
from src.agent.normalize import normalize_command
from src.agent.safety_gate import must_confirm
from src.agent.sensitive import history_line_for_type, is_sensitive_request
from src.agent.session import PendingConfirm, TaskManager
from src.gui.highlight_overlay import HighlightOverlay
from src.nlp.clarify import clarify_heard
from src.speech.dai_chrome import DaiChromeThread, chrome_available, set_dai_chrome_minimized
from src.speech.wake import (
    agent_name,
    classify_utterance,
    clean_spoken_command,
    is_wake_phrase,
    is_wakeup_followup,
    is_wakeup_phrase,
    looks_like_wakeup_progress,
    set_agent_name,
    strip_wake,
    strip_wakeup,
)


class MainWindow(QMainWindow):
    def __init__(self, app_context: Dict[str, Any]) -> None:
        super().__init__()
        self.ctx = app_context
        self.config = app_context["config"]
        self.db = app_context["db"]
        self.pipeline = app_context["pipeline"]
        self.speech = app_context["speech"]
        self.workflows = app_context["workflows"]
        self.user: Dict[str, Any] = app_context["user"]
        self.conf_repo = UserConfRepository(self.db)
        self.log_repo = ExecutionLogRepository(self.db)
        self.nlp_repo = NLPCommandRepository(self.db)
        self.task_repo = TaskRepository(self.db)
        self.capture_repo = ScreenCaptureRepository(self.db)

        app_name = self.config.get("app", {}).get("name", "Automate AI")
        self.setWindowTitle(app_name)
        apply_standard_window_chrome(self)
        ui = self.config.get("ui", {})
        fit_to_screen(
            self,
            preferred_w=int(ui.get("window_width", 1080)),
            preferred_h=int(ui.get("window_height", 680)),
            min_w=int(ui.get("min_width", 860)),
            min_h=int(ui.get("min_height", 560)),
        )
        self.setStyleSheet(get_app_style(ui.get("theme", "light")))

        self._command_worker: Optional[CommandWorker] = None
        self._workflow_worker: Optional[WorkflowWorker] = None
        self._speech_worker: Optional[SpeechWorker] = None
        self._dai_thread = None
        self._dai_setup = None
        self._dai_overlay = None
        self._dai_active = False
        self._dai_primed = False
        self._dai_awaiting_confirm = False
        self._dai_queue: list = []
        self._live_desktop = False
        self._dai_last_cmd = ""
        self._dai_last_at = 0.0
        self._dai_engine = "google"
        self.tasks = TaskManager()
        self.interpreter = CommandInterpreter()
        self._speech_finalizer = SpeechFinalizer()
        self._highlight = HighlightOverlay()
        self._nav_buttons: Dict[str, QPushButton] = {}
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._refresh_all_now)
        self._current_page = "dashboard"

        self._build_ui()
        self._wire()
        self._load_settings()
        # Fast voice hotkey
        QShortcut(QKeySequence("Ctrl+Space"), self, activated=self._listen)
        QShortcut(QKeySequence("Ctrl+Shift+Esc"), self, activated=self._emergency_stop)
        self._show_page("dashboard")
        self.schedule_refresh(immediate=True)
        QTimer.singleShot(600, self._start_dai_listener)
        QTimer.singleShot(800, self._maybe_setup_wizard)
        self._dai_sleep_timer = QTimer(self)
        self._dai_sleep_timer.setSingleShot(True)
        self._dai_sleep_timer.timeout.connect(self._dai_idle_timeout)
        self._dai_prime_timer = QTimer(self)
        self._dai_prime_timer.setSingleShot(True)
        self._dai_prime_timer.timeout.connect(self._dai_clear_prime)
        self._dai_final_timer = QTimer(self)
        self._dai_final_timer.setSingleShot(True)
        self._dai_final_timer.timeout.connect(self._flush_dai_final)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar — wide enough for full nav labels
        side = QFrame()
        side.setObjectName("sideBar")
        side.setFixedWidth(228)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 18, 14, 16)
        sl.setSpacing(4)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        mark = QLabel("A")
        mark.setFixedSize(32, 32)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(
            "background:#4f46e5;color:#ffffff;border-radius:8px;"
            "font-weight:800;font-size:16px;"
        )
        brand_col = QVBoxLayout()
        brand = QLabel(self.config.get("app", {}).get("name", "Automate AI"))
        brand.setObjectName("sideBrand")
        brand.setWordWrap(True)
        tag = QLabel("Your desktop. Automated.")
        tag.setObjectName("pageSubtitle")
        tag.setWordWrap(True)
        brand_col.addWidget(brand)
        brand_col.addWidget(tag)
        brand_row.addWidget(mark, 0, Qt.AlignTop)
        brand_row.addLayout(brand_col, 1)
        sl.addLayout(brand_row)
        sl.addSpacing(16)

        for key, label in (
            ("dashboard", "Dashboard"),
            ("agent", "AI Agent"),
            ("voice", "Voice Command"),
            ("history", "Execution History"),
            ("workflows", "Workflows"),
            ("diagnostics", "Diagnostics"),
            ("settings", "Settings"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("btnNav")
            btn.setMinimumHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._show_page(k))
            self._nav_buttons[key] = btn
            sl.addWidget(btn)

        sl.addStretch()
        ready = QLabel("● SYSTEM_READY")
        ready.setObjectName("statusChip")
        ready.setAlignment(Qt.AlignCenter)
        sl.addWidget(ready)
        sl.addSpacing(8)
        signout = QPushButton("Sign Out")
        signout.setObjectName("btnSecondary")
        signout.setMinimumHeight(36)
        signout.clicked.connect(self.close)
        sl.addWidget(signout)

        # Main column
        main = QVBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        top = QFrame()
        top.setObjectName("topBar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(20, 12, 20, 12)
        tl.setSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search commands or logs…")
        self.search.setMinimumHeight(36)
        self.search.returnPressed.connect(self._search)
        user_lbl = QLabel(self.user.get("username", "user"))
        user_lbl.setStyleSheet(
            "background:#eef2f7;color:#0f172a;border-radius:16px;"
            "padding:8px 14px;font-weight:600;"
        )
        stop = QPushButton("STOP")
        stop.setObjectName("btnDanger")
        stop.setMinimumHeight(36)
        stop.setToolTip("Emergency stop (Ctrl+Shift+Esc)")
        stop.clicked.connect(self._emergency_stop)
        tl.addWidget(self.search, 1)
        tl.addWidget(stop)
        tl.addWidget(user_lbl)

        self.stack = QStackedWidget()
        self.page_dashboard = DashboardPage()
        self.page_agent = AgentPage()
        self.page_voice = VoiceCommandPage()
        self.page_history = HistoryPage()
        self.page_workflows = WorkflowsPage()
        self.page_diagnostics = DiagnosticsPage()
        self.page_settings = SettingsPage()
        self.stack.addWidget(self.page_dashboard)
        self.stack.addWidget(self.page_agent)
        self.stack.addWidget(self.page_voice)
        self.stack.addWidget(self.page_history)
        self.stack.addWidget(self.page_workflows)
        self.stack.addWidget(self.page_diagnostics)
        self.stack.addWidget(self.page_settings)

        main.addWidget(top)
        main.addWidget(self.stack, 1)

        root.addWidget(side)
        root.addLayout(main, 1)
        self.toast = ToastHost(self)

    def _wire(self) -> None:
        self.page_dashboard.open_voice.connect(lambda: self._show_page("voice"))
        self.page_dashboard.open_agent.connect(lambda: self._show_page("agent"))
        self.page_dashboard.open_history.connect(lambda: self._show_page("history"))
        self.page_dashboard.open_workflows.connect(lambda: self._show_page("workflows"))
        self.page_dashboard.run_diagnostics.connect(lambda: self._show_page("diagnostics"))

        self.page_agent.execute_requested.connect(self._run_command)
        self.page_agent.plan_requested.connect(self._preview_plan)
        self.page_agent.mic_requested.connect(self._listen)
        self.page_agent.stop_requested.connect(self._emergency_stop)
        self.page_agent.suggestion_requested.connect(self.page_agent.set_command_text)
        self.page_agent.clarify_chosen.connect(self._on_dai_confirm)

        self.page_voice.execute_requested.connect(self._run_command)
        self.page_voice.mic_requested.connect(self._listen)
        self.page_voice.rerun_requested.connect(self._run_command)
        self.page_voice.sensitivity_changed.connect(self._set_sensitivity)
        self.page_voice.stop_requested.connect(self._stop_workers)

        self.page_workflows.run_requested.connect(self._run_workflow)
        self.page_workflows.create_requested.connect(self._create_workflow)
        self.page_workflows.delete_requested.connect(self._delete_workflow)
        self.page_workflows.edit_requested.connect(self._edit_workflow)
        self.page_workflows.refresh_requested.connect(self.refresh_all)
        self.page_workflows.record_start_requested.connect(self._start_workflow_recording)
        self.page_workflows.record_stop_save_requested.connect(self._stop_workflow_recording)

        self.page_settings.save_requested.connect(self._save_settings)
        self.page_voice.show_dai_requested.connect(self._start_dai_listener)

        self.page_diagnostics.refresh_requested.connect(self._refresh_diagnostics)
        self.page_diagnostics.test_capture_requested.connect(self._test_capture)
        self.page_diagnostics.test_ocr_requested.connect(self._test_ocr)
        self.page_diagnostics.test_mouse_requested.connect(self._test_mouse)
        self.page_diagnostics.test_keyboard_requested.connect(self._test_keyboard)
        self.page_diagnostics.test_mic_requested.connect(self._test_mic)

    def _show_page(self, key: str) -> None:
        mapping = {
            "dashboard": 0,
            "agent": 1,
            "voice": 2,
            "history": 3,
            "workflows": 4,
            "diagnostics": 5,
            "settings": 6,
        }
        self._current_page = key
        self.stack.setCurrentIndex(mapping.get(key, 0))
        for k, btn in self._nav_buttons.items():
            btn.setProperty("active", "true" if k == key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if key == "voice":
            # Pre-open mic path so first listen feels instant
            QTimer.singleShot(0, self.speech.warm_up)
        # Light refresh only for the visible page (keeps UI smooth)
        self.schedule_refresh()

    def _load_settings(self) -> None:
        conf = self.conf_repo.get_map(self.user["user_id"])
        # Merge optional cloud keys from config file defaults
        speech_cfg = self.config.get("speech", {})
        if not conf.get("openai_api_key") and speech_cfg.get("openai_api_key"):
            conf = {**conf, "openai_api_key": speech_cfg.get("openai_api_key")}
        if not conf.get("gemini_api_key") and speech_cfg.get("gemini_api_key"):
            conf = {**conf, "gemini_api_key": speech_cfg.get("gemini_api_key")}
        self.page_settings.apply_conf(conf)
        self.pipeline.apply_user_settings(self.user["user_id"])
        sens = float(conf.get("voice_sensitivity", conf.get("mic_sensitivity", 0.9)))
        self.page_voice.sensitivity.blockSignals(True)
        self.page_voice.sensitivity.setValue(int(sens * 100))
        self.page_voice.sensitivity.blockSignals(False)
        self.speech.set_sensitivity(sens)
        cloud_on = str(conf.get("cloud_ai", "0")) in ("1", "true", "True")
        self.speech.set_api_keys(
            openai_key=str(conf.get("openai_api_key") or speech_cfg.get("openai_api_key") or "") if cloud_on else "",
            gemini_key=str(conf.get("gemini_api_key") or speech_cfg.get("gemini_api_key") or "") if cloud_on else "",
        )
        self._apply_theme(str(conf.get("theme") or self.config.get("ui", {}).get("theme", "light")))
        self._apply_agent_name(str(conf.get("agent_name") or self.config.get("speech", {}).get("wake_word") or "AI"))

    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        style = get_app_style(theme)
        if app is not None:
            app.setStyleSheet(style)
        self.setStyleSheet(style)
        self.conf_repo.set(self.user["user_id"], "theme", theme)

    def _apply_agent_name(self, name: str) -> None:
        before = agent_name()
        chosen = set_agent_name(name)
        self.conf_repo.set(self.user["user_id"], "agent_name", chosen)
        if (
            before.lower() != chosen.lower()
            and self._dai_thread is not None
            and getattr(self, "_dai_engine", "") == "offline"
        ):
            QTimer.singleShot(250, self._restart_dai_listener)
        if self._dai_overlay is not None:
            self._dai_overlay.set_brand(chosen)
        wake = f"{chosen} wakeup"
        self.page_voice.set_engine_label(f"Engine: {chosen} Google mic — say {wake}")
        self.page_agent.set_status(f"Ready — type a goal, or say {wake}")
        if self._dai_overlay is not None and not self._dai_active:
            self._dai_overlay.set_mode("sleep", f"Sleeping — say “{wake}”")

    def _wake_prompt(self) -> str:
        return f"“{agent_name()}”"

    def _save_settings(self, values: dict) -> None:
        self.conf_repo.update_many(self.user["user_id"], values)
        self.pipeline.apply_user_settings(self.user["user_id"])
        self.speech.set_sensitivity(float(values.get("mic_sensitivity", 0.9)))
        if str(values.get("cloud_ai", "0")) in ("1", "true", "True"):
            self.speech.set_api_keys(
                openai_key=str(values.get("openai_api_key") or ""),
                gemini_key=str(values.get("gemini_api_key") or ""),
            )
        else:
            self.speech.set_api_keys(openai_key="", gemini_key="")
        if values.get("theme"):
            self._apply_theme(str(values["theme"]))
        if values.get("agent_name") is not None:
            self._apply_agent_name(str(values.get("agent_name") or "AI"))
        QMessageBox.information(
            self,
            "Settings",
            f"Settings applied.\nSay “{agent_name()}” or “{agent_name()}, open Chrome” to start listening.",
        )
        self.toast.show("Settings saved", "success")
        self._show_page("dashboard")

    def _set_sensitivity(self, value: float) -> None:
        self.conf_repo.set(self.user["user_id"], "voice_sensitivity", f"{value:.2f}")
        self.conf_repo.set(self.user["user_id"], "mic_sensitivity", f"{value:.2f}")
        self.speech.set_sensitivity(value)

    def schedule_refresh(self, immediate: bool = False) -> None:
        if immediate:
            self._refresh_timer.stop()
            self._refresh_all_now()
        else:
            self._refresh_timer.start(60)

    def refresh_all(self) -> None:
        self.schedule_refresh(immediate=True)

    def _refresh_all_now(self) -> None:
        uid = self.user["user_id"]
        conf = self.conf_repo.get_map(uid)
        dry = str(conf.get("dry_run", "0")) in ("1", "true", "True")
        page = self._current_page

        if page in ("dashboard", "history", "workflows", "voice", "agent"):
            logs = self.log_repo.recent(user_id=uid, limit=30)
        else:
            logs = []

        if page == "dashboard":
            stats = self.log_repo.stats(uid)
            self.page_dashboard.update_stats(stats, dry_run=dry)
            self.page_dashboard.update_activity(logs)
        elif page == "agent":
            pass
        elif page == "history":
            captures_by_log = {}
            for log in logs:
                lid = log.get("log_id")
                if lid:
                    captures_by_log[int(lid)] = self.capture_repo.list_for_log(int(lid))
            self.page_history.update_logs(logs, captures_by_log)
        elif page == "voice":
            commands = self.nlp_repo.recent(user_id=uid, limit=12)
            status_map = {}
            for log in logs:
                cid = log.get("command_id")
                if cid:
                    status_map[cid] = log.get("status", "")
            self.page_voice.update_recent(commands, status_map)
        elif page == "workflows":
            stats = self.log_repo.stats(uid)
            wfs = self.workflows.list_workflows(uid)
            avg = self.task_repo.average_steps(uid)
            self.page_workflows.set_workflows(
                wfs, today_executions=stats.get("today", 0), avg_steps=avg
            )
            live = [
                f"{l.get('started_at', '')} · {l.get('status')} · {l.get('action_id') or 'command'}"
                for l in logs[:5]
            ]
            self.page_workflows.set_live_logs(live)
        elif page == "diagnostics":
            self._refresh_diagnostics()
        QApplication.processEvents()

    def _search(self) -> None:
        q = self.search.text().strip()
        if q:
            self._show_page("agent")
            self.page_agent.set_command_text(q)
            self._preview_plan(q)

    def _busy(self) -> bool:
        for worker in (self._command_worker, self._workflow_worker, self._speech_worker):
            if worker is not None and worker.isRunning():
                return True
        return False

    def _needs_desktop_focus(self, text: str) -> bool:
        """URL/app launches don't need minimizing; clicks/typing do."""
        t = text.lower()
        if any(k in t for k in ("click", "type", "write", "press", "scroll", "fill")):
            return True
        return False

    def _run_command(self, text: str, *, source: str = "text", live_desktop: bool = False) -> None:
        if not text.strip():
            return
        spoken = clean_spoken_command(text)
        kind, payload = classify_utterance(spoken, session_active=True)
        if kind == "minimize":
            if self._dai_overlay:
                self._dai_overlay.show()
                self._dai_overlay.set_mode("active", "Minimized — still listening")
            self.showMinimized()
            QApplication.processEvents()
            self.page_voice.set_status_message(f"✓ Minimized ({agent_name()} still listening)")
            return
        if kind == "restore":
            self.showNormal()
            self.raise_()
            self.activateWindow()
            if self._dai_overlay:
                self._dai_overlay.show()
                self._dai_overlay.set_mode("active", "Window restored")
            return
        if kind == "repeat":
            if not self._dai_last_cmd:
                if self._dai_overlay:
                    self._dai_overlay.set_mode("active", "Nothing to repeat")
                return
            text = self._dai_last_cmd
        elif kind in ("command", "wake") and payload:
            text = payload
        else:
            text = spoken or text

        if self._busy():
            if live_desktop:
                self._dai_queue.append(text)
                if self._dai_overlay:
                    self._dai_overlay.set_mode("busy", f"Queued: {text}")
            return
        self._live_desktop = live_desktop
        self._dai_last_cmd = text
        if not live_desktop and self._current_page not in ("voice", "agent"):
            self._show_page("agent")
        self.page_voice.set_command_text(text)
        self.page_agent.set_command_text(text)
        try:
            plan = self.pipeline.preview_plan(text, source=source)
            self.page_agent.show_plan(plan.to_dict())
        except Exception:
            pass
        mode = "LIVE" if not self.pipeline.automation.dry_run else "dry-run"
        self.page_voice.set_busy(True)
        self.page_voice.set_status_message(f"STT: {text}  ·  Running ({mode})…")
        self.page_agent.set_status(f"STT: {text}  ·  Running ({mode})…")
        if self._dai_overlay and live_desktop:
            self._dai_overlay.set_mode("busy", f"STT → {text}")
        # Hide chrome so live clicks land on the real desktop
        if not self.pipeline.automation.dry_run and (
            live_desktop or self._needs_desktop_focus(text)
        ):
            if self._dai_overlay:
                self._dai_overlay.hide_for_action()
            set_dai_chrome_minimized(True)
            self.showMinimized()
            QApplication.processEvents()
        if not self.pipeline.automation.recording:
            self.pipeline.automation.clear_history()
        self._command_worker = CommandWorker(
            self.pipeline, text, self.user["user_id"], source=source, parent=self
        )
        self._command_worker.status.connect(self._on_live_status)
        self._command_worker.status.connect(self.page_agent.mark_status)
        self._command_worker.failed.connect(lambda m: self.page_voice.set_status_message(f"✗ {m}"))
        self._command_worker.finished_ok.connect(self._on_command_done)
        self._command_worker.start()

    def _on_command_done(self, result: dict) -> None:
        self.page_voice.set_busy(False)
        live = self._live_desktop
        self._live_desktop = False
        if self._dai_overlay:
            self._dai_overlay.show_after_action()
        set_dai_chrome_minimized(False)
        if self.isMinimized() and not live:
            self.showNormal()
            self.raise_()
            self.activateWindow()
        if result.get("ok"):
            mode = "dry-run" if result.get("dry_run") else "live"
            self.page_voice.set_status_message(f"✓ Completed successfully ({mode})")
            self.toast.show("✓ Workflow / command completed successfully", "success")
            if self._dai_overlay and self._dai_active and not live:
                self._dai_overlay.set_mode("active", "Listening — next command")
        else:
            err = result.get("error") or "Failed"
            self.page_voice.set_status_message(f"✗ {err}")
            kind = "safety" if "Safety limit" in err or "emergency" in err.lower() else "error"
            self.toast.show(err.split("\n")[0][:160], kind)
            if result.get("suggestions"):
                self.page_agent.show_plan(result.get("plan") or {})
            if self._dai_overlay:
                self._dai_overlay.set_mode(
                    "active" if self._dai_active else "sleep",
                    err.split("\n")[0][:80],
                )
        if result.get("plan"):
            self.page_agent.show_plan(result["plan"])
        self.page_agent.show_vision(
            self.pipeline.last_frame,
            boxes=result.get("boxes") or self.pipeline.last_boxes,
            path=getattr(self.pipeline, "last_capture_path", "") or "",
        )
        if self.pipeline.automation.recording:
            n = len(self.pipeline.automation.session_history)
            self.page_workflows.set_recording(True, step_count=n)
        self.schedule_refresh()
        if live and self._dai_queue:
            nxt = self._dai_queue.pop(0)
            QTimer.singleShot(80, lambda: self._run_command(nxt, source="voice", live_desktop=True))
            return
        if live and result.get("needs_secret"):
            self._prompt_secret_and_type()
            return
        if live and result.get("needs_confirm"):
            self._show_element_confirm(result)
            return
        if live:
            ok = bool(result.get("ok"))
            spoken = self._dai_last_cmd
            safe = history_line_for_type(sensitive=is_sensitive_request(spoken)) if is_sensitive_request(spoken) else (
                f"{'Completed' if ok else 'Failed'}: {spoken}"
            )
            self.tasks.ensure()
            self.tasks.record(safe, ok=ok)
            self._remember_screen(result)
            self.tasks.waiting_for_next()
            self.page_agent.set_task_history(self.tasks.session.history_lines() if self.tasks.session else [])
            if result.get("dry_run"):
                msg = "Dry-run only — turn off Dry-run in Settings. What's next?"
            elif ok:
                msg = "Done. What's next?"
            else:
                msg = (result.get("error") or "That didn't work.")[:80] + " What's next?"
            if self._dai_overlay:
                self._dai_overlay.set_mode("active", msg)
            self._arm_dai_idle()
            agent_log(f"Verification: {'SUCCESS' if ok else 'FAIL'}")

    def _stop_workers(self) -> None:
        self.pipeline.request_stop("Stopped by user")
        for worker in (self._command_worker, self._workflow_worker):
            if worker is not None and worker.isRunning() and hasattr(worker, "stop"):
                worker.stop()
        self.page_voice.set_status_message("● Stop requested…")
        self.page_voice.set_busy(False)
        self.page_agent.set_status("● Stop requested…")

    def _listen(self) -> None:
        if self._busy():
            return
        self._show_page("voice")
        self.page_voice.set_listening(True)
        self.page_voice.set_status_message("● Starting voice…")
        self._speech_worker = SpeechWorker(self.speech, parent=self)
        self._speech_worker.status.connect(self.page_voice.set_status_message)
        self._speech_worker.failed.connect(self._on_speech_fail)
        self._speech_worker.transcribed.connect(self._on_transcribed)
        self._speech_worker.start()

    def _on_speech_fail(self, message: str) -> None:
        self.page_voice.set_listening(False)
        self.page_voice.set_status_message(f"✗ {message}")
        self.page_voice.focus_command()
        if self.statusBar():
            self.statusBar().showMessage(message, 5000)

    def _on_transcribed(self, text: str) -> None:
        self.page_voice.set_listening(False)
        self.page_voice.set_command_text(text)
        self.page_agent.set_command_text(text)
        backend = getattr(self.speech, "last_backend", "") or "voice"
        self.page_voice.set_status_message(f"Heard ({backend}): {text}")
        self.page_agent.set_status(f"Heard ({backend}): {text}")
        self._run_command(text, source="voice")

    def _run_workflow(self, workflow_id: int) -> None:
        if self._busy():
            return
        self._workflow_worker = WorkflowWorker(
            self.pipeline, workflow_id, self.user["user_id"], parent=self
        )
        self._workflow_worker.failed.connect(self._on_workflow_fail)
        self._workflow_worker.finished_ok.connect(self._on_workflow_done)
        if not self.pipeline.automation.dry_run:
            self.showMinimized()
            QApplication.processEvents()
        self._workflow_worker.start()

    def _on_workflow_fail(self, message: str) -> None:
        if self.isMinimized():
            self.showNormal()
        QMessageBox.warning(self, "Workflow", message)

    def _on_workflow_done(self, _result: dict) -> None:
        if self.isMinimized():
            self.showNormal()
            self.raise_()
        self.schedule_refresh()

    def _start_workflow_recording(self) -> None:
        self.pipeline.automation.start_recording()
        self.page_workflows.set_recording(True, step_count=0)
        self._show_page("voice")
        self.page_voice.set_status_message(
            "● Recording workflow — speak or type each step, then Save as workflow"
        )
        QMessageBox.information(
            self,
            "Recording",
            "Recording started.\n\n"
            "1. Go to Voice Command (already opened)\n"
            "2. Speak or type each step (open apps, copy files, click…)\n"
            "3. Open Workflows → Save as workflow and give it a name\n\n"
            "Later say: Run <your workflow name>",
        )

    def _stop_workflow_recording(self) -> None:
        steps = self.pipeline.automation.stop_recording()
        self.page_workflows.set_recording(False, step_count=len(steps))
        if steps:
            QMessageBox.information(
                self,
                "Recording stopped",
                f"Captured {len(steps)} actions.\nClick Save as workflow to name and keep them.",
            )
        else:
            # Resume empty session cleared — user can still save last history
            self.page_workflows.set_recording(False, step_count=0)

    def _create_workflow(self, name: str, description: str) -> None:
        # Prefer full recording session; fall back to last command history
        history = self.pipeline.automation.session_history or self.pipeline.automation.history
        if self.pipeline.automation.recording:
            history = self.pipeline.automation.session_history
            self.pipeline.automation.stop_recording()
            self.page_workflows.set_recording(False, step_count=len(history))

        tasks = self.workflows.tasks_from_action_history(history)
        if not tasks:
            QMessageBox.warning(
                self,
                "No steps to save",
                "Do some actions first (Record steps, then speak/type commands), "
                "then Save as workflow.\n\n"
                "Example: Open Chrome → Search weather → Copy file report to Desktop",
            )
            return
        try:
            self.workflows.create_workflow(
                self.user["user_id"],
                name,
                description,
                tasks=tasks,
                trigger_type="voice",
            )
            self.pipeline.automation.clear_session()
            self.pipeline.automation.clear_history()
            QMessageBox.information(
                self,
                "Workflow saved",
                f"Saved “{name}” with {len(tasks)} steps.\n\n"
                f"Say: Run {name}",
            )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Create failed", str(exc))

    def _delete_workflow(self, workflow_id: int) -> None:
        if QMessageBox.question(self, "Delete", "Delete this workflow?") != QMessageBox.Yes:
            return
        self.workflows.delete_workflow(workflow_id)
        self.refresh_all()

    def _edit_workflow(self, workflow_id: int) -> None:
        wf = self.workflows.get_workflow(workflow_id)
        if not wf:
            QMessageBox.warning(self, "Edit", "Workflow not found.")
            return
        dlg = WorkflowEditorDialog(wf, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        payload = dlg.result_payload()
        if payload.get("name"):
            self.workflows.rename_workflow(workflow_id, payload["name"])
        if payload.get("tasks"):
            self.workflows.save_tasks(workflow_id, payload["tasks"])
        self.toast.show("Workflow updated", "success")
        self.refresh_all()

    def _preview_plan(self, text: str) -> None:
        if not text.strip():
            return
        try:
            plan = self.pipeline.preview_plan(text)
            self.page_agent.show_plan(plan.to_dict())
            self.page_agent.set_status("Plan ready — click Execute when it looks right.")
            if plan.needs_clarification:
                self.toast.show("Low confidence — check suggestions", "warning")
        except Exception as exc:
            self.toast.show(str(exc), "error")

    def _emergency_stop(self) -> None:
        self.pipeline.request_stop("User requested emergency stop.")
        self._stop_workers()
        self.tasks.cancel("Emergency stop")
        self.showNormal()
        set_dai_chrome_minimized(False)
        self.toast.show("🛑 AUTOMATION STOPPED", "safety")
        self.page_agent.set_status("🛑 Emergency stop — remaining actions cancelled.")
        if self._dai_overlay:
            self._dai_overlay.show()
            self._dai_overlay.set_mode("active" if self._dai_active else "sleep", "Stopped. What's next?")

    def _maybe_setup_wizard(self) -> None:
        conf = self.conf_repo.get_map(self.user["user_id"])
        if str(conf.get("setup_complete", "0")) in ("1", "true", "True"):
            return
        dlg = SetupWizard(self.config, self)
        dlg.exec_()
        self.conf_repo.set(self.user["user_id"], "setup_complete", "1")

    def _refresh_diagnostics(self) -> None:
        self.page_diagnostics.set_results(probe_all(self.config))

    def _test_capture(self) -> None:
        result = self.pipeline.capture_preview()
        ok = result.get("ok")
        self.page_diagnostics.set_test_output(
            "Screen capture OK" if ok else f"Capture issue: {self.pipeline.vision.last_capture_error}"
        )
        self.page_agent.show_vision(result.get("frame"), path=result.get("path") or "")
        self.toast.show("Screen capture tested", "success" if ok else "error")

    def _test_ocr(self) -> None:
        frame = self.pipeline.vision.capture_screen()
        preview = self.pipeline.vision.ocr_preview(frame)
        self.page_agent.show_vision(frame, boxes=preview.boxes)
        self.page_diagnostics.set_test_output(f"OCR boxes: {len(preview.boxes or [])}")
        self.toast.show("OCR test finished", "info")

    def _test_mouse(self) -> None:
        if self.pipeline.automation.dry_run:
            self.page_diagnostics.set_test_output("Dry-run on — mouse not moved.")
            return
        ready = self.pipeline.automation.mouse_ready
        self.page_diagnostics.set_test_output(
            "PyAutoGUI ready" if ready else "PyAutoGUI unavailable"
        )

    def _test_keyboard(self) -> None:
        self.page_diagnostics.set_test_output(
            "Keyboard path uses PyAutoGUI type_text (enable live mode to send keys)."
        )

    def _test_mic(self) -> None:
        self.speech.warm_up()
        self.page_diagnostics.set_test_output(
            f"Microphone warm-up requested. Say {self._wake_prompt()} or use Speak."
        )
        self.toast.show("Mic warm-up started", "info")

    def shutdown(self) -> None:
        self._stop_dai_listener()
        for worker in (self._command_worker, self._workflow_worker, self._speech_worker):
            if worker is not None and worker.isRunning():
                if hasattr(worker, "stop"):
                    worker.stop()
                worker.wait(1200)

    def _ensure_dai_overlay(self) -> None:
        if self._dai_overlay is not None:
            return
        self._dai_overlay = DaiOverlay()
        self._dai_overlay.close_requested.connect(self._hide_dai_overlay)
        self._dai_overlay.retry_requested.connect(self._restart_dai_listener)
        self._dai_overlay.tap_requested.connect(self._dai_tap_wake)
        self._dai_overlay.confirm_requested.connect(self._on_dai_confirm)
        self._dai_overlay.stop_requested.connect(self._emergency_stop)
        self._dai_overlay.yes_requested.connect(self._on_element_yes)
        self._dai_overlay.no_requested.connect(self._on_element_no)
        self._dai_overlay.place_corner()
        self._dai_overlay.set_brand(agent_name())

    def _start_dai_listener(self) -> None:
        if self._dai_thread is not None and self._dai_thread.isRunning():
            if self._dai_overlay:
                self._dai_overlay.show()
                self._dai_overlay.raise_()
            return
        self._dai_thread = None
        self._ensure_dai_overlay()
        self._dai_overlay.show()
        self._put_dai_to_sleep("Starting Google mic…")
        if chrome_available():
            self._start_dai_chrome()
            return
        self._start_dai_vosk_fallback("Chrome/Edge not found — using offline mic")

    def _restart_dai_listener(self) -> None:
        self._stop_dai_listener(keep_overlay=True)
        QTimer.singleShot(200, self._start_dai_listener)

    def _start_dai_chrome(self) -> None:
        self._dai_engine = "google"
        thread = DaiChromeThread(parent=self)
        thread.heard_final.connect(self._on_dai_final)
        thread.heard_partial.connect(self._on_dai_partial)
        thread.engine_ready.connect(self._on_dai_chrome_ready)
        thread.failed.connect(self._on_dai_chrome_fail)
        thread.status.connect(
            lambda m: self._dai_overlay.set_mode(
                "active" if self._dai_active else "sleep", m
            )
            if self._dai_overlay and not self._dai_awaiting_confirm
            else None
        )
        self._dai_thread = thread
        thread.start()
        if self._dai_overlay:
            self._dai_overlay.set_mode("sleep", "Opening Chrome Google mic…")

    def _on_dai_chrome_ready(self) -> None:
        self._dai_engine = "google"
        self._put_dai_to_sleep(f"Sleeping — say {self._wake_prompt()}")
        self.page_voice.set_engine_label(
            f"Engine: {agent_name()} Google mic — say {self._wake_prompt()}, then keep speaking steps"
        )
        self.toast.show(
            f"{agent_name()} is sleeping. Say {self._wake_prompt()} when you need it.",
            "info",
        )

    def _on_dai_chrome_fail(self, message: str) -> None:
        if self._dai_thread is not None:
            try:
                self._dai_thread.stop()
                self._dai_thread.wait(800)
            except Exception:
                pass
            self._dai_thread = None
        self._start_dai_vosk_fallback(message)

    def _start_dai_vosk_fallback(self, reason: str = "") -> None:
        self._dai_engine = "offline"
        self._ensure_dai_overlay()
        detail = "Google mic failed — starting offline…"
        if reason:
            detail = reason[:90]
        if self._dai_overlay:
            self._dai_overlay.set_mode("sleep", detail)
        self.page_voice.set_status_message(f"DAI: {detail}")
        self._dai_setup = DaiSetupThread(self.config, parent=self)
        self._dai_setup.status.connect(
            lambda m: self._dai_overlay.set_mode("sleep", m) if self._dai_overlay else None
        )
        self._dai_setup.failed.connect(self._on_dai_setup_fail)
        self._dai_setup.ready.connect(self._on_dai_model_ready)
        self._dai_setup.start()

    def _on_dai_setup_fail(self, message: str) -> None:
        if self._dai_overlay:
            self._dai_overlay.set_mode("error", message)
        self.page_voice.set_status_message(f"DAI overlay: {message}")

    def _on_dai_model_ready(self, model_path: str) -> None:
        self._dai_engine = "offline"
        thread = DaiMicThread(model_path, parent=self)
        thread.heard.connect(self._on_dai_heard)
        if hasattr(thread, "heard_alts"):
            thread.heard.disconnect(self._on_dai_heard)
            thread.heard_alts.connect(self._on_dai_final)
        thread.partial.connect(self._on_dai_partial)
        thread.status.connect(
            lambda m: self._dai_overlay.set_mode(
                "active" if self._dai_active else "sleep", m
            )
            if self._dai_overlay and not self._dai_awaiting_confirm
            else None
        )
        thread.failed.connect(self._on_dai_setup_fail)
        self._dai_thread = thread
        thread.start()
        self._put_dai_to_sleep(f"Offline mic. Sleeping — say {self._wake_prompt()}")
        self.page_voice.set_engine_label(
            f"Engine: Offline {agent_name()} fallback — say {self._wake_prompt()} (install Chrome for better listen)"
        )

    def _on_dai_partial(self, text: str) -> None:
        if not self._dai_overlay or not text or self._dai_awaiting_confirm:
            return
        if self._dai_active:
            self._dai_overlay.set_mode("active", f"STT: {text}")
            return
        if looks_like_wakeup_progress(text):
            self._dai_overlay.set_mode("sleep", f"Hearing: {text}")

    def _on_dai_heard(self, text: str) -> None:
        self._on_dai_final(text, [])

    def _on_dai_final(self, text: str, alternatives: list | None = None) -> None:
        raw = " ".join((text or "").split())
        if not raw:
            return
        released = self._speech_finalizer.feed_final(raw, list(alternatives or []))
        if released:
            self._dispatch_dai_final(released[0], released[1])
            return
        if self._dai_overlay and self._speech_finalizer.pending():
            self._dai_overlay.set_mode(
                "active" if self._dai_active else "sleep",
                f"Hearing: {self._speech_finalizer.held}",
            )
        self._dai_final_timer.start(self._speech_finalizer.remaining_ms())

    def _flush_dai_final(self) -> None:
        released = self._speech_finalizer.take_due()
        if released:
            self._dispatch_dai_final(released[0], released[1])
        elif self._speech_finalizer.pending():
            self._dai_final_timer.start(self._speech_finalizer.remaining_ms())

    def _dispatch_dai_final(self, text: str, alternatives: list | None = None) -> None:
        now = time.monotonic()
        raw = " ".join((text or "").split())
        if not raw:
            return
        alts = list(alternatives or [])
        if self._dai_overlay:
            self._dai_overlay.hint.setText(f"Heard: {raw}")
        key = normalize_command(raw).lower()
        if self._dai_active and key in (
            "stop",
            "dai stop",
            "ai stop",
            "stop now",
            "dai stop now",
            "ai stop now",
            "cancel",
            "cancel task",
            "emergency stop",
        ):
            self._emergency_stop()
            return

        if not self._dai_active:
            if is_wakeup_phrase(raw) or (
                self._dai_primed and is_wakeup_followup(raw)
            ):
                leftover = strip_wakeup(raw) if is_wakeup_phrase(raw) else ""
                self._wake_dai()
                if leftover:
                    self._handle_dai_command(leftover, alts)
                return
            if is_wake_phrase(raw):
                leftover = strip_wake(raw)
                self._wake_dai()
                if leftover:
                    self._handle_dai_command(leftover, alts)
                else:
                    self._arm_dai_idle()
                    if self._dai_overlay:
                        self._dai_overlay.set_mode("active", "I'm listening… speak a command")
                return
            return

        kind, command = classify_utterance(raw, session_active=True)
        if kind == "ignore":
            return
        if command and command == self._dai_last_cmd and (now - self._dai_last_at) < 1.1:
            return
        self._dai_last_at = now
        if kind == "close":
            self._put_dai_to_sleep(f"Sleeping — say {self._wake_prompt()}")
            self.page_voice.set_status_message(f"{agent_name()} went to sleep")
            return
        if kind == "minimize":
            self.showMinimized()
            if self._dai_overlay:
                self._dai_overlay.show()
                self._dai_overlay.set_mode("active", "Minimized. What's next?")
            self._arm_dai_idle()
            return
        if kind == "restore":
            self.showNormal()
            self.raise_()
            if self._dai_overlay:
                self._dai_overlay.set_mode("active", "Restored. What's next?")
            self._arm_dai_idle()
            return
        if kind == "repeat":
            if self._dai_last_cmd:
                self._run_command(self._dai_last_cmd, source="voice", live_desktop=True)
            return
        if kind == "wake":
            if command:
                self._handle_dai_command(command, alts)
            else:
                self._arm_dai_idle()
                if self._dai_overlay:
                    self._dai_overlay.set_mode("active", "Awake — speak a command")
            return
        if kind == "command" and command:
            self._handle_dai_command(command, alts)

    def _on_live_status(self, message: str) -> None:
        if (message or "").startswith("◆highlight "):
            parts = message.split()
            try:
                self._highlight.show_box(int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]))
            except (TypeError, ValueError, IndexError):
                pass
            return
        self.page_voice.set_status_message(message)
        if self._dai_overlay and self._dai_active and "Analyzing" in (message or ""):
            self._dai_overlay.set_mode("analyze", message[:80])

    def _handle_dai_command(self, text: str, alternatives: list | None = None) -> None:
        spoken = clean_spoken_command(normalize_command(text))
        if not spoken:
            return
        agent_log(f'Voice: "{spoken}"')
        interp = self.interpreter.interpret(spoken, is_final=True, tasks=self.tasks)
        if interp.stop:
            self._emergency_stop()
            return
        if interp.end_task:
            self.tasks.complete("Task completed.")
            self.page_agent.set_task_history(self.tasks.session.history_lines() if self.tasks.session else [])
            self._put_dai_to_sleep(f"Task completed. Say {self._wake_prompt()}")
            return
        if self.tasks.session and self.tasks.session.pending:
            low = spoken.lower()
            if low in ("yes", "yeah", "yep", "do it", "click it"):
                self._on_element_yes()
                return
            if low in ("no", "nope", "wrong", "try again"):
                self._on_element_no()
                return
            if "second" in low or "other" in low:
                cands = self.tasks.session.pending.candidates
                if len(cands) >= 2:
                    self._click_candidate(cands[1])
                    return
        if interp.start_task and all(a.type in ("START_TASK",) for a in interp.actions):
            self.tasks.start(spoken)
            if self._dai_overlay:
                self._dai_overlay.set_mode("active", "Okay. Tell me what to do first.")
            self.page_agent.set_task_history(self.tasks.session.history_lines())
            self._arm_dai_idle()
            return
        if interp.reference and interp.actions:
            tgt = interp.actions[0].target or {}
            if tgt.get("x") is not None:
                self._click_candidate(tgt)
                return
        risky, prompt = must_confirm(spoken)
        if risky:
            self.tasks.ensure()
            self.tasks.set_pending(
                PendingConfirm(kind="safety", prompt=prompt, spoken=spoken, action={"text": spoken})
            )
            if self._dai_overlay:
                self._dai_overlay.show_element_confirm(prompt, ["Yes, proceed", "No"])
            self._dai_awaiting_confirm = True
            return
        result = clarify_heard(spoken, alternatives or [])
        if result.needed and result.suggestions and not interp.actions:
            self._dai_awaiting_confirm = True
            self._dai_sleep_timer.start(20000)
            if self._dai_overlay:
                self._dai_overlay.show_clarify(result.heard, result.suggestions)
            self.page_agent.show_clarify(result.heard, result.suggestions)
            return
        self.tasks.ensure(spoken)
        self.tasks.set_status("EXECUTING")
        agent_log(f"Intent: {(interp.actions[0].type if interp.actions else 'COMMAND')}")
        self._run_command(spoken, source="voice", live_desktop=True)

    def _show_element_confirm(self, result: dict) -> None:
        prompt = str(result.get("confirm_prompt") or "Do you mean this?")
        cands = list(result.get("candidates") or [])
        self.tasks.ensure()
        self.tasks.set_pending(
            PendingConfirm(kind="element", prompt=prompt, spoken=self._dai_last_cmd, candidates=cands)
        )
        labels = [str(c.get("text") or "") for c in cands if c.get("text")]
        if self._dai_overlay:
            self._dai_overlay.show()
            self._dai_overlay.show_element_confirm(prompt, labels)
        if cands:
            c = cands[0]
            try:
                self._highlight.show_box(int(c["x"]), int(c["y"]), int(c.get("width") or 40), int(c.get("height") or 20), ms=2400)
            except Exception:
                pass
        self.page_agent.show_clarify(prompt, labels)
        self._dai_awaiting_confirm = True
        self._arm_dai_idle()

    def _on_element_yes(self) -> None:
        pending = self.tasks.session.pending if self.tasks.session else None
        self._dai_awaiting_confirm = False
        if self._dai_overlay:
            self._dai_overlay.clear_clarify()
        if not pending:
            return
        if pending.kind == "safety" and pending.action.get("text"):
            self.tasks.set_pending(None)
            self._run_command(str(pending.action["text"]), source="voice", live_desktop=True)
            return
        if pending.candidates:
            self._click_candidate(pending.candidates[0])

    def _on_element_no(self) -> None:
        self._dai_awaiting_confirm = False
        self.tasks.set_pending(None)
        if self._dai_overlay:
            self._dai_overlay.clear_clarify()
            self._dai_overlay.set_mode("active", "Okay — say the exact label.")
        self._arm_dai_idle()

    def _click_candidate(self, cand: dict) -> None:
        self.tasks.set_pending(None)
        self._dai_awaiting_confirm = False
        if self._dai_overlay:
            self._dai_overlay.clear_clarify()
            self._dai_overlay.hide_for_action()
        set_dai_chrome_minimized(True)
        self.showMinimized()
        QApplication.processEvents()
        time.sleep(0.25)
        try:
            x = int(cand.get("x") or 0)
            y = int(cand.get("y") or 0)
            w = int(cand.get("width") or 0)
            h = int(cand.get("height") or 0)
            self._highlight.show_box(x, y, w or 40, h or 20, ms=400)
            self.pipeline.automation.capture_region = dict(getattr(self.pipeline.vision, "last_region", {}) or {})
            self.pipeline.automation.click(
                x + max(w, 8) // 2,
                y + max(h, 8) // 2,
                label=str(cand.get("text") or ""),
            )
            self.tasks.record(f"Clicked {cand.get('text') or 'element'}", ok=True)
            self.tasks.waiting_for_next()
        except Exception as exc:
            self.tasks.record(f"Click failed: {exc}", ok=False)
        set_dai_chrome_minimized(False)
        if self._dai_overlay:
            self._dai_overlay.show_after_action()
            self._dai_overlay.set_mode("active", "Done. What's next?")
        self.page_agent.set_task_history(self.tasks.session.history_lines() if self.tasks.session else [])
        self._arm_dai_idle()

    def _prompt_secret_and_type(self) -> None:
        dlg = QInputDialog(self)
        dlg.setWindowTitle("Secure input")
        dlg.setLabelText("Type the secret here. DAI will not log it.")
        dlg.setTextEchoMode(QLineEdit.Password)
        if dlg.exec_() != QInputDialog.Accepted:
            if self._dai_overlay:
                self._dai_overlay.set_mode("active", "Cancelled secret. What's next?")
            return
        secret = dlg.textValue()
        if not secret:
            return
        self.showMinimized()
        QApplication.processEvents()
        time.sleep(0.2)
        self.pipeline.automation.type_text(secret)
        self.tasks.record(history_line_for_type(sensitive=True), ok=True)
        self.tasks.waiting_for_next()
        if self._dai_overlay:
            self._dai_overlay.set_mode("active", "Entered secret. What's next?")
        self._arm_dai_idle()

    def _on_dai_confirm(self, text: str) -> None:
        choice = " ".join((text or "").split())
        if not choice:
            return
        self._dai_awaiting_confirm = False
        self._dai_sleep_timer.stop()
        if self._dai_overlay:
            self._dai_overlay.clear_clarify()
            self._dai_overlay.set_mode("busy", f"Yes — {choice}")
        self.page_agent.clear_clarify()
        self._run_command(choice, source="voice", live_desktop=True)

    def _remember_screen(self, result: dict) -> None:
        actions = list(result.get("actions") or [])
        last = actions[-1] if actions else result
        boxes = list(result.get("boxes") or last.get("boxes") or [])
        matches = list(last.get("matches") or [])
        det = last.get("detection") or {}
        elements = []
        if det.get("found") or det.get("x") is not None:
            elements.append(
                {
                    "text": det.get("label") or "",
                    "x": det.get("x"),
                    "y": det.get("y"),
                    "width": det.get("width") or 8,
                    "height": det.get("height") or 8,
                    "score": det.get("confidence"),
                }
            )
        for item in matches or boxes:
            if isinstance(item, dict):
                elements.append(item)
        if elements:
            self.tasks.set_screen(elements)
            self.tasks.session.last_target = elements[0] if self.tasks.session else {}

    def _wake_dai(self) -> None:
        self._dai_active = True
        self._dai_primed = False
        self._dai_prime_timer.stop()
        self._dai_final_timer.stop()
        self._speech_finalizer.clear()
        self._dai_awaiting_confirm = False
        if self._dai_thread is not None and hasattr(self._dai_thread, "set_session_active"):
            self._dai_thread.set_session_active(True)
        self._arm_dai_idle()
        if self._dai_overlay:
            self._dai_overlay.clear_clarify()
            self._dai_overlay.show()
            self._dai_overlay.set_mode("active", "Awake — speak a command")
        self.page_agent.clear_clarify()
        self.page_voice.set_status_message("DAI is awake — speak a command")
        self.tasks.ensure()
        self.toast.show("DAI is awake — I'll keep listening until you say done", "info")

    def _put_dai_to_sleep(self, detail: str = "") -> None:
        if self.tasks.active:
            self.tasks.complete("Session ended.")
        self._dai_active = False
        self._dai_primed = False
        self._dai_awaiting_confirm = False
        self._dai_queue.clear()
        self._dai_sleep_timer.stop()
        self._dai_prime_timer.stop()
        self._dai_final_timer.stop()
        self._speech_finalizer.clear()
        if self._dai_thread is not None and hasattr(self._dai_thread, "set_session_active"):
            self._dai_thread.set_session_active(False)
        if self._dai_overlay:
            self._dai_overlay.clear_clarify()
            self._dai_overlay.set_mode("sleep", detail or f"Sleeping — say {self._wake_prompt()}")
        self.page_agent.clear_clarify()

    def _arm_dai_idle(self) -> None:
        self._dai_sleep_timer.start(90000)

    def _dai_idle_timeout(self) -> None:
        if self._busy():
            self._arm_dai_idle()
            return
        self._put_dai_to_sleep(f"Timed out. Sleeping — say {self._wake_prompt()}")

    def _dai_clear_prime(self) -> None:
        self._dai_primed = False
        if self._dai_overlay and not self._dai_active:
            self._dai_overlay.set_mode("sleep", f"Sleeping — say {self._wake_prompt()}")

    def _dai_tap_wake(self) -> None:
        """Click the AI pill if wake word is not heard."""
        self._wake_dai()
        self.page_voice.set_status_message(f"{agent_name()} listening (tapped)")

    def _hide_dai_overlay(self) -> None:
        if self._dai_overlay:
            self._dai_overlay.hide()

    def _stop_dai_listener(self, keep_overlay: bool = False) -> None:
        self._dai_active = False
        self._dai_sleep_timer.stop()
        self._dai_prime_timer.stop()
        self._dai_final_timer.stop()
        self._speech_finalizer.clear()
        if self._dai_setup is not None:
            try:
                self._dai_setup.wait(400)
            except Exception:
                pass
            self._dai_setup = None
        if self._dai_thread is not None:
            self._dai_thread.stop()
            self._dai_thread.wait(1500)
            self._dai_thread = None
        if not keep_overlay and self._dai_overlay is not None:
            self._dai_overlay.close()
            self._dai_overlay = None
