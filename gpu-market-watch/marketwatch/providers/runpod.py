"""RunPod pricing provider."""
from __future__ import annotations

from datetime import datetime
from typing import List

from ..schema import GpuPrice, validate_and_normalize
from ..util import log, parse_float


def fetch(session, cfg, now: datetime) -> List[GpuPrice]:
    url = cfg.extra.get("base_url", "https://api.runpod.io/pricing")
    try:
        response = session.get(url)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        log("WARN", f"runpod: failed to fetch pricing ({exc})")
        return []

    records = payload.get("data") or payload.get("pricings") or payload
    if isinstance(records, dict):
        records = records.get("gpus") or []

    results: List[GpuPrice] = []
    for item in records:
        gpu_name = item.get("gpu") or item.get("name")
        price = parse_float(item.get("usd_per_hour") or item.get("price_per_hour") or item.get("hourly"))
        if not gpu_name or price is None:
            continue
        record = {
            "gpu": gpu_name,
            "usd_per_hour": price,
            "provider_id": cfg.id,
            "sku": item.get("instance_type") or item.get("sku"),
            "region": item.get("region"),
            "on_demand": True,
            "spot": item.get("spot", False),
            "source_url": url,
            "fetched_at": now,
        }
        results.append(validate_and_normalize(record, now))
    return results


__all__ = ["fetch"]
