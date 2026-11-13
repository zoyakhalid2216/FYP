"""Speech module: Chrome voice (no USB mic) + Whisper/Gemini + fast mic fallback."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.speech.browser_bridge import BrowserSpeechBridge
from src.speech.cloud_stt import audio_data_to_wav_bytes, resolve_api_keys, transcribe_wav_bytes


class SpeechService:
    """
    Capture voice commands quickly.

    Priority (engine=auto):
      1) Chrome Web Speech bridge — works with laptop mic, no USB / PyAudio required
      2) Microphone + OpenAI Whisper / Gemini (if API keys set)
      3) Microphone + Google Web Speech
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        speech_cfg = self.config.get("speech", {})
        self.engine = str(speech_cfg.get("engine", "auto")).lower()
        self.ambient_seconds = float(speech_cfg.get("ambient_seconds", 0.08))

        # Configurable utterance timing
        self.silence_seconds = float(speech_cfg.get("silence_seconds", speech_cfg.get("pause_threshold", 1.8)))
        self.max_phrase_seconds = float(speech_cfg.get("max_phrase_seconds", speech_cfg.get("phrase_time_limit", 30.0)))
        self.start_timeout_seconds = float(speech_cfg.get("start_timeout_seconds", speech_cfg.get("listen_timeout", 8.0)))
        self.phrase_time_limit = self.max_phrase_seconds
        self.listen_timeout = self.start_timeout_seconds

        self.energy_threshold = int(speech_cfg.get("energy_threshold", 120))
        self.mic_sensitivity = float(speech_cfg.get("mic_sensitivity", 0.9))
        self.pause_threshold = self.silence_seconds
        self.non_speaking_duration = min(
            float(speech_cfg.get("non_speaking_duration", 1.5)),
            max(0.2, self.pause_threshold - 0.2),
        )
        self.language = str(speech_cfg.get("language", "en-US"))
        self.browser_timeout = float(speech_cfg.get("browser_timeout", max(22.0, self.max_phrase_seconds)))
        self.cloud_prefer = str(speech_cfg.get("cloud_stt", "auto")).lower()
        self._available = True  # browser path always usable when Chrome exists
        self._sr = None
        self._recognizer = None
        self._mic_index: Optional[int] = None
        self._warmed = False
        self._last_error = ""
        self._last_backend = ""

        wake_w = speech_cfg.get("wake_word")
        if wake_w:
            from src.speech.wake import set_agent_name
            set_agent_name(str(wake_w))
        aliases = speech_cfg.get("wake_aliases")
        if aliases and isinstance(aliases, list):
            from src.speech.wake import set_wake_aliases
            set_wake_aliases(aliases)

        try:
            import speech_recognition as sr

            self._sr = sr
            self._recognizer = sr.Recognizer()
            self._configure()
            try:
                import pyaudio  # noqa: F401

                self._has_pyaudio = True
            except ImportError:
                self._has_pyaudio = False
        except ImportError:
            self._has_pyaudio = False

    @property
    def available(self) -> bool:
        # Always true: Chrome bridge and/or typed fallback messaging
        return True

    @property
    def mic_available(self) -> bool:
        return bool(self._sr and self._recognizer and self._has_pyaudio)

    @property
    def last_error(self) -> str:
        return self._last_error

    @property
    def last_backend(self) -> str:
        return self._last_backend

    def _configure(self) -> None:
        if not self._recognizer:
            return
        threshold = max(28, int(self.energy_threshold * (1.85 - self.mic_sensitivity)))
        self._recognizer.energy_threshold = threshold
        self._recognizer.dynamic_energy_threshold = False
        self._recognizer.pause_threshold = self.pause_threshold
        self._recognizer.non_speaking_duration = min(
            self.non_speaking_duration, max(0.15, self.pause_threshold - 0.05)
        )
        self._recognizer.operation_timeout = 8
        self._recognizer.phrase_threshold = 0.15

    def set_sensitivity(self, value: float) -> None:
        self.mic_sensitivity = max(0.15, min(1.0, float(value)))
        self._configure()

    def set_api_keys(self, *, openai_key: str = "", gemini_key: str = "") -> None:
        speech = self.config.setdefault("speech", {})
        if openai_key is not None:
            speech["openai_api_key"] = openai_key.strip()
        if gemini_key is not None:
            speech["gemini_api_key"] = gemini_key.strip()

    def cloud_status(self) -> Dict[str, bool]:
        keys = resolve_api_keys(self.config)
        return {"openai": bool(keys["openai"]), "gemini": bool(keys["gemini"])}

    def _pick_microphone_index(self) -> Optional[int]:
        if not self._sr:
            return None
        try:
            names = list(self._sr.Microphone.list_microphone_names() or [])
        except Exception as exc:
            self._last_error = str(exc)
            return None
        if not names:
            return None
        ranked = []
        for i, name in enumerate(names):
            n = (name or "").lower()
            score = 0
            if "default" in n:
                score += 50
            if "pulse" in n or "pipewire" in n:
                score += 40
            if any(k in n for k in ("usb", "headset", "microphone", "mic", "array", "built")):
                score += 30
            if any(k in n for k in ("monitor", "loopback", "null", "dummy")):
                score -= 80
            ranked.append((score, i, name))
        ranked.sort(reverse=True)
        return ranked[0][1] if ranked else 0

    def warm_up(self) -> bool:
        """Warm mic path in background; browser path needs no warm-up."""
        if not self.mic_available or self._warmed:
            return self._warmed
        # Skip warm-up when the machine has no audio capture device
        try:
            names = list(self._sr.Microphone.list_microphone_names() or [])
            if not names:
                return False
        except Exception:
            return False
        try:
            if self._mic_index is None:
                self._mic_index = self._pick_microphone_index()
            if self._mic_index is None:
                return False
            with self._sr.Microphone(device_index=self._mic_index) as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.08)
            self._warmed = True
            return True
        except Exception as exc:
            self._last_error = str(exc)
            return False

    def listen_once(self, status_cb: Optional[Callable[[str], None]] = None) -> str:
        emit = status_cb or (lambda _m: None)
        engine = self.engine
        errors = []

        if engine in ("auto", "offline", "vosk"):
            try:
                text = self._listen_offline(emit)
                self._last_backend = "vosk-offline"
                return text
            except Exception as exc:
                errors.append(str(exc))
                self._last_error = str(exc)
                if engine in ("offline", "vosk"):
                    raise
                emit("Offline voice unavailable — trying Chrome…")

        if engine in ("auto", "browser", "chrome"):
            try:
                text = self._listen_browser(emit)
                self._last_backend = "chrome-web-speech"
                return text
            except Exception as exc:
                errors.append(str(exc))
                self._last_error = str(exc)
                if engine in ("browser", "chrome") or not self.mic_available:
                    raise RuntimeError(
                        f"{exc} "
                        "Say DAI wakeup in the small desktop window, or type the command."
                    ) from exc
                emit("Chrome voice unavailable — trying laptop mic…")

        if engine in ("auto", "microphone", "mic", "cloud"):
            try:
                text = self._listen_microphone(emit)
                return text
            except Exception as exc:
                errors.append(str(exc))
                self._last_error = str(exc)
                if engine in ("microphone", "mic", "cloud"):
                    raise

        if engine not in ("auto", "browser", "chrome", "offline", "vosk"):
            try:
                text = self._listen_browser(emit)
                self._last_backend = "chrome-web-speech"
                return text
            except Exception as exc:
                errors.append(str(exc))

        msg = errors[-1] if errors else "Voice capture failed"
        raise RuntimeError(
            f"{msg} Tip: type the command and press Enter — same automation, instant."
        )

    def _listen_offline(self, emit) -> str:
        from src.speech.offline_stt import default_model_dir, listen_utterance, resolve_model_path

        model_dir = default_model_dir(self.config)
        if not resolve_model_path(model_dir):
            raise RuntimeError("Offline speech model not installed yet.")
        emit("Listening offline… speak now")
        return listen_utterance(
            model_dir,
            seconds=self.max_phrase_seconds,
            silence_seconds=self.silence_seconds,
            start_timeout=self.start_timeout_seconds,
            status_cb=emit,
        )

    def _listen_browser(self, emit) -> str:
        bridge = BrowserSpeechBridge(
            host=str(self.config.get("speech", {}).get("bridge_host", "127.0.0.1")),
            port=int(self.config.get("speech", {}).get("bridge_port", 8765)),
        )
        return bridge.listen(
            timeout=self.browser_timeout,
            silence_seconds=self.silence_seconds,
            start_timeout=self.start_timeout_seconds,
            status_cb=emit,
        )

    def _listen_microphone(self, emit) -> str:
        if not self.mic_available:
            raise RuntimeError(
                "Click Speak to use Chrome/Edge voice. "
                "No extra microphone library is required on this PC."
            )

        sr = self._sr
        recognizer = self._recognizer
        self._configure()

        if self._mic_index is None:
            self._mic_index = self._pick_microphone_index()
        if self._mic_index is None:
            raise RuntimeError("No microphone found. Chrome voice does not need a USB mic.")

        emit("Listening…")
        try:
            audio = self._capture_audio(recognizer, emit)
        except AttributeError as exc:
            raise RuntimeError("PyAudio missing — use Chrome voice (default).") from exc
        except OSError as exc:
            self._last_error = str(exc)
            raise RuntimeError(
                f"Microphone blocked ({exc}). Use Chrome voice or type the command."
            ) from exc
        except sr.WaitTimeoutError as exc:
            raise RuntimeError(
                "Didn’t catch speech. Click Mic, wait for “Speak now…”, then talk."
            ) from exc

        emit("Transcribing…")
        text = self._transcribe(audio, emit)
        text = " ".join((text or "").strip().split())
        if not text:
            raise RuntimeError("Empty transcription. Please try again.")
        return text

    def _capture_audio(self, recognizer, emit):
        sr = self._sr
        attempts = (
            {"device_index": self._mic_index, "sample_rate": 16000},
            {"device_index": self._mic_index},
        )
        last_exc = None
        for kwargs in attempts:
            try:
                with sr.Microphone(**kwargs) as source:
                    if not self._warmed:
                        recognizer.adjust_for_ambient_noise(
                            source, duration=self.ambient_seconds
                        )
                        self._warmed = True
                    lo = max(25, int(self.energy_threshold * 0.3))
                    hi = max(lo + 15, int(self.energy_threshold * 2.0))
                    recognizer.energy_threshold = min(
                        max(recognizer.energy_threshold, lo), hi
                    )
                    emit("Speak now…")
                    return recognizer.listen(
                        source,
                        timeout=self.listen_timeout,
                        phrase_time_limit=self.phrase_time_limit,
                    )
            except OSError as exc:
                last_exc = exc
                continue
        if last_exc:
            raise last_exc
        raise RuntimeError("Could not open microphone.")

    def _transcribe(self, audio, emit) -> str:
        sr = self._sr
        recognizer = self._recognizer

        # Prefer Whisper / Gemini when keys exist (more accurate for short commands)
        keys = resolve_api_keys(self.config)
        if keys["openai"] or keys["gemini"]:
            try:
                emit("Cloud STT…")
                wav = audio_data_to_wav_bytes(audio)
                text, backend = transcribe_wav_bytes(
                    wav,
                    language=self.language,
                    config=self.config,
                    prefer=self.cloud_prefer,
                )
                self._last_backend = backend
                return text
            except RuntimeError as exc:
                if str(exc) != "no_cloud_keys":
                    self._last_error = str(exc)
                # fall through to Google

        try:
            text = recognizer.recognize_google(audio, language=self.language)
            self._last_backend = "google-web-speech"
            return text
        except sr.UnknownValueError as exc:
            try:
                result = recognizer.recognize_google(
                    audio, language=self.language, show_all=True
                )
                if isinstance(result, dict):
                    alts = result.get("alternative") or []
                    if alts:
                        best = (alts[0].get("transcript") or "").strip()
                        if best:
                            self._last_backend = "google-web-speech"
                            return best
            except Exception:
                pass
            raise RuntimeError(
                "Could not understand audio. Speak closer/clearer, then retry."
            ) from exc
        except sr.RequestError as exc:
            try:
                text = recognizer.recognize_sphinx(audio)
                self._last_backend = "sphinx"
                return text
            except Exception:
                raise RuntimeError(
                    f"Speech service error: {exc}. Check internet — or type the command."
                ) from exc
