"""Vast.ai pricing provider."""
from __future__ import annotations

from datetime import datetime
from typing import List

from ..schema import GpuPrice, validate_and_normalize
from ..util import log, parse_float


def fetch(session, cfg, now: datetime) -> List[GpuPrice]:
    url = cfg.extra.get("base_url", "https://api.vast.ai/v0/bundles/public")
    try:
        response = session.get(url)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        log("WARN", f"vast_ai: failed to fetch pricing ({exc})")
        return []

    offers = payload.get("offers") or payload.get("data") or []
    results: List[GpuPrice] = []
    for offer in offers:
        gpu_name = offer.get("gpu_name") or offer.get("gpu_type") or offer.get("gpu")
        price = parse_float(offer.get("dph_total") or offer.get("price_per_gpu_hour") or offer.get("total_hourly_cost"))
        if not gpu_name or price is None:
            continue
        record = {
            "gpu": gpu_name,
            "usd_per_hour": price,
            "provider_id": cfg.id,
            "sku": offer.get("id") or offer.get("instance_id"),
            "region": offer.get("region") or offer.get("geolocation"),
            "on_demand": False,
            "spot": True,
            "source_url": url,
            "fetched_at": now,
        }
        results.append(validate_and_normalize(record, now))
    return results


__all__ = ["fetch"]
