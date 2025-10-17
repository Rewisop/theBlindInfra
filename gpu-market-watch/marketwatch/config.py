"""Configuration loading utilities for GPU Market Watch."""
from __future__ import annotations

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
                extra={k: v for k, v in raw.items() if k not in {"id", "enabled", "module"}},
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


__all__ = [
    "load_settings",
    "load_providers",
    "load_dashboard",
    "Settings",
    "ProviderConfig",
    "DashboardConfig",
    "project_path",
]
