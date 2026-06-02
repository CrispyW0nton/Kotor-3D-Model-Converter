from __future__ import annotations

import inspect
import os
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import src.adapters.rendering.pygfx_core.renderer as pygfx_renderer_module
import src.adapters.rendering.pygfx_core.scene_bridge as pygfx_scene_bridge_module
import src.core.animation.gpu_skinning as gpu_skinning_module
import src.core.rendering.mesh_render_data as mesh_render_data_module
import src.core.rendering.skeleton_render_data as skeleton_render_data_module
from src.adapters.rendering.pygfx_core.scene_bridge import PygfxSceneBridge
from src.adapters.rendering.pygfx_core.mesh_cache import PygfxMeshCache
from src.adapters.rendering.pygfx_core.renderer import PygfxViewportRenderer
from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
from src.adapters.rendering.renderer_factory import fallback_order, renderer_capabilities_snapshot
from src.core.rendering.renderer_performance import ViewportFrameGovernor
from src.core.rendering.renderer_backend import RendererBackend, normalize_renderer_backend, renderer_backend_label
from src.core.rendering.renderer_settings import RendererSettings
from src.gui.viewports.viewport_core.widgets.picking_hover import ViewportPickingHoverMixin
from src.gui.viewports.viewport_core.widgets.selection_mesh import ViewportSelectionMeshMixin
from src.gui.viewports.viewport_core.widgets.state_helpers import ViewportStateMixin


class _FakeGeometry:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        if "positions" in kwargs:
            self.positions = _FakeBuffer(kwargs["positions"])
        if "normals" in kwargs:
            self.normals = _FakeBuffer(kwargs["normals"])
        if "texcoords" in kwargs:
            self.texcoords = _FakeBuffer(kwargs["texcoords"])
        if "texcoords1" in kwargs:
            self.texcoords1 = _FakeBuffer(kwargs["texcoords1"])
        if "indices" in kwargs:
            self.indices = _FakeBuffer(kwargs["indices"])


class _FakeBuffer:
    def __init__(self, data):
        self.data = np.asarray(data).copy()
        self.update_calls = []

    def update_range(self, offset=0, size=None):
        self.update_calls.append((offset, size))


class _FakeMaterial:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.side = ""
        self.color = kwargs.get("color")
        self.opacity = 1.0
        self.wireframe = False
        self.flat_shading = False
        self.map = None
        self.light_map = None
        self.light_map_intensity = 0.0
        self.alpha_mode = "auto"
        self.alpha_test = 0.0
        self.thickness = kwargs.get("thickness", 1.0)


class MeshPhongMaterial(_FakeMaterial):
    pass


class MeshBasicMaterial(_FakeMaterial):
    pass


class _FakeLocal:
    def __init__(self):
        self.matrix = None
        self.position = None


class _FakeMesh:
    def __init__(self, geometry, material, **kwargs):
        self.geometry = geometry
        self.material = material
        self.local = _FakeLocal()
        self.name = str(kwargs.get("name", ""))
        self.visible = True


class _FakeSkinnedMesh(_FakeMesh):
    def bind(self, skeleton, bind_matrix=None):
        self.skeleton = skeleton
        self.bind_matrix = bind_matrix


class _FakeGfx:
    Geometry = _FakeGeometry
    MeshPhongMaterial = MeshPhongMaterial
    MeshBasicMaterial = MeshBasicMaterial
    Mesh = _FakeMesh
    SkinnedMesh = _FakeSkinnedMesh
    LineSegmentMaterial = _FakeMaterial
    PointsMaterial = _FakeMaterial
    Line = _FakeMesh
    Points = _FakeMesh

    class Bone:
        def __init__(self, name=""):
            self.name = name

    class Skeleton:
        def __init__(self, bones, bone_inverses=None):
            self.bones = bones
            self.bone_inverses = bone_inverses
            dtype = [("bone_matrices", np.float32, (4, 4))]
            self.bone_matrices_buffer = _FakeBuffer(np.zeros((max(1, len(bones)),), dtype=dtype))

        def update(self):
            return None

    class Background:
        def __init__(self, color):
            self.color = color

        @classmethod
        def from_color(cls, color):
            return cls(color)

    class Texture:
        def __init__(self, data, **kwargs):
            self.data = data
            self.kwargs = kwargs

    class TextureMap:
        def __init__(self, texture, **kwargs):
            self.texture = texture
            self.kwargs = kwargs

    class AmbientLight:
        def __init__(self, color, intensity=1.0):
            self.color = color
            self.intensity = intensity

    class DirectionalLight:
        def __init__(self, color, intensity=1.0):
            self.color = color
            self.intensity = intensity
            self.local = _FakeLocal()

        def look_at(self, target):
            self.target = target

    class PointLight(DirectionalLight):
        pass


class _FakeScene:
    def __init__(self):
        self.children = []

    def add(self, obj):
        self.children.append(obj)

    def remove(self, obj):
        self.children.remove(obj)


class _ViewportPygfxPickProbe(ViewportPickingHoverMixin, ViewportStateMixin, ViewportSelectionMeshMixin):
    def _is_selected_model_root(self, node) -> bool:
        return False


def _mesh_data(*, mesh_id=7, source_revision=(3, 1, 0), material_revision=(1, 0, 0, 0)):
    diffuse_texture_data = None
    lightmap_texture_data = None
    if material_revision == ("texture",):
        diffuse = Image.new("RGBA", (2, 2), (180, 90, 40, 255))
        diffuse_texture_data = SimpleNamespace(
            texture_id="unit_diffuse",
            name="unit_diffuse",
            source=diffuse,
            source_revision=(id(diffuse), 2, 2),
        )
    if material_revision == ("lightmap",):
        diffuse = Image.new("RGBA", (2, 2), (180, 90, 40, 255))
        lightmap = Image.new("RGBA", (2, 2), (90, 120, 160, 255))
        diffuse_texture_data = SimpleNamespace(
            texture_id="unit_diffuse",
            name="unit_diffuse",
            source=diffuse,
            source_revision=(id(diffuse), 2, 2),
        )
        lightmap_texture_data = SimpleNamespace(
            texture_id="unit_lightmap",
            name="unit_lightmap",
            source=lightmap,
            source_revision=(id(lightmap), 2, 2),
        )
    material = SimpleNamespace(
        material_id="mat-a",
        source_revision=material_revision,
        double_sided=False,
        diffuse_texture_data=diffuse_texture_data,
        lightmap_texture_data=lightmap_texture_data,
        alpha_mode="OPAQUE",
        alpha_cutoff=0.5,
        unlit=False,
    )
    return SimpleNamespace(
        mesh_id=mesh_id,
        source=SimpleNamespace(name="mesh-a"),
        positions=np.asarray([(0, 0, 0), (1, 0, 0), (0, 1, 0)], dtype=np.float32),
        normals=None,
        uvs0=None,
        uvs1=None,
        indices=np.asarray([0, 1, 2], dtype=np.uint32),
        material=material,
        material_color=(0.5, 0.6, 0.7, 1.0),
        world_matrix=np.eye(4, dtype=np.float32),
        source_revision=source_revision,
    )


def _skinned_mesh_data(*, mesh_id=17, source_revision=(4, 2, 1, 1)):
    data = _mesh_data(mesh_id=mesh_id, source_revision=source_revision)
    data.is_skinned = True
    data.bone_indices = np.zeros((3, 4), dtype=np.uint32)
    data.bone_weights = np.zeros((3, 4), dtype=np.float32)
    data.bone_weights[:, 0] = 1.0
    data.skinning_cpu_fallback = False
    return data


def test_pygfx_backend_id_alias_and_label() -> None:
    assert RendererBackend.PYGFX_WGPU.value == "pygfx_wgpu"
    assert normalize_renderer_backend("pygfx") is RendererBackend.PYGFX_WGPU
    assert normalize_renderer_backend("pygfx/wgpu") is RendererBackend.PYGFX_WGPU
    assert renderer_backend_label(RendererBackend.PYGFX_WGPU) == "pygfx / WGPU"


