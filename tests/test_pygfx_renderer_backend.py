from __future__ import annotations

import inspect
import os
from types import SimpleNamespace

import numpy as np
import pytest

import src.adapters.rendering.pygfx_core.renderer as pygfx_renderer_module
from src.adapters.rendering.pygfx_core.scene_bridge import PygfxSceneBridge
from src.adapters.rendering.pygfx_core.mesh_cache import PygfxMeshCache
from src.adapters.rendering.pygfx_core.renderer import PygfxViewportRenderer
from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer
from src.adapters.rendering.renderer_factory import fallback_order, renderer_capabilities_snapshot
from src.core.rendering.renderer_backend import RendererBackend, normalize_renderer_backend, renderer_backend_label
from src.core.rendering.renderer_settings import RendererSettings


class _FakeGeometry:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeMaterial:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.side = ""


class _FakeLocal:
    def __init__(self):
        self.matrix = None
        self.position = None


class _FakeMesh:
    def __init__(self, geometry, material):
        self.geometry = geometry
        self.material = material
        self.local = _FakeLocal()
        self.name = ""


class _FakeGfx:
    Geometry = _FakeGeometry
    MeshPhongMaterial = _FakeMaterial
    Mesh = _FakeMesh

    class AmbientLight:
        def __init__(self, color, intensity=1.0):
            self.color = color
            self.intensity = intensity

    class DirectionalLight:
        def __init__(self, color, intensity=1.0):
            self.color = color
            self.intensity = intensity
            self.local = _FakeLocal()

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
    material = SimpleNamespace(
        material_id="mat-a",
        source_revision=material_revision,
        double_sided=False,
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


def test_pygfx_mesh_cache_retains_mesh_until_revision_changes() -> None:
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
    assert cache.geometry_updates_this_frame == 1
    assert cache.material_updates_this_frame == 0


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


def test_viewport_pipeline_skips_pil_overlay_for_pygfx_live_surface() -> None:
    from src.gui.viewports.viewport_core.widgets.rendering_pipeline import ViewportRenderingPipelineMixin

    source = inspect.getsource(ViewportRenderingPipelineMixin._render_frame)

    assert "_gpu_renderer_requires_native_surface_passthrough" in source
    assert "clear_overlay()" in source


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
