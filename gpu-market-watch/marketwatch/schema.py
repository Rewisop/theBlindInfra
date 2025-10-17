"""Data schema definitions for normalized GPU pricing."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from .util import normalize_gpu_name, stable_hash


def _to_utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class GpuPrice:
    """Canonical GPU price record."""

    gpu: str
    usd_per_hour: float
    provider_id: str
    sku: Optional[str] = None
    region: Optional[str] = None
    on_demand: Optional[bool] = None
    spot: Optional[bool] = None
    source_url: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "gpu", normalize_gpu_name(self.gpu))
        usd_per_hour = float(self.usd_per_hour)
        if usd_per_hour < 0:
            raise ValueError("usd_per_hour must be non-negative")
        object.__setattr__(self, "usd_per_hour", usd_per_hour)
        object.__setattr__(self, "fetched_at", _to_utc(self.fetched_at))
        object.__setattr__(self, "generated_at", _to_utc(self.generated_at))
        if self.on_demand is not None:
            object.__setattr__(self, "on_demand", bool(self.on_demand))
        if self.spot is not None:
            object.__setattr__(self, "spot", bool(self.spot))
        object.__setattr__(self, "source_url", str(self.source_url))
        object.__setattr__(self, "content_hash", str(self.content_hash))

    def model_dump(self, mode: str = "python") -> Dict[str, object]:
        payload: Dict[str, object] = {
            "gpu": self.gpu,
            "usd_per_hour": self.usd_per_hour,
            "provider_id": self.provider_id,
            "sku": self.sku,
            "region": self.region,
            "on_demand": self.on_demand,
            "spot": self.spot,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at,
            "generated_at": self.generated_at,
            "content_hash": self.content_hash,
        }
        if mode == "json":
            payload = {
                key: (value.isoformat() if isinstance(value, datetime) else value)
                for key, value in payload.items()
            }
        return payload


def validate_and_normalize(record: dict, generated_at: datetime) -> GpuPrice:
    """Validate a raw record dict and compute derived fields."""
    record = {**record}
    record.setdefault("generated_at", generated_at)
    record.setdefault("source_url", "")
    record["gpu"] = normalize_gpu_name(record.get("gpu", ""))
    record["usd_per_hour"] = float(record.get("usd_per_hour", 0))
    if record["usd_per_hour"] < 0:
        raise ValueError("usd_per_hour must be non-negative")
    record["fetched_at"] = _to_utc(record.get("fetched_at", generated_at))
    record["generated_at"] = _to_utc(record.get("generated_at", generated_at))
    record["content_hash"] = stable_hash(
        {
            "provider_id": record.get("provider_id"),
            "gpu": record.get("gpu"),
            "usd_per_hour": round(float(record.get("usd_per_hour", 0)), 4),
            "region": record.get("region"),
            "sku": record.get("sku"),
            "on_demand": bool(record.get("on_demand")) if record.get("on_demand") is not None else None,
            "spot": bool(record.get("spot")) if record.get("spot") is not None else None,
        }
    )
    return GpuPrice(**record)


def merge_records(records: Iterable[GpuPrice]) -> List[GpuPrice]:
    """Merge duplicate offers, keeping the cheapest price and most recent fetch time."""
    merged: dict = {}
    for rec in records:
        key = (
            rec.provider_id,
            rec.gpu,
            rec.region,
            rec.sku,
            rec.on_demand,
            rec.spot,
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = rec
            continue
        if rec.usd_per_hour < existing.usd_per_hour:
            merged[key] = rec
            continue
        if rec.usd_per_hour == existing.usd_per_hour and rec.fetched_at > existing.fetched_at:
            merged[key] = rec
    return sorted(merged.values(), key=lambda r: (r.provider_id, r.gpu, r.region or "", r.sku or ""))


__all__ = ["GpuPrice", "validate_and_normalize", "merge_records"]