def test_pygfx_capability_snapshot_includes_optional_backend() -> None:
    by_id = {caps.backend_id: caps for caps in renderer_capabilities_snapshot()}

    assert RendererBackend.PYGFX_WGPU.value in by_id
    assert by_id[RendererBackend.PYGFX_WGPU.value].name == "pygfx / WGPU"
    assert by_id[RendererBackend.PYGFX_WGPU.value].api == "pygfx/WGPU"


def test_pygfx_windows_fallback_order_prefers_pygfx_then_wgpu(monkeypatch) -> None:
    monkeypatch.setattr("src.adapters.rendering.renderer_factory.platform.system", lambda: "Windows")

    order = fallback_order(RendererSettings(backend=RendererBackend.PYGFX_WGPU, allow_fallback=True))

    assert order == [
        RendererBackend.PYGFX_WGPU,
        RendererBackend.WGPU_D3D12,
        RendererBackend.WGPU_VULKAN,
        RendererBackend.MODERNGL_GL330,
        RendererBackend.NULL_DIAGNOSTIC,
    ]


def test_pygfx_renderer_reports_unavailable_when_optional_import_missing(monkeypatch) -> None:
    PygfxViewportRenderer._probe_cache = None

    def fake_find_spec(name):
        if name == "pygfx":
            return None
        return object()

    monkeypatch.setattr(pygfx_renderer_module.importlib_util, "find_spec", fake_find_spec)

    caps = PygfxViewportRenderer.probe_availability()

    assert caps.available is False
    assert "pygfx" in caps.reason
    PygfxViewportRenderer._probe_cache = None


def test_pygfx_availability_probe_does_not_import_gpu_runtime(monkeypatch) -> None:
    PygfxViewportRenderer._probe_cache = None
    imported = []

    def fake_import(name):
        imported.append(name)
        raise AssertionError("probe should not import optional GPU modules")

    monkeypatch.setattr(pygfx_renderer_module.importlib, "import_module", fake_import)
    monkeypatch.setattr(pygfx_renderer_module.importlib_util, "find_spec", lambda _name: object())

    caps = PygfxViewportRenderer.probe_availability()

    assert caps.available is True
    assert imported == []
    PygfxViewportRenderer._probe_cache = None


def test_pygfx_mesh_cache_retains_mesh_and_updates_same_shape_revision_in_place() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data()

    first = cache.get_or_create(data, _FakeGfx, scene)
    cache.begin_frame()
    second = cache.get_or_create(data, _FakeGfx, scene)

    assert second is first
    assert second.geometry is first.geometry
    assert cache.geometry_updates_this_frame == 0
    assert cache.material_updates_this_frame == 0

    cache.begin_frame()
    third = cache.get_or_create(_mesh_data(source_revision=(3, 1, 1)), _FakeGfx, scene)

    assert third is first
    assert cache.geometry_updates_this_frame == 0
    assert cache.dynamic_geometry_updates_this_frame == 1
    assert cache.material_updates_this_frame == 0


