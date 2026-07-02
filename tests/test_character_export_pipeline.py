"""T2518 regression: the full Character Builder creature export pipeline.

Reproduces the 2026-07-01 22:38 manual export failure headlessly and locks the
fixes: OBJ import → normalize (Policy 0 correspondence fit) →
apply_template_rig (donor bind) → anatomical split (T2512) →
export_scene("kotor") must produce a written, reload-verified MDL/MDX pair.

The four T2518 fixes under test:
1. Split parts always carry qBone/tBone aligned with their palette (rebuilt
   from skeleton nodes when source arrays are misaligned).
2. The splitter re-records payload mesh names (bind metadata + frozen rig
   state) so the export transaction's provenance/payload contracts accept the
   region parts.
3. Texture resrefs longer than KOTOR's 16-char limit are renamed before any
   writer runs, and every node reference is rewritten consistently.
4. Reload verification tolerates the MDL loader's 16-slot bonemap padding
   (trailing blanks) instead of flagging every <16-bone skin node.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("trimesh")
pytest.importorskip("scipy")

from tests.test_anatomical_partition import _find_drexl_obj, _load_drexl_model

_KOTOR_RESREF_LIMIT = 16


def test_creature_obj_to_mdl_export_end_to_end() -> None:
    obj_path = _find_drexl_obj()
    if obj_path is None:
        pytest.skip("Drexl import OBJ not available")

    import src.core.characters.headless_body_workflow as wf
    from src.core.characters.character_builder import apply_template_rig
    from src.converters.mesh_converter import OBJImporter

    md = wf._import_model_data()
    donor_model = _load_drexl_model()

    mesh_model = OBJImporter().import_file(str(obj_path))
    mesh_model.name = "c_drexlf_uv"
    for node in mesh_model.all_nodes():
        if getattr(node, "vertices", None):
            node.name = "c_drexlf_uv"

    norm = wf.normalize_external_model_for_kotor(
        mesh_model,
        game_version="K2",
        reference_model=donor_model,
        reference_label="c_drexlf",
        expected_mode="creature",
    )
    assert norm["ok"], norm
    assert norm["fit_policy"] == "correspondence_surface_registration"

    rig = apply_template_rig(mesh_model, donor_model, game="K2")
    assert rig.get("ok"), rig
    rigged = rig.get("model") or donor_model

    split = wf.split_skinned_mesh_nodes_with_weight_remap(
        rigged, _load_drexl_model()
    )
    assert split["ok"], split
    parts = [
        n for n in rigged.all_nodes() if getattr(n, "_gr_weight_remap_split", False)
    ]
    assert len(parts) >= 4

    # Fix 1: bind arrays always aligned with the palette.
    for part in parts:
        assert len(part.qbone_list) == len(part.bone_map), part.name
        assert len(part.tbone_list) == len(part.bone_map), part.name
        assert all(str(b or "").strip() for b in part.bone_map), part.name

    # Fix 2: payload provenance re-recorded as the region parts.
    from src.core.characters.character_rig_state import get_character_rig_state

    state = get_character_rig_state(rigged)
    assert state is not None
    part_names = {str(p.name) for p in parts}
    assert part_names <= set(state.payload_mesh_names), (
        state.payload_mesh_names,
        part_names,
    )

    entry = SimpleNamespace(model=rigged, resref="c_drexlf", source_path=str(obj_path))
    scene = SimpleNamespace(
        game_version="K2",
        metadata={},
        get=lambda slot: entry if slot == md.PartSlot.HEADLESS_BODY else None,
    )
    out_dir = tempfile.mkdtemp(prefix="gr_t2518_export_")
    result = wf.export_scene(
        scene, formats=["kotor"], out_dir=out_dir, write_sidecar=False,
        skip_validation=True,
    )
    assert result.ok, (result.code, result.message,
                       [(r.key, r.message) for r in result.formats or []])

    files = {p.name for p in Path(out_dir).iterdir()}
    assert "c_drexlf.mdl" in files and "c_drexlf.mdx" in files, files
    assert (Path(out_dir) / "c_drexlf.mdl").stat().st_size > 1024

    # Fix 3: every texture resref on the exported model fits the engine limit
    # and the rename mapping was recorded for the texture exporter.
    for node in rigged.all_nodes():
        for field in ("texture", "lightmap"):
            name = str(getattr(node, field, "") or "")
            assert len(name) <= _KOTOR_RESREF_LIMIT, (node.name, field, name)
    renames = scene.metadata.get("texture_resref_renames", {})
    assert renames, "over-long OBJ texture name should have been renamed"
    for new_name, original in renames.items():
        assert len(new_name) <= _KOTOR_RESREF_LIMIT
        assert len(original) > _KOTOR_RESREF_LIMIT
