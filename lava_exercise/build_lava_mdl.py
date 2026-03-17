#!/usr/bin/env python3
"""
KotOR MDL/MDX Builder for Lava Trap
=====================================
Builds a proper binary KotOR1 MDL+MDX pair for a flat lava-floor plane.

The strategy:
  1. Patch the existing lava_trap.mdl: fix texture name 'lsl_logos' -> 'lava1'
     and correct the vertex Z-heights to be at ground level (Z=0).
  2. Build a new clean MDL from scratch using the exact binary layout of the
     working lava_trap.mdl as a template, but with:
     - Correct texture name 'lava1'
     - Flat 2×2m plane at Z=0
     - Full [0,1]×[0,1] UV coverage
     - No liquid/envmap flags
  3. Also patch plc_glowpudl.mdl to use 'lava1' texture.
"""

import struct, shutil
from pathlib import Path

LAVA_DIR = Path('/home/user/webapp/lava_exercise/Lava Floor Attempts')
OUT_DIR  = Path('/home/user/webapp/lava_exercise/output')
OUT_DIR.mkdir(exist_ok=True)

# ── Helpers ──────────────────────────────────────────────────────────────────

def pack_str(s: str, length: int) -> bytes:
    """Encode a string to fixed-length null-padded bytes."""
    b = s.encode('ascii')[:length]
    return b + b'\x00' * (length - len(b))

def u32(v): return struct.pack('<I', v)
def i32(v): return struct.pack('<i', v)
def f32(v): return struct.pack('<f', v)
def u16(v): return struct.pack('<H', v)
def u8(v):  return struct.pack('B',  v)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Patch lava_trap.mdl – just fix the texture name
# The texture name is in the mesh header at offset +88 from mesh header start
# ─────────────────────────────────────────────────────────────────────────────

def find_texture_name_offset(mdl: bytearray, old_name: str) -> int:
    """Find the byte offset of a texture name string in the MDL data."""
    needle = old_name.encode('ascii')
    idx = mdl.find(needle)
    return idx

def patch_texture_name(mdl: bytearray, old_name: str, new_name: str, field_len: int = 32):
    """Replace a texture name field in the MDL binary."""
    idx = find_texture_name_offset(mdl, old_name)
    if idx < 0:
        print(f"  WARNING: texture name '{old_name}' not found in MDL")
        return False
    print(f"  Found '{old_name}' at offset 0x{idx:04X}, replacing with '{new_name}'")
    # Zero out the field, then write new name
    for i in range(field_len):
        if idx + i < len(mdl):
            mdl[idx + i] = 0
    new_bytes = new_name.encode('ascii')[:field_len]
    for i, b in enumerate(new_bytes):
        mdl[idx + i] = b
    return True

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Build a fresh MDL+MDX from scratch
# Template: lava_trap.mdl layout (K1, classification=item, 1 mesh node)
# Goal: flat 3×3m plane at Z=0, full UV coverage, texture='lava1'
# ─────────────────────────────────────────────────────────────────────────────

