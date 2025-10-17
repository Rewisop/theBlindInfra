from datetime import datetime, timedelta, timezone

from marketwatch.schema import merge_records, validate_and_normalize


def test_merge_prefers_cheapest_and_latest():
    now = datetime.now(tz=timezone.utc)
    records = [
        validate_and_normalize(
            {
                "gpu": "A100",
                "usd_per_hour": 2.0,
                "provider_id": "vast_ai",
                "sku": "a100",
                "region": "us",
                "on_demand": False,
                "spot": True,
                "source_url": "https://vast.ai",
                "fetched_at": now - timedelta(minutes=5),
            },
            now,
        ),
        validate_and_normalize(
            {
                "gpu": "A100",
                "usd_per_hour": 1.5,
                "provider_id": "vast_ai",
                "sku": "a100",
                "region": "us",
                "on_demand": False,
                "spot": True,
                "source_url": "https://vast.ai",
                "fetched_at": now,
            },
            now,
        ),
    ]
    merged = merge_records(records)
    assert len(merged) == 1
    assert merged[0].usd_per_hour == 1.5
    assert merged[0].fetched_at == records[1].fetched_at


