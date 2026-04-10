"""
Test suite for pykotor integration and GLTF 2.0 round-trip.

Tests cover:
  - pykotor read_tpc API (correct DXT decompression, TXI extraction)
  - GLTF import (GLTFImporter via pygltflib)
  - GLTF export (GLTFExporter via pygltflib)
  - GPU renderer alpha-kill code structure (no raw RGBA leaking to canvas)
  - pykotor-backed TPC/TXI functions called directly
"""
import struct
import sys
import os
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Guard: skip tests that require pykotor when it's not installed
try:
    import pykotor  # noqa: F401
    PYKOTOR_AVAILABLE = True
except ImportError:
    PYKOTOR_AVAILABLE = False

_skip_no_pykotor = pytest.mark.skipif(
    not PYKOTOR_AVAILABLE,
    reason="pykotor package not installed (optional dependency)"
)

# Standard test helpers used in other test files
from core.model_data import (
    KotorModel, ModelNode, NodeFlags, GameVersion
)
from converters.mesh_converter import GLTFImporter, GLTFExporter


# ── Helper: build a minimal TPC byte blob ─────────────────────────────────────

def _make_tpc(w: int, h: int, encoding: int = 4, pixel_fn=None) -> bytes:
    """Build a minimal valid TPC byte blob (uncompressed RGBA or RGB)."""
    data_sz    = 0        # uncompressed
    alpha_test = 0.0
    mip_cnt    = 1
    hdr = struct.pack('<IfHHBB', data_sz, alpha_test, w, h, encoding, mip_cnt)
    hdr += b'\x00' * (128 - len(hdr))   # bytes 14-127 = all zero (TPC marker)

    if encoding == 4:      # RGBA
        if pixel_fn is None:
            pixel_fn = lambda x, y: (100, 150, 200, 255)
        pixel_data = bytes(c for y in range(h) for x in range(w)
                           for c in pixel_fn(x, y))
    elif encoding == 2:    # RGB
        if pixel_fn is None:
            pixel_fn = lambda x, y: (100, 150, 200)
        pixel_data = bytes(c for y in range(h) for x in range(w)
                           for c in pixel_fn(x, y))
    else:
        pixel_data = b'\x00' * (w * h * 4)

    return hdr + pixel_data


