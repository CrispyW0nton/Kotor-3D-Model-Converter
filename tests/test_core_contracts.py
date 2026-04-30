from __future__ import annotations

from types import SimpleNamespace


def test_vertex_space_enum_contract() -> None:
    from src.core.vertex_space import VertexSpace

    assert list(VertexSpace) == [
        VertexSpace.NODE_LOCAL,
        VertexSpace.WORLD,
        VertexSpace.AABB_WALK,
    ]
    assert VertexSpace.NODE_LOCAL == 0
    assert VertexSpace.WORLD == 1
    assert VertexSpace.AABB_WALK == 2


def test_compute_vertex_space_aabb_walkmesh() -> None:
    from src.core.vertex_space import VertexSpace, compute_vertex_space

    assert compute_vertex_space(SimpleNamespace(flags=0x0200), None) is VertexSpace.AABB_WALK


def test_compute_vertex_space_imported_world() -> None:
    from src.core.vertex_space import VertexSpace, compute_vertex_space

    node = SimpleNamespace(flags=0, _imported=True)
    assert compute_vertex_space(node, None) is VertexSpace.WORLD


def test_compute_vertex_space_default_node_local() -> None:
    from src.core.vertex_space import VertexSpace, compute_vertex_space

    assert compute_vertex_space(SimpleNamespace(flags=0), None) is VertexSpace.NODE_LOCAL


def test_inner_geometry_name_matching() -> None:
    from src.core.render_constants import is_inner_geometry_name

    for name in ("eyeRA", "teethU", "TongueMesh", "gumskin", "JawSkin", "eyelid"):
        assert is_inner_geometry_name(name)


def test_face_mesh_name_matching() -> None:
    from src.core.render_constants import is_face_mesh_name

    for name in ("head", "Face_LOD0", "fchead01", "skullcap"):
        assert is_face_mesh_name(name)


def test_inner_geometry_does_not_match_non_inner_names() -> None:
    from src.core.render_constants import is_inner_geometry_name

    for name in ("headhook", "model_root", "rootdummy", "random_mesh", ""):
        assert not is_inner_geometry_name(name)


def test_read_mdl_safe_importable_and_callable() -> None:
    from src.core.mdl_reader_wrapper import read_mdl_safe

    assert callable(read_mdl_safe)


def test_pykotor_mdl_binary_fixes_are_idempotent() -> None:
    from src.core.pykotor_mdl_io_fix import ensure_pykotor_mdl_binary_fixes

    ensure_pykotor_mdl_binary_fixes()
    ensure_pykotor_mdl_binary_fixes()
