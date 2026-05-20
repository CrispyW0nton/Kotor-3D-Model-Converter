"""
GhostRigger-specific MCP tools.

Architecture (Khononov, "Balancing Coupling in Software Design"):
  • Each handler depends on:
      - ModelLocatorPort  (Contract Coupling: find bytes)
      - ModelParserPort   (Contract Coupling: parse bytes)
      - ModelAnalyzer     (Domain service: extract structured info)
  • The adapters (FileSystemModelLocator, MDLBinaryParserAdapter, etc.)
    live in adapters.py — all pykotor / filesystem specifics are there.
  • Handlers receive a pre-built container of collaborators via
    _get_services(), which composes a default adapter chain on first call.
  • Result types (ModelInfo, AuditResult) are immutable data contracts
    defined in ports.py — tools serialize them to JSON; nothing leaks
    the internal model object outside this module.

Changes from v2.9:
  • Removed duplicate _locate_mdl / _load_model helpers (Connascence of
    Algorithm eliminated — now handled by CompositeModelLocator +
    MDLBinaryParserAdapter)
  • Removed scattered sys.path.insert() calls (intrusive path hacking moved
    to MDLBinaryParserAdapter)
  • resolve_game_safe() now delegates to the injected registry
  • handle_model_info() and handle_audit() share ModelAnalyzer (single source
    of truth for model-interrogation logic)
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kotormcp.ports import (
    AuditResult,
    InstallationRegistryPort,
    ModelInfo,
    ModelLocatorPort,
    ModelParserPort,
)
from kotormcp.utils import json_content


# ── Service container ─────────────────────────────────────────────────────────

class _Services:
    """
    Lightweight container wiring the default adapter chain.

    Using a container instead of module-level globals means tests can
    swap individual services without patching globals (lower Distance,
    lower coupling strength for test code).
    """

    def __init__(
        self,
        locator: ModelLocatorPort,
        parser: ModelParserPort,
        analyzer,  # ModelAnalyzer — not typed to avoid circular import
        registry: InstallationRegistryPort,
    ):
        self.locator = locator
        self.parser = parser
        self.analyzer = analyzer
        self.registry = registry


_default_services: Optional[_Services] = None


def _get_services() -> _Services:
    """Build the default service composition on first call (lazy singleton)."""
    global _default_services
    if _default_services is None:
        from kotormcp.adapters import (  # noqa: PLC0415
            CompositeModelLocator,
            FileSystemModelLocator,
            InstallationModelLocator,
            MDLBinaryParserAdapter,
            ModelAnalyzer,
            get_default_registry,
        )
        registry = get_default_registry()
        locator = CompositeModelLocator([
            FileSystemModelLocator(),
            InstallationModelLocator(registry),
        ])
        parser = MDLBinaryParserAdapter()
        analyzer = ModelAnalyzer()
        _default_services = _Services(locator, parser, analyzer, registry)
    return _default_services


def _reset_services() -> None:
    """Force a rebuild of the service container (used in tests)."""
    global _default_services
    _default_services = None


# ── Tool definitions ──────────────────────────────────────────────────────────

def get_tools() -> List[Dict[str, Any]]:
    """Return GhostRigger-specific tool definitions."""
    return [
        {
            "name": "ghostrigger_open_model",
            "description": (
                "Open a KotOR MDL/MDX model in the GhostRigger 3D viewport. "
                "Pass resref (without extension) or an absolute file path. "
                "Optionally provide game/game_path for installation-relative lookup."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resref": {
                        "type": "string",
                        "description": "MDL resource name (e.g. n_sithpraet) or absolute file path",
                    },
                    "game": {
                        "type": "string",
                        "description": "Optional game alias (k1/k2)",
                    },
                    "game_path": {
                        "type": "string",
                        "description": "Optional absolute path to KotOR installation",
                    },
                },
                "required": ["resref"],
            },
        },
        {
            "name": "ghostrigger_render_model",
            "description": (
                "Render a KotOR MDL model to a PNG image and return the file path. "
                "Useful for quick visual inspection. Requires a GPU/OpenGL context."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resref": {
                        "type": "string",
                        "description": "MDL resource name or absolute file path",
                    },
                    "width": {"type": "integer", "default": 512},
                    "height": {"type": "integer", "default": 512},
                    "azimuth": {"type": "number", "default": 45},
                    "elevation": {"type": "number", "default": 30},
                    "output_path": {"type": "string"},
                    "game": {"type": "string"},
                    "game_path": {"type": "string"},
                },
                "required": ["resref"],
            },
        },
        {
            "name": "ghostrigger_model_info",
            "description": (
                "Return structured information about a KotOR MDL model: "
                "node count, mesh nodes, bone list, UV presence, bounding box, "
                "animations, classification, and supermodel."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resref": {
                        "type": "string",
                        "description": "MDL resource name or absolute file path",
                    },
                    "game": {"type": "string"},
                    "game_path": {"type": "string"},
                },
                "required": ["resref"],
            },
        },
        {
            "name": "ghostrigger_list_game_models",
            "description": (
                "List MDL models available in a KotOR installation, with optional "
                "name filter. Returns up to `limit` results."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "game": {"type": "string", "description": "k1 or k2"},
                    "game_path": {"type": "string"},
                    "filter": {"type": "string", "description": "Substring filter"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["game"],
            },
        },
        {
            "name": "ghostrigger_audit",
            "description": (
                "Run a quick integrity check on a KotOR MDL model: "
                "counts nodes, detects UV/normal mismatches, validates bounding box."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resref": {
                        "type": "string",
                        "description": "MDL resource name or absolute file path",
                    },
                    "game": {"type": "string"},
                    "game_path": {"type": "string"},
                },
                "required": ["resref"],
            },
        },
        {
            "name": "ghostrigger_export_model_for_unity",
            "description": (
                "Export a KotOR MDL/MDX model from game data or a file path into "
                "a Unity project Assets folder as FBX, with a GhostRigger metadata "
                "JSON sidecar. Use this for repeatable GhostRigger -> Unity MCP "
                "asset transfer tests."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "resref": {
                        "type": "string",
                        "description": "MDL resource name or absolute file path",
                    },
                    "game": {
                        "type": "string",
                        "description": "Game alias: k1 or k2",
                    },
                    "game_path": {
                        "type": "string",
                        "description": "Optional absolute path to KotOR installation",
                    },
                    "unity_project": {
                        "type": "string",
                        "description": "Absolute Unity project root",
                    },
                    "asset_subdir": {
                        "type": "string",
                        "default": "Assets/KotorImported/GhostRigger",
                        "description": "Unity-project-relative output folder",
                    },
                    "output_name": {
                        "type": "string",
                        "description": "Optional output filename stem; defaults to resref",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["fbx"],
                        "default": "fbx",
                    },
                    "export_rigging": {
                        "type": "boolean",
                        "default": True,
                        "description": "Write rigging JSON sidecars next to the FBX",
                    },
                },
                "required": ["resref", "game", "unity_project"],
            },
        },
        {
            "name": "ghostrigger_validate_unity_import",
            "description": (
                "Build a validation manifest for a GhostRigger-exported Unity asset. "
                "Pass the GhostRigger transfer metadata sidecar and Unity-side import "
                "facts (clips, renderer types, material count, skin/bindpose counts) "
                "to get stable pass/warning/error diagnostics."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "transfer_metadata_path": {
                        "type": "string",
                        "description": "Path to the *.ghostrigger.json transfer sidecar",
                    },
                    "unity_summary": {
                        "type": "object",
                        "description": "Unity import facts: asset_path, clips, renderers, warnings, errors",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional path to write the validation manifest JSON",
                    },
                },
                "required": ["transfer_metadata_path", "unity_summary"],
            },
        },
        {
            "name": "ghostrigger_run_malak_unity_smoke",
            "description": (
                "Run the repeatable Malak main-menu Unity MCP smoke test. Opens the "
                "menu test scene, refreshes the fresh GhostRigger FBX, verifies the "
                "menu instance/Animator, captures before/after screenshots, and "
                "writes an optional launch-readiness report."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "unity_project": {
                        "type": "string",
                        "description": "Absolute Unity project root",
                    },
                    "host": {
                        "type": "string",
                        "default": "127.0.0.1",
                    },
                    "port": {
                        "type": "integer",
                        "default": 6400,
                    },
                    "scene_path": {
                        "type": "string",
                        "description": "Unity scene asset path",
                    },
                    "asset_path": {
                        "type": "string",
                        "description": "Fresh GhostRigger FBX asset path",
                    },
                    "instance_name": {
                        "type": "string",
                        "description": "Expected Malak menu GameObject instance name",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional report JSON path",
                    },
                    "screenshot_delay": {
                        "type": "number",
                        "default": 1.0,
                    },
                },
                "required": ["unity_project"],
            },
        },
    ]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _locate_and_parse(
    resref: str,
    game: Optional[str],
    game_path: Optional[str],
    svc: _Services,
) -> Tuple[str, Any]:
    """
    Locate MDL bytes and parse to a model object.

    Returns (path_label, model).
    Raises FileNotFoundError or Exception on failure.
    """
    path_label, mdl_bytes, mdx_bytes = svc.locator.locate(resref, game, game_path)
    model = svc.parser.parse(mdl_bytes, mdx_bytes, path_label)
    return path_label, model


def _export_fbx_for_unity(model: Any, out_path: Path, export_rigging: bool) -> bool:
    """Small seam for tests around the real FBX exporter."""
    try:
        from src.converters.mesh_converter import FBXExporter  # noqa: PLC0415
    except ImportError:                                      # pragma: no cover - MCP path shim
        from converters.mesh_converter import FBXExporter     # type: ignore  # noqa: PLC0415

    return FBXExporter().export(model, str(out_path), export_rigging=export_rigging)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def handle_open_model(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Open model in GhostRigger viewport via IPC (if running) or return info."""
    resref = arguments.get("resref", "")
    game = arguments.get("game")
    game_path = arguments.get("game_path")
    svc = _get_services()

    try:
        path_label, mdl_bytes, _ = svc.locator.locate(resref, game, game_path)
        size = len(mdl_bytes)
    except FileNotFoundError as exc:
        return json_content({"error": str(exc)})

    # Try to open via IPC (GhostRigger may be running)
    try:
        import requests  # noqa: PLC0415
        resp = requests.post(
            "http://127.0.0.1:7001/api/open_mdl",
            json={
                "version": "1.0",
                "sender": "KotorMCP",
                "action": "open_mdl",
                "payload": {"resref": resref, "module_dir": ""},
            },
            timeout=1.0,
        )
        ipc_ok = resp.json().get("status") == "ok"
    except Exception:
        ipc_ok = False

    return json_content({
        "status": "ok",
        "resref": resref,
        "path": path_label,
        "size": size,
        "ipc_sent": ipc_ok,
        "message": (
            "Opened in GhostRigger viewport" if ipc_ok
            else "IPC not available; model located at path"
        ),
    })


