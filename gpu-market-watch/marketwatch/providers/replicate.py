"""Replicate pricing provider."""
from __future__ import annotations

from datetime import datetime
from typing import List

from ..schema import GpuPrice, validate_and_normalize
from ..util import load_json_snapshot, log, parse_float

DEFAULT_ENDPOINT = "https://api.replicate.com/v1/pricing"


def fetch(session, cfg, now: datetime) -> List[GpuPrice]:
    url = cfg.extra.get("base_url", DEFAULT_ENDPOINT)
    headers = {}
    if token := cfg.extra.get("token"):
        headers["Authorization"] = f"Token {token}"
    payload = None
    try:
        response = session.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # pragma: no cover - defensive
        log("WARN", f"replicate: failed to fetch pricing ({exc})")
        payload = load_json_snapshot(cfg.id)
        if payload is None:
            return []
        log("INFO", "replicate: using bundled snapshot data")

    records = payload.get("prices") or payload.get("hardware") or []
    results: List[GpuPrice] = []
    for item in records:
        gpu_name = item.get("gpu") or item.get("name")
        per_minute = parse_float(item.get("usd_per_minute") or item.get("price_per_minute"))
        per_hour = parse_float(item.get("usd_per_hour"))
        if per_hour is None and per_minute is not None:
            per_hour = per_minute * 60.0
        if not gpu_name or per_hour is None:
            continue
        record = {
            "gpu": gpu_name,
            "usd_per_hour": per_hour,
            "provider_id": cfg.id,
            "sku": item.get("hardware"),
            "region": item.get("region"),
            "on_demand": True,
            "spot": False,
            "source_url": url,
            "fetched_at": now,
        }
        results.append(validate_and_normalize(record, now))
    return results


__all__ = ["fetch"]
