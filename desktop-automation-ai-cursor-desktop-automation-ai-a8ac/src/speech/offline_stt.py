"""Offline speech (Vosk) — works with no internet after the model is on disk."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Callable, Optional
from urllib.request import urlopen

from src.config import ROOT_DIR

VOSK_MODEL_NAME = "vosk-model-small-en-us-0.15"
VOSK_MODEL_URL = (
    f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"
)


def default_model_dir(config: Optional[dict] = None) -> Path:
    rel = "data/models"
    if config:
        rel = str((config.get("paths") or {}).get("models_dir") or rel)
    path = Path(rel)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path / VOSK_MODEL_NAME


def model_is_ready(model_dir: Path) -> bool:
    # Vosk models contain am/ + conf/ (or a nested folder with those)
    if (model_dir / "am").is_dir() and (model_dir / "conf").is_dir():
        return True
    if not model_dir.is_dir():
        return False
    for child in model_dir.iterdir():
        if child.is_dir() and (child / "am").is_dir() and (child / "conf").is_dir():
            return True
    return False


def resolve_model_path(model_dir: Path) -> Optional[Path]:
    if (model_dir / "am").is_dir():
        return model_dir
    if model_dir.is_dir():
        for child in model_dir.iterdir():
            if child.is_dir() and (child / "am").is_dir():
                return child
    return None


def ensure_model(
    model_dir: Path,
    *,
    status_cb: Optional[Callable[[str], None]] = None,
    allow_download: bool = True,
) -> Path:
    emit = status_cb or (lambda _m: None)
    ready = resolve_model_path(model_dir)
    if ready:
        return ready
    if not allow_download:
        raise RuntimeError(
            "Offline speech model is not installed. Connect once and run FIX_INSTALL.bat."
        )
    emit("Downloading offline speech model (one-time, ~40 MB)…")
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    zip_path = model_dir.parent / f"{VOSK_MODEL_NAME}.zip"
    try:
        with urlopen(VOSK_MODEL_URL, timeout=60) as resp, zip_path.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                fh.write(chunk)
        emit("Unpacking speech model…")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(model_dir.parent)
    except Exception as exc:
        raise RuntimeError(
            "Could not download the offline speech model. "
            "Connect to the internet once, then retry. "
            f"({exc})"
        ) from exc
    finally:
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass
    ready = resolve_model_path(model_dir)
    if not ready:
        # extracted folder may already be named correctly
        ready = resolve_model_path(model_dir.parent / VOSK_MODEL_NAME)
    if not ready:
        raise RuntimeError("Speech model extract failed.")
    emit("Offline speech model ready.")
    return ready


def ensure_offline_packages(status_cb: Optional[Callable[[str], None]] = None) -> None:
    """Install vosk + sounddevice into this Python if they are missing."""
    emit = status_cb or (lambda _m: None)
    try:
        import sounddevice  # noqa: F401
        import vosk  # noqa: F401

        return
    except ImportError:
        pass
    import subprocess
    import sys

    emit("Installing offline mic packages (vosk, sounddevice)…")
    cmd = [sys.executable, "-m", "pip", "install", "vosk", "sounddevice"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "pip failed").strip().splitlines()
        tail = err[-1] if err else "pip failed"
        raise RuntimeError(
            "Could not install vosk/sounddevice. In the project folder run:\n"
            ".venv\\Scripts\\python.exe -m pip install vosk sounddevice\n"
            f"({tail})"
        )
    try:
        import sounddevice  # noqa: F401
        import vosk  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "vosk/sounddevice still missing after pip. Run FIX_INSTALL.bat"
        ) from exc
    emit("Offline mic packages installed.")


def process_vosk_stream(
    read_chunk_fn: Callable[[], bytes],
    rec: Any,
    *,
    seconds: float = 30.0,
    silence_seconds: float = 1.8,
    start_timeout: float = 8.0,
    status_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """Read chunks from read_chunk_fn, process via rec, and wait for silence_seconds after speech begins."""
    import time

    emit = status_cb or (lambda _m: None)
    now = time.time()
    deadline = now + max(1.0, float(seconds))
    start_deadline = now + max(0.1, float(start_timeout))
    speech_started = False
    last_speech_at: Optional[float] = None
    accumulated_chunks = []
    last_partial = ""

    while time.time() < deadline:
        t_curr = time.time()
        if not speech_started and t_curr > start_deadline:
            raise TimeoutError("Didn’t catch speech within start timeout. Speak clearly or type.")

        raw = read_chunk_fn()
        if not raw:
            time.sleep(0.01)
            continue

        accepted = rec.AcceptWaveform(raw)
        if accepted:
            payload = json.loads(rec.Result() or "{}")
            chunk_text = " ".join(str(payload.get("text") or "").split())
            if chunk_text:
                accumulated_chunks.append(chunk_text)
                speech_started = True
                last_speech_at = t_curr
                emit(f"Hearing: {' '.join(accumulated_chunks)}")
        else:
            partial = json.loads(rec.PartialResult() or "{}").get("partial") or ""
            if partial:
                speech_started = True
                last_speech_at = t_curr
                if partial != last_partial:
                    last_partial = partial
                    full_preview = (" ".join(accumulated_chunks) + " " + partial).strip()
                    emit(f"Hearing: {full_preview}")

        # Once speech has started, stop only after silence_seconds of silence
        if speech_started and last_speech_at is not None:
            if (t_curr - last_speech_at) >= silence_seconds:
                break

    payload = json.loads(rec.FinalResult() or "{}")
    final_text = " ".join(str(payload.get("text") or "").split())
    if final_text:
        accumulated_chunks.append(final_text)

    full_result = " ".join(accumulated_chunks).strip()
    if not full_result:
        raise RuntimeError("Didn’t catch speech. Say AI wakeup, then your command.")
    return full_result


def listen_utterance(
    model_dir: Path,
    *,
    seconds: float = 30.0,
    silence_seconds: float = 1.8,
    start_timeout: float = 8.0,
    samplerate: int = 16000,
    status_cb: Optional[Callable[[str], None]] = None,
) -> str:
    """Capture one phrase offline with continuous listening until a silence window."""
    emit = status_cb or (lambda _m: None)
    try:
        from vosk import KaldiRecognizer, Model
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(
            "Offline speech packages missing. Run FIX_INSTALL.bat (vosk + sounddevice)."
        ) from exc

    path = resolve_model_path(model_dir)
    if not path:
        path = ensure_model(model_dir, status_cb=emit, allow_download=True)
    emit("Listening (offline)… speak now")
    model = Model(str(path))
    rec = KaldiRecognizer(model, 16000)
    rec.SetWords(False)

    from src.speech.mic_device import open_best_input_stream, read_vosk_chunk

    stream, cap_rate, channels = open_best_input_stream(sd)
    try:
        return process_vosk_stream(
            lambda: read_vosk_chunk(stream, cap_rate, channels),
            rec,
            seconds=seconds,
            silence_seconds=silence_seconds,
            start_timeout=start_timeout,
            status_cb=emit,
        )
    finally:
        try:
            stream.stop()
            stream.close()
        except Exception:
            pass
