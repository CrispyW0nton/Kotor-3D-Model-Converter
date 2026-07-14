"""Focused proof: stock creature previews graft appearance.2da heads.

Body-part (modeltype B) creatures carry no head geometry in their body MDL;
the engine grafts appearance.2da ``normalhead`` -> heads.2da ``head`` at the
body's ``headhook``.  The Map Studio stock preview must mirror that so loaded
maps such as 207tel do not render headless NPCs.  Verified against the real
install on 2026-07-12: 23/32 placed 207tel creatures resolve separate heads
(e.g. 203_ramana -> body n_twilekf + head twilek_f).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


class _StubTable:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    def get(self, row: int, column: str, default: str = "") -> str:
        try:
            return self._rows[row].get(column, default)
        except IndexError:
            return default


def _resolver_with_stub_tables(monkeypatch):
    from src.core.modules import map_studio_stock_content_preview as preview

    resolver = preview.TemplateModelResolver(None, "K2")
    tables = {
        "appearance": _StubTable([
            {"modeltype": "B", "modela": "n_twilekf", "normalhead": "1"},
            {"modeltype": "F", "race": "c_drdprot", "modela": "", "normalhead": "3"},
            {"modeltype": "B", "modela": "n_commm", "normalhead": "****"},
            {
                "modeltype": "F",
                "race": "n_rodian",
                "racetex": "N_Rodian02",
                "modela": "",
                "normalhead": "",
            },
        ]),
        "heads": _StubTable([
            {"head": "pmha01"},
            {"head": "twilek_f"},
        ]),
    }
    monkeypatch.setattr(resolver, "_table", lambda name: tables.get(str(name).lower()))
    utcs = {
        "ramana": {"Appearance_Type": 0},
        "droid": {"Appearance_Type": 1},
        "noheadrow": {"Appearance_Type": 2},
        "rodian": {"Appearance_Type": 3},
        "badrow": {"Appearance_Type": 99},
    }
    monkeypatch.setattr(resolver, "_template_bytes", lambda resref, res_type: b"stub" if resref in utcs else None)
    monkeypatch.setattr(preview, "_read_gff_fields", lambda raw, _utcs=utcs: None)
    # _read_gff_fields is looked up at module level inside creature methods;
    # patch it to map the requested template through the stub UTC table.
    state = {"current": ""}

    def fake_template_bytes(resref, res_type):
        state["current"] = str(resref)
        return b"stub" if str(resref) in utcs else None

    monkeypatch.setattr(resolver, "_template_bytes", fake_template_bytes)
    monkeypatch.setattr(preview, "_read_gff_fields", lambda raw: utcs.get(state["current"]))
    return resolver


def test_creature_head_resolves_normalhead_through_heads_table(monkeypatch) -> None:
    _configure_native_python_roots()
    resolver = _resolver_with_stub_tables(monkeypatch)
    assert resolver.creature_model("ramana") == "n_twilekf"
    assert resolver.creature_head_model("ramana") == "twilek_f"
    assert resolver.head_model_for_placement_kind("creature", "ramana") == "twilek_f"


def test_full_body_and_headless_rows_resolve_no_head(monkeypatch) -> None:
    _configure_native_python_roots()
    resolver = _resolver_with_stub_tables(monkeypatch)
    # Full-body appearance (modeltype F): no separate head even though the
    # row carries a normalhead index.
    assert resolver.creature_model("droid") == "c_drdprot"
    assert resolver.creature_head_model("droid") == ""
    # Blank/**** normalhead cells and invalid rows resolve safely to "".
    assert resolver.creature_head_model("noheadrow") == ""
    assert resolver.creature_head_model("badrow") == ""
    assert resolver.creature_head_model("missing_utc") == ""
    assert resolver.head_model_for_placement_kind("placeable", "ramana") == ""


def test_full_body_racetex_resolves_verbatim_without_body_variation_suffix(monkeypatch) -> None:
    """Modeltype-F RaceTex is a complete instance texture resref."""

    _configure_native_python_roots()
    resolver = _resolver_with_stub_tables(monkeypatch)

    assert resolver.creature_model("rodian") == "n_rodian"
    assert resolver.creature_body_texture("rodian") == "n_rodian02"
    assert resolver.body_texture_for_placement_kind("creature", "rodian") == "n_rodian02"
    assert resolver.creature_body_texture("ramana") == ""


def test_stock_full_body_racetex_overrides_every_flattened_mesh_without_mutating_source() -> None:
    """Static Map Studio preview mirrors Odyssey's actor-wide RaceTex state."""

    _configure_native_python_roots()
    from types import SimpleNamespace

    from src.core.geometry import model_data as md
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    root = md.ModelNode(name="n_rodian", flags=int(md.NodeFlags.HEADER))
    null_skin = md.ModelNode(
        name="torso02",
        flags=int(md.NodeFlags.MESH) | int(md.NodeFlags.SKIN),
        parent=root,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="null",
    )
    authored_fallback = md.ModelNode(
        name="Hair",
        flags=int(md.NodeFlags.MESH),
        parent=root,
        vertices=[(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="n_rodian01",
    )
    root.children = [null_skin, authored_fallback]
    source = md.KotorModel(name="n_rodian", root_node=root)

    class Resolver:
        @staticmethod
        def model_for_placement_kind(kind: str, template_resref: str) -> str:
            return "n_rodian" if kind == "creature" else ""

        @staticmethod
        def body_texture_for_placement_kind(kind: str, template_resref: str) -> str:
            return "n_rodian02" if kind == "creature" else ""

        @staticmethod
        def head_model_for_placement_kind(kind: str, template_resref: str) -> str:
            return ""

    placement = SimpleNamespace(
        placement_id="creature:g_exthgr",
        kind="creature",
        template_resref="g_exthgr",
        creature_source_template_resref="g_exthgr",
        position=(0.0, 0.0, 0.0),
        bearing=0.0,
        is_spatial=True,
    )
    preview_root = md.ModelNode(name="preview", flags=int(md.NodeFlags.HEADER))
    result = append_stock_content_to_preview_root(
        md,
        preview_root,
        placements=(placement,),
        game="K2",
        model_loader=lambda resref: source if str(resref).lower() == "n_rodian" else None,
        resolver=Resolver(),
    )

    assert result.resolved_placement_ids == ("creature:g_exthgr",)
    group = preview_root.children[0]
    assert group._gr_map_studio_body_texture_resref == "n_rodian02"
    assert {mesh.texture_clean for mesh in group.children} == {"n_rodian02"}
    assert all(mesh._gr_instance_texture_override == "n_rodian02" for mesh in group.children)
    assert null_skin.texture_clean == "null"
    assert authored_fallback.texture_clean == "n_rodian01"


def test_head_graft_preserves_headhook_orientation_without_extra_flip() -> None:
    """The complete placement path uses body headhook space exactly once."""

    _configure_native_python_roots()
    import math
    from types import SimpleNamespace

    from src.core.geometry import model_data as md
    from src.core.modules.map_studio_stock_content_preview import append_stock_content_to_preview_root

    def mesh_node(name: str) -> object:
        return md.ModelNode(
            name=name,
            flags=int(md.NodeFlags.MESH),
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.25, 0.0)],
            normals=[(0.0, 0.0, 1.0)] * 3,
            uvs=[(0.0, 0.0)] * 3,
            faces=[(0, 1, 2)],
        )

    body_root = md.ModelNode(name="body_root", flags=int(md.NodeFlags.HEADER))
    body_mesh = mesh_node("body_geom")
    body_mesh.parent = body_root
    half = math.pi / 4.0
    headhook = md.ModelNode(
        name="headhook",
        flags=int(md.NodeFlags.HEADER),
        position=(0.0, 0.0, 1.5),
        rotation=(0.0, 0.0, math.sin(half), math.cos(half)),
    )
    headhook.parent = body_root
    body_root.children.extend((body_mesh, headhook))
    body_model = md.KotorModel(name="stub_body", root_node=body_root)

    head_root = md.ModelNode(name="head_root", flags=int(md.NodeFlags.HEADER))
    head_mesh = mesh_node("head_geom")
    head_mesh.parent = head_root
    head_root.children.append(head_mesh)
    head_model = md.KotorModel(name="stub_head", root_node=head_root)

    class Resolver:
        @staticmethod
        def model_for_placement_kind(kind: str, template_resref: str) -> str:
            return "stub_body" if kind == "creature" else ""

        @staticmethod
        def head_model_for_placement_kind(kind: str, template_resref: str) -> str:
            return "stub_head" if kind == "creature" else ""

    placement = SimpleNamespace(
        placement_id="creature:stub",
        kind="creature",
        template_resref="stub_creature",
        creature_source_template_resref="",
        position=(0.0, 0.0, 0.0),
        bearing=math.pi / 2.0,
        is_spatial=True,
    )
    preview_root = md.ModelNode(name="preview_root", flags=int(md.NodeFlags.HEADER))
    models = {"stub_body": body_model, "stub_head": head_model}

    result = append_stock_content_to_preview_root(
        md,
        preview_root,
        placements=(placement,),
        game="K2",
        model_loader=lambda resref: models.get(str(resref).lower()),
        resolver=Resolver(),
    )

    assert result.resolved_placement_ids == ("creature:stub",)
    group = preview_root.children[0]
    graft = next(node for node in group.children if node._gr_map_studio_mesh_role == "stock_creature_head_0")
    # (1, 0, 0) receives headhook +90Z, then placement bearing +90Z:
    # (1, 0, 0) -> (0, 1, 1.5) -> (-1, 0, 1.5). An extra 180Z
    # half-turn would incorrectly place it at (+1, 0, 1.5).
    assert abs(graft.vertices[1][0] + 1.0) < 1.0e-6
    assert abs(graft.vertices[1][1]) < 1.0e-6
    assert abs(graft.vertices[1][2] - 1.5) < 1.0e-6


