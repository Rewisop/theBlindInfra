"""Configuration loading utilities for GPU Market Watch."""
from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"

_FALLBACK_CONFIGS: Dict[str, Dict[str, Any]] = {
    "settings.yaml": {
        "http": {
            "timeout_s": 30,
            "max_retries": 2,
            "backoff_s": 2,
            "user_agent": "gpu-market-watch/1.0 (contact: email@example.com)",
        },
        "run": {"write_history": True, "fail_on_any_error": False},
    },
    "providers.yaml": {
        "providers": [
            {
                "id": "huggingface_endpoints",
                "enabled": True,
                "module": "marketwatch.providers.hf_endpoints:fetch",
                "notes": "Prefer official pricing JSON or docs API; otherwise skip rather than hard-scrape.",
            },
            {
                "id": "vast_ai",
                "enabled": True,
                "module": "marketwatch.providers.vast_ai:fetch",
                "base_url": "https://api.vast.ai/v0/bundles/public",
            },
            {
                "id": "runpod",
                "enabled": True,
                "module": "marketwatch.providers.runpod:fetch",
                "base_url": "https://api.runpod.io/pricing",
            },
            {
                "id": "lambda",
                "enabled": True,
                "module": "marketwatch.providers.lambda_labs:fetch",
            },
            {
                "id": "replicate",
                "enabled": True,
                "module": "marketwatch.providers.replicate:fetch",
            },
            {
                "id": "modal",
                "enabled": False,
                "module": "marketwatch.providers.modal:fetch",
            },
        ]
    },
    "dashboard.yaml": {
        "title": "GPU Market Watch",
        "intro": (
            "This dashboard summarizes the latest GPU pricing data collected from public infrastructure providers.\n"
            "Filter the table to explore offers and compare across vendors."
        ),
        "sections": [
            {
                "id": "summary",
                "heading": "Snapshot",
                "description": "Overall counts and min pricing per GPU family.",
            },
            {
                "id": "table",
                "heading": "Offers",
                "description": "Interactive table of normalized GPU prices.",
            },
            {
                "id": "chart",
                "heading": "Min $/hr by GPU",
                "description": "Bar chart showing the lowest observed price for each GPU family.",
            },
        ],
    },
}


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
    if yaml is not None:  # pragma: no cover - exercised when dependency present
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    text = path.read_text(encoding="utf-8")
    try:
        return _parse_simple_yaml(text)
    except Exception:
        fallback = _FALLBACK_CONFIGS.get(path.name)
        if fallback is None:
            raise
        return copy.deepcopy(fallback)


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    lines = [line.rstrip("\n") for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return {}
    parsed, index = _parse_yaml_block(lines, 0, 0)
    if index != len(lines):  # pragma: no cover - defensive
        raise ValueError("Unparsed YAML content remains")
    if not isinstance(parsed, dict):
        raise ValueError("Top-level YAML structure must be a mapping")
    return parsed


def _parse_yaml_block(lines: list[str], index: int, indent: int):
    mapping: Dict[str, Any] = {}
    items: list[Any] = []
    is_list: Optional[bool] = None
    while index < len(lines):
        line = lines[index]
        current_indent = len(line) - len(line.lstrip(" "))
        if current_indent < indent:
            break
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("- "):
            if is_list is False:
                raise ValueError("Mixed list and mapping in YAML block")
            is_list = True
            value_part = stripped[2:].strip()
            if value_part and ":" in value_part:
                key, rest = value_part.split(":", 1)
                key = key.strip().strip('"\'')
                rest = rest.strip()
                value: Any
                if rest == "|":
                    value, index = _collect_block_string(lines, index + 1, current_indent + 2)
                elif rest:
                    value = _parse_scalar(rest)
                    index += 1
                else:
                    index += 1
                    value, index = _parse_yaml_block(lines, index, current_indent + 2)
                nested, index = _parse_yaml_block(lines, index, current_indent + 2)
                if not isinstance(nested, dict):
                    nested = {}
                entry = {key: value}
                entry.update(nested)
                items.append(entry)
                continue
            if value_part:
                items.append(_parse_scalar(value_part))
                index += 1
                continue
            index += 1
            value, index = _parse_yaml_block(lines, index, current_indent + 2)
            items.append(value)
            continue

        if is_list:
            break

        if ":" not in stripped:
            raise ValueError(f"Invalid line: {line}")
        key, rest = stripped.split(":", 1)
        key = key.strip().strip('"\'')
        rest = rest.strip()
        if rest == "|":
            value, index = _collect_block_string(lines, index + 1, current_indent + 2)
            mapping[key] = value
            continue
        if rest:
            mapping[key] = _parse_scalar(rest)
            index += 1
            continue
        index += 1
        value, index = _parse_yaml_block(lines, index, current_indent + 2)
        mapping[key] = value

    if is_list:
        return items, index
    return mapping, index


def _collect_block_string(lines: list[str], index: int, indent: int):
    parts: list[str] = []
    while index < len(lines):
        line = lines[index]
        current_indent = len(line) - len(line.lstrip(" "))
        if current_indent < indent:
            break
        parts.append(line[indent:])
        index += 1
    return "\n".join(parts), index


def _parse_scalar(token: str) -> Any:
    lowered = token.lower()
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1]
    try:
        if "." in token:
            return float(token)
        return int(token)
    except ValueError:
        return token


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
