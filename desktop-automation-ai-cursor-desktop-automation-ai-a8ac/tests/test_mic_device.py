from src.speech.mic_device import friendly_mic_error, list_input_candidates


class _FakeApi(dict):
    pass


class _FakeSD:
    def __init__(self, devices, apis):
        self._devices = devices
        self._apis = apis

    def query_devices(self):
        return self._devices

    def query_hostapis(self, index):
        return self._apis[index]


def test_skips_asio_and_prefers_wasapi():
    devices = [
        {"name": "ASIO Mic", "hostapi": 0, "max_input_channels": 1, "default_samplerate": 48000},
        {"name": "Laptop Mic", "hostapi": 1, "max_input_channels": 1, "default_samplerate": 44100},
        {"name": "Speakers", "hostapi": 1, "max_input_channels": 0, "default_samplerate": 44100},
    ]
    apis = [
        {"name": "ASIO"},
        {"name": "Windows WASAPI"},
    ]
    ranked = list_input_candidates(_FakeSD(devices, apis))
    assert ranked
    assert ranked[0]["name"] == "Laptop Mic"
    assert all("ASIO" not in (r["host"] or "") for r in ranked)


def test_friendly_driver_error():
    msg = friendly_mic_error(RuntimeError("Unanticipated host error [PaErrorCode -9999]"))
    assert "Privacy" in msg
    assert "Microphone" in msg
