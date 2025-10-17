"""Hugging Face Inference Endpoints pricing fetcher."""
from __future__ import annotations

from typing import List

from ..schema import GpuPrice, validate_and_normalize
from ..util import log


def fetch(session, cfg, now) -> List[GpuPrice]:
    """Return pricing records if a public feed is available."""
    log("INFO", "huggingface_endpoints: skipped (no public pricing feed)")
    return []


__all__ = ["fetch"]
