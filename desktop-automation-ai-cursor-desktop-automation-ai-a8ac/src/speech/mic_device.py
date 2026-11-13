"""Pick a working Windows microphone for PortAudio / sounddevice."""

from __future__ import annotations

import audioop
from typing import Any, Dict, List, Optional, Tuple

VOSK_RATE = 16000
_SKIP_HOST = ("asio", "jack")
_HOST_SCORE = {
    "wasapi": 80,
    "wdm-ks": 70,
    "wdm": 70,
    "directsound": 60,
    "mme": 50,
    "core audio": 80,
    "alsa": 70,
    "pulse": 75,
    "pipewire": 75,
}


def friendly_mic_error(exc: BaseException) -> str:
    msg = str(exc)
    low = msg.lower()
    if (
        "-9999" in msg
        or "no driver" in low
        or "unanticipated host" in low
        or "invalid device" in low
        or "portaudio" in low
        or "paerror" in low
    ):
        return (
            "Windows has no usable mic driver. "
            "Settings → Privacy → Microphone → On for desktop apps and Python. "
            "Then Retry. Typed commands still work."
        )
    return msg


def _host_name(sd, host_index: int) -> str:
    try:
        return str(sd.query_hostapis(host_index).get("name") or "")
    except Exception:
        return ""


def list_input_candidates(sd) -> List[Dict[str, Any]]:
    """Rank input devices; skip ASIO (causes PaError -9999 with no ASIO driver)."""
    try:
        devices = list(sd.query_devices())
    except Exception:
        return []
    ranked: List[Tuple[int, Dict[str, Any]]] = []
    for idx, dev in enumerate(devices):
        if int(dev.get("max_input_channels") or 0) < 1:
            continue
        host = _host_name(sd, int(dev.get("hostapi") or 0))
        hlow = host.lower()
        if any(s in hlow for s in _SKIP_HOST):
            continue
        score = 10
        for key, pts in _HOST_SCORE.items():
            if key in hlow:
                score = pts
                break
        name = str(dev.get("name") or "").lower()
        if "default" in name or "primary" in name or "mapper" in name:
            score += 8
        if any(k in name for k in ("microphone", "mic", "array", "headset", "realtek", "webcam")):
            score += 6
        if "stereo mix" in name or "loopback" in name or "output" in name:
            score -= 40
        default_sr = int(float(dev.get("default_samplerate") or 44100))
        ranked.append(
            (
                score,
                {
                    "index": idx,
                    "name": dev.get("name"),
                    "host": host,
                    "rate": default_sr,
                    "channels": int(dev.get("max_input_channels") or 1),
                },
            )
        )
    ranked.sort(key=lambda x: -x[0])
    return [item for _s, item in ranked]


def open_best_input_stream(sd, *, vosk_rate: int = VOSK_RATE):
    """
    Open a 1-channel int16 stream. Returns (stream, capture_rate).
    capture_rate may differ from 16 kHz; resample_for_vosk() converts.
    """
    candidates = list_input_candidates(sd)
    if not candidates:
        # Last try: PortAudio default
        candidates = [{"index": None, "name": "default", "host": "", "rate": 44100, "channels": 1}]

    errors: List[str] = []
    rates_try = (16000, 44100, 48000, 32000, 22050)
    for cand in candidates[:8]:
        device = cand["index"]
        want_rates = [16000]
        if cand.get("rate"):
            r0 = int(cand["rate"])
            if r0 not in want_rates:
                want_rates.append(r0)
        for r in rates_try:
            if r not in want_rates:
                want_rates.append(r)
        for latency in ("low", "high"):
            for rate in want_rates:
                for ch in (1, min(2, int(cand.get("channels") or 1))):
                    try:
                        stream = sd.RawInputStream(
                            device=device,
                            samplerate=rate,
                            blocksize=0,
                            dtype="int16",
                            channels=ch,
                            latency=latency,
                        )
                        if not getattr(stream, "active", False):
                            stream.start()
                        return stream, int(rate), int(ch)
                    except Exception as exc:
                        try:
                            stream.close()  # type: ignore[name-defined]
                        except Exception:
                            pass
                        errors.append(f"{cand.get('name')} {rate}Hz {latency}: {exc}")
                        continue
    detail = errors[-1] if errors else "no input devices"
    raise RuntimeError(friendly_mic_error(RuntimeError(detail)))


def resample_for_vosk(raw: bytes, capture_rate: int, channels: int = 1, vosk_rate: int = VOSK_RATE) -> bytes:
    """Convert captured PCM16 to 16 kHz mono for Vosk."""
    if not raw:
        return raw
    pcm = raw
    if channels > 1:
        # take left channel
        try:
            pcm = audioop.tomono(pcm, 2, 1, 0)
        except Exception:
            pcm = raw
    if capture_rate == vosk_rate:
        return pcm
    try:
        converted, _state = audioop.ratecv(pcm, 2, 1, capture_rate, vosk_rate, None)
        return converted
    except Exception:
        return pcm


def read_vosk_chunk(stream, capture_rate: int, channels: int, *, seconds: float = 0.08) -> bytes:
    frames = max(512, int(capture_rate * seconds))
    data, _overflow = stream.read(frames)
    return resample_for_vosk(bytes(data), capture_rate, channels=channels)
