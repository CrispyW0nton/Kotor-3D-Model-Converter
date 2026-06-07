"""Central backend library facade for GhostRigger core systems.

Implementation modules live in subsystem folders under ``src.core``. Import
backend owners directly in new implementation code. This module remains as a
compatibility facade for legacy public paths and stable grouped symbols such as
``SceneManager`` and ``ResourceManager``.
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
    "animation": (
        "animation_engine",
        "animation_library",
        "gpu_skinning",
    ),
    "animation_retargeting": (
        "retargeter",
        "skeleton_template_picker",
    ),
    "assets": (
        "asset_preview",
        "override_layer",
        "resource_manager",
    ),
    "camera": (
        "arcball_camera",
        "camera_controller",
        "camera_manager",
        "camera_model",
        "camera_picker",
        "camera_presets",
        "camera_render_settings",
        "camera_rig",
        "camera_selection",
        "camera_target",
        "camera_viewport_adapter",
        "render_manifest",
        "render_output",
    ),
    "characters": (
        "character_builder",
        "character_export_preflight",
        "creature_appearance",
        "head_workflow",
        "headless_body_workflow",
        "native_skeleton",
    ),
    "diagnostics": (
        "diagnostics",
        "module_reference_safety",
        "validation_service",
    ),
    "export": (
        "gltf_importer",
        "unity_export_bridge",
        "unity_import_validator",
    ),
    "game": (
        "game_library_ext",
        "import_normalisation",
        "kotor_install",
        "kotor_loader",
        "pykotor_bridge",
        "pykotor_mdl_io_fix",
    ),
    "geometry": (
        "map_snap_tools",
        "model_data",
        "vertex_space",
    ),
    "graphics": (
        "tex_atlas",
        "tpc",
        "tpc_render_utils",
        "txi",
    ),
    "gizmo": (
        "gizmo_draw_data",
        "gizmo_mode",
        "gizmo_picker",
        "gizmo_renderer",
        "transform_controller",
        "transform_gizmo",
    ),
    "lighting": (
        "aurora_light_adapter",
        "light_export_bridge",
        "light_gizmo_renderer",
        "light_grouping",
        "light_manager",
        "light_model",
        "light_picker",
        "light_selection",
        "light_types",
        "lightmap_baker",
        "lightmap_bake_job",
        "lightmap_bake_settings",
        "lightmap_compare",
        "lightmap_controller",
        "lightmap_denoiser",
        "lightmap_export_bridge",
        "lightmap_lighting_solver",
        "lightmap_manifest",
        "lightmap_output",
        "lightmap_padding",
        "lightmap_rasterizer",
        "lightmap_sampler",
        "lightmap_shadow_solver",
        "lightmap_uv_validator",
        "particle_emitter",
        "preview_cache",
        "raycast_backend",
        "render_data",
        "settings",
        "shader_complexity",
        "material_map_controller",
        "uv_atlas_generator",
        "uv_channel_info",
        "lighting_rig_presets",
    ),
    "rendering": (
        "accel",
        "color_utils",
        "gpu_debug_tables",
        "gpu_diagnostics_config",
        "gpu_diagnostics_records",
        "gpu_scene_helpers",
        "gpu_shaders",
        "gpu_vbo_layout",
        "hardware_info",
        "mesh_render_data",
        "picking",
        "renderer_backend",
        "renderer_capabilities",
        "renderer_interface",
        "renderer_performance",
        "renderer_profiler",
        "renderer_settings",
        "skeleton_render_data",
        "viewport_display",
        "viewport_navigation",
        "wgpu_shared",
        "wgpu_shaders",
    ),
    "level": (
        "kmap_model",
        "kmap_project",
        "kmap_serializer",
        "kmap_validator",
        "level_export_bridge",
        "level_manifest",
        "level_module_instance",
        "level_room_instance",
        "level_scene",
        "level_texture_resolver",
    ),
    "mdl": (
        "ghostrigger_mdl_reader",
        "mdl_parser",
        "mdl_porter",
        "mdl_reader_wrapper",
        "mdl_writer",
    ),
    "modules": (
        "area_wok_integration",
        "custom_module_packager",
        "module_categories",
        "module_blueprint_service",
        "module_builder_service",
        "module_editor_controller",
        "module_editor_model",
        "module_format",
        "module_hydration",
        "module_layout_service",
        "module_loader",
        "module_object_inspector",
        "module_porter_service",
        "module_save_pipeline",
        "module_walkmesh_service",
    ),
    "scene": (
        "lyt_room_graph",
        "scene_manager",
        "vis_editor",
    ),
    "skeleton": (
        "skeleton_builder",
    ),
    "special": (
        "hooks",
        "lip_reader",
        "render_constants",
        "unity_malak_smoke",
    ),
    "templates": (
        "template_builder",
        "twoda",
    ),
    "walkmesh": (
        "walkmesh_editor",
        "walkmesh_renderer",
    ),
    "workflow": (
        "_workflow_base",
        "composite_workflow",
    ),
}

_ALIASES: dict[str, str] = {}
_ROOT_PACKAGE = __name__.removesuffix(".qt_core")


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
    """Module alias that imports its subsystem implementation on first use."""

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

    def __setattr__(self, name: str, value) -> None:
        if name in {"_target", "_loaded"} or (name.startswith("__") and name.endswith("__")):
            self.__dict__[name] = value
            return
        setattr(self._load(), name, value)
        self.__dict__[name] = value

    def __delattr__(self, name: str) -> None:
        loaded = self._load()
        if hasattr(loaded, name):
            delattr(loaded, name)
        if name in self.__dict__:
            del self.__dict__[name]

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
        target = f"{_ROOT_PACKAGE}.{group}.{module_name}"
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

# Stable public backend facade symbols. Keep this list curated and explicit.
from .animation.animation_engine import AnimationEngine, AnimPose, NodePose, SuperModelResolver
from .assets.override_layer import OverrideEntry, OverrideLayer
from .assets.resource_manager import ResourceManager, get_manager, resolve_model_textures
from .diagnostics.validation_service import Severity, ValidationIssue, ValidationService, validate_scene
from .game.kotor_install import KotorInstallation
from .game.kotor_loader import load_model_from_bytes, load_model_from_file, load_tpc_as_pil
from .geometry.model_data import (
    Animation,
    AnimEvent,
    BoneWeight,
    GameVersion,
    KotorModel,
    ModelClassification,
    ModelNode,
    NodeFlags,
    VertexSkinData,
)
from .geometry.vertex_space import VertexSpace, compute_vertex_space
from .mdl.mdl_parser import MDLAsciiParser, MDLAsciiWriter, MDLBinaryParser
from .mdl.mdl_writer import MDLBinaryWriter
from .modules.module_loader import LoadResult, ModuleLoader, load_module_directory
from .modules.module_save_pipeline import ModuleSaveRequest, ModuleSaveResult, save_module_package
from .scene.scene_manager import SceneGraph, SceneManager, SceneObject, SceneObjectType
from .templates.twoda import TwoDA

__all__ = [
    *_GROUPS.keys(),
    "Animation",
    "AnimationEngine",
    "AnimEvent",
    "AnimPose",
    "BoneWeight",
    "GameVersion",
    "KotorInstallation",
    "KotorModel",
    "LoadResult",
    "MDLAsciiParser",
    "MDLAsciiWriter",
    "MDLBinaryParser",
    "MDLBinaryWriter",
    "ModelClassification",
    "ModelNode",
    "ModuleLoader",
    "ModuleSaveRequest",
    "ModuleSaveResult",
    "NodeFlags",
    "NodePose",
    "OverrideEntry",
    "OverrideLayer",
    "ResourceManager",
    "SceneGraph",
    "SceneManager",
    "SceneObject",
    "SceneObjectType",
    "Severity",
    "SuperModelResolver",
    "TwoDA",
    "ValidationIssue",
    "ValidationService",
    "VertexSkinData",
    "VertexSpace",
    "compute_vertex_space",
    "get_manager",
    "load_model_from_bytes",
    "load_model_from_file",
    "load_module_directory",
    "load_tpc_as_pil",
    "resolve_model_textures",
    "save_module_package",
    "validate_scene",
]
