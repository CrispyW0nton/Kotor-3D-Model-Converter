from __future__ import annotations

import ast
import inspect
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from types import MethodType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
_VIEWPORT_WIDGET_SOURCE_FILES = (
    "src/gui/viewports/viewport_core/widgets/viewport_widget.py",
    "src/gui/viewports/viewport_core/widgets/state_helpers.py",
    "src/gui/viewports/viewport_core/widgets/construction.py",
    "src/gui/viewports/viewport_core/widgets/scene_models.py",
    "src/gui/viewports/viewport_core/widgets/display_controls.py",
    "src/gui/viewports/viewport_core/widgets/camera_workflow.py",
    "src/gui/viewports/viewport_core/widgets/measurement_controls.py",
    "src/gui/viewports/viewport_core/widgets/transform_camera.py",
    "src/gui/viewports/viewport_core/widgets/selection_mesh.py",
    "src/gui/viewports/viewport_core/widgets/history_animation.py",
    "src/gui/viewports/viewport_core/widgets/event_navigation.py",
    "src/gui/viewports/viewport_core/widgets/rendering_pipeline.py",
    "src/gui/viewports/viewport_core/widgets/overlay_layers.py",
    "src/gui/viewports/viewport_core/widgets/picking_hover.py",
    "src/gui/viewports/viewport_core/widgets/drag_interactions.py",
    "src/gui/viewports/viewport_core/widgets/resource_cache.py",
)


def _qt_viewport_widget_source() -> str:
    return "\n".join((ROOT / path).read_text(encoding="utf-8") for path in _VIEWPORT_WIDGET_SOURCE_FILES)


def test_backend_packages_do_not_import_gui_directly() -> None:
    """Backend and headless pipeline packages must not cross into GUI imports."""
    checked_roots = (
        ROOT / "src/core",
        ROOT / "src/sequence",
        ROOT / "src/converters",
        ROOT / "src/autorig",
        ROOT / "src/math",
        ROOT / "src/ipc",
        ROOT / "src/kotormcp",
        ROOT / "src/unreal",
        ROOT / "src/workbench",
        ROOT / "src/systems",
        ROOT / "src/adapters/gpu",
        ROOT / "src/resources",
    )
    violations: list[str] = []

    for root in checked_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module == "src.gui" or module.startswith("src.gui."):
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: from {module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.name
                        if name == "src.gui" or name.startswith("src.gui."):
                            violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: import {name}")

    assert not violations


def test_required_adapter_modules_are_not_gitignored() -> None:
    """Required adapter source files must not be hidden by broad diagnostic ignores."""
    required = [
        "src/adapters/rendering/gpu_diagnostics_exports.py",
    ]
    ignored: list[str] = []
    for path in required:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--", path],
            cwd=ROOT,
            text=True,
            check=True,
            capture_output=True,
        )
        if result.stdout.strip():
            ignored.append(path)

    assert ignored == []


def test_core_ports_define_named_headless_boundaries() -> None:
    """Architecture ports should be importable from stable core ownership."""
    import inspect
    import sys

    from src.core.ports import (
        FileWriterPort,
        GameResourceProvider,
        ScriptCompileResult,
        ScriptCompilerPort,
        TextureDecodeResult,
        TextureDecoder,
        ViewportRendererPort,
    )
    from src.core.export.export_job import ExportJobContext
    from src.core.rendering.renderer_interface import IViewportRenderer
    from src.core.resources.game_resource_provider import GameResourceProvider as ResourceProviderProtocol

    assert GameResourceProvider is ResourceProviderProtocol
    assert ViewportRendererPort is IViewportRenderer
    assert inspect.isclass(TextureDecodeResult)
    assert inspect.isclass(ScriptCompileResult)
    assert isinstance(
        ExportJobContext(request=None, staging_dir=ROOT, output_map={}),  # type: ignore[arg-type]
        FileWriterPort,
    )
    for protocol in (FileWriterPort, GameResourceProvider, ScriptCompilerPort, TextureDecoder):
        assert getattr(protocol, "_is_protocol", False)

    for module_name in (
        "src.core.ports",
        "src.core.ports.files",
        "src.core.ports.resources",
        "src.core.ports.scripts",
        "src.core.ports.textures",
        "src.core.ports.viewport_renderer",
    ):
        source = inspect.getsource(sys.modules[module_name])
        assert "src.gui" not in source
        assert "PySide6" not in source
        assert "tkinter" not in source


def test_headless_backend_packages_do_not_route_through_qt_core_facade() -> None:
    """Headless backend code should import canonical owners, not qt_core shims."""
    checked_roots = (
        ROOT / "src/core",
        ROOT / "src/sequence",
        ROOT / "src/converters",
        ROOT / "src/autorig",
        ROOT / "src/math",
        ROOT / "src/ipc",
        ROOT / "src/kotormcp",
        ROOT / "src/unreal",
        ROOT / "src/workbench",
        ROOT / "src/systems",
        ROOT / "src/adapters/gpu",
        ROOT / "src/resources",
        ROOT / "scripts",
    )
    allowed = {
        Path("src/core/__init__.py"),
        Path("src/core/qt_core.py"),
    }
    offenders: list[str] = []

    for root in checked_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel_path = path.relative_to(ROOT)
            if rel_path in allowed:
                continue
            source = path.read_text(encoding="utf-8")
            if "src.core.qt_core" in source or "core.qt_core" in source:
                offenders.append(str(rel_path))

    assert offenders == []


def test_adapter_gui_imports_are_explicit_boundary_bridges() -> None:
    """Adapter packages may touch GUI code only through named bridge modules."""
    allowed: set[Path] = set()
    violations: list[str] = []

    for path in (ROOT / "src/adapters").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel_path = path.relative_to(ROOT)
        for node in ast.walk(tree):
            imports_gui = False
            imported = ""
            if isinstance(node, ast.ImportFrom):
                imported = node.module or ""
                imports_gui = imported == "src.gui" or imported.startswith("src.gui.")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    imports_gui = imported == "src.gui" or imported.startswith("src.gui.")
                    if imports_gui:
                        break
            if imports_gui and rel_path not in allowed:
                violations.append(f"{rel_path}:{node.lineno}: {imported}")

    assert not violations


def test_ipc_callback_dispatch_uses_qt_adapter_boundary() -> None:
    """IPC should stay headless while Qt callback dispatch lives in an adapter."""
    ipc_sources = (
        ROOT / "src/ipc/client.py",
        ROOT / "src/ipc/server.py",
    )
    for path in ipc_sources:
        source = path.read_text(encoding="utf-8")
        assert "from src.adapters.qt_ipc.threading import marshal_to_gui_thread" in source
        for forbidden in ("PySide6", "QtCore", "QtGui", "QtWidgets", "tkinter", "ImageTk"):
            assert forbidden not in source

    adapter_source = (ROOT / "src/adapters/qt_ipc/threading.py").read_text(encoding="utf-8")
    assert "from PySide6.QtCore import QCoreApplication, QTimer" in adapter_source
    assert "QTimer.singleShot(0, lambda: cb(*args))" in adapter_source


def test_tracked_non_contract_tests_use_backend_owners_not_gui_facades() -> None:
    """Ordinary tests should demonstrate canonical backend ownership."""
    allowed = {
        Path("tests/test_core_contracts.py"),
        Path("tests/test_qt_only_imports.py"),
    }
    forbidden = (
        "from src.gui.camera.",
        "import src.gui.camera.",
        "src.gui.camera.",
        "from src.gui.rendering.",
        "import src.gui.rendering.",
        "src.gui.rendering.",
        "from src.gui.lighting.",
        "import src.gui.lighting.",
        "src.gui.lighting.",
        "from src.gui.textures.",
        "import src.gui.textures.",
        "src.gui.textures.",
        "from src.gui.gizmo.",
        "import src.gui.gizmo.",
        "src.gui.gizmo.",
    )
    tracked = subprocess.run(
        ["git", "ls-files", "tests/*.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()

    violations: list[str] = []
    for raw_path in tracked:
        rel_path = Path(raw_path)
        if rel_path in allowed:
            continue
        source = (ROOT / rel_path).read_text(encoding="utf-8")
        if any(token in source for token in forbidden):
            violations.append(str(rel_path))

    assert violations == []


def test_migrated_test_slices_use_backend_owners_not_qt_core_facade() -> None:
    """Tests migrated with backend slices should import the canonical owners."""
    checked = (
        Path("tests/test_animation_retargeting.py"),
        Path("tests/test_asset_preview.py"),
        Path("tests/test_character_mode.py"),
        Path("tests/test_character_builder_template_rig.py"),
        Path("tests/test_fbx_blender_fallback.py"),
        Path("tests/test_gizmo_follows_object.py"),
        Path("tests/test_gizmo_kmax_transform.py"),
        Path("tests/test_gizmo_mode_state.py"),
        Path("tests/test_lightmap_baker.py"),
        Path("tests/test_module_categories.py"),
        Path("tests/test_headless_body_workflow.py"),
        Path("tests/test_joint_dot_overlay.py"),
        Path("tests/test_regression_export.py"),
        Path("tests/test_regression.py"),
        Path("tests/test_regression_screens.py"),
        Path("tests/test_theme_layout_loading.py"),
        Path("tests/test_unity_export_bridge.py"),
        Path("tests/test_unity_malak_smoke.py"),
        Path("tests/test_walkmesh_coload.py"),
    )
    offenders = [
        str(path)
        for path in checked
        if "src.core.qt_core" in (ROOT / path).read_text(encoding="utf-8")
        or "core.qt_core" in (ROOT / path).read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_tracked_non_facade_tests_do_not_route_through_qt_core() -> None:
    """Ordinary tests should avoid qt_core; facade tests cover compatibility paths."""
    allowed = {
        Path("tests/test_core_contracts.py"),
        Path("tests/test_core_imports.py"),
        Path("tests/test_qt_only_imports.py"),
    }
    tracked = subprocess.run(
        ["git", "ls-files", "tests/*.py"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()

    offenders = []
    for raw_path in tracked:
        rel_path = Path(raw_path)
        if rel_path in allowed:
            continue
        source = (ROOT / rel_path).read_text(encoding="utf-8")
        if "src.core.qt_core" in source or "core.qt_core" in source:
            offenders.append(str(rel_path))

    assert offenders == []


def test_core_imports_subsystem_smoke_uses_canonical_owners() -> None:
    """The core import smoke test should exercise real subsystem modules separately from facade routes."""
    path = ROOT / "tests/test_core_imports.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    subsystem_test = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "test_core_subsystem_imports"
    )
    source = ast.get_source_segment(path.read_text(encoding="utf-8"), subsystem_test) or ""

    assert "src.core.qt_core" not in source
    assert "core.qt_core" not in source
    assert "from src.core.assets.resource_manager import ResourceManager" in source
    assert "from src.core.scene.scene_manager import SceneManager" in source


def test_runtime_sources_do_not_import_gui_backend_facades() -> None:
    """Runtime code should use canonical core/adapter owners, not old GUI backend facades."""
    allowed = {
        Path("src/gui/dialogs/qt_lightmap_baker_dialog.py"),
    }
    forbidden_prefixes = (
        "src.gui.camera.",
        "src.gui.rendering.",
        "src.gui.lighting.",
        "src.gui.textures.",
        "src.gui.gizmo.",
        "src.gui.qt_lib.camera.",
        "src.gui.qt_lib.rendering.",
        "src.gui.qt_lib.lighting.",
        "src.gui.qt_lib.textures.",
        "src.gui.qt_lib.gizmo.",
    )
    violations: list[str] = []

    for root in (ROOT / "src", ROOT / "scripts"):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel_path = path.relative_to(ROOT)
            if rel_path in allowed:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imported_modules: list[str] = []
                if isinstance(node, ast.ImportFrom):
                    imported_modules.append(node.module or "")
                elif isinstance(node, ast.Import):
                    imported_modules.extend(alias.name for alias in node.names)
                for imported in imported_modules:
                    if any(imported.startswith(prefix) for prefix in forbidden_prefixes):
                        violations.append(f"{rel_path}:{node.lineno}: {imported}")

    assert violations == []


def test_backend_reorganization_plan_does_not_reopen_completed_lightmap_slice() -> None:
    """The architecture plan should not describe migrated lightmap bake work as pending."""
    source = (ROOT / "docs/architecture/backend_reorganization_plan.md").read_text(encoding="utf-8")

    assert "bake services pending" not in source
    assert "larger lightmap bake services remain a future slice" not in source
    assert "src/core/lighting/lightmap_baker.py" in source
    assert "src/adapters/gpu/lightmap_baker.py" in source


def test_backend_reorganization_plan_classifies_compatibility_facades() -> None:
    """Compatibility facades should have explicit permanence decisions."""
    source = (ROOT / "docs/architecture/backend_reorganization_plan.md").read_text(encoding="utf-8")

    assert "## Compatibility Facade Policy" in source
    for facade, decision in {
        "`src.core.qt_core`": "Frozen public compatibility API",
        "`src.gui.camera`": "Transitional compatibility path",
        "`src.gui.lighting`": "Transitional compatibility path",
        "`src.gui.rendering`": "Transitional compatibility path",
        "`src.gui.textures`": "Transitional compatibility path",
        "`src.gui.gizmo`": "Transitional compatibility path",
    }.items():
        assert facade in source
        assert decision in source

    assert "New runtime code must not import these facades." in source
    assert "Retirement candidates" in source


def test_resource_browser_uses_core_ports_resource_boundary() -> None:
    """Resource-browser models should consume the provider through the port package."""
    source = (ROOT / "src/gui/panels/qt_resource_browser_model.py").read_text(encoding="utf-8")

    assert "from src.core.ports import (" in source
    assert "from src.core.resources.game_resource_provider import" not in source


def test_export_job_context_implements_file_writer_port() -> None:
    """Export jobs should expose staged file writes through the core file-writer port."""
    source = (ROOT / "src/core/export/export_job.py").read_text(encoding="utf-8")
    ue_export_source = (ROOT / "src/core/retargeting/ue_fbx_exporter.py").read_text(encoding="utf-8")

    assert "def write_bytes(self, path: str | Path, data: bytes) -> None:" in source
    assert "def write_text(self, path: str | Path, text: str, *, encoding: str = \"utf-8\") -> None:" in source
    assert "context.write_text(manifest_path" in ue_export_source


def test_null_renderer_uses_viewport_renderer_port_boundary() -> None:
    """Concrete viewport renderer adapters should consume the named renderer port."""
    source = (ROOT / "src/adapters/rendering/null_renderer.py").read_text(encoding="utf-8")

    assert "from src.core.ports import ViewportRendererPort" in source
    assert "class NullDiagnosticRenderer(ViewportRendererPort):" in source
    assert "from src.core.rendering.renderer_interface import IViewportRenderer" not in source


def test_renderer_factory_proxy_uses_viewport_renderer_port_boundary() -> None:
    """Renderer factory proxy should expose the named viewport renderer port."""
    from src.adapters.rendering.renderer_factory import FallbackViewportRenderer, create_viewport_renderer
    from src.core.ports import ViewportRendererPort

    source = (ROOT / "src/adapters/rendering/renderer_factory.py").read_text(encoding="utf-8")

    assert "from src.core.ports import ViewportRendererPort" in source
    assert "class FallbackViewportRenderer(ViewportRendererPort):" in source
    assert ") -> ViewportRendererPort:" in source
    assert issubclass(FallbackViewportRenderer, ViewportRendererPort)
    assert isinstance(create_viewport_renderer(None), ViewportRendererPort)


def test_unavailable_script_compiler_implements_script_compiler_port() -> None:
    """Script workflows should have a concrete port fallback when no compiler exists."""
    from src.adapters.scripts import UnavailableScriptCompiler
    from src.core.ports import ScriptCompilerPort
    from src.core.validation.validation_bus import ValidationSeverity, ValidationSubsystem

    source = (ROOT / "src/adapters/scripts/unavailable_compiler.py").read_text(encoding="utf-8")
    compiler = UnavailableScriptCompiler()
    result = compiler.compile_script("k_ptar_load.nss", game="K1")

    assert "from src.core.ports import ScriptCompileResult, ScriptCompilerPort" in source
    assert isinstance(compiler, ScriptCompilerPort)
    assert result.output == b""
    assert result.report.has_blocking
    assert result.report.issues[0].severity == ValidationSeverity.BLOCKING
    assert result.report.issues[0].subsystem == ValidationSubsystem.SCRIPT
    assert result.report.issues[0].code == "script.compiler.unavailable"
    assert result.metadata["available"] is False


def test_local_file_writer_implements_file_writer_port() -> None:
    """Plain filesystem writes should go through a concrete file-writer adapter."""
    from src.adapters.files import LocalFileWriter
    from src.core.ports import FileWriterPort

    source = (ROOT / "src/adapters/files/local_file_writer.py").read_text(encoding="utf-8")
    workbench_source = (ROOT / "src/workbench/ue5_rig_export.py").read_text(encoding="utf-8")

    assert "from src.core.ports import FileWriterPort" in source
    assert isinstance(LocalFileWriter(), FileWriterPort)
    assert "file_writer: FileWriterPort | None = None" in workbench_source
    assert "request.file_writer or LocalFileWriter()" in workbench_source
    assert "file_writer.write_text(" in workbench_source


def test_required_script_adapter_modules_are_not_gitignored() -> None:
    """Script compiler adapter sources must not be hidden by broad scripts ignores."""
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--",
            "src/adapters/scripts/__init__.py",
            "src/adapters/scripts/unavailable_compiler.py",
        ],
        cwd=ROOT,
        text=True,
        check=True,
        capture_output=True,
    )

    assert result.stdout.strip() == ""


def test_gui_backend_compatibility_paths_stay_thin() -> None:
    """Old GUI backend-like paths should stay facades unless explicitly exempted."""
    checked_roots = (
        ROOT / "src/gui/camera",
        ROOT / "src/gui/lighting",
        ROOT / "src/gui/gizmo",
        ROOT / "src/gui/textures",
        ROOT / "src/gui/rendering",
    )
    allowed_def_names: dict[Path, set[str]] = {
        Path("src/gui/camera/__init__.py"): {"__getattr__", "__dir__"},
        Path("src/gui/gizmo/__init__.py"): {"__getattr__", "__dir__"},
        Path("src/gui/lighting/__init__.py"): {"__getattr__", "__dir__"},
        Path("src/gui/rendering/qt_gpu_renderer.py"): {"__getattr__", "__dir__"},
    }

    offenders: list[str] = []
    for root in checked_roots:
        for path in root.rglob("*.py"):
            rel_path = path.relative_to(ROOT)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    offenders.append(f"{rel_path}:{node.lineno}: {node.name}")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name not in allowed_def_names.get(rel_path, set()):
                        offenders.append(f"{rel_path}:{node.lineno}: {node.name}")

    assert offenders == []


def test_gui_backend_compatibility_paths_do_not_use_wildcard_reexports() -> None:
    """Old GUI backend-like paths should alias/forward explicitly, not copy symbol tables."""
    checked_roots = (
        ROOT / "src/gui/camera",
        ROOT / "src/gui/lighting",
        ROOT / "src/gui/gizmo",
        ROOT / "src/gui/textures",
        ROOT / "src/gui/rendering",
    )
    offenders: list[str] = []

    for root in checked_roots:
        for path in root.rglob("*.py"):
            rel_path = path.relative_to(ROOT)
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                    offenders.append(f"{rel_path}:{node.lineno}: wildcard import")
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "update"
                    and isinstance(node.func.value, ast.Call)
                    and isinstance(node.func.value.func, ast.Name)
                    and node.func.value.func.id == "globals"
                ):
                    offenders.append(f"{rel_path}:{node.lineno}: globals().update")

    assert offenders == []


def test_backend_and_adapter_modules_do_not_use_wildcard_import_hubs() -> None:
    """Backend and adapter modules should name their dependency owners explicitly."""
    checked_roots = (
        ROOT / "src/core",
        ROOT / "src/adapters",
    )
    offenders: list[str] = []

    for root in checked_roots:
        for path in root.rglob("*.py"):
            rel_path = path.relative_to(ROOT)
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                    offenders.append(f"{rel_path}:{node.lineno}: wildcard import")
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "update"
                    and isinstance(node.func.value, ast.Call)
                    and isinstance(node.func.value.func, ast.Name)
                    and node.func.value.func.id == "globals"
                ):
                    offenders.append(f"{rel_path}:{node.lineno}: globals().update")

    assert offenders == []


def test_scripts_use_backend_owners_not_backend_facade() -> None:
    """Headless scripts should not route backend helpers through qt_core."""
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "scripts").rglob("*.py")
        if "src.core.qt_core" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_kotormcp_uses_backend_owners_not_backend_facade() -> None:
    """MCP adapters are headless and should consume canonical backend owners."""
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "src/kotormcp").rglob("*.py")
        if "src.core.qt_core" in path.read_text(encoding="utf-8")
        or "core.qt_core" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_selected_core_runtime_modules_use_backend_owners_not_qt_core_facade() -> None:
    """Core runtime modules should not route sibling backend helpers through qt_core."""
    checked = (
        Path("src/core/animation/animation_library.py"),
        Path("src/core/animation_retargeting/skeleton_template_picker.py"),
        Path("src/core/assets/asset_preview.py"),
        Path("src/core/assets/resource_manager.py"),
        Path("src/core/characters/character_builder.py"),
        Path("src/core/characters/head_workflow.py"),
        Path("src/core/characters/headless_body_workflow.py"),
        Path("src/core/game/kotor_loader.py"),
        Path("src/core/graphics/tpc_render_utils.py"),
        Path("src/core/lighting/lightmap_rasterizer.py"),
        Path("src/core/modules/module_hydration.py"),
        Path("src/core/modules/module_layout_service.py"),
        Path("src/core/modules/module_walkmesh_service.py"),
        Path("src/core/rendering/mesh_render_data.py"),
        Path("src/core/rendering/frame_core/dependencies.py"),
        Path("src/core/rendering/frame_core/renderer_geometry.py"),
        Path("src/core/rendering/frame_core/renderer_overlays.py"),
        Path("src/core/templates/template_builder.py"),
        Path("src/core/workflow/_workflow_base.py"),
        Path("src/core/workflow/composite_workflow.py"),
    )
    offenders = [
        str(path)
        for path in checked
        if "src.core.qt_core" in (ROOT / path).read_text(encoding="utf-8")
        or "core.qt_core" in (ROOT / path).read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_core_implementation_modules_do_not_reference_backend_facade() -> None:
    """Core implementation modules should not teach or use the qt_core facade."""
    allowed = {
        Path("src/core/__init__.py"),
        Path("src/core/qt_core.py"),
    }
    offenders = []
    for path in (ROOT / "src/core").rglob("*.py"):
        rel_path = path.relative_to(ROOT)
        if rel_path in allowed:
            continue
        source = path.read_text(encoding="utf-8")
        if "src.core.qt_core" in source or "core.qt_core" in source:
            offenders.append(str(rel_path))

    assert offenders == []


def test_core_implementation_modules_do_not_manipulate_sys_path() -> None:
    """Core implementation modules should use package imports, not local path hacks."""
    allowed = {
        Path("src/core/__init__.py"),
        Path("src/core/qt_core.py"),
    }
    offenders: list[str] = []

    for path in (ROOT / "src/core").rglob("*.py"):
        rel_path = path.relative_to(ROOT)
        if rel_path in allowed:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"append", "insert"}
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "path"
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "sys"
            ):
                offenders.append(f"{rel_path}:{node.lineno}: sys.path.{node.func.attr}")

    assert offenders == []


def test_runtime_sources_do_not_route_through_qt_core_facade() -> None:
    """Runtime source should consume canonical backend owners, not qt_core compatibility routes."""
    allowed = {
        Path("src/core/__init__.py"),
        Path("src/core/qt_core.py"),
    }
    offenders: list[str] = []

    for root in (ROOT / "src", ROOT / "scripts"):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel_path = path.relative_to(ROOT)
            if rel_path in allowed:
                continue
            source = path.read_text(encoding="utf-8")
            if "src.core.qt_core" in source or "core.qt_core" in source:
                offenders.append(str(rel_path))

    assert offenders == []


def test_selected_gui_workflow_modules_use_backend_owners_not_qt_core_facade() -> None:
    """GUI workflows may consume backend services, but should not route through qt_core."""
    checked = (
        Path("src/gui/panels/qt_bottom_strip.py"),
        Path("src/gui/panels/qt_character_builder_panel.py"),
        Path("src/gui/panels/qt_inspector_panel.py"),
        Path("src/gui/panels/qt_library_panel.py"),
        Path("src/gui/panels/qt_properties_panel.py"),
        Path("src/gui/panels/qt_workflow_rail.py"),
        Path("src/gui/windows/application_core/shared/animation_workflow.py"),
        Path("src/gui/windows/application_core/shared/bas_workflow.py"),
        Path("src/gui/windows/application_core/functions/geometry.py"),
        Path("src/gui/windows/application_core/functions/startup_library.py"),
        Path("src/gui/windows/application_core/shared/model_io.py"),
        Path("src/gui/windows/application_core/shared/retarget_workflow.py"),
        Path("src/gui/windows/application_core/shared/resource_loading.py"),
        Path("src/gui/windows/application_core/shared/resource_panels.py"),
        Path("src/gui/windows/application_core/shared/scene_workflow.py"),
        Path("src/gui/windows/application_core/shared/startup_library.py"),
        Path("src/gui/windows/application_core/shared/viewport_tools.py"),
        Path("src/gui/windows/application_core/shared/workers.py"),
        Path("src/gui/viewports/viewport_core/widgets/drag_interactions.py"),
        Path("src/gui/viewports/viewport_core/widgets/scene_models.py"),
        Path("src/gui/viewports/viewport_core/widgets/transform_camera.py"),
        Path("src/gui/windows/qt_unreal_animator.py"),
    )
    offenders = [
        str(path)
        for path in checked
        if "src.core.qt_core" in (ROOT / path).read_text(encoding="utf-8")
        or "core.qt_core" in (ROOT / path).read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_texture_format_helpers_are_backend_owned() -> None:
    """TPC/TXI parsing belongs to core graphics, with GUI paths as facades."""
    import sys

    import src.core.graphics.tpc as core_tpc_module
    import src.core.graphics.txi as core_txi_module
    import src.gui.textures.tpc as gui_tpc_module
    import src.gui.textures.txi as gui_txi_module

    from src.core.graphics.tpc import _is_tpc_data as core_is_tpc_data
    from src.core.graphics.txi import _parse_txi_string as core_parse_txi
    from src.gui.textures.tpc import _is_tpc_data as gui_is_tpc_data
    from src.gui.textures.txi import _parse_txi_string as gui_parse_txi

    assert gui_is_tpc_data is core_is_tpc_data
    assert gui_parse_txi is core_parse_txi
    assert gui_tpc_module is core_tpc_module
    assert gui_txi_module is core_txi_module
    assert sys.modules["src.gui.textures.tpc"] is core_tpc_module
    assert sys.modules["src.gui.textures.txi"] is core_txi_module
    for source_path, target_module in (
        ("src/gui/textures/tpc.py", "src.core.graphics.tpc"),
        ("src/gui/textures/txi.py", "src.core.graphics.txi"),
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert f'import_module("{target_module}")' in source
        assert "sys.modules[__name__] = _module" in source
        assert "import *" not in source
    assert "src.gui.textures" not in (ROOT / "src/core/game/kotor_install.py").read_text(encoding="utf-8")


def test_software_render_accel_and_texture_array_cache_are_backend_owned() -> None:
    """Software-render acceleration and PIL-to-array caches belong to backend packages."""
    import sys

    import src.core.rendering.accel as core_accel_module
    import src.core.graphics.tex_atlas as core_tex_atlas_module
    import src.gui.rendering.accel as gui_accel_module
    import src.gui.rendering.qt_accel as qt_gui_accel_module
    import src.gui.textures.qt_tex_atlas as qt_gui_tex_atlas_module
    import src.gui.textures.tex_atlas as gui_tex_atlas_module

    from src.core.graphics.tex_atlas import TexArrayCache as CoreTexArrayCache
    from src.core.rendering.accel import project_vertices_np as core_project_vertices_np
    from src.core.qt_core.graphics.tex_atlas import TexArrayCache as FacadeTexArrayCache
    from src.core.qt_core.rendering.accel import project_vertices_np as facade_project_vertices_np
    from src.gui.rendering.accel import project_vertices_np as gui_project_vertices_np
    from src.gui.textures.tex_atlas import TexArrayCache as GuiTexArrayCache

    assert GuiTexArrayCache is CoreTexArrayCache
    assert FacadeTexArrayCache is CoreTexArrayCache
    assert gui_project_vertices_np is core_project_vertices_np
    assert facade_project_vertices_np is core_project_vertices_np
    assert gui_accel_module is core_accel_module
    assert qt_gui_accel_module is core_accel_module
    assert gui_tex_atlas_module is core_tex_atlas_module
    assert qt_gui_tex_atlas_module is core_tex_atlas_module
    assert sys.modules["src.gui.rendering.accel"] is core_accel_module
    assert sys.modules["src.gui.rendering.qt_accel"] is core_accel_module
    assert sys.modules["src.gui.textures.tex_atlas"] is core_tex_atlas_module
    assert sys.modules["src.gui.textures.qt_tex_atlas"] is core_tex_atlas_module
    assert "src.gui." not in (ROOT / "src/core/rendering/accel.py").read_text(encoding="utf-8")
    assert "src.gui." not in (ROOT / "src/core/graphics/tex_atlas.py").read_text(encoding="utf-8")
    for source_path, target_module in (
        ("src/gui/rendering/accel.py", "src.core.rendering.accel"),
        ("src/gui/rendering/qt_accel.py", "src.core.rendering.accel"),
        ("src/gui/textures/tex_atlas.py", "src.core.graphics.tex_atlas"),
        ("src/gui/textures/qt_tex_atlas.py", "src.core.graphics.tex_atlas"),
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert f'import_module("{target_module}")' in source
        assert "sys.modules[__name__] = _module" in source
        assert "import *" not in source

    frame_deps = (ROOT / "src/core/rendering/frame_core/dependencies.py").read_text(encoding="utf-8")
    assert "src.core.rendering.accel" in frame_deps
    assert "src.core.graphics.tex_atlas" in frame_deps
    assert "src.gui.qt_lib.rendering.accel" not in frame_deps
    assert "src.gui.qt_lib.textures.tex_atlas" not in frame_deps


def test_tpc_render_utils_are_backend_owned() -> None:
    """Headless TPC/DXT render utilities belong to core graphics."""
    import sys

    import src.core.graphics.tpc_render_utils as core_module
    import src.gui.textures.qt_tpc_render_utils as qt_gui_module
    import src.gui.textures.tpc_render_utils as gui_module

    from src.core.graphics.tpc_render_utils import _paste_textured_triangle as core_paste_triangle
    from src.core.graphics.tpc_render_utils import _is_tpc_data as core_is_tpc_data
    from src.core.qt_core.graphics.tpc_render_utils import _is_tpc_data as facade_is_tpc_data
    from src.gui.textures.qt_tpc_render_utils import _is_tpc_data as qt_gui_is_tpc_data
    from src.gui.textures.tpc_render_utils import _paste_textured_triangle as gui_paste_triangle
    from src.gui.textures.tpc_render_utils import _is_tpc_data as gui_is_tpc_data

    assert gui_module is core_module
    assert qt_gui_module is core_module
    assert sys.modules["src.gui.textures.tpc_render_utils"] is core_module
    assert sys.modules["src.gui.textures.qt_tpc_render_utils"] is core_module
    assert gui_is_tpc_data is core_is_tpc_data
    assert qt_gui_is_tpc_data is core_is_tpc_data
    assert facade_is_tpc_data is core_is_tpc_data
    assert gui_paste_triangle is core_paste_triangle

    core_source = (ROOT / "src/core/graphics/tpc_render_utils.py").read_text(encoding="utf-8")
    gui_source = (ROOT / "src/gui/textures/tpc_render_utils.py").read_text(encoding="utf-8")
    qt_gui_source = (ROOT / "src/gui/textures/qt_tpc_render_utils.py").read_text(encoding="utf-8")
    assert "src.gui." not in core_source
    assert "src.core.qt_core" not in core_source
    assert "core.qt_core" not in core_source
    assert "from src.core.game.kotor_loader import load_tpc_as_pil" in core_source
    assert '_TARGET = "src.core.graphics.tpc_render_utils"' in gui_source
    assert '_TARGET = "src.core.graphics.tpc_render_utils"' in qt_gui_source
    assert "globals().update(" not in gui_source
    assert "globals().update(" not in qt_gui_source


def test_camera_state_and_dtos_are_backend_owned() -> None:
    """Headless camera state/DTO helpers belong to core camera."""
    import sys

    import src.gui.camera as gui_camera_package
    import src.core.camera.arcball_camera as core_arcball_module
    import src.core.camera.camera_model as core_camera_model_module
    import src.core.camera.camera_render_settings as core_render_settings_module
    import src.core.camera.render_output as core_render_output_module
    import src.gui.camera.arcball_camera as gui_arcball_module
    import src.gui.camera.camera_model as gui_camera_model_module
    import src.gui.camera.camera_render_settings as gui_render_settings_module
    import src.gui.camera.render_output as gui_render_output_module
    import src.gui.camera.camera_math as gui_camera_math_module
    import src.math.camera_math as core_camera_math_module

    from src.core.camera.arcball_camera import ArcBallCamera as CoreArcBallCamera
    from src.core.camera.camera_model import GhostRiggerCamera as CoreGhostRiggerCamera
    from src.core.camera.camera_render_settings import RenderSettings as CoreRenderSettings
    from src.core.camera.render_output import RenderOutput as CoreRenderOutput
    from src.math.camera_math import camera_forward as core_camera_forward
    from src.gui.camera.arcball_camera import ArcBallCamera as GuiArcBallCamera
    from src.gui.camera.camera_model import GhostRiggerCamera as GuiGhostRiggerCamera
    from src.gui.camera.camera_render_settings import RenderSettings as GuiRenderSettings
    from src.gui.camera.render_output import RenderOutput as GuiRenderOutput
    from src.gui.camera.camera_math import camera_forward as gui_camera_forward

    assert GuiArcBallCamera is CoreArcBallCamera
    assert GuiGhostRiggerCamera is CoreGhostRiggerCamera
    assert GuiRenderSettings is CoreRenderSettings
    assert GuiRenderOutput is CoreRenderOutput
    assert gui_camera_forward is core_camera_forward
    assert gui_camera_package.GhostRiggerCamera is CoreGhostRiggerCamera
    assert gui_camera_package.RenderSettings is CoreRenderSettings
    assert gui_camera_package.RenderOutput is CoreRenderOutput
    camera_package_source = (ROOT / "src/gui/camera/__init__.py").read_text(encoding="utf-8")
    assert '"GhostRiggerCamera": "src.core.camera.camera_model"' in camera_package_source
    assert '"FrameRenderer": "src.adapters.qt_viewport.still_frame_renderer"' in camera_package_source
    assert "def __getattr__" in camera_package_source
    assert "from src.core.camera" not in camera_package_source
    assert "from .frame_renderer import" not in camera_package_source
    module_pairs = {
        "src.gui.camera.arcball_camera": (gui_arcball_module, core_arcball_module),
        "src.gui.camera.camera_model": (gui_camera_model_module, core_camera_model_module),
        "src.gui.camera.camera_render_settings": (gui_render_settings_module, core_render_settings_module),
        "src.gui.camera.render_output": (gui_render_output_module, core_render_output_module),
        "src.gui.camera.camera_math": (gui_camera_math_module, core_camera_math_module),
    }
    for module_path, (gui_module, core_module) in module_pairs.items():
        assert gui_module is core_module
        assert sys.modules[module_path] is core_module

    for source_path, target_module in (
        ("src/gui/camera/arcball_camera.py", "src.core.camera.arcball_camera"),
        ("src/gui/camera/camera_model.py", "src.core.camera.camera_model"),
        ("src/gui/camera/camera_render_settings.py", "src.core.camera.camera_render_settings"),
        ("src/gui/camera/render_output.py", "src.core.camera.render_output"),
        ("src/gui/camera/camera_math.py", "src.math.camera_math"),
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert f'import_module("{target_module}")' in source
        assert "sys.modules[__name__] = _module" in source
        assert "import *" not in source

    sequence_source = (ROOT / "src/sequence/sequence_render.py").read_text(encoding="utf-8")
    validation_source = (ROOT / "src/core/validation/viewport_validator.py").read_text(encoding="utf-8")
    assert "src.gui.camera.camera_render_settings" not in sequence_source
    assert "src.gui.camera.render_output" not in sequence_source
    assert "src.gui.camera.arcball_camera" not in validation_source


def test_camera_workflow_state_is_backend_owned() -> None:
    """Camera workflow records, presets, manager state, adapters, and manifests belong to core camera."""
    import sys

    import src.gui.camera as gui_camera_package
    import src.core.camera.camera_controller as core_controller_module
    import src.core.camera.camera_manager as core_manager_module
    import src.core.camera.camera_picker as core_picker_module
    import src.core.camera.camera_presets as core_presets_module
    import src.core.camera.camera_rig as core_rig_module
    import src.core.camera.camera_selection as core_selection_module
    import src.core.camera.camera_target as core_target_module
    import src.core.camera.camera_viewport_adapter as core_viewport_adapter_module
    import src.core.camera.render_manifest as core_render_manifest_module
    import src.gui.camera.camera_controller as gui_controller_module
    import src.gui.camera.camera_manager as gui_manager_module
    import src.gui.camera.camera_picker as gui_picker_module
    import src.gui.camera.camera_presets as gui_presets_module
    import src.gui.camera.camera_rig as gui_rig_module
    import src.gui.camera.camera_selection as gui_selection_module
    import src.gui.camera.camera_target as gui_target_module
    import src.gui.camera.camera_viewport_adapter as gui_viewport_adapter_module
    import src.gui.camera.render_manifest as gui_render_manifest_module

    from src.core.camera.camera_controller import CameraController as CoreCameraController
    from src.core.camera.camera_manager import CameraManager as CoreCameraManager
    from src.core.camera.camera_picker import CameraPicker as CoreCameraPicker
    from src.core.camera.camera_presets import FRAMING_PRESETS as CoreFramingPresets
    from src.core.camera.camera_rig import CameraRig as CoreCameraRig
    from src.core.camera.camera_selection import CameraSelection as CoreCameraSelection
    from src.core.camera.camera_target import CameraTarget as CoreCameraTarget
    from src.core.camera.camera_viewport_adapter import CameraViewportAdapter as CoreCameraViewportAdapter
    from src.core.camera.render_manifest import RenderManifestEntry as CoreRenderManifestEntry
    from src.core.qt_core.camera.camera_controller import CameraController as FacadeCameraController
    from src.core.qt_core.camera.camera_manager import CameraManager as FacadeCameraManager
    from src.gui.camera.camera_controller import CameraController as GuiCameraController
    from src.gui.camera.camera_manager import CameraManager as GuiCameraManager
    from src.gui.camera.camera_picker import CameraPicker as GuiCameraPicker
    from src.gui.camera.camera_presets import FRAMING_PRESETS as GuiFramingPresets
    from src.gui.camera.camera_rig import CameraRig as GuiCameraRig
    from src.gui.camera.camera_selection import CameraSelection as GuiCameraSelection
    from src.gui.camera.camera_target import CameraTarget as GuiCameraTarget
    from src.gui.camera.camera_viewport_adapter import CameraViewportAdapter as GuiCameraViewportAdapter
    from src.gui.camera.render_manifest import RenderManifestEntry as GuiRenderManifestEntry

    assert GuiCameraController is CoreCameraController
    assert FacadeCameraController is CoreCameraController
    assert GuiCameraManager is CoreCameraManager
    assert FacadeCameraManager is CoreCameraManager
    assert GuiCameraPicker is CoreCameraPicker
    assert GuiFramingPresets is CoreFramingPresets
    assert GuiCameraRig is CoreCameraRig
    assert GuiCameraSelection is CoreCameraSelection
    assert GuiCameraTarget is CoreCameraTarget
    assert GuiCameraViewportAdapter is CoreCameraViewportAdapter
    assert GuiRenderManifestEntry is CoreRenderManifestEntry
    assert gui_camera_package.CameraManager is CoreCameraManager
    assert gui_camera_package.FrameRenderer.__name__ == "FrameRenderer"
    module_pairs = {
        "camera_controller": (gui_controller_module, core_controller_module),
        "camera_manager": (gui_manager_module, core_manager_module),
        "camera_picker": (gui_picker_module, core_picker_module),
        "camera_presets": (gui_presets_module, core_presets_module),
        "camera_rig": (gui_rig_module, core_rig_module),
        "camera_selection": (gui_selection_module, core_selection_module),
        "camera_target": (gui_target_module, core_target_module),
        "camera_viewport_adapter": (gui_viewport_adapter_module, core_viewport_adapter_module),
        "render_manifest": (gui_render_manifest_module, core_render_manifest_module),
    }
    for module_name, (gui_module, core_module) in module_pairs.items():
        assert gui_module is core_module
        assert sys.modules[f"src.gui.camera.{module_name}"] is core_module

    for filename in (
        "camera_controller.py",
        "camera_manager.py",
        "camera_picker.py",
        "camera_presets.py",
        "camera_rig.py",
        "camera_selection.py",
        "camera_target.py",
        "camera_viewport_adapter.py",
        "render_manifest.py",
    ):
        source = (ROOT / "src/core/camera" / filename).read_text(encoding="utf-8")
        assert "src.gui." not in source
        assert "PySide6" not in source
        assert "QtWidgets" not in source
        assert "QtGui" not in source
        assert "QtCore" not in source
        assert "tkinter" not in source
        gui_source = (ROOT / "src/gui/camera" / filename).read_text(encoding="utf-8")
        target_module = f"src.core.camera.{filename.removesuffix('.py')}"
        assert f'import_module("{target_module}")' in gui_source
        assert "sys.modules[__name__] = _module" in gui_source
        assert "globals().update" not in gui_source

    for source_path in (
        ROOT / "src/gui/camera/frame_renderer.py",
        ROOT / "src/gui/panels/qt_camera_panel.py",
        ROOT / "src/gui/viewports/viewport_core/shared/dependencies.py",
    ):
        source = source_path.read_text(encoding="utf-8")
        assert "src.gui.camera.camera_controller" not in source
        assert "src.gui.camera.camera_manager" not in source
        assert "src.gui.camera.camera_picker" not in source
        assert "src.gui.camera.camera_presets" not in source
        assert "src.gui.camera.camera_viewport_adapter" not in source
        assert "src.gui.camera.render_manifest" not in source


def test_gpu_matrix_helper_is_math_owned() -> None:
    """Shared GPU matrix math should not be owned by GUI diagnostics."""
    import sys

    import src.adapters.rendering.gpu_diagnostics_exports as adapter_diagnostics_module
    import src.adapters.rendering.moderngl_resources as adapter_resources_module
    import src.gui.rendering.gpu_core.diagnostics as gui_diagnostics_module
    import src.gui.rendering.gpu_core.math_helpers as gui_gpu_math_module
    import src.math.gpu_math as math_gpu_math_module

    from src.math.gpu_math import _matrix_from_pos_quat_np as math_matrix_from_pos_quat
    from src.adapters.rendering.moderngl_resources import (
        _matrix_from_pos_quat_np as adapter_matrix_from_pos_quat,
    )
    from src.gui.rendering.gpu_core.diagnostics import _matrix_from_pos_quat_np as gui_matrix_from_pos_quat

    assert gui_diagnostics_module is adapter_diagnostics_module
    assert sys.modules["src.gui.rendering.gpu_core.diagnostics"] is adapter_diagnostics_module
    assert gui_gpu_math_module is math_gpu_math_module
    assert sys.modules["src.gui.rendering.gpu_core.math_helpers"] is math_gpu_math_module
    assert gui_matrix_from_pos_quat is math_matrix_from_pos_quat
    assert adapter_matrix_from_pos_quat is math_matrix_from_pos_quat
    diagnostics_source = (ROOT / "src/gui/rendering/gpu_core/diagnostics.py").read_text(encoding="utf-8")
    math_helpers_source = (ROOT / "src/gui/rendering/gpu_core/math_helpers.py").read_text(encoding="utf-8")
    adapter_resources_source = (ROOT / "src/adapters/rendering/moderngl_resources.py").read_text(encoding="utf-8")
    assert '_TARGET = "src.adapters.rendering.gpu_diagnostics_exports"' in diagnostics_source
    assert "sys.modules[__name__] = _module" in diagnostics_source
    assert "globals().update" not in diagnostics_source
    assert 'import_module("src.math.gpu_math")' in math_helpers_source
    assert "sys.modules[__name__] = _module" in math_helpers_source
    assert "import *" not in math_helpers_source
    assert "from src.math.gpu_math import (" in adapter_resources_source
    assert "from src.math.gpu_math import *" not in adapter_resources_source
    assert adapter_resources_module._mat4_from_pos_quat_scale is math_gpu_math_module._mat4_from_pos_quat_scale
    assert "src.gui.rendering.gpu_core.diagnostics" not in (ROOT / "src/math/gpu_math.py").read_text(
        encoding="utf-8"
    )


def test_transform_gizmo_helpers_are_backend_owned() -> None:
    """Renderer-neutral transform gizmo state, picking, and drag policy belong to core gizmo."""
    import sys

    import src.core.gizmo.gizmo_draw_data as core_draw_data_module
    import src.core.gizmo.gizmo_mode as core_mode_module
    import src.core.gizmo.gizmo_picker as core_picker_module
    import src.core.gizmo.gizmo_renderer as core_renderer_module
    import src.core.gizmo as core_gizmo_package
    import src.core.gizmo.transform_controller as core_controller_module
    import src.core.gizmo.transform_gizmo as core_gizmo_module
    import src.gui.gizmo as gui_gizmo_package
    import src.gui.gizmo.gizmo_draw_data as gui_draw_data_module
    import src.gui.gizmo.gizmo_mode as gui_mode_module
    import src.gui.gizmo.gizmo_picker as gui_picker_module
    import src.gui.gizmo.gizmo_renderer as gui_renderer_module
    import src.gui.gizmo.transform_math as gui_transform_math_module
    import src.gui.gizmo.transform_controller as gui_controller_module
    import src.gui.gizmo.transform_gizmo as gui_gizmo_module
    import src.math.transform_math as math_transform_math_module

    from src.core.gizmo.gizmo_draw_data import GizmoRenderData as CoreGizmoRenderData
    from src.core.gizmo.gizmo_mode import GizmoMode as CoreGizmoMode
    from src.core.gizmo.gizmo_picker import GizmoPicker as CoreGizmoPicker
    from src.core.gizmo.gizmo_renderer import GizmoRenderer as CoreGizmoRenderer
    from src.core.gizmo.transform_controller import TransformController as CoreTransformController
    from src.core.gizmo.transform_gizmo import TransformGizmo as CoreTransformGizmo
    from src.core.qt_core.gizmo.gizmo_mode import GizmoMode as FacadeGizmoMode
    from src.gui.gizmo.gizmo_draw_data import GizmoRenderData as GuiGizmoRenderData
    from src.gui.gizmo.gizmo_mode import GizmoMode as GuiGizmoMode
    from src.gui.gizmo.gizmo_picker import GizmoPicker as GuiGizmoPicker
    from src.gui.gizmo.gizmo_renderer import GizmoRenderer as GuiGizmoRenderer
    from src.gui.gizmo.transform_math import ray_from_mouse as GuiRayFromMouse
    from src.gui.gizmo.transform_controller import TransformController as GuiTransformController
    from src.gui.gizmo.transform_gizmo import TransformGizmo as GuiTransformGizmo
    from src.math.transform_math import ray_from_mouse as MathRayFromMouse

    assert GuiGizmoRenderData is CoreGizmoRenderData
    assert GuiGizmoMode is CoreGizmoMode
    assert FacadeGizmoMode is CoreGizmoMode
    assert GuiGizmoPicker is CoreGizmoPicker
    assert GuiGizmoRenderer is CoreGizmoRenderer
    assert GuiTransformController is CoreTransformController
    assert GuiTransformGizmo is CoreTransformGizmo
    assert GuiRayFromMouse is MathRayFromMouse
    assert gui_gizmo_package.GizmoMode is CoreGizmoMode
    assert gui_gizmo_package.__all__ == tuple(core_gizmo_package.__all__)
    assert gui_transform_math_module is math_transform_math_module
    assert sys.modules["src.gui.gizmo.transform_math"] is math_transform_math_module
    module_pairs = {
        "gizmo_draw_data": (gui_draw_data_module, core_draw_data_module),
        "gizmo_mode": (gui_mode_module, core_mode_module),
        "gizmo_picker": (gui_picker_module, core_picker_module),
        "gizmo_renderer": (gui_renderer_module, core_renderer_module),
        "transform_controller": (gui_controller_module, core_controller_module),
        "transform_gizmo": (gui_gizmo_module, core_gizmo_module),
    }
    for module_name, (gui_module, core_module) in module_pairs.items():
        assert gui_module is core_module
        assert sys.modules[f"src.gui.gizmo.{module_name}"] is core_module

    for filename in (
        "__init__.py",
        "gizmo_draw_data.py",
        "gizmo_mode.py",
        "gizmo_picker.py",
        "gizmo_renderer.py",
        "transform_controller.py",
        "transform_gizmo.py",
    ):
        source = (ROOT / "src/core/gizmo" / filename).read_text(encoding="utf-8")
        assert "src.gui." not in source
        assert "PySide6" not in source
        assert "QtWidgets" not in source
        assert "QtGui" not in source
        assert "QtCore" not in source
        assert "tkinter" not in source
        if filename != "__init__.py":
            gui_source = (ROOT / "src/gui/gizmo" / filename).read_text(encoding="utf-8")
            target_module = f"src.core.gizmo.{filename.removesuffix('.py')}"
            assert f'import_module("{target_module}")' in gui_source
            assert "sys.modules[__name__] = _module" in gui_source
            assert "globals().update" not in gui_source

    gui_package_source = (ROOT / "src/gui/gizmo/__init__.py").read_text(encoding="utf-8")
    assert '"GizmoMode": "src.core.gizmo.gizmo_mode"' in gui_package_source
    assert '"TransformController": "src.core.gizmo.transform_controller"' in gui_package_source
    assert '"TransformGizmo": "src.core.gizmo.transform_gizmo"' in gui_package_source
    assert "def __getattr__" in gui_package_source
    assert "from src.core.gizmo" not in gui_package_source
    assert "import *" not in gui_package_source
    transform_math_source = (ROOT / "src/gui/gizmo/transform_math.py").read_text(encoding="utf-8")
    assert 'import_module("src.math.transform_math")' in transform_math_source
    assert "sys.modules[__name__] = _module" in transform_math_source
    assert "import *" not in transform_math_source

    viewport_deps = (ROOT / "src/gui/viewports/viewport_core/shared/dependencies.py").read_text(encoding="utf-8")
    assert "src.gui.qt_lib.gizmo.gizmo_mode" not in viewport_deps
    assert "src.gui.qt_lib.gizmo.transform_controller" not in viewport_deps
    assert "src.gui.qt_lib.gizmo.transform_gizmo" not in viewport_deps
    assert "from src.core.gizmo.gizmo_mode import GizmoMode" in viewport_deps


def test_gpu_debug_tables_are_backend_owned() -> None:
    """GPU/material diagnostic table generation is backend rendering support."""
    import sys

    import src.core.rendering.gpu_debug_tables as core_debug_tables_module
    import src.gui.rendering.gpu_core.debug_tables as gui_debug_tables_module

    from src.core.qt_core.rendering.gpu_debug_tables import ModuleDrawItem as FacadeModuleDrawItem
    from src.core.rendering.gpu_debug_tables import ModuleDrawItem as CoreModuleDrawItem
    from src.core.rendering.gpu_debug_tables import debug_material_role_table as core_material_role_table
    from src.gui.rendering.gpu_core.debug_tables import ModuleDrawItem as GuiModuleDrawItem
    from src.gui.rendering.gpu_core.debug_tables import debug_material_role_table as gui_material_role_table
    from src.gui.rendering.gpu_renderer import ModuleDrawItem as PublicModuleDrawItem
    from src.gui.rendering.gpu_renderer import debug_material_role_table as public_material_role_table

    assert GuiModuleDrawItem is CoreModuleDrawItem
    assert FacadeModuleDrawItem is CoreModuleDrawItem
    assert PublicModuleDrawItem is CoreModuleDrawItem
    assert gui_material_role_table is core_material_role_table
    assert public_material_role_table is core_material_role_table
    assert gui_debug_tables_module is core_debug_tables_module
    assert sys.modules["src.gui.rendering.gpu_core.debug_tables"] is core_debug_tables_module

    core_source = (ROOT / "src/core/rendering/gpu_debug_tables.py").read_text(encoding="utf-8")
    assert "src.gui." not in core_source
    assert "PySide6" not in core_source
    assert "QtWidgets" not in core_source
    assert "QtGui" not in core_source
    assert "QtCore" not in core_source
    assert "from dataclasses import dataclass" in core_source
    assert "from .diagnostics import" not in core_source

    renderer_source = (ROOT / "src/adapters/rendering/moderngl_renderer_impl.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    gui_facade = (ROOT / "src/gui/rendering/gpu_core/debug_tables.py").read_text(encoding="utf-8")
    assert "from src.core.rendering.gpu_debug_tables import (" in renderer_source
    assert "from src.core.rendering.gpu_debug_tables import *" not in renderer_source
    assert '"ModuleDrawItem": "src.core.rendering.gpu_debug_tables"' in public_facade
    assert "src.gui.rendering.gpu_core.debug_tables" not in public_facade
    assert 'import_module("src.core.rendering.gpu_debug_tables")' in gui_facade
    assert "sys.modules[__name__] = _module" in gui_facade
    assert "globals().update" not in gui_facade


def test_gpu_shader_sources_are_backend_owned() -> None:
    """ModernGL shader source strings are renderer backend data, not GUI logic."""
    import sys

    import src.core.rendering.gpu_shaders as core_gpu_shaders_module
    import src.gui.rendering.gpu_core.shaders as gui_gpu_shaders_module

    from src.core.qt_core.rendering.gpu_shaders import _VERT_SRC as facade_vert_src
    from src.core.rendering.gpu_shaders import _FRAG_SRC as core_frag_src
    from src.core.rendering.gpu_shaders import _VERT_SRC as core_vert_src
    from src.gui.rendering.gpu_core.shaders import _VERT_SRC as gui_vert_src
    from src.gui.rendering.gpu_renderer import _FRAG_SRC as public_frag_src
    from src.gui.rendering.gpu_renderer import _VERT_SRC as public_vert_src

    assert gui_vert_src is core_vert_src
    assert facade_vert_src is core_vert_src
    assert public_vert_src is core_vert_src
    assert public_frag_src is core_frag_src
    assert gui_gpu_shaders_module is core_gpu_shaders_module
    assert sys.modules["src.gui.rendering.gpu_core.shaders"] is core_gpu_shaders_module

    core_source = (ROOT / "src/core/rendering/gpu_shaders.py").read_text(encoding="utf-8")
    assert "src.gui." not in core_source
    assert "PySide6" not in core_source
    assert "QtWidgets" not in core_source
    assert "QtGui" not in core_source
    assert "QtCore" not in core_source
    assert "from .diagnostics import" not in core_source
    assert "uniform float u_uv_v_flip" in core_source

    renderer_source = (ROOT / "src/adapters/rendering/moderngl_renderer_impl.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    gui_facade = (ROOT / "src/gui/rendering/gpu_core/shaders.py").read_text(encoding="utf-8")
    assert "from src.core.rendering.gpu_shaders import _FRAG_SRC, _GRID_FRAG_SRC, _GRID_VERT_SRC, _VERT_SRC" in renderer_source
    assert "from src.core.rendering.gpu_shaders import *" not in renderer_source
    assert '"_VERT_SRC": "src.core.rendering.gpu_shaders"' in public_facade
    assert "src.gui.rendering.gpu_core.shaders" not in public_facade
    assert 'import_module("src.core.rendering.gpu_shaders")' in gui_facade
    assert "sys.modules[__name__] = _module" in gui_facade
    assert "globals().update" not in gui_facade


def test_gpu_scene_helpers_are_backend_owned() -> None:
    """Model bounds, texture TXI application, and composite-model helpers belong to core rendering."""
    from src.adapters.rendering.moderngl_scene_helpers import render_model_autoframe as AdapterRenderAutoframe
    from src.core.qt_core.rendering.gpu_scene_helpers import _CompositeModel as FacadeCompositeModel
    from src.core.qt_core.rendering.gpu_scene_helpers import _compute_model_bounds as facade_compute_bounds
    from src.core.rendering.gpu_scene_helpers import _CompositeModel as CoreCompositeModel
    from src.core.rendering.gpu_scene_helpers import _apply_txi_from_textures_to_model as core_apply_txi
    from src.core.rendering.gpu_scene_helpers import _compute_model_bounds as core_compute_bounds
    from src.gui.rendering.gpu_core.scene_helpers import _CompositeModel as GuiCompositeModel
    from src.gui.rendering.gpu_core.scene_helpers import _compute_model_bounds as gui_compute_bounds
    from src.gui.rendering.gpu_core.scene_helpers import render_model_autoframe as GuiRenderAutoframe
    from src.gui.rendering.gpu_renderer import _CompositeModel as PublicCompositeModel
    from src.gui.rendering.gpu_renderer import _apply_txi_from_textures_to_model as public_apply_txi
    from src.gui.rendering.gpu_renderer import _compute_model_bounds as public_compute_bounds
    from src.gui.rendering.gpu_renderer import render_model_autoframe as PublicRenderAutoframe

    assert GuiCompositeModel is CoreCompositeModel
    assert FacadeCompositeModel is CoreCompositeModel
    assert PublicCompositeModel is CoreCompositeModel
    assert gui_compute_bounds is core_compute_bounds
    assert facade_compute_bounds is core_compute_bounds
    assert public_compute_bounds is core_compute_bounds
    assert public_apply_txi is core_apply_txi
    assert GuiRenderAutoframe is AdapterRenderAutoframe
    assert PublicRenderAutoframe is AdapterRenderAutoframe

    core_source = (ROOT / "src/core/rendering/gpu_scene_helpers.py").read_text(encoding="utf-8")
    for forbidden in ("src.gui.", "PySide6", "QtWidgets", "QtGui", "QtCore", "moderngl", "GpuRenderer"):
        assert forbidden not in core_source

    adapter_scene_source = (ROOT / "src/adapters/rendering/moderngl_scene_helpers.py").read_text(encoding="utf-8")
    gui_scene_source = (ROOT / "src/gui/rendering/gpu_core/scene_helpers.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    mcp_tool_source = (ROOT / "src/kotormcp/tools/ghostrigger.py").read_text(encoding="utf-8")
    debug_materials_source = (ROOT / "src/kotormcp/tools/debug_materials.py").read_text(encoding="utf-8")
    backend_plan = (ROOT / "docs/architecture/backend_reorganization_plan.md").read_text(encoding="utf-8")
    assert "from src.adapters.rendering.moderngl_legacy_bridge import GpuRenderer" in adapter_scene_source
    assert "from src.core.rendering.gpu_scene_helpers import" in adapter_scene_source
    assert "src.gui." not in adapter_scene_source
    assert 'import_module("src.adapters.rendering.moderngl_scene_helpers")' in gui_scene_source
    assert "sys.modules[__name__] = _module" in gui_scene_source
    assert "from .renderer import *" not in gui_scene_source
    assert "def render_model_autoframe" not in gui_scene_source
    assert '"_compute_model_bounds": "src.core.rendering.gpu_scene_helpers"' in public_facade
    assert '"render_model_autoframe": "src.adapters.rendering.moderngl_scene_helpers"' in public_facade
    assert "from src.adapters.rendering.moderngl_scene_helpers import render_model_autoframe" in mcp_tool_source
    assert "from src.adapters.rendering.moderngl_scene_helpers import render_model_autoframe" in debug_materials_source
    assert "`src.gui.rendering.gpu_core.scene_helpers` as a module alias over the adapter owner" in backend_plan
    assert "`src/adapters/rendering/moderngl_scene_helpers.py` because it creates and" in backend_plan


def test_gpu_benchmark_adapter_imports_renderer_dependencies_explicitly() -> None:
    """The ModernGL benchmark adapter should not rely on scene-helper wildcard side effects."""
    import sys

    import src.adapters.rendering.moderngl_benchmark as adapter_benchmark_module
    import src.adapters.rendering.moderngl_cli as adapter_cli_module
    import src.gui.rendering.gpu_core.benchmark as gui_benchmark_module
    import src.gui.rendering.gpu_core.cli as gui_cli_module

    from src.adapters.rendering.moderngl_benchmark import _benchmark as adapter_benchmark
    from src.adapters.rendering.moderngl_cli import _main as adapter_main
    from src.gui.rendering.gpu_core.benchmark import _benchmark as direct_benchmark
    from src.gui.rendering.gpu_core.cli import _main as direct_main
    from src.gui.rendering.gpu_renderer import _benchmark as public_benchmark
    from src.gui.rendering.gpu_renderer import _main as public_main

    assert direct_benchmark is adapter_benchmark
    assert public_benchmark is adapter_benchmark
    assert direct_main is adapter_main
    assert public_main is adapter_main
    assert gui_benchmark_module is adapter_benchmark_module
    assert gui_cli_module is adapter_cli_module
    assert sys.modules["src.gui.rendering.gpu_core.benchmark"] is adapter_benchmark_module
    assert sys.modules["src.gui.rendering.gpu_core.cli"] is adapter_cli_module

    benchmark_source = (ROOT / "src/adapters/rendering/moderngl_benchmark.py").read_text(encoding="utf-8")
    cli_source = (ROOT / "src/adapters/rendering/moderngl_cli.py").read_text(encoding="utf-8")
    gui_benchmark_source = (ROOT / "src/gui/rendering/gpu_core/benchmark.py").read_text(encoding="utf-8")
    gui_cli_source = (ROOT / "src/gui/rendering/gpu_core/cli.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    assert "from .scene_helpers import *" not in benchmark_source
    assert "from src.adapters.rendering.moderngl_legacy_bridge import GpuRenderer" in benchmark_source
    assert "import numpy as np" in benchmark_source
    assert "from PIL import Image" in benchmark_source
    assert "from src.adapters.rendering.moderngl_benchmark import _benchmark" in cli_source
    assert "from src.adapters.rendering.moderngl_legacy_bridge import GpuRenderer" in cli_source
    assert 'import_module("src.adapters.rendering.moderngl_benchmark")' in gui_benchmark_source
    assert 'import_module("src.adapters.rendering.moderngl_cli")' in gui_cli_source
    assert "sys.modules[__name__] = _module" in gui_benchmark_source
    assert "sys.modules[__name__] = _module" in gui_cli_source
    assert "import *" not in gui_benchmark_source
    assert "import *" not in gui_cli_source
    assert '"_benchmark": "src.adapters.rendering.moderngl_benchmark"' in public_facade
    assert '"_main": "src.adapters.rendering.moderngl_cli"' in public_facade


def test_gpu_diagnostics_config_is_backend_owned() -> None:
    """GPU diagnostic env/path helpers belong to core rendering."""
    from src.core.qt_core.rendering.gpu_diagnostics_config import _gl_state_trace_path as facade_trace_path
    from src.core.rendering.gpu_diagnostics_config import _debug_visualize_mode as core_debug_mode
    from src.core.rendering.gpu_diagnostics_config import _gl_state_trace_path as core_trace_path
    from src.core.rendering.gpu_diagnostics_config import _lm_composite_mode as core_lm_mode
    from src.gui.rendering.gpu_core.diagnostics import _debug_visualize_mode as gui_debug_mode
    from src.gui.rendering.gpu_core.diagnostics import _gl_state_trace_path as gui_trace_path
    from src.gui.rendering.gpu_renderer import _gl_state_trace_path as public_trace_path
    from src.gui.rendering.gpu_renderer import _lm_composite_mode as public_lm_mode

    assert gui_trace_path is core_trace_path
    assert facade_trace_path is core_trace_path
    assert public_trace_path is core_trace_path
    assert gui_debug_mode is core_debug_mode
    assert public_lm_mode is core_lm_mode

    core_source = (ROOT / "src/core/rendering/gpu_diagnostics_config.py").read_text(encoding="utf-8")
    for forbidden in ("src.gui.", "PySide6", "QtWidgets", "QtGui", "QtCore", "moderngl"):
        assert forbidden not in core_source

    diagnostics_source = (ROOT / "src/gui/rendering/gpu_core/diagnostics.py").read_text(encoding="utf-8")
    adapter_exports = (ROOT / "src/adapters/rendering/gpu_diagnostics_exports.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    assert '_TARGET = "src.adapters.rendering.gpu_diagnostics_exports"' in diagnostics_source
    assert "sys.modules[__name__] = _module" in diagnostics_source
    assert '"src.core.rendering.gpu_diagnostics_config"' in adapter_exports
    assert '"src.core.rendering.gpu_diagnostics_records"' in adapter_exports
    assert '"src.adapters.gpu.moderngl_runtime"' in adapter_exports
    assert "def __getattr__" in adapter_exports
    assert "_EXPORT_MODULES" not in adapter_exports
    assert "for _module_name in" not in adapter_exports
    assert "getattr(_module, \"__all__\"" not in adapter_exports
    assert "import *" not in adapter_exports
    assert "def " not in diagnostics_source
    assert "class " not in diagnostics_source
    assert "def _gl_state_trace_path" not in diagnostics_source
    assert '"_gl_state_trace_path": "src.core.rendering.gpu_diagnostics_config"' in public_facade


def test_gpu_diagnostics_records_are_backend_owned() -> None:
    """Pure GPU diagnostic heuristics belong to core rendering."""
    from src.core.qt_core.rendering.gpu_diagnostics_records import (
        _build_skin_dump_record as facade_build_skin_dump_record,
        _build_gl_state_trace_record as facade_gl_state_record,
        _build_lm_data_dump_record as facade_lm_data_record,
        _first_divergence_stage as facade_first_divergence_stage,
        _homogeneous_position_json as facade_homogeneous_position_json,
        _matrix4_json as facade_matrix4_json,
        _matrix_max_abs_delta as facade_matrix_max_abs_delta,
        _matrix_rotation_only as facade_matrix_rotation_only,
        _matrix_translation_norm as facade_matrix_translation_norm,
        _node_pose_chain_records as facade_node_pose_chain_records,
        _node_parent_chain_names as facade_parent_chain_names,
        _node_world_matrix_for_pose_np as facade_node_world_matrix,
        _pose_node_transform as facade_pose_node_transform,
        _qbone_direct_bind_json as facade_qbone_direct_bind_json,
        _qbone_inverse_bind_json as facade_qbone_inverse_bind_json,
        _qbone_matrix_np as facade_qbone_matrix_np,
        _quat_xyzw_to_mat4_np as facade_quat_to_mat4,
        _select_skin_3g_probe_vertices as facade_select_3g_probe_vertices,
        _select_skin_probe_vertex as facade_select_probe_vertex,
        _skin_bind_equivalence_record as facade_skin_bind_equivalence_record,
        _skin_3g_candidate_records as facade_skin_3g_candidate_records,
        _skin_3g_matrix_for_formula as facade_skin_3g_matrix_for_formula,
        _skin_3g_role_for_bone as facade_skin_3g_role_for_bone,
        _skin_3g_role_priority as facade_skin_3g_role_priority,
        _skin_live_slot_records as facade_skin_live_slot_records,
        _SKIN_3G_FORMULAS as facade_skin_3g_formulas,
        _should_auto_clamp_diffuse as facade_auto_clamp,
        _uploaded_palette_array_from_uploader as facade_uploaded_palette_array,
        _xoreos_first_frame_orientation_matrix as facade_xoreos_first_frame,
    )
    from src.core.rendering.gpu_diagnostics_records import (
        _build_skin_dump_record as core_build_skin_dump_record,
        _build_gl_state_trace_record as core_gl_state_record,
        _build_lm_data_dump_record as core_lm_data_record,
        _first_divergence_stage as core_first_divergence_stage,
        _homogeneous_position_json as core_homogeneous_position_json,
        _matrix4_json as core_matrix4_json,
        _matrix_max_abs_delta as core_matrix_max_abs_delta,
        _matrix_rotation_only as core_matrix_rotation_only,
        _matrix_translation_norm as core_matrix_translation_norm,
        _node_pose_chain_records as core_node_pose_chain_records,
        _node_parent_chain_names as core_parent_chain_names,
        _node_world_matrix_for_pose_np as core_node_world_matrix,
        _pose_node_transform as core_pose_node_transform,
        _qbone_direct_bind_json as core_qbone_direct_bind_json,
        _qbone_inverse_bind_json as core_qbone_inverse_bind_json,
        _qbone_matrix_np as core_qbone_matrix_np,
        _quat_xyzw_to_mat4_np as core_quat_to_mat4,
        _select_skin_3g_probe_vertices as core_select_3g_probe_vertices,
        _select_skin_probe_vertex as core_select_probe_vertex,
        _skin_bind_equivalence_record as core_skin_bind_equivalence_record,
        _skin_3g_candidate_records as core_skin_3g_candidate_records,
        _skin_3g_matrix_for_formula as core_skin_3g_matrix_for_formula,
        _skin_3g_role_for_bone as core_skin_3g_role_for_bone,
        _skin_3g_role_priority as core_skin_3g_role_priority,
        _skin_live_slot_records as core_skin_live_slot_records,
        _SKIN_3G_FORMULAS as core_skin_3g_formulas,
        _should_auto_clamp_diffuse as core_auto_clamp,
        _uploaded_palette_array_from_uploader as core_uploaded_palette_array,
        _xoreos_first_frame_orientation_matrix as core_xoreos_first_frame,
    )
    from src.gui.rendering.gpu_core.diagnostics import _build_gl_state_trace_record as gui_gl_state_record
    from src.gui.rendering.gpu_core.diagnostics import _build_lm_data_dump_record as gui_lm_data_record
    from src.gui.rendering.gpu_core.diagnostics import _first_divergence_stage as gui_first_divergence_stage
    from src.gui.rendering.gpu_core.diagnostics import _homogeneous_position_json as gui_homogeneous_position_json
    from src.gui.rendering.gpu_core.diagnostics import _matrix4_json as gui_matrix4_json
    from src.gui.rendering.gpu_core.diagnostics import _matrix_max_abs_delta as gui_matrix_max_abs_delta
    from src.gui.rendering.gpu_core.diagnostics import _matrix_rotation_only as gui_matrix_rotation_only
    from src.gui.rendering.gpu_core.diagnostics import _matrix_translation_norm as gui_matrix_translation_norm
    from src.gui.rendering.gpu_core.diagnostics import _node_pose_chain_records as gui_node_pose_chain_records
    from src.gui.rendering.gpu_core.diagnostics import _node_parent_chain_names as gui_parent_chain_names
    from src.gui.rendering.gpu_core.diagnostics import _node_world_matrix_for_pose_np as gui_node_world_matrix
    from src.gui.rendering.gpu_core.diagnostics import _pose_node_transform as gui_pose_node_transform
    from src.gui.rendering.gpu_core.diagnostics import _qbone_direct_bind_json as gui_qbone_direct_bind_json
    from src.gui.rendering.gpu_core.diagnostics import _qbone_inverse_bind_json as gui_qbone_inverse_bind_json
    from src.gui.rendering.gpu_core.diagnostics import _qbone_matrix_np as gui_qbone_matrix_np
    from src.gui.rendering.gpu_core.diagnostics import _quat_xyzw_to_mat4_np as gui_quat_to_mat4
    from src.gui.rendering.gpu_core.diagnostics import _select_skin_3g_probe_vertices as gui_select_3g_probe_vertices
    from src.gui.rendering.gpu_core.diagnostics import _select_skin_probe_vertex as gui_select_probe_vertex
    from src.gui.rendering.gpu_core.diagnostics import _skin_bind_equivalence_record as gui_skin_bind_equivalence_record
    from src.gui.rendering.gpu_core.diagnostics import _skin_3g_candidate_records as gui_skin_3g_candidate_records
    from src.gui.rendering.gpu_core.diagnostics import _skin_3g_matrix_for_formula as gui_skin_3g_matrix_for_formula
    from src.gui.rendering.gpu_core.diagnostics import _skin_3g_role_for_bone as gui_skin_3g_role_for_bone
    from src.gui.rendering.gpu_core.diagnostics import _skin_3g_role_priority as gui_skin_3g_role_priority
    from src.gui.rendering.gpu_core.diagnostics import _skin_live_slot_records as gui_skin_live_slot_records
    from src.gui.rendering.gpu_core.diagnostics import _SKIN_3G_FORMULAS as gui_skin_3g_formulas
    from src.gui.rendering.gpu_core.diagnostics import _build_skin_dump_record as gui_build_skin_dump_record
    from src.gui.rendering.gpu_core.diagnostics import _should_auto_clamp_diffuse as gui_auto_clamp
    from src.gui.rendering.gpu_core.diagnostics import (
        _uploaded_palette_array_from_uploader as gui_uploaded_palette_array,
    )
    from src.gui.rendering.gpu_renderer import _build_gl_state_trace_record as public_gl_state_record
    from src.gui.rendering.gpu_renderer import _build_lm_data_dump_record as public_lm_data_record
    from src.gui.rendering.gpu_renderer import _first_divergence_stage as public_first_divergence_stage
    from src.gui.rendering.gpu_renderer import _homogeneous_position_json as public_homogeneous_position_json
    from src.gui.rendering.gpu_renderer import _matrix4_json as public_matrix4_json
    from src.gui.rendering.gpu_renderer import _matrix_max_abs_delta as public_matrix_max_abs_delta
    from src.gui.rendering.gpu_renderer import _matrix_rotation_only as public_matrix_rotation_only
    from src.gui.rendering.gpu_renderer import _matrix_translation_norm as public_matrix_translation_norm
    from src.gui.rendering.gpu_renderer import _node_pose_chain_records as public_node_pose_chain_records
    from src.gui.rendering.gpu_renderer import _node_parent_chain_names as public_parent_chain_names
    from src.gui.rendering.gpu_renderer import _node_world_matrix_for_pose_np as public_node_world_matrix
    from src.gui.rendering.gpu_renderer import _pose_node_transform as public_pose_node_transform
    from src.gui.rendering.gpu_renderer import _qbone_direct_bind_json as public_qbone_direct_bind_json
    from src.gui.rendering.gpu_renderer import _qbone_inverse_bind_json as public_qbone_inverse_bind_json
    from src.gui.rendering.gpu_renderer import _qbone_matrix_np as public_qbone_matrix_np
    from src.gui.rendering.gpu_renderer import _quat_xyzw_to_mat4_np as public_quat_to_mat4
    from src.gui.rendering.gpu_renderer import _select_skin_3g_probe_vertices as public_select_3g_probe_vertices
    from src.gui.rendering.gpu_renderer import _select_skin_probe_vertex as public_select_probe_vertex
    from src.gui.rendering.gpu_renderer import _skin_bind_equivalence_record as public_skin_bind_equivalence_record
    from src.gui.rendering.gpu_renderer import _skin_3g_candidate_records as public_skin_3g_candidate_records
    from src.gui.rendering.gpu_renderer import _skin_3g_matrix_for_formula as public_skin_3g_matrix_for_formula
    from src.gui.rendering.gpu_renderer import _skin_3g_role_for_bone as public_skin_3g_role_for_bone
    from src.gui.rendering.gpu_renderer import _skin_3g_role_priority as public_skin_3g_role_priority
    from src.gui.rendering.gpu_renderer import _skin_live_slot_records as public_skin_live_slot_records
    from src.gui.rendering.gpu_renderer import _SKIN_3G_FORMULAS as public_skin_3g_formulas
    from src.gui.rendering.gpu_renderer import _build_skin_dump_record as public_build_skin_dump_record
    from src.gui.rendering.gpu_renderer import _should_auto_clamp_diffuse as public_auto_clamp
    from src.gui.rendering.gpu_renderer import (
        _uploaded_palette_array_from_uploader as public_uploaded_palette_array,
    )
    from src.gui.rendering.gpu_renderer import (
        _xoreos_first_frame_orientation_matrix as public_xoreos_first_frame,
    )
    from src.gui.rendering.gpu_core.diagnostics import (
        _xoreos_first_frame_orientation_matrix as gui_xoreos_first_frame,
    )

    assert gui_auto_clamp is core_auto_clamp
    assert facade_auto_clamp is core_auto_clamp
    assert public_auto_clamp is core_auto_clamp
    assert gui_gl_state_record is core_gl_state_record
    assert facade_gl_state_record is core_gl_state_record
    assert public_gl_state_record is core_gl_state_record
    assert gui_lm_data_record is core_lm_data_record
    assert facade_lm_data_record is core_lm_data_record
    assert public_lm_data_record is core_lm_data_record
    assert gui_matrix4_json is core_matrix4_json
    assert facade_matrix4_json is core_matrix4_json
    assert public_matrix4_json is core_matrix4_json
    assert core_matrix4_json([[1, 2], [3.1234567, 4]]) == [[1.0, 2.0], [3.123457, 4.0]]
    assert gui_pose_node_transform is core_pose_node_transform
    assert facade_pose_node_transform is core_pose_node_transform
    assert public_pose_node_transform is core_pose_node_transform
    assert gui_select_probe_vertex is core_select_probe_vertex
    assert facade_select_probe_vertex is core_select_probe_vertex
    assert public_select_probe_vertex is core_select_probe_vertex
    assert gui_parent_chain_names is core_parent_chain_names
    assert facade_parent_chain_names is core_parent_chain_names
    assert public_parent_chain_names is core_parent_chain_names
    assert gui_uploaded_palette_array is core_uploaded_palette_array
    assert facade_uploaded_palette_array is core_uploaded_palette_array
    assert public_uploaded_palette_array is core_uploaded_palette_array
    assert gui_homogeneous_position_json is core_homogeneous_position_json
    assert facade_homogeneous_position_json is core_homogeneous_position_json
    assert public_homogeneous_position_json is core_homogeneous_position_json
    assert gui_first_divergence_stage is core_first_divergence_stage
    assert facade_first_divergence_stage is core_first_divergence_stage
    assert public_first_divergence_stage is core_first_divergence_stage
    assert gui_matrix_max_abs_delta is core_matrix_max_abs_delta
    assert facade_matrix_max_abs_delta is core_matrix_max_abs_delta
    assert public_matrix_max_abs_delta is core_matrix_max_abs_delta
    assert gui_matrix_translation_norm is core_matrix_translation_norm
    assert facade_matrix_translation_norm is core_matrix_translation_norm
    assert public_matrix_translation_norm is core_matrix_translation_norm
    assert gui_matrix_rotation_only is core_matrix_rotation_only
    assert facade_matrix_rotation_only is core_matrix_rotation_only
    assert public_matrix_rotation_only is core_matrix_rotation_only
    assert gui_qbone_inverse_bind_json is core_qbone_inverse_bind_json
    assert facade_qbone_inverse_bind_json is core_qbone_inverse_bind_json
    assert public_qbone_inverse_bind_json is core_qbone_inverse_bind_json
    assert gui_qbone_direct_bind_json is core_qbone_direct_bind_json
    assert facade_qbone_direct_bind_json is core_qbone_direct_bind_json
    assert public_qbone_direct_bind_json is core_qbone_direct_bind_json
    assert gui_qbone_matrix_np is core_qbone_matrix_np
    assert facade_qbone_matrix_np is core_qbone_matrix_np
    assert public_qbone_matrix_np is core_qbone_matrix_np
    assert gui_node_world_matrix is core_node_world_matrix
    assert facade_node_world_matrix is core_node_world_matrix
    assert public_node_world_matrix is core_node_world_matrix
    assert gui_node_pose_chain_records is core_node_pose_chain_records
    assert facade_node_pose_chain_records is core_node_pose_chain_records
    assert public_node_pose_chain_records is core_node_pose_chain_records
    assert gui_quat_to_mat4 is core_quat_to_mat4
    assert facade_quat_to_mat4 is core_quat_to_mat4
    assert public_quat_to_mat4 is core_quat_to_mat4
    assert gui_xoreos_first_frame is core_xoreos_first_frame
    assert facade_xoreos_first_frame is core_xoreos_first_frame
    assert public_xoreos_first_frame is core_xoreos_first_frame
    assert gui_skin_3g_formulas is core_skin_3g_formulas
    assert facade_skin_3g_formulas is core_skin_3g_formulas
    assert public_skin_3g_formulas is core_skin_3g_formulas
    assert gui_skin_3g_matrix_for_formula is core_skin_3g_matrix_for_formula
    assert facade_skin_3g_matrix_for_formula is core_skin_3g_matrix_for_formula
    assert public_skin_3g_matrix_for_formula is core_skin_3g_matrix_for_formula
    assert gui_skin_3g_role_for_bone is core_skin_3g_role_for_bone
    assert facade_skin_3g_role_for_bone is core_skin_3g_role_for_bone
    assert public_skin_3g_role_for_bone is core_skin_3g_role_for_bone
    assert gui_skin_3g_role_priority is core_skin_3g_role_priority
    assert facade_skin_3g_role_priority is core_skin_3g_role_priority
    assert public_skin_3g_role_priority is core_skin_3g_role_priority
    assert gui_select_3g_probe_vertices is core_select_3g_probe_vertices
    assert facade_select_3g_probe_vertices is core_select_3g_probe_vertices
    assert public_select_3g_probe_vertices is core_select_3g_probe_vertices
    assert gui_skin_bind_equivalence_record is core_skin_bind_equivalence_record
    assert facade_skin_bind_equivalence_record is core_skin_bind_equivalence_record
    assert public_skin_bind_equivalence_record is core_skin_bind_equivalence_record
    assert gui_skin_3g_candidate_records is core_skin_3g_candidate_records
    assert facade_skin_3g_candidate_records is core_skin_3g_candidate_records
    assert public_skin_3g_candidate_records is core_skin_3g_candidate_records
    assert gui_skin_live_slot_records is core_skin_live_slot_records
    assert facade_skin_live_slot_records is core_skin_live_slot_records
    assert public_skin_live_slot_records is core_skin_live_slot_records
    assert gui_build_skin_dump_record is core_build_skin_dump_record
    assert facade_build_skin_dump_record is core_build_skin_dump_record
    assert public_build_skin_dump_record is core_build_skin_dump_record

    core_source = (ROOT / "src/core/rendering/gpu_diagnostics_records.py").read_text(encoding="utf-8")
    for forbidden in ("src.gui.", "PySide6", "QtWidgets", "QtGui", "QtCore", "moderngl"):
        assert forbidden not in core_source

    diagnostics_source = (ROOT / "src/gui/rendering/gpu_core/diagnostics.py").read_text(encoding="utf-8")
    adapter_exports = (ROOT / "src/adapters/rendering/gpu_diagnostics_exports.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    assert '_TARGET = "src.adapters.rendering.gpu_diagnostics_exports"' in diagnostics_source
    assert '"src.core.rendering.gpu_diagnostics_records"' in adapter_exports
    assert "def __getattr__" in adapter_exports
    assert "_EXPORT_MODULES" not in adapter_exports
    assert "for _module_name in" not in adapter_exports
    assert "import *" not in adapter_exports
    assert "def _should_auto_clamp_diffuse" not in diagnostics_source
    assert "def _build_gl_state_trace_record" not in diagnostics_source
    assert "def _build_lm_data_dump_record" not in diagnostics_source
    assert "def _matrix4_json" not in diagnostics_source
    assert "def _pose_node_transform" not in diagnostics_source
    assert "def _select_skin_probe_vertex" not in diagnostics_source
    assert "def _node_parent_chain_names" not in diagnostics_source
    assert "def _uploaded_palette_array_from_uploader" not in diagnostics_source
    assert "def _homogeneous_position_json" not in diagnostics_source
    assert "def _first_divergence_stage" not in diagnostics_source
    assert "def _matrix_max_abs_delta" not in diagnostics_source
    assert "def _qbone_inverse_bind_json" not in diagnostics_source
    assert "def _qbone_matrix_np" not in diagnostics_source
    assert "def _node_world_matrix_for_pose_np" not in diagnostics_source
    assert "def _node_pose_chain_records" not in diagnostics_source
    assert "def _quat_xyzw_to_mat4_np" not in diagnostics_source
    assert "def _xoreos_first_frame_orientation_matrix" not in diagnostics_source
    assert "_SKIN_3G_FORMULAS = {" not in diagnostics_source
    assert "def _skin_3g_matrix_for_formula" not in diagnostics_source
    assert "def _skin_3g_role_for_bone" not in diagnostics_source
    assert "def _select_skin_3g_probe_vertices" not in diagnostics_source
    assert "def _skin_bind_equivalence_record" not in diagnostics_source
    assert "def _skin_3g_candidate_records" not in diagnostics_source
    assert "def _skin_live_slot_records" not in diagnostics_source
    assert "def _build_skin_dump_record" not in diagnostics_source
    assert '"_should_auto_clamp_diffuse": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_build_gl_state_trace_record": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_build_lm_data_dump_record": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_matrix4_json": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_pose_node_transform": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_select_skin_probe_vertex": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_node_parent_chain_names": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_uploaded_palette_array_from_uploader": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_homogeneous_position_json": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_matrix_rotation_only": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_qbone_matrix_np": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_node_world_matrix_for_pose_np": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_quat_xyzw_to_mat4_np": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_xoreos_first_frame_orientation_matrix": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_SKIN_3G_FORMULAS": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_skin_3g_matrix_for_formula": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_select_skin_3g_probe_vertices": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_skin_bind_equivalence_record": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_skin_3g_candidate_records": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_skin_live_slot_records": "src.core.rendering.gpu_diagnostics_records"' in public_facade
    assert '"_build_skin_dump_record": "src.core.rendering.gpu_diagnostics_records"' in public_facade


def test_renderer_color_utils_are_backend_owned() -> None:
    """Shared renderer color parsing should not be duplicated in GUI adapters."""
    from src.core.qt_core.rendering.color_utils import _hex_to_rgb_float as facade_hex_to_rgb
    from src.core.rendering.color_utils import _hex_to_rgb_float as core_hex_to_rgb
    from src.core.rendering.wgpu_shared import _hex_to_rgb_float as wgpu_hex_to_rgb
    from src.gui.rendering.gpu_core.diagnostics import _hex_to_rgb_float as gpu_diag_hex_to_rgb
    from src.gui.rendering.gpu_renderer import _hex_to_rgb_float as gpu_public_hex_to_rgb
    from src.gui.rendering.wgpu_renderer import _hex_to_rgb_float as wgpu_public_hex_to_rgb

    assert core_hex_to_rgb("#336699", (0.0, 0.0, 0.0)) == (0.2, 0.4, 0.6)
    assert core_hex_to_rgb("bad", (0.1, 0.2, 0.3)) == (0.1, 0.2, 0.3)
    assert facade_hex_to_rgb is core_hex_to_rgb
    assert wgpu_hex_to_rgb is core_hex_to_rgb
    assert gpu_diag_hex_to_rgb is core_hex_to_rgb
    assert gpu_public_hex_to_rgb is core_hex_to_rgb
    assert wgpu_public_hex_to_rgb is core_hex_to_rgb

    core_source = (ROOT / "src/core/rendering/color_utils.py").read_text(encoding="utf-8")
    for forbidden in ("src.gui.", "PySide6", "QtWidgets", "QtGui", "QtCore", "moderngl", "wgpu"):
        assert forbidden not in core_source

    diagnostics_source = (ROOT / "src/gui/rendering/gpu_core/diagnostics.py").read_text(encoding="utf-8")
    wgpu_shared_source = (ROOT / "src/core/rendering/wgpu_shared.py").read_text(encoding="utf-8")
    gpu_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    wgpu_facade = (ROOT / "src/adapters/rendering/wgpu_renderer_exports.py").read_text(encoding="utf-8")
    assert "from src.core.rendering.color_utils import *" in diagnostics_source
    assert "from src.core.rendering.color_utils import _hex_to_rgb_float" in wgpu_shared_source
    assert "def _hex_to_rgb_float" not in diagnostics_source
    assert "def _hex_to_rgb_float" not in wgpu_shared_source
    assert '"_hex_to_rgb_float": "src.core.rendering.color_utils"' in gpu_facade
    assert '"_hex_to_rgb_float": "src.core.rendering.color_utils"' in wgpu_facade


def test_gpu_vbo_layout_helpers_are_backend_owned() -> None:
    """VBO layout constants and split helpers belong to core rendering."""
    import numpy as np

    from src.core.qt_core.rendering.gpu_vbo_layout import (
        _VBO_BONE_IDS_FORMAT as facade_bone_ids_format,
        _VBO_MAIN_FORMAT as facade_main_format,
        _split_vbo_attributes_for_gpu as facade_split_vbo_attributes,
    )
    from src.core.rendering.gpu_vbo_layout import (
        _VBO_BONE_IDS_FORMAT as core_bone_ids_format,
        _VBO_MAIN_FORMAT as core_main_format,
        _split_vbo_attributes_for_gpu as core_split_vbo_attributes,
    )
    from src.adapters.rendering.moderngl_resources import (
        _split_vbo_attributes_for_gpu as adapter_split_vbo_attributes,
    )
    from src.gui.rendering.gpu_core.resources import (
        _split_vbo_attributes_for_gpu as gui_split_vbo_attributes,
    )
    from src.gui.rendering.gpu_renderer import (
        _VBO_BONE_IDS_FORMAT as public_bone_ids_format,
        _VBO_MAIN_FORMAT as public_main_format,
        _split_vbo_attributes_for_gpu as public_split_vbo_attributes,
    )

    assert facade_main_format == core_main_format == public_main_format == "3f 3f 2f 2f 4f 4f"
    assert facade_bone_ids_format == core_bone_ids_format == public_bone_ids_format == "4i"
    assert adapter_split_vbo_attributes is core_split_vbo_attributes
    assert gui_split_vbo_attributes is core_split_vbo_attributes
    assert facade_split_vbo_attributes is core_split_vbo_attributes
    assert public_split_vbo_attributes is core_split_vbo_attributes

    rows = np.zeros((2, 22), dtype=np.float32)
    rows[:, 14:18] = [[1.2, 2.0, 3.8, 4.0], [5.0, 6.4, 7.0, 8.0]]
    rows[:, 18:22] = [[0.5, 0.25, 0.25, 0.0], [1.0, 0.0, 0.0, 0.0]]
    main, bone_ids = core_split_vbo_attributes(rows)
    assert main.dtype.name == "float32"
    assert bone_ids.dtype.name == "int32"
    assert main.shape == (2, 18)
    assert bone_ids.tolist() == [[1, 2, 4, 4], [5, 6, 7, 8]]
    assert main[:, 14:18].tolist() == rows[:, 18:22].tolist()

    core_source = (ROOT / "src/core/rendering/gpu_vbo_layout.py").read_text(encoding="utf-8")
    adapter_resources_source = (ROOT / "src/adapters/rendering/moderngl_resources.py").read_text(encoding="utf-8")
    resources_source = (ROOT / "src/gui/rendering/gpu_core/resources.py").read_text(encoding="utf-8")
    adapter_resources_source = (ROOT / "src/adapters/rendering/moderngl_resources.py").read_text(encoding="utf-8")
    renderer_source = (ROOT / "src/adapters/rendering/moderngl_renderer_impl.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    records_source = (ROOT / "src/core/rendering/gpu_diagnostics_records.py").read_text(encoding="utf-8")

    assert "src.gui." not in core_source
    assert "src.gui." not in adapter_resources_source
    assert "def _split_vbo_attributes_for_gpu" not in resources_source
    assert 'import_module("src.adapters.rendering.moderngl_resources")' in resources_source
    assert "sys.modules[__name__] = _module" in resources_source
    assert "import *" not in resources_source
    assert "from src.core.rendering.gpu_vbo_layout import _split_vbo_attributes_for_gpu" in adapter_resources_source
    assert "from src.adapters.rendering.moderngl_resources import (" in renderer_source
    assert "from src.adapters.rendering.moderngl_resources import *" not in renderer_source
    assert "from src.math.gpu_math import (" in renderer_source
    assert "from src.math.gpu_math import *" not in renderer_source
    assert '"_split_vbo_attributes_for_gpu": "src.core.rendering.gpu_vbo_layout"' in public_facade
    assert "from src.core.rendering.gpu_vbo_layout import _VBO_BONE_IDS_FORMAT, _VBO_MAIN_FORMAT" in records_source


def test_wgpu_shader_sources_are_backend_owned() -> None:
    """WGPU shader source loading and fallback strings belong to core rendering."""
    import sys

    import src.core.rendering.wgpu_shaders as core_wgpu_shaders_module
    import src.gui.rendering.wgpu_core.shaders as gui_wgpu_shaders_module

    from src.core.qt_core.rendering.wgpu_shaders import _GRID_WGSL as facade_grid_wgsl
    from src.core.rendering.wgpu_shaders import _GRID_WGSL as core_grid_wgsl
    from src.core.rendering.wgpu_shaders import _load_mesh_shader as core_load_mesh_shader
    from src.gui.rendering.wgpu_core.shaders import _GRID_WGSL as gui_grid_wgsl
    from src.gui.rendering.wgpu_renderer import _GRID_WGSL as public_grid_wgsl
    from src.gui.rendering.wgpu_renderer import _load_mesh_shader as public_load_mesh_shader

    assert gui_grid_wgsl is core_grid_wgsl
    assert facade_grid_wgsl is core_grid_wgsl
    assert public_grid_wgsl is core_grid_wgsl
    assert public_load_mesh_shader is core_load_mesh_shader
    assert "scene_lights" in core_load_mesh_shader()
    assert gui_wgpu_shaders_module is core_wgpu_shaders_module
    assert sys.modules["src.gui.rendering.wgpu_core.shaders"] is core_wgpu_shaders_module

    core_source = (ROOT / "src/core/rendering/wgpu_shaders.py").read_text(encoding="utf-8")
    assert "src.gui." not in core_source
    assert "PySide6" not in core_source
    assert "QtWidgets" not in core_source
    assert "QtGui" not in core_source
    assert "QtCore" not in core_source
    assert "from .shared import" not in core_source
    assert (ROOT / "src/core/rendering/shaders/wgpu_mesh_textured.wgsl").exists()
    assert (ROOT / "src/core/rendering/shaders/wgpu_mesh_skinned.wgsl").exists()
    assert not (ROOT / "src/gui/rendering/shaders/wgpu_mesh_textured.wgsl").exists()
    assert not (ROOT / "src/gui/rendering/shaders/wgpu_mesh_skinned.wgsl").exists()

    renderer_source = (ROOT / "src/adapters/rendering/wgpu_core/renderer.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/wgpu_renderer_exports.py").read_text(encoding="utf-8")
    gui_facade = (ROOT / "src/gui/rendering/wgpu_core/shaders.py").read_text(encoding="utf-8")
    assert "from src.core.rendering.wgpu_shaders import (" in renderer_source
    assert "from src.core.rendering.wgpu_shaders import *" not in renderer_source
    assert '"_load_mesh_shader": "src.core.rendering.wgpu_shaders"' in public_facade
    assert "src.gui.rendering.wgpu_core.shaders" not in public_facade
    assert 'import_module("src.core.rendering.wgpu_shaders")' in gui_facade
    assert "sys.modules[__name__] = _module" in gui_facade
    assert "globals().update" not in gui_facade


def test_wgpu_shared_dtos_and_helpers_are_backend_owned() -> None:
    """WGPU resource DTOs and pure helper functions belong to core rendering."""
    from src.core.qt_core.rendering.wgpu_shared import WgpuMeshResource as FacadeWgpuMeshResource
    from src.core.rendering.wgpu_shared import WgpuMeshResource as CoreWgpuMeshResource
    from src.core.rendering.wgpu_shared import _WgpuBackendSpec as CoreBackendSpec
    from src.core.rendering.wgpu_shared import _format_is_srgb as core_format_is_srgb
    from src.core.rendering.wgpu_shared import _mat4_perspective_wgpu as core_mat4_perspective
    from src.core.rendering.wgpu_shared import _srgb_to_linear as core_srgb_to_linear
    from src.gui.rendering.wgpu_core.shared import WgpuMeshResource as GuiWgpuMeshResource
    from src.gui.rendering.wgpu_core.shared import _WgpuBackendSpec as GuiBackendSpec
    from src.gui.rendering.wgpu_core.shared import _format_is_srgb as gui_format_is_srgb
    from src.gui.rendering.wgpu_renderer import WgpuMeshResource as PublicWgpuMeshResource
    from src.gui.rendering.wgpu_renderer import _format_is_srgb as public_format_is_srgb
    from src.gui.rendering.wgpu_renderer import _srgb_to_linear as public_srgb_to_linear

    assert GuiWgpuMeshResource is CoreWgpuMeshResource
    assert FacadeWgpuMeshResource is CoreWgpuMeshResource
    assert PublicWgpuMeshResource is CoreWgpuMeshResource
    assert GuiBackendSpec is CoreBackendSpec
    assert gui_format_is_srgb is core_format_is_srgb
    assert public_format_is_srgb is core_format_is_srgb
    assert public_srgb_to_linear is core_srgb_to_linear
    assert core_format_is_srgb("rgba8unorm-srgb")
    assert not core_format_is_srgb("rgba8unorm")
    assert core_srgb_to_linear((1.0, 0.5, 0.0))[0] == 1.0
    assert core_mat4_perspective(1.0, 1.0, 0.1, 100.0).shape == (4, 4)

    core_source = (ROOT / "src/core/rendering/wgpu_shared.py").read_text(encoding="utf-8")
    for forbidden in ("src.gui.", "PySide6", "QtWidgets", "QtGui", "QtCore", "rendercanvas", "import wgpu"):
        assert forbidden not in core_source

    gui_shared_source = (ROOT / "src/gui/rendering/wgpu_core/shared.py").read_text(encoding="utf-8")
    adapter_shared_source = (ROOT / "src/adapters/rendering/wgpu_core/shared.py").read_text(encoding="utf-8")
    public_facade = (ROOT / "src/adapters/rendering/wgpu_renderer_exports.py").read_text(encoding="utf-8")
    assert 'import_module("src.adapters.rendering.wgpu_core.shared")' in gui_shared_source
    assert "from src.core.rendering.wgpu_shared import (" in adapter_shared_source
    assert "from src.core.rendering.wgpu_shared import *" not in adapter_shared_source
    assert '"WgpuMeshResource": "src.core.rendering.wgpu_shared"' in public_facade
    assert '"_srgb_to_linear": "src.core.rendering.wgpu_shared"' in public_facade


def test_lightmap_export_bridge_is_backend_owned() -> None:
    """Generated-lightmap export manifests belong to core lighting."""
    import sys

    import src.core.lighting.lightmap_export_bridge as core_export_bridge_module
    import src.gui.lighting.lightmap_export_bridge as gui_export_bridge_module

    from src.core.lighting.lightmap_export_bridge import (
        export_baked_lightmap_manifest as core_export_manifest,
    )
    from src.gui.lighting.lightmap_export_bridge import (
        export_baked_lightmap_manifest as gui_export_manifest,
    )

    assert gui_export_manifest is core_export_manifest
    assert gui_export_bridge_module is core_export_bridge_module
    assert sys.modules["src.gui.lighting.lightmap_export_bridge"] is core_export_bridge_module
    gui_source = (ROOT / "src/gui/lighting/lightmap_export_bridge.py").read_text(encoding="utf-8")
    assert 'import_module("src.core.lighting.lightmap_export_bridge")' in gui_source
    assert "sys.modules[__name__] = _module" in gui_source
    assert "import *" not in gui_source
    assert "src.gui.lighting.lightmap_export_bridge" not in (
        ROOT / "src/converters/mesh_converter.py"
    ).read_text(encoding="utf-8")


def test_lightmap_bake_support_helpers_are_backend_owned() -> None:
    """Headless lightmap bake support helpers belong to core lighting."""
    from importlib import import_module
    import sys

    from src.core.lighting.lightmap_bake_job import LightmapBakeJob as CoreLightmapBakeJob
    from src.core.lighting.lightmap_bake_settings import LightmapBakeSettings as CoreLightmapBakeSettings
    from src.core.lighting.lightmap_padding import LightmapPadding as CoreLightmapPadding
    from src.core.lighting.lightmap_rasterizer import LightmapRasterizer as CoreLightmapRasterizer
    from src.core.lighting.lightmap_uv_validator import LightmapUVValidator as CoreLightmapUVValidator
    from src.core.lighting.uv_atlas_generator import UVAtlasGenerator as CoreUVAtlasGenerator
    from src.core.qt_core.lighting.lightmap_bake_job import LightmapBakeJob as FacadeLightmapBakeJob
    from src.gui.lighting.lightmap_bake_job import LightmapBakeJob as GuiLightmapBakeJob
    from src.gui.lighting.lightmap_bake_settings import LightmapBakeSettings as GuiLightmapBakeSettings
    from src.gui.lighting.lightmap_padding import LightmapPadding as GuiLightmapPadding
    from src.gui.lighting.lightmap_rasterizer import LightmapRasterizer as GuiLightmapRasterizer
    from src.gui.lighting.lightmap_uv_validator import LightmapUVValidator as GuiLightmapUVValidator
    from src.gui.lighting.uv_atlas_generator import UVAtlasGenerator as GuiUVAtlasGenerator

    assert GuiLightmapBakeJob is CoreLightmapBakeJob
    assert FacadeLightmapBakeJob is CoreLightmapBakeJob
    assert GuiLightmapBakeSettings is CoreLightmapBakeSettings
    assert GuiLightmapPadding is CoreLightmapPadding
    assert GuiLightmapRasterizer is CoreLightmapRasterizer
    assert GuiLightmapUVValidator is CoreLightmapUVValidator
    assert GuiUVAtlasGenerator is CoreUVAtlasGenerator

    support_modules = (
        "lightmap_bake_job",
        "lightmap_bake_settings",
        "lightmap_compare",
        "lightmap_denoiser",
        "lightmap_lighting_solver",
        "lightmap_manifest",
        "lightmap_output",
        "lightmap_padding",
        "lightmap_rasterizer",
        "lightmap_sampler",
        "lightmap_shadow_solver",
        "lightmap_uv_validator",
        "raycast_backend",
        "uv_atlas_generator",
        "uv_channel_info",
    )
    for module_name in support_modules:
        core_module = import_module(f"src.core.lighting.{module_name}")
        gui_module = import_module(f"src.gui.lighting.{module_name}")
        assert gui_module is core_module
        assert sys.modules[f"src.gui.lighting.{module_name}"] is core_module

        filename = f"{module_name}.py"
        assert "src.gui." not in (ROOT / "src/core/lighting" / filename).read_text(encoding="utf-8")
        gui_source = (ROOT / "src/gui/lighting" / filename).read_text(encoding="utf-8")
        assert f'import_module("src.core.lighting.{module_name}")' in gui_source
        assert "sys.modules[__name__] = _module" in gui_source
        assert "import *" not in gui_source

    for source_path in (
        "src/gui/lighting/lightmap_baker.py",
        "src/gui/lighting/lightmap_bake_worker.py",
        "src/gui/dialogs/lightmap_bake_worker.py",
        "src/gui/dialogs/qt_lightmap_baker_dialog.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.gui.lighting.lightmap_bake_job" not in source
        assert "src.gui.lighting.lightmap_bake_settings" not in source
        assert "src.gui.lighting.lightmap_uv_validator" not in source


def test_lighting_domain_and_render_data_are_backend_owned() -> None:
    """Lighting domain records, settings, and render snapshots belong to core lighting."""
    from importlib import import_module
    import sys

    import src.gui.lighting as gui_lighting_package
    from src.core.lighting.light_gizmo_renderer import LIGHT_HELPER_COLORS as CoreLightHelperColors
    from src.core.lighting.light_manager import LightManager as CoreLightManager
    from src.core.lighting.light_model import GhostRiggerLight as CoreGhostRiggerLight
    from src.core.lighting.light_types import SceneLightingMode as CoreSceneLightingMode
    from src.core.lighting.render_data import SceneLightingRenderData as CoreSceneLightingRenderData
    from src.core.lighting.settings import LightingSettings as CoreLightingSettings
    from src.core.qt_core.lighting.light_model import GhostRiggerLight as FacadeGhostRiggerLight
    from src.gui.lighting.light_gizmo_renderer import LIGHT_HELPER_COLORS as GuiLightHelperColors
    from src.gui.lighting.light_manager import LightManager as GuiLightManager
    from src.gui.lighting.light_model import GhostRiggerLight as GuiGhostRiggerLight
    from src.gui.lighting.light_types import SceneLightingMode as GuiSceneLightingMode
    from src.gui.lighting.render_data import SceneLightingRenderData as GuiSceneLightingRenderData
    from src.gui.lighting.settings import LightingSettings as GuiLightingSettings

    assert GuiGhostRiggerLight is CoreGhostRiggerLight
    assert FacadeGhostRiggerLight is CoreGhostRiggerLight
    assert GuiLightManager is CoreLightManager
    assert GuiSceneLightingMode is CoreSceneLightingMode
    assert GuiSceneLightingRenderData is CoreSceneLightingRenderData
    assert GuiLightingSettings is CoreLightingSettings
    assert GuiLightHelperColors is CoreLightHelperColors
    assert gui_lighting_package.GhostRiggerLight is CoreGhostRiggerLight
    assert gui_lighting_package.LightManager is CoreLightManager
    assert gui_lighting_package.SceneLightingMode is CoreSceneLightingMode
    lighting_package_source = (ROOT / "src/gui/lighting/__init__.py").read_text(encoding="utf-8")
    assert '"GhostRiggerLight": "src.core.lighting.light_model"' in lighting_package_source
    assert '"SceneLightingMode": "src.core.lighting.light_types"' in lighting_package_source
    assert "def __getattr__" in lighting_package_source
    assert "from src.core.lighting" not in lighting_package_source

    domain_modules = (
        "aurora_light_adapter",
        "light_export_bridge",
        "light_gizmo_renderer",
        "light_grouping",
        "light_manager",
        "light_model",
        "light_selection",
        "light_types",
        "lighting_rig_presets",
        "render_data",
        "settings",
        "shader_complexity",
    )
    for module_name in domain_modules:
        core_module = import_module(f"src.core.lighting.{module_name}")
        gui_module = import_module(f"src.gui.lighting.{module_name}")
        assert gui_module is core_module
        assert sys.modules[f"src.gui.lighting.{module_name}"] is core_module

        filename = f"{module_name}.py"
        assert "src.gui." not in (ROOT / "src/core/lighting" / filename).read_text(encoding="utf-8")
        gui_source = (ROOT / "src/gui/lighting" / filename).read_text(encoding="utf-8")
        assert f'import_module("src.core.lighting.{module_name}")' in gui_source
        assert "sys.modules[__name__] = _module" in gui_source
        assert "import *" not in gui_source

    for source_path in (
        "src/gui/panels/qt_lighting_panel.py",
        "src/gui/rendering/wgpu_core/shared.py",
        "src/gui/rendering/wgpu_core/renderer.py",
        "src/gui/rendering/gpu_core/diagnostics.py",
        "src/gui/lighting/light_picker.py",
        "src/gui/lighting/lightmap_baker.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.gui.lighting.light_model" not in source
        assert "src.gui.lighting.light_types" not in source
        assert "src.gui.lighting.light_gizmo_renderer" not in source
        assert "src.gui.lighting.render_data" not in source

    old_lighting_facade_imports = []
    old_lighting_facades = (
        "src.gui.qt_lib.lighting.lightmap_uv_validator",
        "src.gui.qt_lib.lighting.lightmap_compare",
        "src.gui.qt_lib.lighting.render_data",
    )
    for source_path in (ROOT / "src").rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        if any(facade in source for facade in old_lighting_facades):
            old_lighting_facade_imports.append(str(source_path.relative_to(ROOT)))
    assert old_lighting_facade_imports == []


def test_lighting_preview_state_and_cache_are_backend_owned() -> None:
    """Lightmap preview state, material-map state, and preview cache belong to core lighting."""
    from importlib import import_module
    import sys

    from src.core.lighting.lightmap_controller import LightmapController as CoreLightmapController
    from src.core.lighting.material_map_controller import MaterialMapController as CoreMaterialMapController
    from src.core.lighting.preview_cache import LightmapPreviewCache as CoreLightmapPreviewCache
    from src.core.qt_core.lighting.lightmap_controller import LightmapController as FacadeLightmapController
    from src.core.qt_core.lighting.material_map_controller import MaterialMapController as FacadeMaterialMapController
    from src.core.qt_core.lighting.preview_cache import LightmapPreviewCache as FacadeLightmapPreviewCache
    from src.adapters.qt_viewport.lighting_viewport_controller import LightingViewportController as AdapterLightingViewportController
    from src.gui.lighting.lightmap_controller import LightmapController as GuiLightmapController
    from src.gui.lighting.lighting_viewport_controller import LightingViewportController as GuiLightingViewportController
    from src.gui.lighting.material_map_controller import MaterialMapController as GuiMaterialMapController
    from src.gui.lighting.preview_cache import LightmapPreviewCache as GuiLightmapPreviewCache

    assert GuiLightmapController is CoreLightmapController
    assert FacadeLightmapController is CoreLightmapController
    assert GuiMaterialMapController is CoreMaterialMapController
    assert FacadeMaterialMapController is CoreMaterialMapController
    assert GuiLightmapPreviewCache is CoreLightmapPreviewCache
    assert FacadeLightmapPreviewCache is CoreLightmapPreviewCache
    assert GuiLightingViewportController is AdapterLightingViewportController
    lighting_adapter_module = import_module("src.adapters.qt_viewport.lighting_viewport_controller")
    lighting_gui_module = import_module("src.gui.lighting.lighting_viewport_controller")
    assert lighting_gui_module is lighting_adapter_module
    assert sys.modules["src.gui.lighting.lighting_viewport_controller"] is lighting_adapter_module

    material_maps = CoreMaterialMapController()
    material_maps.set_enabled("env", False)
    assert material_maps.environment is False
    assert material_maps.to_renderer_attrs()["show_environment_map"] is False

    controller = CoreLightmapController()
    controller.set_settings(9.0, "hybrid")
    assert controller.intensity == 4.0
    assert controller.enabled is True

    cache = CoreLightmapPreviewCache(max_entries=1)
    cache.put("a", object())
    cache.put("b", object())
    assert cache.get("a") is None
    assert cache.get("b") is not None

    for module_name in ("lightmap_controller", "material_map_controller", "preview_cache"):
        core_module = import_module(f"src.core.lighting.{module_name}")
        gui_module = import_module(f"src.gui.lighting.{module_name}")
        assert gui_module is core_module
        assert sys.modules[f"src.gui.lighting.{module_name}"] is core_module

        filename = f"{module_name}.py"
        assert "src.gui." not in (ROOT / "src/core/lighting" / filename).read_text(encoding="utf-8")
        gui_source = (ROOT / "src/gui/lighting" / filename).read_text(encoding="utf-8")
        assert f'import_module("src.core.lighting.{module_name}")' in gui_source
        assert "sys.modules[__name__] = _module" in gui_source
        assert "import *" not in gui_source

    for source_path in (
        "src/gui/lighting/lightmap_baker.py",
        "src/gui/lighting/lighting_viewport_controller.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.gui.lighting.lightmap_controller" not in source
        assert "src.gui.lighting.material_map_controller" not in source
        assert "src.gui.lighting.preview_cache" not in source

    adapter_source = (ROOT / "src/adapters/qt_viewport/lighting_viewport_controller.py").read_text(encoding="utf-8")
    gui_source = (ROOT / "src/gui/lighting/lighting_viewport_controller.py").read_text(encoding="utf-8")
    assert "class LightingViewportController" in adapter_source
    assert "from src.core.lighting.lightmap_controller import LightmapController" in adapter_source
    assert "from src.core.lighting.material_map_controller import MaterialMapController" in adapter_source
    assert "src.gui." not in adapter_source
    assert 'import_module("src.adapters.qt_viewport.lighting_viewport_controller")' in gui_source
    assert "sys.modules[__name__] = _module" in gui_source
    assert "import *" not in gui_source


def test_lightmap_baker_pipeline_is_backend_owned_with_gui_gpu_adapter() -> None:
    """The lightmap bake pipeline belongs to core; the GUI path only injects the GPU solver default."""
    from src.adapters.gpu.lightmap_baker import LightmapBaker as AdapterLightmapBaker
    from src.adapters.gpu.lightmap_gpu_solver import LightmapGpuSolver
    from src.core.lighting.lightmap_baker import LightmapBaker as CoreLightmapBaker
    from src.core.lighting.lightmap_lighting_solver import LightmapLightingSolver
    from src.core.qt_core.lighting.lightmap_baker import LightmapBaker as FacadeLightmapBaker
    from src.gui.lighting.lightmap_baker import LightmapBaker as GuiLightmapBaker

    assert FacadeLightmapBaker is CoreLightmapBaker
    assert GuiLightmapBaker is AdapterLightmapBaker
    assert issubclass(AdapterLightmapBaker, CoreLightmapBaker)
    assert AdapterLightmapBaker is not CoreLightmapBaker
    assert isinstance(CoreLightmapBaker().lighting_solver, LightmapLightingSolver)
    assert not isinstance(CoreLightmapBaker().lighting_solver, LightmapGpuSolver)
    assert isinstance(AdapterLightmapBaker().lighting_solver, LightmapGpuSolver)

    core_source = (ROOT / "src/core/lighting/lightmap_baker.py").read_text(encoding="utf-8")
    for forbidden in ("src.gui.", "PySide6", "QtWidgets", "QtGui", "QtCore", "LightmapGpuSolver"):
        assert forbidden not in core_source

    adapter_source = (ROOT / "src/adapters/gpu/lightmap_baker.py").read_text(encoding="utf-8")
    assert "from src.core.lighting.lightmap_baker import LightmapBaker as _CoreLightmapBaker" in adapter_source
    assert "from src.adapters.gpu.lightmap_gpu_solver import LightmapGpuSolver" in adapter_source
    assert "LightmapGpuSolver(LightmapLightingSolver())" in adapter_source
    assert "src.gui." not in adapter_source

    gui_source = (ROOT / "src/gui/lighting/lightmap_baker.py").read_text(encoding="utf-8")
    assert 'import_module("src.adapters.gpu.lightmap_baker")' in gui_source
    assert "sys.modules[__name__] = _module" in gui_source
    assert "class LightmapBaker" not in gui_source
    assert "LightmapGpuSolver" not in gui_source

    worker_source = (ROOT / "src/gui/dialogs/lightmap_bake_worker.py").read_text(encoding="utf-8")
    worker_facade_source = (ROOT / "src/gui/lighting/lightmap_bake_worker.py").read_text(encoding="utf-8")
    dialog_source = (ROOT / "src/gui/dialogs/qt_lightmap_baker_dialog.py").read_text(encoding="utf-8")
    assert "from src.adapters.gpu.lightmap_baker import LightmapBaker" in worker_source
    assert "from src.adapters.gpu.lightmap_baker import LightmapBaker" in dialog_source
    assert "from .lightmap_baker import LightmapBaker" not in worker_source
    assert 'import_module("src.gui.dialogs.lightmap_bake_worker")' in worker_facade_source
    assert "sys.modules[__name__] = _module" in worker_facade_source
    assert "import *" not in worker_facade_source
    assert "class LightmapBakeWorker" not in worker_facade_source
    assert "from src.gui.lighting.lightmap_baker import LightmapBaker" not in dialog_source
    assert "from src.gui.lighting.lightmap_bake_worker import" not in dialog_source


def test_lightmap_gpu_solver_is_explicit_gpu_adapter() -> None:
    """The ModernGL lightmap solver is a GPU adapter, not GUI lighting product logic."""
    import sys

    import src.adapters.gpu.lightmap_gpu_solver as adapter_lightmap_gpu_solver_module
    import src.gui.lighting.lightmap_gpu_solver as gui_lightmap_gpu_solver_module

    from src.adapters.gpu.lightmap_gpu_solver import LightmapGpuSolver as AdapterLightmapGpuSolver
    from src.adapters.gpu.moderngl_context import _create_moderngl_standalone_context
    from src.adapters.gpu.moderngl_runtime import _MODERNGL as AdapterModernGLAvailable
    from src.adapters.gpu.viewport_probe import _gr_gpu_probe as AdapterGpuProbe
    from src.gui.lighting.lightmap_gpu_solver import LightmapGpuSolver as GuiLightmapGpuSolver
    from src.gui.rendering.gpu_core.diagnostics import _MODERNGL as GuiDiagnosticsModernGLAvailable
    from src.gui.rendering.gpu_core.diagnostics import _gr_gpu_probe as GuiDiagnosticsGpuProbe
    from src.gui.rendering.gpu_renderer import (
        _create_moderngl_standalone_context as PublicCreateModernGLContext,
    )
    from src.gui.rendering.gpu_renderer import _gr_gpu_probe as PublicGpuProbe
    from src.gui.qt_lib.lighting.lightmap_gpu_solver import LightmapGpuSolver as QtLibLightmapGpuSolver

    assert GuiLightmapGpuSolver is AdapterLightmapGpuSolver
    assert gui_lightmap_gpu_solver_module is adapter_lightmap_gpu_solver_module
    assert sys.modules["src.gui.lighting.lightmap_gpu_solver"] is adapter_lightmap_gpu_solver_module
    assert QtLibLightmapGpuSolver is AdapterLightmapGpuSolver
    assert PublicCreateModernGLContext is _create_moderngl_standalone_context
    assert GuiDiagnosticsModernGLAvailable is AdapterModernGLAvailable
    assert GuiDiagnosticsGpuProbe is AdapterGpuProbe
    assert PublicGpuProbe is AdapterGpuProbe

    adapter_source = (ROOT / "src/adapters/gpu/lightmap_gpu_solver.py").read_text(encoding="utf-8")
    context_source = (ROOT / "src/adapters/gpu/moderngl_context.py").read_text(encoding="utf-8")
    runtime_source = (ROOT / "src/adapters/gpu/moderngl_runtime.py").read_text(encoding="utf-8")
    probe_source = (ROOT / "src/adapters/gpu/viewport_probe.py").read_text(encoding="utf-8")
    gui_diagnostics_source = (ROOT / "src/gui/rendering/gpu_core/diagnostics.py").read_text(encoding="utf-8")
    gui_facade_source = (ROOT / "src/gui/lighting/lightmap_gpu_solver.py").read_text(encoding="utf-8")
    gui_baker_source = (ROOT / "src/gui/lighting/lightmap_baker.py").read_text(encoding="utf-8")
    adapter_baker_source = (ROOT / "src/adapters/gpu/lightmap_baker.py").read_text(encoding="utf-8")
    public_facade_source = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    renderer_source = (ROOT / "src/adapters/rendering/moderngl_renderer_impl.py").read_text(encoding="utf-8")
    resources_source = (ROOT / "src/gui/rendering/gpu_core/resources.py").read_text(encoding="utf-8")
    adapter_resources_source = (ROOT / "src/adapters/rendering/moderngl_resources.py").read_text(encoding="utf-8")

    assert "from src.core.lighting.lightmap_lighting_solver import LightmapLightingSolver" in adapter_source
    assert "from src.adapters.gpu.moderngl_context import _create_moderngl_standalone_context" in adapter_source
    assert "from src.gui.qt_lib.rendering.gpu_renderer import _create_moderngl_standalone_context" not in adapter_source
    assert "from src.core.rendering.gpu_diagnostics_config import _GL_BACKEND_ENV" in context_source
    assert "src.gui." not in context_source
    assert "src.gui." not in runtime_source
    assert "src.gui." not in probe_source
    assert "def _create_moderngl_standalone_context" not in gui_diagnostics_source
    assert "def _gr_gpu_probe" not in gui_diagnostics_source
    assert "import numpy as np" not in gui_diagnostics_source
    diagnostics_exports_source = (ROOT / "src/adapters/rendering/gpu_diagnostics_exports.py").read_text(
        encoding="utf-8"
    )
    assert '_TARGET = "src.adapters.rendering.gpu_diagnostics_exports"' in gui_diagnostics_source
    assert '"src.adapters.gpu.moderngl_runtime"' in diagnostics_exports_source
    assert '"src.adapters.gpu.viewport_probe"' in diagnostics_exports_source
    assert "def __getattr__" in diagnostics_exports_source
    assert "_EXPORT_MODULES" not in diagnostics_exports_source
    assert "for _module_name in" not in diagnostics_exports_source
    assert "import *" not in diagnostics_exports_source
    assert '"_create_moderngl_standalone_context": "src.adapters.gpu.moderngl_context"' in public_facade_source
    assert '"_gr_gpu_probe": "src.adapters.gpu.viewport_probe"' in public_facade_source
    assert "from .diagnostics import *" not in renderer_source
    assert "from .diagnostics import *" not in resources_source
    assert "from src.adapters.gpu.moderngl_runtime import" in renderer_source
    assert "from src.adapters.gpu.moderngl_runtime import" in adapter_resources_source
    assert 'import_module("src.adapters.rendering.moderngl_resources")' in resources_source
    assert "sys.modules[__name__] = _module" in resources_source
    assert "import *" not in resources_source
    assert "from src.adapters.gpu.viewport_probe import _gr_gpu_probe" in adapter_resources_source
    assert 'import_module("src.adapters.gpu.lightmap_gpu_solver")' in gui_facade_source
    assert "sys.modules[__name__] = _module" in gui_facade_source
    assert "import *" not in gui_facade_source
    assert "from src.adapters.gpu.lightmap_gpu_solver import LightmapGpuSolver" in adapter_baker_source
    assert 'import_module("src.adapters.gpu.lightmap_baker")' in gui_baker_source
    assert "sys.modules[__name__] = _module" in gui_baker_source
    assert "from src.adapters.gpu.lightmap_baker import LightmapBaker" not in gui_baker_source
    assert "LightmapGpuSolver" not in gui_baker_source
    assert "from .lightmap_gpu_solver import LightmapGpuSolver" not in gui_baker_source


def test_light_picker_is_backend_owned() -> None:
    """Screen-space light-helper picking belongs to core lighting."""
    import sys

    import src.core.lighting.light_picker as core_light_picker_module
    import src.gui.lighting.light_picker as gui_light_picker_module

    from src.core.lighting.light_picker import LightPicker as CoreLightPicker
    from src.core.qt_core.lighting.light_picker import LightPicker as FacadeLightPicker
    from src.gui.lighting.light_picker import LightPicker as GuiLightPicker
    from src.gui.qt_lib.lighting.light_picker import LightPicker as QtLibLightPicker

    assert GuiLightPicker is CoreLightPicker
    assert FacadeLightPicker is CoreLightPicker
    assert QtLibLightPicker is CoreLightPicker
    assert gui_light_picker_module is core_light_picker_module
    assert sys.modules["src.gui.lighting.light_picker"] is core_light_picker_module

    core_source = (ROOT / "src/core/lighting/light_picker.py").read_text(encoding="utf-8")
    for forbidden in ("src.gui.", "PySide6", "QtWidgets", "QtGui", "QtCore"):
        assert forbidden not in core_source
    gui_source = (ROOT / "src/gui/lighting/light_picker.py").read_text(encoding="utf-8")
    assert 'import_module("src.core.lighting.light_picker")' in gui_source
    assert "sys.modules[__name__] = _module" in gui_source
    assert "import *" not in gui_source

    viewport_deps = (ROOT / "src/gui/viewports/viewport_core/shared/dependencies.py").read_text(encoding="utf-8")
    assert "from src.core.lighting.light_picker import LightPicker" in viewport_deps
    assert "src.gui.lighting.light_picker" not in viewport_deps


def test_backend_renderer_dependencies_use_qt_viewport_adapter() -> None:
    """Backend renderer callers should depend on the explicit Qt viewport adapter."""
    adapter_source = (ROOT / "src/adapters/qt_viewport/frame_renderer.py").read_text(encoding="utf-8")
    still_frame_source = (ROOT / "src/adapters/qt_viewport/still_frame_renderer.py").read_text(encoding="utf-8")
    sequence_source = (ROOT / "src/sequence/sequence_render.py").read_text(encoding="utf-8")
    validator_source = (ROOT / "src/core/validation/viewport_validator.py").read_text(encoding="utf-8")

    assert "from src.adapters.qt_viewport.still_frame_renderer import FrameRenderer" in adapter_source
    assert "from src.core.rendering.frame_core.renderer import FrameRenderer" in adapter_source
    assert "class FrameRenderer" in still_frame_source
    assert "from src.core.camera.camera_render_settings import RenderSettings" in still_frame_source
    assert "src.gui.camera.frame_renderer" not in adapter_source
    assert "src.adapters.qt_viewport.frame_renderer" in sequence_source
    assert "src.adapters.qt_viewport.frame_renderer" in validator_source
    assert "from src.gui" not in sequence_source
    assert "from src.gui" not in validator_source


def test_software_frame_renderer_is_backend_owned() -> None:
    """The Tk-free software FrameRenderer belongs to core rendering."""
    from importlib import import_module
    import sys

    import src.core.rendering.frame_core.math_helpers as core_frame_math_helpers_module
    from src.core.rendering.frame_core.renderer import FrameRenderer as CoreFrameRenderer
    import src.math.frame_math as math_frame_math_module
    from src.gui.rendering.frame_core.renderer import FrameRenderer as GuiFrameRenderer
    from src.gui.rendering.viewport_core import FrameRenderer as ViewportCoreFrameRenderer
    from src.gui.viewports.frame_renderer import FrameRenderer as ViewportFrameRenderer

    assert GuiFrameRenderer is CoreFrameRenderer
    assert ViewportCoreFrameRenderer is CoreFrameRenderer
    assert ViewportFrameRenderer is CoreFrameRenderer
    assert core_frame_math_helpers_module is math_frame_math_module
    assert sys.modules["src.core.rendering.frame_core.math_helpers"] is math_frame_math_module

    frame_core_modules = (
        "colors",
        "dependencies",
        "diagnostics",
        "math_helpers",
        "mixin_imports",
        "rasterizer",
        "renderer",
        "renderer_geometry",
        "renderer_meshes",
        "renderer_overlays",
        "renderer_render_loop",
        "renderer_setup",
        "renderer_textures",
        "texture_cache",
    )
    for module_name in frame_core_modules:
        core_module = import_module(f"src.core.rendering.frame_core.{module_name}")
        gui_module = import_module(f"src.gui.rendering.frame_core.{module_name}")
        assert gui_module is core_module
        assert sys.modules[f"src.gui.rendering.frame_core.{module_name}"] is core_module

    for source_path in (ROOT / "src/core/rendering/frame_core").glob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        assert "src.gui." not in source
        assert "PySide6" not in source
        assert "QtWidgets" not in source
        assert "QtGui" not in source
        assert "QtCore" not in source
        assert "ImageTk" not in source

        if source_path.name != "__init__.py":
            gui_source = (ROOT / "src/gui/rendering/frame_core" / source_path.name).read_text(encoding="utf-8")
            module_name = source_path.stem
            assert f'import_module("src.core.rendering.frame_core.{module_name}")' in gui_source
            assert "sys.modules[__name__] = _module" in gui_source
            assert "globals().update" not in gui_source

    core_math_source = (ROOT / "src/core/rendering/frame_core/math_helpers.py").read_text(encoding="utf-8")
    assert 'import_module("src.math.frame_math")' in core_math_source
    assert "sys.modules[__name__] = _module" in core_math_source
    assert "import *" not in core_math_source
    for source_name in (
        "diagnostics.py",
        "colors.py",
        "rasterizer.py",
        "texture_cache.py",
        "mixin_imports.py",
        "renderer_setup.py",
        "renderer_render_loop.py",
        "renderer_textures.py",
        "renderer_geometry.py",
        "renderer_meshes.py",
        "renderer_overlays.py",
    ):
        source = (ROOT / "src/core/rendering/frame_core" / source_name).read_text(encoding="utf-8")
        assert "import *" not in source
        assert "globals().update" not in source

    for source_path in (
        ROOT / "src/adapters/qt_viewport/frame_renderer.py",
        ROOT / "scripts/diagnose_transforms.py",
        ROOT / "scripts/render_baseline.py",
        ROOT / "scripts/validate_all_models.py",
        ROOT / "scripts/visual_audit_k2.py",
        ROOT / "src/ipc/server.py",
        ROOT / "src/kotormcp/tools/ghostrigger.py",
        ROOT / "src/gui/viewports/viewport_core/shared/dependencies.py",
    ):
        source = source_path.read_text(encoding="utf-8")
        assert "src.gui.rendering.frame_core" not in source


def test_renderer_contract_helpers_are_backend_owned() -> None:
    """Renderer-neutral contracts and helpers belong to core rendering."""
    import sys

    import src.core.rendering.hardware_info as core_hardware_info_module
    import src.core.rendering.picking as core_picking_module
    import src.core.rendering.renderer_backend as core_renderer_backend_module
    import src.core.rendering.renderer_capabilities as core_renderer_capabilities_module
    import src.core.rendering.renderer_interface as core_renderer_interface_module
    import src.core.rendering.renderer_performance as core_renderer_performance_module
    import src.core.rendering.renderer_profiler as core_renderer_profiler_module
    import src.core.rendering.renderer_settings as core_renderer_settings_module
    import src.core.rendering.viewport_display as core_viewport_display_module
    import src.gui.rendering.hardware_info as gui_hardware_info_module
    import src.gui.rendering.picking as gui_picking_module
    import src.gui.rendering.renderer_backend as gui_renderer_backend_module
    import src.gui.rendering.renderer_capabilities as gui_renderer_capabilities_module
    import src.gui.rendering.renderer_interface as gui_renderer_interface_module
    import src.gui.rendering.renderer_performance as gui_renderer_performance_module
    import src.gui.rendering.renderer_profiler as gui_renderer_profiler_module
    import src.gui.rendering.renderer_settings as gui_renderer_settings_module
    import src.gui.rendering.viewport_display as gui_rendering_viewport_display_module
    import src.gui.viewports.viewport_display as gui_viewport_display_module

    from src.core.rendering.picking import PickHit as CorePickHit
    from src.core.rendering.renderer_backend import RendererBackend as CoreRendererBackend
    from src.core.rendering.renderer_capabilities import RendererCapabilities as CoreRendererCapabilities
    from src.core.rendering.renderer_performance import RenderBatchKey as CoreRenderBatchKey
    from src.core.rendering.renderer_settings import RendererSettings as CoreRendererSettings
    from src.core.rendering.viewport_display import ViewportDisplayMode as CoreViewportDisplayMode
    from src.core.rendering.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE as CoreDefaultNavProfile
    from src.core.rendering.viewport_navigation import ViewportNavigationProfile as CoreViewportNavigationProfile
    from src.core.rendering.viewport_navigation import normalize_viewport_navigation_profile as core_normalize_nav_profile
    from src.core.qt_core.rendering.renderer_backend import RendererBackend as FacadeRendererBackend
    from src.core.qt_core.rendering.viewport_navigation import ViewportNavigationProfile as FacadeViewportNavigationProfile
    from src.gui.rendering.picking import PickHit as GuiPickHit
    from src.gui.rendering.renderer_backend import RendererBackend as GuiRendererBackend
    from src.gui.rendering.renderer_capabilities import RendererCapabilities as GuiRendererCapabilities
    from src.gui.rendering.renderer_performance import RenderBatchKey as GuiRenderBatchKey
    from src.gui.rendering.renderer_settings import RendererSettings as GuiRendererSettings
    from src.gui.rendering.viewport_display import ViewportDisplayMode as GuiRenderingDisplayMode
    from src.gui.rendering.viewport_navigation import ViewportNavigationProfile as GuiRenderingNavigationProfile
    from src.gui.viewports.viewport_display import ViewportDisplayMode as GuiViewportDisplayMode
    from src.gui.viewports.viewport_navigation import DEFAULT_VIEWPORT_NAVIGATION_PROFILE as GuiDefaultNavProfile
    from src.gui.viewports.viewport_navigation import ViewportNavigationProfile as GuiViewportNavigationProfile
    from src.gui.viewports.viewport_navigation import normalize_viewport_navigation_profile as gui_normalize_nav_profile

    assert GuiRendererBackend is CoreRendererBackend
    assert FacadeRendererBackend is CoreRendererBackend
    assert GuiRendererCapabilities is CoreRendererCapabilities
    assert GuiRendererSettings is CoreRendererSettings
    assert GuiPickHit is CorePickHit
    assert GuiRenderBatchKey is CoreRenderBatchKey
    assert GuiViewportDisplayMode is CoreViewportDisplayMode
    assert GuiRenderingDisplayMode is CoreViewportDisplayMode
    assert GuiViewportNavigationProfile is CoreViewportNavigationProfile
    assert GuiRenderingNavigationProfile is CoreViewportNavigationProfile
    assert FacadeViewportNavigationProfile is CoreViewportNavigationProfile
    assert GuiDefaultNavProfile == CoreDefaultNavProfile
    assert gui_normalize_nav_profile is core_normalize_nav_profile
    assert gui_hardware_info_module is core_hardware_info_module
    assert sys.modules["src.gui.rendering.hardware_info"] is core_hardware_info_module

    module_pairs = {
        "src.gui.rendering.picking": (gui_picking_module, core_picking_module),
        "src.gui.rendering.renderer_backend": (gui_renderer_backend_module, core_renderer_backend_module),
        "src.gui.rendering.renderer_capabilities": (
            gui_renderer_capabilities_module,
            core_renderer_capabilities_module,
        ),
        "src.gui.rendering.renderer_interface": (gui_renderer_interface_module, core_renderer_interface_module),
        "src.gui.rendering.renderer_performance": (
            gui_renderer_performance_module,
            core_renderer_performance_module,
        ),
        "src.gui.rendering.renderer_profiler": (gui_renderer_profiler_module, core_renderer_profiler_module),
        "src.gui.rendering.renderer_settings": (gui_renderer_settings_module, core_renderer_settings_module),
        "src.gui.rendering.viewport_display": (
            gui_rendering_viewport_display_module,
            core_viewport_display_module,
        ),
        "src.gui.viewports.viewport_display": (gui_viewport_display_module, core_viewport_display_module),
    }
    for module_path, (gui_module, core_module) in module_pairs.items():
        assert gui_module is core_module
        assert sys.modules[module_path] is core_module

    core_rendering_sources = (
        "src/core/rendering/renderer_backend.py",
        "src/core/rendering/renderer_capabilities.py",
        "src/core/rendering/renderer_settings.py",
        "src/core/rendering/renderer_interface.py",
        "src/core/rendering/picking.py",
        "src/core/rendering/renderer_performance.py",
        "src/core/rendering/renderer_profiler.py",
        "src/core/rendering/hardware_info.py",
        "src/core/rendering/viewport_display.py",
        "src/core/rendering/viewport_navigation.py",
    )
    for source_path in core_rendering_sources:
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.gui." not in source
        assert "PySide6" not in source

    for source_path in (
        "src/gui/rendering/wgpu_core/shared.py",
        "src/gui/rendering/renderer_factory.py",
        "src/gui/rendering/null_renderer.py",
        "src/gui/rendering/moderngl_renderer.py",
        "src/gui/rendering/direct3d_renderer.py",
        "src/gui/integration/editor_services.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.gui.rendering.renderer_" not in source
        assert "src.gui.rendering.picking" not in source
        assert "src.gui.rendering.renderer_performance" not in source
        assert "src.gui.rendering.renderer_profiler" not in source
        assert "src.gui.viewports.viewport_display" not in source
        assert "src.gui.viewports.viewport_navigation" not in source

    gui_viewport_navigation = (ROOT / "src/gui/viewports/viewport_navigation.py").read_text(encoding="utf-8")
    gui_rendering_navigation = (ROOT / "src/gui/rendering/viewport_navigation.py").read_text(encoding="utf-8")
    assert "from src.core.rendering.viewport_navigation import *" in gui_viewport_navigation
    assert '_TARGET = "src.core.rendering.viewport_navigation"' in gui_rendering_navigation
    assert "sys.modules[__name__]" in gui_rendering_navigation
    gui_hardware_info = (ROOT / "src/gui/rendering/hardware_info.py").read_text(encoding="utf-8")
    assert 'import_module("src.core.rendering.hardware_info")' in gui_hardware_info
    assert "sys.modules[_FACADE_NAME] = _module" in gui_hardware_info
    assert "globals().update" not in gui_hardware_info

    for source_path, target_module in (
        ("src/gui/rendering/picking.py", "src.core.rendering.picking"),
        ("src/gui/rendering/renderer_backend.py", "src.core.rendering.renderer_backend"),
        ("src/gui/rendering/renderer_capabilities.py", "src.core.rendering.renderer_capabilities"),
        ("src/gui/rendering/renderer_interface.py", "src.core.rendering.renderer_interface"),
        ("src/gui/rendering/renderer_performance.py", "src.core.rendering.renderer_performance"),
        ("src/gui/rendering/renderer_profiler.py", "src.core.rendering.renderer_profiler"),
        ("src/gui/rendering/renderer_settings.py", "src.core.rendering.renderer_settings"),
        ("src/gui/rendering/viewport_display.py", "src.core.rendering.viewport_display"),
        ("src/gui/viewports/viewport_display.py", "src.core.rendering.viewport_display"),
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert f'import_module("{target_module}")' in source
        assert "sys.modules[__name__] = _module" in source
        assert "import *" not in source

    old_navigation_imports = []
    for source_path in (ROOT / "src").rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        if (
            "src.gui.qt_lib.viewports.viewport_navigation" in source
            or "src.gui.viewports.viewport_navigation" in source
        ):
            old_navigation_imports.append(str(source_path.relative_to(ROOT)))
    assert old_navigation_imports == []

    old_rendering_imports = []
    old_rendering_facades = (
        "src.gui.qt_lib.rendering.renderer_settings",
        "src.gui.qt_lib.rendering.renderer_backend",
        "src.gui.qt_lib.rendering.renderer_capabilities",
        "src.gui.qt_lib.rendering.hardware_info",
        "src.gui.qt_lib.rendering.picking",
        "src.gui.qt_lib.rendering.renderer_performance",
        "src.gui.qt_lib.rendering.gpu_renderer",
        "src.gui.qt_lib.rendering.qt_gpu_renderer",
        "src.gui.qt_lib.viewports.viewport_display",
    )
    for source_path in (ROOT / "src").rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        if any(facade in source for facade in old_rendering_facades):
            old_rendering_imports.append(str(source_path.relative_to(ROOT)))
    assert old_rendering_imports == []


def test_viewport_renderer_adapters_have_explicit_owner() -> None:
    """Concrete viewport renderer selection belongs to the adapters package."""
    import sys

    import src.adapters.rendering.direct3d_renderer as adapter_direct3d_module
    import src.adapters.rendering.moderngl_renderer as adapter_moderngl_module
    import src.adapters.rendering.null_renderer as adapter_null_module
    import src.adapters.rendering.moderngl_resources as adapter_resources_module
    import src.adapters.rendering.moderngl_renderer_impl as adapter_gpu_impl_module
    import src.adapters.rendering.renderer_factory as adapter_factory
    import src.adapters.rendering.wgpu_core.renderer as adapter_wgpu_renderer
    import src.gui.rendering.direct3d_renderer as gui_direct3d_module
    import src.gui.rendering.moderngl_renderer as gui_moderngl_module
    import src.gui.rendering.null_renderer as gui_null_module
    import src.gui.rendering.gpu_core.resources as gui_resources_module
    import src.gui.rendering.gpu_core.renderer as gui_gpu_impl_module
    import src.gui.rendering.renderer_factory as gui_factory
    import src.gui.rendering.wgpu_core.renderer as gui_wgpu_renderer
    from src.adapters.rendering.moderngl_legacy_bridge import _build_vbo_data as bridged_vbo_builder
    from src.adapters.rendering.moderngl_legacy_bridge import _GlTexCache as bridged_tex_cache
    from src.adapters.rendering.moderngl_legacy_bridge import _GpuMesh as bridged_gpu_mesh
    from src.adapters.rendering.moderngl_legacy_bridge import _PREBUILT_STATIC_MESH_ATTR as bridged_prebuilt_attr
    from src.adapters.rendering.moderngl_legacy_bridge import (
        _prebuilt_static_gpu_mesh_data as bridged_prebuilt_mesh_data,
    )
    from src.adapters.rendering.moderngl_legacy_bridge import (
        clear_prebuilt_static_gpu_model_data as bridged_clear_prebuilt_model,
    )
    from src.adapters.rendering.moderngl_legacy_bridge import (
        clear_prebuilt_static_gpu_mesh_data as bridged_clear_prebuilt_mesh,
    )
    from src.adapters.rendering.moderngl_legacy_bridge import moderngl_runtime_available
    from src.adapters.rendering.moderngl_legacy_bridge import prebuild_static_gpu_mesh_data as bridged_prebuild_mesh
    from src.adapters.rendering.moderngl_resources import _build_vbo_data as adapter_vbo_builder
    from src.adapters.rendering.moderngl_resources import _GlTexCache as adapter_tex_cache
    from src.adapters.rendering.moderngl_resources import _GpuMesh as adapter_gpu_mesh
    from src.adapters.rendering.moderngl_resources import _PREBUILT_STATIC_MESH_ATTR as adapter_prebuilt_attr
    from src.adapters.rendering.moderngl_resources import (
        _prebuilt_static_gpu_mesh_data as adapter_prebuilt_mesh_data,
    )
    from src.adapters.rendering.moderngl_resources import (
        clear_prebuilt_static_gpu_model_data as adapter_clear_prebuilt_model,
    )
    from src.adapters.rendering.moderngl_resources import (
        clear_prebuilt_static_gpu_mesh_data as adapter_clear_prebuilt_mesh,
    )
    from src.adapters.rendering.moderngl_resources import prebuild_static_gpu_mesh_data as adapter_prebuild_mesh
    from src.adapters.rendering.direct3d_renderer import Direct3DRenderer as AdapterDirect3DRenderer
    from src.adapters.rendering.moderngl_renderer import ModernGLRenderer as AdapterModernGLRenderer
    from src.adapters.rendering.null_renderer import NullDiagnosticRenderer as AdapterNullDiagnosticRenderer
    from src.adapters.rendering.renderer_factory import create_viewport_renderer as adapter_create_renderer
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer as AdapterWgpuRenderer
    from src.adapters.rendering.wgpu_core.resources import WgpuResourceCache as AdapterWgpuResourceCache
    from src.gui.rendering.direct3d_renderer import Direct3DRenderer as GuiDirect3DRenderer
    from src.gui.rendering.moderngl_renderer import ModernGLRenderer as GuiModernGLRenderer
    from src.gui.rendering.null_renderer import NullDiagnosticRenderer as GuiNullDiagnosticRenderer
    from src.gui.rendering.gpu_renderer import _build_vbo_data as public_vbo_builder
    from src.gui.rendering.gpu_renderer import _GlTexCache as public_tex_cache
    from src.gui.rendering.gpu_renderer import _GpuMesh as public_gpu_mesh
    from src.gui.rendering.gpu_renderer import _PREBUILT_STATIC_MESH_ATTR as public_prebuilt_attr
    from src.gui.rendering.gpu_renderer import _prebuilt_static_gpu_mesh_data as public_prebuilt_mesh_data
    from src.gui.rendering.gpu_renderer import clear_prebuilt_static_gpu_model_data as public_clear_prebuilt_model
    from src.gui.rendering.gpu_renderer import clear_prebuilt_static_gpu_mesh_data as public_clear_prebuilt_mesh
    from src.gui.rendering.gpu_renderer import prebuild_static_gpu_mesh_data as public_prebuild_mesh
    from src.gui.rendering.qt_gpu_renderer import create_viewport_renderer as qt_gpu_create_renderer
    from src.gui.rendering.wgpu_core.resources import WgpuResourceCache as GuiWgpuResourceCache
    from src.gui.rendering.wgpu_renderer import WgpuRenderer as PublicWgpuRenderer

    assert gui_factory is adapter_factory
    assert gui_wgpu_renderer is adapter_wgpu_renderer
    assert GuiDirect3DRenderer is AdapterDirect3DRenderer
    assert GuiModernGLRenderer is AdapterModernGLRenderer
    assert GuiNullDiagnosticRenderer is AdapterNullDiagnosticRenderer
    assert gui_direct3d_module is adapter_direct3d_module
    assert gui_moderngl_module is adapter_moderngl_module
    assert gui_null_module is adapter_null_module
    assert gui_resources_module is adapter_resources_module
    assert gui_gpu_impl_module is adapter_gpu_impl_module
    assert sys.modules["src.gui.rendering.direct3d_renderer"] is adapter_direct3d_module
    assert sys.modules["src.gui.rendering.moderngl_renderer"] is adapter_moderngl_module
    assert sys.modules["src.gui.rendering.null_renderer"] is adapter_null_module
    assert sys.modules["src.gui.rendering.gpu_core.resources"] is adapter_resources_module
    assert sys.modules["src.gui.rendering.gpu_core.renderer"] is adapter_gpu_impl_module
    assert PublicWgpuRenderer is AdapterWgpuRenderer
    assert GuiWgpuResourceCache is AdapterWgpuResourceCache
    assert bridged_vbo_builder is adapter_vbo_builder
    assert bridged_tex_cache is adapter_tex_cache
    assert bridged_gpu_mesh is adapter_gpu_mesh
    assert bridged_prebuilt_attr is adapter_prebuilt_attr
    assert bridged_prebuilt_mesh_data is adapter_prebuilt_mesh_data
    assert bridged_clear_prebuilt_model is adapter_clear_prebuilt_model
    assert bridged_clear_prebuilt_mesh is adapter_clear_prebuilt_mesh
    assert bridged_prebuild_mesh is adapter_prebuild_mesh
    assert bridged_vbo_builder is public_vbo_builder
    assert bridged_tex_cache is public_tex_cache
    assert bridged_gpu_mesh is public_gpu_mesh
    assert bridged_prebuilt_attr is public_prebuilt_attr
    assert bridged_prebuilt_mesh_data is public_prebuilt_mesh_data
    assert bridged_clear_prebuilt_model is public_clear_prebuilt_model
    assert bridged_clear_prebuilt_mesh is public_clear_prebuilt_mesh
    assert bridged_prebuild_mesh is public_prebuild_mesh
    assert isinstance(moderngl_runtime_available(), bool)
    assert qt_gpu_create_renderer is adapter_create_renderer

    adapter_source = (ROOT / "src/adapters/rendering/renderer_factory.py").read_text(encoding="utf-8")
    assert "from src.adapters.rendering.direct3d_renderer import Direct3DRenderer" in adapter_source
    assert "from src.adapters.rendering.moderngl_renderer import ModernGLRenderer" in adapter_source
    assert "from src.adapters.rendering.null_renderer import NullDiagnosticRenderer" in adapter_source
    assert "from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer" in adapter_source
    for forbidden in (
        "from src.gui.rendering.direct3d_renderer",
        "from src.gui.rendering.moderngl_renderer",
        "from src.gui.rendering.null_renderer",
        "from src.gui.rendering.wgpu_renderer",
    ):
        assert forbidden not in adapter_source

    bridge_source = (ROOT / "src/adapters/rendering/moderngl_legacy_bridge.py").read_text(encoding="utf-8")
    assert "from src.adapters.rendering import moderngl_renderer_impl as _gpu_renderer_impl" in bridge_source
    assert "from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer" in bridge_source
    assert "src.gui.rendering.gpu_core.renderer" not in bridge_source
    assert "from src.adapters.rendering.moderngl_resources import (" in bridge_source
    assert "src.gui.rendering.gpu_core.resources" not in bridge_source
    assert "_GlTexCache" in bridge_source
    assert "_GpuMesh" in bridge_source
    assert "_PREBUILT_STATIC_MESH_ATTR" in bridge_source
    assert "_prebuilt_static_gpu_mesh_data" in bridge_source
    assert "_build_vbo_data" in bridge_source
    assert "clear_prebuilt_static_gpu_model_data" in bridge_source
    assert "prebuild_static_gpu_mesh_data" in bridge_source

    public_gpu_facade = (ROOT / "src/adapters/rendering/gpu_renderer_exports.py").read_text(encoding="utf-8")
    assert '"GpuRenderer": "src.adapters.rendering.moderngl_legacy_bridge"' in public_gpu_facade
    assert '"_build_vbo_data": "src.adapters.rendering.moderngl_resources"' in public_gpu_facade
    assert '"_GlTexCache": "src.adapters.rendering.moderngl_resources"' in public_gpu_facade
    assert '"_GpuMesh": "src.adapters.rendering.moderngl_resources"' in public_gpu_facade
    assert '"_PREBUILT_STATIC_MESH_ATTR": "src.adapters.rendering.moderngl_resources"' in public_gpu_facade
    assert '"_prebuilt_static_gpu_mesh_data": "src.adapters.rendering.moderngl_resources"' in public_gpu_facade
    assert '"prebuild_static_gpu_mesh_data": "src.adapters.rendering.moderngl_resources"' in public_gpu_facade
    assert '"_bas_attachment_local_transform_np": "src.math.gpu_math"' in public_gpu_facade
    assert '"_mat4_from_pos_quat_scale": "src.math.gpu_math"' in public_gpu_facade
    assert '"src.gui.rendering.gpu_core.renderer"' not in public_gpu_facade
    assert '"src.gui.rendering.gpu_core.diagnostics"' not in public_gpu_facade
    assert '"src.gui.rendering.gpu_core.resources"' not in public_gpu_facade
    gui_gpu_facade = (ROOT / "src/gui/rendering/gpu_renderer.py").read_text(encoding="utf-8")
    qt_gpu_facade = (ROOT / "src/gui/rendering/qt_gpu_renderer.py").read_text(encoding="utf-8")
    assert '_TARGET = "src.adapters.rendering.gpu_renderer_exports"' in gui_gpu_facade
    assert "sys.modules[__name__]" in gui_gpu_facade
    assert '_GPU_EXPORTS = "src.adapters.rendering.gpu_renderer_exports"' in qt_gpu_facade
    assert '"create_viewport_renderer": "src.adapters.rendering.renderer_factory"' in qt_gpu_facade
    assert "def __getattr__" in qt_gpu_facade
    assert "import *" not in qt_gpu_facade
    assert "src.gui.rendering.gpu_renderer" not in gui_gpu_facade
    assert "src.gui.rendering.gpu_renderer" not in qt_gpu_facade

    adapter_wgpu_source = (ROOT / "src/adapters/rendering/wgpu_core/renderer.py").read_text(encoding="utf-8")
    assert "from src.adapters.rendering.moderngl_resources import _build_vbo_data" in adapter_wgpu_source
    assert "from src.adapters.rendering.moderngl_legacy_bridge import _build_vbo_data" not in adapter_wgpu_source
    assert "from src.gui.rendering.gpu_renderer import _build_vbo_data" not in adapter_wgpu_source
    assert "from .resources import *" not in adapter_wgpu_source
    assert "from .shared import *" not in adapter_wgpu_source
    assert "from src.adapters.rendering.wgpu_core.resources import WgpuResourceCache" in adapter_wgpu_source
    assert "from src.core.rendering.wgpu_shared import (" in adapter_wgpu_source

    adapter_wgpu_resources_source = (ROOT / "src/adapters/rendering/wgpu_core/resources.py").read_text(
        encoding="utf-8"
    )
    assert "from .shared import (" in adapter_wgpu_resources_source
    assert "from .shared import *" not in adapter_wgpu_resources_source
    assert "log = logging.getLogger(__name__)" in adapter_wgpu_resources_source

    for source_path in (
        "src/gui/viewports/viewport_core/shared/dependencies.py",
        "src/kotormcp/tools/debug_skinning.py",
        "scripts/dump_qbone_renderer_parity_3j4.py",
        "scripts/skin_3i_step7_visual_gate.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.adapters.rendering.moderngl_legacy_bridge" in source
        assert "from src.gui.rendering.gpu_renderer import" not in source
        assert "src.gui.qt_lib.rendering.gpu_renderer" not in source

    for source_path in (
        "src/gui/viewports/viewport_core/shared/dependencies.py",
        "src/gui/windows/application_core/shared/viewport_tools.py",
        "src/gui/windows/application_core/functions/geometry.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.adapters.rendering.moderngl_resources" in source
        assert "from src.gui.rendering.gpu_renderer import" not in source
        assert "src.gui.qt_lib.rendering.gpu_renderer" not in source

    regen_script_source = (ROOT / "scripts/regen_skin_3i_step6_dump.py").read_text(encoding="utf-8")
    assert "from src.core.rendering.gpu_diagnostics_records import _build_skin_dump_record" in regen_script_source
    assert "src.gui.qt_lib.rendering.gpu_renderer" not in regen_script_source

    ipc_source = (ROOT / "src/ipc/server.py").read_text(encoding="utf-8")
    mcp_source = (ROOT / "src/kotormcp/tools/ghostrigger.py").read_text(encoding="utf-8")
    assert "src.adapters.rendering.moderngl_legacy_bridge" in ipc_source
    assert "src.adapters.rendering.moderngl_scene_helpers" in ipc_source
    assert "src.adapters.rendering.moderngl_legacy_bridge" in mcp_source
    assert "src.adapters.rendering.moderngl_scene_helpers" in mcp_source
    assert "src.core.rendering.gpu_scene_helpers" in mcp_source
    assert "src.gui.rendering.gpu_core.renderer" not in ipc_source
    assert "src.gui.rendering.gpu_core.renderer" not in mcp_source
    assert "src.gui.rendering.gpu_core.scene_helpers" not in mcp_source

    for source_path in (
        ("src/gui/rendering/direct3d_renderer.py", "src.adapters.rendering.direct3d_renderer"),
        ("src/gui/rendering/moderngl_renderer.py", "src.adapters.rendering.moderngl_renderer"),
        ("src/gui/rendering/null_renderer.py", "src.adapters.rendering.null_renderer"),
        ("src/gui/rendering/gpu_core/resources.py", "src.adapters.rendering.moderngl_resources"),
        ("src/gui/rendering/gpu_core/renderer.py", "src.adapters.rendering.moderngl_renderer_impl"),
    ):
        source_path, target = source_path
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert f'import_module("{target}")' in source
        assert "sys.modules[__name__] = _module" in source
        assert "import *" not in source
        assert "class " not in source
        assert "def " not in source

    gui_factory_source = (ROOT / "src/gui/rendering/renderer_factory.py").read_text(encoding="utf-8")
    assert 'import_module("src.adapters.rendering.renderer_factory")' in gui_factory_source
    assert "sys.modules[__name__]" in gui_factory_source

    for source_path, target in (
        ("src/gui/rendering/wgpu_core/shared.py", "src.adapters.rendering.wgpu_core.shared"),
        ("src/gui/rendering/wgpu_core/resources.py", "src.adapters.rendering.wgpu_core.resources"),
        ("src/gui/rendering/wgpu_core/renderer.py", "src.adapters.rendering.wgpu_core.renderer"),
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert f'import_module("{target}")' in source
        assert "sys.modules[__name__]" in source

    public_wgpu_facade = (ROOT / "src/adapters/rendering/wgpu_renderer_exports.py").read_text(encoding="utf-8")
    assert '"WgpuRenderer": "src.adapters.rendering.wgpu_core.renderer"' in public_wgpu_facade
    assert '"WgpuResourceCache": "src.adapters.rendering.wgpu_core.resources"' in public_wgpu_facade
    assert "_EXPORT_MODULES" not in public_wgpu_facade
    assert "for candidate in" not in public_wgpu_facade
    gui_wgpu_facade = (ROOT / "src/gui/rendering/wgpu_renderer.py").read_text(encoding="utf-8")
    assert '_TARGET = "src.adapters.rendering.wgpu_renderer_exports"' in gui_wgpu_facade
    assert "sys.modules[__name__]" in gui_wgpu_facade
    assert "src.gui.rendering.wgpu_core" not in gui_wgpu_facade

    for source_path in (
        "src/gui/rendering/qt_gpu_renderer.py",
        "src/gui/windows/qt_main_window.py",
        "src/gui/windows/application_core/shared/workers.py",
        "src/gui/windows/application_core/functions/startup_library.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.gui.qt_lib.rendering.renderer_factory" not in source


def test_skeleton_render_data_is_backend_owned() -> None:
    """Skeleton overlay and skinning DTO helpers belong to core rendering."""
    import sys

    import src.core.rendering.skeleton_render_data as core_skeleton_module
    import src.gui.rendering.skeleton_render_data as gui_skeleton_module

    from src.core.rendering.skeleton_render_data import (
        SkeletonRenderData as CoreSkeletonRenderData,
        build_skeleton_render_data as core_build_skeleton_render_data,
    )
    from src.core.qt_core.rendering.skeleton_render_data import (
        SkeletonRenderData as FacadeSkeletonRenderData,
    )
    from src.gui.rendering.skeleton_render_data import (
        SkeletonRenderData as GuiSkeletonRenderData,
        build_skeleton_render_data as gui_build_skeleton_render_data,
    )

    assert GuiSkeletonRenderData is CoreSkeletonRenderData
    assert FacadeSkeletonRenderData is CoreSkeletonRenderData
    assert gui_build_skeleton_render_data is core_build_skeleton_render_data
    assert gui_skeleton_module is core_skeleton_module
    assert sys.modules["src.gui.rendering.skeleton_render_data"] is core_skeleton_module
    assert "src.gui." not in (ROOT / "src/core/rendering/skeleton_render_data.py").read_text(encoding="utf-8")
    gui_source = (ROOT / "src/gui/rendering/skeleton_render_data.py").read_text(encoding="utf-8")
    assert 'import_module("src.core.rendering.skeleton_render_data")' in gui_source
    assert "sys.modules[__name__] = _module" in gui_source
    assert "import *" not in gui_source

    for source_path in (
        "src/gui/rendering/mesh_render_data.py",
        "src/gui/rendering/wgpu_core/renderer.py",
        "src/gui/viewports/viewport_core/widgets/rendering_pipeline.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.gui.rendering.skeleton_render_data" not in source
        assert "src.gui.qt_lib.rendering.skeleton_render_data" not in source


def test_mesh_render_data_is_backend_owned_with_gui_vbo_adapter() -> None:
    """Mesh/material render-data DTOs belong to core rendering with explicit GUI VBO injection."""
    import sys

    import src.adapters.rendering.mesh_render_data as adapter_mesh_module
    import src.gui.rendering.mesh_render_data as gui_mesh_module

    from src.adapters.rendering.mesh_render_data import (
        MeshRenderData as AdapterMeshRenderData,
        iter_mesh_render_data as adapter_iter_mesh_render_data,
    )
    from src.core.rendering.mesh_render_data import (
        MeshRenderData as CoreMeshRenderData,
        iter_mesh_render_data as core_iter_mesh_render_data,
    )
    from src.core.qt_core.rendering.mesh_render_data import (
        MeshRenderData as FacadeMeshRenderData,
    )
    from src.gui.rendering.mesh_render_data import (
        MeshRenderData as GuiMeshRenderData,
        iter_mesh_render_data as gui_iter_mesh_render_data,
    )

    assert AdapterMeshRenderData is CoreMeshRenderData
    assert GuiMeshRenderData is CoreMeshRenderData
    assert FacadeMeshRenderData is CoreMeshRenderData
    assert gui_mesh_module is adapter_mesh_module
    assert sys.modules["src.gui.rendering.mesh_render_data"] is adapter_mesh_module
    assert adapter_iter_mesh_render_data is not core_iter_mesh_render_data
    assert gui_iter_mesh_render_data is not core_iter_mesh_render_data
    assert "src.gui." not in (ROOT / "src/core/rendering/mesh_render_data.py").read_text(encoding="utf-8")

    adapter_source = (ROOT / "src/adapters/rendering/mesh_render_data.py").read_text(encoding="utf-8")
    gui_facade = (ROOT / "src/gui/rendering/mesh_render_data.py").read_text(encoding="utf-8")
    assert "src.gui." not in adapter_source
    assert "kwargs.setdefault(\"vbo_builder\", _vbo_builder())" in adapter_source
    assert "from src.adapters.rendering.moderngl_resources import _build_vbo_data" in adapter_source
    assert "from src.adapters.rendering.moderngl_legacy_bridge import _build_vbo_data" not in adapter_source
    assert "globals().update" not in adapter_source
    assert "def __getattr__" in adapter_source
    assert "_CORE_EXPORTS" in adapter_source
    assert 'import_module("src.adapters.rendering.mesh_render_data")' in gui_facade
    assert "sys.modules[__name__] = _module" in gui_facade
    assert "import *" not in gui_facade
    assert "def iter_mesh_render_data" not in gui_facade
    assert "from src.gui.rendering.gpu_renderer import _build_vbo_data" not in gui_facade

    for source_path in (
        "src/gui/rendering/wgpu_core/resources.py",
        "src/gui/rendering/wgpu_core/renderer.py",
    ):
        source = (ROOT / source_path).read_text(encoding="utf-8")
        assert "src.gui.rendering.mesh_render_data" not in source
        assert "src.gui.qt_lib.rendering.mesh_render_data" not in source


def test_vertex_space_enum_contract() -> None:
    from src.core.geometry.vertex_space import VertexSpace

    assert list(VertexSpace) == [
        VertexSpace.NODE_LOCAL,
        VertexSpace.WORLD,
        VertexSpace.AABB_WALK,
    ]
    assert VertexSpace.NODE_LOCAL == 0
    assert VertexSpace.WORLD == 1
    assert VertexSpace.AABB_WALK == 2


def test_compute_vertex_space_aabb_walkmesh() -> None:
    from src.core.geometry.vertex_space import VertexSpace, compute_vertex_space

    assert compute_vertex_space(SimpleNamespace(flags=0x0200), None) is VertexSpace.AABB_WALK


def test_compute_vertex_space_imported_world() -> None:
    from src.core.geometry.vertex_space import VertexSpace, compute_vertex_space

    node = SimpleNamespace(flags=0, _imported=True)
    assert compute_vertex_space(node, None) is VertexSpace.WORLD


def test_compute_vertex_space_default_node_local() -> None:
    from src.core.geometry.vertex_space import VertexSpace, compute_vertex_space

    assert compute_vertex_space(SimpleNamespace(flags=0), None) is VertexSpace.NODE_LOCAL


def test_inner_geometry_name_matching() -> None:
    from src.core.special.render_constants import is_inner_geometry_name

    for name in ("eyeRA", "teethU", "TongueMesh", "gumskin", "JawSkin", "eyelid"):
        assert is_inner_geometry_name(name)


def test_face_mesh_name_matching() -> None:
    from src.core.special.render_constants import is_face_mesh_name

    for name in ("head", "Face_LOD0", "fchead01", "skullcap"):
        assert is_face_mesh_name(name)


def test_inner_geometry_does_not_match_non_inner_names() -> None:
    from src.core.special.render_constants import is_inner_geometry_name

    for name in ("headhook", "model_root", "rootdummy", "random_mesh", ""):
        assert not is_inner_geometry_name(name)


def test_read_mdl_safe_importable_and_callable() -> None:
    from src.core.mdl.mdl_reader_wrapper import read_mdl_safe

    assert callable(read_mdl_safe)


def test_pykotor_mdl_binary_fixes_are_idempotent() -> None:
    from src.core.game.pykotor_mdl_io_fix import ensure_pykotor_mdl_binary_fixes

    ensure_pykotor_mdl_binary_fixes()
    ensure_pykotor_mdl_binary_fixes()


def test_ascii_mdl_nodes_keep_imported_uv_orientation() -> None:
    from src.core.mdl.mdl_parser import MDLAsciiParser

    model = MDLAsciiParser().parse(
        [
            "newmodel uv_test",
            "node trimesh mesh",
            "parent NULL",
            "bitmap redtex",
            "bitmap2 greentex",
            "verts 3",
            "0 0 0",
            "1 0 0",
            "0 1 0",
            "tverts 3",
            "0 0",
            "1 0",
            "0 1",
            "faces 1",
            "0 1 2 1 0 1 2 0",
            "endnode",
            "donemodel",
        ]
    )

    assert model.root_node is not None
    assert model.root_node.texture_names == ["redtex", "greentex"]
    assert model.root_node.uvs == [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    assert model.root_node.imported_ascii is True
    assert model.root_node.uv_v_flip is True
    assert model.root_node.face_mats == [0]


def test_gpu_shader_has_per_node_uv_v_flip_control() -> None:
    from src.core.rendering.gpu_shaders import _VERT_SRC

    assert "uniform float u_uv_v_flip" in _VERT_SRC
    assert "mix(in_uv.y, 1.0 - in_uv.y, u_uv_v_flip)" in _VERT_SRC


def test_gpu_ascii_multitexture_split_is_ascii_gated() -> None:
    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer

    source = inspect.getsource(GpuRenderer._render_gpu)
    assert "ASCII/Kotor Tool MDLs use face_mats as per-face texture slots" in source
    assert "getattr(node, 'imported_ascii', False)" in source
    assert "gm.mat_slots" in source


def test_viewport_render_loop_is_gpu_only() -> None:
    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    render_now = inspect.getsource(QtViewportWidget._render_now)
    render_frame = inspect.getsource(QtViewportWidget._render_frame)
    badge = inspect.getsource(QtViewportWidget._set_renderer_badge)
    thumbnail = inspect.getsource(QtViewportWidget._render_neutral_pose_thumbnail)
    gpu_render = inspect.getsource(GpuRenderer.render)
    cpu_hook = inspect.getsource(GpuRenderer._render_cpu)

    viewport_sources = "\n".join([render_now, render_frame, badge, thumbnail])
    assert "_use_gpu = False" not in viewport_sources
    assert 'setText("CPU' not in viewport_sources
    assert "self._renderer.render(" not in viewport_sources
    assert "_draw_cpu_overlays(" not in render_frame
    assert "_draw_performance_overlay(" not in render_now
    assert "_render_cpu(" not in gpu_render
    assert "backend'] = 'cpu'" not in gpu_render
    assert "FrameRenderer" not in cpu_hook
    assert "return None" in cpu_hook


def test_add_model_to_scene_dialog_stays_compact_under_layout_apply() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.dialogs.add_model_to_scene_dialog import AddModelToSceneDialog
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = AddModelToSceneDialog("K2:c_drdmktwo")
    dialog.apply_ghost_layout(SimpleNamespace(dialog_width=1650))

    source = inspect.getsource(QtGhostRiggerMainWindow._choose_model_import_action)
    assert "apply_current_layout(dialog)" not in source
    assert "apply_current_theme(dialog)" not in source
    assert "dialog.apply_ghost_theme(active_theme)" in source
    assert dialog.width() <= AddModelToSceneDialog.MAX_WIDTH
    assert dialog.maximumWidth() == AddModelToSceneDialog.MAX_WIDTH
    assert dialog.minimumWidth() == AddModelToSceneDialog.MAX_WIDTH


def test_qt_gpu_viewport_uses_overlay_not_cpu_textured_fallback() -> None:
    import inspect

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    frame_source = inspect.getsource(QtViewportWidget._render_frame)
    source = inspect.getsource(QtViewportWidget._draw_gpu_viewport_overlays)
    legacy_source = inspect.getsource(QtViewportWidget._draw_cpu_overlays)
    native_gizmo_source = inspect.getsource(QtViewportWidget._gpu_renderer_supports_native_gizmo_drawing)
    drag_source = inspect.getsource(QtViewportWidget._drag_lmb)
    skip_source = inspect.getsource(QtViewportWidget._can_skip_live_overlay_rebuild)
    wgpu_draw_source = inspect.getsource(WgpuRenderer._draw_gizmo_lines)
    wgpu_pipeline_source = inspect.getsource(WgpuRenderer._create_gizmo_line_pipeline)

    assert "_draw_gpu_viewport_overlays" in frame_source
    assert "_draw_performance_overlay" in frame_source
    assert "self._renderer.render(" not in frame_source
    assert "_draw_mesh_textured" not in source
    assert "_draw_mesh_flat" not in source
    assert "self._xray_mode" in source
    assert "_draw_grid" in source
    assert "_draw_stats" in source
    assert "_draw_transform_gizmo" in source
    assert "not self._gpu_renderer_supports_native_gizmo_drawing()" in source
    assert 'backend_id.startswith("wgpu_")' in native_gizmo_source
    assert "supports_gizmo_drawing" in native_gizmo_source
    assert 'reason="gizmo drag", scene=True, gizmo=True' in drag_source
    assert "self._notify_node_moved(node)" not in drag_source
    assert "_gpu_renderer_supports_native_gizmo_drawing()" in skip_source
    assert "pipeline_gizmo_triangles" in wgpu_pipeline_source
    assert '"triangles"' in wgpu_draw_source
    assert "_draw_axes" in source
    assert "return self._draw_gpu_viewport_overlays" in legacy_source


def test_qt_gpu_viewport_keeps_gpu_for_wire_and_texture_off_modes() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    frame_source = inspect.getsource(QtViewportWidget._render_frame)
    gpu_source = inspect.getsource(QtViewportWidget._render_gpu_frame)
    texture_snapshot_source = inspect.getsource(QtViewportWidget._gpu_texture_snapshot)

    assert "gpu_can_match_mode" not in frame_source
    assert "self._render_gpu_frame(w, h)" in frame_source
    assert "self._renderer.render(" not in frame_source
    assert "and self._renderer.show_texture" not in frame_source
    assert "show_texture = bool(self._renderer.show_texture)" in gpu_source
    assert "show_wireframe = bool(self._renderer.show_wireframe)" in gpu_source
    assert 'dirty_flags.get("resources", False)' in texture_snapshot_source
    assert "_gpu_baked_lightmap_snapshot_model_id" in texture_snapshot_source


def test_wgpu_renderer_defers_uncached_uploads_without_caching_fallback_materials() -> None:
    import inspect

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.adapters.rendering.wgpu_core.resources import WgpuResourceCache

    init_source = inspect.getsource(WgpuRenderer.__init__)
    budget_source = inspect.getsource(WgpuRenderer._begin_upload_budget)
    consume_source = inspect.getsource(WgpuRenderer._consume_upload_budget)
    cache_source = inspect.getsource(WgpuResourceCache.get_or_upload_mesh)
    texture_source = inspect.getsource(WgpuResourceCache.get_or_upload_texture)
    material_source = inspect.getsource(WgpuResourceCache.get_or_create_material)
    render_source = inspect.getsource(WgpuRenderer.render)
    diagnostics_source = inspect.getsource(WgpuRenderer.get_diagnostics)

    assert "self.deferred_mesh_uploads = False" in init_source
    assert "self._frame_upload_budget_remaining" in init_source
    assert "self._pending_uploads_count = 0" in budget_source
    assert "budget = min(budget, 4)" in budget_source
    assert "self._defer_resource_upload(kind, key)" in consume_source
    assert 'self._renderer._consume_upload_budget("mesh", mesh_id)' in cache_source
    assert 'self._renderer._consume_upload_budget("texture", texture_id)' in texture_source
    assert "deferred_after == deferred_before" in material_source
    assert "self.materials[material_id] = resource" in material_source
    assert "self._begin_upload_budget()" in render_source
    assert '"upload_budget_used"' in diagnostics_source


def test_qt_viewport_grid_toggle_controls_cpu_and_gpu_paths() -> None:
    import inspect

    from src.core.rendering.frame_core.renderer import FrameRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    frame_grid_source = inspect.getsource(FrameRenderer._draw_grid)
    viewport_build_source = inspect.getsource(QtViewportWidget._build)
    toggle_source = inspect.getsource(QtViewportWidget.toggle_grid)
    gpu_source = inspect.getsource(QtViewportWidget._render_gpu_frame)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions) + inspect.getsource(QtGhostRiggerMainWindow._build_menu)

    assert 'getattr(self, "show_grid", True)' in frame_grid_source
    assert "self.grid_button" in viewport_build_source
    assert "self._renderer.show_grid = self.grid_button.isChecked()" in viewport_build_source
    assert "self._gpu_renderer.show_grid = enabled" in toggle_source
    assert 'show_grid = bool(getattr(self._renderer, "show_grid", True))' in gpu_source
    assert "Toggle Grid" in menu_source
    assert 'setShortcut("Alt+G")' in menu_source
    assert '"grid_button"' in menu_source


def test_main_window_help_menu_uses_real_about_dialog() -> None:
    import inspect

    from src.gui.qt_lib.dialogs.qt_dialogs import QtAboutDialog, show_about
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    action_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    about_source = inspect.getsource(show_about)

    assert "self.about_action" in action_source
    assert "About GhostRigger..." in action_source
    assert "help_menu.addAction(self.about_action)" in menu_source
    assert "QtAboutDialog(parent)" in about_source
    assert hasattr(QtAboutDialog, "apply_ghost_theme")


def test_qt_viewport_performance_overlay_stacks_above_stats_badge() -> None:
    import inspect

    from src.core.rendering.frame_core.renderer import FrameRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    stats_source = inspect.getsource(FrameRenderer._draw_stats)
    perf_source = inspect.getsource(QtViewportWidget._draw_performance_overlay)

    assert "max(12, H - 28)" in stats_source
    assert "h - 50" in perf_source
    assert "_draw_hud_pill" in perf_source
    assert "max_width = max(80, w - 16)" in perf_source
    assert "_hud_pill_width(label, max_width=max_width)" in perf_source


def test_viewport_animation_hud_sits_under_model_stats_not_fps_overlay() -> None:
    import inspect

    from src.core.rendering.frame_core.renderer import FrameRenderer

    stats_source = inspect.getsource(FrameRenderer._draw_stats)

    assert "hud_right_limit = max(hud_left + 120, W - 172)" in stats_source
    assert "max_width=hud_max_width" in stats_source
    assert "animation_row_y = stats_row_y + hud_row_step" in stats_source
    assert "12,\n                animation_row_y," in stats_source
    assert "Show animation progress without overlapping the bottom-right FPS indicator" in stats_source
    assert "H - 52" not in stats_source
    assert "txt_w = len(anim_txt)" not in stats_source
    assert "warn_y = animation_row_y + hud_row_step" in stats_source


def test_viewport_hud_state_changes_dirty_overlay_immediately() -> None:
    import inspect

    from src.core.rendering.renderer_performance import ViewportFrameGovernor
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    load_source = inspect.getsource(QtViewportWidget.load_model)
    shade_source = inspect.getsource(QtViewportWidget.set_shade_mode)
    render_mode_source = inspect.getsource(QtViewportWidget.set_render_mode)
    texture_source = inspect.getsource(QtViewportWidget.toggle_texture)
    animation_source = inspect.getsource(QtViewportWidget.set_animation_pose)
    event_filter_source = inspect.getsource(QtViewportWidget.eventFilter)
    skip_source = inspect.getsource(QtViewportWidget._can_skip_live_overlay_rebuild)

    assert "hud" in ViewportFrameGovernor.DIRTY_FLAGS
    assert "hud=True" in load_source
    assert "hud=True" in shade_source
    assert "hud=True" in render_mode_source
    assert "hud=True" in texture_source
    assert "hud=True" in animation_source
    assert 'reason="viewport resized", overlay=True, hud=True' in event_filter_source
    assert '"hud"' in skip_source


def test_qt_gpu_viewport_resets_render_targets_on_model_load() -> None:
    import inspect

    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    gpu_source = inspect.getsource(GpuRenderer.reset_framebuffers)
    load_source = inspect.getsource(QtViewportWidget.load_model)

    assert "self._fbo = None" in gpu_source
    assert "self._fbo_simple = None" in gpu_source
    assert "reset_framebuffers()" in load_source
    assert "self._request_render(fast=True)" in load_source


def test_gpu_renderer_supports_texture_off_and_wireframe_modes() -> None:
    import inspect

    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer

    init_source = inspect.getsource(GpuRenderer.__init__)
    render_source = inspect.getsource(GpuRenderer._render_gpu)

    assert "self.show_texture: bool = True" in init_source
    assert "self.show_solid: bool = True" in init_source
    assert "self.wire_color: tuple[float, float, float] = (0.18, 0.62, 0.95)" in init_source
    assert "self.show_diffuse_map: bool = True" in init_source
    assert "self.show_lightmap_map: bool = False" in init_source
    assert "self.show_environment_map: bool = True" in init_source
    assert "self.show_specular_map: bool = True" in init_source
    assert "self.lightmap_intensity: float = 0.55" in init_source
    assert "self.lightmap_mode: str = \"disabled\"" in init_source
    assert "self.show_light_gizmos: bool = True" in init_source
    assert "_texture_allowed = bool(self.show_texture and self.show_diffuse_map)" in render_source
    assert "bool(self.show_lightmap_map)" in render_source
    assert "bool(self.show_environment_map)" in render_source
    assert "bool(self.show_specular_map)" in render_source
    assert "_draw_light_gizmos" in render_source
    assert "ctx.wireframe = bool(self.show_wireframe and not self.show_solid)" in render_source
    assert "if self.show_solid and self.show_wireframe" in render_source
    assert "u_wireframe_enabled" in render_source
    assert "u_wire_color" in render_source


def test_gpu_renderer_exposes_module_render_modes_and_selection_tint() -> None:
    import inspect

    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer
    from src.core.rendering.gpu_shaders import _FRAG_SRC
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    init_source = inspect.getsource(GpuRenderer.__init__)
    render_source = inspect.getsource(GpuRenderer._render_gpu)
    viewport_source = inspect.getsource(QtViewportWidget._render_gpu_frame)

    assert 'self.render_mode: str = "realistic"' in init_source
    assert "uniform int   u_render_mode" in _FRAG_SRC
    assert "uniform int   u_selected" in _FRAG_SRC
    assert "u_render_mode == 1" in _FRAG_SRC
    assert "u_render_mode == 2" in _FRAG_SRC
    assert "soft_shade" in _FRAG_SRC
    assert "0.76 + max(dot(N, u_light_dir), 0.0) * 0.24" in _FRAG_SRC
    assert "mix(lit_color, vec3(1.0, 0.78, 0.12), 0.45)" in _FRAG_SRC
    assert "getattr(node, '_gr_hidden', False)" in render_source
    assert "_detail_texture_allowed = bool(self.show_texture and _render_mode_int == 0)" in render_source
    assert "u_bump_tex" in _FRAG_SRC
    assert "u_has_bump" in _FRAG_SRC
    assert "u_lightmap_intensity" in _FRAG_SRC
    assert "u_lightmap_mode" in _FRAG_SRC
    assert "if _gpu_is_module and _render_mode_int in (1, 2)" in render_source
    assert "render_mode = str(getattr(self._renderer" in viewport_source
    assert "lightmap_intensity = float(getattr(self._renderer" in viewport_source
    assert "lightmap_mode = str(getattr(self._renderer" in viewport_source
    assert "selected_node = getattr(self._renderer" in viewport_source
    assert "selected_nodes = list(getattr(self, \"_selected_meshes\"" in viewport_source
    assert "_texture_allowed = bool(self.show_texture and self.show_diffuse_map)" in render_source


def test_gpu_static_mesh_prebuild_uses_ram_and_chunked_uploads() -> None:
    import inspect

    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer
    from src.adapters.rendering.moderngl_resources import (
        clear_prebuilt_static_gpu_model_data,
        prebuild_static_gpu_mesh_data,
    )
    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.core.rendering.frame_core.renderer import FrameRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    node = ModelNode(
        name="tri",
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="test",
    )
    model = KotorModel(name="prebuild", root_node=node)

    assert prebuild_static_gpu_mesh_data(model) == 1
    entry = getattr(node, "_gr_gpu_prebuilt_static_mesh")
    assert entry["model_id"] == id(model)
    assert entry["vdata"].shape[0] == 3
    assert getattr(model, "_gr_bounds_prepared") is True
    assert getattr(model, "_gr_render_bounds") == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))
    assert clear_prebuilt_static_gpu_model_data(model) == 1
    assert not hasattr(node, "_gr_gpu_prebuilt_static_mesh")

    init_source = inspect.getsource(GpuRenderer.__init__)
    render_source = inspect.getsource(GpuRenderer._render_gpu)
    renderer_set_model_source = inspect.getsource(FrameRenderer.set_model)
    load_source = inspect.getsource(QtViewportWidget.load_model)
    viewport_source = inspect.getsource(QtViewportWidget._render_gpu_frame)

    assert "self.max_new_mesh_uploads_per_frame: int = 64" in init_source
    assert "self.deferred_mesh_uploads = True" in render_source
    assert "_prebuilt_static_gpu_mesh_data" in render_source
    assert "prepared_bounds = getattr(m, \"_gr_render_bounds\", None)" in renderer_set_model_source
    assert "getattr(m, \"_gr_defer_txi_metadata\", False)" in renderer_set_model_source
    assert "clear_prebuilt_static_gpu_model_data(old_model)" in load_source
    assert "self._gpu_renderer.clear_caches()" in load_source
    assert "if not getattr(model, \"_gr_bounds_prepared\", False)" in load_source
    assert "self._start_deferred_txi_metadata(model)" in load_source
    assert "gpuUploadProgress.emit" in viewport_source
    assert "_request_render(fast=True)" in viewport_source


def test_kmax_scene_composite_preserves_authored_root_name_for_animation_skinning() -> None:
    from src.core.animation.gpu_skinning import MatrixPaletteUploader
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    root = ModelNode(name="N_Bith", flags=int(NodeFlags.HEADER), position=(9.0, 8.0, 7.0))
    head_bone = ModelNode(name="head_g", flags=int(NodeFlags.HEADER))
    skin = ModelNode(name="Head", flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH) | int(NodeFlags.SKIN))
    skin.bone_map = ["N_Bith", "head_g"]
    skin.qbone_list = [(1.0, 0.0, 0.0, 0.0)] * 3
    skin.tbone_list = [(0.0, 0.0, 0.0)] * 3
    root.children.append(head_bone)
    head_bone.parent = root
    root.children.append(skin)
    skin.parent = root
    model = KotorModel(name="N_Bith", root_node=root)

    fake_viewport = SimpleNamespace()
    fake_viewport._tag_scene_object_nodes = MethodType(QtViewportWidget._tag_scene_object_nodes, fake_viewport)
    fake_viewport._tag_scene_source_indices = MethodType(QtViewportWidget._tag_scene_source_indices, fake_viewport)
    fake_viewport._euler_degrees_to_quat = QtViewportWidget._euler_degrees_to_quat

    instance = SimpleNamespace(
        id="scene-object-1",
        name="Bith Actor",
        visible=True,
        metadata={"_runtime_model": model},
        transform=SimpleNamespace(position=(1.0, 2.0, 3.0), rotation=(0.0, 0.0, 0.0)),
    )

    composite = QtViewportWidget._build_scene_composite_model(fake_viewport, [instance], "Untitled Scene")
    placed_root = composite.root_node.children[0]
    placed_skin = placed_root.children[1]

    assert placed_root.name == "N_Bith"
    assert placed_root.position == (1.0, 2.0, 3.0)
    assert getattr(placed_root, "_gr_scene_source_position") == (9.0, 8.0, 7.0)
    assert getattr(placed_root, "_gr_scene_gpu_transform") is True
    assert getattr(placed_root, "_gr_scene_object_name") == "Bith Actor"
    assert placed_skin.bone_map[0] == placed_root.name
    assert getattr(placed_skin, "_gr_scene_object_id") == "scene-object-1"

    uploader = MatrixPaletteUploader(max_bones=4)
    uploader.build_inverse_bind_pose(composite)
    assert uploader._name_to_dfs_index["n_bith"] == 0
    assert uploader._name_to_dfs_index["head_g"] == 1
    assert uploader._name_to_dfs_index["head"] == 2
    assert uploader._model_node_count == 3
    uploader.compute_skin_node_palette(placed_skin, SimpleNamespace(nodes={}))
    assert uploader._skin_inverse_bind_source == "qBone_tBone_dfs_indexed_TR_no_invert"


def test_kmax_scene_composite_keeps_bas_layers_out_of_body_dfs_indices() -> None:
    from src.core.animation.gpu_skinning import MatrixPaletteUploader
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    root = ModelNode(name="P_CarthBB", flags=int(NodeFlags.HEADER))
    spine = ModelNode(name="torso_g", flags=int(NodeFlags.HEADER), parent=root)
    headhook = ModelNode(name="headhook", flags=int(NodeFlags.HEADER), parent=root)
    after_hook = ModelNode(name="rhand", flags=int(NodeFlags.HEADER), parent=root)
    body_skin = ModelNode(name="torso", flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH) | int(NodeFlags.SKIN), parent=root)
    body_skin.bone_map = ["P_CarthBB", "torso_g", "headhook", "rhand"]
    body_skin.qbone_list = [(1.0, 0.0, 0.0, 0.0)] * 5
    body_skin.tbone_list = [(0.0, 0.0, 0.0)] * 5
    root.children.extend([spine, headhook, after_hook, body_skin])
    body = KotorModel(name="P_CarthBB", root_node=root)

    head_root = ModelNode(name="pmha01")
    head_mesh = ModelNode(
        name="head",
        flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH) | int(NodeFlags.SKIN),
        parent=head_root,
    )
    head_root.children.append(head_mesh)
    head = KotorModel(name="pmha01", root_node=head_root)

    window = SimpleNamespace()
    window._find_model_node = MethodType(QtGhostRiggerMainWindow._find_model_node, window)
    window._reset_bas_model_node_traversal = MethodType(QtGhostRiggerMainWindow._reset_bas_model_node_traversal, window)
    window._prepare_bas_layer_root = MethodType(QtGhostRiggerMainWindow._prepare_bas_layer_root, window)
    window._tag_bas_attachment_subtree = MethodType(QtGhostRiggerMainWindow._tag_bas_attachment_subtree, window)
    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, head, "headhook", slot="head") is True

    fake_viewport = SimpleNamespace()
    fake_viewport._tag_scene_object_nodes = MethodType(QtViewportWidget._tag_scene_object_nodes, fake_viewport)
    fake_viewport._tag_scene_source_indices = MethodType(QtViewportWidget._tag_scene_source_indices, fake_viewport)
    fake_viewport._euler_degrees_to_quat = QtViewportWidget._euler_degrees_to_quat
    instance = SimpleNamespace(
        id="bas-preview",
        name="P_CarthBB BAS",
        visible=True,
        metadata={"_runtime_model": body},
        transform=SimpleNamespace(position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0)),
    )

    composite = QtViewportWidget._build_scene_composite_model(fake_viewport, [instance], "BAS Preview")
    placed_root = composite.root_node.children[0]
    stack = [placed_root]
    placed_root_nodes = []
    while stack:
        node = stack.pop()
        placed_root_nodes.append(node)
        stack.extend(reversed(getattr(node, "children", []) or []))
    placed_nodes = {
        getattr(node, "name", ""): node
        for node in placed_root_nodes
        if not bool(getattr(node, "_gr_bas_attachment_layer", False))
    }

    assert getattr(placed_nodes["P_CarthBB"], "_gr_source_dfs_index") == 0
    assert getattr(placed_nodes["torso_g"], "_gr_source_dfs_index") == 1
    assert getattr(placed_nodes["headhook"], "_gr_source_dfs_index") == 2
    assert getattr(placed_nodes["rhand"], "_gr_source_dfs_index") == 3
    assert getattr(placed_nodes["torso"], "_gr_source_dfs_index") == 4

    uploader = MatrixPaletteUploader(max_bones=8)
    uploader.build_inverse_bind_pose(composite)
    assert uploader._name_to_dfs_index["rhand"] == 3
    assert uploader._name_to_dfs_index["torso"] == 4
    assert uploader._model_node_count == 5
    assert "pmha01" not in uploader._name_to_dfs_index
    uploader.compute_skin_node_palette(placed_nodes["torso"], SimpleNamespace(nodes={}))
    assert uploader._skin_inverse_bind_source == "qBone_tBone_dfs_indexed_TR_no_invert"


def test_kmax_scene_gpu_transform_uses_authored_vbo_basis() -> None:
    from src.math.gpu_math import _scene_authored_world_transform, _scene_gpu_model_matrix

    child = SimpleNamespace(
        position=(2.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent=None,
    )
    root = SimpleNamespace(
        position=(100.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent=None,
        _gr_scale=(3.0, 3.0, 3.0),
        _gr_scene_object_root=True,
        _gr_scene_gpu_transform=True,
        _gr_scene_source_position=(9.0, 8.0, 7.0),
        _gr_scene_source_rotation=(0.0, 0.0, 0.0, 1.0),
    )
    child.parent = root

    authored_pos, _authored_rot = _scene_authored_world_transform(child)
    scene_mat = _scene_gpu_model_matrix(child)

    assert authored_pos == pytest.approx((11.0, 8.0, 7.0))
    assert scene_mat[0, 3] == pytest.approx(100.0)
    assert scene_mat[0, 0] == pytest.approx(3.0)


def test_kmax_scene_reload_preserves_selected_object_for_pivot_tools() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    load_model_source = inspect.getsource(QtViewportWidget.load_model)
    load_scene_source = inspect.getsource(QtViewportWidget.load_scene_instances)

    assert 'getattr(root_node, "_gr_scene_composite_root", False)' in load_model_source
    assert "selected_id =" in load_scene_source
    assert "self.load_model(composite" in load_scene_source
    assert "self.select_scene_object(selected_id)" in load_scene_source


def test_transform_cache_evict_clears_frame_and_gpu_child_caches() -> None:
    from types import SimpleNamespace

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    child = SimpleNamespace(children=[])
    setattr(child, "_gr_gpu_prebuilt_static_mesh", {"model_id": 1, "skin_bind_transform": False})
    parent = SimpleNamespace(children=[child])

    invalidated = []
    viewport = SimpleNamespace(
        _renderer=SimpleNamespace(
            _wt_cache={id(parent): object(), id(child): object()},
            _frame_view=object(),
            _frame_verts_cache={id(child): [(0.0, 0.0, 0.0)]},
            _frame_norms_cache={id(child): [(0.0, 0.0, 1.0)]},
        ),
        _gpu_renderer=SimpleNamespace(invalidate_node=lambda node: invalidated.append(node)),
    )

    QtViewportWidget._evict_transform_cache(viewport, parent)

    assert not hasattr(child, "_gr_gpu_prebuilt_static_mesh")
    assert viewport._renderer._wt_cache == {}
    assert viewport._renderer._frame_view is None
    assert viewport._renderer._frame_verts_cache == {}
    assert viewport._renderer._frame_norms_cache == {}
    assert invalidated == [parent, child]


def test_model_load_worker_uses_single_read_and_gpu_prebuild() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import (
        ModelLoadWorker,
        QtGhostRiggerMainWindow,
        QtProgressToast,
        ResourceModelLoadWorker,
    )
    from src.gui.windows.application_core.shared.workers import load_resource_model_from_game_resources

    file_source = inspect.getsource(ModelLoadWorker.run)
    toast_source = inspect.getsource(QtProgressToast)
    window_source = inspect.getsource(QtGhostRiggerMainWindow)
    start_resource_source = inspect.getsource(QtGhostRiggerMainWindow._start_resource_load)
    ui_resource_source = inspect.getsource(QtGhostRiggerMainWindow._load_resource_model_on_ui_thread)
    get_resource_manager_source = inspect.getsource(QtGhostRiggerMainWindow._get_resource_manager)
    resource_source = inspect.getsource(ResourceModelLoadWorker.run)
    resource_loader_source = inspect.getsource(load_resource_model_from_game_resources)
    viewport_preload_source = inspect.getsource(__import__(
        "src.gui.qt_lib.viewports.qt_viewport",
        fromlist=["QtViewportWidget"],
    ).QtViewportWidget._preload_gpu_textures)

    assert "progress = QtCore.Signal(str, int, int)" in inspect.getsource(ModelLoadWorker)
    assert "progress = QtCore.Signal(str, int, int)" in inspect.getsource(ResourceModelLoadWorker)
    assert "raw = path.read_bytes()" in file_source
    assert 'raw.decode("utf-8", errors="replace")' in file_source
    assert "load_model_from_bytes" in file_source
    assert "load_model_from_file" not in file_source
    assert "self.progress.emit" in file_source
    assert "_prebuild_gpu_mesh_data_for_model(model)" in file_source
    assert "self.progress.emit" in resource_source
    assert "_prebuild_gpu_mesh_data_for_model(model)" in resource_loader_source
    assert "load_resource_model_from_game_resources" in resource_source
    assert "_load_resource_model_on_ui_thread" in start_resource_source
    assert "ResourceModelLoadWorker(" not in start_resource_source
    assert "load_resource_model_from_game_resources" in ui_resource_source
    assert "QThread" not in ui_resource_source
    assert "def update_progress" in toast_source
    assert "worker.progress.connect(self._on_model_load_progress)" in window_source
    assert "gpuUploadProgress.connect(self._on_viewport_gpu_upload_progress)" in window_source
    assert "existing is not None" in get_resource_manager_source
    assert "_resource_manager_dirs" in get_resource_manager_source
    assert "tex_cache.get" not in viewport_preload_source


def test_qt_realistic_texture_prewarm_loads_detail_textures_without_paint_stall() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    node = SimpleNamespace(
        vertices=[(0.0, 0.0, 0.0)],
        texture_clean="LMA_wall01.tga",
        texture="LMA_wall01",
        lightmap="LMA_wall01_lm",
        bump_map="mdl_bump",
        txi_envmaptexture="CM_Baremetal",
        txi_specularcolour="metal_spec",
        txi_bumpmaptexture="stone_bump",
        texture_names=["trim01", "NULL", "****", "None", "lma_wall01"],
    )
    helper = SimpleNamespace(
        vertices=[],
        texture_clean="should_not_load",
        lightmap="should_not_load_lm",
    )
    model = SimpleNamespace(
        all_nodes=lambda: [node, helper],
        mesh_nodes=lambda: [],
    )

    names = QtViewportWidget._texture_names_for_prewarm(model)

    assert names == [
        "lma_wall01",
        "lma_wall01_lm",
        "mdl_bump",
        "cm_baremetal",
        "metal_spec",
        "stone_bump",
        "trim01",
    ]

    prewarm_source = inspect.getsource(QtViewportWidget._prewarm_textures)
    deferred_txi_source = inspect.getsource(QtViewportWidget._on_deferred_txi_finished)

    assert "_texture_names_for_prewarm(model)" in prewarm_source
    assert "_texturePrewarmFinished.emit(model_id)" in prewarm_source
    assert "time_module.sleep(0.35)" not in prewarm_source
    assert "self._prewarm_textures(self.model)" in deferred_txi_source


def test_gpu_auto_clamp_diffuse_is_disabled_for_module_geometry() -> None:
    from types import SimpleNamespace

    from src.core.rendering.gpu_diagnostics_records import _should_auto_clamp_diffuse

    atlas_like_node = SimpleNamespace(
        txi_clamp_s=False,
        txi_clamp_t=False,
        animate_uv=False,
        txi_proceduretype="",
        txi_blending=0,
        uvs=[(0.1, 0.2), (0.9, 0.2), (0.9, 0.8), (0.1, 0.8)],
    )

    assert _should_auto_clamp_diffuse(atlas_like_node, is_module=False) is True
    assert _should_auto_clamp_diffuse(atlas_like_node, is_module=True) is False


def test_module_mesh_properties_panel_lists_selects_and_hides_meshes() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()
    mesh_a = SimpleNamespace(
        name="room_a",
        is_mesh=True,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        texture="wall01",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    mesh_b = SimpleNamespace(
        name="room_b",
        is_mesh=True,
        vertices=[(0, 0, 0)],
        faces=[(0, 0, 0)],
        texture="greybox",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: [mesh_a, mesh_b],
        all_nodes=lambda: [mesh_a, mesh_b],
        bone_nodes=lambda: [],
        texture_list=lambda: ["wall01", "greybox"],
    )

    selected = []
    panel.moduleMeshSelected.connect(selected.append)
    panel.show_model(model)

    assert panel.module_mesh_tree.topLevelItemCount() == 2
    panel.module_mesh_tree.setCurrentItem(panel.module_mesh_tree.topLevelItem(0))
    assert selected[-1] is mesh_a

    panel._set_selected_meshes_hidden(True)
    assert mesh_a._gr_hidden is True
    assert panel.module_mesh_tree.topLevelItem(0).text(4) == "no"

    panel.module_mesh_tree.topLevelItem(0).setSelected(True)
    panel._hide_unselected_module_meshes()
    assert mesh_b._gr_hidden is True


def test_module_mesh_properties_panel_supports_multi_select_all() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()
    meshes = [
        SimpleNamespace(
            name=f"mesh_{index}",
            is_mesh=True,
            vertices=[(0, 0, 0)],
            faces=[(0, 0, 0)],
            texture="tex",
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
        for index in range(3)
    ]
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: meshes,
        all_nodes=lambda: meshes,
        bone_nodes=lambda: [],
        texture_list=lambda: ["tex"],
    )
    selected_batches = []
    panel.moduleMeshesSelected.connect(selected_batches.append)

    panel.show_model(model)
    panel.select_all_module_meshes()

    assert len(panel._selected_module_meshes()) == 3
    assert selected_batches[-1] == meshes


def test_module_mesh_panel_reports_when_node_exists_for_external_selection_sync() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    mesh = SimpleNamespace(
        name="Object76",
        is_mesh=True,
        vertices=[(0, 0, 0)],
        faces=[(0, 0, 0)],
        texture="lhr_wall107",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    helper = SimpleNamespace(name="headhook", is_mesh=False, vertices=[], faces=[])
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: [mesh],
        all_nodes=lambda: [mesh, helper],
        bone_nodes=lambda: [],
        texture_list=lambda: ["lhr_wall107"],
    )
    panel = QtPropertiesPanel()
    panel.show_model(model)

    assert panel.has_module_mesh(mesh) is True
    assert panel.has_module_mesh(helper) is False
    assert panel.select_module_meshes([mesh]) is True
    assert panel._selected_module_meshes() == [mesh]
    assert panel.select_module_meshes([helper]) is False
    assert panel._selected_module_meshes() == []


def test_sprite_material_panel_detects_and_edits_alpha_card_meshes() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.panels.qt_sprite_material_panel import QtSpriteMaterialPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    blade = SimpleNamespace(
        name="blade01",
        texture="w_lsabreblue",
        is_mesh=True,
        txi_blending=0,
        txi_alpha_test=0.0,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=0,
        alpha=1.0,
    )
    body = SimpleNamespace(
        name="hilt",
        texture="metal01",
        is_mesh=True,
        txi_blending=0,
        txi_alpha_test=0.0,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=0,
        alpha=1.0,
    )
    null_texture_card = SimpleNamespace(
        name="torso_g",
        texture="null",
        is_mesh=True,
        type_label="trimesh",
        txi_blending=0,
        txi_alpha_test=0.5,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=1,
        alpha=1.0,
    )
    dummy_bone = SimpleNamespace(
        name="weaponhook",
        texture="p_zaalbar02",
        is_mesh=True,
        type_label="dummy",
        txi_blending=0,
        txi_alpha_test=0.5,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=1,
        alpha=1.0,
    )
    saber_hilt = SimpleNamespace(
        name="LghtSbr09",
        texture="w_shortsbr_001",
        is_mesh=True,
        type_label="trimesh",
        txi_blending=0,
        txi_alpha_test=0.5,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=0,
        alpha=1.0,
    )
    saber_helper = SimpleNamespace(
        name="plane242",
        texture="w_lsabreblue01",
        is_mesh=True,
        is_saber=True,
        type_label="lightsaber",
        txi_blending=0,
        txi_alpha_test=0.0,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=0,
        alpha=1.0,
    )
    nodes = [blade, body, null_texture_card, dummy_bone, saber_hilt, saber_helper]
    model = SimpleNamespace(
        mesh_nodes=lambda: nodes,
        all_nodes=lambda: nodes,
    )
    panel = QtSpriteMaterialPanel()
    changed = []
    selected = []
    panel.spriteRenderChanged.connect(changed.append)
    panel.spriteSelected.connect(selected.append)
    panel.set_model(model)

    names = [panel.tree.topLevelItem(index).text(1) for index in range(panel.tree.topLevelItemCount())]
    assert panel.tree.topLevelItemCount() == 2
    assert names == ["blade01", "LghtSbr09"]
    assert "torso_g" not in names
    assert "weaponhook" not in names
    assert "plane242" not in names
    assert panel.tree.topLevelItem(0).text(4) == "Lighten"
    assert panel.tree.topLevelItem(0).text(7) == "key, glow 1.6"
    assert panel.tree.topLevelItem(1).text(3) == "Hilt"
    assert panel.tree.topLevelItem(1).text(4) == "Opaque"
    assert panel.tree.topLevelItem(1).text(7) == "hilt"

    panel.tree.setCurrentItem(panel.tree.topLevelItem(0))
    assert selected[-1] is blade
    assert panel.key_matte_check.isChecked() is True
    assert panel.glow_spin.value() == pytest.approx(1.6)
    panel._set_combo_value(panel.mode_combo, "cutout")
    panel.cutoff_spin.setValue(0.375)

    assert blade.txi_blending == 2
    assert blade.txi_alpha_test == pytest.approx(0.375)
    assert blade._gr_sprite_alpha_source == "luminance"
    assert blade._gr_sprite_glow == pytest.approx(1.6)
    assert getattr(blade, "_gr_revision", 0) > 0
    assert changed[-1] == [blade]

    panel.tree.topLevelItem(0).setCheckState(0, QtCore.Qt.Unchecked)
    assert blade._gr_hidden is True
    panel._reset_selected()
    assert blade.txi_blending == 0
    assert blade._gr_hidden is False


def test_wgpu_material_data_promotes_sprite_alpha_cards_to_alpha_queues() -> None:
    from src.core.rendering.mesh_render_data import _material_data

    alpha_card = SimpleNamespace(
        name="torso_g",
        texture="p_zaalbar01",
        is_mesh=True,
        alpha=1.0,
        txi_blending=0,
        txi_alpha_test=0.0,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=1,
        vertices=[],
        faces=[],
    )
    saber_card = SimpleNamespace(
        name="plane329",
        texture="w_lsabreturq01",
        is_mesh=True,
        alpha=1.0,
        txi_blending=0,
        txi_alpha_test=0.0,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=0,
        vertices=[],
        faces=[],
    )
    hilt = SimpleNamespace(
        name="LghtSbr09",
        texture="w_shortsbr_001",
        is_mesh=True,
        alpha=1.0,
        txi_blending=0,
        txi_alpha_test=0.5,
        txi_wateralpha=1.0,
        txi_decal=False,
        transparency_hint=0,
        vertices=[],
        faces=[],
    )

    assert _material_data(alpha_card, {}).alpha_mode == "MASK"
    saber_material = _material_data(saber_card, {})
    assert saber_material.alpha_mode == "BLEND"
    assert saber_material.blend_mode == "LIGHTEN"
    assert saber_material.sprite_alpha_source == 1
    assert saber_material.sprite_glow == pytest.approx(1.6)
    hilt_material = _material_data(hilt, {})
    assert hilt_material.alpha_mode == "OPAQUE"
    assert hilt_material.blend_mode == "ALPHA"
    assert hilt_material.sprite_alpha_source == 0
    assert hilt_material.sprite_glow == 0.0


def test_module_mesh_properties_panel_splits_meshes_nulls_and_walkmeshes() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()
    regular_mesh = SimpleNamespace(
        name="regular_mesh",
        is_mesh=True,
        vertices=[(0, 0, 0)],
        faces=[(0, 0, 0)],
        texture="wall",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    grey_geometry = SimpleNamespace(
        name="walkmesh_12",
        is_mesh=False,
        vertex_space=2,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        texture="",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    null_mesh = SimpleNamespace(
        name="external_null",
        is_mesh=True,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        texture="NULL",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: [regular_mesh, null_mesh],
        all_nodes=lambda: [regular_mesh, null_mesh, grey_geometry],
        bone_nodes=lambda: [],
        texture_list=lambda: ["wall"],
    )

    panel.show_model(model)

    mesh_names = [
        panel.module_mesh_tree.topLevelItem(index).text(0)
        for index in range(panel.module_mesh_tree.topLevelItemCount())
    ]
    walkmesh_names = [
        panel.module_walkmesh_tree.topLevelItem(index).text(0)
        for index in range(panel.module_walkmesh_tree.topLevelItemCount())
    ]
    null_names = [
        panel.module_null_mesh_tree.topLevelItem(index).text(0)
        for index in range(panel.module_null_mesh_tree.topLevelItemCount())
    ]
    assert mesh_names == ["regular_mesh"]
    assert null_names == ["external_null"]
    assert walkmesh_names == ["walkmesh_12"]
    assert panel.module_browser_tabs.tabText(1) == "NULL Meshes"
    assert panel.module_browser_tabs.tabText(2) == "Walkmeshes"


def test_module_mesh_properties_panel_lists_coloaded_walkmesh_overlay_nodes() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()
    overlay_node = SimpleNamespace(
        name="m01aa_01a_overlay",
        flags=0x0200,
        vertex_space=1,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        texture="walkmesh",
        _gr_walkmesh_overlay_proxy=True,
        _gr_hidden=True,
    )
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: [],
        all_nodes=lambda: [],
        bone_nodes=lambda: [],
        texture_list=lambda: [],
        _gr_extra_module_mesh_nodes=[overlay_node],
    )

    selected_batches = []
    panel.moduleMeshesSelected.connect(selected_batches.append)
    panel.show_model(model)

    assert panel.module_walkmesh_tree.topLevelItemCount() == 1
    assert panel.module_walkmesh_tree.topLevelItem(0).text(0) == "m01aa_01a_overlay"
    assert panel.module_walkmesh_tree.topLevelItem(0).text(4) == "no"
    panel.module_walkmesh_tree.setCurrentItem(panel.module_walkmesh_tree.topLevelItem(0))
    assert selected_batches[-1] == [overlay_node]


def test_coloaded_walkmesh_overlay_aligns_to_existing_model_walkmesh_bounds() -> None:
    from src.gui.qt_lib.windows.qt_main_window import (
        _walkmesh_overlay_node_from_wok,
        _walkmesh_overlay_offset_for_model,
    )

    face = SimpleNamespace(v1=0, v2=1, v3=2, surface=7)
    wok = SimpleNamespace(
        verts=[(100.0, 200.0, 5.0), (110.0, 200.0, 5.0), (100.0, 210.0, 5.0)],
        faces=[face],
    )
    reference_walkmesh = SimpleNamespace(
        name="walkmesh_12",
        flags=0x0200,
        vertex_space=2,
        vertices=[(10.0, 20.0, 1.0), (20.0, 20.0, 1.0), (10.0, 30.0, 1.0)],
        faces=[(0, 1, 2)],
    )
    model = SimpleNamespace(
        all_nodes=lambda: [reference_walkmesh],
        render_bounds=lambda: ((10.0, 20.0, 1.0), (20.0, 30.0, 1.0)),
    )

    offset = _walkmesh_overlay_offset_for_model(model, wok)
    proxy = _walkmesh_overlay_node_from_wok(wok, "K1:m01aa_01a.wok", offset)

    assert offset == (-90.0, -180.0, -4.0)
    assert proxy.name == "m01aa_01a_overlay"
    assert proxy.vertices == reference_walkmesh.vertices
    assert proxy.faces == [(0, 1, 2)]
    assert proxy.face_mats == [7]
    assert proxy._gr_walkmesh_overlay_proxy is True
    assert proxy._gr_hidden is True


def test_coloaded_walkmesh_overlay_visibility_syncs_renderer_state() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    proxy = SimpleNamespace(_gr_hidden=True)
    renderer = SimpleNamespace(_walkmesh_overlay=SimpleNamespace(_gr_module_node=proxy), show_walkmesh=True)
    button_states = []
    button = SimpleNamespace(setChecked=lambda checked: button_states.append(bool(checked)))
    window = SimpleNamespace(viewport=SimpleNamespace(_renderer=renderer, walkmesh_button=button))

    QtGhostRiggerMainWindow._sync_walkmesh_overlay_visibility(window)

    assert renderer.show_walkmesh is False
    assert button_states[-1] is False

    proxy._gr_hidden = False
    QtGhostRiggerMainWindow._sync_walkmesh_overlay_visibility(window)

    assert renderer.show_walkmesh is True
    assert button_states[-1] is True


def test_hidden_module_mesh_panel_selection_is_not_forwarded_to_viewport() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    calls = []
    viewport = SimpleNamespace(set_selected_meshes=lambda nodes: calls.append(list(nodes)))
    window = SimpleNamespace(viewport=viewport)
    hidden = SimpleNamespace(name="001ebo1_overlay", _gr_hidden=True)
    visible = SimpleNamespace(name="WALK1", _gr_hidden=False)

    QtGhostRiggerMainWindow._on_module_meshes_selected_from_panel(window, [hidden])
    assert calls == []

    QtGhostRiggerMainWindow._on_module_meshes_selected_from_panel(window, [visible])
    assert calls == [[visible]]


def test_qt_viewport_exposes_mesh_multiselect_box_and_ctrl_a() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_skeleton_panel import node_browser_role
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = _qt_viewport_widget_source()

    assert "meshSelectionChanged = QtCore.Signal(list)" in source
    assert "meshHovered = QtCore.Signal(object)" in source
    assert "def set_selected_meshes" in source
    assert "def select_all_meshes" in source
    assert "QtCore.Qt.Key_A" in source
    assert "def _mesh_nodes_in_rect" in source
    assert "def _all_geometry_nodes" in source
    assert "def _is_selectable_mesh_node" in source
    assert "QtWidgets.QRubberBand" in source
    assert "def _front_facing_score" in source
    assert "def _point_in_triangle" in source
    assert QtViewportWidget._is_selectable_mesh_node(SimpleNamespace(is_saber=True, vertices=[1], faces=[1])) is False
    assert node_browser_role(SimpleNamespace(is_saber=True, is_mesh=True), "lightsaber") == "Lightsaber"


def test_qt_viewport_mesh_pick_requires_real_triangle_and_hover_outline() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = _qt_viewport_widget_source()
    pick_source = inspect.getsource(QtViewportWidget._mesh_hit_test_detail)
    release_source = inspect.getsource(QtViewportWidget._release_lmb)
    overlay_source = inspect.getsource(QtViewportWidget._draw_gpu_viewport_overlays)

    assert "self._hovered_mesh_node = None" in source
    assert "_update_mesh_hover(event)" in source
    assert "self.meshHovered.emit(mesh_node)" in source
    assert "self.meshHovered.emit(None)" in source
    assert "_mesh_hit_test_detail(x, y, allow_gpu=False)" in source
    assert "_mesh_hit_test_detail(x, y, allow_gpu=False)" in release_source
    assert "_draw_selected_model_outline(draw, w, h)" in overlay_source
    hover_outline_source = inspect.getsource(QtViewportWidget._draw_hovered_mesh_outline)
    hover_update_source = inspect.getsource(QtViewportWidget._update_mesh_hover)
    projected_bounds_source = inspect.getsource(QtViewportWidget._projected_mesh_bounds)
    selected_outline_source = inspect.getsource(QtViewportWidget._draw_selected_model_outline)
    assert "_draw_hovered_mesh_outline(draw, w, h)" in selected_outline_source
    assert "hull =" not in selected_outline_source
    assert "255, 212, 0, 230" not in selected_outline_source
    assert 'node is getattr(self._renderer, "selected_node", None)' in hover_outline_source
    assert "self._mesh_hover_suppressed_for_animation()" in hover_outline_source
    assert "self._mesh_hover_suppressed_for_animation()" in hover_update_source
    assert "animation hover suppressed" in hover_update_source
    assert "self._renderer._get_world_verts_for_node(node)" in projected_bounds_source
    assert "cpu_skin_vbo_arrays" not in source
    assert "_ray_triangle_intersection" in source
    assert "allow_gpu: bool = True" in pick_source
    assert "if allow_gpu:" in pick_source
    default_pick_source = release_source[release_source.index("if self._renderer.show_bones:"):]
    assert default_pick_source.index("_mesh_hit_test_detail(x, y, allow_gpu=False)") < default_pick_source.index("_light_hit_test(x, y)")
    assert "area + dist2" not in pick_source
    assert "_hit_test_model_bounds" not in release_source

    hit = QtViewportWidget._ray_triangle_intersection(
        (0.25, 0.25, 1.0),
        (0.0, 0.0, -1.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    miss = QtViewportWidget._ray_triangle_intersection(
        (1.25, 1.25, 1.0),
        (0.0, 0.0, -1.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    assert hit == 1.0
    assert miss is None


def test_qt_viewport_context_menu_does_not_pick_on_right_click() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._show_mesh_context_menu)
    hide_source = inspect.getsource(QtViewportWidget._set_selected_meshes_hidden)

    assert "self.set_selected_node(node)" not in source
    assert "if not self._selected_meshes" not in source
    assert "node is not None and id(node) not in selected_ids" in source
    assert "Hide Selected" in source
    assert "unhide_all_action.setEnabled(self.model is not None)" in source
    assert "_set_selected_meshes_hidden(True)" in source
    assert "self.set_selected_meshes([])" not in hide_source


def test_qt_gpu_viewport_disables_gpu_culling_for_cpu_parity() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._render_gpu_frame)
    assert "cull_faces = False" in source


def test_transform_gizmo_controller_applies_translate_rotate_scale_and_cancel() -> None:
    from types import SimpleNamespace

    import pytest

    from src.core.gizmo.gizmo_mode import GizmoMode
    from src.core.gizmo.transform_controller import TransformController
    from src.core.gizmo.transform_gizmo import TransformGizmo

    class _Camera:
        fov = 45.0

        def _view_matrix(self):
            return (
                (1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
                (0.0, -1.0, 0.0),
                (0.0, 10.0, 0.0),
            )

    camera = _Camera()
    node = SimpleNamespace(
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        vertices=[(1.0, 2.0, 3.0)],
        compute_bounds=lambda: None,
    )
    controller = TransformController()

    controller.begin_drag(node, GizmoMode.TRANSLATE, "TRANSLATE_X", (100, 100), camera, depth=5.0)
    controller.drag((120, 100), camera, 500)
    assert node.position[0] > 0.0
    controller.cancel()
    assert node.position == pytest.approx((0.0, 0.0, 0.0))

    controller.begin_drag(node, GizmoMode.ROTATE, "ROTATE_Z", (100, 100), camera, depth=5.0)
    controller.drag((140, 100), camera, 500)
    assert node.rotation[2] < 0.0
    before, after, changed = controller.end_drag()
    assert changed is node
    assert before is not None and after is not None
    assert after.rotation != pytest.approx(before.rotation)

    controller.begin_drag(node, GizmoMode.SCALE, "SCALE_UNIFORM", (100, 100), camera, depth=5.0)
    controller.drag((120, 90), camera, 500)
    assert node.vertices[0][0] > 1.0
    assert node.vertices[0][1] > 2.0

    gizmo = TransformGizmo()
    assert gizmo.mode == GizmoMode.TRANSLATE
    assert gizmo.cycle_mode() == GizmoMode.ROTATE
    assert gizmo.cycle_mode() == GizmoMode.SCALE
    assert gizmo.cycle_mode() == GizmoMode.TRANSLATE


def test_gizmo_picker_hits_projected_rotation_polylines() -> None:
    from src.core.gizmo.gizmo_picker import GizmoPicker

    picker = GizmoPicker()
    handle = {
        "name": "ROTATE_Z",
        "kind": "polyline",
        "points": [(10, 10), (50, 10), (50, 50)],
        "radius": 8,
    }

    assert picker.hit_test((30, 14), [handle]) == "ROTATE_Z"
    assert picker.hit_test((30, 30), [handle]) is None


def test_gizmo_picker_prioritizes_uniform_scale_center_handle() -> None:
    from src.core.gizmo.gizmo_picker import GizmoPicker

    picker = GizmoPicker()
    handles = [
        {"name": "SCALE_X", "kind": "segment", "start": (50, 50), "end": (100, 50), "radius": 10},
        {"name": "SCALE_UNIFORM", "kind": "point", "pos": (50, 50), "radius": 14, "priority": 10},
    ]

    assert picker.hit_test((50, 50), handles) == "SCALE_UNIFORM"


def test_qt_viewport_selection_does_not_auto_recenter_but_z_frames_selection() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import pytest
    from PySide6 import QtWidgets

    from src.core.geometry.model_data import ModelNode
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    viewport.camera.target = [0.0, 0.0, 0.0]
    viewport.camera.distance = 10.0
    viewport.camera.azimuth = 90.0
    viewport.camera.elevation = 0.0
    old_eye = viewport.camera.eye()

    mesh = ModelNode(
        name="selected_face",
        vertices=[(10.0, 0.0, 0.0), (12.0, 0.0, 0.0), (10.0, 2.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    face_bounds = ((10.0, 0.0, 0.0), (12.0, 2.0, 0.0))

    viewport.set_selected_node(mesh, orbit_bounds=face_bounds)

    assert viewport.camera.target == pytest.approx([0.0, 0.0, 0.0])
    assert viewport.camera.eye() == pytest.approx(old_eye)

    viewport.camera.target = [0.0, 0.0, 0.0]
    viewport.frame_selection_or_all()

    assert viewport.camera.target == pytest.approx([11.0, 1.0, 0.0])


def test_qt_viewport_transform_typein_commits_mesh_vertices_without_type_error() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    node = SimpleNamespace(
        name="typein_mesh",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    try:
        viewport._renderer.selected_node = node
        viewport._sync_transform_typein_bar()

        viewport._on_transform_typein_edited("X", "1.25")

        assert node.position == pytest.approx((1.25, 0.0, 0.0))
        assert viewport.undo() is True
        assert node.position == pytest.approx((0.0, 0.0, 0.0))
        assert viewport.redo() is True
        assert node.position == pytest.approx((1.25, 0.0, 0.0))
    finally:
        viewport.deleteLater()


def test_qt_lighting_panel_editor_refresh_preserves_selected_light() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.panels.qt_lighting_panel import QtLightingPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    first = SimpleNamespace(
        name="AuroraLight001",
        is_light=True,
        light_kind="point",
        light_radius=1.5,
        light_enabled=True,
        light_multiplier=1.0,
        light_cone_degrees=45.0,
        light_area_size=1.0,
        light_ambient_only=False,
    )
    second = SimpleNamespace(
        name="AuroraLight223",
        is_light=True,
        light_kind="point",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        light_radius=11.75,
        light_enabled=True,
        light_multiplier=1.0,
        light_cone_degrees=45.0,
        light_area_size=1.0,
        light_ambient_only=False,
    )
    panel = QtLightingPanel()
    panel.set_model(SimpleNamespace(all_nodes=lambda: [first, second]))
    panel.tree.setCurrentItem(panel.tree.topLevelItem(1))
    second.position = (4.0, 5.0, 6.0)

    panel.radius_spin.setValue(12.25)

    assert panel._selected is second
    assert second.light_radius == 12.25
    assert second.position == (4.0, 5.0, 6.0)
    assert first.light_radius == 1.5
    assert panel.tree.currentItem().data(0, QtCore.Qt.UserRole) is second
    assert panel.findChild(QtWidgets.QGroupBox, "AddLightToSceneGroup") is not None
    assert panel.findChild(QtWidgets.QGroupBox, "LightingSystemGroup") is not None
    assert panel.pos_spins == []


def test_qt_viewport_can_pick_light_gizmos() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    light = SimpleNamespace(
        name="AuroraLight223",
        is_light=True,
        position=(1.0, 2.0, 3.0),
    )
    mesh = SimpleNamespace(
        name="room_mesh",
        is_light=False,
        position=(0.0, 0.0, 0.0),
    )
    viewport = QtViewportWidget()
    viewport.model = SimpleNamespace(all_nodes=lambda: [mesh, light])
    viewport._renderer._node_world_transform = lambda node: (node.position, (0.0, 0.0, 0.0, 1.0), True)
    viewport._renderer._proj = lambda _x, _y, _z, _w, _h: (100, 120, 5.0)

    assert viewport._light_hit_test(104, 123) is light
    assert viewport._light_hit_test(140, 160) is None


def test_qt_viewport_preserves_module_mesh_node_selection_under_scene_root_tags() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.geometry.model_data import ModelNode
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = ModelNode(name="M01aa_01a")
    root._gr_scene_object_root = True
    root._gr_scene_object_id = "scene-module"
    mesh = ModelNode(
        name="Object3234",
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    mesh.parent = root
    mesh._gr_scene_object_root_ref = root
    mesh._gr_scene_object_id = "scene-module"
    viewport = QtViewportWidget()
    viewport._gpu_renderer = SimpleNamespace(selected_node=None, selected_nodes=[])
    try:
        viewport.set_selected_node(mesh, orbit_bounds=((0.0, 0.0, 0.0), (1.0, 1.0, 0.0)))

        assert viewport._renderer.selected_node is mesh
        assert viewport._gpu_renderer.selected_node is mesh
        assert viewport._gpu_renderer.selected_nodes == [mesh]
        assert viewport.get_selected_meshes() == [mesh]
        assert getattr(mesh, "_gr_selected", False) is True
    finally:
        viewport.deleteLater()


def test_wgpu_gpu_pick_miss_falls_back_to_cpu_mesh_picker() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.rendering.picking import PickHit
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    mesh = SimpleNamespace(name="CM_Floor")
    viewport = QtViewportWidget()
    viewport.model = SimpleNamespace()
    viewport._gpu_renderer = SimpleNamespace(
        get_capabilities=lambda: SimpleNamespace(supports_gpu_id_picking=True),
        pick=lambda *_args, **_kwargs: PickHit(
            hit=False,
            renderer_backend="wgpu_d3d12",
            diagnostic={"method": "WGPU GPU ID", "result": "miss"},
        ),
    )

    class _CpuPicker:
        def __init__(self) -> None:
            self.called = False

        def pick(self, request, scene, camera):
            self.called = True
            return PickHit(
                hit=True,
                object_ref=mesh,
                hit_kind="mesh",
                diagnostic={"method": "CPU raycast", "face_bounds": ((0, 0, 0), (1, 1, 0))},
            )

    cpu_picker = _CpuPicker()
    viewport._picking_provider = cpu_picker
    try:
        hit = viewport._mesh_hit_test_detail(10, 12)

        assert cpu_picker.called is True
        assert hit == (mesh, ((0, 0, 0), (1, 1, 0)))
        assert viewport._last_pick_diagnostics["method"] == "CPU raycast"
    finally:
        viewport.deleteLater()


def test_wgpu_helper_hit_test_selects_screen_space_helpers_before_meshes() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    helper = SimpleNamespace(
        name="Waypoint_Helper",
        type_label="dummy",
        position=(1.0, 2.0, 3.0),
        vertices=[],
        faces=[],
    )
    mesh = SimpleNamespace(
        name="CM_Floor",
        is_mesh=True,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
    )
    viewport = QtViewportWidget()
    viewport.model = SimpleNamespace(all_nodes=lambda: [mesh, helper])
    viewport._gpu_renderer = SimpleNamespace(backend_id="wgpu_d3d12")
    viewport._renderer._node_world_transform = lambda node: (node.position, (0, 0, 0, 1), True)
    viewport._renderer._proj = lambda _x, _y, _z, _w, _h: (100, 100, 2.0)
    try:
        assert viewport._helper_hit_test(104, 103) is helper
        assert viewport._helper_hit_test(150, 150) is None
    finally:
        viewport.deleteLater()


def test_viewport_toolbar_exposes_helper_toggle_and_selection_mode_menu() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    try:
        helper_button = viewport.findChild(QtWidgets.QPushButton, "ViewportDummyHelpersButton")
        light_helper_button = viewport.findChild(QtWidgets.QPushButton, "ViewportLightHelpersButton")
        mode_button = viewport.findChild(QtWidgets.QToolButton, "ViewportSelectionModeButton")

        assert helper_button is viewport.dummy_helpers_button
        assert light_helper_button is viewport.light_helpers_button
        assert viewport.dummy_helpers_button.isCheckable()
        assert viewport.dummy_helpers_button.isChecked() is True
        assert viewport.light_helpers_button.isCheckable()
        assert viewport.light_helpers_button.isChecked() is True
        assert bool(getattr(viewport._renderer, "show_dummy_helpers", False)) is True
        assert bool(getattr(viewport._renderer, "show_light_gizmos", False)) is True
        assert bool(getattr(viewport._renderer, "show_light_radius_volumes", False)) is True
        assert mode_button is viewport.selection_mode_button
        assert [action.data() for action in mode_button.menu().actions()] == [
            "object",
            "mesh",
            "helpers",
            "lights",
            "cameras",
        ]

        viewport.set_viewport_selection_mode("helpers")
        assert viewport._viewport_selection_mode == "helpers"
        assert mode_button.toolTip() == "Viewport selection mode: Helpers"
        assert not mode_button.icon().isNull()

        viewport.set_dummy_helper_visibility(False)
        assert viewport.dummy_helpers_button.isChecked() is False
        assert bool(getattr(viewport._renderer, "show_dummy_helpers", True)) is False
        viewport.set_light_helper_visibility(False, False)
        assert viewport.light_helpers_button.isChecked() is False
        assert bool(getattr(viewport._renderer, "show_light_gizmos", True)) is False
        assert bool(getattr(viewport._renderer, "show_light_radius_volumes", True)) is False
    finally:
        viewport.deleteLater()


def test_viewport_selection_mode_filters_click_targets() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    class _Position:
        def x(self) -> int:
            return 100

        def y(self) -> int:
            return 100

    class _Event:
        def position(self):
            return _Position()

        def modifiers(self):
            return QtCore.Qt.NoModifier

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    mesh = SimpleNamespace(name="Mesh", is_mesh=True, vertices=[(0, 0, 0)], faces=[(0, 0, 0)])
    helper = SimpleNamespace(name="Waypoint_Helper", type_label="dummy")
    light = SimpleNamespace(name="AuroraLight001", is_light=True)
    camera = SimpleNamespace(name="Camera001", is_camera=True)
    selected: list[object | None] = []
    viewport.set_selected_node = lambda node, *args, **kwargs: selected.append(node)
    viewport._mesh_hit_test_detail = lambda *args, **kwargs: (mesh, None)
    viewport._helper_hit_test = lambda *args, **kwargs: helper
    viewport._light_hit_test = lambda *args, **kwargs: light
    viewport._camera_hit_test = lambda *args, **kwargs: camera
    viewport._renderer.show_bones = False
    try:
        viewport.set_viewport_selection_mode("helpers")
        viewport._release_lmb(_Event())
        viewport.set_viewport_selection_mode("lights")
        viewport._release_lmb(_Event())
        viewport.set_viewport_selection_mode("cameras")
        viewport._release_lmb(_Event())
        viewport.set_viewport_selection_mode("mesh")
        viewport._release_lmb(_Event())

        assert selected == [helper, light, camera, mesh]
    finally:
        viewport.deleteLater()


def test_viewport_marquee_selection_respects_active_selection_mode() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    mesh = SimpleNamespace(name="Mesh", is_mesh=True, vertices=[(0, 0, 0)], faces=[(0, 0, 0)])
    helper = SimpleNamespace(name="Waypoint_Helper", type_label="dummy", position=(10, 10, 0))
    light = SimpleNamespace(name="AuroraLight001", is_light=True, position=(20, 20, 0))
    camera_node = SimpleNamespace(name="Camera001", is_camera=True, position=(30, 30, 0))
    camera = SimpleNamespace(
        id="cam1",
        original_ref=camera_node,
        position=(30, 30, 0),
        visible=True,
        deleted=False,
        selected=False,
        metadata={},
        apply_to_original=lambda: None,
    )
    viewport = QtViewportWidget()
    viewport.model = SimpleNamespace(all_nodes=lambda: [mesh, helper, light, camera_node])
    viewport.camera_manager.cameras = [camera]
    viewport._renderer._node_world_transform = lambda node: (getattr(node, "position", (0, 0, 0)), (0, 0, 0, 1), True)
    viewport._renderer._proj = lambda x, y, z, w, h: (x, y, 1.0)
    viewport._projected_mesh_bounds = lambda node, width, height: (0, 0, 5, 5, [], []) if node is mesh else None
    rect = QtCore.QRect(QtCore.QPoint(0, 0), QtCore.QPoint(25, 25))
    try:
        viewport.set_viewport_selection_mode("helpers")
        viewport._apply_marquee_selection(rect, QtCore.Qt.NoModifier)
        assert viewport._renderer.selected_node is helper
        assert getattr(helper, "_gr_selected", False) is True
        assert getattr(light, "_gr_light_selected", False) is False

        viewport.set_viewport_selection_mode("lights")
        viewport._apply_marquee_selection(rect, QtCore.Qt.NoModifier)
        assert viewport._renderer.selected_node is light
        assert getattr(light, "_gr_light_selected", False) is True
        assert getattr(helper, "_gr_selected", False) is False

        viewport.set_viewport_selection_mode("cameras")
        viewport._apply_marquee_selection(QtCore.QRect(QtCore.QPoint(25, 25), QtCore.QPoint(35, 35)), QtCore.Qt.NoModifier)
        assert viewport._renderer.selected_node is camera_node
        assert camera.selected is True

        viewport.set_viewport_selection_mode("object")
        viewport._apply_marquee_selection(rect, QtCore.Qt.NoModifier)
        assert mesh in viewport._selected_viewport_nodes
        assert helper in viewport._selected_viewport_nodes
        assert light in viewport._selected_viewport_nodes
        assert camera_node not in viewport._selected_viewport_nodes
    finally:
        viewport.deleteLater()


def test_viewport_hover_respects_active_selection_mode() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    class _Position:
        def x(self) -> int:
            return 100

        def y(self) -> int:
            return 100

    class _Event:
        def position(self):
            return _Position()

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    mesh = SimpleNamespace(name="Mesh", is_mesh=True, vertices=[(0, 0, 0)], faces=[(0, 0, 0)])
    helper = SimpleNamespace(name="Waypoint_Helper", type_label="dummy")
    light = SimpleNamespace(name="AuroraLight001", is_light=True)
    camera = SimpleNamespace(name="Camera001", is_camera=True)
    viewport.model = SimpleNamespace()
    viewport._mesh_hit_test_detail = lambda *args, **kwargs: (mesh, None)
    viewport._helper_hit_test = lambda *args, **kwargs: helper
    viewport._light_hit_test = lambda *args, **kwargs: light
    viewport._camera_hit_test = lambda *args, **kwargs: camera
    try:
        viewport.set_viewport_selection_mode("helpers")
        viewport._update_mesh_hover(_Event())
        assert viewport._hovered_helper_node is helper
        assert viewport._hovered_mesh_node is None

        viewport.set_viewport_selection_mode("lights")
        viewport._update_mesh_hover(_Event())
        assert viewport._renderer._hovered_light is light
        assert viewport._hovered_helper_node is None

        viewport.set_viewport_selection_mode("cameras")
        viewport._update_mesh_hover(_Event())
        assert viewport._hovered_camera_node is camera

        viewport.set_viewport_selection_mode("mesh")
        viewport._update_mesh_hover(_Event())
        assert viewport._hovered_mesh_node is mesh
        assert viewport._hovered_camera_node is None
    finally:
        viewport.deleteLater()


def test_viewport_marquee_drag_only_updates_rubber_band_before_release() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    class _Position:
        def __init__(self, x: int, y: int) -> None:
            self._x = x
            self._y = y

        def x(self) -> int:
            return self._x

        def y(self) -> int:
            return self._y

    class _Event:
        def __init__(self, x: int, y: int, buttons=QtCore.Qt.LeftButton) -> None:
            self._position = _Position(x, y)
            self._buttons = buttons

        def position(self):
            return self._position

        def modifiers(self):
            return QtCore.Qt.NoModifier

        def buttons(self):
            return self._buttons

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    helper = SimpleNamespace(name="Waypoint_Helper", type_label="dummy", position=(15, 15, 0))
    viewport = QtViewportWidget()
    viewport.model = SimpleNamespace(all_nodes=lambda: [helper])
    viewport._renderer.show_bones = False
    viewport._renderer._node_world_transform = lambda node: (getattr(node, "position", (0, 0, 0)), (0, 0, 0, 1), True)
    viewport._renderer._proj = lambda x, y, z, w, h: (x, y, 1.0)
    try:
        viewport.set_viewport_selection_mode("helpers")
        viewport._press_lmb(_Event(0, 0))
        viewport._drag_lmb(_Event(25, 25))

        assert viewport._mesh_box_selecting is True
        assert viewport._renderer.selected_node is None
        assert getattr(helper, "_gr_selected", False) is False

        viewport._release_lmb(_Event(25, 25, buttons=QtCore.Qt.NoButton))
        assert viewport._renderer.selected_node is helper
        assert getattr(helper, "_gr_selected", False) is True
    finally:
        viewport.deleteLater()


def test_wgpu_helper_marquee_selects_on_release_without_live_cpu_projection() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    helper = SimpleNamespace(name="Waypoint_Helper", type_label="dummy", position=(15, 15, 0))
    viewport = QtViewportWidget()
    viewport.model = SimpleNamespace(all_nodes=lambda: [helper])
    viewport._gpu_renderer = SimpleNamespace(selected_node=None, selected_nodes=[], backend_id="wgpu_d3d12")
    calls = {"helper_rect": 0}

    def helper_nodes_in_rect(rect):
        calls["helper_rect"] += 1
        return [helper]

    viewport._helper_nodes_in_rect = helper_nodes_in_rect
    rect = QtCore.QRect(QtCore.QPoint(0, 0), QtCore.QPoint(25, 25))
    try:
        viewport.set_viewport_selection_mode("helpers")
        viewport._apply_marquee_selection(rect, QtCore.Qt.NoModifier, live=True)
        assert calls["helper_rect"] == 0
        assert viewport._renderer.selected_node is None

        viewport._apply_marquee_selection(rect, QtCore.Qt.NoModifier, live=False)
        assert calls["helper_rect"] == 1
        assert viewport._renderer.selected_node is helper
        assert getattr(helper, "_gr_selected", False) is True
    finally:
        viewport.deleteLater()


def test_wgpu_marquee_selection_uses_gpu_picker_for_mesh_mode() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.core.rendering.picking import PickHit
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    mesh = SimpleNamespace(name="Mesh", is_mesh=True, vertices=[(0, 0, 0)], faces=[(0, 0, 0)])

    def marquee_pick(request, scene, camera, rect):
        return [PickHit(hit=True, kind="mesh", object_ref=mesh)]

    viewport = QtViewportWidget()
    viewport.model = SimpleNamespace(all_nodes=lambda: [mesh])
    viewport._gpu_renderer = SimpleNamespace(
        selected_node=None,
        selected_nodes=[],
        backend_id="wgpu_d3d12",
        marquee_pick=marquee_pick,
    )
    viewport._mesh_nodes_in_rect = lambda rect: (_ for _ in ()).throw(AssertionError("CPU mesh marquee was used"))
    rect = QtCore.QRect(QtCore.QPoint(0, 0), QtCore.QPoint(25, 25))
    try:
        viewport.set_viewport_selection_mode("mesh")
        viewport._apply_marquee_selection(rect, QtCore.Qt.NoModifier, live=False)

        assert viewport._renderer.selected_node is mesh
        assert viewport._selected_meshes == [mesh]
        assert getattr(mesh, "_gr_selected", False) is True
    finally:
        viewport.deleteLater()


def test_qt_viewport_preserves_light_node_selection_under_scene_root_tags() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.geometry.model_data import ModelNode
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = ModelNode(name="M01aa_01a")
    root._gr_scene_object_root = True
    root._gr_scene_object_id = "scene-module"
    light = SimpleNamespace(
        name="AuroraLight223",
        is_light=True,
        position=(1.0, 2.0, 3.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent=root,
        _gr_scene_object_root_ref=root,
        _gr_scene_object_id="scene-module",
    )
    viewport = QtViewportWidget()
    viewport._gpu_renderer = SimpleNamespace(selected_node=None, selected_nodes=[])
    viewport._gizmo_world_position = lambda node: tuple(getattr(node, "position", (0.0, 0.0, 0.0)))
    try:
        viewport.set_selected_node(light)

        assert viewport._renderer.selected_node is light
        assert viewport._gpu_renderer.selected_node is light
        assert viewport._gpu_renderer.selected_nodes == []
        assert viewport.get_selected_meshes() == []
        assert getattr(light, "_gr_gizmo_world_position", None) == (1.0, 2.0, 3.0)
    finally:
        viewport.deleteLater()


def test_qt_viewport_preserves_null_helper_selection_under_scene_root_tags() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.geometry.model_data import ModelNode
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = ModelNode(name="M01aa_01a")
    root._gr_scene_object_root = True
    root._gr_scene_object_id = "scene-module"
    helper = SimpleNamespace(
        name="RoomNull01",
        parent=root,
        _gr_scene_object_root_ref=root,
        _gr_scene_object_id="scene-module",
        position=(2.0, 3.0, 4.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    viewport = QtViewportWidget()
    viewport._gizmo_world_position = lambda node: tuple(getattr(node, "position", (0.0, 0.0, 0.0)))
    try:
        viewport.set_selected_node(helper)

        assert viewport._renderer.selected_node is helper
        assert viewport.get_selected_meshes() == []
        assert getattr(helper, "_gr_gizmo_world_position", None) == (2.0, 3.0, 4.0)
    finally:
        viewport.deleteLater()


def test_moderngl_selection_stays_on_explicit_node_without_scene_child_expansion() -> None:
    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer

    root = SimpleNamespace(
        name="M01aa_01a",
        _gr_scene_object_root=True,
        _gr_scene_object_id="scene-module",
    )
    child = SimpleNamespace(
        name="Object3234",
        _gr_scene_object_id="scene-module",
        _gr_scene_object_root_ref=root,
    )
    other = SimpleNamespace(name="Other", _gr_scene_object_id="other")
    renderer = GpuRenderer()
    renderer.selected_node = root

    assert renderer._is_node_selected_for_render(root) is True
    assert renderer._is_node_selected_for_render(child) is False
    assert renderer._is_node_selected_for_render(other) is False


def test_moderngl_child_selection_does_not_select_sibling_meshes_or_lights() -> None:
    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer

    root = SimpleNamespace(
        name="M01aa_01a",
        _gr_scene_object_root=True,
        _gr_scene_object_id="scene-module",
    )
    selected_mesh = SimpleNamespace(
        name="Object3234",
        _gr_scene_object_id="scene-module",
        _gr_scene_object_root_ref=root,
    )
    sibling_mesh = SimpleNamespace(
        name="Object3258",
        _gr_scene_object_id="scene-module",
        _gr_scene_object_root_ref=root,
    )
    sibling_light = SimpleNamespace(
        name="AuroraLight273",
        is_light=True,
        _gr_scene_object_id="scene-module",
        _gr_scene_object_root_ref=root,
    )
    renderer = GpuRenderer()
    renderer.selected_node = selected_mesh

    assert renderer._is_node_selected_for_render(selected_mesh) is True
    assert renderer._is_node_selected_for_render(sibling_mesh) is False
    assert renderer._is_node_selected_for_render(sibling_light) is False

    renderer.selected_node = sibling_light

    assert renderer._is_node_selected_for_render(sibling_light) is True
    assert renderer._is_node_selected_for_render(selected_mesh) is False
    assert renderer._is_node_selected_for_render(sibling_mesh) is False


def test_wgpu_light_helper_line_buffer_matches_gizmo_line_stride(monkeypatch) -> None:
    import numpy as np

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

    captured = {}

    class _Device:
        def create_buffer_with_data(self, *, data, usage):
            captured["shape"] = tuple(data.shape)
            captured["data"] = np.asarray(data, dtype=np.float32).copy()
            captured["usage"] = usage
            return SimpleNamespace(data=captured["data"])

    fake_wgpu = SimpleNamespace(BufferUsage=SimpleNamespace(VERTEX=7))
    monkeypatch.setitem(__import__("sys").modules, "wgpu", fake_wgpu)

    renderer = WgpuRenderer()
    renderer.device = _Device()

    buffer, count = renderer._position_line_buffer(
        [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)],
        usage=fake_wgpu.BufferUsage.VERTEX,
    )

    assert buffer is not None
    assert count == 2
    assert captured["shape"] == (2, 3)
    assert captured["usage"] == fake_wgpu.BufferUsage.VERTEX
    assert captured["data"].tolist() == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]


def test_wgpu_mesh_hover_uses_explicit_hovered_node_and_toggle() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

    renderer = WgpuRenderer()
    hovered = SimpleNamespace(name="Object3258")
    sibling = SimpleNamespace(name="AuroraLight273", is_light=True)

    renderer.hovered_node = hovered
    renderer.show_mesh_hover = True

    assert renderer._is_hovered_mesh_data(SimpleNamespace(source=hovered)) is True
    assert renderer._is_hovered_mesh_data(SimpleNamespace(source=sibling)) is False

    renderer.show_mesh_hover = False
    assert renderer._is_hovered_mesh_data(SimpleNamespace(source=hovered)) is False

    renderer.show_mesh_hover = True
    hovered._gr_hidden = True
    assert renderer._is_hovered_mesh_data(SimpleNamespace(source=hovered)) is False


def test_qt_mesh_hover_uses_cpu_pick_even_when_gpu_pick_is_available() -> None:
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    hovered = SimpleNamespace(name="CM_Walls1")
    calls = []

    class _Position:
        def x(self):
            return 42

        def y(self):
            return 64

    viewport = SimpleNamespace(
        mesh_hover_enabled=True,
        model=object(),
        _transform_gizmo=SimpleNamespace(hovered_handle=None),
        _measurement_mode=False,
        _hovered_mesh_node=None,
        _hovered_mesh_face_bounds=None,
        meshHovered=SimpleNamespace(emit=lambda node: calls.append(("hover", node))),
        _request_render=lambda fast=False, **kwargs: calls.append(("render", fast, kwargs)),
    )

    def pick_detail(x, y, *, allow_gpu=True):
        calls.append(("pick", x, y, allow_gpu))
        return hovered, ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))

    viewport._mesh_hit_test_detail = pick_detail

    QtViewportWidget._update_mesh_hover(viewport, SimpleNamespace(position=lambda: _Position()))

    assert ("pick", 42, 64, False) in calls
    assert viewport._hovered_mesh_node is hovered
    assert calls[-1][0:2] == ("render", True)
    assert calls[-1][2]["reason"] == "viewport hover changed"


def test_qt_mesh_hover_is_suppressed_while_animation_pose_is_active() -> None:
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    calls = []

    class _Position:
        def x(self):
            return 42

        def y(self):
            return 64

    viewport = SimpleNamespace(
        mesh_hover_enabled=True,
        model=object(),
        _renderer=SimpleNamespace(_anim_pose=object()),
        _transform_gizmo=SimpleNamespace(hovered_handle=None),
        _measurement_mode=False,
        _hovered_mesh_node=object(),
        _hovered_mesh_face_bounds=((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
        _gpu_renderer=SimpleNamespace(hovered_node=object()),
        meshHovered=SimpleNamespace(emit=lambda node: calls.append(("hover", node))),
        _request_render=lambda fast=False, **kwargs: calls.append(("render", fast, kwargs)),
        _mesh_hit_test_detail=lambda *args, **kwargs: calls.append(("pick", args, kwargs)),
    )

    QtViewportWidget._update_mesh_hover(viewport, SimpleNamespace(position=lambda: _Position()))

    assert viewport._hovered_mesh_node is None
    assert viewport._hovered_mesh_face_bounds is None
    assert viewport._gpu_renderer.hovered_node is None
    assert not any(call[0] == "pick" for call in calls)
    assert calls[-1][0:2] == ("render", True)
    assert calls[-1][2]["reason"] == "animation hover suppressed"


def test_qt_viewport_clears_mesh_hover_during_camera_navigation() -> None:
    import inspect
    from types import SimpleNamespace

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._press_navigation)
    wheel_source = inspect.getsource(QtViewportWidget.eventFilter)
    hover_source = inspect.getsource(QtViewportWidget._update_mesh_hover)

    assert "_clear_mesh_hover" in source
    assert "_clear_viewport_hover(request=False)" in wheel_source
    assert "viewport hover changed" in hover_source
    assert "snap view animation" not in hover_source

    calls = []
    viewport = SimpleNamespace(
        _hovered_mesh_node=object(),
        _hovered_mesh_face_bounds=((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)),
        _gpu_renderer=SimpleNamespace(hovered_node=object()),
        meshHovered=SimpleNamespace(emit=lambda node: calls.append(("hover", node))),
        _request_render=lambda fast=False, **kwargs: calls.append(("render", fast, kwargs)),
    )

    cleared = QtViewportWidget._clear_mesh_hover(viewport, reason="camera orbit started")

    assert cleared is True
    assert viewport._hovered_mesh_node is None
    assert viewport._hovered_mesh_face_bounds is None
    assert viewport._gpu_renderer.hovered_node is None
    assert ("hover", None) in calls
    assert calls[-1][0:2] == ("render", True)
    assert calls[-1][2]["reason"] == "camera orbit started"


def test_wgpu_light_volume_helpers_match_moderngl_editor_sizes() -> None:
    from src.core.lighting.light_gizmo_renderer import LIGHT_HELPER_POINT_RADIUS, LIGHT_HELPER_SPOT_LENGTH
    from src.core.lighting.render_data import SceneLightRenderData, build_light_volume_line_batches

    point = SceneLightRenderData(
        light_id=1,
        node_id="point",
        name="AuroraLight001",
        enabled=True,
        light_type="aurora_point",
        position=(0.0, 0.0, 0.0),
        direction=(0.0, 0.0, -1.0),
        color_rgb=(1.0, 1.0, 1.0),
        intensity=1.0,
        radius=50.0,
        cone_angle_degrees=45.0,
        area_size=8.0,
        ambient_only=False,
        cast_shadows=True,
        group="",
        selected=False,
        hovered=False,
        visible=True,
        revision=0,
    )
    spot = SceneLightRenderData(
        **{
            **point.__dict__,
            "light_id": 2,
            "node_id": "spot",
            "name": "Spot",
            "light_type": "spot",
            "radius": 80.0,
        }
    )

    batches = build_light_volume_line_batches(
        SimpleNamespace(lights=(point, spot), show_helpers=True, show_volumes=True)
    )
    vertices_by_color = [vertices for _color, vertices in batches]
    all_vertices = [vertex for vertices in vertices_by_color for vertex in vertices]

    assert max(abs(vertex[0]) for vertex in all_vertices) <= LIGHT_HELPER_POINT_RADIUS + 0.001
    assert min(vertex[2] for vertex in all_vertices) >= -LIGHT_HELPER_SPOT_LENGTH - 0.001


def test_wgpu_light_helper_color_uses_theme_palette_not_light_tint() -> None:
    from src.core.lighting.render_data import SceneLightRenderData, build_light_helper_line_batches

    light = SceneLightRenderData(
        light_id=1,
        node_id="point",
        name="AuroraLight001",
        enabled=True,
        light_type="aurora_point",
        position=(0.0, 0.0, 0.0),
        direction=(0.0, 0.0, -1.0),
        color_rgb=(0.05, 0.2, 1.0),
        intensity=1.0,
        radius=5.0,
        cone_angle_degrees=45.0,
        area_size=1.0,
        ambient_only=False,
        cast_shadows=True,
        group="",
        selected=False,
        hovered=False,
        visible=True,
        revision=0,
    )

    batches = build_light_helper_line_batches(
        SimpleNamespace(
            lights=(light,),
            show_helpers=True,
            helper_palette={"point": (1.0, 0.82, 0.10), "aurora_point": (1.0, 0.82, 0.10)},
        )
    )

    assert batches
    assert batches[0][0] == (1.0, 0.82, 0.10)


def test_light_picker_hits_visible_projected_light_volume_ring() -> None:
    from src.core.lighting.light_picker import LightPicker

    node = SimpleNamespace(
        is_light=True,
        light_kind="aurora_point",
        light_radius=4.0,
        position=(0.0, 0.0, 1.0),
    )

    def project(x, y, z, _width, _height):
        return (100.0 + x * 20.0, 100.0 + y * 20.0, float(z))

    def world_transform(light):
        return light.position, (0.0, 0.0, 0.0, 1.0), False

    picker = LightPicker(max_screen_distance=8)

    assert picker.hit_test([node], 113, 100, 400, 300, project, world_transform, include_volumes=False) is None
    assert picker.hit_test([node], 113, 100, 400, 300, project, world_transform, include_volumes=True) is node
    assert picker.hit_test([node], 113, 100, 400, 300, project, world_transform) is node


def test_wgpu_scene_lighting_only_drives_realistic_base_modes() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.rendering.viewport_display import ViewportDisplayMode, ViewportDisplayOptions

    renderer = WgpuRenderer()
    lighting = SimpleNamespace(mode="scene", diffuse_enabled=True)

    assert renderer._scene_lighting_enabled(lighting, ViewportDisplayOptions(display_mode=ViewportDisplayMode.FULL_MATERIAL)) is True
    assert renderer._scene_lighting_enabled(lighting, ViewportDisplayOptions(display_mode=ViewportDisplayMode.TEXTURED)) is True
    assert renderer._scene_lighting_enabled(lighting, ViewportDisplayOptions(display_mode=ViewportDisplayMode.SHADED)) is False
    assert renderer._scene_lighting_enabled(lighting, ViewportDisplayOptions(display_mode=ViewportDisplayMode.SOLID)) is False


def test_wgpu_bas_attachment_follows_animated_socket_matrix() -> None:
    import numpy as np

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.geometry.model_data import ModelNode

    renderer = WgpuRenderer()
    renderer._active_anim_pose = SimpleNamespace(
        nodes={
            "rhand": SimpleNamespace(
                position=(2.0, 3.0, 4.0),
                rotation=(0.0, 0.0, 0.0, 1.0),
            )
        },
        nodes_by_index={},
        duplicate_node_names=set(),
    )
    prepared = np.eye(4, dtype=np.float32)
    prepared[0, 3] = 12.5
    body = ModelNode(name="body")
    socket = ModelNode(name="rhand", parent=body)
    body.children.append(socket)
    weapon_root = ModelNode(name="weaponroot", parent=socket)
    weapon_root._gr_bas_attachment_root = True
    weapon_root._gr_bas_attachment_layer = True
    weapon_root._gr_bas_socket_name = "rhand"
    socket.children.append(weapon_root)
    blade = ModelNode(name="blade", parent=weapon_root)
    blade.position = (0.0, 0.0, 0.25)
    blade._gr_bas_attachment_layer = True
    blade._gr_bas_attachment_root_ref = weapon_root
    weapon_root.children.append(blade)
    mesh_data = SimpleNamespace(source=blade, is_skinned=False, world_matrix=prepared)

    matrix = renderer._mesh_model_matrix(mesh_data)

    assert matrix[0, 3] == pytest.approx(2.0)
    assert matrix[1, 3] == pytest.approx(3.0)
    assert matrix[2, 3] == pytest.approx(4.25)


def test_wgpu_bas_head_skin_uses_animated_socket_root_not_head_node_offset() -> None:
    import numpy as np

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.geometry.model_data import ModelNode

    renderer = WgpuRenderer()
    renderer._active_anim_pose = SimpleNamespace(
        nodes={
            "headhook": SimpleNamespace(
                position=(0.25, -0.5, 1.75),
                rotation=(0.0, 0.0, 0.0, 1.0),
            )
        },
        nodes_by_index={},
        duplicate_node_names=set(),
    )
    prepared = np.eye(4, dtype=np.float32)
    body = ModelNode(name="body")
    socket = ModelNode(name="headhook", parent=body)
    body.children.append(socket)
    head_root = ModelNode(name="pmha01", parent=socket)
    head_root._gr_bas_attachment_root = True
    head_root._gr_bas_attachment_layer = True
    head_root._gr_bas_socket_name = "headhook"
    socket.children.append(head_root)
    head_skin = ModelNode(name="head", parent=head_root, flags=0x61)
    head_skin.position = (0.0, 0.0, 2.0)
    head_skin._gr_bas_attachment_layer = True
    head_skin._gr_bas_attachment_root_ref = head_root
    head_root.children.append(head_skin)
    mesh_data = SimpleNamespace(source=head_skin, is_skinned=False, world_matrix=prepared)

    matrix = renderer._mesh_model_matrix(mesh_data)

    np.testing.assert_allclose(matrix[:3, 3], np.asarray([0.25, -0.5, 1.75], dtype=np.float32), atol=1e-6)


def test_bas_runtime_contract_is_documented_and_guarded() -> None:
    import inspect
    from pathlib import Path

    from src.adapters.rendering import mesh_render_data
    from src.adapters.rendering import moderngl_renderer_impl as gpu_renderer_impl
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

    contract_path = Path(__file__).resolve().parents[1] / "src" / "systems" / "bas" / "README.md"
    contract = contract_path.read_text(encoding="utf-8")
    assert "BAS layers follow the animated socket transform every frame" in contract
    assert "BAS skin meshes stay out of the body skin palette" in contract
    assert "WGPU/D3D and ModernGL/OpenGL" in contract

    wgpu_source = inspect.getsource(WgpuRenderer._mesh_model_matrix)
    assert "_gr_bas_attachment_layer" in wgpu_source
    assert "self._active_anim_pose is not None" in wgpu_source
    assert "node_world_matrix(matrix_source, anim_pose=self._active_anim_pose)" in wgpu_source
    assert "render-queue bind matrix" in wgpu_source

    modern_gl_source = inspect.getsource(gpu_renderer_impl)
    assert "_bas_attachment_local_transform_np" in modern_gl_source
    assert "not bool(getattr(node, \"_gr_bas_attachment_layer\", False))" in modern_gl_source
    assert "BAS attachment skins are socket followers" in modern_gl_source

    mesh_source = inspect.getsource(mesh_render_data._extract_skinning)
    assert "_gr_bas_attachment_layer" in mesh_source
    assert "BAS attachment layers follow sockets outside body skinning" in mesh_source


def test_integration_packages_are_headless_and_classified() -> None:
    """Integration/system packages stay headless until a deliberate split is planned."""
    plan_source = (ROOT / "docs/architecture/backend_reorganization_plan.md").read_text(encoding="utf-8")
    classified_packages = (
        "src.autorig",
        "src.formats",
        "src.infra",
        "src.io",
        "src.measurement",
        "src.mesh_tools",
        "src.resources",
        "src.unreal",
        "src.workbench",
        "src.systems",
    )
    for package_name in classified_packages:
        assert package_name in plan_source

    forbidden_markers = (
        "from PySide6",
        "import PySide6",
        "QtWidgets",
        "QtGui",
        "QtCore",
        "tkinter",
        "ImageTk",
        "from src.gui",
        "import src.gui",
        "src.gui.",
        "from src.core.qt_core",
        "import src.core.qt_core",
        "src.core.qt_core.",
    )
    offenders: list[str] = []
    package_dirs = (
        ROOT / "src/autorig",
        ROOT / "src/formats",
        ROOT / "src/infra",
        ROOT / "src/io",
        ROOT / "src/measurement",
        ROOT / "src/mesh_tools",
        ROOT / "src/resources",
        ROOT / "src/unreal",
        ROOT / "src/workbench",
        ROOT / "src/systems",
    )
    for package_dir in package_dirs:
        for source_path in package_dir.rglob("*.py"):
            source = source_path.read_text(encoding="utf-8")
            for marker in forbidden_markers:
                if marker in source:
                    offenders.append(f"{source_path.relative_to(ROOT)}: {marker}")
    assert offenders == []


def test_qt_viewport_shader_complexity_does_not_override_lighting_mode() -> None:
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    calls = []
    viewport = SimpleNamespace(
        _renderer=SimpleNamespace(lighting_mode="scene"),
        _gpu_renderer=SimpleNamespace(lighting_mode="scene"),
        _request_render=lambda: calls.append("render"),
    )

    QtViewportWidget.set_shader_complexity_mode(viewport, "lighting_cost")

    assert viewport._renderer.shader_complexity_mode == "lighting_cost"
    assert viewport._gpu_renderer.shader_complexity_mode == "lighting_cost"
    assert viewport._renderer.lighting_mode == "scene"
    assert viewport._gpu_renderer.lighting_mode == "scene"
    assert calls == ["render"]


def test_wgpu_canvas_draw_sizes_depth_from_current_surface_texture() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

    source = inspect.getsource(WgpuRenderer._draw_to_canvas)

    assert "current_texture = self.context.get_current_texture()" in source
    assert "current_texture.size" in source
    assert "self._ensure_depth_texture(int(width), int(height))" in source
    assert "view = current_texture.create_view()" in source


def test_wgpu_diffuse_textures_upload_capped_linear_mips(monkeypatch) -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.adapters.rendering.wgpu_core.resources import WgpuResourceCache

    captured = {"writes": [], "samplers": []}

    class _Texture:
        def create_view(self):
            return object()

    class _Queue:
        def write_texture(self, destination, data, layout, size):
            captured["writes"].append(
                {
                    "mip": destination["mip_level"],
                    "size": tuple(size),
                    "bytes_per_row": layout["bytes_per_row"],
                    "data_size": len(data),
                }
            )

    class _Device:
        def __init__(self):
            self.queue = _Queue()

        def create_texture(self, **kwargs):
            captured["texture"] = kwargs
            return _Texture()

        def create_sampler(self, **kwargs):
            captured["samplers"].append(kwargs)
            return object()

    fake_wgpu = SimpleNamespace(
        TextureUsage=SimpleNamespace(TEXTURE_BINDING=1, COPY_DST=2),
        TextureDimension=SimpleNamespace(d2="2d"),
        TextureFormat=SimpleNamespace(rgba8unorm="rgba8unorm", rgba8unorm_srgb="rgba8unorm-srgb"),
        AddressMode=SimpleNamespace(clamp_to_edge="clamp", repeat="repeat"),
        FilterMode=SimpleNamespace(linear="linear"),
        MipmapFilterMode=SimpleNamespace(nearest="nearest", linear="linear"),
    )
    monkeypatch.setitem(__import__("sys").modules, "wgpu", fake_wgpu)

    renderer = WgpuRenderer()
    renderer.device = _Device()
    cache = WgpuResourceCache(renderer)
    rgba = bytes([96, 80, 64, 255]) * (16 * 16)

    resource = cache._upload_rgba8_texture(
        "diffuse",
        rgba,
        16,
        16,
        source_revision=(1, 16, 16),
        label="diffuse",
    )

    assert resource.mip_level_count == 3
    assert captured["texture"]["mip_level_count"] == 3
    assert [write["size"] for write in captured["writes"]] == [(16, 16, 1), (8, 8, 1), (4, 4, 1)]
    assert captured["samplers"][0]["address_mode_u"] == "repeat"
    assert captured["samplers"][0]["mipmap_filter"] == "linear"
    assert captured["samplers"][0]["lod_max_clamp"] == 2.0


def test_wgpu_lightmaps_remain_single_level_linear_clamped(monkeypatch) -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.adapters.rendering.wgpu_core.resources import WgpuResourceCache

    captured = {"writes": [], "samplers": []}

    class _Texture:
        def create_view(self):
            return object()

    class _Queue:
        def write_texture(self, destination, data, layout, size):
            captured["writes"].append({"mip": destination["mip_level"], "size": tuple(size)})

    class _Device:
        def __init__(self):
            self.queue = _Queue()

        def create_texture(self, **kwargs):
            captured["texture"] = kwargs
            return _Texture()

        def create_sampler(self, **kwargs):
            captured["samplers"].append(kwargs)
            return object()

    fake_wgpu = SimpleNamespace(
        TextureUsage=SimpleNamespace(TEXTURE_BINDING=1, COPY_DST=2),
        TextureDimension=SimpleNamespace(d2="2d"),
        TextureFormat=SimpleNamespace(rgba8unorm="rgba8unorm", rgba8unorm_srgb="rgba8unorm-srgb"),
        AddressMode=SimpleNamespace(clamp_to_edge="clamp", repeat="repeat"),
        FilterMode=SimpleNamespace(linear="linear"),
        MipmapFilterMode=SimpleNamespace(nearest="nearest", linear="linear"),
    )
    monkeypatch.setitem(__import__("sys").modules, "wgpu", fake_wgpu)

    renderer = WgpuRenderer()
    renderer.device = _Device()
    cache = WgpuResourceCache(renderer)
    rgba = bytes([255, 255, 255, 255]) * (16 * 16)

    resource = cache._upload_rgba8_texture(
        "lightmap",
        rgba,
        16,
        16,
        source_revision=(1, 16, 16),
        label="lightmap",
        lightmap=True,
    )

    assert resource.mip_level_count == 1
    assert captured["texture"]["mip_level_count"] == 1
    assert [write["size"] for write in captured["writes"]] == [(16, 16, 1)]
    assert captured["samplers"][0]["address_mode_u"] == "clamp"
    assert captured["samplers"][0]["mipmap_filter"] == "nearest"
    assert captured["samplers"][0]["lod_max_clamp"] == 0.0


def test_wgpu_render_normals_smooth_compatible_uv_seam_duplicates() -> None:
    import numpy as np

    from src.core.rendering.mesh_render_data import smooth_render_normals

    positions = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        dtype=np.float32,
    )
    normals = np.asarray(
        [
            (0.0, 0.0, 1.0),
            (0.0, 0.24, 0.97),
            (0.0, 0.0, 1.0),
            (0.0, 0.24, 0.97),
        ],
        dtype=np.float32,
    )

    smoothed = smooth_render_normals(positions, normals, np.asarray([0, 2, 3, 1, 3, 2], dtype=np.uint32))

    assert smoothed[0].tolist() == pytest.approx(smoothed[1].tolist(), abs=1e-5)
    assert np.linalg.norm(smoothed[0]) == pytest.approx(1.0)


def test_wgpu_render_normals_preserve_hard_edge_duplicate_vertices() -> None:
    from src.core.rendering.mesh_render_data import smooth_render_normals

    positions = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    ]
    normals = [
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 0.0),
    ]

    smoothed = smooth_render_normals(positions, normals, [0, 2, 3, 1, 3, 2])

    assert smoothed[0].tolist() == pytest.approx([0.0, 0.0, 1.0])
    assert smoothed[1].tolist() == pytest.approx([1.0, 0.0, 0.0])


def test_wgpu_render_data_generates_area_weighted_normals_when_missing() -> None:
    import numpy as np

    from src.core.rendering.mesh_render_data import iter_mesh_render_data

    node = SimpleNamespace(
        name="missing_normals",
        vertices=[(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[],
        uvs=[],
        uvs_lm=[],
        faces=[(0, 1, 2)],
        face_uvs=[],
        is_skin=False,
        vertex_space=1,
        render=True,
        texture="",
        alpha=1.0,
    )
    model = SimpleNamespace(all_nodes=lambda: [node])

    rows = list(iter_mesh_render_data(model, textures={}))

    assert len(rows) == 1
    np.testing.assert_allclose(rows[0].normals, np.asarray([(0.0, 0.0, 1.0)] * 3, dtype=np.float32), atol=1e-6)


def test_wgpu_skinned_mesh_revision_changes_between_bind_and_lbs_modes(monkeypatch) -> None:
    import numpy as np

    from src.core.rendering import mesh_render_data

    node = SimpleNamespace(
        name="torso",
        vertices=[(0.0, 0.0, 0.0)],
        faces=[(0, 0, 0)],
        is_skin=True,
        vertex_space=0,
        render=True,
        texture="",
        alpha=1.0,
        skin_data=[{"weights": [(0, 1.0)]}],
        bone_map=["pelvis"],
        _gr_revision=7,
    )
    model = SimpleNamespace(all_nodes=lambda: [node])
    positions = np.asarray([(0.0, 0.0, 0.0)], dtype=np.float32)
    normals = np.asarray([(0.0, 0.0, 1.0)], dtype=np.float32)
    uvs = np.asarray([(0.5, 0.5)], dtype=np.float32)
    indices = np.asarray([0, 0, 0], dtype=np.uint32)
    bone_indices = np.asarray([[0, 0, 0, 0]], dtype=np.uint16)
    bone_weights = np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)

    monkeypatch.setattr(
        mesh_render_data,
        "_extract_node_arrays",
        lambda _node, *, anim_pose=None, vbo_builder=None: (
            positions,
            normals,
            uvs,
            uvs,
            indices,
            bone_indices,
            bone_weights,
            np.eye(4, dtype=np.float32),
        ),
    )

    bind_row = list(mesh_render_data.iter_mesh_render_data(model, textures={}, anim_pose=None))[0]
    animated_row = list(
        mesh_render_data.iter_mesh_render_data(
            model,
            textures={},
            anim_pose=SimpleNamespace(nodes={}, time=0.25),
            allow_cpu_skinning=False,
        )
    )[0]

    assert bind_row.is_skinned is True
    assert animated_row.is_skinned is True
    assert bind_row.source_revision[:-1] == animated_row.source_revision[:-1]
    assert bind_row.source_revision[-1] == 0
    assert animated_row.source_revision[-1] == 1


def test_wgpu_animation_queue_key_uses_mode_not_pose_time() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.rendering.viewport_display import ViewportDisplayMode, ViewportDisplayOptions

    renderer = WgpuRenderer()
    renderer._active_scene = object()
    renderer._active_anim_base_pose = object()
    renderer._active_textures = {}
    options = ViewportDisplayOptions(display_mode=ViewportDisplayMode.TEXTURED)

    renderer._active_anim_pose = SimpleNamespace(time=0.1)
    first = renderer._render_queue_revision_key(
        options,
        force_untextured=False,
        force_no_lightmaps=True,
    )
    renderer._active_anim_pose = SimpleNamespace(time=0.6)
    second = renderer._render_queue_revision_key(
        options,
        force_untextured=False,
        force_no_lightmaps=True,
    )
    renderer._active_anim_pose = None
    stopped = renderer._render_queue_revision_key(
        options,
        force_untextured=False,
        force_no_lightmaps=True,
    )

    assert first == second
    assert first != stopped


def test_animation_skinning_profiles_resolve_content_browser_families() -> None:
    from src.core.animation.animation_engine import AnimationEngine
    from src.core.animation.skinning_profiles import resolve_skinning_profile
    from src.core.geometry.model_data import KotorModel

    local_character = resolve_skinning_profile("N_DarthMalak", "NULL", [], inherited_animation=False)
    skinned_droid = resolve_skinning_profile("P_HK47", "NULL", ["TorsoHoses", "L_hose"], inherited_animation=False, has_skin=True)
    rigid_droid = resolve_skinning_profile("P_T3M3", "NULL", [], inherited_animation=False, has_skin=False)
    bith = resolve_skinning_profile("N_Bith", "S_Male02", [], inherited_animation=True)
    carth = resolve_skinning_profile("P_CarthBB", "S_Female02", [], inherited_animation=True)
    head = resolve_skinning_profile("PMHC01", "S_Female02", ["talkdummy"], inherited_animation=True, taxonomy="head")
    creature = resolve_skinning_profile("C_Rancor", "NULL", ["cameramaster"], inherited_animation=False)

    assert local_character.module_name.endswith("generated_character_skinning")
    assert local_character.resref == "n_darthmalak"
    assert skinned_droid.module_name.endswith("generated_character_skinning")
    assert skinned_droid.resref == "p_hk47"
    assert rigid_droid.module_name.endswith("generated_character_skinning")
    assert rigid_droid.resref == "p_t3m3"
    assert bith.module_name.endswith("generated_character_skinning")
    assert bith.species == "bith"
    assert carth.module_name.endswith("generated_character_skinning")
    assert head.module_name.endswith("generated_character_skinning")
    assert creature.module_name.endswith("generated_character_skinning")

    model = KotorModel(name="N_DarthMalak", supermodel="NULL")
    engine = AnimationEngine(model)
    assert engine.skinning_profile.module_name.endswith("generated_character_skinning")
    assert engine.skinning_profile.resref == "n_darthmalak"
    assert engine.skinning_profile.skin_node_count > 0


def test_animation_skinning_profiles_include_generated_character_registry() -> None:
    import sys

    import src.core.animation.skinning_profiles.generated_character_skinning as compat_generated_module
    import src.core.animation.skinning_profiles.types.generated_character_skinning as typed_generated_module

    from src.core.animation.skinning_profiles import resolve_skinning_profile
    from src.core.animation.skinning_profiles.generated_character_skinning import (
        CHARACTER_SKINNING_PROFILE_ROWS as COMPAT_PROFILE_ROWS,
    )
    from src.core.animation.skinning_profiles.types.generated_character_skinning import (
        CHARACTER_SKINNING_PROFILE_BY_KEY,
        CHARACTER_SKINNING_PROFILE_ROWS,
    )

    assert compat_generated_module is typed_generated_module
    assert sys.modules["src.core.animation.skinning_profiles.generated_character_skinning"] is typed_generated_module
    assert COMPAT_PROFILE_ROWS is CHARACTER_SKINNING_PROFILE_ROWS
    assert len(CHARACTER_SKINNING_PROFILE_ROWS) >= 600
    assert not any(str(row["resref"]).startswith(("gi_", "or_")) for row in CHARACTER_SKINNING_PROFILE_ROWS)
    assert CHARACTER_SKINNING_PROFILE_BY_KEY["k1:n_darthmalak"]["skin_node_count"] > 0

    compat_source = (ROOT / "src/core/animation/skinning_profiles/generated_character_skinning.py").read_text(
        encoding="utf-8"
    )
    assert 'import_module(f"{__package__}.types.generated_character_skinning")' in compat_source
    assert "sys.modules[__name__] = _module" in compat_source
    assert "import *" not in compat_source

    malak = resolve_skinning_profile("N_DarthMalak", "NULL", [], inherited_animation=False)
    hk47 = resolve_skinning_profile("P_HK47", "NULL", ["TorsoHoses"], inherited_animation=False)
    t3 = resolve_skinning_profile("P_T3M3", "NULL", [], inherited_animation=False)

    assert malak.key == "k1:n_darthmalak"
    assert hk47.key == "k1:p_hk47"
    assert hk47.skin_node_count > 0
    assert t3.key == "k1:p_t3m3"
    assert t3.rigid_animated is True
    assert t3.requires_skin is False


def test_animation_skinning_profiles_load_typed_profile_directories() -> None:
    from src.core.animation.skinning_profiles import (
        SKINNING_PROFILES,
        SKINNING_SPECIES_PROFILES,
        resolve_skinning_profile,
    )

    module_names = {profile.module_name for profile in SKINNING_PROFILES}

    assert "src.core.animation.skinning_profiles.types.characters.human" in module_names
    assert "src.core.animation.skinning_profiles.types.droids.t3m3" in module_names
    assert "src.core.animation.skinning_profiles.types.droids.t3m4" in module_names
    assert "src.core.animation.skinning_profiles.types.specialcase.malak" in module_names
    assert "src.core.animation.skinning_profiles.types.generated_character_skinning" not in module_names
    assert ".types.characters." in SKINNING_SPECIES_PROFILES["human"].module_name
    assert ".types.droids." in SKINNING_SPECIES_PROFILES["utility_droid"].module_name
    assert ".types.droids." in SKINNING_SPECIES_PROFILES["droid"].module_name
    assert ".types.supermodels." in SKINNING_SPECIES_PROFILES["supermodel"].module_name

    t3m4 = resolve_skinning_profile("P_T3M4", "NULL", [], inherited_animation=False, has_skin=False)
    malak = resolve_skinning_profile("N_DarthMalak", "NULL", [], inherited_animation=False)

    assert t3m4.module_name == "src.core.animation.skinning_profiles.types.generated_character_skinning"
    assert t3m4.rigid_animated is True
    assert malak.module_name == "src.core.animation.skinning_profiles.types.generated_character_skinning"


def test_animation_skinning_profiles_mark_party_character_weight_policies() -> None:
    from src.core.animation.skinning_profiles import resolve_skinning_profile

    party_cases = {
        ("K1", "P_CarthBB", "S_Female02", True): ("human", "authored_normalized_top4"),
        ("K1", "P_Zaalbar", "N_WookieM", True): ("wookie", "authored_normalized_top4"),
        ("K1", "P_T3M3", "NULL", False): ("utility_droid", "rigid_node_animation"),
        ("K2", "P_G0T0", "NULL", False): ("utility_droid", "rigid_node_animation"),
        ("K2", "P_HK47", "NULL", True): ("droid", "authored_normalized_top4"),
    }

    for (game, resref, supermodel, has_skin), (species, weight_policy) in party_cases.items():
        profile = resolve_skinning_profile(
            resref,
            supermodel,
            [],
            inherited_animation=has_skin,
            has_skin=has_skin,
            metadata={"game": game},
        )

        assert profile.content_group == "party_character"
        assert profile.species == species
        assert profile.weight_policy == weight_policy
        assert profile.max_influences == 4


def test_qt_viewport_exposes_animation_playback_governor_and_live_overlay_skip() -> None:
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    viewport_source = _qt_viewport_widget_source()
    init_source = inspect.getsource(QtGhostRiggerMainWindow.__init__)
    play_source = inspect.getsource(QtGhostRiggerMainWindow._handle_animation_action)
    tick_source = inspect.getsource(QtGhostRiggerMainWindow._tick_animation)

    assert "def set_animation_playback_active" in viewport_source
    assert "self._frame_governor.set_animation_playing(bool(active), reason)" in viewport_source
    assert "def _can_skip_live_overlay_rebuild" in viewport_source
    assert 'dirty_flags.get("scene", False)' in viewport_source
    assert "self._skip_overlay_pixmap_update = True" in viewport_source
    assert "governor is not None and governor.animation_playing" in viewport_source
    assert "and not governor.animation_playing" in viewport_source
    assert "self.canvas.is_live_surface()" in viewport_source
    assert 'getattr(self._renderer, "_anim_pose", None) is not None' in viewport_source
    assert "self._render_timer.setTimerType(QtCore.Qt.PreciseTimer)" in viewport_source
    assert "self._animation_timer.setTimerType(QtCore.Qt.PreciseTimer)" in init_source
    assert "self._animation_timer.setInterval(30)" in init_source
    assert "self._animation_status_last_update = 0.0" in init_source
    assert 'self.viewport.set_animation_playback_active(True, "animation playback")' in play_source
    assert "self.viewport.set_animation_playback_active(False)" in play_source
    assert "should_update_status" in tick_source
    assert ">= 0.20" in tick_source
    assert "self.viewport.set_animation_playback_active(False)" in tick_source


def test_main_model_load_uses_inherited_animation_panel_loader() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    loaded_source = inspect.getsource(QtGhostRiggerMainWindow._on_model_loaded)
    retarget_source = inspect.getsource(QtGhostRiggerMainWindow._activate_retarget_target_model)
    library_source = inspect.getsource(QtGhostRiggerMainWindow._activate_animation_entry_model)

    assert "self._load_animation_panel_model(model)" in loaded_source
    assert "self.animations_panel.load_model(model)" not in loaded_source
    assert "self._load_animation_panel_model(model)" in retarget_source
    assert "self._load_animation_panel_model(model)" in library_source
    loader_source = inspect.getsource(QtGhostRiggerMainWindow._load_animation_panel_model)
    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    assert '"Animation Browser"' in layout_source
    assert "animationSourceChanged.connect(self._handle_animation_source_changed)" in layout_source
    assert "QtBodyAttachmentPanel(self)" in layout_source
    assert '"Body Attachment System"' in layout_source
    assert "body_attachment_panel_action" in actions_source
    assert 'self.body_attachment_panel_action = QtGui.QAction(self._icon("body_attachment"), "Body Attachment System", self)' in actions_source
    assert "modules_menu.addAction(self.body_attachment_panel_action)" in menu_source
    assert "_animation_source_model(model)" in loader_source
    assert "_animation_inheritance_supermodel(model)" in loader_source
    assert "_animation_resolution_context(model, inheritance_game, inheritance_supermodel)" in loader_source
    assert Path("src/gui/icons/body_attachment.svg").exists()


def test_wgpu_external_lighting_snapshot_receives_renderer_helper_palette(monkeypatch) -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.lighting.render_data import SceneLightingRenderData

    monkeypatch.setitem(__import__("sys").modules, "wgpu", SimpleNamespace())
    renderer = WgpuRenderer()
    renderer.device = object()
    renderer.queue = object()
    renderer.light_buffer = object()
    renderer.lighting_uniform_buffer = object()
    renderer._active_lighting_render_data = SceneLightingRenderData()
    renderer.light_helper_palette = {"light": (1.0, 0.82, 0.10), "point": (1.0, 0.82, 0.10)}

    assert renderer._ensure_light_resource() is None
    assert renderer._active_lighting_render_data.helper_palette["light"] == (1.0, 0.82, 0.10)


def test_wgpu_material_uniforms_respect_diffuse_toggle_and_display_options() -> None:
    import numpy as np

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.rendering.viewport_display import ViewportDisplayMode, ViewportDisplayOptions

    renderer = WgpuRenderer()
    material = SimpleNamespace(
        diffuse_texture_resource=object(),
        has_lightmap=False,
        alpha_mode="OPAQUE",
        alpha_cutoff=0.5,
    )
    options = ViewportDisplayOptions(display_mode=ViewportDisplayMode.TEXTURED, show_textures=True)

    renderer.show_diffuse_map = False
    data = renderer._mesh_uniform_bytes(np.eye(4, dtype=np.float32), (1.0, 1.0, 1.0, 1.0), material, options)
    assert len(data) == 192
    flags = np.frombuffer(data[144:160], dtype=np.float32)
    assert flags[0] == 0.0

    renderer.show_diffuse_map = True
    data = renderer._mesh_uniform_bytes(np.eye(4, dtype=np.float32), (1.0, 1.0, 1.0, 1.0), material, options)
    flags = np.frombuffer(data[144:160], dtype=np.float32)
    assert flags[0] == 1.0

    shaded = ViewportDisplayOptions(display_mode=ViewportDisplayMode.SHADED)
    data = renderer._mesh_uniform_bytes(np.eye(4, dtype=np.float32), (1.0, 1.0, 1.0, 1.0), material, shaded)
    params = np.frombuffer(data[160:176], dtype=np.float32)
    sprite = np.frombuffer(data[176:192], dtype=np.float32)
    assert params[1] == 2.0
    assert sprite[2] == 1.0

    flat = ViewportDisplayOptions(display_mode=ViewportDisplayMode.SOLID, force_flat_colour=True)
    data = renderer._mesh_uniform_bytes(np.eye(4, dtype=np.float32), (1.0, 1.0, 1.0, 1.0), material, flat)
    sprite = np.frombuffer(data[176:192], dtype=np.float32)
    assert sprite[2] == 0.0

    model_matrix = np.eye(4, dtype=np.float32)
    model_matrix[0, 3] = 7.0
    data = renderer._mesh_uniform_bytes(
        np.eye(4, dtype=np.float32),
        (1.0, 1.0, 1.0, 1.0),
        material,
        options,
        model_matrix=model_matrix,
    )
    decoded_model = np.frombuffer(data[64:128], dtype=np.float32).reshape(4, 4).T
    assert decoded_model[0, 3] == 7.0

    sprite_material = SimpleNamespace(
        diffuse_texture_resource=object(),
        has_lightmap=False,
        alpha_mode="BLEND",
        alpha_cutoff=0.25,
        sprite_alpha_source=1,
        sprite_glow=1.6,
    )
    data = renderer._mesh_uniform_bytes(np.eye(4, dtype=np.float32), (1.0, 1.0, 1.0, 1.0), sprite_material, options)
    sprite = np.frombuffer(data[176:192], dtype=np.float32)
    assert sprite[0] == 1.0
    assert sprite[1] == pytest.approx(1.6)
    assert sprite[2] == 2.0


def test_wgpu_mesh_uniform_marks_selected_mesh_for_shader_fill() -> None:
    import numpy as np

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.rendering.viewport_display import ViewportDisplayMode, ViewportDisplayOptions

    renderer = WgpuRenderer()
    material = SimpleNamespace(
        diffuse_texture_resource=object(),
        has_lightmap=False,
        alpha_mode="OPAQUE",
        alpha_cutoff=0.5,
    )
    options = ViewportDisplayOptions(display_mode=ViewportDisplayMode.TEXTURED, show_textures=True)

    unselected = renderer._mesh_uniform_bytes(
        np.eye(4, dtype=np.float32),
        (1.0, 1.0, 1.0, 1.0),
        material,
        options,
        selected=False,
    )
    selected = renderer._mesh_uniform_bytes(
        np.eye(4, dtype=np.float32),
        (1.0, 1.0, 1.0, 1.0),
        material,
        options,
        selected=True,
    )

    assert np.frombuffer(unselected[160:176], dtype=np.float32)[3] == 0.0
    assert np.frombuffer(selected[160:176], dtype=np.float32)[3] == 1.0


def test_wgpu_mesh_shaders_apply_moderngl_selected_yellow_fill() -> None:
    from src.core.rendering import wgpu_shaders as wgpu_renderer

    expected = "mix(out_color.rgb, vec3<f32>(1.0, 0.78, 0.12), 0.45)"

    assert expected in wgpu_renderer._load_mesh_shader()
    assert expected in wgpu_renderer._load_skinned_mesh_shader()
    assert "sprite_keyed_alpha" in wgpu_renderer._load_mesh_shader()
    assert "sprite_emission_tint" in wgpu_renderer._load_mesh_shader()
    assert "!sprite_emissive && lighting_state.flags.y" in wgpu_renderer._load_mesh_shader()
    assert "out_color.rgb * soft_shade, out_color.a" in wgpu_renderer._load_mesh_shader()
    assert "locals.model * vec4<f32>(input.position, 1.0)" in wgpu_renderer._load_mesh_shader()
    assert "locals.model * skin_position(input)" in wgpu_renderer._load_skinned_mesh_shader()


def test_wgpu_routes_saber_sprites_through_additive_blend_pass() -> None:
    import inspect
    import numpy as np

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.adapters.rendering.wgpu_core.resources import WgpuResourceCache
    from src.core.rendering.viewport_display import ViewportDisplayMode

    create_source = inspect.getsource(WgpuRenderer._create_textured_pipeline)
    mesh_source = inspect.getsource(WgpuRenderer._draw_meshes)
    skin_source = inspect.getsource(WgpuRenderer._skinned_pipeline_for_pass)

    assert "src_factor\": wgpu.BlendFactor.one if additive else wgpu.BlendFactor.src_alpha" in create_source
    assert "dst_factor\": wgpu.BlendFactor.one if additive else wgpu.BlendFactor.one_minus_src_alpha" in create_source
    assert "blend_mode = str(getattr(material_data, \"blend_mode\", \"ALPHA\")" in mesh_source
    assert 'item[0] == "BLEND" and item[1] == "ADDITIVE"' in mesh_source
    assert 'draw_pass("additive", additive, self.pipeline_mesh_additive' in mesh_source
    assert 'pass_name).lower() == "additive"' in skin_source
    assert "self._should_draw_selected_mesh_edges(item, mode, edge_overlay)" in mesh_source
    assert "_uses_sprite_wire_hull" in inspect.getsource(WgpuResourceCache.upload_mesh)

    renderer = WgpuRenderer.__new__(WgpuRenderer)
    glow_card = SimpleNamespace(material=SimpleNamespace(blend_mode="ADDITIVE", sprite_alpha_source=1))
    lighten_glow_card = SimpleNamespace(material=SimpleNamespace(blend_mode="LIGHTEN", sprite_alpha_source=1))
    opaque_mesh = SimpleNamespace(material=SimpleNamespace(blend_mode="ALPHA", sprite_alpha_source=0))
    assert renderer._should_draw_selected_mesh_edges(glow_card, ViewportDisplayMode.TEXTURED, False) is False
    assert renderer._should_draw_selected_mesh_edges(lighten_glow_card, ViewportDisplayMode.TEXTURED, False) is False
    assert renderer._should_draw_selected_mesh_edges(glow_card, ViewportDisplayMode.TEXTURED, True) is True
    assert renderer._should_draw_selected_mesh_edges(glow_card, ViewportDisplayMode.WIREFRAME, False) is True
    assert renderer._should_draw_selected_mesh_edges(lighten_glow_card, ViewportDisplayMode.WIREFRAME, False) is True
    assert renderer._should_draw_selected_mesh_edges(opaque_mesh, ViewportDisplayMode.TEXTURED, False) is True

    cache = WgpuResourceCache.__new__(WgpuResourceCache)
    positions = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        dtype=np.float32,
    )
    hull = cache._build_edge_indices(None, len(positions), positions=positions, geometric=True)
    assert hull is not None
    assert len(hull) == 8


def test_wgpu_mesh_draw_uses_per_draw_uniforms_for_selected_fill() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

    draw_source = inspect.getsource(WgpuRenderer._draw_mesh_item)
    render_source = inspect.getsource(WgpuRenderer.render)
    uniform_source = inspect.getsource(WgpuRenderer._set_mesh_uniform)

    assert "self._set_mesh_uniform(render_pass, uniform)" in draw_source
    assert "self._begin_uniform_frame()" in render_source
    assert "render_pass.set_bind_group(0, self.mesh_bind_group, [offset])" in uniform_source


def test_wgpu_mesh_hover_edges_are_translucent_and_isolated_from_selection_edges() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

    renderer = WgpuRenderer()
    draw_source = inspect.getsource(WgpuRenderer._draw_meshes)
    edge_source = inspect.getsource(WgpuRenderer._draw_edge_items)
    pipeline_source = inspect.getsource(WgpuRenderer._create_line_pipeline)

    assert renderer.hovered_edge_alpha < 1.0
    assert renderer.show_mesh_hover_edges is False
    assert 'getattr(self, "show_mesh_hover_edges", False)' in draw_source
    assert 'getattr(self, "hovered_edge_alpha", 0.45)' in draw_source
    assert "self._set_line_uniform(render_pass, self._mesh_mvp_matrix(mvp, mesh_data), color)" in edge_source
    assert "wgpu.BlendFactor.src_alpha" in pipeline_source


def test_wgpu_skinned_edge_overlay_uses_skin_palette_during_animation() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.core.rendering import wgpu_shaders as wgpu_renderer

    create_source = inspect.getsource(WgpuRenderer._create_skinned_line_pipeline)
    edge_source = inspect.getsource(WgpuRenderer._draw_edge_items)

    assert "pipeline_lines_skinned" in create_source
    assert "_SKINNED_LINE_WGSL" in create_source
    assert "self.skin_bind_group_layout" in create_source
    assert "get_or_update_skin_palette" in edge_source
    assert "render_pass.set_bind_group(1, skin_resource.bind_group)" in edge_source
    assert "pipeline = self.pipeline_lines_skinned" in edge_source
    assert "@group(1) @binding(0)" in wgpu_renderer._SKINNED_LINE_WGSL
    assert "locals.mvp * skin_position(input)" in wgpu_renderer._SKINNED_LINE_WGSL


def test_wgpu_render_consumes_mesh_hover_payload() -> None:
    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(WgpuRenderer.render)
    viewport_source = inspect.getsource(QtViewportWidget._render_gpu_frame)

    assert 'self.hovered_node = kwargs.get("hovered_node")' in source
    assert 'self.show_mesh_hover = bool(kwargs.get("show_mesh_hover"' in source
    assert 'hovered_node=getattr(self, "_hovered_mesh_node", None)' in viewport_source
    assert 'show_mesh_hover=bool(getattr(self, "mesh_hover_enabled", True))' in viewport_source


def test_qt_lighting_panel_select_light_syncs_from_viewport_without_emitting() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.panels.qt_lighting_panel import QtLightingPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    first = SimpleNamespace(name="AuroraLight001", is_light=True, light_kind="point", light_radius=1.5)
    second = SimpleNamespace(name="AuroraLight223", is_light=True, light_kind="point", light_radius=11.75)
    panel = QtLightingPanel()
    emitted = []
    panel.lightSelected.connect(emitted.append)
    panel.set_model(SimpleNamespace(all_nodes=lambda: [first, second]))
    emitted.clear()

    assert panel.has_light(second) is True
    assert panel.select_light(second) is True

    assert emitted == []
    assert panel._selected is second
    assert panel.tree.currentItem().data(0, QtCore.Qt.UserRole) is second
    assert panel.radius_spin.value() == 11.75

    assert panel.has_light(SimpleNamespace(name="NotALight", is_light=False)) is False
    assert panel.select_light(None) is False

    assert emitted == []
    assert panel._selected is None
    assert panel.tree.selectedItems() == []


def test_qt_lighting_panel_clears_when_viewport_selects_non_light() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_lighting_panel import QtLightingPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    light = SimpleNamespace(name="AuroraLight223", is_light=True, light_kind="point", light_radius=11.75)
    mesh = SimpleNamespace(name="Object3258", vertices=[(0.0, 0.0, 0.0)], faces=[(0, 0, 0)])
    panel = QtLightingPanel()
    emitted = []
    panel.lightSelected.connect(emitted.append)
    panel.set_model(SimpleNamespace(all_nodes=lambda: [light, mesh]))
    panel.select_light(light)
    emitted.clear()

    panel.select_light(mesh)

    assert emitted == []
    assert panel._selected is None
    assert panel.tree.selectedItems() == []


def test_qt_skeleton_panel_can_sync_root_without_emitting_selection() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_skeleton_panel import QtSkeletonPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    child = SimpleNamespace(name="head", type_label="dummy", is_mesh=False, children=[])
    root = SimpleNamespace(name="N_Bith", type_label="dummy", is_mesh=False, children=[child])
    model = SimpleNamespace(
        root_node=root,
        node_count=lambda: 2,
        mesh_nodes=lambda: [],
    )
    panel = QtSkeletonPanel()
    emitted = []
    panel.nodeSelected.connect(emitted.append)
    panel.load_model(model)

    panel.select_node(root, emit=False)

    assert emitted == []
    assert panel.tree.currentItem().text(0).endswith("N_Bith")
    assert panel.get_selected_nodes() == [root]


def test_qt_skeleton_panel_uses_detailed_browser_columns_and_icons() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtGui, QtWidgets

    from src.gui.qt_lib.panels.qt_skeleton_panel import QtSkeletonPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    hook = SimpleNamespace(name="rhandhook", type_label="dummy", is_mesh=False, children=[], attachments=["w_lghtsbr"])
    mesh = SimpleNamespace(
        name="torso_g",
        type_label="trimesh",
        is_mesh=True,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
        faces=[(0, 1, 1)],
        children=[],
    )
    root = SimpleNamespace(name="P_CarthBB", type_label="dummy", is_mesh=False, children=[hook, mesh])
    hook.parent = root
    mesh.parent = root
    model = SimpleNamespace(root_node=root, node_count=lambda: 3, mesh_nodes=lambda: [mesh])

    panel = QtSkeletonPanel()
    panel.load_model(model)

    assert [panel.tree.headerItem().text(index) for index in range(panel.tree.columnCount())] == [
        "Node",
        "Role",
        "Mesh",
        "Verts",
        "Faces",
        "Children",
        "Attach",
    ]
    assert panel.tree.header().sectionResizeMode(0) == QtWidgets.QHeaderView.Stretch
    assert panel.tree.header().sectionResizeMode(1) == QtWidgets.QHeaderView.ResizeToContents

    root_item = panel.tree.topLevelItem(0)
    hook_item = root_item.child(0)
    mesh_item = root_item.child(1)
    assert not root_item.icon(0).isNull()
    assert hook_item.text(1) == "Hook"
    assert hook_item.text(6) == "1"
    assert mesh_item.text(1) == "Mesh"
    assert mesh_item.text(2) == "trimesh"
    assert mesh_item.text(3) == "2"
    assert mesh_item.text(4) == "1"
    option = QtWidgets.QStyleOptionViewItem()
    option.initFrom(panel.tree)
    option.fontMetrics = QtGui.QFontMetrics(panel.tree.font())
    assert panel.tree.itemDelegate().sizeHint(option, panel.tree.model().index(0, 0)).height() >= 24

    panel._filter("torso")
    assert root_item.isHidden() is False
    assert hook_item.isHidden() is True
    assert mesh_item.isHidden() is False


def test_qt_skeleton_panel_preserves_module_node_hierarchy() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_skeleton_panel import QtSkeletonPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    root = SimpleNamespace(name="M01aa_01a", type_label="dummy", is_mesh=False, children=[])
    door = SimpleNamespace(name="Door_16", type_label="dummy", is_mesh=False, children=[])
    hook = SimpleNamespace(name="cameraHook", type_label="dummy", is_mesh=False, children=[])
    light = SimpleNamespace(name="AuroraLight273", type_label="light", is_light=True, is_mesh=False, children=[])
    meshes = [
        SimpleNamespace(name=f"Object{index}", type_label="trimesh", is_mesh=True, vertices=[(0, 0, 0)], faces=[(0, 0, 0)], children=[])
        for index in range(12)
    ]
    for child in [door, hook, light, *meshes]:
        child.parent = root
    root.children = [door, hook, light, *meshes]
    model = SimpleNamespace(root_node=root, node_count=lambda: len(root.children) + 1, mesh_nodes=lambda: meshes)

    panel = QtSkeletonPanel()
    panel.load_model(model)

    root_item = panel.tree.topLevelItem(0)
    assert root_item.text(0) == "M01aa_01a"
    assert root_item.childCount() == len(root.children)
    assert [root_item.child(index).text(0) for index in range(4)] == [
        "Door_16",
        "cameraHook",
        "AuroraLight273",
        "Object0",
    ]
    assert root_item.child(0).text(1) == "Bone"
    assert root_item.child(1).text(1) == "Hook"
    assert root_item.child(2).text(1) == "Light"
    assert root_item.child(3).text(1) == "Mesh"
    assert all(root_item.child(index).text(0) not in {"Bones", "Lights", "Helpers", "Meshes"} for index in range(root_item.childCount()))

    selected = []
    panel.nodeSelected.connect(selected.append)
    panel.tree.setCurrentItem(root_item.child(3))
    assert selected[-1] is meshes[0]


def test_qt_scene_outliner_uses_detailed_browser_columns_icons_and_filter() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtGui, QtWidgets

    from src.gui.qt_lib.panels.qt_scene_outliner_panel import QtSceneOutlinerPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ref = SimpleNamespace(resref="P_Zaalbar", original_name="", source_module="", source_archive="", source_path="", resource_type="model")
    root_node = SimpleNamespace(name="P_Zaalbar", type_label="dummy", is_mesh=False, children=[])
    head_hook = SimpleNamespace(name="headhook", type_label="dummy", is_mesh=False, children=[], index=4)
    saber_hook = SimpleNamespace(name="rhand", type_label="dummy", is_mesh=False, children=[], index=12)
    aurora_light = SimpleNamespace(
        name="AuroraLight331",
        type_label="light",
        is_light=True,
        is_mesh=False,
        children=[],
        index=44,
        light_kind="aurora_point",
        light_radius=12.0,
    )
    torso_mesh = SimpleNamespace(name="torso", type_label="skin", is_mesh=True, is_skin=True, children=[], index=2)
    head_hook.parent = root_node
    saber_hook.parent = root_node
    aurora_light.parent = root_node
    torso_mesh.parent = root_node
    root_node.children = [torso_mesh, head_hook, saber_hook, aurora_light]
    runtime_model = SimpleNamespace(root_node=root_node, all_nodes=lambda: [root_node, torso_mesh, head_hook, saber_hook, aurora_light])
    model = SimpleNamespace(
        id="model-001",
        name="P_Zaalbar",
        object_type="model",
        visible=True,
        locked=False,
        selected=True,
        source_ref=ref,
        metadata={"node_count": 87, "_runtime_model": runtime_model},
        group_id="party",
    )
    hidden_light = SimpleNamespace(
        id="light-001",
        name="KeyLight",
        object_type="light",
        visible=False,
        locked=True,
        selected=False,
        source_ref=SimpleNamespace(resref="", original_name="", source_module="", source_archive="", source_path="", resource_type="light"),
        metadata={},
        group_id="",
    )
    scene = SimpleNamespace(
        id="scene-001",
        name="Untitled Scene",
        display_name="Untitled Scene",
        game="K1",
        dirty=False,
        objects=[model, hidden_light],
    )

    panel = QtSceneOutlinerPanel()
    emitted = []
    helper_emitted = []
    light_emitted = []
    panel.objectSelected.connect(emitted.append)
    panel.helperNodeSelected.connect(helper_emitted.append)
    panel.lightNodeSelected.connect(light_emitted.append)
    panel.set_scene(scene)

    assert [panel.tree.headerItem().text(index) for index in range(panel.tree.columnCount())] == [
        "Object",
        "Kind",
        "State",
        "Children",
        "Source",
        "ID",
    ]
    assert panel.tree.header().sectionResizeMode(0) == QtWidgets.QHeaderView.Stretch
    assert panel.tree.header().sectionResizeMode(1) == QtWidgets.QHeaderView.ResizeToContents
    assert panel.count_label.text() == "1 models  2 lights  0 cameras  2 helpers"

    root_item = panel.tree.topLevelItem(0)
    models_bucket = root_item.child(0)
    model_item = models_bucket.child(0)
    lights_bucket = root_item.child(1)
    light_item = lights_bucket.child(0)
    runtime_light_item = lights_bucket.child(1)
    helpers_bucket = root_item.child(3)
    assert not root_item.icon(0).isNull()
    assert model_item.text(1) == "Model"
    assert model_item.text(2) == "visible, selected"
    assert model_item.text(3) == "87"
    assert model_item.text(4) == "P_Zaalbar"
    assert model_item.childCount() == 0
    assert helpers_bucket.text(0) == "Helpers"
    assert helpers_bucket.text(3) == "2"
    assert helpers_bucket.child(0).text(0) == "headhook"
    assert helpers_bucket.child(0).text(1) == "Helper"
    assert helpers_bucket.child(0).text(2) == "dummy"
    assert lights_bucket.text(3) == "2"
    assert light_item.text(2) == "hidden, locked"
    assert runtime_light_item.text(0) == "AuroraLight331"
    assert runtime_light_item.text(1) == "Light"
    assert runtime_light_item.text(2) == "enabled, visible"
    assert runtime_light_item.text(4) == "P_Zaalbar"
    option = QtWidgets.QStyleOptionViewItem()
    option.initFrom(panel.tree)
    option.fontMetrics = QtGui.QFontMetrics(panel.tree.font())
    assert panel.tree.itemDelegate().sizeHint(option, panel.tree.model().index(0, 0)).height() >= 24

    panel._filter("zaalbar")
    assert root_item.isHidden() is False
    assert models_bucket.isHidden() is False
    assert model_item.isHidden() is False
    assert lights_bucket.isHidden() is False
    assert light_item.isHidden() is True
    assert runtime_light_item.isHidden() is False
    assert helpers_bucket.isHidden() is False

    panel._filter("")
    panel.tree.setCurrentItem(root_item)
    emitted.clear()
    panel.tree.setCurrentItem(model_item)
    assert emitted == ["model-001"]
    emitted.clear()
    helper_emitted.clear()
    panel.tree.setCurrentItem(helpers_bucket.child(0))
    assert emitted == []
    assert helper_emitted == [head_hook]
    helper_emitted.clear()
    light_emitted.clear()
    panel.tree.setCurrentItem(runtime_light_item)
    assert emitted == []
    assert helper_emitted == []
    assert light_emitted == [aurora_light]


def test_main_window_keeps_cross_panel_selection_sync_on_scene_outliner() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    init_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    select_source = inspect.getsource(QtGhostRiggerMainWindow._select_scene_object_impl)
    skeleton_source = inspect.getsource(QtGhostRiggerMainWindow._on_skeleton_node_selected)
    viewport_source = inspect.getsource(QtGhostRiggerMainWindow._on_viewport_scene_node_selected)

    assert "self.skeleton_panel.nodeSelected.connect(self._on_skeleton_node_selected)" in init_source
    assert "self.scene_outliner_panel.helperNodeSelected.connect(self._on_scene_outliner_helper_node_selected)" in init_source
    assert "self.scene_outliner_panel.lightNodeSelected.connect(self._on_scene_outliner_light_node_selected)" in init_source
    assert "self._sync_skeleton_root_for_scene_object(obj)" in select_source
    assert 'self.viewport.set_selected_node(node, source="nodes panel")' in skeleton_source
    assert "_select_lighting_node_from_node" not in inspect.getsource(QtGhostRiggerMainWindow)
    assert "_select_module_mesh_from_node" not in inspect.getsource(QtGhostRiggerMainWindow)
    assert "def _on_scene_outliner_helper_node_selected(self, node)" in inspect.getsource(QtGhostRiggerMainWindow)
    assert 'self.viewport.set_selected_node(node, source="scene outliner helper")' in inspect.getsource(QtGhostRiggerMainWindow)
    assert "def _on_scene_outliner_light_node_selected(self, node)" in inspect.getsource(QtGhostRiggerMainWindow)
    assert 'self.viewport.set_selected_node(node, source="scene outliner light")' in inspect.getsource(QtGhostRiggerMainWindow)
    assert "self.lighting_panel.select_light(node)" in inspect.getsource(QtGhostRiggerMainWindow)
    assert "self._sync_skeleton_root_for_scene_object(obj)" in viewport_source


def test_main_statusbar_has_persistent_viewport_render_state() -> None:
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    viewport_source = _qt_viewport_widget_source()
    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    status_source = inspect.getsource(QtGhostRiggerMainWindow._build_statusbar)

    assert "renderStateChanged" in viewport_source
    assert "render_state_status_text" in viewport_source
    assert "_configured_renderer_status_label" in viewport_source
    assert "viewport.renderStateChanged.connect(self._on_viewport_render_state_changed)" in layout_source
    assert "viewport_render_state_label" in status_source
    assert "addPermanentWidget" in status_source


def test_cinematic_camera_model_links_focal_length_and_fov() -> None:
    import math
    import pytest

    from src.core.camera.camera_model import GhostRiggerCamera

    camera = GhostRiggerCamera()
    camera.set_focal_length(85.0)

    assert camera.focal_length_mm == pytest.approx(85.0)
    assert camera.field_of_view_degrees < 30.0

    camera.set_field_of_view(60.0)

    assert camera.field_of_view_degrees == pytest.approx(60.0)
    assert camera.focal_length_mm == pytest.approx(36.0 / (2.0 * math.tan(math.radians(60.0) * 0.5)))


def test_camera_manager_serializes_scene_cameras_and_active_camera() -> None:
    from types import SimpleNamespace
    from src.core.camera.camera_manager import CameraManager

    model = SimpleNamespace(name="danm13aa", _base_nodes=[])
    model.all_nodes = lambda: list(model._base_nodes)
    manager = CameraManager()
    manager.set_model(model)
    camera = manager.create_camera(camera_type="Cinematic Camera")
    manager.set_active_camera(camera.id)
    manager.select_camera(camera.id)

    payload = manager.serialize()

    assert payload["active_camera_id"] == camera.id
    assert payload["cameras"][0]["name"] == "Camera001"
    assert getattr(model, "_gr_camera_state")["active_camera_id"] == camera.id
    assert any(getattr(node, "is_camera", False) for node in model.all_nodes())

    restored = CameraManager()
    restored.set_model(model)

    assert restored.get_active_camera().id == camera.id
    assert restored.get_all_cameras()[0].name == "Camera001"


def test_render_output_builds_incrementing_camera_paths(tmp_path) -> None:
    from pathlib import Path

    from src.core.camera.camera_render_settings import RenderSettings
    from src.core.camera.render_output import RenderOutput

    settings = RenderSettings(output_directory=str(tmp_path), output_format="JPG", filename_prefix="")
    output = RenderOutput()
    first = output.build_output_path("Camera001", settings, module_name="danm13aa")
    Path(first).write_text("existing", encoding="utf-8")
    second = output.build_output_path("Camera001", settings, module_name="danm13aa")

    assert Path(first).name == "danm13aa_Camera001_0001.jpg"
    assert Path(second).name == "danm13aa_Camera001_0002.jpg"


def test_qt_viewport_exposes_cinematic_camera_workflow_methods() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = _qt_viewport_widget_source()

    assert "self.camera_manager = CameraManager()" in source
    assert "def switch_to_camera" in source
    assert "def switch_to_perspective" in source
    assert "def update_view_from_camera" in source
    assert "def update_camera_from_view" in source
    assert "def render_still_frame" in source
    assert "_camera_hit_test" in source
    assert "_draw_active_camera_overlays" in source


def test_camera_letterbox_render_burns_opaque_black_bars() -> None:
    from PIL import Image, ImageDraw

    from src.adapters.qt_viewport.camera_overlays import CameraOverlays as AdapterCameraOverlays
    from src.core.camera.camera_model import GhostRiggerCamera
    from src.gui.camera.camera_overlays import CameraOverlays as GuiCameraOverlays

    assert GuiCameraOverlays is AdapterCameraOverlays

    camera = GhostRiggerCamera(show_letterbox=True, letterbox_ratio=4.0)
    image = Image.new("RGBA", (100, 100), (64, 64, 64, 255))
    overlays = AdapterCameraOverlays()
    draw = ImageDraw.Draw(image, "RGBA")

    overlays.draw_letterbox(draw, overlays.active_frame_rect(camera, 100, 100), 100, 100, opaque=True)

    assert image.getpixel((50, 5)) == (0, 0, 0, 255)


def test_kmax_scene_camera_and_light_objects_are_first_class_scene_objects(tmp_path) -> None:
    from src.core.scene.kmax_scene_manager import KMaxSceneManager
    from src.core.scene.kmax_serializer import KMaxSerializer
    from src.core.scene.scene_object import Transform

    manager = KMaxSceneManager()
    camera = manager.add_camera_object(
        "Target Camera",
        Transform(position=(1.0, 2.0, 3.0), rotation=(10.0, 20.0, 30.0)),
        name="ShotCam",
    )
    light = manager.add_light_object(
        "spot",
        Transform(position=(-1.0, 0.5, 4.0)),
        name="KeyLight",
        properties={"color": (0.4, 0.6, 1.0), "intensity": 3.5, "cone_angle": 35.0},
    )
    manager.update_camera_properties(camera.id, focal_length_mm=50.0, target_enabled=True)
    manager.update_light_properties(light.id, radius=9.0, affects_lightmap=False)
    adopted_camera = manager.add_camera_object("Free Camera", name="AdoptedCam", object_id="camera-panel-id", select=False)
    adopted_light = manager.add_light_object("point", name="AdoptedLight", object_id="light-panel-id", select=False)

    path = tmp_path / "camera_light_scene.kmax"
    manager.save_kmax(path)
    payload = KMaxSerializer.to_dict(KMaxSerializer.load(path))

    assert [obj["object_type"] for obj in payload["objects"]] == ["camera", "light", "camera", "light"]
    assert payload["cameras"][0]["scene_object_id"] == camera.id
    assert payload["cameras"][0]["camera_type"] == "Target Camera"
    assert payload["cameras"][0]["focal_length_mm"] == 50.0
    assert payload["lights"][0]["scene_object_id"] == light.id
    assert payload["lights"][0]["type"] == "spot"
    assert payload["lights"][0]["radius"] == 9.0
    assert payload["lights"][0]["affects_lightmap"] is False
    assert adopted_camera.id == "camera-panel-id"
    assert adopted_light.id == "light-panel-id"


def test_sequence_camera_light_bindings_use_stable_scene_ids() -> None:
    from types import SimpleNamespace

    from src.core.camera.camera_manager import CameraManager
    from src.core.lighting.light_manager import LightManager
    from src.core.lighting.light_model import GhostRiggerLight
    from src.core.scene.kmax_scene_manager import KMaxSceneManager
    from src.sequence.sequence_binding import SequenceTargetType
    from src.sequence.sequence_evaluator import SequenceEvaluator
    from src.sequence.sequence_manager import SequenceManager, ensure_sequence_object_id, infer_target_type
    from src.sequence.sequence_model import GhostRiggerLevelSequence
    from src.sequence.tracks.camera_cut_track import CameraCutTrack
    from src.sequence.tracks.camera_property_track import CAMERA_PROPERTIES, CameraPropertyTrack
    from src.sequence.tracks.light_property_track import LIGHT_PROPERTIES, LightPropertyTrack

    manager = KMaxSceneManager()
    scene_camera = manager.add_camera_object("Cinematic Camera", name="ShotCam")
    scene_light = manager.add_light_object("area", name="Fill")
    assert ensure_sequence_object_id(scene_camera) == scene_camera.id
    assert infer_target_type(scene_camera) == SequenceTargetType.CAMERA
    assert ensure_sequence_object_id(scene_light) == scene_light.id
    assert infer_target_type(scene_light) == SequenceTargetType.LIGHT
    assert {"focal_length_mm", "field_of_view_degrees", "focus_distance", "aperture_f_stop", "near_clip", "far_clip", "letterbox_ratio", "target_position"} <= CAMERA_PROPERTIES
    assert {"enabled", "visible", "color", "intensity", "radius", "cone_angle", "area_size", "ambient_only", "casts_shadows", "affects_diffuse", "affects_specular", "affects_lightmap", "affects_environment"} <= LIGHT_PROPERTIES

    camera_manager = CameraManager()
    camera = camera_manager.create_camera(name="ShotCam")
    light_manager = LightManager()
    light = light_manager.add_light(GhostRiggerLight(name="Key", type="spot"))
    viewport = SimpleNamespace(camera_manager=camera_manager, switched=[])
    viewport.parent = lambda: SimpleNamespace(lighting_panel=SimpleNamespace(manager=light_manager))
    viewport.switch_to_camera = lambda camera_id: viewport.switched.append(camera_id)
    viewport.refresh_cameras = lambda: None
    viewport.refresh_lighting = lambda: None
    sequence_manager = SequenceManager()
    sequence = GhostRiggerLevelSequence()
    camera_binding = sequence_manager.add_object_binding(sequence, camera.original_ref)
    focal_track = CameraPropertyTrack(parent_binding_id=camera_binding.binding_id, property_name="focal_length_mm")
    focal_track.add_keyframe(10, 75.0)
    camera_binding.add_track(focal_track)
    cut_track = CameraCutTrack()
    cut_track.add_cut(camera_binding.binding_id, 0, 20, "ShotCam")
    sequence.master_tracks.append(cut_track)
    light_binding = sequence_manager.add_object_binding(sequence, light.original_ref)
    intensity = LightPropertyTrack(parent_binding_id=light_binding.binding_id, property_name="intensity")
    shadow = LightPropertyTrack(parent_binding_id=light_binding.binding_id, property_name="casts_shadows")
    intensity.add_keyframe(10, 4.25)
    shadow.add_keyframe(10, False)
    light_binding.add_track(intensity)
    light_binding.add_track(shadow)

    SequenceEvaluator(viewport).evaluate(sequence, 10)

    assert camera.focal_length_mm == 75.0
    assert viewport.switched == [camera.id]
    assert light.original_ref.light_multiplier == 4.25
    assert light.original_ref.light_shadow is False


def test_sequence_frame_range_edit_keeps_playback_end_tracking_sequence_end() -> None:
    from src.sequence.sequence_model import GhostRiggerLevelSequence

    sequence = GhostRiggerLevelSequence(end_frame=240, playback_end_frame=240)

    sequence.set_frame_range(0, 6)
    assert sequence.end_frame == 6
    assert sequence.playback_end_frame == 6

    sequence.set_frame_range(0, 60)
    assert sequence.end_frame == 60
    assert sequence.playback_end_frame == 60

    sequence.playback_start_frame = 10
    sequence.playback_end_frame = 24
    sequence.set_frame_range(0, 120)

    assert sequence.playback_start_frame == 10
    assert sequence.playback_end_frame == 24


def test_scene_camera_light_authoring_state_flows_are_safe_and_sequence_bindable() -> None:
    from types import SimpleNamespace

    from src.core.camera.camera_model import GhostRiggerCamera
    from src.core.scene.kmax_scene_manager import KMaxSceneManager
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow
    from PySide6 import QtWidgets

    node = SimpleNamespace(name="CameraNode", position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0), children=[])
    node.children.append(SimpleNamespace(parent=node))
    camera = GhostRiggerCamera(original_ref=node)
    payload = camera.to_dict()

    assert "original_ref" not in payload
    assert payload["id"] == camera.id

    manager = KMaxSceneManager()
    light = manager.add_light_object("point", name="MoveLight")
    camera_obj = manager.add_camera_object("Cinematic Camera", name="MoveCamera", select=False)
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    viewport.load_scene_instances(manager.active_scene.objects, scene_name="Light Move Smoke")
    light_node = next(
        node
        for node in viewport.model.all_nodes()
        if str(getattr(node, "_gr_scene_object_id", "") or "") == light.id
    )
    camera_node = next(
        node
        for node in viewport.model.all_nodes()
        if str(getattr(node, "_gr_scene_object_id", "") or "") == camera_obj.id
    )

    assert getattr(light_node, "is_light", False) is True
    assert getattr(camera_node, "is_camera", False) is True
    assert tuple(getattr(light_node, "_gr_pivot_world")) == tuple(light_node.position)
    assert tuple(getattr(camera_node, "_gr_pivot_world")) == tuple(camera_node.position)
    viewport.set_selected_node(light_node)
    assert getattr(viewport._renderer, "selected_node", None) is light_node
    assert tuple(viewport._gizmo_world_position(light_node)) == tuple(light_node.position)
    light_node._gr_pivot_edit_mode = "affect_pivot_only"
    light_node._gr_pivot_world = (3.0, 2.0, 1.0)
    assert tuple(viewport._gizmo_world_position(light_node)) == (3.0, 2.0, 1.0)
    camera_node._gr_pivot_edit_mode = "affect_object_only"
    camera_node._gr_pivot_world = (8.0, 8.0, 8.0)
    assert tuple(viewport._gizmo_world_position(camera_node)) == tuple(camera_node.position)
    scene_camera = viewport.camera_manager.find_by_original(camera_node)
    assert scene_camera is not None
    scene_camera.target_enabled = True
    scene_camera.target_position = (0.0, 1.0, 2.0)
    scene_camera.position = tuple(camera_node.position)
    scene_camera.apply_to_original()
    camera_node.position = (2.0, 3.0, 4.0)
    viewport._notify_node_moved(camera_node, live=True)
    assert scene_camera.position == (2.0, 3.0, 4.0)
    assert scene_camera.target_position == (2.0, 4.0, 6.0)
    assert tuple(getattr(camera_node, "_gr_gizmo_world_position")) == (2.0, 3.0, 4.0)

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    workflow_source = inspect.getsource(QtGhostRiggerMainWindow._add_scene_object_to_sequence)
    outliner_source = (ROOT / "src/gui/panels/qt_scene_outliner_panel.py").read_text(encoding="utf-8")
    drag_source = (ROOT / "src/gui/viewports/viewport_core/widgets/drag_interactions.py").read_text(encoding="utf-8")
    history_source = (ROOT / "src/gui/viewports/viewport_core/widgets/history_animation.py").read_text(encoding="utf-8")
    scene_models_source = (ROOT / "src/gui/viewports/viewport_core/widgets/scene_models.py").read_text(encoding="utf-8")
    state_helpers_source = (ROOT / "src/gui/viewports/viewport_core/widgets/state_helpers.py").read_text(encoding="utf-8")
    transform_gizmo_source = (ROOT / "src/core/gizmo/transform_gizmo.py").read_text(encoding="utf-8")
    scene_workflow_source = (ROOT / "src/gui/windows/application_core/shared/scene_workflow.py").read_text(encoding="utf-8")
    editor_services_source = (ROOT / "src/gui/windows/application_core/shared/editor_services.py").read_text(encoding="utf-8")
    viewport_tools_source = (ROOT / "src/gui/windows/application_core/shared/viewport_tools.py").read_text(encoding="utf-8")
    renderer_overlay_source = (ROOT / "src/core/rendering/frame_core/renderer_overlays.py").read_text(encoding="utf-8")
    sequence_track_list_source = (ROOT / "src/gui/sequence_editor/sequence_track_list_widget.py").read_text(encoding="utf-8")
    sequence_editor_source = (ROOT / "src/gui/sequence_editor/sequence_editor_window.py").read_text(encoding="utf-8")

    assert "objectAddToSequenceRequested.connect(self._add_scene_object_to_sequence)" in layout_source
    assert "editor.manager.add_object_binding(editor.sequence, obj)" in workflow_source
    assert "objectAddToSequenceRequested = QtCore.Signal(str)" in outliner_source
    assert "Add to Sequence" in outliner_source
    assert "_expanded_item_keys" in outliner_source
    assert "_restore_expanded_item_keys" in outliner_source
    assert "def _tag_scene_helper_pivot" in scene_models_source
    assert "_tag_scene_helper_pivot(node, instance, position)" in scene_models_source
    assert "_gr_pivot_edit_mode" in state_helpers_source
    assert "bool(getattr(obj, \"is_light\", False)) or bool(getattr(obj, \"is_camera\", False))" in transform_gizmo_source
    assert "from src.systems.bas.model_recipe import BAS_SLOT_ORDER" in viewport_tools_source
    assert "self._notify_node_moved(node, live=True)" in drag_source
    assert "self._notify_node_moved(node)" in drag_source
    assert "def _notify_node_moved(self, node, *, live: bool = False)" in history_source
    assert "camera.target_position" in history_source
    assert "_gr_transform_previewing" in scene_workflow_source
    assert "payload[\"target_position\"]" in scene_workflow_source
    assert "if live_preview:" in scene_workflow_source
    assert "if bool(getattr(node, \"_gr_transform_previewing\", False)):" in editor_services_source
    assert "H - 72 - text_h" in renderer_overlay_source
    assert "addSelectedObjectRequested = QtCore.Signal()" in sequence_track_list_source
    assert "addTrackRequested = QtCore.Signal(str)" in sequence_track_list_source
    assert "deleteSelectionRequested = QtCore.Signal()" in sequence_track_list_source
    assert "Add Selected Scene Object" in sequence_track_list_source
    assert "Add Track" in sequence_track_list_source
    assert "Delete Track" in sequence_track_list_source
    assert "deleteSelectionRequested.connect(self._delete_selected_outliner_item)" in sequence_editor_source
    assert "def _delete_selected_outliner_item" in sequence_editor_source
    assert "master_track_types = {\"Camera Cut\", \"Sub Sequence\", \"Event\"}" in sequence_editor_source


def test_scene_camera_light_authoring_uses_registered_svg_icons_and_delete_signal() -> None:
    required_icons = {
        "camera_free.svg",
        "camera_target.svg",
        "camera_cinematic.svg",
        "light_point.svg",
        "light_spot.svg",
        "light_directional.svg",
        "light_area.svg",
        "light_ambient.svg",
        "viewport_light_helpers.svg",
        "lighting_mode_scene.svg",
        "lighting_mode_shader.svg",
        "lighting_complexity_basic.svg",
        "lighting_rig_kotor.svg",
    }
    icon_dir = ROOT / "src/gui/icons"
    assert required_icons <= {path.name for path in icon_dir.glob("*.svg")}

    from src.gui.qt_lib.panels.qt_lighting_panel import QtLightingPanel

    icon_manager_source = (ROOT / "src/gui/assets/qt_icon_manager.py").read_text(encoding="utf-8")
    camera_panel_source = (ROOT / "src/gui/panels/qt_camera_panel.py").read_text(encoding="utf-8")
    lighting_panel_source = (ROOT / "src/gui/panels/qt_lighting_panel.py").read_text(encoding="utf-8")
    sequence_toolbar_source = (ROOT / "src/gui/sequence_editor/sequence_toolbar.py").read_text(encoding="utf-8")
    event_source = (ROOT / "src/gui/viewports/viewport_core/widgets/event_navigation.py").read_text(encoding="utf-8")
    viewport_source = (ROOT / "src/gui/viewports/viewport_core/widgets/viewport_widget.py").read_text(encoding="utf-8")
    viewport_construction_source = (ROOT / "src/gui/viewports/viewport_core/widgets/construction.py").read_text(encoding="utf-8")
    viewport_display_source = (ROOT / "src/gui/viewports/viewport_core/widgets/display_controls.py").read_text(encoding="utf-8")
    main_layout_source = (ROOT / "src/gui/windows/application_core/shared/main_layout.py").read_text(encoding="utf-8")
    chrome_source = (ROOT / "src/gui/windows/application_core/shared/window_chrome.py").read_text(encoding="utf-8")
    viewport_tools_source = (ROOT / "src/gui/windows/application_core/shared/viewport_tools.py").read_text(encoding="utf-8")
    sequence_property_source = (ROOT / "src/gui/sequence_editor/sequence_property_panel.py").read_text(encoding="utf-8")

    for icon_name in ("SCENE", "CAMERA_FREE", "CAMERA_TARGET", "CAMERA_CINEMATIC", "LIGHT_POINT", "LIGHT_SPOT", "LIGHT_DIRECTIONAL", "LIGHT_AREA", "LIGHT_AMBIENT", "VIEWPORT_LIGHT_HELPERS", "LIGHTING_MODE_SCENE", "LIGHTING_COMPLEXITY_BASIC", "LIGHTING_RIG_KOTOR"):
        assert icon_name in icon_manager_source
    assert "qt_icon_manager.get(icon_name, 18)" in camera_panel_source
    assert "qt_icon_manager.get(icon_name, 18)" in lighting_panel_source
    assert '"Add Light to Scene"' in lighting_panel_source
    assert '"Lighting System"' in lighting_panel_source
    assert '"Texture Maps:"' in lighting_panel_source
    assert '"position"' not in inspect.getsource(QtLightingPanel._apply_editor)
    assert "ViewportLightHelpersButton" in viewport_construction_source
    assert "toggle_light_helpers" in viewport_display_source
    assert "createCamera = QtCore.Signal(str)" in sequence_toolbar_source
    assert "createLight = QtCore.Signal(str)" in sequence_toolbar_source
    assert "sceneObjectDeleteRequested = QtCore.Signal(str)" in viewport_source
    assert "Key_Delete" in event_source
    assert "sceneObjectDeleteRequested.emit(object_id)" in event_source
    assert "sceneObjectDeleteRequested.connect(self._delete_scene_object)" in main_layout_source
    assert "self.scene_manager.select_object(object_id)" in (ROOT / "src/gui/windows/application_core/shared/scene_workflow.py").read_text(encoding="utf-8")
    assert "viewport.switch_to_perspective()" in (ROOT / "src/gui/windows/application_core/shared/scene_workflow.py").read_text(encoding="utf-8")
    assert 'addMenu("Create")' in chrome_source
    assert '"Create Camera"' in chrome_source
    assert '"Create Light"' in chrome_source
    assert 'self._icon("camera_free")' in chrome_source
    assert 'self._icon("light_point")' in chrome_source
    assert "object_id=object_id" in viewport_tools_source
    assert "scene_manager.add_camera_object" in viewport_tools_source
    assert "scene_manager.add_light_object" in viewport_tools_source
    assert "all_lights(include_deleted=True)" in viewport_tools_source
    assert "scene_manager.remove_light_object(object_id)" in viewport_tools_source
    assert "sequence.set_frame_range" in sequence_property_source


def test_camera_overlays_are_qt_viewport_adapter_owned() -> None:
    """Camera overlay drawing is adapter-owned, with the old GUI path as a facade."""
    import sys

    import src.adapters.qt_viewport.camera_overlays as adapter_camera_overlays_module
    import src.gui.camera.camera_overlays as gui_camera_overlays_module

    adapter_source = (ROOT / "src/adapters/qt_viewport/camera_overlays.py").read_text(encoding="utf-8")
    gui_source = (ROOT / "src/gui/camera/camera_overlays.py").read_text(encoding="utf-8")
    dependencies_source = (ROOT / "src/gui/viewports/viewport_core/shared/dependencies.py").read_text(encoding="utf-8")
    still_frame_source = (ROOT / "src/adapters/qt_viewport/still_frame_renderer.py").read_text(encoding="utf-8")

    assert "class CameraOverlays" in adapter_source
    assert gui_camera_overlays_module is adapter_camera_overlays_module
    assert sys.modules["src.gui.camera.camera_overlays"] is adapter_camera_overlays_module
    assert 'import_module("src.adapters.qt_viewport.camera_overlays")' in gui_source
    assert "sys.modules[__name__] = _module" in gui_source
    assert "import *" not in gui_source
    assert "from src.adapters.qt_viewport.camera_overlays import CameraOverlays" in dependencies_source
    assert "from src.adapters.qt_viewport.camera_overlays import CameraOverlays" in still_frame_source
    assert "src.gui.camera.camera_overlays" not in still_frame_source


def test_camera_gizmo_renderer_is_qt_viewport_adapter_owned() -> None:
    """Camera helper/frustum drawing is adapter-owned, with the old GUI path as a facade."""
    import sys

    import src.adapters.qt_viewport.camera_gizmo_renderer as adapter_camera_gizmo_module
    import src.gui.camera.camera_gizmo_renderer as gui_camera_gizmo_module

    from src.adapters.qt_viewport.camera_gizmo_renderer import CameraGizmoRenderer as AdapterCameraGizmoRenderer
    from src.gui.camera.camera_gizmo_renderer import CameraGizmoRenderer as GuiCameraGizmoRenderer
    from src.gui.qt_lib.camera.camera_gizmo_renderer import CameraGizmoRenderer as QtLibCameraGizmoRenderer

    assert GuiCameraGizmoRenderer is AdapterCameraGizmoRenderer
    assert gui_camera_gizmo_module is adapter_camera_gizmo_module
    assert sys.modules["src.gui.camera.camera_gizmo_renderer"] is adapter_camera_gizmo_module
    assert QtLibCameraGizmoRenderer is AdapterCameraGizmoRenderer

    adapter_source = (ROOT / "src/adapters/qt_viewport/camera_gizmo_renderer.py").read_text(encoding="utf-8")
    gui_source = (ROOT / "src/gui/camera/camera_gizmo_renderer.py").read_text(encoding="utf-8")
    dependencies_source = (ROOT / "src/gui/viewports/viewport_core/shared/dependencies.py").read_text(encoding="utf-8")

    assert "class CameraGizmoRenderer" in adapter_source
    assert "from src.math.camera_math import" in adapter_source
    assert "PySide6" not in adapter_source
    assert "src.gui." not in adapter_source
    assert 'import_module("src.adapters.qt_viewport.camera_gizmo_renderer")' in gui_source
    assert "sys.modules[__name__] = _module" in gui_source
    assert "import *" not in gui_source
    assert "from src.adapters.qt_viewport.camera_gizmo_renderer import CameraGizmoRenderer" in dependencies_source
    assert "src.gui.camera.camera_gizmo_renderer" not in dependencies_source


def test_still_frame_renderer_suppresses_viewport_camera_overlays() -> None:
    import sys
    from types import SimpleNamespace

    from PIL import Image

    import src.adapters.qt_viewport.still_frame_renderer as adapter_frame_renderer_module
    import src.gui.camera.frame_renderer as gui_frame_renderer_module
    from src.core.camera.camera_model import GhostRiggerCamera
    from src.core.camera.camera_render_settings import RenderSettings
    from src.adapters.qt_viewport.still_frame_renderer import FrameRenderer as AdapterFrameRenderer
    from src.gui.camera.frame_renderer import FrameRenderer as GuiFrameRenderer

    assert GuiFrameRenderer is AdapterFrameRenderer
    assert gui_frame_renderer_module is adapter_frame_renderer_module
    assert sys.modules["src.gui.camera.frame_renderer"] is adapter_frame_renderer_module
    gui_frame_source = (ROOT / "src/gui/camera/frame_renderer.py").read_text(encoding="utf-8")
    assert 'import_module("src.adapters.qt_viewport.still_frame_renderer")' in gui_frame_source
    assert "sys.modules[__name__] = _module" in gui_frame_source
    assert "import *" not in gui_frame_source

    calls = []
    viewport = SimpleNamespace(
        _renderer=SimpleNamespace(show_gimbal=True, show_grid=True, show_light_gizmos=True),
        _gpu_renderer=SimpleNamespace(show_grid=True, show_light_gizmos=True),
        _camera_helper_renderer=SimpleNamespace(show_camera_helpers=True),
        _render_suppress_camera_overlays=False,
    )

    def _render_frame(width: int, height: int):
        calls.append(bool(viewport._render_suppress_camera_overlays))
        return Image.new("RGBA", (width, height), (32, 32, 32, 255))

    viewport._render_frame = _render_frame
    renderer = AdapterFrameRenderer(viewport)
    settings = RenderSettings(
        resolution_source="custom",
        resolution_width=32,
        resolution_height=24,
        include_letterbox=False,
        include_safe_frame=False,
        include_camera_guides=False,
        include_grid=False,
        include_helpers=False,
    )

    image = renderer.render_current_frame(settings, GhostRiggerCamera())

    assert image.size == (32, 24)
    assert calls == [True]
    assert viewport._render_suppress_camera_overlays is False
    assert viewport._renderer.show_grid is True
    assert viewport._camera_helper_renderer.show_camera_helpers is True


def test_viewport_navigation_profiles_are_available() -> None:
    from src.gui.qt_lib.viewports.viewport_navigation import (
        DEFAULT_VIEWPORT_NAVIGATION_PROFILE,
        VIEWPORT_NAVIGATION_HELP,
        VIEWPORT_NAVIGATION_PROFILES,
        normalize_viewport_navigation_profile,
    )

    assert set(VIEWPORT_NAVIGATION_PROFILES) == {"3dsmax", "blender", "maya"}
    assert DEFAULT_VIEWPORT_NAVIGATION_PROFILE == "maya"
    assert normalize_viewport_navigation_profile("3ds Max") == "3dsmax"
    assert normalize_viewport_navigation_profile("Blender") == "blender"
    assert normalize_viewport_navigation_profile("Maya") == "maya"
    assert "T: Toggle texture" in VIEWPORT_NAVIGATION_HELP
    assert "Shift+T: Top view" in VIEWPORT_NAVIGATION_HELP
    assert "Alt+G: Toggle grid" in VIEWPORT_NAVIGATION_HELP
    assert "Alt+X: Toggle X-Ray viewport overlay" in VIEWPORT_NAVIGATION_HELP


def test_qt_viewport_uses_profiled_navigation_actions() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._navigation_action)
    assert 'profile == "3dsmax"' in source
    assert 'profile == "blender"' in source
    assert 'profile == "maya"' in source
    assert "QtCore.Qt.AltModifier" in source


def test_qt_viewport_gpu_grid_is_native_and_xray_is_overlay_only() -> None:
    import inspect

    from src.adapters.rendering.moderngl_renderer_impl import GpuRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    gpu_source = inspect.getsource(GpuRenderer._draw_grid)
    assert "ctx.depth_mask = False" in gpu_source
    assert "vao.render(moderngl.LINES)" in gpu_source
    render_source = inspect.getsource(GpuRenderer._render_gpu)
    assert "self._draw_grid(ctx, mvp)" in render_source
    overlay_source = inspect.getsource(QtViewportWidget._draw_gpu_viewport_overlays)
    assert "if self._xray_mode" in overlay_source
    assert "not gpu_base" not in overlay_source
    event_source = inspect.getsource(QtViewportWidget.eventFilter)
    assert "QtCore.Qt.Key_G" in event_source
    assert "self.grid_button.click()" in event_source
    assert "QtCore.Qt.Key_X" in event_source
    assert "QtCore.Qt.AltModifier" in event_source


def test_qt_animations_panel_can_select_loaded_animation() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    model = SimpleNamespace(
        animations=[
            SimpleNamespace(name="pause1"),
            SimpleNamespace(name="walkss"),
        ]
    )

    panel.load_model(model, select_name="walkss")

    assert panel.selected_animation() == "walkss"
    assert panel.listbox.currentItem().text() == "Walkss [walkss]"
    assert panel.info.toPlainText() == "2 animation(s)"


def test_qt_animations_panel_displays_readable_names_with_raw_animation_slots() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel, animation_display_name, animation_row_label

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    model = SimpleNamespace(
        animations=[
            SimpleNamespace(name="pause1"),
            SimpleNamespace(name="animloop03"),
            SimpleNamespace(name="b1a1"),
            SimpleNamespace(name="b5a1"),
            SimpleNamespace(name="b6a1"),
            SimpleNamespace(name="b7a1"),
            SimpleNamespace(name="b8a1"),
            SimpleNamespace(name="c10n3"),
            SimpleNamespace(name="c2a1"),
            SimpleNamespace(name="f2p4a"),
            SimpleNamespace(name="g1a1"),
            SimpleNamespace(name="g2f1"),
            SimpleNamespace(name="g2r1"),
            SimpleNamespace(name="g2w1"),
            SimpleNamespace(name="g3w1"),
            SimpleNamespace(name="g5a1"),
            SimpleNamespace(name="g6a1"),
            SimpleNamespace(name="g7a1"),
            SimpleNamespace(name="g8a1"),
            SimpleNamespace(name="g9a1"),
            SimpleNamespace(name="g3x1"),
            SimpleNamespace(name="g3y1"),
            SimpleNamespace(name="g3z1"),
            SimpleNamespace(name="m2d1"),
            SimpleNamespace(name="m4d2"),
        ]
    )
    emitted = []
    panel.animationSelected.connect(emitted.append)

    panel.load_model(model, select_name="b1a1")

    assert animation_display_name("pause1") == "Idle 1"
    assert panel.listbox.item(0).text() == "Idle 1 [pause1]"
    assert panel.listbox.item(1).text() == "Ambient Loop 03 [animloop03]"
    assert panel.listbox.item(2).text() == "Blaster Set 1 Attack 1 [b1a1]"
    assert panel.listbox.item(3).text() == "Blaster Set 5 (Single Hand Blasters) Attack 1 [b5a1]"
    assert panel.listbox.item(4).text() == "Blaster Set 6 (Dual Blasters: L + R) Attack 1 [b6a1]"
    assert panel.listbox.item(5).text() == "Blaster Set 7 (Blaster Rifles: Both Hands) Attack 1 [b7a1]"
    assert panel.listbox.item(6).text() == "Blaster Set 8 (Assault Cannons: Both Hands) Attack 1 [b8a1]"
    assert panel.listbox.item(7).text() == "Combat Set 10 Block 3 [c10n3]"
    assert panel.listbox.item(8).text() == "Combat Set 2 (Single Hand Melee: Vibrosword, Short Sword) Attack 1 [c2a1]"
    assert panel.listbox.item(9).text() == "Fists Set 2 Parry 4 Form A [f2p4a]"
    assert panel.listbox.item(10).text() == "General Weapon Set 1 (Single Hand Melee: Shortsword) Attack 1 [g1a1]"
    assert panel.listbox.item(11).text() == "General Weapon Set 2 (Single Hand Melee: Lightsaber, Melee) Flurry 1 [g2f1]"
    assert panel.listbox.item(12).text() == "General Weapon Set 2 (Single Hand Melee: Lightsaber, Melee) Idle (On Guard Pose) 1 [g2r1]"
    assert panel.listbox.item(13).text() == "General Weapon Set 2 (Single Hand Melee: Lightsaber, Melee) Activate Lightsaber 1 [g2w1]"
    assert panel.listbox.item(14).text() == "General Weapon Set 3 Activate Weapon 1 [g3w1]"
    assert panel.listbox.item(15).text() == "General Weapon Set 5 (Blaster Pistol) Attack 1 [g5a1]"
    assert panel.listbox.item(16).text() == "General Weapon Set 6 (Dual Blasters) Attack 1 [g6a1]"
    assert panel.listbox.item(17).text() == "General Weapon Set 7 (Blaster Rifles) Attack 1 [g7a1]"
    assert panel.listbox.item(18).text() == "General Weapon Set 8 (Hand to Hand Combat) Attack 1 [g8a1]"
    assert panel.listbox.item(19).text() == "General Weapon Set 9 (Assault Cannons) Attack 1 [g9a1]"
    assert panel.listbox.item(20).text() == "General Weapon Set 3 Fall Through Air 1 [g3x1]"
    assert panel.listbox.item(21).text() == "General Weapon Set 3 Air-To-Ground Fall 1 [g3y1]"
    assert panel.listbox.item(22).text() == "General Weapon Set 3 Get Back Up 1 [g3z1]"
    assert panel.listbox.item(23).text() == "Melee Set 2 (Vibroswords, Shortswords) Defend 1 [m2d1]"
    assert panel.listbox.item(24).text() == "Melee Set 4 Defend 2 [m4d2]"
    assert animation_row_label("c10a1", game="K2") == "Combat Set 10 Attack 1 [c10a1] [K2]"
    assert animation_row_label("b8a1", game="K1") == "Blaster Set 8 (Assault Cannons: Both Hands) Attack 1 [b8a1] [K1]"
    assert animation_row_label("b8a1", game="K2") == "Blaster Set 8 Attack 1 [b8a1] [K2]"
    assert animation_row_label("b9a1", game="K1") == "Blaster Set 9 Attack 1 [b9a1] [K1]"
    assert animation_row_label("b9a1", game="K2") == "Blaster Set 9 (Assault Cannons: Both Hands) Attack 1 [b9a1] [K2]"
    assert panel.selected_animation() == "b1a1"
    assert emitted[-1] == "b1a1"
    assert panel.select_animation("pause1") is True
    assert panel.selected_animation() == "pause1"


def test_qt_animations_panel_marks_inherited_readable_names_with_raw_slots() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()

    panel.add_effective_animation({"name": "pause1", "inherited": True, "source": "S_Male02", "game": "K1"})

    item = panel.listbox.item(0)
    assert item.text() == "Idle 1 (Inherited from S_Male02) [pause1] [K1]"
    panel.listbox.setCurrentItem(item)
    assert panel.selected_animation() == "pause1"


def test_qt_animations_panel_exposes_inheritance_game_selector() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    changes = []
    panel.inheritanceGameChanged.connect(changes.append)

    panel.set_inheritance_game("K2")

    assert panel.selected_inheritance_game() == "K2"
    assert changes[-1] == "K2"

    panel.set_inheritance_game("")

    assert panel.selected_inheritance_game() == ""


def test_qt_animations_panel_exposes_animation_source_selector() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    changes = []
    panel.animationSourceChanged.connect(changes.append)

    panel.set_animation_source("head")

    assert panel.selected_animation_source() == "head"
    assert changes[-1] == "head"

    panel.set_animation_source("attachment")

    assert panel.selected_animation_source() == "attachment"


def test_main_window_head_animation_source_accepts_standalone_head() -> None:
    from src.core.geometry.model_data import KotorModel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    class Panel:
        def selected_animation_source(self) -> str:
            return "head"

    window = QtGhostRiggerMainWindow.__new__(QtGhostRiggerMainWindow)
    window.animations_panel = Panel()
    window._current_head_model = None
    window._current_model = KotorModel(name="PMHC01", supermodel="S_Female02")

    assert window._animation_source_model() is window._current_model

    window._current_model = KotorModel(name="PMBAM", supermodel="S_Male02")

    assert window._animation_source_model() is None


def test_main_window_loads_inherited_animations_for_standalone_head() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.animation.animation_engine import SuperModelResolver
    from src.core.geometry.model_data import Animation, KotorModel
    from src.gui.qt_lib.panels.qt_animation_panel import ANIMATION_NAME_ROLE, QtAnimationsPanel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    SuperModelResolver.prime_cache(
        "S_Female02",
        KotorModel(
            name="S_Female02",
            animations=[
                Animation(name="b5a1", length=1.0),
                Animation(name="lookr", length=1.0),
                Animation(name="tlknorm", length=1.0),
                Animation(name="walk", length=1.0),
            ],
        ),
    )
    try:
        head = KotorModel(name="PMHC01", supermodel="S_Female02")
        head.animations = [Animation(name="custom_face_pose", length=1.0)]
        window = QtGhostRiggerMainWindow.__new__(QtGhostRiggerMainWindow)
        window.animations_panel = QtAnimationsPanel()
        window.animations_panel.set_animation_source("head")
        window._current_model = head
        window._current_head_model = None
        window._current_game = "K1"
        window._get_resource_manager = lambda: None

        window._load_animation_panel_model(head)

        assert window.animations_panel.select_animation("tlknorm") is True
        assert "Inherited from S_Female02" in window.animations_panel.listbox.currentItem().text()
        shown = {
            window.animations_panel.listbox.item(index).data(ANIMATION_NAME_ROLE)
            for index in range(window.animations_panel.listbox.count())
        }
        assert shown == {"custom_face_pose", "lookr", "tlknorm"}
    finally:
        SuperModelResolver.clear_cache()
        SuperModelResolver.configure(None)


def test_body_attachment_panel_exposes_bas_slots_and_attach_signal() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_body_attachment_panel import QtBodyAttachmentPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtBodyAttachmentPanel()
    emitted = []
    panel.attachRequested.connect(lambda slot, resref: emitted.append((slot, resref)))

    panel.set_selected_slot("right_weapon")
    panel.model_combo.setCurrentText("w_lghtsbr_001")
    panel.attach_button.click()

    assert panel.selected_slot() == "right_weapon"
    assert emitted[-1] == ("right_weapon", "w_lghtsbr_001")
    assert "HEAD" in {button.text().splitlines()[0] for button in panel.findChildren(QtWidgets.QToolButton)}
    assert "BODY" in {button.text().splitlines()[0] for button in panel.findChildren(QtWidgets.QToolButton)}
    assert {"MASK", "GOGGLES", "BELT"} <= {button.text().splitlines()[0] for button in panel.findChildren(QtWidgets.QToolButton)}

    panel.set_selected_slot("left_weapon")
    preset_resrefs = {str(panel.model_combo.itemData(index) or "") for index in range(panel.model_combo.count())}
    assert "w_vbroswrd_001" in preset_resrefs
    assert "w_vbroblade_001" not in preset_resrefs

    panel.set_selected_slot("left_hand")
    panel.model_combo.setCurrentText("w_vbroswrd_001")
    panel.attach_button.click()

    assert emitted[-1] == ("right_weapon", "w_lghtsbr_001")
    assert panel.attach_button.isEnabled() is False

    panel.set_mode("full_body")
    assert panel.selected_mode() == "full_body"
    assert panel.selected_slot() != "head"
    panel.set_selected_slot("head")
    assert panel.attach_button.isEnabled() is False


def test_body_attachment_panel_tracks_attachment_layers() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_body_attachment_panel import QtBodyAttachmentPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtBodyAttachmentPanel()

    panel.set_body_model(SimpleNamespace(name="PMBAM"))
    panel.set_slot_model("head", resref="pmhc01")
    panel.set_slot_model("right_weapon", resref="w_lghtsbr_001")

    rows = panel.layer_rows()
    assert rows[0] == ("BODY", "PMBAM", "Base")
    assert ("HEAD", "pmhc01", "Attached") in rows
    assert ("MASK", "", "Empty") in rows
    assert ("GOGGLES", "", "Empty") in rows
    assert ("BELT", "", "Empty") in rows
    assert ("R. Wep", "w_lghtsbr_001", "Attached") in rows
    assert ("L. Weapon", "", "Empty") in rows
    assert ("L. HAND", "", "Socket") in rows
    assert ("R. HAND", "", "Socket") in rows

    head_row = next(index for index, row in enumerate(rows) if row[0] == "HEAD")
    panel.layer_tree.setCurrentItem(panel.layer_tree.topLevelItem(head_row))

    assert panel.selected_slot() == "head"


def test_body_attachment_panel_exposes_save_build_signal() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_body_attachment_panel import QtBodyAttachmentPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtBodyAttachmentPanel()
    calls = []
    panel.saveBuildRequested.connect(lambda: calls.append("save"))

    panel.save_build_button.click()

    assert calls == ["save"]


def test_bas_weapon_alignment_defaults_keep_sabers_identity() -> None:
    from src.systems.bas.attachment_alignment import default_bas_attachment_transform

    assert default_bas_attachment_transform("right_weapon", "w_lghtsbr_001")["position"] == [0.0, 0.0, 0.0]
    assert default_bas_attachment_transform("right_weapon", "w_blstrrfl_001")["position"] == [0.0, 0.06, 0.09]
    assert default_bas_attachment_transform("left_weapon", "w_vbroshort_001")["position"] == [0.0, 0.0, 0.035]
    assert default_bas_attachment_transform("left_weapon", "w_vbroswrd_001")["position"] == [0.0, 0.0, 0.055]


def test_bas_attach_seeds_weapon_alignment_without_overwriting_same_model_adjustment() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    calls = []
    body = SimpleNamespace(name="P_CarthBB")
    panel = SimpleNamespace(
        set_status=lambda text: calls.append(("status", text)),
        set_slot_model=lambda slot, model, resref="": calls.append(("slot", slot, resref)),
    )
    window = SimpleNamespace(
        _bas_body_model=body,
        _current_model=body,
        _bas_attachments={},
        _bas_attachment_resrefs={},
        _bas_attachment_transforms={},
        body_attachment_panel=panel,
        _load_bas_attachment_model=lambda resref: SimpleNamespace(name=resref),
        _rebuild_bas_preview=lambda: "BAS preview updated.",
        _refresh_bas_animation_panel_after_layer_change=lambda slot: calls.append(("anim", slot)),
    )

    QtGhostRiggerMainWindow._handle_bas_attach_requested(window, "right_weapon", "w_blstrrfl_001")
    assert window._bas_attachment_transforms["right_weapon"]["position"] == [0.0, 0.06, 0.09]

    window._bas_attachment_transforms["right_weapon"]["position"] = [0.25, 0.0, 0.0]
    QtGhostRiggerMainWindow._handle_bas_attach_requested(window, "right_weapon", "w_blstrrfl_001")
    assert window._bas_attachment_transforms["right_weapon"]["position"] == [0.25, 0.0, 0.0]

    QtGhostRiggerMainWindow._handle_bas_attach_requested(window, "right_weapon", "w_lghtsbr_001")
    assert window._bas_attachment_transforms["right_weapon"]["position"] == [0.0, 0.0, 0.0]


def test_bas_mask_goggles_and_belt_slots_use_socket_layers() -> None:
    from types import MethodType

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    root = ModelNode(name="bodyroot")
    headhook = ModelNode(name="headhook", parent=root)
    pelvis = ModelNode(name="pelvis_g", parent=root)
    root.children.extend([headhook, pelvis])
    body = KotorModel(name="Body", root_node=root)
    head_root = ModelNode(name="headroot")
    mask_hook = ModelNode(name="MaskHook", parent=head_root)
    goggle_hook = ModelNode(name="GoggleHook", parent=head_root)
    head_root.children.extend([mask_hook, goggle_hook])
    head = KotorModel(name="Head", root_node=head_root)
    mask = KotorModel(name="Mask", root_node=ModelNode(name="maskroot"))
    goggles = KotorModel(name="Goggles", root_node=ModelNode(name="goggleroot"))
    belt = KotorModel(name="Belt", root_node=ModelNode(name="beltroot"))

    window = SimpleNamespace()
    window._find_model_node = MethodType(QtGhostRiggerMainWindow._find_model_node, window)
    window._reset_bas_model_node_traversal = MethodType(QtGhostRiggerMainWindow._reset_bas_model_node_traversal, window)
    window._prepare_bas_layer_root = MethodType(QtGhostRiggerMainWindow._prepare_bas_layer_root, window)
    window._tag_bas_attachment_subtree = MethodType(QtGhostRiggerMainWindow._tag_bas_attachment_subtree, window)

    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, head, "headhook", slot="head") is True
    attached_head = headhook.children[-1]
    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, mask, "MaskHook", slot="mask") is True
    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, goggles, "GoggleHook", slot="goggles") is True
    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, belt, "pelvis_g", slot="belt") is True

    assert attached_head.children[0].children[-1]._gr_bas_socket_name == "MaskHook"
    assert attached_head.children[1].children[-1]._gr_bas_socket_name == "GoggleHook"
    assert pelvis.children[-1]._gr_bas_socket_name == "pelvis_g"
    assert pelvis.children[-1]._gr_bas_attachment_layer is True


def test_qt_animations_panel_exposes_inheritance_supermodel_selector() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    changes = []
    panel.inheritanceSupermodelChanged.connect(changes.append)

    panel.set_inheritance_supermodel("S_Female03")

    assert panel.selected_inheritance_supermodel() == "S_Female03"
    assert changes[-1] == "S_Female03"

    panel.set_inheritance_supermodel("")

    assert panel.selected_inheritance_supermodel() == ""


def test_animation_resolution_game_override_preserves_model_source_game() -> None:
    from src.core.geometry.model_data import GameVersion, KotorModel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    model = KotorModel(name="OverrideSourceGame")
    model._gr_source_game = "K2"

    QtGhostRiggerMainWindow._apply_animation_resolution_game(None, model, "K1")

    assert model.game_version == GameVersion.K1
    assert model._gr_source_game == "K2"


def test_animation_resolution_context_temporarily_overrides_supermodel() -> None:
    from src.core.geometry.model_data import GameVersion, KotorModel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    model = KotorModel(name="OverrideSupermodel", supermodel="S_Male02")
    model.game_version = GameVersion.K1

    class Window:
        _apply_animation_resolution_game = QtGhostRiggerMainWindow._apply_animation_resolution_game

    window = Window()

    with QtGhostRiggerMainWindow._animation_resolution_context(window, model, "K2", "S_Female03"):
        assert model.supermodel == "S_Female03"
        assert model.game_version == GameVersion.K2

    assert model.supermodel == "S_Male02"
    assert model.game_version == GameVersion.K1


def test_bas_attachment_preview_parents_item_to_body_socket() -> None:
    from types import MethodType

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    root = ModelNode(name="bodyroot")
    rhand = ModelNode(name="rhand", parent=root)
    root.children.append(rhand)
    body = KotorModel(name="Body", root_node=root)
    item_root = ModelNode(name="weaponroot")
    item = KotorModel(name="Weapon", root_node=item_root)
    window = SimpleNamespace()
    window._find_model_node = MethodType(QtGhostRiggerMainWindow._find_model_node, window)
    window._reset_bas_model_node_traversal = MethodType(QtGhostRiggerMainWindow._reset_bas_model_node_traversal, window)
    window._prepare_bas_layer_root = MethodType(QtGhostRiggerMainWindow._prepare_bas_layer_root, window)
    window._tag_bas_attachment_subtree = MethodType(QtGhostRiggerMainWindow._tag_bas_attachment_subtree, window)

    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, item, "rhand") is True

    assert len(rhand.children) == 1
    assert rhand.children[0].name == "weaponroot"
    assert rhand.children[0].parent is rhand
    assert rhand.children[0]._gr_bas_attachment_root is True
    assert rhand.children[0]._gr_bas_socket_name == "rhand"
    assert rhand.children[0]._gr_bas_attachment_layer is True


def test_bas_attachment_socket_layer_follows_body_dummy_without_skinning() -> None:
    from types import MethodType

    import pytest

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow
    from src.adapters.rendering.mesh_render_data import _extract_skinning, node_world_matrix

    root = ModelNode(name="bodyroot")
    headhook = ModelNode(name="headhook", parent=root)
    headhook.position = (0.0, 0.0, 1.5)
    root.children.append(headhook)
    body = KotorModel(name="Body", root_node=root)
    head_root = ModelNode(name="headroot")
    head_root.position = (0.0, 0.0, -1.5)
    head_mesh = ModelNode(name="head", parent=head_root, flags=0x61, vertices=[(0.0, 0.0, 0.25)], faces=[(0, 0, 0)])
    head_mesh.bone_map = ["head_g"]
    head_mesh.skin_data = [object()]
    head_root.children.append(head_mesh)
    head = KotorModel(name="Head", root_node=head_root)
    window = SimpleNamespace()
    window._find_model_node = MethodType(QtGhostRiggerMainWindow._find_model_node, window)
    window._reset_bas_model_node_traversal = MethodType(QtGhostRiggerMainWindow._reset_bas_model_node_traversal, window)
    window._prepare_bas_layer_root = MethodType(QtGhostRiggerMainWindow._prepare_bas_layer_root, window)
    window._tag_bas_attachment_subtree = MethodType(QtGhostRiggerMainWindow._tag_bas_attachment_subtree, window)

    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, head, "headhook", slot="head") is True

    attached_root = headhook.children[-1]
    assert attached_root.position == pytest.approx((0.0, 0.0, 0.0))
    assert attached_root._gr_bas_socket_name == "headhook"
    matrix = node_world_matrix(attached_root)
    assert matrix[2, 3] == pytest.approx(1.5)
    attached_mesh = attached_root.children[0]
    skinning = _extract_skinning(attached_mesh, 1, skeleton_id=id(body))
    assert skinning.is_skinned is False


def test_bas_head_skin_uses_attachment_root_local_bind_space_when_weapon_is_added() -> None:
    from types import MethodType

    import numpy as np
    import pytest

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow
    from src.adapters.rendering.mesh_render_data import _extract_node_arrays

    root = ModelNode(name="bodyroot")
    headhook = ModelNode(name="headhook", parent=root)
    headhook.position = (0.0, 0.0, 10.0)
    rhand = ModelNode(name="rhand", parent=root)
    rhand.position = (1.0, 0.0, 1.0)
    root.children.extend([headhook, rhand])
    body = KotorModel(name="Body", root_node=root)

    head_root = ModelNode(name="headroot")
    head_mesh = ModelNode(
        name="head",
        parent=head_root,
        flags=0x61,
        vertices=[(0.0, 0.0, -2.0), (0.0, 0.5, -1.5), (0.25, 0.0, -1.0)],
        faces=[(0, 1, 2)],
    )
    head_mesh.position = (0.0, 0.0, 2.0)
    head_mesh.bone_map = ["head_g"]
    head_mesh.skin_data = [object(), object(), object()]
    head_root.children.append(head_mesh)
    head = KotorModel(name="Head", root_node=head_root)

    weapon_root = ModelNode(name="weaponroot")
    weapon_mesh = ModelNode(name="weaponmesh", parent=weapon_root, flags=0x20, vertices=[(0, 0, 0)], faces=[(0, 0, 0)])
    weapon_root.children.append(weapon_mesh)
    weapon = KotorModel(name="Weapon", root_node=weapon_root)

    window = SimpleNamespace()
    window._find_model_node = MethodType(QtGhostRiggerMainWindow._find_model_node, window)
    window._reset_bas_model_node_traversal = MethodType(QtGhostRiggerMainWindow._reset_bas_model_node_traversal, window)
    window._prepare_bas_layer_root = MethodType(QtGhostRiggerMainWindow._prepare_bas_layer_root, window)
    window._tag_bas_attachment_subtree = MethodType(QtGhostRiggerMainWindow._tag_bas_attachment_subtree, window)

    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, head, "headhook", slot="head") is True
    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, body, weapon, "rhand", slot="right_weapon") is True

    attached_head_mesh = headhook.children[-1].children[0]
    positions, _normals, _uvs0, _uvs1, _indices, _bones, _weights, world_matrix = _extract_node_arrays(attached_head_mesh)

    np.testing.assert_allclose(
        positions,
        np.asarray([(0.0, 0.0, 0.0), (0.0, 0.5, 0.5), (0.25, 0.0, 1.0)], dtype=np.float32),
        atol=1e-6,
    )
    assert world_matrix[2, 3] == pytest.approx(10.0)
    assert float(positions[:, 2].min()) >= -1e-6


def test_moderngl_bas_head_skin_uses_root_local_vbo_and_socket_draw_matrix() -> None:
    import inspect

    import numpy as np
    import pytest

    from src.adapters.rendering import moderngl_renderer_impl as gpu_renderer_impl
    from src.adapters.rendering.moderngl_resources import _build_vbo_data
    from src.core.geometry.model_data import ModelNode
    from src.math.gpu_math import (
        _bas_attachment_local_transform_np,
        _mat4_from_pos_quat_scale,
    )

    headhook = ModelNode(name="headhook")
    headhook.position = (0.0, 0.0, 10.0)
    head_root = ModelNode(name="headroot", parent=headhook)
    head_root._gr_bas_attachment_root = True
    head_root._gr_bas_attachment_layer = True
    head_root._gr_bas_socket_name = "headhook"
    headhook.children.append(head_root)
    head_mesh = ModelNode(
        name="head",
        parent=head_root,
        flags=0x61,
        vertices=[(0.0, 0.0, -2.0), (0.0, 0.5, -1.5), (0.25, 0.0, -1.0)],
        faces=[(0, 1, 2)],
    )
    head_mesh.position = (0.0, 0.0, 2.0)
    head_mesh._gr_bas_attachment_layer = True
    head_mesh._gr_bas_attachment_root_ref = head_root
    head_mesh.bone_map = ["head_g"]
    head_mesh.skin_data = [object(), object(), object()]
    head_root.children.append(head_mesh)

    local_wp, local_wo = _bas_attachment_local_transform_np(head_mesh, head_root)
    vdata, _idx = _build_vbo_data(
        head_mesh,
        local_wp,
        local_wo,
        apply_skin_node_transform_for_bind=True,
    )
    assert vdata is not None
    np.testing.assert_allclose(
        vdata[:, 0:3],
        np.asarray([(0.0, 0.0, 0.0), (0.0, 0.5, 0.5), (0.25, 0.0, 1.0)], dtype=np.float32),
        atol=1e-6,
    )

    draw_matrix = _mat4_from_pos_quat_scale(headhook.position, headhook.rotation, (1.0, 1.0, 1.0))
    assert draw_matrix[2, 3] == pytest.approx(10.0)
    drawn = np.asarray([draw_matrix @ np.asarray([*row[:3], 1.0]) for row in vdata], dtype=np.float32)
    np.testing.assert_allclose(
        drawn[:, 0:3],
        np.asarray([(0.0, 0.0, 10.0), (0.0, 0.5, 10.5), (0.25, 0.0, 11.0)], dtype=np.float32),
        atol=1e-6,
    )
    source = inspect.getsource(gpu_renderer_impl)
    assert "if _skin_can_lbs:" in source
    assert "BAS attachment skins are socket followers" in source


def test_bas_model_recipe_preserves_body_layers_sockets_and_resrefs() -> None:
    from src.systems.bas.model_recipe import build_bas_model_recipe

    body = SimpleNamespace(name="P_CarthBB", _gr_source_resref="p_carthbb", _gr_source_game="K1", supermodel="S_Male02")
    head = SimpleNamespace(name="pmha01", _gr_source_resref="pmha01", _gr_source_game="K1")
    weapon = SimpleNamespace(name="w_blstrpstl_001", _gr_source_resref="w_blstrpstl_001", _gr_source_game="K1")
    mask = SimpleNamespace(name="i_mask_001", _gr_source_resref="i_mask_001", _gr_source_game="K1")
    belt = SimpleNamespace(name="i_belt_001", _gr_source_resref="i_belt_001", _gr_source_game="K1")

    recipe = build_bas_model_recipe(
        body_model=body,
        attachment_models={"head": head, "mask": mask, "belt": belt, "right_weapon": weapon},
        attachment_resrefs={"head": "pmha01", "mask": "i_mask_001", "belt": "i_belt_001", "right_weapon": "w_blstrpstl_001"},
        attachment_transforms={
            "head": {"position": [0.0, 0.0, 1.25], "rotation": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
            "right_weapon": {"position": [0.1, -0.2, 0.3], "rotation": [0.0, 0.0, 0.707, 0.707], "scale": [1.0, 1.0, 1.0]},
        },
        game="K1",
        build_name="Carth Test Build",
    )

    layers = {layer["slot"]: layer for layer in recipe["layers"]}
    assert recipe["schema"] == "ghostrigger.bas.model"
    assert recipe["recipe_id"] == "carth_test_build"
    assert recipe["display_name"] == "Carth Test Build"
    assert recipe["body"]["resref"] == "p_carthbb"
    assert recipe["body"]["supermodel"] == "S_Male02"
    assert layers["body"]["state"] == "base"
    assert layers["head"]["state"] == "attached"
    assert layers["head"]["socket"] == "headhook"
    assert layers["head"]["transform"]["position"] == [0.0, 0.0, 1.25]
    assert layers["mask"]["resref"] == "i_mask_001"
    assert layers["mask"]["socket"] == "MaskHook"
    assert layers["belt"]["resref"] == "i_belt_001"
    assert layers["belt"]["socket"] == "pelvis_g"
    assert layers["right_weapon"]["resref"] == "w_blstrpstl_001"
    assert layers["right_weapon"]["socket"] == "rhand"
    assert layers["right_weapon"]["transform"]["rotation"] == [0.0, 0.0, 0.707, 0.707]
    assert layers["left_hand"]["state"] == "socket"
    assert layers["left_weapon"]["state"] == "empty"
    assert recipe["mode"] == "headless_body"
    assert recipe["runtime"]["attachment_transform_mode"] == "socket_follower"


def test_main_window_saves_bas_model_recipe_into_system_models_dir(tmp_path) -> None:
    import json
    from types import MethodType

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    body = SimpleNamespace(name="P_CarthBB", _gr_source_resref="p_carthbb", _gr_source_game="K1")
    head = SimpleNamespace(name="pmha01", _gr_source_resref="pmha01", _gr_source_game="K1")
    window = SimpleNamespace(
        app_root=tmp_path,
        _current_game="K1",
        _bas_attachments={"head": head},
        _bas_attachment_resrefs={"head": "pmha01"},
        _infer_game_from_model=lambda _model: "K1",
    )
    window._save_bas_model_recipe = MethodType(QtGhostRiggerMainWindow._save_bas_model_recipe, window)

    path = window._save_bas_model_recipe(body)

    assert path == tmp_path / "src" / "systems" / "bas" / "models" / "k1_p_carthbb_pmha01.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["body"]["resref"] == "p_carthbb"
    assert data["attachments"] == {"head": "pmha01"}
    assert data["layers"][1]["socket"] == "headhook"
    assert data["layers"][1]["transform"]["position"] == [0.0, 0.0, 0.0]


def test_main_window_loads_bas_recipe_as_composed_preview_model(tmp_path) -> None:
    import json
    from types import MethodType

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    body = SimpleNamespace(name="P_CarthBB", _gr_source_resref="p_carthbb", _gr_source_game="K1")
    head = SimpleNamespace(name="pmha01", _gr_source_resref="pmha01", _gr_source_game="K1")
    recipe = {
        "schema": "ghostrigger.bas.model",
        "version": 1,
        "game": "K1",
        "display_name": "Carth BAS Named",
        "body": {"resref": "p_carthbb", "name": "P_CarthBB", "game": "K1"},
        "layers": [
            {"slot": "body", "state": "base", "resref": "p_carthbb"},
            {
                "slot": "head",
                "state": "attached",
                "resref": "pmha01",
                "game": "K1",
                "socket": "headhook",
                "transform": {"position": [0.0, 0.0, 1.25], "rotation": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]},
            },
        ],
    }
    path = tmp_path / "carth_bas_named.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    calls = []
    manager = SimpleNamespace(load_model=lambda resref, game: {"p_carthbb": body, "pmha01": head}[resref])
    timer = SimpleNamespace(stop=lambda: calls.append("stop"))
    panel = SimpleNamespace(
        set_body_model=lambda model: calls.append(("body", model)),
        set_slot_model=lambda slot, model=None, resref="": calls.append(("slot", slot, resref)),
        clear_slot_model=lambda slot: calls.append(("clear", slot)),
        set_status=lambda message: calls.append(("status", message)),
    )
    window = SimpleNamespace(
        _get_resource_manager=lambda: manager,
        _animation_timer=timer,
        _retarget_timer=timer,
        _animation_engine=None,
        _animation_last_tick=None,
        _retarget_engine=None,
        _retarget_last_tick=None,
        _bas_attachments={},
        _bas_attachment_resrefs={},
        _bas_attachment_transforms={},
        _add_loaded_model_to_scene=lambda model, label: calls.append(("scene", model, label)),
        _rebuild_bas_preview=lambda: calls.append("rebuild") or "BAS preview updated.",
        body_attachment_panel=panel,
        _load_animation_panel_model=lambda model: calls.append(("animations", model)),
        animations_panel=object(),
        _populate_animation_library_from_current_model=lambda: calls.append("library"),
        _log=lambda message, kind="info": calls.append(("log", kind, message)),
    )
    window._load_bas_model_recipe_from_path = MethodType(QtGhostRiggerMainWindow._load_bas_model_recipe_from_path, window)

    result = window._load_bas_model_recipe_from_path(path)

    assert result is None
    assert window._current_model is body
    assert window._bas_body_model is body
    assert window._bas_attachments == {"head": head}
    assert window._bas_attachment_resrefs == {"head": "pmha01"}
    assert window._bas_attachment_transforms["head"]["position"] == [0.0, 0.0, 1.25]
    assert window._bas_active_build_name == "Carth BAS Named"
    assert ("scene", body, "K1:p_carthbb") in calls
    assert "rebuild" in calls


def test_bas_resets_stale_camera_node_wrapper_before_attaching_layers() -> None:
    import copy

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.core.camera.camera_manager import CameraManager
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    root = ModelNode(name="bodyroot")
    lhand = ModelNode(name="lhand", parent=root)
    root.children.append(lhand)
    body = KotorModel(name="Body", root_node=root)
    manager = CameraManager()
    manager.model = body
    manager._install_all_nodes_wrapper()

    preview = copy.deepcopy(body)
    weapon_root = ModelNode(name="weaponroot")
    weapon_mesh = ModelNode(name="weaponmesh", parent=weapon_root, flags=0x20, vertices=[(0, 0, 0)], faces=[(0, 0, 0)])
    weapon_root.children.append(weapon_mesh)
    weapon = KotorModel(name="Weapon", root_node=weapon_root)
    window = SimpleNamespace()
    window._find_model_node = MethodType(QtGhostRiggerMainWindow._find_model_node, window)
    window._reset_bas_model_node_traversal = MethodType(QtGhostRiggerMainWindow._reset_bas_model_node_traversal, window)
    window._prepare_bas_layer_root = MethodType(QtGhostRiggerMainWindow._prepare_bas_layer_root, window)
    window._tag_bas_attachment_subtree = MethodType(QtGhostRiggerMainWindow._tag_bas_attachment_subtree, window)

    QtGhostRiggerMainWindow._reset_bas_model_node_traversal(window, preview)
    assert QtGhostRiggerMainWindow._attach_bas_item_to_preview(window, preview, weapon, "lhand") is True
    assert "weaponmesh" in {node.name for node in preview.all_nodes()}
    assert "weaponmesh" in {node.name for node in type(preview).all_nodes(preview)}

    manager.set_model(preview)

    assert "weaponmesh" in {node.name for node in preview.all_nodes()}


def test_bas_preview_targets_body_scene_object_not_arbitrary_selection() -> None:
    from types import MethodType

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    body_model = SimpleNamespace(name="Body")
    previous_preview = SimpleNamespace(name="Body_bas_old")
    selected_other = SimpleNamespace(selected=True, metadata={"_runtime_model": SimpleNamespace(name="Other")})
    body_object = SimpleNamespace(selected=False, metadata={"_runtime_model": body_model})
    scene_manager = SimpleNamespace(
        active_scene=SimpleNamespace(objects=[selected_other, body_object]),
        get_selected_objects=lambda: [selected_other],
    )
    window = SimpleNamespace(
        scene_manager=scene_manager,
        _bas_body_model=body_model,
        _current_model=body_model,
        _bas_preview_model=previous_preview,
    )

    target = QtGhostRiggerMainWindow._bas_target_scene_object(window, previous_preview=previous_preview)

    assert target is body_object


def test_bas_preview_applies_as_layer_and_restores_animation_pose() -> None:
    from types import MethodType

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    calls = []
    body_model = SimpleNamespace(name="Body")
    preview = SimpleNamespace(name="Body_bas")
    selected_other = SimpleNamespace(selected=True, metadata={"_runtime_model": SimpleNamespace(name="Other")})
    body_object = SimpleNamespace(selected=False, metadata={"_runtime_model": body_model})
    scene_manager = SimpleNamespace(
        active_scene=SimpleNamespace(objects=[selected_other, body_object]),
        get_selected_objects=lambda: [selected_other],
        mark_dirty=lambda: calls.append("dirty"),
    )

    class Viewport:
        def set_animation_pose(self, pose, name="", time=0.0, length=0.0):
            calls.append(("pose", pose, name, time, length))

        def set_animation_playback_active(self, active, reason=""):
            calls.append(("active", active, reason))

        def refresh_view(self):
            calls.append("refresh_view")

    class Engine:
        current_animation = SimpleNamespace(name="walk", length=1.5)
        current_time = 0.5
        is_playing = True

        def evaluate(self, t=0.0):
            calls.append(("evaluate", t))
            return "pose-at-current-time"

    window = SimpleNamespace(
        scene_manager=scene_manager,
        viewport=Viewport(),
        _bas_body_model=body_model,
        _current_model=body_model,
        _bas_preview_model=None,
        _bas_attachments={"head": object(), "right_weapon": object()},
        _bas_attachment_resrefs={"head": "pmhc01", "right_weapon": "w_lghtsbr_001"},
        _animation_engine=Engine(),
        _refresh_scene_view=lambda: calls.append("refresh_scene"),
    )
    window._bas_target_scene_object = MethodType(QtGhostRiggerMainWindow._bas_target_scene_object, window)
    window._restore_bas_animation_pose_after_viewport_refresh = MethodType(
        QtGhostRiggerMainWindow._restore_bas_animation_pose_after_viewport_refresh,
        window,
    )
    window._request_bas_viewport_refresh = MethodType(QtGhostRiggerMainWindow._request_bas_viewport_refresh, window)
    window._sync_bas_body_animation_engine = MethodType(QtGhostRiggerMainWindow._sync_bas_body_animation_engine, window)

    QtGhostRiggerMainWindow._apply_bas_preview_to_viewport(window, preview)

    assert selected_other.metadata["_runtime_model"].name == "Other"
    assert body_object.metadata["_runtime_model"] is preview
    assert body_object.metadata["_runtime_bas_body_model"] is body_model
    assert body_object.metadata["_runtime_bas_preview_model"] is preview
    assert body_object.metadata["body_attachment_system"]["attachments"] == {
        "head": "pmhc01",
        "right_weapon": "w_lghtsbr_001",
    }
    assert body_object.metadata["body_attachment_system"]["layers"] == [
        {"slot": "head", "resref": "pmhc01", "enabled": True},
        {"slot": "right_weapon", "resref": "w_lghtsbr_001", "enabled": True},
    ]
    assert "refresh_scene" in calls
    assert ("evaluate", 0.5) in calls
    assert ("pose", "pose-at-current-time", "walk", 0.5, 1.5) in calls
    assert ("active", True, "") in calls
    assert "refresh_view" in calls


def test_animation_source_model_keeps_bas_body_as_animation_owner() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    body = SimpleNamespace(name="Body")
    preview = SimpleNamespace(name="Body_bas")
    window = SimpleNamespace(
        _bas_preview_model=preview,
        _bas_body_model=body,
        _current_model=body,
        animations_panel=SimpleNamespace(selected_animation_source=lambda: "body"),
    )
    window._animation_source_key = MethodType(QtGhostRiggerMainWindow._animation_source_key, window)

    assert QtGhostRiggerMainWindow._animation_source_model(window) is body


def test_bas_animation_engine_returns_to_body_without_losing_time() -> None:
    from src.core.animation.animation_engine import AnimationEngine
    from src.core.geometry.model_data import Animation, KotorModel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    body = KotorModel(name="Body")
    preview = KotorModel(name="Body_bas")
    body.animations = [Animation(name="walk", length=2.0)]
    preview.animations = [Animation(name="walk", length=2.0)]
    engine = AnimationEngine(preview)
    assert engine.play("walk", loop=True, blend=False) is True
    engine.seek(0.75)

    @contextmanager
    def resolution_context(_model, _game, _supermodel=""):
        yield

    window = SimpleNamespace(
        _animation_engine=engine,
        _animation_loop=True,
        animations_panel=SimpleNamespace(selected_animation_source=lambda: "body"),
        _get_resource_manager=lambda: None,
        _animation_inheritance_game=lambda _model: "K1",
        _animation_inheritance_supermodel=lambda _model: "",
        _animation_resolution_context=resolution_context,
        _apply_animation_resolution_game=lambda _model, _game: None,
        _current_model=body,
        _bas_body_model=body,
    )
    window._animation_source_key = MethodType(QtGhostRiggerMainWindow._animation_source_key, window)

    QtGhostRiggerMainWindow._sync_bas_body_animation_engine(window, preview)

    assert window._animation_engine.model is body
    assert window._animation_engine.current_animation.name == "walk"
    assert window._animation_engine.current_time == pytest.approx(0.75)
    assert window._animation_engine.is_playing is True


def test_bas_layer_change_does_not_reload_body_animation_panel() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    calls = []
    body = SimpleNamespace(name="Body")
    window = SimpleNamespace(
        _bas_body_model=body,
        _current_model=body,
        animations_panel=SimpleNamespace(
            selected_animation_source=lambda: "body",
            selected_animation=lambda: "pause2",
        ),
        _load_animation_panel_model=lambda model, select_name="": calls.append((model, select_name)),
    )
    window._animation_source_key = MethodType(QtGhostRiggerMainWindow._animation_source_key, window)

    QtGhostRiggerMainWindow._refresh_bas_animation_panel_after_layer_change(window, "right_weapon")

    assert calls == []


def test_bas_layer_change_refreshes_matching_attachment_animation_panel() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    calls = []
    body = SimpleNamespace(name="Body")
    window = SimpleNamespace(
        _bas_body_model=body,
        _current_model=body,
        animations_panel=SimpleNamespace(
            selected_animation_source=lambda: "attachment",
            selected_animation=lambda: "activate",
        ),
        _load_animation_panel_model=lambda model, select_name="": calls.append((model, select_name)),
    )
    window._animation_source_key = MethodType(QtGhostRiggerMainWindow._animation_source_key, window)

    QtGhostRiggerMainWindow._refresh_bas_animation_panel_after_layer_change(window, "right_weapon")

    assert calls == [(body, "activate")]


def test_bas_scene_object_activation_preserves_body_animation_panel() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    calls = []
    body = SimpleNamespace(name="Body")
    preview = SimpleNamespace(name="Body_bas")
    obj = SimpleNamespace(
        metadata={
            "_runtime_model": preview,
            "_runtime_bas_body_model": body,
            "_runtime_bas_preview_model": preview,
            "body_attachment_system": {"active": True},
        }
    )
    window = SimpleNamespace(
        _bas_body_model=body,
        _bas_preview_model=preview,
        _current_model=None,
        animations_panel=SimpleNamespace(selected_animation_source=lambda: "body"),
        animation_retarget_panel=object(),
        _load_animation_panel_model=lambda model, select_name="": calls.append(("animations", model, select_name)),
    )
    window._animation_source_key = MethodType(QtGhostRiggerMainWindow._animation_source_key, window)

    QtGhostRiggerMainWindow._activate_scene_object_model(window, obj)

    assert window._current_model is body
    assert calls == []


def test_bas_ignores_anatomical_hand_placeholders() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    calls = []
    window = SimpleNamespace(
        _show_workspace_dock=lambda name: calls.append(("dock", name)),
        body_attachment_panel=SimpleNamespace(set_status=lambda text: calls.append(("status", text))),
        _bas_attachments={},
        _bas_attachment_resrefs={},
    )

    QtGhostRiggerMainWindow._handle_bas_attach_requested(window, "left_hand", "w_vbroswrd_001")
    QtGhostRiggerMainWindow._handle_bas_clear_requested(window, "right_hand")

    assert calls == [("status", "Hand slots are sockets; attach items through L. Weapon or R. Weapon.")]
    assert window._bas_attachments == {}


def test_animation_selection_previews_first_frame_without_starting_playback() -> None:
    from types import SimpleNamespace

    from src.core.geometry.model_data import Animation, KotorModel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    model = KotorModel(name="PreviewModel")
    model.animations = [Animation(name="pause1", length=1.25)]
    calls = []

    class Viewport:
        def set_animation_pose(self, pose, name="", time=0.0, length=0.0):
            calls.append(("pose", pose, name, time, length))

        def set_animation_playback_active(self, active, reason=""):
            calls.append(("active", active, reason))

    class Timer:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    @contextmanager
    def resolution_context(_model, _game, _supermodel=""):
        yield

    window = SimpleNamespace(
        _animation_engine=None,
        _animation_timer=Timer(),
        _animation_last_tick="old",
        _animation_status_last_update=12.0,
        viewport=Viewport(),
        _get_resource_manager=lambda: None,
        _log=lambda *_args, **_kwargs: None,
        _animation_inheritance_game=lambda _model: "K1",
        _animation_inheritance_supermodel=lambda _model: "",
        _animation_resolution_context=resolution_context,
        _apply_animation_resolution_game=lambda _model, _game: None,
    )

    assert QtGhostRiggerMainWindow._preview_selected_animation_first_frame(window, model, "pause1") is True

    pose_call = calls[0]
    assert pose_call[0] == "pose"
    assert pose_call[2:] == ("pause1", 0.0, 1.25)
    assert calls[1] == ("active", False, "")
    assert window._animation_timer.stopped is True
    assert window._animation_engine.is_playing is False
    assert window._animation_last_tick is None
    assert window._animation_status_last_update == 0.0


def test_qt_animations_panel_exposes_bake_and_binary_export_actions() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    labels = {button.text() for button in panel.findChildren(QtWidgets.QPushButton)}

    assert "Bake Animation" in labels
    assert "Export Binary MDL" in labels


def test_main_window_moves_rig_panel_to_modules_window() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_rig_panel import QtRigWindow
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert 'right_tabs.addTab(self.rig_panel' not in source
    assert "self.rig_window = QtRigWindow(self)" in source
    assert "self.rig_panel = self.rig_window.panel" in source

    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    assert "self.rig_window_action" in actions_source
    assert "self._open_rig_window" in actions_source

    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    assert "modules_menu.addAction(self.rig_window_action)" in menu_source

    open_source = inspect.getsource(QtGhostRiggerMainWindow._open_rig_window)
    assert "window.show()" in open_source
    assert "window.raise_()" in open_source
    assert QtRigWindow.__name__ == "QtRigWindow"
    assert hasattr(QtRigWindow, "rigActionRequested")


def test_main_window_exposes_module_meshes_as_detachable_dock() -> None:
    import inspect
    from pathlib import Path

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    refresh_source = inspect.getsource(QtGhostRiggerMainWindow._refresh_all)

    assert "self.properties_panel = QtPropertiesPanel(self, module_browser_enabled=False)" in layout_source
    assert "self.module_geometry_panel = QtPropertiesPanel(self)" in layout_source
    assert "self.module_geometry_panel.set_module_browser_only(True)" in layout_source
    assert '"module_meshes"' in layout_source
    assert "self.module_meshes_panel_action" in actions_source
    assert 'self._icon("module_meshes")' in actions_source
    assert "modules_menu.addAction(self.module_meshes_panel_action)" in menu_source
    assert "self.module_geometry_panel.show_model(self._active_viewport_model())" in refresh_source
    assert "self.viewport.meshSelectionChanged.connect(self.module_geometry_panel.select_module_meshes)" in layout_source
    assert "meshHovered.connect(self.module_geometry_panel" not in layout_source
    assert (Path("src/gui/icons/module_meshes.svg")).exists()
    assert hasattr(QtPropertiesPanel, "set_module_browser_only")


def test_main_window_exposes_sprite_materials_as_rendering_dock() -> None:
    import inspect
    from pathlib import Path

    from src.gui.qt_lib.panels.qt_sprite_material_panel import QtSpriteMaterialPanel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    refresh_source = inspect.getsource(QtGhostRiggerMainWindow._refresh_all)
    changed_source = inspect.getsource(QtGhostRiggerMainWindow._on_sprite_materials_changed)
    persistence_source = inspect.getsource(QtGhostRiggerMainWindow._apply_sprite_material_overrides)
    scene_source = inspect.getsource(QtGhostRiggerMainWindow._refresh_scene_view)

    assert "self.sprite_materials_panel = QtSpriteMaterialPanel(self)" in layout_source
    assert '"sprite_materials"' in layout_source
    assert "self.sprite_materials_panel_action" in actions_source
    assert 'self._icon("sprite_materials")' in actions_source
    assert "modules_menu.addAction(self.sprite_materials_panel_action)" in menu_source
    assert "self.sprite_materials_panel.set_model(self._active_viewport_model())" in refresh_source
    assert "self.sprite_materials_panel.spriteRenderChanged.connect(self._on_sprite_materials_changed)" in layout_source
    assert "renderer.invalidate_node_cache()" in changed_source
    assert "self.viewport.refresh_view()" in changed_source
    assert "self._save_sprite_material_overrides()" in changed_source
    assert "sprite_material_overrides.json" in inspect.getsource(QtGhostRiggerMainWindow._sprite_persistence_path)
    assert "setattr(node, \"_gr_sprite_alpha_source\"" in persistence_source
    assert "self._apply_sprite_material_overrides(model)" in scene_source
    assert (Path("src/gui/icons/sprite_materials.svg")).exists()
    assert hasattr(QtSpriteMaterialPanel, "spriteRenderChanged")


def test_main_window_exposes_adjust_pivot_in_modules_menu() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)

    assert "self.adjust_pivot_panel = AdjustPivotPanel(self)" in layout_source
    assert '"adjust_pivot"' in layout_source
    assert "self.adjust_pivot_panel_action" in actions_source
    assert 'self._show_workspace_dock("adjust_pivot")' in actions_source
    assert "modules_menu.addAction(self.adjust_pivot_panel_action)" in menu_source


def test_adjust_pivot_mode_buttons_are_persistent_toggles() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.adjust_pivot_panel import AdjustPivotPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = AdjustPivotPanel()
    try:
        panel.set_selection_state(1, locked=False, hierarchy_available=True)
        emitted = []
        panel.pivotModeChanged.connect(emitted.append)

        pivot_button = panel._mode_buttons["affect_pivot_only"]
        object_button = panel._mode_buttons["affect_object_only"]
        hierarchy_button = panel._mode_buttons["affect_hierarchy_only"]

        pivot_button.click()
        assert pivot_button.isChecked()
        assert not object_button.isChecked()
        assert emitted[-1] == "affect_pivot_only"

        hierarchy_button.click()
        assert hierarchy_button.isChecked()
        assert not pivot_button.isChecked()
        assert emitted[-1] == "affect_hierarchy_only"
    finally:
        panel.close()


def test_adjust_pivot_mode_starts_object_only_for_normal_gizmo_drags() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    mode_source = inspect.getsource(QtGhostRiggerMainWindow._set_pivot_edit_mode)

    assert 'self.settings_data["last_pivot_edit_mode"] = "affect_object_only"' in layout_source
    assert 'self.viewport.set_pivot_edit_mode("affect_object_only")' in layout_source
    assert "save_settings(self.settings_path, self.settings_data)" not in mode_source


def test_regular_properties_panel_can_omit_module_mesh_tab() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel(module_browser_enabled=False)
    tab_names = [panel.tabs.tabText(index) for index in range(panel.tabs.count())]

    assert tab_names == ["General"]
    assert panel.module_tab is None
    panel.select_module_meshes([])
    panel.refresh_module_mesh_rows()


def test_module_mesh_panel_omits_redundant_open_window_control() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import inspect

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()

    assert not hasattr(panel, "open_module_meshes_window_button")
    panel_source = inspect.getsource(QtPropertiesPanel._show_module_browser_context_menu)
    assert "Open Module Meshes Window" not in panel_source
    assert "moduleMeshesWindowRequested.emit" not in panel_source


def test_qt_overflow_helpers_scroll_dense_toolbar_rows() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.assets.qt_theme import make_horizontal_overflow_area, make_scrollable_panel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    strip = QtWidgets.QWidget()
    strip.setMinimumWidth(900)
    strip_scroll = make_horizontal_overflow_area(strip, "TestToolbarScroll", height=40)
    strip_scroll.resize(240, 40)

    assert strip_scroll.widget() is strip
    assert strip_scroll.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded
    assert strip_scroll.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarAlwaysOff
    assert strip.minimumWidth() >= 900

    panel = QtWidgets.QWidget()
    panel_scroll = make_scrollable_panel(panel, "TestDockScroll")

    assert panel_scroll.widget() is panel
    assert panel_scroll.widgetResizable() is True
    assert panel_scroll.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded
    assert panel_scroll.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded


def test_main_window_command_bar_is_fixed_and_docks_are_scrollable() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    command_source = inspect.getsource(QtGhostRiggerMainWindow._make_command_bar)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    button_source = inspect.getsource(QtGhostRiggerMainWindow._tool_button)
    visibility_source = inspect.getsource(QtGhostRiggerMainWindow._on_detachable_panel_visibility)
    dock_source = inspect.getsource(QtGhostRiggerMainWindow._create_detachable_panel)
    init_source = inspect.getsource(QtGhostRiggerMainWindow.__init__)
    top_level_source = inspect.getsource(QtGhostRiggerMainWindow._on_detachable_panel_top_level_changed)
    show_detachable_source = inspect.getsource(QtGhostRiggerMainWindow._show_detachable_panel)
    new_host_source = inspect.getsource(QtGhostRiggerMainWindow._move_detachable_panel_to_new_host)

    assert "CommandBarScroll" not in command_source
    assert "host_layout.addWidget(bar, 1)" in command_source
    assert "visual_profile_combo" in command_source
    assert "make_scrollable_panel(widget" in dock_source
    assert 'f"{key}DockScroll"' in dock_source
    assert "QtWidgets.QMainWindow.AllowNestedDocks" in init_source
    assert "QtWidgets.QMainWindow.AllowTabbedDocks" in init_source
    assert "QtWidgets.QMainWindow.GroupedDragging" in init_source
    assert "QtWidgets.QDockWidget.DockWidgetFloatable" in dock_source
    assert "_promote_detached_panel_window" not in top_level_source
    assert "dock.setFloating(True)" in show_detachable_source
    assert "_promote_detached_panel_window" not in show_detachable_source
    assert "QtFloatingDockHost(self, dock.windowTitle(), key)" in new_host_source


def test_viewport_and_character_builder_toolbars_are_scrollable() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    viewport_source = inspect.getsource(QtViewportWidget._build)
    builder_source = inspect.getsource(QtCharacterBuilderWindow._build_toolbars)
    bottom_source = inspect.getsource(QtCharacterBuilderWindow._build_bottom_strip)

    assert "make_horizontal_overflow_area(" in viewport_source
    assert '"ViewportToolbarScroll"' in viewport_source
    assert "make_horizontal_overflow_area(" in builder_source
    assert '"CharacterBuilderToolbarScroll"' in builder_source
    assert "make_scrollable_panel(self.bottom_strip" in bottom_source


def test_main_window_moves_utility_tabs_to_tools_windows() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_diagnostics_panel import QtDiagnosticsPanel, QtDiagnosticsWindow
    from src.gui.qt_lib.panels.qt_texture_panel import QtTextureToolWindow
    from src.gui.qt_lib.windows.qt_blueprint_editor import QtBlueprintEditorWindow
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    for tab_expr in (
        "right_tabs.addTab(self.texture_panel",
        "right_tabs.addTab(self.normal_map_panel",
        "right_tabs.addTab(self.diagnostics_panel",
        "right_tabs.addTab(self.blueprint_panel",
    ):
        assert tab_expr not in source
    assert "self.texture_tool_window = QtTextureToolWindow(self)" in source
    assert "self.diagnostics_panel = QtDiagnosticsPanel(self._get_model, self)" in source
    assert "self.diagnostics_dock = self._create_detachable_panel(" in source
    assert "self.blueprint_window = QtBlueprintEditorWindow(self)" in source
    assert "self.texture_panel = self.texture_tool_window.texture_panel" in source
    assert "self.normal_map_panel = self.texture_tool_window.normal_map_panel" in source
    assert "self.blueprint_panel = self.blueprint_window.panel" in source

    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    assert "self.texture_tool_action" in actions_source
    assert "self.blueprint_editor_action" in actions_source
    assert "self._open_texture_tool_window" in actions_source
    assert "self._open_blueprint_editor_window" in actions_source

    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    assert "tools_menu.addAction(self.diag_action)" in menu_source
    assert "tools_menu.addAction(self.texture_tool_action)" in menu_source
    assert "tools_menu.addAction(self.blueprint_editor_action)" in menu_source
    assert "Legacy Tk" not in actions_source
    assert "Legacy Tk" not in menu_source
    assert "_launch_legacy_tk" not in inspect.getsource(QtGhostRiggerMainWindow)

    model_menu_block = menu_source.split("mdlops_menu = self.menuBar().addMenu", 1)[0]
    assert "self.diag_action" not in model_menu_block

    for method_name in ("_open_texture_tool_window", "_open_blueprint_editor_window"):
        open_source = inspect.getsource(getattr(QtGhostRiggerMainWindow, method_name))
        assert "window.show()" in open_source
        assert "window.raise_()" in open_source

    diagnostics_source = inspect.getsource(QtGhostRiggerMainWindow._show_diagnostics_panel)
    assert "panel.run_diagnostics(self._current_model)" in diagnostics_source
    assert 'self._show_workspace_dock("diagnostics")' in diagnostics_source

    assert QtDiagnosticsPanel.__name__ == "QtDiagnosticsPanel"
    assert QtDiagnosticsWindow.__name__ == "QtDiagnosticsWindow"
    assert QtTextureToolWindow.__name__ == "QtTextureToolWindow"
    assert QtBlueprintEditorWindow.__name__ == "QtBlueprintEditorWindow"


def test_main_window_routes_library_and_animation_library_to_content_browser() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert "self.content_browser_panel = QtContentBrowserPanel(self)" in source
    assert "self.library_panel = self.content_browser_panel" in source
    assert 'self.content_browser_dock = self._create_detachable_panel(' in source
    assert '"Content Browser"' in source
    assert '"content_browser",\n            "Content Browser",\n            self.content_browser_panel,\n            QtCore.Qt.LeftDockWidgetArea,' in source
    assert 'self.scene_dock = self._create_detachable_panel(' in source
    assert 'self.properties_dock = self._create_detachable_panel(' in source
    assert 'self.animations_dock = self._create_detachable_panel(' in source
    assert "self._stack_content_browser_under_scene()" in source
    stack_source = inspect.getsource(QtGhostRiggerMainWindow._stack_content_browser_under_scene)
    assert "self.splitDockWidget(self.scene_dock, self.content_browser_dock, QtCore.Qt.Vertical)" in stack_source
    assert "vertical_splitter.addWidget(self.viewport)" in source
    assert "left_tabs.addTab(" not in source
    assert "right_tabs.addTab(" not in source
    assert "self.animation_library_panel = self.content_browser_panel" in source
    assert "self.animation_library_combined_panel = QtAnimationLibraryCombinedPanel(" not in source
    assert "right_tabs.addTab(self.animation_library_panel" not in source
    assert "right_tabs.addTab(self.character_builder_panel" not in source
    assert "self.character_builder_panel = QtCharacterBuilderPanel" not in source

    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    assert '"Animation Library"' in actions_source
    assert 'self._show_content_browser("Animation")' in actions_source
    assert "self.content_browser_action" in actions_source
    assert "self.scene_panel_action" in actions_source
    assert "self.properties_panel_action" in actions_source
    assert "self.animation_browser_dock_action" in actions_source

    module_source = inspect.getsource(QtGhostRiggerMainWindow._handle_module_action)
    assert 'self._open_blueprint_editor_window()' in module_source
    assert 'self._show_right_tab("Blueprint")' not in module_source

    assert QtContentBrowserPanel.__name__ == "QtContentBrowserPanel"


def test_main_command_strip_groups_dock_modules_on_right_and_sizes_like_viewport() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    command_source = inspect.getsource(QtGhostRiggerMainWindow._make_command_bar)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    button_source = inspect.getsource(QtGhostRiggerMainWindow._tool_button)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._menu_button)
    visibility_source = inspect.getsource(QtGhostRiggerMainWindow._on_detachable_panel_visibility)

    assert 'layout.addWidget(self._tool_button("Scene Information", self.scene_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Properties", self.properties_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("BAS", self.body_attachment_panel_action, "body_attachment"' in command_source
    assert 'layout.addWidget(self._tool_button("Sequence Editor", self.sequence_editor_action' in command_source
    assert 'layout.addWidget(self._tool_button("Animation Browser", self.animation_browser_dock_action' in command_source
    assert 'layout.addWidget(self._tool_button("Nodes", self.nodes_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Lighting", self.lighting_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Cameras", self.camera_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Module Meshes", self.module_meshes_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Adjust Pivot", self.adjust_pivot_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("2DA Browser", self.twoda_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Resource Browser", self.resources_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Diagnostics  Ctrl+D", self.diag_action' in command_source
    assert actions_source.count("self._configure_dock_toggle_action(") >= 13
    for action_name in (
        "content_browser_action",
        "scene_panel_action",
        "properties_panel_action",
        "sequence_editor_action",
        "animation_browser_dock_action",
        "nodes_panel_action",
        "lighting_panel_action",
        "camera_panel_action",
        "module_meshes_panel_action",
        "adjust_pivot_panel_action",
        "twoda_panel_action",
        "resources_panel_action",
        "diag_action",
    ):
        assert f"self.{action_name}" in actions_source
    assert "button.setCheckable(True)" in button_source
    assert "action.toggled.connect(button.setChecked)" in button_source
    assert "self._sync_dock_toggle_action(key, visible)" in visibility_source
    workspace_source = inspect.getsource(QtGhostRiggerMainWindow._show_workspace_dock)
    tab_source = inspect.getsource(QtGhostRiggerMainWindow._tab_workspace_dock_with_visible_peer)
    assert "self._tab_workspace_dock_with_visible_peer(key, dock)" in workspace_source
    assert "self.tabifyDockWidget(anchor, dock)" in tab_source
    assert '"Anims  Ctrl+A"' not in command_source
    assert command_source.index('"New Scene  Ctrl+N"') < command_source.index('"Open Scene  Ctrl+O"')
    assert command_source.index('"Settings  F2"') < command_source.index("layout.addStretch(1)")
    assert command_source.index("layout.addStretch(1)") < command_source.index('"Scene Information"')
    assert command_source.index("layout.addStretch(1)") < command_source.index('"Animation Browser"')
    assert command_source.index('"Sequence Editor"') < command_source.index('"Animation Browser"')
    assert command_source.index('"Animation Browser"') < command_source.index('"Nodes"')
    assert "button.setFixedSize(30, 22)" in button_source
    assert "button.setIconSize(QtCore.QSize(18, 18))" in button_source
    assert "button.setFixedSize(34, 22)" in menu_source


def test_viewport_toolbar_flow_layout_centers_rows() -> None:
    import inspect

    from src.gui.qt_lib.assets.qt_theme import QtFlowLayout
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    flow_source = inspect.getsource(QtFlowLayout)
    viewport_source = inspect.getsource(QtViewportWidget._build)

    assert "horizontal_alignment" in flow_source
    assert "QtCore.Qt.AlignHCenter" in viewport_source
    assert "(max_width - current_width) // 2" in flow_source


def test_sequence_and_diagnostics_use_detachable_dock_registry() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    sequence_source = inspect.getsource(QtGhostRiggerMainWindow._show_sequence_editor_dock)
    diagnostics_source = inspect.getsource(QtGhostRiggerMainWindow._show_diagnostics_panel)
    default_area_source = inspect.getsource(QtGhostRiggerMainWindow._default_dock_area_for_key)

    assert '"sequence_editor": (1180, 720)' in layout_source
    assert '"diagnostics": (760, 560)' in layout_source
    assert "self.sequence_editor_dock = self._create_detachable_panel(" in layout_source
    assert '"sequence_editor",' in layout_source
    assert "self.diagnostics_dock = self._create_detachable_panel(" in layout_source
    assert '"diagnostics",' in layout_source
    assert 'self._show_workspace_dock("sequence_editor")' in sequence_source
    assert 'self._show_workspace_dock("diagnostics")' in diagnostics_source
    assert 'key in {"output_log", "sequence_editor"}' in default_area_source


def test_main_window_bottom_area_is_resizable_splitter() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert "vertical_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)" in source
    assert "self.vertical_splitter = vertical_splitter" in source
    assert "vertical_splitter.addWidget(self.viewport)" in source
    assert "vertical_splitter.addWidget(self.log_panel)" in source
    assert "root.addWidget(vertical_splitter, 1)" in source
    assert "main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)" not in source
    assert "root.addWidget(self.log_panel, 0)" not in source
    assert "vertical_splitter.setSizes([720, 240])" in source


def test_main_window_exposes_animation_helpers_to_python_terminal() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert "self._configure_python_terminal_context()" in layout_source

    context_source = inspect.getsource(QtGhostRiggerMainWindow._configure_python_terminal_context)
    for helper in (
        "model=self._terminal_model",
        "selected_model=self._terminal_model",
        "animation_names=self._terminal_animation_names",
        "select_animation=self._terminal_select_animation",
        "play_animation=self._terminal_play_animation",
        "stop_animation=self._terminal_stop_animation",
        "seek_animation=self._terminal_seek_animation",
        "override_animation=self._terminal_override_animation",
        "create_viewport_widget=self._terminal_create_viewport_widget",
    ):
        assert helper in context_source

    play_source = inspect.getsource(QtGhostRiggerMainWindow._terminal_play_animation)
    assert 'self._handle_animation_action("Play", anim_name)' in play_source

    override_source = inspect.getsource(QtGhostRiggerMainWindow._terminal_override_animation)
    assert "copy.deepcopy(source_anim)" in override_source
    assert "model.animations = animations" in override_source
    assert "self._load_animation_panel_model(model, select_name=target_name)" in override_source

    scaffold_source = inspect.getsource(QtGhostRiggerMainWindow._terminal_create_viewport_widget)
    assert "create_custom_viewport_widget(" in scaffold_source
    assert "Created viewport" in scaffold_source


def test_viewport_widget_scaffold_creates_focused_modules(tmp_path) -> None:
    from src.gui.viewports.viewport_core.widget_scaffold import create_custom_viewport_widget

    result = create_custom_viewport_widget("Orbit Gizmo", target_root=tmp_path)

    assert result["kind"] == "widget"
    assert result["module_name"] == "orbit_gizmo"
    assert result["class_name"] == "OrbitGizmoWidget"
    widget_path = Path(result["path"])
    assert widget_path == tmp_path / "orbit_gizmo.py"
    text = widget_path.read_text(encoding="utf-8")
    assert "class OrbitGizmoWidget(QtWidgets.QWidget)" in text
    assert "apply_ghost_theme" in text
    assert "apply_ghost_layout" in text

    with pytest.raises(FileExistsError):
        create_custom_viewport_widget("Orbit Gizmo", target_root=tmp_path)

    mixin = create_custom_viewport_widget("orbit selection", kind="mixin", target_root=tmp_path)
    mixin_text = Path(mixin["path"]).read_text(encoding="utf-8")
    assert mixin["class_name"] == "OrbitSelectionMixin"
    assert "class OrbitSelectionMixin" in mixin_text
    assert "_install_orbit_selection_hooks" in mixin_text


def test_qt_main_window_builds_baked_animation_clip() -> None:
    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    root = ModelNode(name="rootdummy")
    head = ModelNode(name="head")
    root.children.append(head)
    head.parent = root
    anim_node = ModelNode(name="head")
    anim_node.controllers = [
        {
            "type": 8,
            "name": "position",
            "columns": 3,
            "times": [0.0, 1.0],
            "values": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        }
    ]
    model = KotorModel(name="BakeTest", root_node=root)
    model.animations = [Animation(name="move", length=1.0, nodes=[anim_node])]

    baked = QtGhostRiggerMainWindow._build_baked_animation(
        SimpleNamespace(),
        model,
        "move",
        "move_baked",
        fps=2,
    )

    assert baked.name == "move_baked"
    assert len(baked.nodes) == 1
    ctrl = baked.nodes[0].controllers[0]
    assert ctrl["type"] == 8
    assert ctrl["times"] == [0.0, 0.5, 1.0]
    assert ctrl["values"] == [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [1.0, 0.0, 0.0]]


def test_mdl_porter_animation_nodes_are_serialized_as_dummy_nodes() -> None:
    from src.core.geometry.model_data import ModelNode, NodeFlags
    from src.core.mdl.mdl_porter import MDLBinaryWriter

    anim_node = ModelNode(name="robe", flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN))
    anim_node.controllers = [
        {
            "type": 20,
            "name": "orientation",
            "columns": 4,
            "times": [0.0],
            "values": [[0.0, 0.0, 0.0, 1.0]],
        }
    ]

    block = MDLBinaryWriter()._build_anim_node(anim_node, [anim_node], False, 168)

    assert int.from_bytes(block[0:2], "little") == int(NodeFlags.HEADER)


def test_mdl_porter_rebuilds_flat_animation_nodes_as_reachable_tree() -> None:
    from src.core.geometry.model_data import Animation, ModelNode
    from src.core.mdl.mdl_porter import MDLBinaryWriter

    root = ModelNode(name="root")
    pelvis = ModelNode(name="pelvis")
    head = ModelNode(name="head")
    root.children.append(pelvis)
    pelvis.parent = root
    pelvis.children.append(head)
    head.parent = pelvis

    anim_head = ModelNode(name="head")
    anim_head.controllers = [
        {
            "type": 20,
            "name": "orientation",
            "columns": 4,
            "times": [0.0],
            "values": [[0.0, 0.0, 0.0, 1.0]],
        }
    ]
    anim = Animation(name="look", nodes=[anim_head])

    nodes = MDLBinaryWriter()._animation_nodes_with_hierarchy(anim, [root, pelvis, head])

    assert [node.name for node in nodes] == ["root", "pelvis", "head"]
    assert nodes[1].parent is nodes[0]
    assert nodes[2].parent is nodes[1]
    assert nodes[2].controllers == anim_head.controllers


def test_mdl_writer_skin_palette_uses_emitted_node_indices() -> None:
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    writer = MDLBinaryWriter()
    writer._node_index_by_name = {
        "root": 0,
        "cape05_g": 14,
        "rforearm_g": 27,
    }

    assert writer._skin_bone_node_index("Cape05_g") == 14
    assert writer._skin_bone_node_index("RForeArm_G") == 27
    assert writer._skin_bone_node_index("") == -1


def test_mdl_writer_rebuilds_flat_animation_nodes_as_reachable_tree() -> None:
    from src.core.geometry.model_data import Animation, ModelNode
    from src.core.mdl.mdl_writer import MDLBinaryWriter

    root = ModelNode(name="root")
    pelvis = ModelNode(name="pelvis")
    head = ModelNode(name="head")
    root.children.append(pelvis)
    pelvis.parent = root
    pelvis.children.append(head)
    head.parent = pelvis

    anim_head = ModelNode(name="head")
    anim_head.controllers = [
        {
            "type": 20,
            "name": "orientation",
            "columns": 4,
            "times": [0.0],
            "values": [[0.0, 0.0, 0.0, 1.0]],
        }
    ]
    anim = Animation(name="look", nodes=[anim_head])

    nodes = MDLBinaryWriter()._animation_nodes_with_hierarchy(anim, [root, pelvis, head])

    assert [node.name for node in nodes] == ["root", "pelvis", "head"]
    assert nodes[1].parent is nodes[0]
    assert nodes[2].parent is nodes[1]
    assert nodes[2].controllers == anim_head.controllers


def test_binary_mdl_export_uses_skin_aware_writer() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._export_mdl_binary)

    assert "from src.core.mdl.mdl_writer import MDLBinaryWriter" in source


def test_retarget_apply_promotes_target_model_for_animation_list() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    window = SimpleNamespace()
    target = SimpleNamespace(name="N_Bith", mdl_path="")
    calls = []
    window._retarget_target_model = target
    window._current_model = SimpleNamespace(name="N_DarthMalak")
    window._current_game = "K1"
    window.animation_retarget_panel = SimpleNamespace(_target_game="K2")
    window._infer_game_from_model = lambda _model: "K1"
    window._set_model_internal = lambda model, path="": calls.append(("set", model, path))
    window._populate_animation_library_from_current_model = lambda: calls.append(("populate",))
    window._show_right_tab = lambda label: calls.append(("tab", label))
    window.animations_panel = SimpleNamespace(
        select_animation=lambda name: calls.append(("select", name))
    )
    window._retarget_target_label = MethodType(
        QtGhostRiggerMainWindow._retarget_target_label,
        window,
    )

    QtGhostRiggerMainWindow._activate_retarget_target_model(window, "walkss")

    assert ("set", target, "K2:N_Bith") in calls
    assert ("populate",) in calls
    assert ("select", "walkss") in calls
    assert ("tab", "Animations") in calls


def test_scene_animation_entries_collect_all_runtime_models() -> None:
    from types import SimpleNamespace

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    window = SimpleNamespace()
    anim_walk = SimpleNamespace(name="walk", length=1.0)
    anim_talk = SimpleNamespace(name="talk", length=2.0)
    bith = SimpleNamespace(name="N_Bith", animations=[anim_walk])
    malak = SimpleNamespace(name="N_DarthMalak", animations=[anim_talk])
    window.scene_manager = SimpleNamespace(
        active_scene=SimpleNamespace(
            objects=[
                SimpleNamespace(
                    id="obj-bith",
                    name="Cantina Bith",
                    source_ref=SimpleNamespace(game="K1", resref="n_bith"),
                    metadata={"_runtime_model": bith},
                ),
                SimpleNamespace(
                    id="obj-malak",
                    name="Malak",
                    source_ref=SimpleNamespace(game="K1", resref="n_darthmalak"),
                    metadata={"_runtime_model": malak},
                ),
            ]
        )
    )
    window._infer_game_from_model = lambda _model: "K1"

    entries = QtGhostRiggerMainWindow._collect_scene_animation_entries(window)

    assert {entry["animation"] for entry in entries} == {"walk", "talk"}
    assert {entry["object_name"] for entry in entries} == {"Cantina Bith", "Malak"}
    assert {entry["resref"] for entry in entries} == {"n_bith", "n_darthmalak"}


def test_quinn_bone_map_loads_as_unreal_target_model() -> None:
    import pytest

    from src.unreal.quinn import QUINN_BONE_MAP, load_quinn_skeleton_asset, unreal_skeleton_model

    if not QUINN_BONE_MAP.exists():
        pytest.skip("SKM_Quinn_Simple_BoneMap.xml not available")

    asset = load_quinn_skeleton_asset()
    model = unreal_skeleton_model(asset)
    names = {node.name.lower() for node in model.all_nodes()}

    assert asset.name == "SKM_Quinn_Simple"
    assert 80 <= asset.bone_count < 100
    assert asset.source == "SKM_Quinn_Simple.FBX"
    assert {"root", "pelvis", "spine_01", "head", "hand_l", "hand_r"} <= names
    assert model.find_node("spine_01").parent is model.find_node("pelvis")
    assert model.find_node("clavicle_out_l") is None


def test_quinn_fbx_import_loads_viewport_mesh() -> None:
    import pytest

    from src.unreal.quinn import QUINN_FBX, load_quinn_fbx_model, load_quinn_skeleton_asset

    if not QUINN_FBX.exists():
        pytest.skip("SKM_Quinn_Simple.FBX not available")

    model = load_quinn_fbx_model(load_quinn_skeleton_asset())
    meshes = model.mesh_nodes()

    assert model.name == "SKM_Quinn_Simple"
    assert len(meshes) == 1
    assert len(meshes[0].vertices) > 40_000
    assert len(meshes[0].faces) > 80_000
    assert meshes[0].is_skin
    assert len(meshes[0].skin_data) == len(meshes[0].vertices)
    assert len(meshes[0].bone_map) > 60
    assert all(sd.influences for sd in meshes[0].skin_data)
    assert all(abs(sum(inf.weight for inf in sd.influences) - 1.0) < 1e-5 for sd in meshes[0].skin_data)
    assert meshes[0].uvs[0][1] > 0.7
    assert "MI_Quinn_01_BaseColor_0" in meshes[0].texture_names
    assert "MI_Quinn_02_BaseColor_1" in meshes[0].texture_names
    assert model.find_node("pelvis") is not None
    assert model.find_node("spine_01").parent is model.find_node("pelvis")
    assert model.find_node("head").bone_world_position()[2] > model.find_node("pelvis").bone_world_position()[2]
    assert not getattr(model.find_node("pelvis"), "_hide_skeleton_overlay", False)
    assert model.find_node("clavicle_out_l") is None

    uncorrected = load_quinn_fbx_model(load_quinn_skeleton_asset(), yaw_180=False)
    assert meshes[0].vertices[0][0] == pytest.approx(-uncorrected.mesh_nodes()[0].vertices[0][0])
    assert meshes[0].vertices[0][1] == pytest.approx(-uncorrected.mesh_nodes()[0].vertices[0][1])
    assert meshes[0].vertices[0][2] == pytest.approx(uncorrected.mesh_nodes()[0].vertices[0][2])


def test_quinn_control_bones_do_not_enter_viewport_skeleton_overlay() -> None:
    import pytest

    pytest.importorskip("PIL")

    from PIL import Image, ImageDraw

    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer
    from src.unreal.quinn import QUINN_FBX, load_quinn_fbx_model, load_quinn_skeleton_asset

    if not QUINN_FBX.exists():
        pytest.skip("SKM_Quinn_Simple.FBX not available")

    model = load_quinn_fbx_model(load_quinn_skeleton_asset())
    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)
    renderer._proj = lambda x, y, z, w, h: (int(100 + x * 10), int(100 - z * 10), y)

    img = Image.new("RGB", (240, 240), "black")
    renderer._draw_bones(ImageDraw.Draw(img), 240, 240)
    names = {getattr(node, "name", "").lower() for *_screen, node in renderer._bone_screen_positions}

    assert "pelvis" in names
    assert "ik_foot_root" not in names
    assert "ik_hand_root" not in names
    assert "interaction" not in names
    assert "center_of_mass" not in names


def test_quinn_aliases_map_common_kotor_supermodel_bones() -> None:
    import pytest

    from src.core.geometry.model_data import ModelNode
    from src.unreal.animation_retargeting import build_bone_map
    from src.unreal.quinn import QUINN_BONE_MAP, load_quinn_skeleton_asset, unreal_skeleton_model

    if not QUINN_BONE_MAP.exists():
        pytest.skip("SKM_Quinn_Simple_BoneMap.xml not available")

    source = SimpleNamespace(
        name="S_Male02",
        all_nodes=lambda: [
            ModelNode(name="pelvis_g"),
            ModelNode(name="spine_g"),
            ModelNode(name="torso_g"),
            ModelNode(name="torsoUpr_g"),
            ModelNode(name="rCollar_g"),
            ModelNode(name="rbicepl_g"),
            ModelNode(name="lforearm"),
            ModelNode(name="rhand"),
            ModelNode(name="rthigh"),
            ModelNode(name="lshin_g"),
            ModelNode(name="rfootT_g"),
        ],
    )
    target = unreal_skeleton_model(load_quinn_skeleton_asset())

    report = build_bone_map(source, target)

    assert report.mapping["pelvis_g"] == "pelvis"
    assert report.mapping["spine_g"] == "spine_01"
    assert report.mapping["torso_g"] == "spine_02"
    assert report.mapping["torsoupr_g"] in {"spine_03", "spine_04", "spine_01"}
    assert report.mapping["rcollar_g"] == "clavicle_r"
    assert report.mapping["rbicepl_g"] == "lowerarm_r"
    assert report.mapping["lforearm"] == "lowerarm_l"
    assert report.mapping["rhand"] == "hand_r"
    assert report.mapping["rthigh"] == "thigh_r"
    assert report.mapping["lshin_g"] == "calf_l"
    assert report.mapping["rfoott_g"] == "ball_r"


def test_quinn_aliases_include_real_kotor_mesh_bone_nodes() -> None:
    import pytest

    from src.core.geometry.model_data import ModelNode, NodeFlags
    from src.unreal.animation_retargeting import build_bone_map
    from src.unreal.quinn import QUINN_BONE_MAP, load_quinn_skeleton_asset, unreal_skeleton_model

    if not QUINN_BONE_MAP.exists():
        pytest.skip("SKM_Quinn_Simple_BoneMap.xml not available")

    source = SimpleNamespace(
        name="S_Male02",
        all_nodes=lambda: [
            ModelNode(name="pelvis_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="torso_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="torsoUpr_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="neck_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rCollar_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rbicep_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rbicepL_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rforearm_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rhand_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rhand"),
            ModelNode(name="Torso", flags=int(NodeFlags.SKIN)),
        ],
    )
    target = unreal_skeleton_model(load_quinn_skeleton_asset())

    report = build_bone_map(source, target)

    assert report.mapping["pelvis_g"] == "pelvis"
    assert report.mapping["torso_g"] == "spine_02"
    assert report.mapping["torsoupr_g"] in {"spine_03", "spine_04", "spine_01"}
    assert report.mapping["neck_g"] == "neck_01"
    assert report.mapping["rcollar_g"] == "clavicle_r"
    assert report.mapping["rbicep_g"] == "upperarm_r"
    assert report.mapping["rbicepl_g"] == "lowerarm_r"
    assert report.mapping["rforearm_g"] == "lowerarm_r"
    assert report.mapping["rhand_g"] == "hand_r"
    assert report.mapping["rhand"] == "hand_r"
    assert "torso" not in report.mapping


def test_unreal_bone_map_excludes_dummy_and_hook_helpers() -> None:
    from src.core.geometry.model_data import ModelNode
    from src.unreal.animation_retargeting import build_bone_map

    source = SimpleNamespace(
        name="S_Male02",
        all_nodes=lambda: [
            ModelNode(name="rootdummy"),
            ModelNode(name="talkdummy"),
            ModelNode(name="headhook"),
            ModelNode(name="pelvis_g"),
        ],
    )
    target = SimpleNamespace(
        name="SKM_Quinn_Simple",
        all_nodes=lambda: [
            ModelNode(name="root"),
            ModelNode(name="dummyroot"),
            ModelNode(name="headhook"),
            ModelNode(name="pelvis"),
        ],
    )

    report = build_bone_map(
        source,
        target,
        manual_mapping={
            "rootdummy": "root",
            "talkdummy": "root",
            "headhook": "headhook",
            "pelvis_g": "dummyroot",
        },
    )

    assert "rootdummy" not in report.mapping
    assert "talkdummy" not in report.mapping
    assert "headhook" not in report.mapping
    assert "rootdummy" not in report.missing_source
    assert "talkdummy" not in report.missing_source
    assert "headhook" not in report.missing_source
    assert report.mapping["pelvis_g"] == "pelvis"


def test_unreal_viewport_hides_dummy_and_hook_helpers_from_bone_overlay() -> None:
    import pytest

    pytest.importorskip("PIL")

    from PIL import Image, ImageDraw

    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    root = ModelNode(name="root")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 1.0))
    talkdummy = ModelNode(name="talkdummy", position=(0.0, 0.0, 2.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 3.0))
    headhook = ModelNode(name="headhook", position=(0.0, 0.0, 3.0))
    root.children.extend([pelvis, headhook])
    pelvis.parent = root
    pelvis.children.append(talkdummy)
    talkdummy.parent = pelvis
    talkdummy.children.append(torso)
    torso.parent = talkdummy
    headhook.parent = root

    model = KotorModel(name="S_Male02", root_node=root)
    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)
    renderer.set_hidden_bone_name_fragments(("dummy", "hook"))
    renderer._proj = lambda x, y, z, w, h: (int(100 + z * 10), 100, z)

    img = Image.new("RGB", (240, 240), "black")
    renderer._draw_bones(ImageDraw.Draw(img), 240, 240)
    names = {getattr(node, "name", "").lower() for *_screen, node in renderer._bone_screen_positions}

    assert "root" in names
    assert "pelvis_g" in names
    assert "torso_g" in names
    assert "talkdummy" not in names
    assert "headhook" not in names


def test_unreal_viewport_hidden_helper_selection_does_not_draw_gimbal() -> None:
    import pytest

    pytest.importorskip("PIL")

    from PIL import Image, ImageDraw

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    root = ModelNode(name="root")
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 1.0))
    root.children.append(rootdummy)
    rootdummy.parent = root

    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(KotorModel(name="S_Male02", root_node=root))
    renderer.set_hidden_bone_name_fragments(("dummy", "hook"))
    renderer.selected_node = rootdummy
    renderer._gimbal_handles = [(10, 10, "X")]

    img = Image.new("RGB", (240, 240), "black")
    renderer._draw_gimbal(ImageDraw.Draw(img), 240, 240)

    assert renderer.selected_node is None
    assert renderer._gimbal_handles == []


def test_unreal_animator_inserts_synthetic_spine_between_pelvis_and_torso() -> None:
    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 2.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 4.0))
    root.children.append(pelvis)
    pelvis.parent = root
    pelvis.children.append(rootdummy)
    rootdummy.parent = pelvis
    rootdummy.children.append(torso)
    torso.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow.__new__(QtUnrealAnimatorWindow)

    assert window._ensure_source_spine_g(model) is True

    spine = model.find_node("spine_g")
    assert spine is not None
    assert spine.parent is pelvis
    assert torso.parent is spine
    assert torso in spine.children
    assert torso not in rootdummy.children
    assert spine.position == (0.0, 0.0, 3.0)
    assert torso.position == (0.0, 0.0, 3.0)


def test_unreal_animator_inserts_synthetic_spine_when_pelvis_and_torso_share_rootdummy() -> None:
    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    root = ModelNode(name="s_female03")
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 0.0))
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 16.0))
    root.children.append(rootdummy)
    rootdummy.parent = root
    rootdummy.children.extend([pelvis, torso])
    pelvis.parent = rootdummy
    torso.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow.__new__(QtUnrealAnimatorWindow)

    assert window._ensure_source_spine_g(model) is True

    spine = model.find_node("spine_g")
    assert spine is not None
    assert pelvis.parent is rootdummy
    assert spine.parent is pelvis
    assert torso.parent is spine
    assert spine in pelvis.children
    assert torso in spine.children
    assert torso not in rootdummy.children
    assert spine.position == (0.0, 0.0, 3.0)
    assert torso.position == (0.0, 0.0, 3.0)


def test_unreal_animator_repositions_existing_spine_between_pelvis_and_torso() -> None:
    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 2.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 4.0))
    spine = ModelNode(name="spine_g", position=(99.0, 99.0, 99.0))
    root.children.extend([pelvis, spine])
    pelvis.parent = root
    spine.parent = root
    pelvis.children.append(rootdummy)
    rootdummy.parent = pelvis
    rootdummy.children.append(torso)
    torso.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow.__new__(QtUnrealAnimatorWindow)

    assert window._ensure_source_spine_g(model) is True
    assert spine.parent is pelvis
    assert torso.parent is spine
    assert spine in pelvis.children
    assert torso in spine.children
    assert spine not in root.children


def test_unreal_animator_source_bone_browser_lists_and_selects_spine() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 2.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 4.0))
    root.children.append(pelvis)
    pelvis.parent = root
    pelvis.children.append(rootdummy)
    rootdummy.parent = pelvis
    rootdummy.children.append(torso)
    torso.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow()
    try:
        window.set_source_model(model, "K1")
        rows = {
            window.source_bones.topLevelItem(row).text(0): window.source_bones.topLevelItem(row)
            for row in range(window.source_bones.topLevelItemCount())
        }

        assert "spine_g" in rows
        assert "rootdummy" not in rows
        assert rows["spine_g"].text(1) == "pelvis_g"
        assert rows["spine_g"].text(2) == "synthetic"

        window.source_bones.setCurrentItem(rows["spine_g"])
        assert getattr(window.source_viewport._renderer.selected_node, "name", "") == "spine_g"
    finally:
        window.close()


def test_unreal_animator_manually_adds_and_deletes_source_synthetic_bones() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    root = ModelNode(name="s_female03")
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 0.0))
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 16.0))
    torso_upper = ModelNode(name="torsoUpr_g", position=(0.0, 0.0, 4.0))
    neck = ModelNode(name="neck_g", position=(0.0, 0.0, 6.0))
    eyelid = ModelNode(name="eyelid", position=(1.0, 0.0, 7.0))
    root.children.append(rootdummy)
    rootdummy.parent = root
    rootdummy.children.extend([pelvis, torso, eyelid])
    pelvis.parent = rootdummy
    torso.parent = rootdummy
    torso.children.append(torso_upper)
    torso_upper.parent = torso
    torso_upper.children.append(neck)
    neck.parent = torso_upper
    eyelid.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow()
    try:
        window.set_source_model(model, "K1")

        assert model.find_node("spine_05") is None
        assert model.find_node("lowerarm_twist_01_l") is None
        assert model.find_node("ik_foot_root") is None
        assert model.find_node("interaction") is None
        assert model.find_node("center_of_mass") is None

        spacer = window._add_source_synthetic_bone("spine_05", child_node=neck)
        assert spacer is not None
        assert spacer.name == "spine_05"
        assert spacer.parent is torso_upper
        assert neck.parent is spacer
        assert bool(getattr(spacer, "_ghostrigger_synthetic_unreal_source", False))
        assert bool(getattr(spacer, "_ghostrigger_synthetic_manual_source", False))
        assert spacer.position == (0.0, 0.0, 3.0)
        assert neck.position == (0.0, 0.0, 3.0)

        rows = {
            window.source_bones.topLevelItem(row).text(0): window.source_bones.topLevelItem(row)
            for row in range(window.source_bones.topLevelItemCount())
        }
        assert "pelvis_g" in rows
        assert "torso_g" in rows
        assert "torsoUpr_g" in rows
        assert "neck_g" in rows
        assert "eyelid" in rows
        assert "spine_05" in rows
        assert "ik_foot_root" not in rows
        assert rows["spine_05"].text(2) == "synthetic"
        assert "Quinn bones" not in window.source_label.text()

        window.source_bones.setCurrentItem(rows["spine_05"])
        assert window._delete_selected_source_synthetic_bone() is True
        assert model.find_node("spine_05") is None
        assert neck.parent is torso_upper
        assert neck.position == (0.0, 0.0, 6.0)
    finally:
        window.close()


def test_unreal_animator_exposes_reload_code_button() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    window = QtUnrealAnimatorWindow()
    try:
        assert window.reload_code_action.shortcut().toString() == "Ctrl+Shift+R"
        assert window.reload_code_button.text() == "Reload Code"
        with_signal = []
        window.reloadCodeRequested.connect(lambda: with_signal.append(True))

        window.reload_code_button.click()

        assert with_signal == [True]
    finally:
        window.close()


def test_unreal_animator_animation_selection_arms_preview_pose() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 16.0))
    root.children.extend([pelvis, torso])
    pelvis.parent = root
    torso.parent = root
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [
        Animation(name="pause1", length=1.0),
        Animation(name="taunt", length=1.6),
    ]

    window = QtUnrealAnimatorWindow()
    try:
        window.set_source_model(model, "K1")
        window.anim_list.setCurrentRow(1)

        assert window.selected_animation_name() == "taunt"
        assert window._preview_engine is not None
        assert window._preview_engine.current_animation.name == "taunt"
        assert not window._preview_timer.isActive()
        assert window.preview_button.isEnabled()
        assert window.source_frame_label.text() == "0 / 48f"
        assert window.target_frame_label.text() == "0 / 48f"
    finally:
        window.close()


def test_unreal_animator_uses_gpu_during_animation_preview() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 16.0))
    root.children.extend([pelvis, torso])
    pelvis.parent = root
    torso.parent = root
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [Animation(name="pause1", length=1.0)]

    window = QtUnrealAnimatorWindow()
    try:
        window.set_source_model(model, "K1")
        window.source_viewport.toggle_gpu_renderer(False)
        window.target_viewport.toggle_gpu_renderer(False)

        window.preview_selected_animation()

        assert window.source_viewport._use_gpu is True
        assert window.target_viewport._use_gpu is True

        window.stop_preview()

        assert window.source_viewport._use_gpu is True
        assert window.target_viewport._use_gpu is True
    finally:
        window.close()


def test_retarget_pose_applies_source_bind_relative_rotation_to_target_bind() -> None:
    import math

    import pytest

    from src.core.animation.animation_engine import AnimPose, NodePose
    from src.core.animation_retargeting.retargeter import retarget_pose
    from src.core.geometry.model_data import ModelNode

    src_bind = (0.0, 0.0, math.sin(math.radians(45.0)), math.cos(math.radians(45.0)))
    target_bind = (0.0, math.sin(math.radians(15.0)), 0.0, math.cos(math.radians(15.0)))
    source = SimpleNamespace(name="source", all_nodes=lambda: [ModelNode(name="RHand", rotation=src_bind)])
    target = SimpleNamespace(name="target", all_nodes=lambda: [ModelNode(name="RHand", rotation=target_bind)])
    pose = AnimPose(nodes={"rhand": NodePose(name="RHand", rotation=src_bind)})

    result = retarget_pose(pose, source, target)

    assert result.pose.nodes["rhand"].rotation == pytest.approx(target_bind)


def test_manual_bone_map_override_drives_retarget_pose() -> None:
    from src.core.animation.animation_engine import AnimPose, NodePose
    from src.core.animation_retargeting.retargeter import build_bone_map, retarget_pose
    from src.core.geometry.model_data import ModelNode

    source = SimpleNamespace(name="source", all_nodes=lambda: [ModelNode(name="source_arm")])
    target = SimpleNamespace(name="target", all_nodes=lambda: [ModelNode(name="target_arm")])

    report = build_bone_map(source, target, manual_mapping={"source_arm": "target_arm"})
    result = retarget_pose(
        AnimPose(nodes={"source_arm": NodePose(name="source_arm")}),
        source,
        target,
        mapping_report=report,
    )

    assert report.manual_matches == 1
    assert report.mapping == {"source_arm": "target_arm"}
    assert "target_arm" in result.pose.nodes


def test_preserve_model_scale_scales_position_deltas_by_target_height() -> None:
    import pytest

    from src.core.animation.animation_engine import AnimPose, NodePose
    from src.core.animation_retargeting.retargeter import RetargetConfig, retarget_pose
    from src.core.geometry.model_data import KotorModel, ModelNode

    src_root = ModelNode(name="root")
    src_head = ModelNode(name="head", position=(0.0, 0.0, 10.0))
    src_root.children.append(src_head)
    src_head.parent = src_root
    source = KotorModel(name="source", root_node=src_root)

    dst_root = ModelNode(name="root")
    dst_head = ModelNode(name="head", position=(0.0, 0.0, 5.0))
    dst_root.children.append(dst_head)
    dst_head.parent = dst_root
    target = KotorModel(name="target", root_node=dst_root)

    pose = AnimPose(nodes={"head": NodePose(name="head", position=(0.0, 0.0, 20.0))})

    scaled = retarget_pose(pose, source, target)
    unscaled = retarget_pose(
        pose,
        source,
        target,
        config=RetargetConfig(preserve_model_scale=False),
    )

    assert scaled.pose.nodes["head"].position[2] == pytest.approx(10.0)
    assert unscaled.pose.nodes["head"].position[2] == pytest.approx(15.0)


def test_bone_map_reports_interpolated_target_bridge_bones() -> None:
    from src.core.geometry.model_data import ModelNode
    from src.unreal.animation_retargeting import build_bone_map

    src_a = ModelNode(name="a")
    src_b = ModelNode(name="b")
    dst_root = ModelNode(name="target")
    dst_a = ModelNode(name="a")
    dst_mid = ModelNode(name="mid")
    dst_b = ModelNode(name="b")
    dst_a.parent = dst_root
    dst_mid.parent = dst_a
    dst_b.parent = dst_mid
    dst_root.children.append(dst_a)
    dst_a.children.append(dst_mid)
    dst_mid.children.append(dst_b)
    source = SimpleNamespace(name="source", all_nodes=lambda: [src_a, src_b])
    target = SimpleNamespace(name="target", all_nodes=lambda: [dst_root, dst_a, dst_mid, dst_b])

    report = build_bone_map(source, target)

    assert report.mapping == {"a": "a", "b": "b"}
    assert report.derived_target == ("mid",)
    assert "mid" not in report.missing_target


def test_retarget_pose_bridges_dense_target_chain() -> None:
    import math

    import pytest

    from src.core.animation.animation_engine import AnimPose, NodePose
    from src.core.geometry.model_data import KotorModel, ModelNode
    from src.unreal.animation_retargeting import retarget_pose

    source = KotorModel(name="source")
    source_root = ModelNode(name="source")
    source.root_node = source_root
    source_a = ModelNode(name="a")
    source_b = ModelNode(name="b")
    source_a.parent = source_root
    source_b.parent = source_a
    source_root.children.append(source_a)
    source_a.children.append(source_b)

    target = KotorModel(name="target")
    target_root = ModelNode(name="target")
    target.root_node = target_root
    target_a = ModelNode(name="a")
    target_mid = ModelNode(name="mid")
    target_b = ModelNode(name="b")
    target_a.parent = target_root
    target_mid.parent = target_a
    target_b.parent = target_mid
    target_root.children.append(target_a)
    target_a.children.append(target_mid)
    target_mid.children.append(target_b)

    q90 = (0.0, 0.0, math.sin(math.radians(45.0)), math.cos(math.radians(45.0)))
    pose = AnimPose(nodes={
        "a": NodePose(name="a"),
        "b": NodePose(name="b", rotation=q90),
    })

    result = retarget_pose(pose, source, target)

    assert "mid" in result.pose.nodes
    assert "mid" in result.report.derived_target
    assert result.pose.nodes["mid"].rotation[2] == pytest.approx(math.sin(math.radians(22.5)))
    assert result.pose.nodes["b"].rotation[2] == pytest.approx(math.sin(math.radians(22.5)))


def test_retarget_animation_bakes_bridge_bones() -> None:
    import math

    from src.core.geometry.model_data import Animation, KotorModel, ModelNode
    from src.unreal.animation_retargeting import retarget_animation

    source = KotorModel(name="source")
    source_root = ModelNode(name="source")
    source.root_node = source_root
    source_a = ModelNode(name="a")
    source_b = ModelNode(name="b")
    source_a.parent = source_root
    source_b.parent = source_a
    source_root.children.append(source_a)
    source_a.children.append(source_b)

    q90 = (0.0, 0.0, math.sin(math.radians(45.0)), math.cos(math.radians(45.0)))
    anim_b = ModelNode(name="b")
    anim_b.controllers = [{"type": 20, "times": [0.0, 1.0], "values": [(0.0, 0.0, 0.0, 1.0), q90]}]
    source.animations = [Animation(name="turn", length=1.0, nodes=[anim_b])]

    target = KotorModel(name="target")
    target_root = ModelNode(name="target")
    target.root_node = target_root
    target_a = ModelNode(name="a")
    target_mid = ModelNode(name="mid")
    target_b = ModelNode(name="b")
    target_a.parent = target_root
    target_mid.parent = target_a
    target_b.parent = target_mid
    target_root.children.append(target_a)
    target_a.children.append(target_mid)
    target_mid.children.append(target_b)

    baked, report = retarget_animation(source.animations[0], source, target)

    baked_names = {node.name.lower() for node in baked.nodes}
    assert "mid" in baked_names
    assert "mid" in report.derived_target


def test_gpu_vbo_splits_skin_bind_and_animated_input_space() -> None:
    import inspect

    from src.adapters.rendering import moderngl_resources

    source = inspect.getsource(moderngl_resources._build_vbo_data)
    assert "apply_skin_node_transform_for_bind" in source
    assert "not is_skin or bool(apply_skin_node_transform_for_bind)" in source
    assert "elif _node_vs == 1 or is_skin" in source


def test_arcball_frame_bounds_expands_clip_range_for_large_assets() -> None:
    from src.core.camera.arcball_camera import ArcBallCamera

    camera = ArcBallCamera()
    camera.frame_bounds((-1200.0, -900.0, -200.0), (1200.0, 900.0, 200.0), reset_view=True)

    assert camera._far > 1000.0
    assert camera._far > camera.distance
    assert 0.001 <= camera._near <= 0.05
    assert camera._near < max(0.001, camera.distance - 200.0)


def test_arcball_zoom_tightens_near_clip_for_close_animation_inspection() -> None:
    from src.core.camera.arcball_camera import ArcBallCamera

    camera = ArcBallCamera()
    camera._near = 0.05
    camera.distance = 1.0

    camera.zoom(30.0)

    assert camera.distance < 0.1
    assert camera._near == pytest.approx(0.001)
    assert camera._far > camera.distance


def test_wgpu_frustum_culling_uses_world_space_mesh_bounds() -> None:
    from types import SimpleNamespace

    import numpy as np

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

    renderer = WgpuRenderer()
    mesh = SimpleNamespace(
        positions=np.asarray([(10.0, 10.0, 10.0), (11.0, 11.0, 11.0)], dtype=np.float32),
        world_matrix=np.asarray(
            [
                [1.0, 0.0, 0.0, -10.5],
                [0.0, 1.0, 0.0, -10.5],
                [0.0, 0.0, 1.0, -10.5],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        ),
        is_skinned=False,
    )
    unit_cube_planes = (
        (1.0, 0.0, 0.0, 1.0),
        (-1.0, 0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0, 1.0),
        (0.0, -1.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, 1.0),
        (0.0, 0.0, -1.0, 1.0),
    )

    assert renderer._mesh_data_outside_frustum(mesh, unit_cube_planes) is False


def test_wgpu_frustum_culling_keeps_animated_skinned_meshes_visible() -> None:
    from types import SimpleNamespace

    import numpy as np

    from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

    renderer = WgpuRenderer()
    renderer._active_anim_pose = SimpleNamespace(time=1.0)
    mesh = SimpleNamespace(
        positions=np.asarray([(50.0, 50.0, 50.0), (51.0, 51.0, 51.0)], dtype=np.float32),
        is_skinned=True,
    )
    unit_cube_planes = (
        (1.0, 0.0, 0.0, 1.0),
        (-1.0, 0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0, 1.0),
        (0.0, -1.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, 1.0),
        (0.0, 0.0, -1.0, 1.0),
    )

    assert renderer._mesh_data_outside_frustum(mesh, unit_cube_planes) is False