async def handle_render_model(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Render MDL to PNG and return file path."""
    import os  # noqa: PLC0415

    resref = arguments.get("resref", "")
    game = arguments.get("game")
    game_path = arguments.get("game_path")
    width = int(arguments.get("width", 512))
    height = int(arguments.get("height", 512))
    azimuth = float(arguments.get("azimuth", 45))
    elevation = float(arguments.get("elevation", 30))
    output_path: Optional[str] = arguments.get("output_path")
    svc = _get_services()

    try:
        path_label, model = _locate_and_parse(resref, game, game_path, svc)
    except FileNotFoundError as exc:
        return json_content({"error": str(exc)})
    except Exception as exc:
        return json_content({"error": f"Failed to parse MDL: {exc}"})

    try:
        # Bootstrap sys.path so relative imports (..core.model_data) resolve.
        # The gui package uses "from ..core.model_data import …" which requires
        # the project root (parent of src/) to be on sys.path so that
        # "src.gui" and "src.core" are addressable as proper sub-packages.
        import sys  # noqa: PLC0415
        _project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)

        # MCP servers are long-lived, so they can retain stale qt_lib alias
        # modules from before the GUI package was grouped under src.gui.rendering.
        # Drop only those known aliases before importing the canonical modules.
        for _mod_name in (
            "src.gui.rendering.gpu_renderer",
            "src.gui.rendering.viewport_core",
            "src.gui.rendering",
            "src.gui.qt_lib.rendering.gpu_renderer",
            "src.gui.qt_lib.rendering.viewport_core",
            "src.gui.qt_lib.rendering",
        ):
            _mod = sys.modules.get(_mod_name)
            _target = str(getattr(_mod, "_target", "") or "")
            if _target.startswith("src.gui.") or (
                _mod_name == "src.gui.rendering" and getattr(_mod, "__path__", None) == []
            ):
                sys.modules.pop(_mod_name, None)
        _qt_lib = sys.modules.get("src.gui.qt_lib")
        _aliases = getattr(_qt_lib, "_ALIASES", None)
        if isinstance(_aliases, dict):
            for _alias in list(_aliases):
                if _alias.startswith("src.gui.rendering."):
                    _aliases.pop(_alias, None)

        import importlib.util as _importlib_util  # noqa: PLC0415

        def _load_gui_module(_name: str, _rel_path: str):
            _path = os.path.join(_project_root, _rel_path)
            _spec = _importlib_util.spec_from_file_location(_name, _path)
            if _spec is None or _spec.loader is None:
                raise ImportError(f"Could not load {_name} from {_path}")
            _module = _importlib_util.module_from_spec(_spec)
            sys.modules[_name] = _module
            _spec.loader.exec_module(_module)
            return _module

        _viewport_core = _load_gui_module(
            "src.gui.rendering.viewport_core",
            os.path.join("src", "gui", "rendering", "viewport_core.py"),
        )
        sys.modules["src.gui.viewport_core"] = _viewport_core
        _gpu_renderer = _load_gui_module(
            "src.gui.rendering.gpu_renderer",
            os.path.join("src", "gui", "rendering", "gpu_renderer.py"),
        )
        sys.modules["src.gui.gpu_renderer"] = _gpu_renderer

        GpuRenderer = _gpu_renderer.GpuRenderer
        render_model_autoframe = _gpu_renderer.render_model_autoframe
        ArcBallCamera = _viewport_core.ArcBallCamera
        _load_tpc_bytes = _viewport_core._load_tpc_bytes
        _is_tpc_data = _viewport_core._is_tpc_data

        # ── Build texture dict from model nodes + game library ─────────────────
        # Collect all texture names referenced by the model
        tex_names: list = []
        seen_tex: set = set()
        try:
            all_nodes_fn = getattr(model, 'all_nodes', None)
            nodes = list(all_nodes_fn()) if all_nodes_fn else []
            for _n in nodes:
                if not getattr(_n, 'is_mesh', False):
                    continue
                for attr in ('texture', 'lightmap', 'bump_map',
                             'txi_envmaptexture', 'txi_specularcolour'):
                    _t = str(getattr(_n, attr, '') or '').strip().lower()
                    if _t and _t not in ('null', '', 'none') and _t not in seen_tex:
                        tex_names.append(_t)
                        seen_tex.add(_t)
                # Also check texture_names list (multi-texture nodes)
                for _tn in getattr(_n, 'texture_names', []):
                    _t = str(_tn or '').strip().lower()
                    if _t and _t not in ('null', '', 'none') and _t not in seen_tex:
                        tex_names.append(_t)
                        seen_tex.add(_t)
        except Exception:
            pass

        textures: dict = {}
        _lib = getattr(svc, 'library', None) or getattr(svc, 'lib', None)
        # Try to find game library from service
        if _lib is None:
            try:
                from src.resources.game_library import GameLibrary  # noqa: PLC0415
                _lib = GameLibrary()
                if game_path and os.path.isdir(game_path):
                    _lib.scan(game_path)
            except Exception:
                pass
        if _lib is not None:
            _game_tag = 'K2' if (game or '').upper() in ('K2', 'TSL', 'KOTOR2') else 'K1'
            for tname in tex_names:
                try:
                    raw = _lib.get_texture_data(tname, _game_tag)
                    if raw:
                        img_tex = None
                        if _is_tpc_data(raw):
                            img_tex = _load_tpc_bytes(raw)
                        else:
                            try:
                                import io as _io
                                from PIL import Image as _PILImg  # noqa: PLC0415
                                img_tex = _PILImg.open(_io.BytesIO(raw)).convert('RGBA')
                            except Exception:
                                pass
                        if img_tex is not None:
                            textures[tname] = img_tex
                except Exception:
                    pass

        # Auto-frame the model from its bounding box
        camera = ArcBallCamera()
        camera.azimuth = azimuth
        camera.elevation = elevation
        bb_min = getattr(model, "bb_min", None)
        bb_max = getattr(model, "bb_max", None)
        if bb_min is not None and bb_max is not None:
            camera.frame_bounds(bb_min, bb_max)
        else:
            camera.distance = 3.5
            camera.target = [0.0, 0.0, 0.9]

        renderer = GpuRenderer()
        renderer.force_cpu = True  # headless environment: always use CPU/PIL fallback
        img = renderer.render(model, camera, width, height, textures=textures)

        if img is None:
            return json_content({"error": "Renderer returned None (Pillow may be missing)"})

        if output_path is None:
            output_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "audit_output"
            )
            os.makedirs(output_dir, exist_ok=True)
            # Sanitise resref for use as a filename
            safe_ref = os.path.basename(resref).replace(os.sep, "_")
            output_path = os.path.join(
                output_dir,
                f"mcp_render_{safe_ref}_{int(azimuth)}az_{int(elevation)}el.png",
            )

        img.save(output_path)
        return json_content({
            "status": "ok",
            "resref": resref,
            "output_path": os.path.abspath(output_path),
            "width": width,
            "height": height,
            "backend": renderer.perf.get("backend", "unknown"),
        })
    except Exception as exc:
        import traceback  # noqa: PLC0415
        return json_content({"error": f"Render failed: {exc}", "traceback": traceback.format_exc()})


async def handle_model_info(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return structured model metadata as a ModelInfo contract."""
    resref = arguments.get("resref", "")
    game = arguments.get("game")
    game_path = arguments.get("game_path")
    svc = _get_services()

    try:
        path_label, model = _locate_and_parse(resref, game, game_path, svc)
    except FileNotFoundError as exc:
        return json_content({"error": str(exc)})
    except Exception as exc:
        return json_content({"error": f"Failed to parse MDL: {exc}"})

    try:
        info: ModelInfo = svc.analyzer.model_info(model, resref, path_label)
        # Convert frozen dataclass to dict for JSON serialisation
        d = {
            "resref": info.resref,
            "path": info.path,
            "node_count": info.node_count,
            "mesh_node_count": info.mesh_node_count,
            "total_vertices": info.total_vertices,
            "total_faces": info.total_faces,
            "bone_count": info.bone_count,
            "bones": info.bones,
            "animations": info.animations,
            "bounding_box": {
                "min": info.bounding_box_min,
                "max": info.bounding_box_max,
            },
            "classification": info.classification,
            "supermodel": info.supermodel,
        }
        return json_content(d)
    except Exception as exc:
        return json_content({"error": f"Info extraction failed: {exc}"})


async def handle_list_game_models(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """List MDL resources in an installation."""
    game_alias = arguments.get("game")
    game_path = arguments.get("game_path")
    name_filter = (arguments.get("filter") or "").lower()
    limit = int(arguments.get("limit", 50))
    svc = _get_services()

    game = svc.registry.resolve(game_alias)
    if game is None:
        return json_content({"error": "Specify game (k1/k2)."})

    try:
        installation = svc.registry.load(game, game_path)
        results = []
        for entry in installation.iter_resources("all"):
            if entry.restype != "MDL":
                continue
            if name_filter and name_filter not in entry.resref.lower():
                continue
            results.append({
                "resref": entry.resref,
                "source": entry.source,
                "size": entry.size,
            })
            if len(results) >= limit:
                break
        return json_content({"count": len(results), "models": results})
    except Exception as exc:
        return json_content({"error": str(exc)})


async def handle_audit(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Quick integrity check on a model — returns an AuditResult contract."""
    resref = arguments.get("resref", "")
    game = arguments.get("game")
    game_path = arguments.get("game_path")
    svc = _get_services()

    try:
        path_label, model = _locate_and_parse(resref, game, game_path, svc)
    except FileNotFoundError as exc:
        return json_content({"error": str(exc)})
    except Exception as exc:
        return json_content({"error": f"Failed to parse MDL: {exc}"})

    try:
        result: AuditResult = svc.analyzer.audit(model, resref)
        return json_content({
            "resref": result.resref,
            "status": result.status,
            "node_count": result.node_count,
            "mesh_node_count": result.mesh_node_count,
            "bounding_box_ok": result.bounding_box_ok,
            "issues": result.issues,
            "warnings": result.warnings,
        })
    except Exception as exc:
        return json_content({"error": f"Audit failed: {exc}"})


async def handle_export_model_for_unity(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Export a KotOR model into a Unity project asset folder."""
    resref = str(arguments.get("resref", "") or "").strip()
    game = arguments.get("game")
    game_path = arguments.get("game_path")
    unity_project_raw = str(arguments.get("unity_project", "") or "").strip()
    asset_subdir = str(
        arguments.get("asset_subdir") or "Assets/KotorImported/GhostRigger"
    )
    output_name = str(arguments.get("output_name", "") or "").strip() or None
    fmt = str(arguments.get("format") or "fbx").lower().lstrip(".")
    export_rigging = bool(arguments.get("export_rigging", True))
    svc = _get_services()

    if not resref:
        return json_content({"error": "resref is required."})
    if not game:
        return json_content({"error": "game is required."})
    if not unity_project_raw:
        return json_content({"error": "unity_project is required."})
    if fmt != "fbx":
        return json_content({"error": f"Unsupported Unity transfer format: {fmt}"})

    try:
        path_label, model = _locate_and_parse(resref, game, game_path, svc)
    except FileNotFoundError as exc:
        return json_content({"error": str(exc)})
    except Exception as exc:
        return json_content({"error": f"Failed to parse MDL: {exc}"})

    try:
        try:
            from src.core.unity_export_bridge import export_model_for_unity  # noqa: PLC0415
        except ImportError:                                      # pragma: no cover - MCP path shim
            from core.unity_export_bridge import export_model_for_unity  # type: ignore  # noqa: PLC0415

        result = export_model_for_unity(
            model,
            game=str(game).upper(),
            resref=resref,
            asset_name=output_name,
            unity_project=Path(unity_project_raw),
            asset_subdir=asset_subdir,
            extension=fmt,
            export_rigging=export_rigging,
            exporter=_export_fbx_for_unity,
            source_path=path_label,
        )
        return json_content(result)
    except Exception as exc:
        return json_content({"error": f"Unity export failed: {exc}"})


async def handle_validate_unity_import(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Validate Unity-side import facts against a GhostRigger transfer sidecar."""
    transfer_path = str(arguments.get("transfer_metadata_path", "") or "").strip()
    unity_summary = arguments.get("unity_summary") or {}
    output_raw = str(arguments.get("output_path", "") or "").strip()
    if not transfer_path:
        return json_content({"error": "transfer_metadata_path is required."})
    if not isinstance(unity_summary, dict):
        return json_content({"error": "unity_summary must be an object."})

    try:
        try:
            from src.core.unity_import_validator import validate_unity_import_file  # noqa: PLC0415
        except ImportError:                                      # pragma: no cover - MCP path shim
            from core.unity_import_validator import validate_unity_import_file  # type: ignore  # noqa: PLC0415

        manifest = validate_unity_import_file(
            Path(transfer_path),
            unity_summary,
            Path(output_raw) if output_raw else None,
        )
        return json_content(manifest)
    except Exception as exc:
        return json_content({"error": f"Unity import validation failed: {exc}"})


async def handle_run_malak_unity_smoke(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Run the Unity MCP Malak main-menu smoke test."""
    unity_project_raw = str(arguments.get("unity_project", "") or "").strip()
    if not unity_project_raw:
        return json_content({"error": "unity_project is required."})

    try:
        try:
            from src.core.unity_malak_smoke import (  # noqa: PLC0415
                DEFAULT_ASSET_PATH,
                DEFAULT_INSTANCE_NAME,
                DEFAULT_SCENE_PATH,
                run_malak_main_menu_smoke,
            )
        except ImportError:  # pragma: no cover - MCP path shim
            from core.unity_malak_smoke import (  # type: ignore  # noqa: PLC0415
                DEFAULT_ASSET_PATH,
                DEFAULT_INSTANCE_NAME,
                DEFAULT_SCENE_PATH,
                run_malak_main_menu_smoke,
            )

        output_raw = str(arguments.get("output_path", "") or "").strip()
        report = run_malak_main_menu_smoke(
            unity_project=Path(unity_project_raw),
            host=str(arguments.get("host") or "127.0.0.1"),
            port=int(arguments.get("port") or 6400),
            scene_path=str(arguments.get("scene_path") or DEFAULT_SCENE_PATH),
            asset_path=str(arguments.get("asset_path") or DEFAULT_ASSET_PATH),
            instance_name=str(arguments.get("instance_name") or DEFAULT_INSTANCE_NAME),
            output_path=Path(output_raw) if output_raw else None,
            screenshot_delay=float(arguments.get("screenshot_delay") or 1.0),
        )
        return json_content(report)
    except Exception as exc:
        return json_content({"error": f"Malak Unity smoke failed: {exc}"})


# ── Backward-compatible helper ────────────────────────────────────────────────

def resolve_game_safe(label: Optional[str]):
    """Resolve game label without raising (backward-compatible shim)."""
    return _get_services().registry.resolve(label)
