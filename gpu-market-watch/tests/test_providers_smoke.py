from datetime import datetime, timezone

from marketwatch.config import ProviderConfig
from marketwatch.providers import runpod, vast_ai
from marketwatch.schema import GpuPrice


class DummyResponse:
    def __init__(self, data, text=""):
        self._data = data
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class DummySession:
    def __init__(self, data, text=""):
        self.data = data
        self.text = text

    def get(self, url, headers=None):
        return DummyResponse(self.data, self.text)


def test_runpod_fetch_normalizes_records():
    now = datetime.now(tz=timezone.utc)
    session = DummySession(
        {
            "data": [
                {
                    "gpu": "A100",
                    "usd_per_hour": 2.5,
                    "instance_type": "A100",
                    "region": "us-west",
                }
            ]
        }
    )
    cfg = ProviderConfig(id="runpod", enabled=True, module="marketwatch.providers.runpod:fetch", extra={"base_url": "http://mock"})
    results = runpod.fetch(session, cfg, now)
    assert len(results) == 1
    assert isinstance(results[0], GpuPrice)
    assert results[0].provider_id == "runpod"


def test_vast_ai_fetch_handles_missing_fields():
    now = datetime.now(tz=timezone.utc)
    session = DummySession({"offers": [{"gpu_name": "RTX 3090", "dph_total": 0.5}]})
    cfg = ProviderConfig(id="vast_ai", enabled=True, module="marketwatch.providers.vast_ai:fetch", extra={"base_url": "http://mock"})
    results = vast_ai.fetch(session, cfg, now)
    assert len(results) == 1
    assert results[0].spot is True


