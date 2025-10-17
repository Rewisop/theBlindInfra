"""Utility helpers for marketwatch."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import requests
from dateutil import parser as date_parser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import load_settings


LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}
DEFAULT_LOG_LEVEL = LOG_LEVELS.get(os.getenv("DEEP_MARKET_LOG_LEVEL", "INFO").upper(), 20)


def log(level: str, message: str) -> None:
    lvl = LOG_LEVELS.get(level.upper(), 20)
    if lvl >= DEFAULT_LOG_LEVEL:
        now = iso_now()
        print(f"[{now}] {level.upper()}: {message}")


def iso_now() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def utc_now() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return date_parser.parse(str(value)).astimezone(timezone.utc)


def parse_money(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def make_session() -> requests.Session:
    settings = load_settings().http
    session = requests.Session()
    session.headers.update({"User-Agent": settings.user_agent})
    retry = Retry(
        total=settings.max_retries,
        read=settings.max_retries,
        connect=settings.max_retries,
        backoff_factor=settings.backoff_s,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.request = _wrap_request(session.request, settings.timeout_s)  # type: ignore
    return session


def _wrap_request(func, timeout: int):
    def wrapped(method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return func(method, url, **kwargs)

    return wrapped


def stable_hash(payload: Dict[str, Any]) -> str:
    dumped = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def normalize_gpu_name(name: str) -> str:
    mapping = {
        "a100_80g": "A100 80GB",
        "a100-80g": "A100 80GB",
        "a100": "A100",
        "rtx_3090": "RTX 3090",
        "rtx3090": "RTX 3090",
        "rtx_4090": "RTX 4090",
        "rtx4090": "RTX 4090",
        "h100": "H100",
        "l40s": "L40S",
    }
    key = name.strip().lower().replace(" ", "").replace("/", "")
    return mapping.get(key, name.strip())


def write_json_atomic(path: Path, obj: Any) -> bool:
    payload = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return _write_atomic(path, payload.encode("utf-8"))


def write_csv_atomic(path: Path, rows: Iterable[Dict[str, Any]]) -> bool:
    df = pd.DataFrame(list(rows))
    payload = df.to_csv(index=False) if not df.empty else ""
    return _write_atomic(path, payload.encode("utf-8"))


def append_jsonl(path: Path, line: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def write_text_atomic(path: Path, text: str) -> bool:
    return _write_atomic(path, text.encode("utf-8"))


def _write_atomic(path: Path, payload: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp", suffix=path.suffix)
    with os.fdopen(tmp_fd, "wb") as fh:
        fh.write(payload)
    if path.exists() and path.read_bytes() == payload:
        os.remove(tmp_path)
        return False
    os.replace(tmp_path, path)
    return True


__all__ = [
    "log",
    "iso_now",
    "utc_now",
    "parse_datetime",
    "parse_money",
    "parse_float",
    "make_session",
    "stable_hash",
    "normalize_gpu_name",
    "write_json_atomic",
    "write_csv_atomic",
    "append_jsonl",
    "write_text_atomic",
]
