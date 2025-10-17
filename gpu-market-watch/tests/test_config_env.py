"""Tests for provider environment overrides."""

from __future__ import annotations

from textwrap import dedent

from marketwatch.config import load_providers


def _write_provider_cfg(tmp_path, body: str):
    cfg_path = tmp_path / "providers.yaml"
    cfg_path.write_text(dedent(body))
    return cfg_path


def test_env_prefix_overrides_extra(monkeypatch, tmp_path):
    cfg_path = _write_provider_cfg(
        tmp_path,
        """
        providers:
          - id: "replicate"
            enabled: true
            module: "marketwatch.providers.replicate:fetch"
            base_url: "https://example.com"
        """,
    )
    monkeypatch.setenv("GPU_MARKET_REPLICATE_TOKEN", "from_prefix")
    load_providers.cache_clear()
    providers = load_providers(cfg_path)
    replicate = next(p for p in providers if p.id == "replicate")
    assert replicate.extra["token"] == "from_prefix"
    assert replicate.extra["base_url"] == "https://example.com"


def test_known_env_shortcuts_apply(monkeypatch, tmp_path):
    cfg_path = _write_provider_cfg(
        tmp_path,
        """
        providers:
          - id: "runpod"
            enabled: true
            module: "marketwatch.providers.runpod:fetch"
        """,
    )
    monkeypatch.delenv("GPU_MARKET_RUNPOD_TOKEN", raising=False)
    monkeypatch.setenv("RUNPOD_API_KEY", "secret-key")
    load_providers.cache_clear()
    providers = load_providers(cfg_path)
    runpod = next(p for p in providers if p.id == "runpod")
    assert runpod.extra["token"] == "secret-key"
