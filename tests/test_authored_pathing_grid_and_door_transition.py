"""Two export-blocking regressions found while shipping 921srt.

1. Path-graph generation scanned every walkmesh face for every sampled
   point, so a floor-filled converted module (thousands of faces) stalled
   export for many minutes. An XY face grid makes it fast and must return the
   same graph the linear scan produced.
2. A door with TransitionDestin = -1 (the standard "no transition text"
   sentinel most stock doors carry) was rejected as an invalid negative
   value, blocking export of every ordinary open/close door.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _dense_grid_wok(n: int):
    """An n x n grid of walkable quads (2*n*n faces) as a WOKData."""
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(name="dense")
    index: dict[tuple[int, int], int] = {}
    for gx in range(n + 1):
        for gy in range(n + 1):
            index[(gx, gy)] = len(wok.verts)
            wok.verts.append((float(gx), float(gy), 0.0))
    for gx in range(n):
        for gy in range(n):
            a = index[(gx, gy)]
            b = index[(gx + 1, gy)]
            c = index[(gx + 1, gy + 1)]
            d = index[(gx, gy + 1)]
            wok.faces.append(WOKFace(a, b, c, 1, -1, -1, -1))
            wok.faces.append(WOKFace(a, c, d, 1, -1, -1, -1))
    return wok


def test_face_grid_matches_linear_scan_and_is_fast() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_pathing import _WalkmeshFaceGrid
    from src.core.modules.authored_walkmesh_sampling import walkmesh_face_at_xy

    wok = _dense_grid_wok(40)  # 3200 faces
    grid = _WalkmeshFaceGrid(wok)
    # Grid answers agree with the linear scan on interior sample points.
    for gx in range(40):
        for gy in range(0, 40, 7):
            x, y = gx + 0.25, gy + 0.75
            linear = walkmesh_face_at_xy(wok, x, y)
            g = grid.face_at(x, y)
            assert g == linear, f"grid {g} != linear {linear} at ({x},{y})"
    # A point outside the mesh returns -1 from both.
    assert grid.face_at(-5.0, -5.0) == -1
    # The grid resolves many queries far faster than a linear scan would.
    t0 = time.perf_counter()
    for _ in range(2000):
        grid.face_at(19.3, 19.7)
    grid_time = time.perf_counter() - t0
    assert grid_time < 0.5  # 2000 dense-mesh queries in well under a second


def test_face_grid_matches_linear_scan_for_non_finite_and_epsilon_boundary_queries() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_pathing import _WalkmeshFaceGrid
    from src.core.modules.authored_walkmesh_sampling import walkmesh_face_at_xy
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        name="epsilon",
        verts=[(1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 1.0, 0.0)],
        faces=[WOKFace(0, 1, 2, 1, -1, -1, -1)],
    )
    grid = _WalkmeshFaceGrid(wok)
    for x, y in ((float("nan"), 0.2), (float("inf"), 0.2), (1.2, float("-inf"))):
        assert grid.face_at(x, y) == walkmesh_face_at_xy(wok, x, y) == -1
    x, y = 1.0 - 1.0e-8, 0.2
    assert grid.face_at(x, y) == walkmesh_face_at_xy(wok, x, y) == 0


def test_path_graph_generation_on_dense_walkmesh_is_quick() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_pathing import build_authored_path_graph_from_walkmesh

    wok = _dense_grid_wok(45)  # ~4050 faces, like a floor-filled room set
    t0 = time.perf_counter()
    graph = build_authored_path_graph_from_walkmesh(wok)
    elapsed = time.perf_counter() - t0
    assert graph.points  # one connected walkable component -> at least one center
    assert elapsed < 10.0, f"path graph took {elapsed:.1f}s on a dense walkmesh"


def test_path_graph_never_links_overlapping_xy_walkmesh_components_at_different_heights() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_pathing import build_authored_path_graph_from_walkmesh
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(name="stacked")
    for z, x0, x1 in ((0.0, 0.0, 10.0), (5.0, 5.0, 15.0)):
        base = len(wok.verts)
        wok.verts.extend(((x0, 0.0, z), (x1, 0.0, z), (x1, 10.0, z), (x0, 10.0, z)))
        wok.faces.extend(
            (
                WOKFace(base, base + 1, base + 2, 1, -1, -1, -1),
                WOKFace(base, base + 2, base + 3, 1, -1, -1, -1),
            )
        )
    wok.rebuild_adjacencies()

    graph = build_authored_path_graph_from_walkmesh(wok)
    assert graph.metadata["walkmesh_component_count"] == 2
    assert len(graph.points) == 2
    assert graph.connections == ()


def test_path_graph_keeps_coincident_coordinate_index_seams_disconnected() -> None:
    """A visual seam is not a traversable WOK/PTH connection."""

    _configure_native_python_roots()
    from src.core.modules.authored_module_pathing import build_authored_path_graph_from_walkmesh
    from src.core.modules.module_format import WOKData, WOKFace

    # The two triangles occupy the two halves of one square and their diagonal
    # endpoints are coordinate-identical.  Distinct vertex indices make that
    # diagonal an intentional Odyssey collision seam.
    wok = WOKData(
        name="index_seam",
        verts=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        faces=[WOKFace(0, 1, 2, 1), WOKFace(3, 4, 5, 1)],
    )

    graph = build_authored_path_graph_from_walkmesh(wok)

    assert graph.metadata["walkmesh_component_count"] == 2
    assert len(graph.points) == 2
    assert {point.metadata["component_index"] for point in graph.points} == {0, 1}
    assert graph.connections == ()


def _door(*, transition_destination: int, linked_to: str = "", linked_to_flags: int = 0):
    from src.core.modules.authored_module_objects import AuthoredDoorInstance

    return AuthoredDoorInstance(
        template_resref="door_mal02",
        tag="MalachorDoor02",
        position=(0.0, 0.0, 3.0),
        bearing=0.0,
        linked_to=linked_to,
        linked_to_flags=linked_to_flags,
        transition_destination=transition_destination,
    )


def test_door_transition_destination_minus_one_is_accepted() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_objects import _validate_transition_intent

    blocking: list[str] = []
    _validate_transition_intent("Door", _door(transition_destination=-1), blocking)
    assert blocking == [], blocking  # plain open/close door: no transition, no error


def test_door_transition_destination_below_sentinel_still_blocks() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_objects import _validate_transition_intent

    blocking: list[str] = []
    _validate_transition_intent("Door", _door(transition_destination=-2), blocking)
    assert any("invalid TransitionDestin" in message for message in blocking)


def test_door_with_transition_text_but_no_link_is_flagged() -> None:
    _configure_native_python_roots()
    from src.core.modules.authored_module_objects import _validate_transition_intent

    blocking: list[str] = []
    _validate_transition_intent("Door", _door(transition_destination=1000), blocking)
    assert any("incomplete transition" in message for message in blocking)