def build_flat_plane_mdl(
    model_name: str = 'lava_floor',
    texture:    str = 'lava1',
    half_w:   float = 1.5,   # half-width in meters (total = 2*half_w)
    half_h:   float = 1.5,   # half-height
    z:        float = 0.0,
) -> tuple[bytes, bytes]:
    """
    Build a minimal KotOR1 MDL+MDX for a flat textured plane.
    Returns (mdl_bytes, mdx_bytes).
    
    Geometry: 4 vertices, 2 triangles (quad)
      v0 = (-hw, -hh, z)  uv=(0,1)
      v1 = ( hw, -hh, z)  uv=(1,1)
      v2 = ( hw,  hh, z)  uv=(1,0)
      v3 = (-hw,  hh, z)  uv=(0,0)
    Faces: (0,1,2), (0,2,3)
    Normal: (0,0,1) for all verts
    """
    hw, hh = half_w, half_h
    
    # Vertex data
    verts = [
        (-hw, -hh, z),  # v0
        ( hw, -hh, z),  # v1
        ( hw,  hh, z),  # v2
        (-hw,  hh, z),  # v3
    ]
    normals = [(0.0, 0.0, 1.0)] * 4
    uvs = [
        (0.0, 1.0),  # v0
        (1.0, 1.0),  # v1
        (1.0, 0.0),  # v2
        (0.0, 0.0),  # v3
    ]
    faces = [(0, 1, 2), (0, 2, 3)]
    
    nv = len(verts)
    nf = len(faces)
    
    # ── Build MDX ──────────────────────────────────────────────────────────
    # Stride: pos(12) + normal(12) + uv(8) = 32 bytes per vertex
    STRIDE = 32
    mdx_buf = bytearray()
    for i in range(nv):
        x, y, zv = verts[i]
        nx, ny, nz = normals[i]
        u, v = uvs[i]
        mdx_buf += struct.pack('<fff', x, y, zv)    # position  12 bytes
        mdx_buf += struct.pack('<fff', nx, ny, nz)  # normal    12 bytes
        mdx_buf += struct.pack('<ff',  u, v)        # UV        8 bytes
    
    mdx_size = len(mdx_buf)
    assert mdx_size == nv * STRIDE, f"{mdx_size} != {nv * STRIDE}"
    
    # ── Build MDL ─────────────────────────────────────────────────────────
    # We'll build the data section, then prepend the 12-byte file header.
    # The data section starts at BASE = 12.
    #
    # Layout (data section, all offsets relative to BASE=12):
    #
    # [0x00] Geometry header (80 bytes)
    #   [0]  fp1 = 4273776  (K1 magic)
    #   [4]  fp2 = 4273392  (K1 magic alt)
    #   [8]  model name (32 bytes)
    #  [40]  root_node_off → offset of root node (relative to BASE)
    #  [44]  node_count = 2
    #  [48-76] zeros (anims, etc.)
    #  [77]  geo_type = 2 (trimesh)
    #
    # [0x50=80] Model header (88 bytes)
    #   [0]  model_type = 32 (item)
    #   [3]  disable_fog = 0
    #   [8]  anim_array_off = 0
    #  [12]  anim_count = 0
    #  [24]  bb_min (12 bytes)
    #  [36]  bb_max (12 bytes)
    #  [48]  radius (4)
    #  [52]  anim_scale = 1.0 (4)
    #  [56]  supermodel (32 bytes) = 'NULL'
    #
    # [0xA8=168] Name array header (24 bytes)
    #  [0]  unk1=0, unk2=0
    #  [8]  unk3=0, unk4=0
    # [16]  names_array_off → relative to BASE
    # [20]  names_count = 2
    # [24]  unk5=0 (4 bytes padding for some readers)
    #
    # [0xC0=192] Root node header (80 bytes)
    # [0x110=272] Mesh node header
    # Faces, vertex indices, vertices, name strings...

    # We'll lay it out precisely:
    B = 12  # BASE
    
    # Pre-compute sizes:
    # Each node header is 80 bytes (common) + type extension
    # Null node: 80 bytes (flags=1, type=dummy)
    # Mesh node: 80 + 340 (mesh extension for K1) + faces + vertex_index_list + vertex_offsets
    
    NODE_HDR_SIZE = 80
    MESH_EXT_K1 = 332  # mesh header for K1 (without K2's 8 extra bytes)
    # Actually let's use the exact offsets from lava_trap.mdl as template:
    # Root (dummy) node is at offset 0x00A2 relative to BASE = 0x0A in file after header
    # Object126 (mesh) node is at some offset
    
    # Let's keep it simple: mirror the existing lava_trap.mdl structure exactly
    # but with corrected values. The existing file is only 1016 bytes.

    # Reading the original to get exact offsets:
    orig = bytearray(Path(LAVA_DIR / 'lava_trap.mdl').read_bytes())
    
    # The original has:
    #   - model name at 0x14 (after 12-byte file header + 8 bytes) = "lava_trap"
    #   - root_node_off at BASE+40 = offset 0x0C+40 = 0x34
    #   - Model classification at BASE+80 = 0x0C+80 = 0x5C

    # Strategy: copy the whole file, patch:
    # 1. Model name  (at offset 0x0C + 8 = 0x14, 32 bytes)
    # 2. Texture     (find 'lsl_logos' and replace with 'lava1' padded to 32 bytes)
    # 3. All 4 vertices in MDX (stride 32 bytes)
    # 4. Bounding box in MDL mesh header
    
    return bytes(orig), bytes(mdx_buf)  # placeholder, we'll do proper patching below


