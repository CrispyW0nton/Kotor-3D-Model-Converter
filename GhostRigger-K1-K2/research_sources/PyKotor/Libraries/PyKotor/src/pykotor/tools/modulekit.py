"""ModuleKit helpers (functions only).

Classes live in `pykotor.common.modulekit`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pykotor.common.modulekit import ModuleKit, ModuleKitManager
    from pykotor.extract.installation import Installation


def _module_kit_manager(installation: Installation) -> ModuleKitManager:
    from pykotor.common.modulekit import ModuleKitManager

    return ModuleKitManager(installation)


def get_module_kit_manager(installation: Installation) -> "ModuleKitManager":
    """Return a `ModuleKitManager` for an installation (convenience wrapper)."""
    return _module_kit_manager(installation)


def get_module_kit(installation: Installation, module_root: str) -> "ModuleKit":
    """Convenience helper for one-off implicit-kit access."""
    return _module_kit_manager(installation).get_module_kit(module_root)
