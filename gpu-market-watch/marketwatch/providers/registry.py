"""Dynamic loader for provider fetch functions."""
from __future__ import annotations

import importlib
from typing import Callable, List

from ..config import ProviderConfig, load_providers

FetchFunc = Callable[..., list]


def get_enabled_providers() -> List[tuple[ProviderConfig, FetchFunc]]:
    providers = []
    for cfg in load_providers():
        if not cfg.enabled:
            continue
        func = load_callable(cfg.module)
        providers.append((cfg, func))
    return providers


def load_callable(path: str) -> FetchFunc:
    module_name, func_name = path.split(":", 1)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    return func


__all__ = ["get_enabled_providers", "load_callable"]