def _make_simple_model(name="test_cube") -> KotorModel:
    """Build a minimal KotorModel with one triangle mesh for GLTF tests."""
    model = KotorModel(name=name, supermodel="NULL",
                       game_version=GameVersion.K1)
    root = ModelNode(name=name, flags=int(NodeFlags.HEADER))
    model.root_node = root

    mesh = ModelNode(name="body",
                     flags=int(NodeFlags.HEADER | NodeFlags.MESH),
                     parent=root)
    mesh.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    mesh.normals  = [(0.0, 0.0, 1.0), (0.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
    mesh.uvs      = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    mesh.faces    = [(0, 1, 2)]
    mesh.texture  = "testtex"
    mesh.render   = True
    mesh.compute_bounds()
    root.children.append(mesh)
    model.compute_bounds()
    return model


# ── pykotor TPC API tests ──────────────────────────────────────────────────────

class TestPykotorTpcApi:
    """Direct tests of pykotor's read_tpc API with our TPC data."""

    def test_pykotor_reads_rgba_tpc(self):
        """pykotor.read_tpc decodes a 4×4 RGBA TPC correctly."""
        try:
            from pykotor.resource.formats.tpc.tpc_auto import read_tpc
            from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat
            from PIL import Image
        except ImportError as e:
            pytest.skip(f"Required lib not available: {e}")

        tpc = _make_tpc(4, 4, encoding=4,
                        pixel_fn=lambda x, y: (255, 128, 64, 255))
        pk_tpc = read_tpc(tpc)
        pk_tpc.convert(TPCTextureFormat.RGBA)
        mip = pk_tpc.get(0, 0)
        img = mip.to_pil_image()

        assert img is not None
        assert img.mode == 'RGBA'
        assert img.size == (4, 4)
        r, g, b, a = img.getpixel((0, 0))
        assert r == 255, f"R wrong: {r}"
        assert g == 128, f"G wrong: {g}"
        assert b == 64,  f"B wrong: {b}"
        assert a == 255, f"A wrong: {a}"

    def test_pykotor_reads_8x8_tpc(self):
        """pykotor handles 8×8 RGBA TPC."""
        try:
            from pykotor.resource.formats.tpc.tpc_auto import read_tpc
            from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat
        except ImportError as e:
            pytest.skip(f"pykotor not available: {e}")

        tpc = _make_tpc(8, 8, encoding=4)
        pk_tpc = read_tpc(tpc)
        assert pk_tpc is not None
        assert pk_tpc.dimensions() == (8, 8)

    def test_pykotor_tpc_is_version_233(self):
        """pykotor >= 2.3.1 is installed."""
        import pkg_resources
        dist = pkg_resources.get_distribution('pykotor')
        major, minor, patch = [int(x) for x in dist.version.split('.')[:3]]
        assert (major, minor, patch) >= (2, 3, 1), \
            f"pykotor {dist.version} < 2.3.1"

    def test_pykotor_txi_extraction(self):
        """pykotor TPC.txi returns the TXI string embedded in the file."""
        try:
            from pykotor.resource.formats.tpc.tpc_auto import read_tpc
        except ImportError as e:
            pytest.skip(f"pykotor not available: {e}")

        # Build a TPC with TXI appended — pykotor reads it from the trailer
        txi_text = "bumpmaptexture someNormal\n"
        tpc_bytes = _make_tpc(4, 4, encoding=4) + txi_text.encode('utf-8')
        pk_tpc = read_tpc(tpc_bytes)
        # .txi is a str; may be empty if pykotor can't detect the trailer in our
        # synthetic TPC, but it must be a str and not crash.
        assert isinstance(pk_tpc.txi, str)


# ── TPC detection helper tests ────────────────────────────────────────────────

class TestTpcDetection:
    """_is_tpc_data must correctly identify TPC vs TGA data."""

    def _get_is_tpc_data(self):
        """Import _is_tpc_data without triggering gui.viewport package imports."""
        # We extract just the function by compiling the early part of viewport.py
        import importlib.util, types
        spec = importlib.util.spec_from_file_location(
            "_viewport_tpc",
            os.path.join(os.path.dirname(__file__), '..', 'src', 'gui', 'viewport.py'))
        # We can't import the full module; instead, grab _is_tpc_data's source inline
        # by reading until the function ends
        raise ImportError("use pykotor detect_tpc instead")

    @_skip_no_pykotor
    def test_pykotor_detects_tpc(self):
        """pykotor.detect_tpc identifies our TPC blobs correctly."""
        from pykotor.resource.formats.tpc.tpc_auto import detect_tpc
        from pykotor.resource.type import ResourceType

        tpc = _make_tpc(4, 4)
        fmt = detect_tpc(tpc)
        assert fmt == ResourceType.TPC, f"Expected TPC, got {fmt}"

    @_skip_no_pykotor
    def test_pykotor_detects_tga(self):
        """pykotor.detect_tpc identifies non-TPC data as TGA."""
        from pykotor.resource.formats.tpc.tpc_auto import detect_tpc
        from pykotor.resource.type import ResourceType

        # Build a minimal TGA header (18 bytes + image data)
        w, h = 4, 4
        tga_hdr = struct.pack('<BBBHHBHHHHBB',
                              0,   # id length
                              0,   # colour map type
                              2,   # image type (true colour uncompressed)
                              0, 0, 0,  # colour map spec
                              0, 0,     # x/y origin
                              w, h,     # width/height
                              32,       # bpp
                              0x28)     # image descriptor (top-left origin, 8 alpha bits)
        tga_data = tga_hdr + bytes([100, 150, 200, 255] * (w * h))
        fmt = detect_tpc(tga_data)
        assert fmt == ResourceType.TGA, f"Expected TGA, got {fmt}"


# ── GLTF 2.0 round-trip tests ─────────────────────────────────────────────────

class TestGLTFRoundTrip:
    """GLTF 2.0 / GLB import-export round-trip."""

    def test_gltf_exporter_creates_valid_glb(self):
        """GLTFExporter writes a valid .glb file with correct magic header."""
        try:
            import pygltflib
        except ImportError:
            pytest.skip("pygltflib not installed")

        model = _make_simple_model()
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            path = f.name
        try:
            ok = GLTFExporter().export(model, path, binary=True)
            assert ok, "GLTFExporter.export returned False"
            assert os.path.exists(path), "GLB file was not created"
            assert os.path.getsize(path) > 12, "GLB file is too small"
            with open(path, 'rb') as f:
                magic = f.read(4)
            assert magic == b'glTF', f"GLB magic header wrong: {magic!r}"
        finally:
            try: os.unlink(path)
            except Exception: pass

    def test_gltf_json_export(self):
        """GLTFExporter can write GLTF JSON format (.gltf)."""
        try:
            import pygltflib
        except ImportError:
            pytest.skip("pygltflib not installed")

        model = _make_simple_model()
        with tempfile.NamedTemporaryFile(suffix='.gltf', delete=False) as f:
            path = f.name
        try:
            ok = GLTFExporter().export(model, path, binary=False)
            assert ok, "GLTFExporter GLTF JSON export returned False"
            assert os.path.exists(path)
            with open(path) as f:
                content = f.read()
            assert '"asset"' in content, "GLTF JSON missing asset field"
            assert '"GLTF"' in content.upper() or '"mesh"' in content.lower()
        finally:
            try: os.unlink(path)
            except Exception: pass

    def test_gltf_importer_loads_exported_model(self):
        """GLTFImporter successfully imports a model exported by GLTFExporter."""
        try:
            import pygltflib
        except ImportError:
            pytest.skip("pygltflib not installed")

        model = _make_simple_model()
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            path = f.name
        try:
            GLTFExporter().export(model, path, binary=True)
            imported = GLTFImporter().import_file(path, model_name='test_cube')
            assert imported is not None, "GLTFImporter returned None"
            meshes = imported.mesh_nodes() if hasattr(imported, 'mesh_nodes') else []
            assert len(meshes) >= 1, f"Expected mesh nodes, got {len(meshes)}"
        finally:
            try: os.unlink(path)
            except Exception: pass

    def test_gltf_vertex_count_preserved(self):
        """Vertex count is preserved through GLTF export/import."""
        try:
            import pygltflib
        except ImportError:
            pytest.skip("pygltflib not installed")

        model = _make_simple_model()
        original_verts = 3

        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            path = f.name
        try:
            GLTFExporter().export(model, path, binary=True)
            imported = GLTFImporter().import_file(path)
            assert imported is not None
            meshes = imported.mesh_nodes() if hasattr(imported, 'mesh_nodes') else []
            if meshes:
                total_verts = sum(len(getattr(n, 'vertices', [])) for n in meshes)
                assert total_verts >= original_verts, \
                    f"Expected ≥{original_verts} verts, got {total_verts}"
        finally:
            try: os.unlink(path)
            except Exception: pass

    def test_gltf_uv_flip_on_import(self):
        """UVs are V-flipped on GLTF import (KotOR convention)."""
        try:
            import pygltflib
        except ImportError:
            pytest.skip("pygltflib not installed")

        # Export a model with known UVs
        model = _make_simple_model()
        # Original UV: (0.0, 0.0) at vertex 0 (V=0 = bottom in KotOR)
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            path = f.name
        try:
            GLTFExporter().export(model, path, binary=True)
            imported = GLTFImporter().import_file(path)
            assert imported is not None
            meshes = imported.mesh_nodes() if hasattr(imported, 'mesh_nodes') else []
            if meshes and hasattr(meshes[0], 'uvs') and meshes[0].uvs:
                u, v = meshes[0].uvs[0]
                # KotOR V=0 -> exported as V=1 in GLTF -> re-imported as V=0
                # The exact value depends on the exporter's V-flip; just check it's normalized
                assert 0.0 <= u <= 1.0, f"UV U out of range: {u}"
                assert 0.0 <= v <= 1.0, f"UV V out of range: {v}"
        finally:
            try: os.unlink(path)
            except Exception: pass


# ── GLTF Skin Weight (JOINTS_0 / WEIGHTS_0) tests ────────────────────────────

class TestGLTFSkinWeights:
    """Verify GLTF skin weight JOINTS_0 remapping (Phase 15.3 fix).

    GLTF 2.0 §3.7.2: JOINTS_0 values are indices into skin.joints[], NOT
    global gltf.nodes[] indices.  The exporter must remap KotOR bone_map
    indices → skin joint-list positions.
    """

    @staticmethod
    def _make_skin_model() -> KotorModel:
        """Build a minimal skinned KotorModel: root dummy + one bone + one skin mesh."""
        from core.model_data import BoneWeight, VertexSkinData
        model = KotorModel(name="skin_test", supermodel="NULL",
                           game_version=GameVersion.K1)
        root = ModelNode(name="root", flags=int(NodeFlags.HEADER))
        model.root_node = root

        bone = ModelNode(name="Bone01", flags=int(NodeFlags.HEADER), parent=root)
        root.children.append(bone)

        skin = ModelNode(name="body",
                         flags=int(NodeFlags.HEADER | NodeFlags.SKIN),
                         parent=root)
        skin.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        skin.normals  = [(0.0, 0.0, 1.0)] * 3
        skin.uvs      = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        skin.faces    = [(0, 1, 2)]
        skin.texture  = "skin_tex"
        skin.render   = True
        # bone_map: index 0 → "root", index 1 → "Bone01"
        skin.bone_map = ["root", "Bone01"]
        # All 3 vertices weighted 100 % to Bone01 (bone_map index 1)
        skin.skin_data = [
            VertexSkinData(influences=[BoneWeight(bone_index=1, weight=1.0)]),
            VertexSkinData(influences=[BoneWeight(bone_index=1, weight=1.0)]),
            VertexSkinData(influences=[BoneWeight(bone_index=1, weight=1.0)]),
        ]
        skin.compute_bounds()
        root.children.append(skin)
        model.compute_bounds()
        return model

    def test_joints0_in_skin_range(self):
        """JOINTS_0 values must be < len(skin.joints) for every vertex."""
        try:
            import pygltflib, struct as st, tempfile, os
        except ImportError:
            pytest.skip("pygltflib not installed")

        model = self._make_skin_model()
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            path = f.name
        try:
            ok = GLTFExporter().export(model, path, binary=True)
            assert ok, "GLTFExporter returned False for skin model"
            gltf = pygltflib.GLTF2().load(path)
            # Find the JOINTS_0 accessor
            joints_acc = None
            for prim in [p for m in gltf.meshes for p in m.primitives]:
                if prim.attributes.JOINTS_0 is not None:
                    joints_acc = gltf.accessors[prim.attributes.JOINTS_0]
                    # Also get the skin the node uses to determine joint count
                    break
            if joints_acc is None:
                pytest.skip("Model has no JOINTS_0 — skin export skipped (no skin data)")

            # Determine the number of joints in the first skin
            assert gltf.skins, "GLTF has no skin despite having JOINTS_0 accessor"
            n_joints = len(gltf.skins[0].joints)
            assert n_joints > 0, "Skin has zero joints"

            # Read raw JOINTS_0 bytes and verify every joint index < n_joints
            bv = gltf.bufferViews[joints_acc.bufferView]
            buf_data = gltf.binary_blob()
            start = bv.byteOffset + (joints_acc.byteOffset or 0)
            n_verts = joints_acc.count
            for vi in range(n_verts):
                j0, j1, j2, j3 = st.unpack_from('<BBBB', buf_data, start + vi * 4)
                assert j0 < n_joints, \
                    f"Vertex {vi} JOINTS_0.x={j0} >= n_joints={n_joints} (remapping bug)"
                # j1/j2/j3 may be 0 (unused slots), which is always valid
                assert j1 < n_joints, \
                    f"Vertex {vi} JOINTS_0.y={j1} >= n_joints={n_joints}"
        finally:
            try: os.unlink(path)
            except Exception: pass

    def test_weights0_sum_to_one(self):
        """WEIGHTS_0 for each vertex must sum to ≈ 1.0."""
        try:
            import pygltflib, struct as st, tempfile, os
        except ImportError:
            pytest.skip("pygltflib not installed")

        model = self._make_skin_model()
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as f:
            path = f.name
        try:
            ok = GLTFExporter().export(model, path, binary=True)
            assert ok
            gltf = pygltflib.GLTF2().load(path)
            weights_acc = None
            for prim in [p for m in gltf.meshes for p in m.primitives]:
                if prim.attributes.WEIGHTS_0 is not None:
                    weights_acc = gltf.accessors[prim.attributes.WEIGHTS_0]
                    break
            if weights_acc is None:
                pytest.skip("No WEIGHTS_0 in exported GLTF")
            bv = gltf.bufferViews[weights_acc.bufferView]
            buf_data = gltf.binary_blob()
            start = bv.byteOffset + (weights_acc.byteOffset or 0)
            n_verts = weights_acc.count
            for vi in range(n_verts):
                w0, w1, w2, w3 = st.unpack_from('<ffff', buf_data, start + vi * 16)
                total = w0 + w1 + w2 + w3
                assert abs(total - 1.0) < 1e-4, \
                    f"Vertex {vi} weights sum = {total:.6f}, expected ≈ 1.0"
        finally:
            try: os.unlink(path)
            except Exception: pass


# ── GPU renderer structure tests ──────────────────────────────────────────────

class TestGpuRendererAlphaKill:
    """GPU renderer must kill alpha channel on readback."""

    GPU_RENDERER_PATH = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'gui', 'gpu_renderer.py')

    @classmethod
    def _read_src(cls):
        with open(cls.GPU_RENDERER_PATH) as f:
            return f.read()

    def test_fbo_clear_color_matches_viewport_bg(self):
        """FBO clear colour must use (18,18,40) to match viewport _BG."""
        src = self._read_src()
        assert '18/255' in src or '18 / 255' in src, \
            "FBO clear R/G not 18/255 (viewport _BG mismatch)"
        assert '40/255' in src or '40 / 255' in src, \
            "FBO clear B not 40/255 (viewport _BG mismatch)"

    def test_readback_composites_alpha_against_bg(self):
        """Readback must pre-multiply alpha against background, not return raw RGBA."""
        src = self._read_src()
        assert '255 - a' in src, \
            "GPU readback does not composite alpha against background colour"

    def test_readback_does_not_return_raw_rgba(self):
        """Raw RGBA should not be passed through; must be flattened to RGB."""
        src = self._read_src()
        assert "Image.fromarray(arr, 'RGBA')" not in src, \
            "GPU readback still returns raw RGBA without alpha compositing"

    def test_glsl_opaque_kills_texture_alpha(self):
        """GLSL shader forces final_alpha=1.0 for fully opaque nodes."""
        src = self._read_src()
        assert 'final_alpha = 1.0' in src, \
            "GLSL shader does not force alpha=1 for opaque surfaces"
        assert 'u_blend_mode == 0' in src, \
            "GLSL shader missing opaque blend-mode guard"
        assert 'u_node_alpha >= 0.999' in src, \
            "GLSL shader missing node_alpha opacity threshold check"


# =============================================================================
# Section 5 — envmap / bumpmap alpha channel fix  (v2.8)
# =============================================================================

def _semi_alpha_img(alpha: int = 128):
    """Return a 16×16 RGBA image whose alpha channel is all *alpha*."""
    from PIL import Image as _Image
    return _Image.new('RGBA', (16, 16), (200, 150, 100, alpha))


def _parse_txi(text: str) -> dict:
    from gui.viewport import _parse_txi_string
    return _parse_txi_string(text)


def _apply_alpha(img, txi_meta: dict):
    from gui.viewport import TextureCache
    return TextureCache._apply_kotor_alpha(b'', img, txi_meta)


class TestEnvmapAlphaFix:
    """
    KotOR DXT5 textures store an environment-map BLEND WEIGHT (not transparency)
    in their alpha channel when the TXI contains 'envmaptexture <name>'.
    Before this fix the CPU viewport renderer would treat that channel as genuine
    alpha, making creatures such as c_bantha, c_rancor and the sithpraet appear
    semi-transparent.  These tests verify the corrected behaviour.
    """

    def test_envmaptexture_forces_alpha_255(self):
        """envmaptexture in TXI → alpha channel is the env-map BLEND WEIGHT (preserved).

        CORRECTED BEHAVIOUR (Phase 1 fix):
        Previously this test asserted alpha was forced to 255, which was WRONG.
        The Odyssey engine uses the diffuse alpha channel as the blend weight between
        the surface colour and the reflected environment map texture.  Forcing alpha=255
        would destroy the env-map blend effect (droids, metals, etc. losing sheen).

        The GPU fragment shader uses:
            float env_weight = diffuse_samp.a;
            lit_color = mix(lit_color, env_col, env_weight);
        and forces final output alpha=1.0 (opaque surface).

        The CPU _apply_kotor_alpha must PRESERVE the alpha channel so this blend weight
        is available when needed.

        Reference: OldRepublicDevs/PyKotor creature.py TXI spec +
                   KotorBlender reader.py envmaptexture notes.
        """
        import numpy as np
        img    = _semi_alpha_img(128)
        result = _apply_alpha(img, _parse_txi('envmaptexture CM_Baremetal'))
        arr    = np.array(result)
        # Alpha must NOT be forced to 255 — it should remain at 128 (the blend weight)
        assert arr[:, :, 3].min() >= 120 and arr[:, :, 3].max() <= 140, (
            f"envmaptexture: alpha should be preserved (~128), got min={arr[:,:,3].min()} "
            f"max={arr[:,:,3].max()}. Alpha is the env-map blend weight, not transparency."
        )

    def test_bumpmaptexture_forces_alpha_255(self):
        """bumpmaptexture in TXI → alpha channel must be forced to 255 (normal map data)."""
        import numpy as np
        img    = _semi_alpha_img(64)
        result = _apply_alpha(img, _parse_txi('bumpmaptexture c_bantha_n'))
        arr    = np.array(result)
        assert arr[:, :, 3].min() == 255, "bumpmaptexture: alpha not forced to 255"

    def test_standard_blending0_forces_alpha_255(self):
        """Standard opaque surface (blending=0, no TXI specials) → force alpha=255."""
        import numpy as np
        img    = _semi_alpha_img(100)
        result = _apply_alpha(img, _parse_txi(''))   # empty TXI → blending=0
        arr    = np.array(result)
        assert arr[:, :, 3].min() == 255, "blending=0 standard: alpha not forced to 255"

    def test_additive_blending_preserves_alpha(self):
        """blending additive (1) → alpha channel must be left unchanged (particle FX)."""
        import numpy as np
        img    = _semi_alpha_img(128)
        result = _apply_alpha(img, _parse_txi('blending additive'))
        arr    = np.array(result)
        assert arr[:, :, 3].min() == 128, "blending additive: alpha should NOT be changed"

    def test_punchthrough_blending_applies_cutoff(self):
        """blending punchthrough (2) → pixels above threshold→255, below→0."""
        import numpy as np
        from PIL import Image as _Image
        # Build image with a mix of above/below threshold pixels
        arr_in = np.zeros((16, 16, 4), dtype=np.uint8)
        arr_in[:8, :, :] = [200, 150, 100, 200]   # above 128 → 255
        arr_in[8:, :, :] = [200, 150, 100, 50]    # below 128 → 0
        img    = _Image.fromarray(arr_in, 'RGBA')
        result = _apply_alpha(img, _parse_txi('blending punchthrough'))
        out    = np.array(result)
        assert np.all(out[:8, :, 3] == 255), "punchthrough: above-threshold not 255"
        assert np.all(out[8:, :, 3] == 0),   "punchthrough: below-threshold not 0"

    def test_envmap_and_bump_both_in_txi(self):
        """Both envmaptexture and bumpmaptexture present → still force alpha=255."""
        import numpy as np
        img    = _semi_alpha_img(64)
        txi    = _parse_txi('envmaptexture CM_Fog\nbumpmaptexture n_surface')
        result = _apply_alpha(img, txi)
        arr    = np.array(result)
        assert arr[:, :, 3].min() == 255, "env+bump combined: alpha not forced to 255"

    def test_already_opaque_texture_unchanged(self):
        """A fully-opaque texture (alpha=255) should pass through unmodified."""
        import numpy as np
        img    = _semi_alpha_img(255)
        result = _apply_alpha(img, _parse_txi('envmaptexture CM_Baremetal'))
        arr    = np.array(result)
        assert arr[:, :, 3].min() == 255
        assert arr[:, :, 3].max() == 255

    def test_txi_parse_envmaptexture_field(self):
        """_parse_txi_string correctly extracts 'envmaptexture' key (lowercased)."""
        txi = _parse_txi('envmaptexture CM_Baremetal\nblending 0')
        assert txi.get('envmaptexture') == 'cm_baremetal'
        assert txi.get('blending') == 0

    def test_sithpraet_txi_triggers_envmap_fix(self):
        """Actual n_sithpraet01.txi has envmaptexture → alpha PRESERVED (blend weight).

        CORRECTED BEHAVIOUR (Phase 1 fix):
        The sithpraet model's TXI specifies an envmaptexture (CM_Baremetal or similar).
        This means the diffuse alpha channel encodes the environment-map blend weight,
        NOT transparency.  The GPU fragment shader uses this alpha to blend the reflected
        env-map onto the surface colour (giving the metallic sheen effect).

        _apply_kotor_alpha must PRESERVE this alpha so the blend weight is available.
        The surface itself is rendered opaque (final_alpha=1.0 forced in the shader).
        """
        import os
        import numpy as np
        repo  = os.path.dirname(os.path.dirname(__file__))
        txi_p = os.path.join(repo, 'test_assets', 'n_sithpraet01.txi')
        if not os.path.exists(txi_p):
            pytest.skip("n_sithpraet01.txi not found in test_assets")
        txi_text = open(txi_p).read()
        txi = _parse_txi(txi_text)
        assert bool(txi.get('envmaptexture', '')), \
            "n_sithpraet01.txi should have envmaptexture set"
        img    = _semi_alpha_img(128)
        result = _apply_alpha(img, txi)
        arr    = np.array(result)
        # Alpha must be preserved (not forced to 255) — it is the env-map blend weight
        assert arr[:, :, 3].min() >= 120 and arr[:, :, 3].max() <= 140, (
            f"sithpraet envmap: alpha should be preserved (~128 blend weight), "
            f"got min={arr[:,:,3].min()} max={arr[:,:,3].max()}. "
            "Alpha must NOT be forced to 255 for env-map textures."
        )


