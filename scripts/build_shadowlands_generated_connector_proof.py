"""Build a focused proof for a reviewed stock room with no shipped WOK portal."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402


for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))


OUT_DIR = ROOT / "artifacts" / "shadowlands_proof" / "generated_connector"
KMAP_PATH = OUT_DIR / "grgenerated.kmap"
REPORT_PATH = OUT_DIR / "structural_proof.json"


def _game_dir() -> Path:
    settings_path = ROOT / "settings.json"
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        configured = Path(str(settings.get("k1_dir") or ""))
        if (configured / "chitin.key").is_file():
            return configured
    configured = Path(os.environ.get("K1_PATH", ""))
    if (configured / "chitin.key").is_file():
        return configured
    fallback = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
    if (fallback / "chitin.key").is_file():
        return fallback
    raise FileNotFoundError("A KOTOR 1 installation is required for the proof.")


def main() -> int:
    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload
    from src.core.modules.authored_module_walkmesh import compile_authored_room_connection_walkmeshes
    from src.core.modules.module_editor_controller import ModuleEditorController

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resources = ResourceManager()
    if not resources.set_k1_dir(str(_game_dir())):
        raise RuntimeError("Could not load the configured KOTOR 1 installation.")

    controller = ModuleEditorController()
    controller.new_project(name="grgenerated", game="K1")
    clearing = controller.add_map_studio_building_room(
        points=((0.0, 0.0), (24.0, 0.0), (24.0, 20.0), (0.0, 20.0)),
        wall_height=6.0,
        style_id="architecture:k1_shadowlands",
    )
    stock = controller.add_authored_environment_kit_piece(
        piece_id="k1_m23aa_m23aa_04a",
        position=(12.0, 20.0, 0.0),
        target_room_resref=clearing,
        resource_manager=resources,
    )
    controller.set_authored_module_entry_point(
        position=(12.0, 14.0, 0.05),
        facing=math.pi * 0.5,
    )
    authored = authored_project_from_kmap_payload(controller.project.extra_sections["authored_module"])
    build = compile_authored_room_connection_walkmeshes(authored)
    stock_room = next(room for room in authored.rooms if room.normalised_resref() == stock)
    generated_wok = dict(stock_room.primitive.metadata.get("wok_auto_generated") or {})
    closure = dict(stock_room.primitive.metadata.get("environment_kit_exterior_closure") or {})
    rebase = dict(stock_room.primitive.metadata.get("environment_kit_generated_rebase") or {})
    report = {
        "result": "PASS",
        "proof": "Pascal Shadowlands clearing -> generated connector -> stock m23aa_04a chamber",
        "kmap": str(KMAP_PATH),
        "rooms": [room.normalised_resref() for room in authored.rooms],
        "stock_position": [float(value) for value in stock_room.position],
        "stock_wok_faces": len(tuple(stock_room.primitive.wok.faces or ())),
        "generated_wok_validation": generated_wok.get("structural_validation"),
        "rebase_policy": rebase.get("policy"),
        "portal_count": len(build.portals),
        "portal_midpoint_gaps": [float(portal.midpoint_gap) for portal in build.portals],
        "wall_generation_policy": closure.get("wall_generation_policy"),
        "sealed_boundary_edges": int(closure.get("sealed_boundary_edges", 0) or 0),
        "preserved_stock_wall_edges": int(closure.get("preserved_stock_wall_edges", 0) or 0),
    }
    required = (
        build.ready,
        len(build.portals) == 1,
        max(report["portal_midpoint_gaps"], default=1.0) <= 2.0e-5,
        report["generated_wok_validation"] == "passed",
        report["rebase_policy"] == "walkmesh_center_xy_and_minimum_z_to_room_origin",
        report["wall_generation_policy"] == "exposed_wok_boundary_only",
        max(abs(value) for value in report["stock_position"]) < 60.0,
    )
    if not all(required):
        report["result"] = "FAIL"
    controller.save_project(KMAP_PATH)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
