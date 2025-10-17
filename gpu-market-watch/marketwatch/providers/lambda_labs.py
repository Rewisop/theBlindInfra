"""Lambda Labs pricing provider."""
from __future__ import annotations

from datetime import datetime
from typing import List

from ..schema import GpuPrice, validate_and_normalize
from ..util import load_json_snapshot, log, parse_float

DEFAULT_ENDPOINT = "https://cloud.lambdalabs.com/api/v1/instance-types"


def fetch(session, cfg, now: datetime) -> List[GpuPrice]:
    url = cfg.extra.get("base_url", DEFAULT_ENDPOINT)
    payload = None
    try:
        response = session.get(url)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        log("WARN", f"lambda: failed to fetch pricing ({exc})")
        payload = load_json_snapshot(cfg.id)
        if payload is None:
            return []
        log("INFO", "lambda: using bundled snapshot data")

    instances = payload.get("data") or payload.get("instance_types") or {}
    if isinstance(instances, dict):
        items = instances.values()
    else:
        items = instances

    results: List[GpuPrice] = []
    for item in items:
        gpu_name = item.get("gpu_type") or item.get("name")
        hourly_price = (
            parse_float(item.get("price_cents_per_hour"))
            if item.get("price_cents_per_hour") is not None
            else parse_float(item.get("usd_per_hour") or item.get("price_per_hour"))
        )
        if hourly_price is not None and item.get("price_cents_per_hour") is not None:
            hourly_price = hourly_price / 100.0
        if not gpu_name or hourly_price is None:
            continue
        record = {
            "gpu": gpu_name,
            "usd_per_hour": hourly_price,
            "provider_id": cfg.id,
            "sku": item.get("instance_type_name") or item.get("slug"),
            "region": item.get("region"),
            "on_demand": True,
            "spot": False,
            "source_url": url,
            "fetched_at": now,
        }
        results.append(validate_and_normalize(record, now))
    return results


__all__ = ["fetch"]