def test_flattener_pre_transform_offsets_and_rotates_head_meshes() -> None:
    _configure_native_python_roots()
    import math

    from src.core.geometry import model_data as md
    from src.core.modules.map_studio_stock_content_preview import _flattened_mesh_nodes

    head_mesh = md.ModelNode(
        name="head_geom",
        flags=int(md.NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0)] * 3,
        faces=[(0, 1, 2)],
    )
    root = md.ModelNode(name="head_root", flags=int(md.NodeFlags.HEADER))
    head_mesh.parent = root
    root.children.append(head_mesh)
    head_model = md.KotorModel(name="stub_head", root_node=root)

    group = md.ModelNode(name="group", flags=int(md.NodeFlags.HEADER))
    hook_position = (0.0, 0.1, 1.6)
    half = math.pi / 4.0  # 90-degree Z rotation
    hook_rotation = (0.0, 0.0, math.sin(half), math.cos(half))
    meshes = _flattened_mesh_nodes(
        md,
        head_model,
        group,
        group_resref="authored:creature:i_x",
        role="stock_creature_head",
        pre_transform=(hook_position, hook_rotation),
    )
    assert len(meshes) == 1
    assert meshes[0]._gr_map_studio_mesh_role == "stock_creature_head_0"
    baked = meshes[0].vertices
    # Vertex (1, 0, 0) rotates to (0, 1, 0) then translates by the hook.
    assert abs(baked[1][0] - 0.0) < 1.0e-6
    assert abs(baked[1][1] - 1.1) < 1.0e-6
    assert abs(baked[1][2] - 1.6) < 1.0e-6
    # The origin vertex lands exactly on the hook position.
    assert all(abs(baked[0][axis] - hook_position[axis]) < 1.0e-6 for axis in range(3))
