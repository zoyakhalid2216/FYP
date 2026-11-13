"""Cloud speech-to-text backends (OpenAI Whisper + Google Gemini)."""

from __future__ import annotations

import io
import os
import wave
from typing import Any, Dict, Optional, Tuple


def _env_key(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def resolve_api_keys(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    speech = (config or {}).get("speech", {})
    openai_key = (
        str(speech.get("openai_api_key") or "").strip()
        or _env_key("OPENAI_API_KEY", "OPENAI_KEY")
    )
    gemini_key = (
        str(speech.get("gemini_api_key") or "").strip()
        or _env_key("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")
    )
    return {"openai": openai_key, "gemini": gemini_key}


def audio_data_to_wav_bytes(audio_data) -> bytes:
    """Convert SpeechRecognition AudioData to mono WAV bytes."""
    raw = audio_data.get_wav_data()
    return raw


def pcm_to_wav_bytes(pcm: bytes, *, sample_rate: int = 16000, sample_width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def transcribe_wav_bytes(
    wav_bytes: bytes,
    *,
    language: str = "en",
    config: Optional[Dict[str, Any]] = None,
    prefer: str = "auto",
) -> Tuple[str, str]:
    """
    Transcribe WAV audio with the fastest available cloud backend.

    Returns (text, backend_name). Raises RuntimeError if none succeed.
    """
    keys = resolve_api_keys(config)
    lang = (language or "en").split("-")[0].lower()
    errors = []

    order = []
    if prefer == "openai":
        order = ["openai", "gemini"]
    elif prefer == "gemini":
        order = ["gemini", "openai"]
    else:
        # Whisper tends to be snappy for short commands; try it first when keyed
        order = ["openai", "gemini"]

    for backend in order:
        if backend == "openai" and keys["openai"]:
            try:
                text = _openai_whisper(wav_bytes, api_key=keys["openai"], language=lang)
                if text:
                    return text, "openai-whisper"
            except Exception as exc:
                errors.append(f"openai: {exc}")
        if backend == "gemini" and keys["gemini"]:
            try:
                text = _gemini_audio(wav_bytes, api_key=keys["gemini"], language=lang)
                if text:
                    return text, "gemini"
            except Exception as exc:
                errors.append(f"gemini: {exc}")

    if not keys["openai"] and not keys["gemini"]:
        raise RuntimeError("no_cloud_keys")
    raise RuntimeError("; ".join(errors) or "Cloud STT failed")


def _openai_whisper(wav_bytes: bytes, *, api_key: str, language: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=20.0)
    bio = io.BytesIO(wav_bytes)
    bio.name = "command.wav"
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=bio,
        language=language,
        response_format="text",
        temperature=0,
    )
    if isinstance(result, str):
        return " ".join(result.strip().split())
    text = getattr(result, "text", None) or str(result)
    return " ".join(text.strip().split())


def _gemini_audio(wav_bytes: bytes, *, api_key: str, language: str) -> str:
    # google-genai is preferred; fall back to google.generativeai
    prompt = (
        "Transcribe this short desktop-automation voice command. "
        f"Language hint: {language}. "
        "Return ONLY the spoken words, no quotes or commentary."
    )
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        audio_part = genai.types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav")
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, audio_part],
        )
        text = (getattr(response, "text", None) or "").strip()
        return " ".join(text.split())
    except Exception:
        import google.generativeai as genai_old

        genai_old.configure(api_key=api_key)
        model = genai_old.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            [
                prompt,
                {"mime_type": "audio/wav", "data": wav_bytes},
            ]
        )
        text = (getattr(response, "text", None) or "").strip()
        return " ".join(text.split())
