"""Always-on Vosk microphone thread (offline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

from src.speech.wake import (
    WAKE_GRAMMAR,
    classify_utterance,
    is_wake_phrase,
    is_wakeup_followup,
)


class DaiSetupThread(QThread):
    """Load or download the offline model, then report the folder path."""

    ready = pyqtSignal(str)
    failed = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, config: Optional[dict] = None, parent=None) -> None:
        super().__init__(parent)
        self.config = config or {}

    def run(self) -> None:
        try:
            from src.speech.offline_stt import (
                default_model_dir,
                ensure_model,
                ensure_offline_packages,
            )

            ensure_offline_packages(status_cb=self.status.emit)
            path = ensure_model(
                default_model_dir(self.config),
                status_cb=self.status.emit,
                allow_download=True,
            )
            self.ready.emit(str(path))
        except Exception as exc:
            self.failed.emit(str(exc))


class DaiMicThread(QThread):
    """Continuously listen: wake grammar + free-form STT in parallel."""

    heard = pyqtSignal(str)
    heard_alts = pyqtSignal(str, list)
    partial = pyqtSignal(str)
    status = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, model_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.model_path = Path(model_path)
        self._stop = False
        self._session_active = False

    def stop(self) -> None:
        self._stop = True

    def set_session_active(self, active: bool) -> None:
        self._session_active = bool(active)

    def run(self) -> None:
        from src.speech.mic_device import (
            friendly_mic_error,
            open_best_input_stream,
            read_vosk_chunk,
        )

        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel
            import sounddevice as sd

            SetLogLevel(-1)
        except ImportError:
            self.failed.emit(
                "Offline mic packages missing (vosk/sounddevice). Run FIX_INSTALL.bat."
            )
            return

        stream = None
        try:
            self.status.emit("Loading offline speech…")
            model = Model(str(self.model_path))

            def make_recs():
                wake = KaldiRecognizer(model, 16000, WAKE_GRAMMAR)
                cmd = KaldiRecognizer(model, 16000)
                wake.SetWords(False)
                cmd.SetWords(False)
                try:
                    cmd.SetMaxAlternatives(3)
                except Exception:
                    pass
                return wake, cmd

            def pick_text(payload):
                texts = []
                for alt in payload.get("alternatives") or []:
                    piece = " ".join(str((alt or {}).get("text") or "").split())
                    if piece:
                        texts.append(piece)
                main = " ".join(str(payload.get("text") or "").split())
                if main:
                    texts.insert(0, main)
                seen = set()
                uniq = []
                for piece in texts:
                    key = piece.lower()
                    if key in ("[unk]", "unk"):
                        continue
                    if key not in seen:
                        seen.add(key)
                        uniq.append(piece)
                return uniq

            def choose_heard(texts, session):
                ranked = []
                for t in texts:
                    if not t:
                        continue
                    kind, cmd = classify_utterance(t, session_active=session)
                    if kind == "ignore":
                        if (not session) and (is_wake_phrase(t) or is_wakeup_followup(t)):
                            ranked.append((3, 0, t))
                        continue
                    extra = len((cmd or t).split())
                    rank = 4 + extra
                    if kind in ("close", "minimize", "restore", "repeat"):
                        rank = 20
                    elif kind == "wake":
                        rank = 10 + extra
                    ranked.append((rank, extra, t))
                if not ranked:
                    return ""
                ranked.sort(reverse=True)
                return ranked[0][2]

            rec_wake, rec_cmd = make_recs()
            self.status.emit("Opening microphone…")
            stream, cap_rate, channels = open_best_input_stream(sd)
            self.status.emit("Offline mic on — say AI")
            last_partial = ""
            last_emitted = ""
            last_session = False
            while not self._stop:
                session = self._session_active
                if last_session and not session:
                    rec_wake, rec_cmd = make_recs()
                    last_partial = ""
                    last_emitted = ""
                last_session = session

                raw = read_vosk_chunk(stream, cap_rate, channels, seconds=0.08)
                wake_final = rec_wake.AcceptWaveform(raw)
                cmd_final = rec_cmd.AcceptWaveform(raw)

                wake_texts = []
                cmd_texts = []
                if wake_final:
                    wake_texts = pick_text(json.loads(rec_wake.Result() or "{}"))
                if cmd_final:
                    cmd_texts = pick_text(json.loads(rec_cmd.Result() or "{}"))

                wake_partial = ""
                cmd_partial = ""
                if not wake_final:
                    wake_partial = " ".join(
                        str(
                            json.loads(rec_wake.PartialResult() or "{}").get("partial") or ""
                        ).split()
                    )
                if not cmd_final:
                    cmd_partial = " ".join(
                        str(
                            json.loads(rec_cmd.PartialResult() or "{}").get("partial") or ""
                        ).split()
                    )

                live = cmd_partial or wake_partial
                if live and live != last_partial:
                    last_partial = live
                    self.partial.emit(live)

                candidates = []
                candidates.extend(cmd_texts)
                candidates.extend(wake_texts)
                chosen = choose_heard(candidates, session)

                if chosen and chosen.lower() != last_emitted.lower():
                    last_emitted = chosen
                    alts = [c for c in candidates if c and c.lower() != chosen.lower()]
                    self.heard.emit(chosen)
                    self.heard_alts.emit(chosen, alts)
                    last_partial = ""
                    rec_wake, rec_cmd = make_recs()
                    continue
        except Exception as exc:
            self.failed.emit(friendly_mic_error(exc))
        finally:
            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    pass
                try:
                    stream.close()
                except Exception:
                    pass
