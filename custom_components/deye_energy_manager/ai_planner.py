"""Compatibility entry point for the deterministic 0.7.7 Optimizer Core."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

try:
    from .optimizer_core import (  # type: ignore
        ALGORITHM_VERSION,
        build_energy_plan,
        build_plan_bundle,
        simulate_alternative,
        snapshot_id,
    )
except (ImportError, ValueError):
    # Unit tests load this file directly, outside a package.  Loading the
    # sibling by path keeps the exact same implementation in both contexts.
    module_path = Path(__file__).with_name("optimizer_core.py")
    module_name = "deye_energy_manager_optimizer_core"
    module = sys.modules.get(module_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load optimizer core from {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    ALGORITHM_VERSION = module.ALGORITHM_VERSION
    build_energy_plan = module.build_energy_plan
    build_plan_bundle = module.build_plan_bundle
    simulate_alternative = module.simulate_alternative
    snapshot_id = module.snapshot_id


__all__ = [
    "ALGORITHM_VERSION",
    "build_energy_plan",
    "build_plan_bundle",
    "simulate_alternative",
    "snapshot_id",
]
