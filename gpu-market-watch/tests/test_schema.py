from datetime import datetime, timezone

from marketwatch.schema import GpuPrice, merge_records, validate_and_normalize


def test_validate_and_normalize_generates_hash():
    now = datetime.now(tz=timezone.utc)
    record = {
        "gpu": "a100_80g",
        "usd_per_hour": 1.23,
        "provider_id": "test",
        "sku": "a100",
        "region": "us-east",
        "on_demand": True,
        "spot": False,
        "source_url": "https://example.com",
        "fetched_at": now,
    }
    normalized = validate_and_normalize(record, now)
    assert normalized.gpu == "A100 80GB"
    assert len(normalized.content_hash) == 64
    dumped = normalized.model_dump()
    assert dumped["generated_at"].tzinfo is not None


