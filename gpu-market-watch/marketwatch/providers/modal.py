"""Modal Labs pricing provider."""
from __future__ import annotations

from datetime import datetime
from typing import List

from bs4 import BeautifulSoup

from ..schema import GpuPrice, validate_and_normalize
from ..util import log, parse_money

DEFAULT_URL = "https://modal.com/pricing"


def fetch(session, cfg, now: datetime) -> List[GpuPrice]:
    url = cfg.extra.get("base_url", DEFAULT_URL)
    try:
        response = session.get(url)
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - defensive
        log("WARN", f"modal: failed to fetch pricing ({exc})")
        return []

    soup = BeautifulSoup(response.text, "lxml")
    table = soup.find("table")
    if not table:
        log("WARN", "modal: pricing table not found, skipping")
        return []

    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    results: List[GpuPrice] = []
    for row in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not cells or len(cells) != len(headers):
            continue
        data = dict(zip(headers, cells))
        gpu_name = data.get("gpu") or data.get("hardware")
        price = parse_money(data.get("price") or data.get("$/hr") or data.get("usd/hr"))
        if not gpu_name or price is None:
            continue
        record = {
            "gpu": gpu_name,
            "usd_per_hour": price,
            "provider_id": cfg.id,
            "sku": data.get("plan") or data.get("sku"),
            "region": data.get("region"),
            "on_demand": True,
            "spot": False,
            "source_url": url,
            "fetched_at": now,
        }
        results.append(validate_and_normalize(record, now))
    return results


__all__ = ["fetch"]
