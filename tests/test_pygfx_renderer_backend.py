from __future__ import annotations

import inspect
import os
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import src.adapters.rendering.pygfx_core.renderer as pygfx_renderer_module
from src.adapters.rendering.pygfx_core.scene_bridge import PygfxSceneBridge
from src.adapters.rendering.pygfx_core.mesh_cache import PygfxMeshCache
from src.adapters.rendering.pygfx_core.renderer import PygfxViewportRenderer
from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
from src.adapters.rendering.renderer_factory import fallback_order, renderer_capabilities_snapshot
from src.core.rendering.renderer_performance import ViewportFrameGovernor
from src.core.rendering.renderer_backend import RendererBackend, normalize_renderer_backend, renderer_backend_label
from src.core.rendering.renderer_settings import RendererSettings


class _FakeGeometry:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        if "positions" in kwargs:
            self.positions = _FakeBuffer(kwargs["positions"])
        if "normals" in kwargs:
            self.normals = _FakeBuffer(kwargs["normals"])
        if "texcoords" in kwargs:
            self.texcoords = _FakeBuffer(kwargs["texcoords"])
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


class _FakeGfx:
    Geometry = _FakeGeometry
    MeshPhongMaterial = MeshPhongMaterial
    MeshBasicMaterial = MeshBasicMaterial
    Mesh = _FakeMesh
    LineSegmentMaterial = _FakeMaterial
    PointsMaterial = _FakeMaterial
    Line = _FakeMesh
    Points = _FakeMesh

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


def _mesh_data(*, mesh_id=7, source_revision=(3, 1, 0), material_revision=(1, 0, 0, 0)):
    diffuse_texture_data = None
    if material_revision == ("texture",):
        diffuse = Image.new("RGBA", (2, 2), (180, 90, 40, 255))
        diffuse_texture_data = SimpleNamespace(
            texture_id="unit_diffuse",
            name="unit_diffuse",
            source=diffuse,
            source_revision=(id(diffuse), 2, 2),
        )
    material = SimpleNamespace(
        material_id="mat-a",
        source_revision=material_revision,
        double_sided=False,
        diffuse_texture_data=diffuse_texture_data,
    )
    return SimpleNamespace(
        mesh_id=mesh_id,
        source=SimpleNamespace(name="mesh-a"),
        positions=np.asarray([(0, 0, 0), (1, 0, 0), (0, 1, 0)], dtype=np.float32),
        normals=None,
        uvs0=None,
        indices=np.asarray([0, 1, 2], dtype=np.uint32),
        material=material,
        material_color=(0.5, 0.6, 0.7, 1.0),
        world_matrix=np.eye(4, dtype=np.float32),
        source_revision=source_revision,
    )


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
    assert renderer.use_native_skeleton_overlay is False
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
    assert record.material.map is None
    assert record.material.flat_shading is True

    cache.apply_view_style(show_solid=True, show_wireframe=False, show_texture=True, render_mode="flat")
    assert type(record.material).__name__ == "MeshBasicMaterial"
    assert record.material.map is None

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


def test_pygfx_grid_toggle_updates_native_helper_visibility() -> None:
    renderer = PygfxViewportRenderer(settings=RendererSettings())
    renderer._grid_helper = SimpleNamespace(visible=True)
    renderer.show_grid = False

    renderer._apply_view_state()

    assert renderer._grid_helper.visible is False


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
