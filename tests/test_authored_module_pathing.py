import sys
from pathlib import Path


def _install_native_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "native/GhostRigger.Core.Scene.Modules/Python",
        "native/GhostRigger.Core.Resources.Game/Python",
        "native/GhostRigger.Core.Scene/Python",
        "native/GhostRigger.Core.Scene.Walkmesh/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Math/Python",
        "native/GhostRigger.Core.Rendering.Lighting/Python",
        ".",
    ):
        path = str((repo / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def test_t2608_compiles_walkmesh_anchor_pathing_to_pth() -> None:
    _install_native_payload_paths()

    from pykotor.resource.generics.pth import read_pth
    from src.core.modules.authored_module_pathing import AuthoredPathAnchor, compile_authored_pathing_for_module
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_wok

    wok = build_rectangular_room_wok(RectangularRoomPrimitive(room_resref="grdev01_room01"))

    compiled = compile_authored_pathing_for_module(
        wok,
        anchors=(
            AuthoredPathAnchor("player_start", (0.0, -3.0, 0.0)),
            AuthoredPathAnchor("test_placeable", (1.75, 1.5, 0.0)),
        ),
    )
    pth = read_pth(compiled.pth_bytes)

    assert compiled.validation.ok is True
    assert compiled.metadata["source"] == "src.core.modules.authored_module_pathing"
    assert compiled.metadata["point_count"] == 3
    assert compiled.metadata["connection_count"] == 6
    assert compiled.metadata["anchor_labels"] == ["player_start", "test_placeable"]
    assert len(pth) == 3
    assert len(pth.outgoing(0)) == 2
    assert len(pth.outgoing(1)) == 2
    assert len(pth.outgoing(2)) == 2
    assert pth[1].x == 0.0
    assert pth[1].y == -3.0
    assert pth[2].x == 1.75
    assert pth[2].y == 1.5


def test_t2608_blocks_path_points_outside_walkmesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_pathing import (
        AuthoredPathAnchor,
        build_authored_path_graph_from_walkmesh,
        compile_authored_pathing_for_module,
        validate_authored_path_graph,
    )
    from src.core.modules.authored_room_geometry import RectangularRoomPrimitive, build_rectangular_room_wok

    wok = build_rectangular_room_wok(RectangularRoomPrimitive(room_resref="grdev01_room01"))
    anchors = (AuthoredPathAnchor("outside", (99.0, 99.0, 0.0)),)
    graph = build_authored_path_graph_from_walkmesh(wok, anchors=anchors)
    validation = validate_authored_path_graph(graph, wok=wok)

    assert validation.ok is False
    assert any("outside the generated walkmesh" in issue for issue in validation.blocking_issues)
    try:
        compile_authored_pathing_for_module(wok, anchors=anchors)
    except ValueError as exc:
        assert "outside the generated walkmesh" in str(exc)
    else:
        raise AssertionError("outside path anchors should block before PTH serialization")


def test_t2629_blocks_path_connections_that_leave_walkmesh() -> None:
    _install_native_payload_paths()

    from src.core.modules.authored_module_pathing import (
        AuthoredPathConnection,
        AuthoredPathGraph,
        AuthoredPathPoint,
        validate_authored_path_graph,
    )
    from src.core.modules.module_format import WOKData, WOKFace

    wok = WOKData(
        verts=[
            (-2.0, -1.0, 0.0),
            (-1.0, -1.0, 0.0),
            (-1.0, 1.0, 0.0),
            (-2.0, 1.0, 0.0),
            (1.0, -1.0, 0.0),
            (2.0, -1.0, 0.0),
            (2.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
        ],
        faces=[
            WOKFace(0, 1, 2, 4),
            WOKFace(0, 2, 3, 4),
            WOKFace(4, 5, 6, 4),
            WOKFace(4, 6, 7, 4),
        ],
    )
    graph = AuthoredPathGraph(
        points=(
            AuthoredPathPoint(label="left_island", x=-1.5, y=0.0),
            AuthoredPathPoint(label="right_island", x=1.5, y=0.0),
        ),
        connections=(AuthoredPathConnection(source=0, target=1),),
    )

    validation = validate_authored_path_graph(graph, wok=wok, connection_sample_interval=0.25)

    assert validation.ok is False
    assert any("leaves the generated walkmesh" in issue for issue in validation.blocking_issues)
