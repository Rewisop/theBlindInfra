"""Data schema definitions for normalized GPU pricing."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional

from pydantic import BaseModel, Field, field_validator

from .util import normalize_gpu_name, stable_hash


class GpuPrice(BaseModel):
    """Canonical GPU price record."""

    gpu: str
    usd_per_hour: float = Field(ge=0)
    provider_id: str
    sku: Optional[str] = None
    region: Optional[str] = None
    on_demand: Optional[bool] = None
    spot: Optional[bool] = None
    source_url: str
    fetched_at: datetime
    generated_at: datetime
    content_hash: str

    model_config = {
        "frozen": True,
        "json_encoders": {datetime: lambda dt: dt.replace(tzinfo=timezone.utc).isoformat()},
    }

    @field_validator("fetched_at", "generated_at", mode="before")
    @classmethod
    def _ensure_datetime(cls, value: datetime) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return datetime.fromisoformat(str(value)).astimezone(timezone.utc)

    @field_validator("gpu", mode="before")
    @classmethod
    def _normalize_gpu(cls, value: str) -> str:
        return normalize_gpu_name(value)


def validate_and_normalize(record: dict, generated_at: datetime) -> GpuPrice:
    """Validate a raw record dict and compute derived fields."""
    record = {**record}
    record.setdefault("generated_at", generated_at)
    record["gpu"] = normalize_gpu_name(record.get("gpu", ""))
    record["content_hash"] = stable_hash(
        {
            "provider_id": record.get("provider_id"),
            "gpu": record.get("gpu"),
            "usd_per_hour": round(float(record.get("usd_per_hour", 0)), 4),
            "region": record.get("region"),
            "sku": record.get("sku"),
            "on_demand": record.get("on_demand"),
            "spot": record.get("spot"),
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
