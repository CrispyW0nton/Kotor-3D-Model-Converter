from __future__ import annotations

from src.gui.viewports.viewport_core.widgets.selection_mesh import ViewportSelectionMeshMixin


class _Node:
    def __init__(self, name: str, pos: tuple[float, float, float]) -> None:
        self.name = name
        self.position = pos

    def bone_world_position(self) -> tuple[float, float, float]:
        return tuple(float(v) for v in self.position)


class _Viewport(ViewportSelectionMeshMixin):
    def __init__(self) -> None:
        self._positions = []
        self._evicted = []
        self._render_requested = False
        self._joint_drag_node = None
        self._joint_drag_nodes = []
        self._joint_drag_mirror_nodes = []

    def _joint_hit_positions(self) -> list:
        return list(self._positions)

    def _is_external_skeleton_node(self, _node) -> bool:
        return False

    def _evict_transform_cache(self, node) -> None:
        self._evicted.append(node)

    def _request_render(self, **_kwargs) -> None:
        self._render_requested = True


def test_hold_v_joint_snap_excludes_dragged_node_and_moves_to_visible_target() -> None:
    viewport = _Viewport()
    dragged = _Node("lhand", (0.0, 0.0, 0.0))
    target = _Node("bendak_lhand", (2.0, 3.0, 4.0))
    viewport._joint_drag_node = dragged
    viewport._joint_drag_nodes = [dragged]
    viewport._positions = [
        (100, 100, 0.5, dragged),
        (112, 106, 0.5, target),
    ]

    assert viewport._snap_joint_drag_to_visible_bone_at_cursor(112, 106) is True

    assert dragged.position == (2.0, 3.0, 4.0)
    assert viewport._evicted == [dragged]
    assert viewport._render_requested is True


def test_hold_v_joint_snap_mirrors_delta_for_symmetry_partner() -> None:
    viewport = _Viewport()
    dragged = _Node("lhand", (0.0, 0.0, 0.0))
    mirror = _Node("rhand", (10.0, 0.0, 0.0))
    target = _Node("bendak_lhand", (2.0, 3.0, 4.0))
    viewport._joint_drag_node = dragged
    viewport._joint_drag_nodes = [dragged]
    viewport._joint_drag_mirror_nodes = [mirror]
    viewport._positions = [
        (100, 100, 0.5, dragged),
        (112, 106, 0.5, target),
        (130, 106, 0.5, mirror),
    ]

    assert viewport._snap_joint_drag_to_visible_bone_at_cursor(112, 106) is True

    assert dragged.position == (2.0, 3.0, 4.0)
    assert mirror.position == (8.0, 3.0, 4.0)
