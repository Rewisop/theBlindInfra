"""Configuration loading utilities for GPU Market Watch."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


@dataclass
class HttpSettings:
    timeout_s: int
    max_retries: int
    backoff_s: float
    user_agent: str


@dataclass
class RunSettings:
    write_history: bool
    fail_on_any_error: bool


@dataclass
class Settings:
    http: HttpSettings
    run: RunSettings


@dataclass
class ProviderConfig:
    id: str
    enabled: bool
    module: str
    extra: Dict[str, Any]


_DEFAULT_ENV_OVERRIDES: Dict[str, Dict[str, tuple[str, ...]]] = {
    "runpod": {"token": ("RUNPOD_API_KEY", "RUNPOD_API_TOKEN")},
    "replicate": {"token": ("REPLICATE_API_TOKEN", "REPLICATE_TOKEN")},
    "huggingface_endpoints": {
        "token": (
            "HF_API_KEY",
            "HF_API_TOKEN",
            "HUGGINGFACE_API_KEY",
            "HUGGINGFACE_API_TOKEN",
        )
    },
}

_ENV_SANITIZE = re.compile(r"[^A-Z0-9]+")


@dataclass
class DashboardConfig:
    title: str
    intro: str
    sections: List[Dict[str, Any]]


@lru_cache(maxsize=1)
def load_settings(path: Optional[Path] = None) -> Settings:
    """Load runtime and HTTP settings from YAML."""
    cfg_path = path or CONFIG_DIR / "settings.yaml"
    data = _load_yaml(cfg_path)
    http = data.get("http", {})
    run = data.get("run", {})
    http_settings = HttpSettings(
        timeout_s=int(http.get("timeout_s", 30)),
        max_retries=int(http.get("max_retries", 2)),
        backoff_s=float(http.get("backoff_s", 2)),
        user_agent=str(http.get("user_agent", "gpu-market-watch/1.0")),
    )
    run_settings = RunSettings(
        write_history=bool(run.get("write_history", True)),
        fail_on_any_error=bool(run.get("fail_on_any_error", False)),
    )
    return Settings(http=http_settings, run=run_settings)


@lru_cache(maxsize=1)
def load_providers(path: Optional[Path] = None) -> List[ProviderConfig]:
    cfg_path = path or CONFIG_DIR / "providers.yaml"
    data = _load_yaml(cfg_path)
    providers: List[ProviderConfig] = []
    for raw in data.get("providers", []):
        providers.append(
            ProviderConfig(
                id=str(raw.get("id")),
                enabled=bool(raw.get("enabled", True)),
                module=str(raw.get("module")),
                extra=_merge_provider_env(
                    str(raw.get("id")),
                    {k: v for k, v in raw.items() if k not in {"id", "enabled", "module"}},
                ),
            )
        )
    return providers


@lru_cache(maxsize=1)
def load_dashboard(path: Optional[Path] = None) -> DashboardConfig:
    cfg_path = path or CONFIG_DIR / "dashboard.yaml"
    data = _load_yaml(cfg_path)
    return DashboardConfig(
        title=str(data.get("title", "GPU Market Watch")),
        intro=str(data.get("intro", "")),
        sections=list(data.get("sections", [])),
    )


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def project_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def _merge_provider_env(provider_id: str, extra: Dict[str, Any]) -> Dict[str, Any]:
    if not provider_id:
        return extra

    merged = dict(extra)
    normalized_id = _normalize_env_component(provider_id)
    prefix = f"GPU_MARKET_{normalized_id}_"
    for env_name, env_value in os.environ.items():
        if env_name.startswith(prefix):
            key = _normalize_env_key(env_name[len(prefix) :])
            if key:
                merged[key] = env_value

    overrides = _DEFAULT_ENV_OVERRIDES.get(provider_id.lower()) or {}
    for target_key, candidates in overrides.items():
        for env_name in candidates:
            value = os.getenv(env_name)
            if value:
                merged[target_key] = value
                break

    return merged


def _normalize_env_component(value: str) -> str:
    return _ENV_SANITIZE.sub("_", value.upper()).strip("_")


def _normalize_env_key(value: str) -> str:
    cleaned = _normalize_env_component(value)
    return cleaned.lower()


__all__ = [
    "load_settings",
    "load_providers",
    "load_dashboard",
    "Settings",
    "ProviderConfig",
    "DashboardConfig",
    "project_path",
]
