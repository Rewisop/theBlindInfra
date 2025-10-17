"""Utility helpers for marketwatch."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

try:  # pragma: no cover - optional dependency
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    import requests  # type: ignore
    from requests.adapters import HTTPAdapter  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    requests = None  # type: ignore[assignment]
    HTTPAdapter = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from urllib3.util.retry import Retry  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Retry = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from dateutil import parser as date_parser  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    date_parser = None  # type: ignore[assignment]

from .config import load_settings, project_path


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
    if date_parser is not None:
        return date_parser.parse(str(value)).astimezone(timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


class _OfflineSession:
    def __init__(self, reason: str):
        self.reason = reason
        self.headers: Dict[str, str] = {}

    def get(self, url: str, **kwargs):  # pragma: no cover - simple fallback
        raise RuntimeError(self.reason)

    def request(self, method: str, url: str, **kwargs):  # pragma: no cover - simple fallback
        raise RuntimeError(self.reason)


def make_session():
    settings = load_settings().http
    if requests is None or HTTPAdapter is None or Retry is None:
        return _OfflineSession("requests library unavailable")

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
    session.request = _wrap_request(session.request, settings.timeout_s)  # type: ignore[attr-defined]
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
    data = list(rows)
    if pd is not None:
        df = pd.DataFrame(data)
        payload = df.to_csv(index=False) if not df.empty else ""
    else:
        if not data:
            payload = ""
        else:
            buffer = io.StringIO()
            fieldnames = sorted({key for row in data for key in row.keys()})
            writer = csv.DictWriter(buffer, fieldnames=fieldnames)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
            payload = buffer.getvalue()
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


def load_json_snapshot(provider_id: str) -> Optional[Any]:
    """Load a bundled JSON snapshot for a provider.

    Parameters
    ----------
    provider_id:
        Identifier for the provider, used to locate ``config/snapshots/<id>.json``.

    Returns
    -------
    Optional[Any]
        Parsed JSON object if the snapshot exists, otherwise ``None``.
    """

    if not provider_id:
        return None

    snapshot_path = project_path("config", "snapshots", f"{provider_id}.json")
    if not snapshot_path.exists():
        return None
    try:
        with snapshot_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # pragma: no cover - defensive
        log("WARN", f"{provider_id}: failed to load bundled snapshot ({exc})")
        return None


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
    "load_json_snapshot",
]
