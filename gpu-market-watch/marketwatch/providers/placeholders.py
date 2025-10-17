"""Placeholder modules for future providers."""
from __future__ import annotations

from datetime import datetime
from typing import List

from ..schema import GpuPrice


def fetch(session, cfg, now: datetime) -> List[GpuPrice]:  # pragma: no cover - placeholder
    return []


__all__ = ["fetch"]
