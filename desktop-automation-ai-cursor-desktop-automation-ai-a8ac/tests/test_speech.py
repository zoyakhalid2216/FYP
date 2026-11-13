"""Speech helpers tests (no mic required)."""

from src.speech.cloud_stt import resolve_api_keys, pcm_to_wav_bytes
from src.speech.recognizer import SpeechService


def test_resolve_api_keys_empty():
    keys = resolve_api_keys({"speech": {}})
    assert keys["openai"] == ""
    assert keys["gemini"] == ""


def test_pcm_to_wav_roundtrip_header():
    wav = pcm_to_wav_bytes(b"\x00\x00" * 160, sample_rate=16000)
    assert wav[:4] == b"RIFF"
    assert b"WAVE" in wav[:16]


def test_speech_service_always_available():
    svc = SpeechService({"speech": {"engine": "browser"}})
    assert svc.available is True


def test_listen_does_not_require_pyaudio(monkeypatch):
    svc = SpeechService({"speech": {"engine": "auto"}})
    svc._has_pyaudio = False

    def chrome_fail(*_a, **_k):
        raise RuntimeError("Allow microphone in Chrome")

    monkeypatch.setattr(svc, "_listen_browser", chrome_fail)
    try:
        svc.listen_once()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        msg = str(exc).lower()
        assert "no microphone library" not in msg
        assert "chrome" in msg or "edge" in msg or "execute" in msg


def test_dai_chrome_page_is_continuous():
    from src.speech.dai_chrome import _HTML

    assert "continuous = true" in _HTML
    assert "maxAlternatives = 5" in _HTML
    assert "wakeup" in _HTML.lower()


def test_speech_timing_config():
    svc = SpeechService({
        "speech": {
            "engine": "browser",
            "silence_seconds": 1.8,
            "max_phrase_seconds": 30.0,
            "start_timeout_seconds": 8.0,
            "pause_threshold": 1.8,
        }
    })
    assert svc.silence_seconds == 1.8
    assert svc.max_phrase_seconds == 30.0
    assert svc.start_timeout_seconds == 8.0
    assert svc.pause_threshold == 1.8


def test_offline_stt_mid_sentence_pause_does_not_cut():
    """Simulate speech -> 1.0s pause -> more speech -> silence. Must NOT end during 1.0s pause."""
    import time
    from src.speech.offline_stt import process_vosk_stream

    class FakeRecognizer:
        def __init__(self):
            self.start_t = time.perf_counter()
            self.step = 0

        def AcceptWaveform(self, data):
            return False

        def PartialResult(self):
            self.step += 1
            elapsed = time.perf_counter() - self.start_t
            # 0.0s - 0.2s: first part of sentence
            if elapsed < 0.2:
                return '{"partial": "open chrome"}'
            # 0.2s - 1.1s: mid-sentence pause (~0.9s of silence)
            elif elapsed < 1.1:
                return '{"partial": "open chrome"}'
            # 1.1s - 1.4s: second part of sentence
            elif elapsed < 1.4:
                return '{"partial": "open chrome and search weather"}'
            # 1.4s+: silence window begins
            else:
                return '{"partial": "open chrome and search weather"}'

        def FinalResult(self):
            return '{"text": "open chrome and search weather"}'

    def read_chunk():
        time.sleep(0.04)
        return b"\x00" * 4000

    rec = FakeRecognizer()
    # silence_seconds=1.2: 0.9s pause < 1.2s, so does not end during the pause.
    # At ~1.4s + 1.2s = ~2.6s, silence >= 1.2s, so it finishes.
    t0 = time.perf_counter()
    result = process_vosk_stream(
        read_chunk,
        rec,
        seconds=10.0,
        silence_seconds=0.7,
        start_timeout=5.0,
    )
    total_time = time.perf_counter() - t0

    assert "open chrome" in result
    assert "search weather" in result
    # Mid-sentence pause ended at 1.1s, second speech ended at 1.4s, so total_time >= 1.4s
    assert total_time >= 1.4, f"Finished too early ({total_time:.2f}s), mid-sentence pause cut it off!"


def test_offline_stt_start_timeout():
    """Verify start_timeout raises TimeoutError when no speech is detected."""
    import pytest
    from src.speech.offline_stt import process_vosk_stream

    class SilentRecognizer:
        def AcceptWaveform(self, data):
            return False

        def PartialResult(self):
            return '{"partial": ""}'

        def FinalResult(self):
            return '{"text": ""}'

    def silent_read():
        import time
        time.sleep(0.04)
        return b"\x00" * 4000

    with pytest.raises(TimeoutError):
        process_vosk_stream(
            silent_read,
            SilentRecognizer(),
            seconds=5.0,
            silence_seconds=0.5,
            start_timeout=0.25,
        )

