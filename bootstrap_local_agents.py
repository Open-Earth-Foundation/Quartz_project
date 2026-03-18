from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

LOCAL_PACKAGE_ALIAS = "quartz_agents"


def load_local_agents_package() -> ModuleType:
    existing = sys.modules.get(LOCAL_PACKAGE_ALIAS)
    if existing is not None:
        return existing

    package_dir = Path(__file__).resolve().parent / "agents"
    init_path = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        LOCAL_PACKAGE_ALIAS,
        init_path,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to create import spec for {init_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[LOCAL_PACKAGE_ALIAS] = module
    spec.loader.exec_module(module)
    return module

