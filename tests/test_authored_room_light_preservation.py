"""Stock-converted rooms keep their baked lights on export.

Making a stock room editable flattens it and drops its model lights; the
export gate refused to silently ship unlit rooms. Since the user's edits
(moved placeables, filled walkmesh) never touch room render geometry, the
export now reuses each room's original imported MDL/MDX verbatim (lights,
animations, emitters intact) and ships the edited .wok alongside. The IFO
engine-contract check no longer demands GhostRigger's identity/tag when the
stock IFO is preserved.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_render_geometry_edited_flag_gates_preservation() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_export import _room_render_geometry_edited

    pristine = SimpleNamespace(primitive=SimpleNamespace(metadata={"source": "stock_room_conversion"}))
    edited = SimpleNamespace(primitive=SimpleNamespace(metadata={"render_geometry_edited": True}))
    assert _room_render_geometry_edited(pristine) is False
    assert _room_render_geometry_edited(edited) is True


def test_unedited_stock_room_is_preservation_eligible_even_without_runtime_graph_counts() -> None:
    _configure_native_python_roots()
    from dataclasses import replace

    from src.core.modules.authored_imported_mesh import ImportedMeshRoomPrimitive
    from src.core.modules.authored_module_export import _room_is_eligible_for_stock_model_preservation

    primitive = ImportedMeshRoomPrimitive(
        room_resref="plainroom",
        surfaces=(),
        source_model="plainroom",
        metadata={"source_runtime_graph": {"light_count": 0}},
    )
    room = SimpleNamespace(primitive=primitive, metadata={"source": "stock_room_conversion"})
    assert _room_is_eligible_for_stock_model_preservation(room) is True
    edited = SimpleNamespace(
        primitive=replace(primitive, metadata={**primitive.metadata, "render_geometry_edited": True}),
        metadata=room.metadata,
    )
    assert _room_is_eligible_for_stock_model_preservation(edited) is False


def test_preserved_stock_room_model_reads_import_source(tmp_path) -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_export import _preserved_stock_room_model

    # No import_source -> None (nothing to preserve).
    project = SimpleNamespace(extra={})
    assert _preserved_stock_room_model(project, "921srtb") is None
    # A real capsule with the room's MDL/MDX returns those exact bytes.
    real_mod = Path(r"C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\Candidates\921srt\K2\Modules\921srt.mod")
    if not real_mod.is_file():
        return
    project = SimpleNamespace(extra={"import_source": str(real_mod)})
    result = _preserved_stock_room_model(project, "921srtb")
    assert result is not None
    mdl, mdx = result
    assert mdl[:4] == b"\x00\x00\x00\x00" or len(mdl) > 100  # MDL binary prefix
    assert len(mdx) > 0


def test_ifo_contract_accepts_preserved_stock_identity() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_metadata import build_authored_ifo_bytes
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from src.core.modules.dev_module_smoke import _verify_ifo_engine_contract

    # Build a GhostRigger IFO but with a foreign Mod_ID and non-MODULE tag,
    # like a preserved stock module (921srt: real id + odd Mod_Tag).
    from pykotor.resource.formats.gff import bytes_gff, read_gff

    ifo = build_authored_ifo_bytes(
        AuthoredModuleMetadata(module_root="921srt", game="K2", display_name="921srt", tag="921srt"),
        ModuleEntryPoint(area_resref="921srt"),
        area_resrefs=("921srt",),
    )
    gff = read_gff(ifo)
    gff.root.set_binary("Mod_ID", bytes.fromhex("ed8ae69ee373711c96f1c53ad1cb0ff5"))
    gff.root.set_string("Mod_Tag", "ImTraskUlgoensignwiththeRepublic")
    foreign_ifo = bytes(bytes_gff(gff))

    # Not preserved: the foreign identity/tag are flagged.
    strict: list[str] = []
    _verify_ifo_engine_contract(foreign_ifo, "921srt", strict, ifo_preserved=False)
    assert any("Mod_ID does not match" in m for m in strict)
    assert any("Mod_Tag must be stock-style MODULE" in m for m in strict)

    # Preserved: the original module's identity/tag are authoritative.
    preserved: list[str] = []
    _verify_ifo_engine_contract(foreign_ifo, "921srt", preserved, ifo_preserved=True)
    assert not any("Mod_ID does not match" in m for m in preserved)
    assert not any("Mod_Tag must be stock-style MODULE" in m for m in preserved)