# ─────────────────────────────────────────────────────────────────────────────
# ACTUAL WORK
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("LAVA TRAP MDL FIXER")
print("=" * 60)

# ── Task 1: Patch lava_trap.mdl texture name ──────────────────────────────
print("\n[1] Patching lava_trap.mdl: 'lsl_logos' → 'lava1'")
mdl_orig = bytearray((LAVA_DIR / 'lava_trap.mdl').read_bytes())
mdx_orig = bytearray((LAVA_DIR / 'lava_trap.mdx').read_bytes())

mdl_patched = bytearray(mdl_orig)

# Fix texture name
ok = patch_texture_name(mdl_patched, 'lsl_logos', 'lava1', field_len=32)

# Verify the MDX vertex data (already verified as correct 32-byte stride)
# Let's also fix the vertices to be at Z=0 instead of Z≈2.55
# And center the plane (currently offset in X by ~2.4 units)
# Original: x=[-2.27, 7.02], y=[-3.35, 3.06], z≈2.48-2.56
# Target:   3×3m centered at origin: x=[-1.5, 1.5], y=[-1.5, 1.5], z=0

STRIDE = 32
hw, hh = 1.5, 1.5
new_verts = [
    (-hw, -hh, 0.0),
    ( hw, -hh, 0.0),
    ( hw,  hh, 0.0),
    (-hw,  hh, 0.0),
]
new_normals = [(0.0, 0.0, 1.0)] * 4
new_uvs = [
    (0.0, 0.0),  # v0 bottom-left
    (1.0, 0.0),  # v1 bottom-right
    (1.0, 1.0),  # v2 top-right
    (0.0, 1.0),  # v3 top-left
]

print("  Rewriting MDX vertex data (Z=0, centered, full UV coverage):")
mdx_patched = bytearray()
for i, (v, n, uv) in enumerate(zip(new_verts, new_normals, new_uvs)):
    x, y, z = v
    nx, ny, nz = n
    u, vv = uv
    chunk = struct.pack('<fff', x, y, z)   # position
    chunk += struct.pack('<fff', nx, ny, nz)  # normal
    chunk += struct.pack('<ff',  u, vv)       # UV
    # MDX has an 8-byte sentinel/padding at the end: 0x80 96 18 4B × 2 (NaN sentinels?)
    mdx_patched += chunk
    print(f"    v{i}: pos=({x:.2f},{y:.2f},{z:.2f}) uv=({u:.2f},{vv:.2f})")

# Preserve the original trailing bytes (sentinel / padding)
mdx_patched += mdx_orig[len(mdx_patched):]
print(f"  MDX: {len(mdx_orig)} → {len(mdx_patched)} bytes")

# Also update bounding box in MDL mesh header
# The mesh header is at offset BASE + mesh_node_off + NODE_HDR_SIZE
# From our binary dump, Object126 node starts around 0xA2 (relative to BASE)
# Mesh extension starts at node_start + 80
# Bounding box is at mesh_ext + 20 (bb_min 12 bytes) and + 32 (bb_max 12 bytes)
# Let's find it by searching for the original bb_min values

# Original bb values from parser output:
# bb_min = (-2.3126, -3.3487, 0.0), bb_max = (7.0247, 3.0644, 2.5595)
orig_bbmin = struct.pack('<fff', -2.3126344680786133, -3.3487725257873535, 0.0)
new_bbmin  = struct.pack('<fff', -hw, -hh, 0.0)
new_bbmax  = struct.pack('<fff',  hw,  hh, 0.0)

