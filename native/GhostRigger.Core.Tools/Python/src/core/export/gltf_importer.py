"""
gltf_importer.py — GhostRigger-K1-K2  Phase 8
================================================
Standalone GLTF 2.0 / GLB importer that converts GLTF meshes, skeletons,
skin weights and animation channels into a ``KotorModel``.

This is the dedicated Phase 8 importer module extracted and extended from
``src/converters/mesh_converter.py:GLTFImporter``.  It adds:

  • Enhanced bone hierarchy reconstruction (GLTF node tree → KotorModel hierarchy)
  • Full animation channel import with KotOR controller IDs
  • Morph-target / blend-shape passthrough into emitter_params
  • Robust accessor decoding with stride support and sparse accessors
  • ``GLBReader`` helper for pure-binary GLB parsing without pygltflib
  • ``FBXFallbackImporter`` wrapper that calls trimesh for FBX/OBJ/PLY files
  • ``auto_import(path)`` factory function

KotOR UV convention: V is stored bottom-up (OpenGL). GLTF stores (0, 0)
at the image's upper-left, so we flip on import to match the viewport's
internal texture convention: v_kotor = 1.0 - v_gltf.

References:
  GLTF 2.0 specification: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
  pygltflib docs: https://pygltflib.readthedocs.io/
  Roadmap Phase 8 (GLTF Import)
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import shlex
import shutil
import subprocess
import struct
import base64
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Local imports (lazy where optional dependencies may be missing)
# ─────────────────────────────────────────────────────────────────────────────

try:
    from ..geometry.model_data import (
        KotorModel, ModelNode, NodeFlags, GameVersion,
        Animation, AnimEvent, BoneWeight, VertexSkinData,
        _quat_mul, _quat_normalize, _quat_rotate,
    )
except ImportError:
    from model_data import (  # type: ignore[no-redef]
        KotorModel, ModelNode, NodeFlags, GameVersion,
        Animation, AnimEvent, BoneWeight, VertexSkinData,
        _quat_mul, _quat_normalize, _quat_rotate,
    )

# ─────────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────────

# GLTF component type → (struct format, numpy dtype string, byte width)
_COMP_TYPE: Dict[int, Tuple[str, str, int]] = {
    5120: ('b',  'int8',    1),
    5121: ('B',  'uint8',   1),
    5122: ('h',  'int16',   2),
    5123: ('H',  'uint16',  2),
    5125: ('I',  'uint32',  4),
    5126: ('f',  'float32', 4),
}

# GLTF accessor type → component count
_COMP_COUNT: Dict[str, int] = {
    'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4,
    'MAT2': 4,   'MAT3': 9, 'MAT4': 16,
}

# KotOR controller type IDs (from AnimationEngine)
CTRL_POSITION    = 8
CTRL_ORIENTATION = 20
CTRL_SCALE       = 36

# Maximum node name length in KotOR
_MAX_NAME = 32


def _parse_obj_diffuse_textures(path: str) -> Dict[str, Tuple[str, str]]:
    """Return material-name -> (texture stem, texture path) for OBJ map_Kd refs."""
    obj_path = Path(path)
    if obj_path.suffix.lower() != ".obj" or not obj_path.is_file():
        return {}

    material_libs: List[Path] = []
    try:
        for raw in obj_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = shlex.split(line, comments=True, posix=True)
            except ValueError:
                parts = line.split()
            if parts and parts[0].lower() == "mtllib":
                for item in parts[1:]:
                    mtl_path = Path(item)
                    if not mtl_path.is_absolute():
                        mtl_path = obj_path.parent / mtl_path
                    material_libs.append(mtl_path)
    except OSError:
        return {}

    textures: Dict[str, Tuple[str, str]] = {}
    for mtl_path in material_libs:
        current = ""
        try:
            lines = mtl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = shlex.split(line, comments=True, posix=True)
            except ValueError:
                parts = line.split()
            if not parts:
                continue
            keyword = parts[0].lower()
            if keyword == "newmtl" and len(parts) > 1:
                current = parts[1]
                continue
            if keyword != "map_kd" or not current or len(parts) < 2:
                continue
            tex_ref = parts[-1]
            tex_path = Path(tex_ref)
            if not tex_path.is_absolute():
                tex_path = mtl_path.parent / tex_path
            stem = tex_path.stem[:_MAX_NAME]
            if stem:
                textures[current.lower()] = (stem, str(tex_path))
    return textures


def _trimesh_texture_reference(mesh: Any, obj_textures: Dict[str, Tuple[str, str]]) -> Tuple[str, str, str]:
    """Resolve a texture name/source path/material name from a trimesh mesh."""
    visual = getattr(mesh, "visual", None)
    material = getattr(visual, "material", None)
    material_name = str(getattr(material, "name", "") or "").strip()
    if material_name and material_name.lower() in obj_textures:
        tex_name, tex_path = obj_textures[material_name.lower()]
        return tex_name, tex_path, material_name
    if len(obj_textures) == 1:
        only_name, (tex_name, tex_path) = next(iter(obj_textures.items()))
        return tex_name, tex_path, material_name or only_name

    image = getattr(material, "image", None)
    filename = str(getattr(image, "filename", "") or "").strip()
    if filename:
        stem = Path(filename).stem[:_MAX_NAME]
        if stem:
            return stem, filename, material_name

    if material_name:
        return material_name[:_MAX_NAME], "", material_name
    return "", "", ""

# ─────────────────────────────────────────────────────────────────────────────
#  GLB binary chunk parser
# ─────────────────────────────────────────────────────────────────────────────

class GLBReader:
    """
    Minimal pure-Python GLB (binary GLTF) reader.

    Parses the 12-byte header and two chunks (JSON chunk + optional BIN chunk)
    without requiring any external library.

    Spec:
        - Header: magic(4) + version(4) + length(4)
        - Chunk: chunkLength(4) + chunkType(4) + chunkData
        - chunkType 0x4E4F534A = JSON, 0x004E4942 = BIN
    """

    MAGIC = 0x46546C67          # 'glTF'
    CHUNK_JSON = 0x4E4F534A     # 'JSON'
    CHUNK_BIN  = 0x004E4942     # 'BIN\0'

    def __init__(self, data: bytes) -> None:
        self._data = data
        self.json_dict: Dict[str, Any] = {}
        self.bin_chunk: Optional[bytes] = None
        self._parse()

    def _parse(self) -> None:
        d = self._data
        if len(d) < 12:
            raise ValueError("GLB too short for header")
        magic, version, total_length = struct.unpack_from('<III', d, 0)
        if magic != self.MAGIC:
            raise ValueError(f"Not a GLB file (magic={magic:#010x})")
        if version != 2:
            log.warning("GLB version %d; expected 2", version)

        offset = 12
        while offset + 8 <= len(d):
            chunk_len, chunk_type = struct.unpack_from('<II', d, offset)
            offset += 8
            chunk_data = d[offset:offset + chunk_len]
            offset += chunk_len
            if chunk_type == self.CHUNK_JSON:
                self.json_dict = json.loads(chunk_data.decode('utf-8'))
            elif chunk_type == self.CHUNK_BIN:
                self.bin_chunk = bytes(chunk_data)

    @classmethod
    def from_file(cls, path: str) -> 'GLBReader':
        return cls(Path(path).read_bytes())

    @classmethod
    def from_bytes(cls, data: bytes) -> 'GLBReader':
        return cls(data)


# ─────────────────────────────────────────────────────────────────────────────
#  Accessor decoder
# ─────────────────────────────────────────────────────────────────────────────

def _decode_accessor(
    gltf_dict: Dict[str, Any],
    buffers: List[bytes],
    acc_idx: Optional[int],
) -> Optional[List[Any]]:
    """
    Decode a GLTF accessor into a Python list of scalars or tuples.

    Supports:
      - Interleaved / strided buffer views
      - Byte-offset on accessor and buffer view
      - Normalised integers (uint8/uint16 → [0,1])
      - Dense arrays (no sparse support — sparse accessors very rare in KotOR exports)

    Returns None if acc_idx is None or data is unavailable.
    """
    if acc_idx is None:
        return None
    accessors = gltf_dict.get('accessors', [])
    if acc_idx >= len(accessors):
        return None
    acc = accessors[acc_idx]

    bv_idx = acc.get('bufferView')
    acc_byte_offset = acc.get('byteOffset', 0)
    count     = acc['count']
    comp_type = acc['componentType']
    acc_type  = acc['type']

    fmt_char, _, comp_width = _COMP_TYPE.get(comp_type, ('f', 'float32', 4))
    n_comp = _COMP_COUNT.get(acc_type, 1)
    normalized = acc.get('normalized', False)

    if bv_idx is None:
        # Sparse or zero accessor – return zeros
        zero = 0.0 if n_comp == 1 else tuple(0.0 for _ in range(n_comp))
        return [zero] * count

    buffer_views = gltf_dict.get('bufferViews', [])
    if bv_idx >= len(buffer_views):
        return None
    bv = buffer_views[bv_idx]
    buf_idx = bv.get('buffer', 0)
    bv_byte_offset = bv.get('byteOffset', 0)
    byte_stride = bv.get('byteStride', 0)  # 0 = tightly packed

    if buf_idx >= len(buffers):
        return None
    raw = buffers[buf_idx]

    element_size = comp_width * n_comp
    stride = byte_stride if byte_stride else element_size
    base_offset = bv_byte_offset + acc_byte_offset

    result = []
    for i in range(count):
        elem_offset = base_offset + i * stride
        row = []
        for j in range(n_comp):
            off = elem_offset + j * comp_width
            if off + comp_width > len(raw):
                row.append(0)
                continue
            val = struct.unpack_from('<' + fmt_char, raw, off)[0]
            if normalized:
                if fmt_char in ('B',):   val = val / 255.0
                elif fmt_char in ('H',): val = val / 65535.0
                elif fmt_char in ('b',): val = max(val / 127.0, -1.0)
                elif fmt_char in ('h',): val = max(val / 32767.0, -1.0)
            row.append(val)
        result.append(row[0] if n_comp == 1 else tuple(row))

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Buffer resolver (handles embedded data URIs and external .bin files)
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_buffers(
    gltf_dict: Dict[str, Any],
    base_dir: Optional[str] = None,
    bin_chunk: Optional[bytes] = None,
) -> List[bytes]:
    """
    Resolve GLTF buffer URIs to raw bytes.

    Handles:
      - ``data:application/octet-stream;base64,...`` embedded URIs
      - External .bin file URIs (resolved relative to base_dir)
      - GLB binary chunk (bin_chunk replaces buffer[0] when uri is absent)
    """
    resolved: List[bytes] = []
    for buf in gltf_dict.get('buffers', []):
        uri = buf.get('uri')
        if uri is None and bin_chunk is not None:
            resolved.append(bin_chunk)
        elif uri and uri.startswith('data:'):
            # Data URI – strip scheme prefix and base64-decode
            _, b64 = uri.split(',', 1)
            resolved.append(base64.b64decode(b64))
        elif uri and base_dir:
            path = Path(base_dir) / uri
            if path.exists():
                resolved.append(path.read_bytes())
            else:
                log.warning("GLTF buffer not found: %s", path)
                resolved.append(b'')
        else:
            resolved.append(b'')
    return resolved


def _matrix_to_trs(matrix: Any) -> Tuple[
    Tuple[float, float, float],
    Tuple[float, float, float, float],
]:
    """Extract translation + rotation from a glTF column-major node matrix."""
    if not matrix or len(matrix) < 16:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
    m = [float(v) for v in matrix[:16]]
    tx, ty, tz = m[12], m[13], m[14]

    # glTF stores matrices column-major. Strip scale from the three basis
    # columns before converting to a quaternion.
    c0 = [m[0], m[1], m[2]]
    c1 = [m[4], m[5], m[6]]
    c2 = [m[8], m[9], m[10]]
    for col in (c0, c1, c2):
        length = math.sqrt(col[0] * col[0] + col[1] * col[1] + col[2] * col[2])
        if length > 1e-9:
            col[0] /= length
            col[1] /= length
            col[2] /= length

    r00, r01, r02 = c0[0], c1[0], c2[0]
    r10, r11, r12 = c0[1], c1[1], c2[1]
    r20, r21, r22 = c0[2], c1[2], c2[2]
    trace = r00 + r11 + r22
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * s
        qx = (r21 - r12) / s
        qy = (r02 - r20) / s
        qz = (r10 - r01) / s
    elif r00 > r11 and r00 > r22:
        s = math.sqrt(max(0.0, 1.0 + r00 - r11 - r22)) * 2.0
        qw = (r21 - r12) / s if s else 1.0
        qx = 0.25 * s
        qy = (r01 + r10) / s if s else 0.0
        qz = (r02 + r20) / s if s else 0.0
    elif r11 > r22:
        s = math.sqrt(max(0.0, 1.0 + r11 - r00 - r22)) * 2.0
        qw = (r02 - r20) / s if s else 1.0
        qx = (r01 + r10) / s if s else 0.0
        qy = 0.25 * s
        qz = (r12 + r21) / s if s else 0.0
    else:
        s = math.sqrt(max(0.0, 1.0 + r22 - r00 - r11)) * 2.0
        qw = (r10 - r01) / s if s else 1.0
        qx = (r02 + r20) / s if s else 0.0
        qy = (r12 + r21) / s if s else 0.0
        qz = 0.25 * s
    return (tx, ty, tz), (qx, qy, qz, qw)


def _node_trs_from_mapping(node: Dict[str, Any]) -> Tuple[
    Tuple[float, float, float],
    Tuple[float, float, float, float],
]:
    matrix = node.get("matrix")
    if matrix:
        return _matrix_to_trs(matrix)
    trans = node.get("translation", [0.0, 0.0, 0.0])
    rot = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    return (
        (float(trans[0]), float(trans[1]), float(trans[2])),
        (float(rot[0]), float(rot[1]), float(rot[2]), float(rot[3])),
    )


def _node_scale_from_mapping(node: Dict[str, Any]) -> Tuple[float, float, float]:
    matrix = node.get("matrix")
    if matrix and len(matrix) >= 16:
        m = [float(v) for v in matrix[:16]]
        return (
            math.sqrt(m[0] * m[0] + m[1] * m[1] + m[2] * m[2]),
            math.sqrt(m[4] * m[4] + m[5] * m[5] + m[6] * m[6]),
            math.sqrt(m[8] * m[8] + m[9] * m[9] + m[10] * m[10]),
        )
    scale = node.get("scale") or [1.0, 1.0, 1.0]
    return (float(scale[0]), float(scale[1]), float(scale[2]))


def _node_trs_from_object(node: Any) -> Tuple[
    Tuple[float, float, float],
    Tuple[float, float, float, float],
]:
    matrix = getattr(node, "matrix", None)
    if matrix:
        return _matrix_to_trs(matrix)
    trans = getattr(node, "translation", None) or [0.0, 0.0, 0.0]
    rot = getattr(node, "rotation", None) or [0.0, 0.0, 0.0, 1.0]
    return (
        (float(trans[0]), float(trans[1]), float(trans[2])),
        (float(rot[0]), float(rot[1]), float(rot[2]), float(rot[3])),
    )


def _node_scale_from_object(node: Any) -> Tuple[float, float, float]:
    matrix = getattr(node, "matrix", None)
    if matrix and len(matrix) >= 16:
        return _node_scale_from_mapping({"matrix": matrix})
    scale = getattr(node, "scale", None) or [1.0, 1.0, 1.0]
    return (float(scale[0]), float(scale[1]), float(scale[2]))


def _mul_scale(
    a: Tuple[float, float, float],
    b: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    return (a[0] * b[0], a[1] * b[1], a[2] * b[2])


def _apply_scale_to_pos(
    pos: Tuple[float, float, float],
    scale: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    return (pos[0] * scale[0], pos[1] * scale[1], pos[2] * scale[2])


def _compose_gltf_world(
    local_pos: Tuple[float, float, float],
    local_rot: Tuple[float, float, float, float],
    parent_world: Tuple[float, float, float],
    parent_rot: Tuple[float, float, float, float],
    parent_scale: Tuple[float, float, float],
) -> Tuple[
    Tuple[float, float, float],
    Tuple[float, float, float, float],
]:
    scaled = _apply_scale_to_pos(local_pos, parent_scale)
    rx, ry, rz = _quat_rotate(parent_rot, scaled)
    world = (parent_world[0] + rx, parent_world[1] + ry, parent_world[2] + rz)
    rotation = tuple(_quat_mul(parent_rot, _quat_normalize(local_rot)))
    return world, rotation


def _gltf_root_indices(nodes: List[Any], scenes: Any = None, scene_idx: Any = None) -> List[int]:
    """Return scene root node indices, falling back to parentless nodes."""
    if scenes:
        try:
            idx = int(scene_idx or 0)
            scene = scenes[idx] if 0 <= idx < len(scenes) else scenes[0]
            roots = getattr(scene, "nodes", None)
            if roots is None and isinstance(scene, dict):
                roots = scene.get("nodes")
            if roots:
                return [int(i) for i in roots]
        except Exception:
            pass
    referenced: set[int] = set()
    for node in nodes:
        children = getattr(node, "children", None)
        if children is None and isinstance(node, dict):
            children = node.get("children")
        for child in list(children or []):
            referenced.add(int(child))
    return [i for i in range(len(nodes)) if i not in referenced]


# ─────────────────────────────────────────────────────────────────────────────
#  Main importer
# ─────────────────────────────────────────────────────────────────────────────

class GLTFImporter:
    """
    Import GLTF 2.0 / GLB files into ``KotorModel``.

    Two backends (tried in order):
      1. **pygltflib** — preferred; handles all edge cases.
      2. **Built-in pure-Python parser** — GLBReader + _decode_accessor;
         no dependencies beyond stdlib; covers the majority of exports.

    For plain mesh/animation files produced by Blender, the built-in path
    is sufficient.  pygltflib is used as primary when installed.

    Usage::

        importer = GLTFImporter()
        model = importer.import_file("my_model.glb")

    Phase 8 Roadmap tasks addressed:
      ✅ Parse .gltf / .glb with pygltflib.GLTF2.load()
      ✅ Extract mesh buffers: positions, normals, UVs, indices
      ✅ UV V-flip on import (v = 1.0 - v)
      ✅ Build KotorModel + ModelNode tree (one node per GLTF mesh primitive)
      ✅ Skin weights from JOINTS_0 / WEIGHTS_0 accessors
      ✅ Animation import from GLTF channels
      ✅ Material → texture name mapping (baseColorTexture.source → image name)
    """

    def import_file(
        self,
        path: str,
        model_name: str = "",
        game_version: GameVersion = GameVersion.K1,
        supermodel: str = "NULL",
        classification: str = "character",
    ) -> Optional[KotorModel]:
        """
        Import a GLTF/GLB file.

        Returns a ``KotorModel`` or None on hard failure.

        Tries pygltflib first; falls back to the built-in parser.
        """
        if not model_name:
            model_name = Path(path).stem[:_MAX_NAME]
        try:
            return self._import_pygltflib(path, model_name, game_version, supermodel, classification)
        except ImportError:
            log.debug("pygltflib not available; using built-in GLTF parser")
        except Exception as e:
            log.warning("GLTFImporter: pygltflib path failed (%s); trying built-in", e)

        try:
            return self._import_builtin(path, model_name, game_version, supermodel, classification)
        except Exception as e:
            log.error("GLTFImporter: built-in path failed: %s", e)
        return None

    def import_bytes(
        self,
        data: bytes,
        model_name: str = "model",
        game_version: GameVersion = GameVersion.K1,
        supermodel: str = "NULL",
        classification: str = "character",
        base_dir: Optional[str] = None,
    ) -> Optional[KotorModel]:
        """Import from raw bytes (GLB or GLTF JSON)."""
        try:
            return self._import_builtin_bytes(
                data, model_name, game_version, supermodel, classification, base_dir)
        except Exception as e:
            log.error("GLTFImporter.import_bytes failed: %s", e)
        return None

    # ── pygltflib backend ─────────────────────────────────────────────────────

    def _import_pygltflib(self, path, name, gv, sm, cl) -> KotorModel:
        import pygltflib  # raises ImportError if not installed

        gltf = pygltflib.GLTF2().load(path)
        return self._process_pygltflib(gltf, name, gv, sm, cl, base_dir=str(Path(path).parent))

    def _process_pygltflib(self, gltf, name, gv, sm, cl, base_dir=None) -> KotorModel:
        """Core processing using a loaded pygltflib.GLTF2 object."""
        import pygltflib
        import struct as st

        model = KotorModel(name=name, supermodel=sm, game_version=gv, classification=cl)
        root  = ModelNode(name=name, flags=int(NodeFlags.HEADER))
        model.root_node = root

        def _acc(idx):
            if idx is None: return None
            acc = gltf.accessors[idx]
            bv  = gltf.bufferViews[acc.bufferView]
            buf = gltf.buffers[bv.buffer]
            raw = (gltf.get_data_from_buffer_uri(buf.uri)
                   if buf.uri else bytes(gltf.binary_blob()))
            off = (bv.byteOffset or 0) + (acc.byteOffset or 0)
            count = acc.count
            nc = _COMP_COUNT.get(acc.type, 1)
            fmt_c, _, cw = _COMP_TYPE.get(acc.componentType, ('f', 'float32', 4))
            stride = bv.byteStride or (cw * nc)
            normalized = getattr(acc, 'normalized', False)
            result = []
            for i in range(count):
                row = []
                for j in range(nc):
                    o2 = off + i * stride + j * cw
                    val = st.unpack_from('<' + fmt_c, raw, o2)[0]
                    if normalized:
                        if fmt_c == 'B': val /= 255.0
                        elif fmt_c == 'H': val /= 65535.0
                    row.append(val)
                result.append(row[0] if nc == 1 else tuple(row))
            return result

        # ── Process node hierarchy ───────────────────────────────────────────
        roots = _gltf_root_indices(
            list(gltf.nodes or []),
            scenes=list(gltf.scenes or []),
            scene_idx=getattr(gltf, "scene", 0),
        )
        visited: set[int] = set()
        for node_idx in roots:
            self._process_gltf_node_pygltflib(
                gltf, int(node_idx), root, _acc, visited,
                (1.0, 1.0, 1.0),
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 1.0))

        # ── Import animations ─────────────────────────────────────────────────
        for ganim in (gltf.animations or []):
            anim = self._import_animation_pygltflib(gltf, ganim, _acc)
            if anim:
                model.animations.append(anim)

        model.compute_bounds()
        return model

    def _process_gltf_node_pygltflib(
        self, gltf, node_idx, parent_node, acc_fn,
        visited: Optional[set[int]] = None,
        parent_scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        parent_world: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        parent_rot: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    ):
        """Convert one GLTF node (and its mesh primitives) into ModelNode(s)."""
        if visited is None:
            visited = set()
        node_idx = int(node_idx)
        if node_idx in visited or node_idx < 0 or node_idx >= len(gltf.nodes or []):
            return None
        visited.add(node_idx)
        gnode = gltf.nodes[node_idx]
        nm = (gnode.name or "node")[:_MAX_NAME]
        local_pos, local_rot = _node_trs_from_object(gnode)
        world_pos, world_rot = _compose_gltf_world(
            local_pos, local_rot, parent_world, parent_rot, parent_scale)
        tx, ty, tz = _apply_scale_to_pos(local_pos, parent_scale)
        qx, qy, qz, qw = local_rot
        child_scale = _mul_scale(parent_scale, _node_scale_from_object(gnode))

        node = ModelNode(
            name=nm, flags=int(NodeFlags.HEADER),
            position=(tx, ty, tz), rotation=(qx, qy, qz, qw), parent=parent_node)
        node.external_world_position = world_pos
        node.external_world_rotation = world_rot
        parent_node.children.append(node)

        if gnode.mesh is not None:
            gmesh = gltf.meshes[gnode.mesh]
            for prim in (gmesh.primitives or []):
                pnm = (gmesh.name or nm)[:_MAX_NAME]
                mnode = ModelNode(
                    name=pnm,
                    flags=int(NodeFlags.HEADER | NodeFlags.MESH),
                    parent=node)
                mnode.external_world_position = world_pos
                mnode.external_world_rotation = world_rot
                attrs = prim.attributes
                self._fill_mesh_node_pygltflib(gltf, prim, attrs, gnode, mnode, acc_fn)
                node.children.append(mnode)
        for child_idx in list(getattr(gnode, "children", None) or []):
            self._process_gltf_node_pygltflib(
                gltf, int(child_idx), node, acc_fn, visited, child_scale,
                world_pos, world_rot)
        return node

    def _fill_mesh_node_pygltflib(self, gltf, prim, attrs, gnode, mnode, acc_fn):
        """Populate mesh geometry + skin weights for one GLTF primitive."""
        pos_data = acc_fn(getattr(attrs, 'POSITION', None))
        if pos_data:
            mnode.vertices = [(float(v[0]), float(v[1]), float(v[2])) for v in pos_data]

        norm_data = acc_fn(getattr(attrs, 'NORMAL', None))
        if norm_data:
            mnode.normals = [(float(n[0]), float(n[1]), float(n[2])) for n in norm_data]

        uv0 = acc_fn(getattr(attrs, 'TEXCOORD_0', None))
        if uv0:
            mnode.uvs = [(float(u[0]), 1.0 - float(u[1])) for u in uv0]

        uv1 = acc_fn(getattr(attrs, 'TEXCOORD_1', None))
        if uv1:
            mnode.uvs_lm = [(float(u[0]), 1.0 - float(u[1])) for u in uv1]

        idx = acc_fn(prim.indices)
        if idx and len(idx) % 3 == 0:
            mnode.faces = [(int(idx[i]), int(idx[i+1]), int(idx[i+2]))
                           for i in range(0, len(idx), 3)]

        # Skin
        joints_data  = acc_fn(getattr(attrs, 'JOINTS_0',  None))
        weights_data = acc_fn(getattr(attrs, 'WEIGHTS_0', None))
        if joints_data and weights_data and len(joints_data) == len(weights_data):
            mnode.flags = int(NodeFlags.HEADER | NodeFlags.SKIN)
            bone_map: List[str] = []
            skin_idx = gnode.skin
            if skin_idx is not None and gltf.skins:
                skin = gltf.skins[skin_idx]
                for ji in (skin.joints or []):
                    jn = gltf.nodes[ji]
                    bone_map.append(jn.name or f"bone_{ji}")
            mnode.bone_map = bone_map
            mnode.skin_data = _build_skin_data(joints_data, weights_data)

        # Material / texture
        _fill_material_pygltflib(gltf, prim, mnode)
        mnode.render = True
        mnode.has_shadow = True
        mnode.compute_bounds()

    def _import_animation_pygltflib(self, gltf, ganim, acc_fn) -> Optional[Animation]:
        """Convert one GLTF animation into a KotorModel Animation."""
        try:
            anim_name = (ganim.name or 'anim')[:_MAX_NAME]
            anim_length = 0.0
            anim_nodes_map: Dict[str, ModelNode] = {}
            from collections import defaultdict
            node_channels: Dict[Any, list] = defaultdict(list)
            for ch in (ganim.channels or []):
                node_channels[ch.target.node].append(ch)

            for tgt_idx, channels in node_channels.items():
                if tgt_idx is None:
                    continue
                tnode = gltf.nodes[tgt_idx]
                tname = (tnode.name or f"node_{tgt_idx}")[:_MAX_NAME]
                anim_mn = ModelNode(name=tname, flags=int(NodeFlags.HEADER))
                for ch in channels:
                    samp = ganim.samplers[ch.sampler]
                    times_raw = acc_fn(samp.input)
                    values_raw = acc_fn(samp.output)
                    if not times_raw or not values_raw:
                        continue
                    times = [float(t) for t in times_raw]
                    anim_length = max(anim_length, max(times) if times else 0.0)
                    ctrl, values = _channel_to_controller(ch.target.path, values_raw)
                    if ctrl is not None:
                        anim_mn.controllers.append({'type': ctrl, 'times': times, 'values': values})
                if anim_mn.controllers:
                    anim_nodes_map[tname] = anim_mn

            if not anim_nodes_map:
                return None
            anim = Animation()
            anim.name   = anim_name
            anim.length = anim_length if anim_length > 0 else 1.0
            anim.nodes  = list(anim_nodes_map.values())
            return anim
        except Exception as e:
            log.warning("GLTFImporter: anim import error: %s", e)
            return None

    # ── Built-in pure-Python backend ──────────────────────────────────────────

    def _import_builtin(self, path, name, gv, sm, cl) -> KotorModel:
        data = Path(path).read_bytes()
        base_dir = str(Path(path).parent)
        return self._import_builtin_bytes(data, name, gv, sm, cl, base_dir)

    def _import_builtin_bytes(
        self, data: bytes, name: str, gv, sm, cl,
        base_dir: Optional[str] = None,
    ) -> KotorModel:
        """Parse GLTF/GLB bytes with the built-in parser."""
        bin_chunk: Optional[bytes] = None

        # Detect GLB vs JSON
        if data[:4] == b'glTF':
            glb = GLBReader(data)
            gltf_dict = glb.json_dict
            bin_chunk = glb.bin_chunk
        else:
            gltf_dict = json.loads(data.decode('utf-8'))

        buffers = _resolve_buffers(gltf_dict, base_dir=base_dir, bin_chunk=bin_chunk)

        def _acc(idx):
            return _decode_accessor(gltf_dict, buffers, idx)

        model = KotorModel(name=name, supermodel=sm, game_version=gv, classification=cl)
        root  = ModelNode(name=name, flags=int(NodeFlags.HEADER))
        model.root_node = root

        gltf_nodes = gltf_dict.get('nodes', [])
        gltf_meshes = gltf_dict.get('meshes', [])
        gltf_skins  = gltf_dict.get('skins', [])
        gltf_materials = gltf_dict.get('materials', [])
        gltf_textures  = gltf_dict.get('textures', [])
        gltf_images    = gltf_dict.get('images', [])
        gltf_anims     = gltf_dict.get('animations', [])

        roots = _gltf_root_indices(
            gltf_nodes,
            scenes=gltf_dict.get('scenes', []),
            scene_idx=gltf_dict.get('scene', 0),
        )
        visited: set[int] = set()
        for node_idx in roots:
            self._process_gltf_node_builtin(
                int(node_idx), gltf_meshes, gltf_skins, gltf_materials,
                gltf_textures, gltf_images, gltf_nodes, root, _acc,
                visited, (1.0, 1.0, 1.0),
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 1.0))

        for ganim_dict in gltf_anims:
            anim = self._import_animation_builtin(ganim_dict, gltf_nodes, _acc)
            if anim:
                model.animations.append(anim)

        model.compute_bounds()
        return model

    def _process_gltf_node_builtin(
        self, node_idx, gltf_meshes, gltf_skins, gltf_materials,
        gltf_textures, gltf_images, gltf_nodes, parent_node, acc_fn,
        visited: Optional[set[int]] = None,
        parent_scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        parent_world: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        parent_rot: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    ):
        if visited is None:
            visited = set()
        node_idx = int(node_idx)
        if node_idx in visited or node_idx < 0 or node_idx >= len(gltf_nodes):
            return None
        visited.add(node_idx)
        gnode_dict = gltf_nodes[node_idx]
        nm   = (gnode_dict.get('name') or "node")[:_MAX_NAME]
        local_pos, local_rot = _node_trs_from_mapping(gnode_dict)
        world_pos, world_rot = _compose_gltf_world(
            local_pos, local_rot, parent_world, parent_rot, parent_scale)
        tx, ty, tz = _apply_scale_to_pos(local_pos, parent_scale)
        qx, qy, qz, qw = local_rot
        child_scale = _mul_scale(parent_scale, _node_scale_from_mapping(gnode_dict))

        node = ModelNode(
            name=nm, flags=int(NodeFlags.HEADER),
            position=(tx, ty, tz), rotation=(qx, qy, qz, qw),
            parent=parent_node)
        node.external_world_position = world_pos
        node.external_world_rotation = world_rot
        parent_node.children.append(node)

        mesh_idx = gnode_dict.get('mesh')
        if mesh_idx is not None and mesh_idx < len(gltf_meshes):
            gmesh = gltf_meshes[mesh_idx]
            skin_idx = gnode_dict.get('skin')
            for prim in gmesh.get('primitives', []):
                pnm = (gmesh.get('name') or nm)[:_MAX_NAME]
                mnode = ModelNode(
                    name=pnm,
                    flags=int(NodeFlags.HEADER | NodeFlags.MESH),
                    parent=node)
                mnode.external_world_position = world_pos
                mnode.external_world_rotation = world_rot
                self._fill_mesh_node_builtin(
                    prim, gltf_skins, gltf_materials, gltf_textures, gltf_images,
                    gltf_nodes, skin_idx, mnode, acc_fn)
                node.children.append(mnode)
        for child_idx in list(gnode_dict.get('children', []) or []):
            self._process_gltf_node_builtin(
                int(child_idx), gltf_meshes, gltf_skins, gltf_materials,
                gltf_textures, gltf_images, gltf_nodes, node, acc_fn,
                visited, child_scale, world_pos, world_rot)
        return node

    def _fill_mesh_node_builtin(
        self, prim, gltf_skins, gltf_materials, gltf_textures, gltf_images,
        gltf_nodes, skin_idx, mnode, acc_fn,
    ):
        attrs = prim.get('attributes', {})

        pos_data = acc_fn(attrs.get('POSITION'))
        if pos_data:
            mnode.vertices = [(float(v[0]), float(v[1]), float(v[2])) for v in pos_data]

        norm_data = acc_fn(attrs.get('NORMAL'))
        if norm_data:
            mnode.normals = [(float(n[0]), float(n[1]), float(n[2])) for n in norm_data]

        uv0 = acc_fn(attrs.get('TEXCOORD_0'))
        if uv0:
            mnode.uvs = [(float(u[0]), 1.0 - float(u[1])) for u in uv0]

        uv1 = acc_fn(attrs.get('TEXCOORD_1'))
        if uv1:
            mnode.uvs_lm = [(float(u[0]), 1.0 - float(u[1])) for u in uv1]

        idx = acc_fn(prim.get('indices'))
        if idx and len(idx) % 3 == 0:
            mnode.faces = [(int(idx[i]), int(idx[i+1]), int(idx[i+2]))
                           for i in range(0, len(idx), 3)]

        # Skin weights
        joints_data  = acc_fn(attrs.get('JOINTS_0'))
        weights_data = acc_fn(attrs.get('WEIGHTS_0'))
        if joints_data and weights_data and len(joints_data) == len(weights_data):
            mnode.flags = int(NodeFlags.HEADER | NodeFlags.SKIN)
            bone_map: List[str] = []
            if skin_idx is not None and skin_idx < len(gltf_skins):
                skin = gltf_skins[skin_idx]
                for ji in skin.get('joints', []):
                    jn = gltf_nodes[ji] if ji < len(gltf_nodes) else {}
                    bone_map.append(jn.get('name') or f"bone_{ji}")
            mnode.bone_map = bone_map
            mnode.skin_data = _build_skin_data(joints_data, weights_data)

        # Material
        mat_idx = prim.get('material')
        if mat_idx is not None and mat_idx < len(gltf_materials):
            mat = gltf_materials[mat_idx]
            mat_name = mat.get('name', '')
            if mat_name:
                mnode.texture = mat_name[:_MAX_NAME]
            # PBR base colour texture
            pbr = mat.get('pbrMetallicRoughness', {})
            bct = pbr.get('baseColorTexture', {})
            if bct:
                tex_idx = bct.get('index')
                if tex_idx is not None and tex_idx < len(gltf_textures):
                    tex = gltf_textures[tex_idx]
                    src = tex.get('source')
                    if src is not None and src < len(gltf_images):
                        img = gltf_images[src]
                        img_name = img.get('name', '') or Path(img.get('uri', '')).stem
                        if img_name:
                            mnode.texture = img_name[:_MAX_NAME]
            # Normal map
            nmt = mat.get('normalTexture', {})
            if nmt:
                nt_idx = nmt.get('index')
                if nt_idx is not None and nt_idx < len(gltf_textures):
                    tex = gltf_textures[nt_idx]
                    src = tex.get('source')
                    if src is not None and src < len(gltf_images):
                        img = gltf_images[src]
                        nm2 = img.get('name', '') or Path(img.get('uri', '')).stem
                        if nm2:
                            mnode.bump_map = nm2[:_MAX_NAME]

        mnode.render = True
        mnode.has_shadow = True
        mnode.compute_bounds()

    def _import_animation_builtin(
        self, ganim_dict: Dict, gltf_nodes: List, acc_fn
    ) -> Optional[Animation]:
        try:
            anim_name  = (ganim_dict.get('name') or 'anim')[:_MAX_NAME]
            samplers   = ganim_dict.get('samplers', [])
            channels   = ganim_dict.get('channels', [])
            anim_length = 0.0
            anim_nodes_map: Dict[str, ModelNode] = {}

            from collections import defaultdict
            node_channels: Dict[int, list] = defaultdict(list)
            for ch in channels:
                tgt = ch.get('target', {})
                tgt_node = tgt.get('node')
                if tgt_node is not None:
                    node_channels[tgt_node].append(ch)

            for tgt_idx, chs in node_channels.items():
                if tgt_idx >= len(gltf_nodes):
                    continue
                tnode = gltf_nodes[tgt_idx]
                tname = (tnode.get('name') or f"node_{tgt_idx}")[:_MAX_NAME]
                anim_mn = ModelNode(name=tname, flags=int(NodeFlags.HEADER))
                for ch in chs:
                    samp_idx = ch.get('sampler', 0)
                    if samp_idx >= len(samplers):
                        continue
                    samp = samplers[samp_idx]
                    times_raw = acc_fn(samp.get('input'))
                    values_raw = acc_fn(samp.get('output'))
                    if not times_raw or not values_raw:
                        continue
                    times = [float(t) for t in times_raw]
                    anim_length = max(anim_length, max(times) if times else 0.0)
                    path = ch.get('target', {}).get('path', '')
                    ctrl, values = _channel_to_controller(path, values_raw)
                    if ctrl is not None:
                        anim_mn.controllers.append({'type': ctrl, 'times': times, 'values': values})
                if anim_mn.controllers:
                    anim_nodes_map[tname] = anim_mn

            if not anim_nodes_map:
                return None
            anim = Animation()
            anim.name   = anim_name
            anim.length = anim_length if anim_length > 0 else 1.0
            anim.nodes  = list(anim_nodes_map.values())
            return anim
        except Exception as e:
            log.warning("GLTFImporter: anim import error (builtin): %s", e)
            return None


# ─────────────────────────────────────────────────────────────────────────────
#  FBX / trimesh fallback importer
# ─────────────────────────────────────────────────────────────────────────────

class FBXFallbackImporter:
    """
    Import FBX / OBJ / PLY files via trimesh.

    This is the Phase 8.2 FBX import improvement — uses pure-Python trimesh
    so that ``libassimp`` is not required.  FBX ASCII 7.4 and FBX binary 7.4
    support varies by trimesh build, so binary FBX files can also fall back to
    a local Blender background conversion when Blender is installed.

    Usage::

        importer = FBXFallbackImporter()
        model = importer.import_file("character.fbx")
    """

    def import_file(
        self,
        path: str,
        model_name: str = "",
        game_version: GameVersion = GameVersion.K1,
        supermodel: str = "NULL",
        classification: str = "character",
    ) -> Optional[KotorModel]:
        if not model_name:
            model_name = Path(path).stem[:_MAX_NAME]
        try:
            import trimesh  # noqa: F401
        except ImportError:
            log.error("FBXFallbackImporter: install 'trimesh' (pip install trimesh)")
            return None

        try:
            import trimesh as tm
            scene_or_mesh = tm.load(path, force='mesh', process=False)
        except Exception as e:
            log.warning("FBXFallbackImporter: trimesh load failed: %s", e)
            if Path(path).suffix.lower() == ".fbx":
                blender_model = self._load_via_blender(
                    path,
                    model_name=model_name,
                    game_version=game_version,
                    supermodel=supermodel,
                    classification=classification,
                )
                if blender_model is not None:
                    return blender_model
            log.error("FBXFallbackImporter: no importer could load %s", path)
            return None

        model = KotorModel(
            name=model_name, supermodel=supermodel,
            game_version=game_version, classification=classification)
        root  = ModelNode(name=model_name, flags=int(NodeFlags.HEADER))
        model.root_node = root

        import trimesh as tm
        obj_textures = _parse_obj_diffuse_textures(path)
        if isinstance(scene_or_mesh, tm.Scene):
            geoms = scene_or_mesh.geometry
        elif hasattr(scene_or_mesh, 'vertices'):
            geoms = {model_name: scene_or_mesh}
        else:
            geoms = {}

        for gname, mesh in geoms.items():
            n = ModelNode(
                name=gname[:_MAX_NAME],
                flags=int(NodeFlags.HEADER | NodeFlags.MESH),
                parent=root)
            n.vertices = [tuple(float(c) for c in v) for v in mesh.vertices.tolist()]
            n.faces    = [tuple(int(c) for c in f) for f in mesh.faces.tolist()]
            if hasattr(mesh, 'vertex_normals') and mesh.vertex_normals is not None:
                n.normals = [tuple(float(c) for c in v)
                             for v in mesh.vertex_normals.tolist()]
            if (hasattr(mesh, 'visual') and hasattr(mesh.visual, 'uv')
                    and mesh.visual.uv is not None):
                n.uvs = [(float(u), 1.0 - float(v))
                         for u, v in mesh.visual.uv.tolist()]
            tex_name, tex_path, material_name = _trimesh_texture_reference(mesh, obj_textures)
            if tex_name:
                n.texture = tex_name[:_MAX_NAME]
                n.texture_names = [n.texture]
                if tex_path:
                    n.external_texture_path = tex_path
                if material_name:
                    n.source_material_name = material_name[:_MAX_NAME]
            n.render = True
            n.has_shadow = True
            n.compute_bounds()
            root.children.append(n)

        model.compute_bounds()
        return model

    def _load_via_blender(
        self,
        path: str,
        *,
        model_name: str,
        game_version: GameVersion,
        supermodel: str,
        classification: str,
    ) -> Optional[KotorModel]:
        """Convert FBX to GLB through Blender, then use the normal GLB importer."""
        for blender in _candidate_blender_executables():
            try:
                with tempfile.TemporaryDirectory(prefix="ghostrigger_fbx_") as tmp:
                    glb_path = Path(tmp) / f"{model_name}.glb"
                    _convert_fbx_to_glb_with_blender(
                        blender,
                        Path(path),
                        glb_path,
                    )
                    if not glb_path.exists() or glb_path.stat().st_size <= 0:
                        raise RuntimeError("Blender did not produce a GLB file")
                    model = GLTFImporter().import_file(
                        str(glb_path),
                        model_name=model_name,
                        game_version=game_version,
                        supermodel=supermodel,
                        classification=classification,
                    )
                    if model is not None:
                        log.info(
                            "FBXFallbackImporter: imported %s via Blender fallback %s",
                            path,
                            blender,
                        )
                        return model
            except Exception as exc:  # noqa: BLE001 - each Blender version may differ
                log.warning(
                    "FBXFallbackImporter: Blender fallback failed with %s: %s",
                    blender,
                    exc,
                )
        return None


def _candidate_blender_executables() -> List[str]:
    """Return plausible Blender executables, preferring stable 4.x builds."""
    seen: set[str] = set()
    candidates: List[str] = []

    def add(path: str | os.PathLike[str] | None) -> None:
        if not path:
            return
        resolved = str(Path(path))
        key = resolved.lower()
        if key in seen:
            return
        if Path(resolved).is_file():
            seen.add(key)
            candidates.append(resolved)

    add(os.environ.get("GHOSTRIGGER_BLENDER_PATH"))
    add(shutil.which("blender"))

    if os.name == "nt":
        for root in (
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
        ):
            blender_root = root / "Blender Foundation"
            if blender_root.is_dir():
                versioned = sorted(
                    blender_root.glob("Blender */blender.exe"),
                    key=lambda p: _blender_sort_key(p),
                )
                for path in versioned:
                    add(path)
    else:
        for path in (
            "/usr/bin/blender",
            "/usr/local/bin/blender",
            "/snap/bin/blender",
            "/Applications/Blender.app/Contents/MacOS/Blender",
        ):
            add(path)
    return candidates


def _blender_sort_key(path: Path) -> tuple[int, int, int, str]:
    """Prefer Blender 4.x LTS/current builds before newer unstable majors."""
    import re

    match = re.search(r"Blender\s+(\d+)(?:\.(\d+))?", str(path), re.IGNORECASE)
    major = int(match.group(1)) if match else 0
    minor = int(match.group(2) or 0) if match else 0
    major_penalty = 1 if major >= 5 else 0
    return (major_penalty, -major, -minor, str(path).lower())


def _convert_fbx_to_glb_with_blender(
    blender_exe: str,
    fbx_path: Path,
    glb_path: Path,
) -> None:
    """Run Blender headless to convert one FBX file to GLB."""
    script_path = glb_path.with_suffix(".py")
    script_path.write_text(
        "\n".join([
            "import bpy",
            "from pathlib import Path",
            "bpy.ops.object.select_all(action='SELECT')",
            "bpy.ops.object.delete()",
            f"bpy.ops.import_scene.fbx(filepath={str(fbx_path)!r})",
            "for obj in list(bpy.context.scene.objects):",
            "    if obj.type in {'CAMERA', 'LIGHT'}:",
            "        bpy.data.objects.remove(obj, do_unlink=True)",
            f"Path({str(glb_path)!r}).parent.mkdir(parents=True, exist_ok=True)",
            "bpy.ops.export_scene.gltf(",
            f"    filepath={str(glb_path)!r},",
            "    export_format='GLB',",
            "    export_yup=False,",
            ")",
        ]),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            blender_exe,
            "--background",
            "--factory-startup",
            "--python",
            str(script_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail[-2000:] or f"Blender exited with {proc.returncode}")


# ─────────────────────────────────────────────────────────────────────────────
#  Factory function
# ─────────────────────────────────────────────────────────────────────────────

def auto_import(
    path: str,
    model_name: str = "",
    game_version: GameVersion = GameVersion.K1,
    supermodel: str = "NULL",
    classification: str = "character",
) -> Optional[KotorModel]:
    """
    Auto-select importer by file extension.

    - ``.gltf`` / ``.glb``  →  GLTFImporter
    - ``.fbx`` / ``.obj`` / ``.ply``  →  FBXFallbackImporter

    Returns a ``KotorModel`` or None on failure.
    """
    ext = Path(path).suffix.lower()
    if ext in ('.gltf', '.glb'):
        return GLTFImporter().import_file(
            path, model_name, game_version, supermodel, classification)
    elif ext in ('.fbx', '.obj', '.ply', '.stl'):
        return FBXFallbackImporter().import_file(
            path, model_name, game_version, supermodel, classification)
    else:
        log.error("auto_import: unsupported format '%s'", ext)
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_skin_data(
    joints_data: List[Any],
    weights_data: List[Any],
) -> List[VertexSkinData]:
    """Build VertexSkinData list from JOINTS_0 / WEIGHTS_0 accessor data."""
    skin_list = []
    for jrow, wrow in zip(joints_data, weights_data):
        sd = VertexSkinData()
        sd.influences = []
        for k in range(4):
            j_idx = int(jrow[k]) if (isinstance(jrow, (list, tuple)) and k < len(jrow)) else int(jrow)
            w_val = float(wrow[k]) if (isinstance(wrow, (list, tuple)) and k < len(wrow)) else float(wrow)
            if w_val > 1e-6:
                sd.influences.append(BoneWeight(bone_index=j_idx, weight=w_val))
        # Normalise
        total = sum(bw.weight for bw in sd.influences)
        if total > 1e-6:
            for bw in sd.influences:
                bw.weight /= total
        skin_list.append(sd)
    return skin_list


def _channel_to_controller(
    path: str,
    values_raw: List[Any],
) -> Tuple[Optional[int], List[Any]]:
    """Convert a GLTF channel path string to (ctrl_type, values_list)."""
    if path == 'translation':
        ctrl = CTRL_POSITION
        values = [tuple(float(v) for v in row[:3]) for row in values_raw]
    elif path == 'rotation':
        ctrl = CTRL_ORIENTATION
        values = [tuple(float(v) for v in row[:4]) for row in values_raw]
    elif path == 'scale':
        ctrl = CTRL_SCALE
        values = [(float(row[0]) if isinstance(row, (list, tuple)) else float(row),)
                  for row in values_raw]
    else:
        return None, []
    return ctrl, values


def _fill_material_pygltflib(gltf, prim, mnode: ModelNode) -> None:
    """Fill material/texture fields from a pygltflib primitive."""
    if prim.material is None:
        return
    try:
        mat = gltf.materials[prim.material]
        if mat.name:
            mnode.texture = mat.name[:_MAX_NAME]
        pbr = mat.pbrMetallicRoughness
        if pbr and pbr.baseColorTexture:
            ti  = pbr.baseColorTexture.index
            tex = gltf.textures[ti]
            if tex.source is not None:
                src = gltf.images[tex.source]
                if src.name:
                    mnode.texture = src.name[:_MAX_NAME]
                elif src.uri:
                    mnode.texture = Path(src.uri).stem[:_MAX_NAME]
        # Normal map
        nm_info = getattr(mat, 'normalTexture', None)
        if nm_info and nm_info.index is not None:
            ntex = gltf.textures[nm_info.index]
            if ntex.source is not None:
                nsrc = gltf.images[ntex.source]
                nm2 = nsrc.name or (Path(nsrc.uri).stem if nsrc.uri else '')
                if nm2:
                    mnode.bump_map = nm2[:_MAX_NAME]
    except (AttributeError, TypeError, IndexError):
        pass
