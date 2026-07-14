from __future__ import annotations

import sys
from pathlib import Path


def _install_payload_paths() -> None:
    repo = Path(__file__).resolve().parents[1]
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for path in reversed(_python_roots(repo)):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def test_cpu_painter_draws_background_geometry_before_foreground_regardless_of_centroid_depth() -> None:
    _install_payload_paths()
    from PIL import Image, ImageDraw
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.rendering.frame_core.renderer import FrameRenderer

    root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
    foreground = ModelNode(
        name="foreground",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(-1.0, -1.0, 5.0), (1.0, -1.0, 5.0), (0.0, 1.0, 5.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        faces=[(0, 1, 2)],
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        texture="fixture_foreground",
        diffuse=(1.0, 0.0, 0.0),
    )
    background = ModelNode(
        name="sky_panel",
        flags=int(NodeFlags.MESH),
        parent=root,
        vertices=[(-1.0, -1.0, -5.0), (1.0, -1.0, -5.0), (0.0, 1.0, -5.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        faces=[(0, 1, 2)],
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)],
        texture="fixture_sky",
        diffuse=(0.0, 0.0, 1.0),
        background_geometry=True,
    )
    root.children.extend((foreground, background))
    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(KotorModel(name="sky_order", root_node=root))
    renderer._frame_view = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    renderer._frame_verts_cache = {}
    renderer._frame_norms_cache = {}
    renderer._iter_mesh_nodes = lambda: (foreground, background)
    renderer._get_world_verts_for_node = lambda node: list(node.vertices)
    renderer._get_world_normals_for_node = lambda node: list(node.normals)
    renderer._screen_size_lod_cap = lambda _width, _height: 100
    renderer._proj_batch = lambda vertices, _width, _height: [
        (50.0 + float(x) * 30.0, 50.0 - float(y) * 30.0, float(z)) for x, y, z in vertices
    ]
    renderer.show_solid = True
    renderer.show_wireframe = False
    renderer.selected_node = None

    image = Image.new("RGB", (100, 100), "black")
    renderer._draw_mesh_flat(ImageDraw.Draw(image), image, 100, 100)
    red, _green, blue = image.getpixel((50, 50))

    assert red > blue, "The foreground must overwrite a giant background panel in the CPU painter."