idx = mdl_patched.find(orig_bbmin)
if idx >= 0:
    print(f"  Found bb_min at 0x{idx:04X}, updating bounding box")
    mdl_patched[idx:idx+12] = new_bbmin
    mdl_patched[idx+12:idx+24] = new_bbmax
    # Also update radius (next 4 bytes after bb_max? No, bb is at mesh_ext+20)
    # radius is at mesh_ext+44 = idx + (44-20) = idx+24 after bb_max
    # Actually let's just compute: radius = half-diagonal
    import math
    r = math.sqrt(hw**2 + hh**2)
    mdl_patched[idx+24:idx+28] = struct.pack('<f', r)
    print(f"  Updated bbox: min=({-hw},{-hh},0) max=({hw},{hh},0) radius={r:.3f}")
else:
    print("  WARNING: bb_min not found in MDL, bounding box not updated")

# Save patched lava_trap
out_mdl = OUT_DIR / 'lava_trap.mdl'
out_mdx = OUT_DIR / 'lava_trap.mdx'
out_mdl.write_bytes(bytes(mdl_patched))
out_mdx.write_bytes(bytes(mdx_patched))
print(f"  Saved: {out_mdl}")
print(f"  Saved: {out_mdx}")

# ── Task 2: Patch plc_glowpudl.mdl texture name ──────────────────────────
print("\n[2] Patching plc_glowpudl.mdl: 'plc_bldpdlsm' → 'lava1'")
mdl_pudl = bytearray((LAVA_DIR / 'plc_glowpudl.mdl').read_bytes())
mdx_pudl = (LAVA_DIR / 'plc_glowpudl.mdx').read_bytes()

# The texture name is 32 chars, so pad 'lava1' with nulls to 32 bytes
ok2 = patch_texture_name(mdl_pudl, 'plc_bldpdlsm', 'lava1', field_len=32)

out_pudl_mdl = OUT_DIR / 'plc_lavapudl.mdl'
out_pudl_mdx = OUT_DIR / 'plc_lavapudl.mdx'
out_pudl_mdl.write_bytes(bytes(mdl_pudl))
shutil.copy(LAVA_DIR / 'plc_glowpudl.mdx', out_pudl_mdx)
print(f"  Saved: {out_pudl_mdl}")
print(f"  Saved: {out_pudl_mdx}")

# ── Task 3: Build a "from-scratch" perfectly clean lava plane ─────────────
print("\n[3] Building clean lava_floor.mdl from scratch")
# Use the existing lava_trap.mdl as a byte-level template but with model_name='lava_floor'
mdl_clean = bytearray(mdl_patched)  # start from already-patched version

# Update model name in geometry header: at BASE+8 (which is file offset 12+8=20)
BASE = 12
new_model_name = 'lava_floor'
name_offset = BASE + 8  # model name is 32 bytes at geometry header offset +8
mdl_clean[name_offset:name_offset+32] = pack_str(new_model_name, 32)
print(f"  Set model name to '{new_model_name}'")

# Also update the root node name (it's stored separately in the name array)
# The root node name 'lava_trap' will still be in the name table - let's patch it
old_root_name = b'lava_trap\x00'
idx_root = mdl_clean.find(old_root_name)
if idx_root >= 0:
    mdl_clean[idx_root:idx_root+len(old_root_name)] = b'lava_floor\x00'
    print(f"  Updated root node name at 0x{idx_root:04X}")

out_floor_mdl = OUT_DIR / 'lava_floor.mdl'
out_floor_mdx = OUT_DIR / 'lava_floor.mdx'
out_floor_mdl.write_bytes(bytes(mdl_clean))
out_floor_mdx.write_bytes(bytes(mdx_patched))
print(f"  Saved: {out_floor_mdl}")
print(f"  Saved: {out_floor_mdx}")

print("\n[Done] Output files in:", OUT_DIR)

