"""Central Qt GUI library facade.

The implementation modules live in category folders under ``src.gui``. Import
through this module when code outside those folders needs GUI pieces, for
example ``src.gui.qt_lib.panels.qt_common_panels``.
"""

from __future__ import annotations

from importlib import import_module, reload
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import spec_from_loader
from types import ModuleType
from typing import Iterable
import sys


_GROUPS: dict[str, tuple[str, ...]] = {
    "assets": (
        "qt_icon_manager",
        "qt_matrix_background",
        "qt_theme",
    ),
    "dialogs": (
        "qt_dialogs",
        "qt_export_dialog",
        "qt_settings_dialog",
    ),
    "panels": (
        "qt_animation_panel",
        "qt_bottom_strip",
        "qt_character_builder_panel",
        "qt_common_panels",
        "qt_diagnostics_panel",
        "qt_inspector_panel",
        "qt_library_panel",
        "qt_log_panel",
        "qt_modular_panel",
        "qt_normal_map_panel",
        "qt_properties_panel",
        "qt_resource_panel",
        "qt_rig_panel",
        "qt_texture_panel",
        "qt_workflow_rail",
    ),
    "rendering": (
        "accel",
        "gpu_renderer",
        "qt_accel",
        "qt_gpu_renderer",
        "viewport_core",
        "viewport_navigation",
    ),
    "textures": (
        "qt_tex_atlas",
        "qt_tpc_render_utils",
        "tex_atlas",
        "tpc_render_utils",
    ),
    "viewports": (
        "qt_uv_viewer",
        "qt_viewport",
    ),
    "windows": (
        "qt_blueprint_editor",
        "qt_character_builder_window",
        "qt_main_window",
        "qt_retarget_window",
        "qt_unreal_animator",
    ),
}

_ALIASES: dict[str, str] = {}


class _AliasLoader(Loader):
    def __init__(self, target: str) -> None:
        self.target = target

    def create_module(self, spec: ModuleSpec) -> ModuleType | None:
        return sys.modules.get(spec.name)

    def exec_module(self, module: ModuleType) -> None:
        loaded = import_module(self.target)
        if getattr(module, "_loaded", None) is not None:
            loaded = reload(loaded)
        module.__dict__["_loaded"] = loaded
        module.__dict__["_target"] = self.target
        for name, value in loaded.__dict__.items():
            if name not in {"__name__", "__package__", "__spec__", "__loader__"}:
                module.__dict__[name] = value


class _AliasFinder(MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: object | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        alias_target = _ALIASES.get(fullname)
        if alias_target is None:
            return None
        return spec_from_loader(fullname, _AliasLoader(alias_target))


class _LazyModule(ModuleType):
    """Module alias that imports its grouped implementation on first use."""

    def __init__(self, alias: str, target: str) -> None:
        super().__init__(alias)
        self.__dict__["_target"] = target
        self.__dict__["_loaded"] = None

    def _load(self) -> ModuleType:
        loaded = self.__dict__.get("_loaded")
        if loaded is None:
            loaded = import_module(self.__dict__["_target"])
            self.__dict__["_loaded"] = loaded
            for name, value in loaded.__dict__.items():
                if name not in {"__name__", "__package__", "__spec__", "__loader__"}:
                    self.__dict__[name] = value
        return loaded

    def __getattr__(self, name: str):
        return getattr(self._load(), name)

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(dir(self._load())))


def _make_package(name: str) -> ModuleType:
    package = ModuleType(name)
    package.__package__ = name
    package.__path__ = []  # type: ignore[attr-defined]
    return package


def _register_alias(alias: str, target: str) -> _LazyModule:
    _ALIASES[alias] = target
    module = _LazyModule(alias, target)
    module.__package__ = alias.rpartition(".")[0]
    module.__loader__ = _AliasLoader(target)
    module.__spec__ = spec_from_loader(alias, module.__loader__)
    sys.modules[alias] = module
    return module


def _register_group(group: str, modules: Iterable[str]) -> ModuleType:
    package_name = f"{__name__}.{group}"
    package = _make_package(package_name)
    sys.modules[package_name] = package
    globals()[group] = package

    for module_name in modules:
        alias = f"{package_name}.{module_name}"
        target = f"src.gui.{group}.{module_name}"
        module = _register_alias(alias, target)
        setattr(package, module_name, module)
        globals().setdefault(module_name, module)

    package.__all__ = list(modules)  # type: ignore[attr-defined]
    return package


__path__ = []  # type: ignore[var-annotated]

if not any(isinstance(_finder, _AliasFinder) for _finder in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

for _group, _modules in _GROUPS.items():
    _register_group(_group, _modules)

__all__ = [*_GROUPS.keys()]
