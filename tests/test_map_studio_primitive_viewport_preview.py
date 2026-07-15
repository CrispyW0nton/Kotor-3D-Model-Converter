from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


def _install_gui_payload_path() -> None:
    repo = Path(__file__).resolve().parents[1]
    for relative in (
        "native/GhostRigger.Core.GUI.Display/Python/src",
        "native/GhostRigger.Core.Tools/Python/src",
        ".",
    ):
        path = str((repo / relative).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


class _Node:
    def __init__(self, room: str, primitive: str, offset: float) -> None:
        self.name = primitive
        self._gr_map_studio_room_resref = room
        self._gr_map_studio_primitive_name = primitive
        self.vertices = [(offset, 0.0, 0.0), (offset + 1.0, 0.0, 0.0), (offset, 1.0, 0.0)]
        self.faces = [(0, 1, 2)]
        self.normals = [(0.0, 0.0, 1.0)] * 3
        self.uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        self.uvs_lm = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        self.face_mats = [0]
        self.bounds_updates = 0

    def compute_bounds(self) -> None:
        self.bounds_updates += 1


def _panel(nodes):
    _install_gui_payload_path()
    from gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    requests: list[dict] = []
    evictions: list[object] = []
    viewport = SimpleNamespace(
        _evict_transform_cache=lambda node: evictions.append(node),
        _request_render=lambda **kwargs: requests.append(dict(kwargs)),
        model=SimpleNamespace(),
    )
    panel = SimpleNamespace(
        viewport=viewport,
        _room_preview_model=SimpleNamespace(),
        _room_preview_model_key="before",
        _primitive_recipe_preview_baselines={},
        _primitive_recipe_commit_serial=0,
        _hover_candidate_cache_key="stale",
        _hover_candidate_cache=[object()],
        _hover_candidate_grid={1: object()},
        _component_mesh_preview_baselines={1: object()},
        _pending_room_primitive_commit_preview=object(),
        _iter_room_preview_mesh_nodes=lambda room: tuple(
            (SimpleNamespace(), node)
            for node in nodes
            if node._gr_map_studio_room_resref.lower() == str(room).lower()
        ),
        _sync_room_preview_model=lambda model: None,
        _push_map_studio_component_selection=lambda: None,
    )
    return ModuleEditorViewportPanel, panel, requests, evictions


def _payload(name: str, *, empty_uvs: bool = False) -> tuple[dict, ...]:
    return (
        {
            "mesh_name": name,
            "vertices": ((5.0, 0.0, 0.0), (7.0, 0.0, 0.0), (5.0, 2.0, 0.0)),
            "faces": ((0, 1, 2),),
            "normals": ((0.0, 0.0, 1.0),) * 3,
            "uvs": () if empty_uvs else ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
            "uvs_lm": (),
            "face_mats": (2,),
        },
    )


def test_primitive_recipe_preview_is_scoped_cancelable_and_uv_none_safe() -> None:
    selected = _Node("room01", "polyCube1", 0.0)
    sibling = _Node("room01", "polyCube2", 10.0)
    original = tuple(selected.vertices)
    sibling_original = tuple(sibling.vertices)
    cls, panel, requests, evictions = _panel((selected, sibling))

    assert cls.apply_primitive_recipe_preview(
        panel, "room01", "polyCube1", _payload("polyCube1", empty_uvs=True)
    ) is True
    assert selected.vertices[0] == (5.0, 0.0, 0.0)
    assert selected.uvs == []
    assert tuple(sibling.vertices) == sibling_original
    assert len(panel._primitive_recipe_preview_baselines) == 1
    assert selected in evictions
    assert requests[-1]["reason"] == "Map Studio primitive recipe preview"

    cls.clear_primitive_recipe_preview(panel)
    assert tuple(selected.vertices) == original
    assert tuple(sibling.vertices) == sibling_original
    assert panel._primitive_recipe_preview_baselines == {}
    assert requests[-1]["reason"] == "Map Studio primitive recipe preview restored"


def test_primitive_recipe_preview_promote_retains_arrays_and_replacement_discards_baseline() -> None:
    selected = _Node("room01", "polyCube1", 0.0)
    cls, panel, requests, _evictions = _panel((selected,))
    assert cls.apply_primitive_recipe_preview(panel, "room01", "polyCube1", _payload("polyCube1"))
    preview_vertices = tuple(selected.vertices)

    assert cls.promote_primitive_recipe_preview(panel, "room01", "polyCube1") is True
    assert tuple(selected.vertices) == preview_vertices
    assert panel._primitive_recipe_preview_baselines == {}
    assert panel._room_preview_model_key.startswith("resident-primitive-recipe:room01:polyCube1:")
    assert requests[-1]["reason"] == "Map Studio primitive recipe committed"

    assert cls.apply_primitive_recipe_preview(panel, "room01", "polyCube1", _payload("polyCube1"))
    cls.set_authored_room_preview_model(panel, SimpleNamespace(name="replacement"))
    assert panel._primitive_recipe_preview_baselines == {}
    assert panel._component_mesh_preview_baselines == {}
    assert panel._pending_room_primitive_commit_preview is None


def test_primitive_recipe_preview_missing_or_ambiguous_node_requests_caller_fallback() -> None:
    first = _Node("room01", "polyCube1", 0.0)
    duplicate = _Node("room01", "polyCube1", 3.0)
    cls, panel, _requests, _evictions = _panel((first, duplicate))

    assert cls.apply_primitive_recipe_preview(panel, "room01", "missing", _payload("missing")) is False
    assert cls.apply_primitive_recipe_preview(panel, "room01", "polyCube1", _payload("polyCube1")) is False
    assert panel._primitive_recipe_preview_baselines == {}