def test_pygfx_viewport_bounds_and_gizmo_use_rendered_mesh_cache_records() -> None:
    source = SimpleNamespace(
        name="translated-render-mesh",
        vertices=[(-100.0, -100.0, 0.0), (-99.0, -100.0, 0.0), (-100.0, -99.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    data = _mesh_data(mesh_id=44)
    data.source = source
    data.positions = np.asarray([(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)], dtype=np.float32)
    data.indices = np.asarray([0, 1, 2], dtype=np.uint32)
    cache = PygfxMeshCache()
    scene = _FakeScene()
    record = cache.get_or_create(data, _FakeGfx, scene, selected=False)
    matrix = np.eye(4, dtype=np.float32)
    matrix[:3, 3] = (5.0, 7.0, 0.0)
    record.mesh.local.matrix = matrix

    probe = _ViewportPygfxPickProbe()
    probe._gpu_renderer = SimpleNamespace(
        backend_id="pygfx_wgpu",
        scene_bridge=SimpleNamespace(mesh_cache=cache),
    )
    probe._renderer = SimpleNamespace(
        _proj_batch=lambda points, _w, _h: [tuple(point) for point in points],
        _get_world_verts_for_node=lambda _node: [
            (-100.0, -100.0, 0.0),
            (-99.0, -100.0, 0.0),
            (-100.0, -99.0, 0.0),
        ],
    )
    probe.model = SimpleNamespace(root_node=None)

    bounds = probe._projected_mesh_bounds(source, 100, 100)

    assert bounds is not None
    assert bounds[:4] == pytest.approx((1.0, 3.0, 11.0, 13.0))
    assert probe._gizmo_world_position(source) == pytest.approx((6.0, 8.0, 0.0))


def test_pygfx_mesh_cache_flips_d3d_uvs_like_wgpu_shader() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data()
    data.uvs0 = np.asarray([(0.0, 0.0), (0.5, 0.25), (1.0, 1.0)], dtype=np.float32)
    data.uvs1 = np.asarray([(0.0, 0.1), (0.5, 0.6), (1.0, 0.9)], dtype=np.float32)

    record = cache.get_or_create(data, _FakeGfx, scene)

    assert np.allclose(record.geometry.texcoords.data[:, 0], data.uvs0[:, 0])
    assert np.allclose(record.geometry.texcoords.data[:, 1], 1.0 - data.uvs0[:, 1])
    assert np.allclose(record.geometry.texcoords1.data[:, 0], data.uvs1[:, 0])
    assert np.allclose(record.geometry.texcoords1.data[:, 1], 1.0 - data.uvs1[:, 1])


def test_pygfx_mesh_cache_adds_indices_for_expanded_vbo_triangle_lists() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data()
    data.indices = None
    data.positions = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        dtype=np.float32,
    )

    record = cache.get_or_create(data, _FakeGfx, scene)

    assert record.geometry.indices.data.tolist() == [[0, 1, 2], [3, 4, 5]]


def test_pygfx_mesh_cache_updates_only_dynamic_skin_buffers_for_animation_frames() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data(source_revision=(3, 1, 0, 22, 1, 0))
    data.normals = np.asarray([(0.0, 0.0, 1.0)] * 3, dtype=np.float32)
    data.uvs0 = np.asarray([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], dtype=np.float32)
    data.skinning_cpu_fallback = True
    record = cache.get_or_create(data, _FakeGfx, scene)

    for buffer_name in ("positions", "normals", "texcoords", "indices"):
        getattr(record.geometry, buffer_name).update_calls.clear()
    next_data = _mesh_data(source_revision=(3, 1, 0, 22, 1, 16))
    next_data.positions = data.positions + np.asarray((0.1, 0.0, 0.0), dtype=np.float32)
    next_data.normals = data.normals
    next_data.uvs0 = data.uvs0
    next_data.skinning_cpu_fallback = True

    cache.get_or_create(next_data, _FakeGfx, scene, force_geometry_update=True)

    assert record.geometry.positions.update_calls
    assert record.geometry.normals.update_calls
    assert record.geometry.texcoords.update_calls == []
    assert record.geometry.indices.update_calls == []


def test_pygfx_mesh_cache_rebuilds_geometry_when_topology_shape_changes() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    first = cache.get_or_create(_mesh_data(), _FakeGfx, scene)
    changed = _mesh_data(source_revision=(4, 2, 0))
    changed.positions = np.asarray([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], dtype=np.float32)
    changed.indices = np.asarray([0, 1, 2, 0, 2, 3], dtype=np.uint32)
    cache.begin_frame()

    updated = cache.get_or_create(changed, _FakeGfx, scene)

    assert updated is first
    assert cache.geometry_updates_this_frame == 1
    assert cache.dynamic_geometry_updates_this_frame == 0


def test_pygfx_mesh_cache_updates_same_shape_animation_buffers_in_place() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    first = _mesh_data(source_revision=(3, 1, 0))
    record = cache.get_or_create(first, _FakeGfx, scene)
    cache.begin_frame()
    moved = _mesh_data(source_revision=(3, 1, 99))
    moved.positions = np.asarray([(0, 0, 1), (1, 0, 1), (0, 1, 1)], dtype=np.float32)

    updated = cache.get_or_create(moved, _FakeGfx, scene)

    assert updated is record
    assert updated.geometry is record.geometry
    assert cache.geometry_updates_this_frame == 0
    assert cache.dynamic_geometry_updates_this_frame == 1
    assert np.allclose(record.geometry.positions.data, moved.positions)
    assert record.geometry.positions.update_calls


def test_pygfx_mesh_cache_force_updates_animation_buffers_even_when_revision_key_is_stable() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    record = cache.get_or_create(_mesh_data(source_revision=(3, 1, 0)), _FakeGfx, scene)
    cache.begin_frame()
    moved = _mesh_data(source_revision=(3, 1, 0))
    moved.positions = np.asarray([(0, 0, 2), (1, 0, 2), (0, 1, 2)], dtype=np.float32)

    cache.get_or_create(moved, _FakeGfx, scene, force_geometry_update=True)

    assert cache.geometry_updates_this_frame == 0
    assert cache.dynamic_geometry_updates_this_frame == 1
    assert np.allclose(record.geometry.positions.data, moved.positions)


def test_viewport_frame_governor_tracks_pygfx_style_and_animation_dirty_flags() -> None:
    governor = ViewportFrameGovernor()

    governor.request_redraw("style switch", style=True)
    assert governor.dirty_flags["style"] is True
    assert governor.dirty_flags["scene"] is False
    governor.mark_clean_after_render("style switch")

    governor.request_redraw("animation pose", animation=True)
    assert governor.dirty_flags["animation"] is True
    assert governor.dirty_flags["scene"] is False


def test_pygfx_mesh_cache_updates_material_for_selection_without_geometry_rebuild() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data()
    cache.get_or_create(data, _FakeGfx, scene, selected=False)

    cache.begin_frame()
    cache.get_or_create(data, _FakeGfx, scene, selected=True)

    assert cache.geometry_updates_this_frame == 0
    assert cache.material_updates_this_frame == 1


def test_pygfx_scene_bridge_updates_dirty_transform_without_geometry_rebuild() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data()
    record = cache.get_or_create(data, _FakeGfx, scene)
    record.source.world_position = lambda: (2.0, 3.0, 4.0)
    cache.begin_frame()
    cache.mark_transform_dirty(record.source)

    bridge = PygfxSceneBridge(_FakeGfx, scene, cache)
    bridge.update_dirty_transforms()

    assert cache.geometry_updates_this_frame == 0
    assert cache.material_updates_this_frame == 0
    assert record.transform_dirty is False
    assert record.mesh.local.matrix[0, 3] == pytest.approx(2.0)


def test_pygfx_scene_bridge_uses_identity_model_matrix_for_skinned_vbo_data(monkeypatch) -> None:
    data = _mesh_data()
    data.is_skinned = True
    data.world_matrix = np.eye(4, dtype=np.float32)
    data.world_matrix[0, 3] = 42.0

    def fake_iter_mesh_render_data(model, **kwargs):
        return [data]

    monkeypatch.setattr(pygfx_scene_bridge_module, "iter_mesh_render_data", fake_iter_mesh_render_data)
    bridge = PygfxSceneBridge(_FakeGfx, _FakeScene(), PygfxMeshCache())

    bridge.update_scene(SimpleNamespace(name="model"))

    record = next(iter(bridge.mesh_cache.records.values()))
    assert np.allclose(record.mesh.local.matrix, np.eye(4, dtype=np.float32))


def test_pygfx_scene_bridge_uses_wgpu_vbo_builder_for_uv_seams(monkeypatch) -> None:
    seen = {}

    def fake_iter_mesh_render_data(model, **kwargs):
        seen["vbo_builder"] = kwargs.get("vbo_builder")
        return []

    monkeypatch.setattr(pygfx_scene_bridge_module, "iter_mesh_render_data", fake_iter_mesh_render_data)
    bridge = PygfxSceneBridge(_FakeGfx, _FakeScene(), PygfxMeshCache())

    bridge.update_scene(SimpleNamespace(name="model"))

    assert callable(seen["vbo_builder"])
    assert seen["vbo_builder"].__name__ == "_build_vbo_data"


def test_skinned_animation_vbo_normals_are_cached_between_frames(monkeypatch) -> None:
    node = SimpleNamespace(
        name="skin",
        is_skin=True,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        faces=[(0, 1, 2)],
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[],
        bone_map=["root"],
        skin_data=[(0, 1.0)],
        render=True,
        _gr_revision=3,
        world_transform=lambda: ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    )
    model = SimpleNamespace(all_nodes=lambda: [node])
    vbo = np.zeros((3, 22), dtype=np.float32)
    vbo[:, 0:3] = np.asarray(node.vertices, dtype=np.float32)
    vbo[:, 3:6] = np.asarray(node.normals, dtype=np.float32)
    vbo[:, 6:8] = np.asarray(node.uvs, dtype=np.float32)
    vbo[:, 14] = 0.0
    vbo[:, 18] = 1.0
    calls = {"smooth": 0, "vbo": 0}

    def fake_smooth(positions, normals, indices):
        calls["smooth"] += 1
        return normals

    def fake_vbo_builder(*_args, **_kwargs):
        calls["vbo"] += 1
        return vbo, np.asarray([0, 1, 2], dtype=np.uint32)

    monkeypatch.setattr(mesh_render_data_module, "smooth_render_normals", fake_smooth)

    first = list(
        mesh_render_data_module.iter_mesh_render_data(
            model,
            anim_pose=SimpleNamespace(time=0.0),
            allow_cpu_skinning=False,
            vbo_builder=fake_vbo_builder,
        )
    )
    second = list(
        mesh_render_data_module.iter_mesh_render_data(
            model,
            anim_pose=SimpleNamespace(time=0.1),
            allow_cpu_skinning=False,
            vbo_builder=fake_vbo_builder,
        )
    )

    assert len(first) == 1
    assert len(second) == 1
    assert calls == {"smooth": 1, "vbo": 1}
    assert second[0].source_revision[-1] == 1


def test_rigid_animation_vbo_rows_are_cached_between_frames(monkeypatch) -> None:
    node = SimpleNamespace(
        name="rigid",
        is_skin=False,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        faces=[(0, 1, 2)],
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[],
        render=True,
        _gr_revision=9,
        world_transform=lambda: ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    )
    model = SimpleNamespace(all_nodes=lambda: [node])
    vbo = np.zeros((3, 10), dtype=np.float32)
    vbo[:, 0:3] = np.asarray(node.vertices, dtype=np.float32)
    vbo[:, 3:6] = np.asarray(node.normals, dtype=np.float32)
    vbo[:, 6:8] = np.asarray(node.uvs, dtype=np.float32)
    calls = {"smooth": 0, "vbo": 0}

    def fake_smooth(positions, normals, indices):
        calls["smooth"] += 1
        return normals

    def fake_vbo_builder(*_args, **_kwargs):
        calls["vbo"] += 1
        return vbo, np.asarray([0, 1, 2], dtype=np.uint32)

    monkeypatch.setattr(mesh_render_data_module, "smooth_render_normals", fake_smooth)

    first = list(
        mesh_render_data_module.iter_mesh_render_data(
            model,
            anim_pose=SimpleNamespace(time=0.0),
            vbo_builder=fake_vbo_builder,
        )
    )
    second = list(
        mesh_render_data_module.iter_mesh_render_data(
            model,
            anim_pose=SimpleNamespace(time=0.1),
            vbo_builder=fake_vbo_builder,
        )
    )

    assert len(first) == 1
    assert len(second) == 1
    assert calls == {"smooth": 1, "vbo": 1}


def test_cpu_skinning_reuses_model_inverse_bind_uploader(monkeypatch) -> None:
    calls = {"build": 0, "palette": 0}

    class FakeUploader:
        def __init__(self, max_bones):
            self.max_bones = max_bones

        def build_inverse_bind_pose(self, model):
            calls["build"] += 1
            return len(model.all_nodes())

        def compute_skin_node_palette(self, _node, _anim_pose):
            calls["palette"] += 1

        def as_numpy_array(self):
            return np.asarray([np.eye(4, dtype=np.float32)], dtype=np.float32)

    monkeypatch.setattr(gpu_skinning_module, "MatrixPaletteUploader", FakeUploader)
    node = SimpleNamespace(
        name="skin",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_revision=0,
    )
    model = SimpleNamespace(name="model", supermodel="", all_nodes=lambda: [node])
    skinning = SimpleNamespace(
        is_skinned=True,
        bone_indices=np.zeros((3, 4), dtype=np.uint16),
        bone_weights=np.asarray([[1.0, 0.0, 0.0, 0.0]] * 3, dtype=np.float32),
    )
    positions = np.asarray([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], dtype=np.float32)
    normals = np.asarray([(0.0, 0.0, 1.0)] * 3, dtype=np.float32)

    skeleton_render_data_module.cpu_skin_vbo_arrays(node, positions, normals, skinning, SimpleNamespace(nodes={}), model=model)
    skeleton_render_data_module.cpu_skin_vbo_arrays(node, positions, normals, skinning, SimpleNamespace(nodes={}), model=model)

    assert calls == {"build": 1, "palette": 2}


def test_bas_attachment_skin_meshes_switch_bind_buffers_for_body_animation(monkeypatch) -> None:
    root = SimpleNamespace(
        name="head_root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        children=[],
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root=True,
    )
    skin = SimpleNamespace(
        name="Head",
        parent=root,
        children=[],
        is_skin=True,
        position=(0.0, 0.0, 2.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        vertices=[(0.0, 0.0, -2.0), (1.0, 0.0, -2.0), (0.0, 1.0, -2.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        faces=[(0, 1, 2)],
        uvs=[],
        uvs_lm=[],
        bone_map=["head_root"],
        skin_data=[object(), object(), object()],
        qbone_list=[(1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)],
        tbone_list=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)],
        render=True,
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
        _gr_revision=1,
    )
    root.children = [skin]
    vbo = np.zeros((3, 22), dtype=np.float32)
    vbo[:, 3:6] = np.asarray(skin.normals, dtype=np.float32)
    vbo[:, 14] = 0.0
    vbo[:, 18] = 1.0
    model = SimpleNamespace(all_nodes=lambda: [root, skin])
    calls = {}

    def fake_vbo_builder(_node, world_pos, _world_orient, **kwargs):
        calls["apply_skin_node_transform_for_bind"] = kwargs.get("apply_skin_node_transform_for_bind")
        out = vbo.copy()
        out[:, 0:3] = np.asarray(skin.vertices, dtype=np.float32)
        if kwargs.get("apply_skin_node_transform_for_bind"):
            out[:, 0:3] += np.asarray(world_pos, dtype=np.float32)
        return out, np.asarray([0, 1, 2], dtype=np.uint32)

    rest_rows = list(
        mesh_render_data_module.iter_mesh_render_data(
            model,
            anim_pose=None,
            allow_cpu_skinning=False,
            vbo_builder=fake_vbo_builder,
        )
    )

    assert len(rest_rows) == 1
    assert calls["apply_skin_node_transform_for_bind"] is True
    assert tuple(np.round(rest_rows[0].positions[:, 2], 4)) == (0.0, 0.0, 0.0)

    rows = list(
        mesh_render_data_module.iter_mesh_render_data(
            model,
            anim_pose=SimpleNamespace(time=0.25, nodes={}),
            allow_cpu_skinning=False,
            vbo_builder=fake_vbo_builder,
        )
    )

    assert len(rows) == 1
    assert rows[0].is_skinned is False
    assert rows[0].skinning_cpu_fallback is True
    assert calls["apply_skin_node_transform_for_bind"] is False
    assert tuple(np.round(rows[0].positions[:, 2], 4)) == (-2.0, -2.0, -2.0)
    assert rows[0].bone_indices is None
    assert rows[0].bone_weights is None
    palette_model = mesh_render_data_module.bas_attachment_palette_model_for_node(skin)
    assert palette_model is not None
    assert getattr(palette_model, "_gr_bas_attachment_palette_model") is True
    assert [node.name for node in palette_model.all_nodes()] == ["head_root", "Head"]


def test_pygfx_skin_palette_uses_bas_attachment_local_model(monkeypatch) -> None:
    calls = {"build_nodes": []}

    class FakeUploader:
        def __init__(self, max_bones):
            self.max_bones = max_bones

        def build_inverse_bind_pose(self, model):
            nodes = list(model.all_nodes())
            calls["build_nodes"].append([getattr(node, "name", "") for node in nodes])
            return len(nodes)

        def compute_skin_node_palette(self, _node, _anim_pose):
            pass

        def as_numpy_array(self):
            matrix = np.eye(4, dtype=np.float32)
            matrix[2, 3] = 2.0
            return np.asarray([matrix], dtype=np.float32)

    monkeypatch.setattr(gpu_skinning_module, "MatrixPaletteUploader", FakeUploader)

    root = SimpleNamespace(
        name="head_root",
        parent=None,
        children=[],
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root=True,
    )
    skin = SimpleNamespace(
        name="Head",
        parent=root,
        children=[],
        is_skin=True,
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
    )
    root.children = [skin]
    skeleton_buffer = SimpleNamespace(
        data=np.zeros(1, dtype=[("bone_matrices", np.float32, (4, 4))]),
        update_range=lambda *_args, **_kwargs: None,
    )
    record = SimpleNamespace(source=skin, skeleton=SimpleNamespace(bone_matrices_buffer=skeleton_buffer))

    PygfxMeshCache().update_skin_palette(
        record,
        SimpleNamespace(time=0.1, nodes={}),
        model=SimpleNamespace(name="body", all_nodes=lambda: []),
    )

    assert calls["build_nodes"] == [["head_root", "Head"]]
    assert skeleton_buffer.data[0]["bone_matrices"][3, 2] == pytest.approx(2.0)
    assert skeleton_buffer.data[0]["bone_matrices"][2, 3] == pytest.approx(0.0)


def test_bas_attachment_skin_palette_is_attachment_root_local() -> None:
    root = SimpleNamespace(
        name="head_root",
        parent=None,
        children=[],
        position=(0.0, 0.0, 10.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root=True,
        _gr_bas_attachment_slot="head",
    )
    skin = SimpleNamespace(
        name="Head",
        parent=root,
        children=[],
        is_skin=True,
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
    )
    root.children = [skin]
    palette = np.asarray([np.eye(4, dtype=np.float32)], dtype=np.float32)
    palette[0, 2, 3] = 12.0

    adjusted = skeleton_render_data_module.bas_attachment_root_local_skin_palette(skin, palette, None)

    assert adjusted[0, 2, 3] == pytest.approx(2.0)


def test_bas_attachment_nonskin_face_parts_use_only_matching_head_local_pose() -> None:
    socket = SimpleNamespace(
        name="headhook",
        parent=None,
        children=[],
        position=(10.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    root = SimpleNamespace(
        name="p_carthbbh",
        parent=socket,
        children=[],
        position=(0.0, 0.0, 1.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root=True,
        _gr_bas_socket_name="headhook",
        _gr_bas_attachment_source_model_id=123,
    )
    eye = SimpleNamespace(
        name="eye",
        parent=root,
        children=[],
        position=(0.0, 0.0, 2.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
        _gr_bas_attachment_source_model_id=123,
    )
    socket.children = [root]
    root.children = [eye]

    bind_pose = SimpleNamespace(
        time=0.0,
        nodes={"eye": SimpleNamespace(name="eye", position=(1.0, 0.0, 2.0), rotation=(0.0, 0.0, 0.0, 1.0))},
        _gr_animation_source_model_id=999,
    )
    head_pose = SimpleNamespace(
        time=0.0,
        nodes={"eye": SimpleNamespace(name="eye", position=(1.0, 0.0, 2.0), rotation=(0.0, 0.0, 0.0, 1.0))},
        _gr_animation_source_model_id=123,
    )

    mismatch = mesh_render_data_module.mesh_model_matrix_for_node(eye, anim_pose=bind_pose)
    matched = mesh_render_data_module.mesh_model_matrix_for_node(eye, anim_pose=head_pose)

    assert tuple(np.round(mismatch[:3, 3], 4)) == (10.0, 0.0, 3.0)
    assert tuple(np.round(matched[:3, 3], 4)) == (11.0, 0.0, 3.0)


def test_bas_head_attachment_face_parts_accept_inherited_body_pose_as_local_transform() -> None:
    socket = SimpleNamespace(
        name="headhook",
        parent=None,
        children=[],
        position=(10.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    root = SimpleNamespace(
        name="pmha01",
        parent=socket,
        children=[],
        position=(0.0, 0.0, 1.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root=True,
        _gr_bas_attachment_slot="head",
        _gr_bas_socket_name="headhook",
        _gr_bas_attachment_source_model_id=123,
    )
    eye = SimpleNamespace(
        name="eye",
        parent=root,
        children=[],
        position=(0.0, 0.0, 2.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
        _gr_bas_attachment_source_model_id=123,
    )
    socket.children = [root]
    root.children = [eye]
    inherited_body_pose = SimpleNamespace(
        time=0.0,
        nodes={"eye": SimpleNamespace(name="eye", position=(1.0, 0.0, 2.0), rotation=(0.0, 0.0, 0.0, 1.0))},
        _gr_animation_source_model_id=999,
    )

    matrix = mesh_render_data_module.mesh_model_matrix_for_node(eye, anim_pose=inherited_body_pose)

    assert tuple(np.round(matrix[:3, 3], 4)) == (11.0, 0.0, 3.0)


def test_bas_head_attachment_inherited_pose_includes_head_parent_chain() -> None:
    socket = SimpleNamespace(
        name="headhook",
        parent=None,
        children=[],
        position=(10.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    root = SimpleNamespace(
        name="pmha01",
        parent=socket,
        children=[],
        position=(0.0, 0.0, 1.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root=True,
        _gr_bas_attachment_slot="head",
        _gr_bas_socket_name="headhook",
        _gr_bas_attachment_source_model_id=123,
    )
    hturn = SimpleNamespace(
        name="Hturn_g",
        parent=root,
        children=[],
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
        _gr_bas_attachment_source_model_id=123,
    )
    head = SimpleNamespace(
        name="head_g",
        parent=hturn,
        children=[],
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
        _gr_bas_attachment_source_model_id=123,
    )
    eye = SimpleNamespace(
        name="eyera",
        parent=head,
        children=[],
        position=(0.0, 0.0, 2.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        _gr_bas_attachment_layer=True,
        _gr_bas_attachment_root_ref=root,
        _gr_bas_attachment_source_model_id=123,
    )
    socket.children = [root]
    root.children = [hturn]
    hturn.children = [head]
    head.children = [eye]
    inherited_body_pose = SimpleNamespace(
        time=0.0,
        nodes={
            "hturn_g": SimpleNamespace(name="Hturn_g", position=(0.0, 1.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0)),
            "head_g": SimpleNamespace(name="head_g", position=(0.0, 2.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0)),
            "eyera": SimpleNamespace(name="eyera", position=(0.0, 0.0, 3.0), rotation=(0.0, 0.0, 0.0, 1.0)),
        },
        _gr_animation_source_model_id=999,
    )

    matrix = mesh_render_data_module.mesh_model_matrix_for_node(eye, anim_pose=inherited_body_pose)

    assert tuple(np.round(matrix[:3, 3], 4)) == (10.0, 3.0, 4.0)


def test_carth_pmha01_bas_head_stays_socket_local_for_pause2() -> None:
    k1_path = os.environ.get("K1_PATH", "")
    if not k1_path or not os.path.isdir(k1_path):
        pytest.skip("K1 install not available")

    from src.adapters.rendering.moderngl_resources import _build_vbo_data
    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.assets.resource_manager import ResourceManager
    from src.systems.bas.preview_composer import build_bas_preview_model

    manager = ResourceManager()
    assert manager.set_k1_dir(k1_path)
    SuperModelResolver.configure(manager)
    body = manager.load_model("P_CarthBB", "K1")
    head = manager.load_model("pmha01", "K1")
    assert body is not None
    assert head is not None
    preview = build_bas_preview_model(
        body_model=body,
        attachment_models={"head": head},
        attachment_transforms={"head": {"position": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]}},
    )
    engine = AnimationEngine(body)
    assert engine.play("pause2", loop=True, blend=False)
    engine.seek(9.82)
    pose = engine.evaluate(9.82)
    pose._gr_animation_source_model_id = id(body)
    pose._gr_animation_source_model_name = body.name
    pose._gr_animation_name = "pause2"

    def head_bounds(anim_pose):
        for mesh_data in mesh_render_data_module.iter_mesh_render_data(
            preview,
            anim_pose=anim_pose,
            allow_cpu_skinning=False,
            vbo_builder=_build_vbo_data,
        ):
            if getattr(mesh_data.source, "name", "") != "head" or not getattr(mesh_data.source, "_gr_bas_attachment_layer", False):
                continue
            positions = np.asarray(mesh_data.positions, dtype=np.float32)
            world_matrix = np.asarray(mesh_data.world_matrix, dtype=np.float32).reshape(4, 4)
            world = (world_matrix @ np.column_stack([positions, np.ones(len(positions), dtype=np.float32)]).T).T[:, :3]
            return positions, world, mesh_data
        raise AssertionError("pmha01 head skin mesh not found")

    rest_vbo, rest_world, rest_mesh = head_bounds(None)
    anim_vbo, anim_world, anim_mesh = head_bounds(pose)

    assert float(rest_world[:, 2].min()) == pytest.approx(1.50, abs=0.08)
    assert float(rest_world[:, 2].max()) < 1.90
    assert float(anim_world[:, 2].min()) == pytest.approx(1.50, abs=0.08)
    assert float(anim_world[:, 2].max()) < 1.90
    assert rest_mesh.is_skinned is False
    assert anim_mesh.is_skinned is False
    assert anim_mesh.skinning_cpu_fallback is True
    assert float(anim_vbo[:, 2].max()) < 0.35
    assert float(np.linalg.norm(anim_world.max(axis=0) - anim_world.min(axis=0))) < 0.85


def test_carth_pmha01_bas_head_uses_standalone_head_local_tracks_for_pause2() -> None:
    k1_path = os.environ.get("K1_PATH", "")
    if not k1_path or not os.path.isdir(k1_path):
        pytest.skip("K1 install not available")

    from src.adapters.rendering.moderngl_resources import _build_vbo_data
    from src.core.animation.animation_engine import AnimationEngine, SuperModelResolver
    from src.core.assets.resource_manager import ResourceManager
    from src.systems.bas.preview_composer import build_bas_preview_model

    manager = ResourceManager()
    assert manager.set_k1_dir(k1_path)
    SuperModelResolver.configure(manager)
    body = manager.load_model("P_CarthBB", "K1")
    head = manager.load_model("pmha01", "K1")
    assert body is not None
    assert head is not None
    preview = build_bas_preview_model(body_model=body, attachment_models={"head": head})

    body_engine = AnimationEngine(body)
    head_engine = AnimationEngine(head)
    assert body_engine.play("pause2", loop=True, blend=False)
    assert head_engine.play("pause2", loop=True, blend=False)
    body_pose = body_engine.evaluate(9.82)
    body_pose._gr_animation_source_model_id = id(body)
    body_pose._gr_animation_source_model_name = body.name
    body_pose._gr_animation_name = "pause2"
    head_pose = head_engine.evaluate(9.82)
    head_pose._gr_animation_source_model_id = id(head)
    head_pose._gr_animation_source_model_name = head.name
    head_pose._gr_animation_name = "pause2"

    head_nodes = {str(n.name).lower(): n for n in head.all_nodes()}
    bas_nodes = {
        str(n.name).lower(): n
        for n in preview.all_nodes()
        if getattr(n, "_gr_bas_attachment_layer", False)
    }
    standalone_root = head_nodes["pmha01"]
    bas_root = bas_nodes["pmha01"]
    standalone_anchor = head_nodes["necklwr_g"]
    bas_anchor = bas_nodes["necklwr_g"]
    standalone_root_inv = np.linalg.inv(mesh_render_data_module.mesh_model_matrix_for_node(standalone_root, anim_pose=head_pose))
    bas_root_inv = np.linalg.inv(mesh_render_data_module.mesh_model_matrix_for_node(bas_root, anim_pose=body_pose))
    standalone_anchor_inv = np.linalg.inv(
        mesh_render_data_module.mesh_model_matrix_for_node(standalone_anchor, anim_pose=head_pose)
    )
    bas_anchor_inv = np.linalg.inv(mesh_render_data_module.mesh_model_matrix_for_node(bas_anchor, anim_pose=body_pose))

    for name in ("rootdummy", "torso_g", "torsoupr_g"):
        standalone_local = standalone_root_inv @ mesh_render_data_module.mesh_model_matrix_for_node(
            head_nodes[name], anim_pose=head_pose
        )
        bas_local = bas_root_inv @ mesh_render_data_module.mesh_model_matrix_for_node(bas_nodes[name], anim_pose=body_pose)
        assert not np.allclose(bas_local[:3, 3], standalone_local[:3, 3], atol=1.0e-4), name

    for name in ("hturn_g", "head_g", "talkdummy", "eyera", "eyela", "f_jaw_g"):
        standalone_local = standalone_anchor_inv @ mesh_render_data_module.mesh_model_matrix_for_node(
            head_nodes[name], anim_pose=head_pose
        )
        bas_local = bas_anchor_inv @ mesh_render_data_module.mesh_model_matrix_for_node(bas_nodes[name], anim_pose=body_pose)
        assert np.allclose(bas_local[:3, 3], standalone_local[:3, 3], atol=1.0e-4), name

    def head_skin_root_local(model, pose, *, bas_layer: bool):
        for mesh_data in mesh_render_data_module.iter_mesh_render_data(
            model,
            anim_pose=pose,
            allow_cpu_skinning=True,
            vbo_builder=_build_vbo_data,
        ):
            if getattr(mesh_data.source, "name", "") != "head":
                continue
            if bool(getattr(mesh_data.source, "_gr_bas_attachment_layer", False)) != bool(bas_layer):
                continue
            positions = np.asarray(mesh_data.positions, dtype=np.float32)
            world_matrix = np.asarray(mesh_data.world_matrix, dtype=np.float32).reshape(4, 4)
            world = (world_matrix @ np.column_stack([positions, np.ones(len(positions), dtype=np.float32)]).T).T[:, :3]
            root_inv = bas_anchor_inv if bas_layer else standalone_anchor_inv
            return (root_inv @ np.column_stack([world, np.ones(len(world), dtype=np.float32)]).T).T[:, :3]
        raise AssertionError("head skin mesh not found")

    standalone_head = head_skin_root_local(head, head_pose, bas_layer=False)
    attached_head = head_skin_root_local(preview, body_pose, bas_layer=True)

    assert standalone_head.shape == attached_head.shape
    placement_delta = attached_head - standalone_head
    deformation_residual = placement_delta - placement_delta.mean(axis=0, keepdims=True)
    assert float(np.max(np.abs(deformation_residual))) < 1.0e-4


def test_pygfx_optional_scene_camera_light_cube_smoke() -> None:
    gfx = pytest.importorskip("pygfx")

    scene = gfx.Scene()
    camera = gfx.PerspectiveCamera(45.0, 1.0)
    light = gfx.AmbientLight((0.08, 0.08, 0.08), 1.0)
    geometry = gfx.Geometry(
        positions=np.asarray(
            [
                (-0.5, -0.5, 0.0),
                (0.5, -0.5, 0.0),
                (0.0, 0.5, 0.0),
            ],
            dtype=np.float32,
        ),
        indices=np.asarray([[0, 1, 2]], dtype=np.uint32),
    )
    cube = gfx.Mesh(geometry, gfx.MeshPhongMaterial(color=(0.7, 0.8, 0.9, 1.0)))
    scene.add(light, cube)

    assert camera is not None
    assert cube in scene.children
    assert light in scene.children


def test_existing_wgpu_viewport_backend_still_imports() -> None:
    renderer = WgpuRenderer(RendererBackend.WGPU_AUTO, settings=RendererSettings())

    assert renderer.backend_id == RendererBackend.WGPU_AUTO.value


def test_pygfx_diagnostics_request_native_surface_passthrough() -> None:
    renderer = PygfxViewportRenderer(settings=RendererSettings())

    assert renderer.get_diagnostics()["native_surface_passthrough"] is True
    assert renderer.get_diagnostics()["supports_gizmo_drawing"] is False


def test_pygfx_keeps_legacy_overlay_gizmo_and_cpu_picking_contract() -> None:
    caps = PygfxViewportRenderer.probe_availability()
    renderer = PygfxViewportRenderer(settings=RendererSettings())

    assert caps.supports_textures is True
    assert caps.supports_gizmo_drawing is False
    assert caps.supports_gizmo_interaction is True
    assert caps.supports_cpu_ray_picking is True
    assert caps.supports_gpu_id_picking is False
    assert renderer.use_native_gizmo_overlay is False
    assert renderer.use_native_skeleton_overlay is True
    assert renderer.use_native_light_helper_overlay is False


def test_pygfx_camera_uses_z_up_reference() -> None:
    renderer = PygfxViewportRenderer(settings=RendererSettings())
    gfx = pytest.importorskip("pygfx")
    renderer.camera = gfx.PerspectiveCamera(45.0, 1.0)

    renderer._configure_camera_up()

    assert tuple(float(v) for v in renderer.camera.local.reference_up[:3]) == pytest.approx((0.0, 0.0, 1.0))


def test_pygfx_grid_is_lightweight_z_up_line_grid() -> None:
    renderer = PygfxViewportRenderer(settings=RendererSettings())
    gfx = pytest.importorskip("pygfx")

    grid = renderer._create_z_up_grid(gfx, size=100.0, divisions=40)

    positions = np.asarray(grid.geometry.positions.data)
    assert positions.shape[0] == (40 + 1) * 4
    assert np.allclose(positions[:, 2], 0.0)
    assert type(grid.material).__name__ == "LineSegmentMaterial"


def test_viewport_pipeline_keeps_tool_overlay_for_pygfx_live_surface() -> None:
    from src.gui.viewports.viewport_core.widgets.rendering_pipeline import ViewportRenderingPipelineMixin

    source = inspect.getsource(ViewportRenderingPipelineMixin._render_frame)

    assert "_gpu_renderer_requires_native_surface_passthrough" in source
    assert "_draw_live_surface_tool_overlay" in source
    assert "_update_live_surface_diagnostics()" in source


def test_viewport_pipeline_skips_duplicate_cpu_skeleton_overlay_when_native_supported() -> None:
    from src.gui.viewports.viewport_core.widgets.rendering_pipeline import ViewportRenderingPipelineMixin

    overlay_source = inspect.getsource(ViewportRenderingPipelineMixin._draw_gpu_viewport_overlays)
    live_source = inspect.getsource(ViewportRenderingPipelineMixin._draw_live_surface_tool_overlay)
    dirty_source = inspect.getsource(ViewportRenderingPipelineMixin._can_skip_live_overlay_rebuild)
    capability_source = inspect.getsource(ViewportRenderingPipelineMixin._gpu_renderer_supports_native_skeleton_overlay)

    assert "native_skeleton = self._gpu_renderer_supports_native_skeleton_overlay()" in overlay_source
    assert "self._renderer.show_bones and not native_skeleton" in overlay_source
    assert "_can_skip_animation_cpu_overlay()" in live_source
    assert "_can_skip_animation_cpu_overlay()" in dirty_source
    assert "skeleton_overlay_supported" in capability_source


def test_pygfx_animation_uses_native_skinning_and_retained_overlay_contract() -> None:
    scene_source = inspect.getsource(PygfxSceneBridge.update_scene)
    renderer_source = inspect.getsource(PygfxViewportRenderer.render)
    cache_source = inspect.getsource(PygfxMeshCache._build_geometry)

    assert "allow_cpu_skinning=False" in scene_source
    assert "update_skin_palette" in scene_source
    assert "can_update_animation_only" in renderer_source
    assert "update_animation(scene" in renderer_source
    assert "update_skeleton_overlay" in renderer_source
    assert "skin_indices" in cache_source
    assert "skin_weights" in cache_source


def test_pygfx_live_surface_skips_legacy_hover_outline_to_avoid_duplicate_edges() -> None:
    from src.gui.viewports.viewport_core.widgets.drag_interactions import ViewportDragInteractionsMixin

    source = inspect.getsource(ViewportDragInteractionsMixin._draw_hovered_mesh_outline)

    assert "pygfx_wgpu" in source
    assert "canvas.is_live_surface()" in source


def test_pygfx_live_surface_uses_native_helper_overlay_not_screen_markers() -> None:
    from src.gui.viewports.viewport_core.widgets.overlay_layers import ViewportOverlayLayersMixin
    from src.gui.viewports.viewport_core.widgets.rendering_pipeline import ViewportRenderingPipelineMixin

    overlay_source = inspect.getsource(ViewportOverlayLayersMixin._draw_wgpu_helper_markers)
    pipeline_source = inspect.getsource(ViewportRenderingPipelineMixin._render_gpu_frame)

    assert "pygfx_wgpu" in overlay_source
    assert "canvas.is_live_surface()" in overlay_source
    assert "_build_pygfx_helper_render_data()" in pipeline_source
    assert "helper_render_data=helper_render_data" in pipeline_source


def test_pygfx_scene_bridge_builds_native_overlay_lines() -> None:
    from src.core.gizmo.gizmo_draw_data import GizmoDrawCommand, GizmoRenderData

    bridge = PygfxSceneBridge(_FakeGfx, _FakeScene(), PygfxMeshCache())
    gizmo = GizmoRenderData(
        commands=(
            GizmoDrawCommand(
                kind="line",
                points=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
                colour=(1.0, 0.0, 0.0, 1.0),
                thickness=3.0,
            ),
            GizmoDrawCommand(
                kind="polyline",
                points=((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0, 1.0)),
                colour=(0.0, 1.0, 0.0, 1.0),
                thickness=2.0,
            ),
        )
    )
    skeleton = SimpleNamespace(
        show_links=True,
        show_dots=True,
        bones=(
            SimpleNamespace(
                visible=True,
                selected=True,
                head_position=(0.0, 0.0, 0.0),
                tail_position=(0.0, 0.0, 1.0),
            ),
        ),
    )

    bridge.update_overlays(gizmo_render_data=gizmo, skeleton_render_data=skeleton)

    assert bridge.gizmo_overlay_segments == 3
    assert bridge.skeleton_overlay_segments == 1
    assert len(bridge._overlay_objects) >= 2


def test_pygfx_scene_bridge_builds_native_helper_points() -> None:
    bridge = PygfxSceneBridge(_FakeGfx, _FakeScene(), PygfxMeshCache())
    helpers = SimpleNamespace(
        helpers=(
            SimpleNamespace(position=(1.0, 2.0, 3.0), selected=False, hovered=False, visible=True),
            SimpleNamespace(position=(2.0, 3.0, 4.0), selected=False, hovered=True, visible=True),
            SimpleNamespace(position=(3.0, 4.0, 5.0), selected=True, hovered=False, visible=True),
        )
    )

    bridge.update_overlays(helper_render_data=helpers)

    point_names = {obj.name for obj in bridge._overlay_objects}
    assert {"pygfx-helper", "pygfx-helper-hover", "pygfx-helper-selected"} <= point_names


def test_pygfx_scene_bridge_installs_default_lighting_when_scene_lights_missing() -> None:
    scene = _FakeScene()
    bridge = PygfxSceneBridge(_FakeGfx, scene, PygfxMeshCache())

    bridge.update_lighting(None)

    assert bridge._ambient_light is not None
    assert bridge._ambient_light.intensity >= 0.55
    assert bridge._default_directional_light is not None
    assert bridge._default_directional_light in scene.children


def test_pygfx_mesh_cache_applies_toolbar_view_style_without_geometry_rebuild() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data()
    record = cache.get_or_create(data, _FakeGfx, scene, selected=False)
    cache.begin_frame()

    cache.apply_view_style(
        show_solid=True,
        show_wireframe=True,
        show_texture=False,
        render_mode="flat",
        xray=True,
    )

    assert cache.geometry_updates_this_frame == 0
    assert type(record.material).__name__ == "MeshBasicMaterial"
    assert record.mesh.visible is True
    assert record.edge_mesh.visible is True
    assert record.material.wireframe is False
    assert record.material.opacity == pytest.approx(0.38)


def test_pygfx_mesh_cache_uses_deduped_line_edges_not_material_wireframe() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data()
    data.positions = np.asarray([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], dtype=np.float32)
    data.indices = np.asarray([0, 1, 2, 2, 1, 3], dtype=np.uint32)
    record = cache.get_or_create(data, _FakeGfx, scene, selected=False)

    cache.apply_view_style(show_solid=False, show_wireframe=True, wire_color=(0.18, 0.62, 0.95, 1.0))

    assert record.edge_mesh is not None
    assert record.edge_mesh.geometry is not record.geometry
    assert record.edge_mesh.geometry.positions.data.shape == (10, 3)
    assert record.edge_material.color == pytest.approx((0.18, 0.62, 0.95, 1.0))


def test_pygfx_skinned_wire_overlay_uses_skinned_mesh_to_follow_palette() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _skinned_mesh_data()
    record = cache.get_or_create(data, _FakeGfx, scene, selected=False)

    cache.apply_view_style(show_solid=True, show_wireframe=True, wire_color=(0.18, 0.62, 0.95, 1.0))

    assert record.edge_mesh is not None
    assert isinstance(record.edge_mesh, _FakeSkinnedMesh)
    assert record.edge_mesh.geometry is record.geometry
    assert record.edge_mesh.skeleton is record.skeleton
    assert record.edge_material.wireframe is True
    assert record.edge_material.color == pytest.approx((0.18, 0.62, 0.95, 1.0))


def test_pygfx_animation_only_path_rebuilds_cpu_fallback_attachment_geometry() -> None:
    bridge = PygfxSceneBridge(_FakeGfx, _FakeScene(), PygfxMeshCache())
    data = _mesh_data(source_revision=(8, 1, 0, 250))
    data.skinning_cpu_fallback = True
    bridge.mesh_cache.get_or_create(data, _FakeGfx, bridge.scene, selected=False)

    assert bridge.can_update_animation_only() is False


def test_pygfx_edge_overlay_copies_primary_mesh_transform_when_created_after_sync() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    record = cache.get_or_create(_mesh_data(), _FakeGfx, scene, selected=False)
    matrix = np.eye(4, dtype=np.float32)
    matrix[0, 3] = 12.0
    matrix[1, 3] = -5.0
    matrix[2, 3] = 2.5
    record.mesh.local.matrix = matrix

    cache.apply_view_style(show_solid=True, show_wireframe=True)

    assert record.edge_mesh is not None
    assert np.allclose(record.edge_mesh.local.matrix, matrix)


def test_pygfx_scene_bridge_clear_removes_retained_edge_meshes() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    bridge = PygfxSceneBridge(_FakeGfx, scene, cache)
    record = cache.get_or_create(_mesh_data(), _FakeGfx, scene, selected=False)
    cache.apply_view_style(show_solid=False, show_wireframe=True)
    edge_mesh = record.edge_mesh

    assert edge_mesh in scene.children

    bridge.clear()

    assert record.mesh not in scene.children
    assert edge_mesh not in scene.children
    assert cache.records == {}


def test_pygfx_hover_and_wire_edges_use_distinct_wgpu_palette_colors() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data()
    record = cache.get_or_create(data, _FakeGfx, scene, selected=False, hovered=True)

    cache.apply_view_style(
        show_solid=True,
        show_wireframe=False,
        show_mesh_hover=True,
        wire_color=(0.18, 0.62, 0.95, 1.0),
        hover_color=(0.0, 215 / 255.0, 181 / 255.0, 0.45),
    )

    assert record.edge_mesh.visible is True
    assert record.edge_material.color == pytest.approx((0.0, 215 / 255.0, 181 / 255.0, 0.45))

    cache.update_selection(_FakeGfx, set(), None)
    cache.apply_view_style(
        show_solid=False,
        show_wireframe=True,
        wire_color=(0.18, 0.62, 0.95, 1.0),
        hover_color=(0.0, 215 / 255.0, 181 / 255.0, 0.45),
    )

    assert record.edge_mesh.visible is True
    assert record.edge_material.color == pytest.approx((0.18, 0.62, 0.95, 1.0))


def test_pygfx_mesh_cache_maps_realistic_shaded_flat_and_mesh_modes() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    record = cache.get_or_create(_mesh_data(material_revision=("texture",)), _FakeGfx, scene, selected=False)

    cache.begin_frame()
    cache.apply_view_style(show_solid=True, show_wireframe=False, show_texture=True, render_mode="realistic")
    assert type(record.material).__name__ == "MeshPhongMaterial"
    assert record.material.map is record.diffuse_map
    assert record.mesh.visible is True
    assert record.edge_mesh is None or record.edge_mesh.visible is False

    cache.apply_view_style(show_solid=True, show_wireframe=False, show_texture=True, render_mode="shaded")
    assert type(record.material).__name__ == "MeshPhongMaterial"
    assert record.material.map is record.diffuse_map
    assert record.material.flat_shading is True

    cache.apply_view_style(show_solid=True, show_wireframe=False, show_texture=True, render_mode="flat")
    assert type(record.material).__name__ == "MeshBasicMaterial"
    assert record.material.map is record.diffuse_map

    cache.apply_view_style(show_solid=False, show_wireframe=True, show_texture=True, render_mode="realistic")
    assert record.mesh.visible is False
    assert record.edge_mesh is not None
    assert record.edge_mesh.visible is True

    cache.apply_view_style(show_solid=True, show_wireframe=True, show_texture=True, render_mode="realistic")
    assert record.mesh.visible is True
    assert record.edge_mesh.visible is True


def test_pygfx_mesh_cache_uses_retained_texture_map_without_geometry_rebuild() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data(material_revision=("texture",))
    record = cache.get_or_create(data, _FakeGfx, scene, selected=False)

    assert record.diffuse_map is not None
    assert record.material.map is record.diffuse_map
    assert cache.diagnostics()["texture_cache_size"] == 1

    cache.begin_frame()
    cache.apply_view_style(show_texture=False)
    assert cache.geometry_updates_this_frame == 0
    assert record.material.map is None

    cache.apply_view_style(show_texture=True)
    assert cache.geometry_updates_this_frame == 0
    assert record.material.map is record.diffuse_map

    cache.apply_view_style(show_texture=True, show_diffuse=False)
    assert cache.geometry_updates_this_frame == 0
    assert record.material.map is None


def test_pygfx_mesh_cache_uses_retained_lightmap_uv1_channel() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    data = _mesh_data(material_revision=("lightmap",))
    data.uvs0 = np.asarray([(0.0, 0.0), (0.5, 0.25), (1.0, 1.0)], dtype=np.float32)
    data.uvs1 = np.asarray([(0.0, 0.1), (0.5, 0.6), (1.0, 0.9)], dtype=np.float32)
    record = cache.get_or_create(data, _FakeGfx, scene, selected=False)

    assert record.diffuse_map is not None
    assert record.lightmap_map is not None
    assert record.lightmap_map.kwargs["uv_channel"] == 1

    cache.begin_frame()
    cache.apply_view_style(show_texture=True, show_lightmap=True)
    assert record.material.light_map is record.lightmap_map
    assert record.material.light_map_intensity == pytest.approx(0.55)

    cache.apply_view_style(show_texture=True, show_lightmap=False)
    assert record.material.light_map is None


def test_pygfx_mesh_cache_applies_explicit_culling_without_changing_default() -> None:
    cache = PygfxMeshCache()
    scene = _FakeScene()
    record = cache.get_or_create(_mesh_data(material_revision=("texture",)), _FakeGfx, scene, selected=False)

    cache.apply_view_style(cull_faces=False)
    assert record.material.side == "both"

    cache.apply_view_style(cull_faces=True)
    assert record.material.side == "front"

    data = _mesh_data(mesh_id=8, material_revision=("texture",))
    data.material.double_sided = True
    double_sided = cache.get_or_create(data, _FakeGfx, scene, selected=False)
    cache.apply_view_style(cull_faces=True)
    assert double_sided.material.side == "both"


def test_pygfx_grid_toggle_updates_native_helper_visibility() -> None:
    renderer = PygfxViewportRenderer(settings=RendererSettings())
    renderer._grid_helper = SimpleNamespace(visible=True)
    renderer.show_grid = False

    renderer._apply_view_state()

    assert renderer._grid_helper.visible is False


def test_pygfx_renderer_applies_theme_tokens_to_scene_helpers() -> None:
    class Theme:
        def color(self, key, fallback=""):
            return {
                "viewport.background": "#112233",
                "viewport.gridMinor": "#445566",
            }.get(key, fallback)

    renderer = PygfxViewportRenderer(settings=RendererSettings())
    renderer._gfx = _FakeGfx
    renderer.scene = _FakeScene()
    renderer._install_empty_scene_helpers(_FakeGfx)

    renderer.set_theme_colors(Theme())

    assert renderer.viewport_background == pytest.approx((0x11 / 255.0, 0x22 / 255.0, 0x33 / 255.0))
    assert renderer.grid_minor_color == pytest.approx((0x44 / 255.0, 0x55 / 255.0, 0x66 / 255.0))
    assert renderer._background.color == pytest.approx((*renderer.viewport_background, 1.0))
    assert renderer._grid_helper.material.color == pytest.approx((*renderer.grid_minor_color, 1.0))


def test_renderer_surface_host_keeps_live_surface_visible() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from src.gui.viewports.viewport_host import RendererSurfaceHost

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    host = RendererSurfaceHost()
    surface = QtWidgets.QWidget()

    host.resize(320, 200)
    host.set_renderer_surface(surface, backend_id=RendererBackend.PYGFX_WGPU.value, live_surface=True)
    host.show()
    app.processEvents()

    assert host.current_surface() is surface
    assert host.is_live_surface() is True
    assert surface.isVisible() is True
    assert host.overlay_layer_active() is False
