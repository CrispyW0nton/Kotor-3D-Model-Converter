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
        _project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)

        from src.gui.gpu_renderer import GpuRenderer  # noqa: PLC0415
        from src.gui.viewport import ArcBallCamera    # noqa: PLC0415

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
        img = renderer.render(model, camera, width, height)

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


# ── Backward-compatible helper ────────────────────────────────────────────────

def resolve_game_safe(label: Optional[str]):
    """Resolve game label without raising (backward-compatible shim)."""
    return _get_services().registry.resolve(label)
