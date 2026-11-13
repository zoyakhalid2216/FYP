"""Settings — theme, safety, voice, cloud STT."""

from __future__ import annotations

from typing import Any, Dict

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    save_requested = pyqtSignal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(14)

        title = QLabel("System Settings")
        title.setObjectName("pageTitle")
        sub = QLabel(
            "General, AI planner, voice, automation safety, and privacy — local vs AI-enhanced."
        )
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        card = QFrame()
        card.setObjectName("panelCard")
        card.setMaximumWidth(720)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 22, 24, 22)
        cl.setSpacing(18)

        cl.addWidget(self._section("Agent name"))
        name_row = QHBoxLayout()
        name_row.setSpacing(12)
        name_lbl = QLabel("Call me")
        name_lbl.setMinimumWidth(140)
        self.agent_name = QLineEdit()
        self.agent_name.setText("AI")
        self.agent_name.setMaxLength(24)
        self.agent_name.setPlaceholderText("AI")
        self.agent_name.setMinimumHeight(34)
        self.agent_name.setMinimumWidth(180)
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.agent_name)
        name_row.addStretch(1)
        cl.addLayout(name_row)
        name_tip = QLabel(
            "Say this name to start listening, e.g. “AI” or “AI, open Chrome”. "
            "DAI still works as a backup."
        )
        name_tip.setObjectName("pageSubtitle")
        name_tip.setWordWrap(True)
        cl.addWidget(name_tip)

        # Appearance
        cl.addWidget(self._section("Appearance"))
        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)
        theme_lbl = QLabel("Theme")
        theme_lbl.setMinimumWidth(140)
        self.theme = QComboBox()
        self.theme.addItems(["light", "dark"])
        self.theme.setMinimumWidth(160)
        self.theme.setMinimumHeight(34)
        theme_row.addWidget(theme_lbl)
        theme_row.addWidget(self.theme)
        theme_row.addStretch(1)
        cl.addLayout(theme_row)

        # Safety
        cl.addWidget(self._section("Automation safety"))
        self.dry_run = QCheckBox("Dry-run (safe mode — no real mouse/keyboard)")
        self.dry_run.setChecked(False)
        tip = QLabel(
            "Leave dry-run OFF to actually open Chrome, click, type, and search."
        )
        tip.setObjectName("pageSubtitle")
        tip.setWordWrap(True)
        tip.setContentsMargins(24, 0, 0, 0)
        self.failsafe = QCheckBox("Fail-safe (move mouse to corner to abort)")
        self.failsafe.setChecked(True)

        pause_row = QHBoxLayout()
        pause_row.setSpacing(12)
        pause_lbl = QLabel("Action pause (sec)")
        pause_lbl.setMinimumWidth(140)
        self.pause = QDoubleSpinBox()
        self.pause.setRange(0.02, 3.0)
        self.pause.setSingleStep(0.02)
        self.pause.setValue(0.04)
        self.pause.setMinimumWidth(100)
        self.pause.setMinimumHeight(34)
        pause_row.addWidget(pause_lbl)
        pause_row.addWidget(self.pause)
        pause_row.addStretch(1)

        cl.addWidget(self.dry_run)
        cl.addWidget(tip)
        cl.addWidget(self.failsafe)
        cl.addLayout(pause_row)

        # AI
        cl.addWidget(self._section("AI"))
        self.ai_mode = QComboBox()
        self.ai_mode.addItems(["local", "enhanced"])
        self.ai_mode.setMinimumHeight(34)
        self.confirm_plan = QCheckBox("Explain plan and wait for Execute on the AI Agent page")
        self.confirm_plan.setChecked(True)
        self.min_conf = QDoubleSpinBox()
        self.min_conf.setRange(0.2, 0.95)
        self.min_conf.setSingleStep(0.05)
        self.min_conf.setValue(0.45)
        ai_form = QFormLayout()
        ai_form.addRow("Planner mode", self.ai_mode)
        ai_form.addRow("Confidence threshold", self.min_conf)
        cl.addLayout(ai_form)
        cl.addWidget(self.confirm_plan)
        mode_tip = QLabel(
            "Local = offline NLP planner + Vosk. Enhanced = same planner plus optional cloud STT keys."
        )
        mode_tip.setObjectName("pageSubtitle")
        mode_tip.setWordWrap(True)
        cl.addWidget(mode_tip)

        # Limits
        cl.addWidget(self._section("Automation limits"))
        self.max_actions = QSpinBox()
        self.max_actions.setRange(3, 200)
        self.max_actions.setValue(30)
        self.max_seconds = QSpinBox()
        self.max_seconds.setRange(5, 600)
        self.max_seconds.setValue(60)
        self.max_retries = QSpinBox()
        self.max_retries.setRange(1, 8)
        self.max_retries.setValue(3)
        self.verify_actions = QCheckBox("Verify screen changed after clicks")
        self.verify_actions.setChecked(True)
        lim = QFormLayout()
        lim.addRow("Max actions / command", self.max_actions)
        lim.addRow("Max seconds / command", self.max_seconds)
        lim.addRow("Retries per action", self.max_retries)
        cl.addLayout(lim)
        cl.addWidget(self.verify_actions)

        # Voice
        cl.addWidget(self._section("Voice / microphone"))
        sens_head = QHBoxLayout()
        sens_head.addWidget(QLabel("Sensitivity"))
        sens_head.addStretch(1)
        self.voice_lbl = QLabel("0.70")
        self.voice_lbl.setObjectName("pageSubtitle")
        sens_head.addWidget(self.voice_lbl)
        cl.addLayout(sens_head)

        self.voice = QSlider(Qt.Horizontal)
        self.voice.setRange(10, 100)
        self.voice.setValue(70)
        self.voice.setMinimumHeight(28)
        self.voice.valueChanged.connect(
            lambda v: self.voice_lbl.setText(f"{v / 100:.2f}")
        )
        cl.addWidget(self.voice)
        range_row = QHBoxLayout()
        lo = QLabel("0.10")
        lo.setObjectName("pageSubtitle")
        hi = QLabel("1.00")
        hi.setObjectName("pageSubtitle")
        range_row.addWidget(lo)
        range_row.addStretch(1)
        range_row.addWidget(hi)
        cl.addLayout(range_row)

        voice_timing = QFormLayout()
        self.silence_sec = QDoubleSpinBox()
        self.silence_sec.setRange(0.5, 5.0)
        self.silence_sec.setSingleStep(0.1)
        self.silence_sec.setValue(1.8)
        self.max_phrase = QSpinBox()
        self.max_phrase.setRange(5, 60)
        self.max_phrase.setValue(30)
        self.start_timeout = QSpinBox()
        self.start_timeout.setRange(3, 30)
        self.start_timeout.setValue(8)
        voice_timing.addRow("End utterance after silence (s)", self.silence_sec)
        voice_timing.addRow("Max phrase length (s)", self.max_phrase)
        voice_timing.addRow("Start timeout (s)", self.start_timeout)
        cl.addLayout(voice_timing)

        # Cloud
        cl.addWidget(self._section("Cloud speech (optional)"))
        cloud_tip = QLabel(
            "Leave blank to use Chrome voice (default). Keys also work via environment variables."
        )
        cloud_tip.setObjectName("pageSubtitle")
        cloud_tip.setWordWrap(True)
        cl.addWidget(cloud_tip)

        keys = QFormLayout()
        keys.setSpacing(10)
        keys.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.Password)
        self.openai_key.setPlaceholderText("OPENAI_API_KEY for Whisper")
        self.openai_key.setMinimumHeight(34)
        self.gemini_key = QLineEdit()
        self.gemini_key.setEchoMode(QLineEdit.Password)
        self.gemini_key.setPlaceholderText("GEMINI_API_KEY for Gemini audio")
        self.gemini_key.setMinimumHeight(34)
        keys.addRow("OpenAI", self.openai_key)
        keys.addRow("Gemini", self.gemini_key)
        cl.addLayout(keys)

        cl.addWidget(self._section("Privacy"))
        self.cloud_ai = QCheckBox("Allow cloud AI (Whisper / Gemini) when keys are set")
        self.store_shots = QCheckBox("Store screenshots in SQLite / data/captures")
        self.store_shots.setChecked(True)
        self.store_history = QCheckBox("Store command history")
        self.store_history.setChecked(True)
        cl.addWidget(self.cloud_ai)
        cl.addWidget(self.store_shots)
        cl.addWidget(self.store_history)

        # Actions — avoid bare "&" (Qt mnemonic); use separate buttons
        actions = QHBoxLayout()
        actions.setSpacing(10)
        save = QPushButton("Apply and return")
        save.setObjectName("btnPrimary")
        save.setMinimumHeight(38)
        save.setMinimumWidth(140)
        save.clicked.connect(self._save)
        actions.addWidget(save)
        actions.addStretch(1)
        cl.addLayout(actions)

        root.addWidget(card)
        root.addStretch(1)

        scroll.setWidget(host)
        outer.addWidget(scroll)

    def _section(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("sectionTitle")
        return lab

    def apply_conf(self, conf: Dict[str, Any]) -> None:
        theme = str(conf.get("theme", "light")).lower()
        idx = self.theme.findText(theme)
        self.theme.setCurrentIndex(idx if idx >= 0 else 0)
        self.dry_run.setChecked(str(conf.get("dry_run", "0")) in ("1", "true", "True"))
        self.failsafe.setChecked(str(conf.get("failsafe", "1")) in ("1", "true", "True"))
        self.pause.setValue(float(conf.get("pause_seconds", 0.04)))
        sens = float(conf.get("voice_sensitivity", conf.get("mic_sensitivity", 0.9)))
        self.voice.setValue(int(sens * 100))
        if conf.get("openai_api_key"):
            self.openai_key.setText(str(conf.get("openai_api_key")))
        if conf.get("gemini_api_key"):
            self.gemini_key.setText(str(conf.get("gemini_api_key")))
        idxm = self.ai_mode.findText(str(conf.get("ai_mode", "local")))
        self.ai_mode.setCurrentIndex(idxm if idxm >= 0 else 0)
        self.confirm_plan.setChecked(str(conf.get("confirm_plan", "1")) in ("1", "true", "True"))
        try:
            self.min_conf.setValue(float(conf.get("min_confidence", 0.45)))
        except (TypeError, ValueError):
            pass
        self.max_actions.setValue(int(float(conf.get("max_actions", 30))))
        self.max_seconds.setValue(int(float(conf.get("max_seconds", 60))))
        self.max_retries.setValue(int(float(conf.get("max_retries", 3))))
        self.verify_actions.setChecked(str(conf.get("verify_actions", "1")) in ("1", "true", "True"))
        self.cloud_ai.setChecked(str(conf.get("cloud_ai", "0")) in ("1", "true", "True"))
        self.store_shots.setChecked(str(conf.get("store_screenshots", "1")) in ("1", "true", "True"))
        self.store_history.setChecked(str(conf.get("store_history", "1")) in ("1", "true", "True"))
        self.agent_name.setText(str(conf.get("agent_name") or "AI"))
        try:
            self.silence_sec.setValue(float(conf.get("silence_seconds", 1.8)))
            self.max_phrase.setValue(int(float(conf.get("max_phrase_seconds", 30))))
            self.start_timeout.setValue(int(float(conf.get("start_timeout_seconds", 8))))
        except (TypeError, ValueError):
            pass

    def _save(self) -> None:
        payload = {
            "theme": self.theme.currentText(),
            "dry_run": "1" if self.dry_run.isChecked() else "0",
            "failsafe": "1" if self.failsafe.isChecked() else "0",
            "pause_seconds": str(self.pause.value()),
            "voice_sensitivity": f"{self.voice.value() / 100:.2f}",
            "mic_sensitivity": f"{self.voice.value() / 100:.2f}",
            "silence_seconds": str(self.silence_sec.value()),
            "max_phrase_seconds": str(self.max_phrase.value()),
            "start_timeout_seconds": str(self.start_timeout.value()),
            "ai_mode": self.ai_mode.currentText(),
            "confirm_plan": "1" if self.confirm_plan.isChecked() else "0",
            "min_confidence": str(self.min_conf.value()),
            "max_actions": str(self.max_actions.value()),
            "max_seconds": str(self.max_seconds.value()),
            "max_retries": str(self.max_retries.value()),
            "verify_actions": "1" if self.verify_actions.isChecked() else "0",
            "cloud_ai": "1" if self.cloud_ai.isChecked() else "0",
            "store_screenshots": "1" if self.store_shots.isChecked() else "0",
            "store_history": "1" if self.store_history.isChecked() else "0",
            "agent_name": self.agent_name.text().strip() or "AI",
        }
        if self.openai_key.text().strip():
            payload["openai_api_key"] = self.openai_key.text().strip()
        if self.gemini_key.text().strip():
            payload["gemini_api_key"] = self.gemini_key.text().strip()
        self.save_requested.emit(payload)
