#!/usr/bin/env python3
"""
mdl_patch_texture.py  –  KotOR MDL Binary Texture-Name Patcher
================================================================
Replaces the primary texture (bitmap slot 0) name in a binary KotOR MDL file
without touching the MDX or any other data.

Usage:
    python mdl_patch_texture.py <input.mdl> <new_texture_name> [--out output.mdl]

    e.g.
      python mdl_patch_texture.py lava_trap.mdl lava1
      python mdl_patch_texture.py lava_trap.mdl lava1 --out lava_fixed.mdl

Algorithm:
    1. Parse the MDL file header to find the geometry root node.
    2. Walk the node tree.
    3. For every trimesh node (flags & 0x20) replace the 32-byte texture name
       field at mesh_extension_offset + 88.
    4. Re-write the MDL file (in-place or to a new path).

Why binary patching is safe:
    The texture name field is a fixed 32-byte null-padded ASCII slot.  As long
    as the new name fits in 32 chars we can overwrite it without touching any
    offsets, counts or the MDX.

Limitations:
    • Only patches slot-0 (bitmap / primary diffuse).  Lightmap (slot-1) is
      left unchanged.
    • Designed for K1 trimesh nodes.  Emitter / skin / dangly nodes are skipped.
    • Node children arrays are traversed recursively up to depth 32.
"""

import sys
import struct
import argparse
from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────────────────

BASE = 12  # All file-relative offsets in an MDL are relative to byte 12


def _ru32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0]


def _read_str(data: bytes, off: int, max_len: int = 64) -> str:
    end = data.find(b'\x00', off)
    if end < 0 or end > off + max_len:
        end = off + max_len
    return data[off:end].decode('ascii', errors='replace')


# ── Node walker ───────────────────────────────────────────────────────────────

def _walk_nodes(data: bytearray, abs_off: int, depth: int = 0, visited: set = None):
    """Yield (node_abs_offset, flags) for every node reachable from abs_off."""
    if visited is None:
        visited = set()
    if abs_off in visited or depth > 32:
        return
    visited.add(abs_off)

    if abs_off + 80 > len(data):
        return

    flags = _ru32(data, abs_off)
    yield abs_off, flags

    # Children: offset at node+44, count at node+48
    children_arr_off = _ru32(data, abs_off + 44)
    children_cnt     = _ru32(data, abs_off + 48)

    if children_cnt > 0 and children_arr_off > 0:
        ch_arr_abs = BASE + children_arr_off
        for i in range(min(children_cnt, 512)):
            ptr_off = ch_arr_abs + i * 4
            if ptr_off + 4 > len(data):
                break
            child_rel = _ru32(data, ptr_off)
            if child_rel == 0 or child_rel == 0xFFFFFFFF:
                continue
            yield from _walk_nodes(data, BASE + child_rel, depth + 1, visited)


# ── Main patch function ───────────────────────────────────────────────────────

def patch_mdl_texture(
    mdl_path: str | Path,
    new_texture: str,
    out_path:   str | Path | None = None,
    verbose: bool = True,
) -> int:
    """
    Patch all trimesh nodes in an MDL to use new_texture as their primary texture.

    Returns the number of nodes patched.
    """
    mdl_path = Path(mdl_path)
    if out_path is None:
        out_path = mdl_path
    out_path = Path(out_path)

    if len(new_texture) > 32:
        raise ValueError(f"Texture name too long ({len(new_texture)} > 32 chars): {new_texture!r}")

    data = bytearray(mdl_path.read_bytes())

    if len(data) < BASE + 80:
        raise ValueError(f"MDL too small ({len(data)} bytes)")

    # Geometry header: root_node_off at BASE+40
    root_node_off = _ru32(data, BASE + 40)
    if root_node_off == 0 or root_node_off == 0xFFFFFFFF:
        raise ValueError("MDL has no root node offset")

    root_abs = BASE + root_node_off
    patched_count = 0

    for node_abs, flags in _walk_nodes(data, root_abs):
        # Bit 5 (0x20) = trimesh node
        if not (flags & 0x20):
            continue

        # Mesh extension starts at node_abs + 80 (common node header is 80 bytes)
        mesh_ext = node_abs + 80

        if mesh_ext + 120 > len(data):
            if verbose:
                print(f"  [SKIP] Node at 0x{node_abs:04X}: mesh extension out of bounds")
            continue

        # Texture name field: mesh_ext + 88, 32 bytes
        tex_off = mesh_ext + 88
        old_tex = _read_str(data, tex_off, 32)

        new_tex_bytes = new_texture.encode('ascii')
        new_field = new_tex_bytes + b'\x00' * (32 - len(new_tex_bytes))

        data[tex_off:tex_off + 32] = new_field
        patched_count += 1

        if verbose:
            print(f"  Node at 0x{node_abs:04X}: '{old_tex}' → '{new_texture}'")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(data))

    if verbose:
        if out_path == mdl_path:
            print(f"Patched {patched_count} node(s) in '{mdl_path.name}' (in-place).")
        else:
            print(f"Patched {patched_count} node(s), saved to '{out_path}'.")

    return patched_count


# ── MDX vertex rebuilder (flat plane) ─────────────────────────────────────────

def rebuild_mdx_flat_plane(
    mdx_path: str | Path,
    out_path: str | Path | None = None,
    half_w: float = 1.5,
    half_h: float = 1.5,
    z: float = 0.0,
) -> None:
    """
    Replace the first 4 vertices in an MDX file with a centered flat quad at Z=z.

    Vertex layout (stride 32 bytes each):
        pos(12) + normal(12) + uv(8)

    UV assignment:
        v0 = (-hw, -hh, z)  uv=(0,0)
        v1 = ( hw, -hh, z)  uv=(1,0)
        v2 = ( hw,  hh, z)  uv=(1,1)
        v3 = (-hw,  hh, z)  uv=(0,1)
    """
    mdx_path = Path(mdx_path)
    if out_path is None:
        out_path = mdx_path
    out_path = Path(out_path)

    STRIDE = 32
    verts   = [(-half_w, -half_h, z), (half_w, -half_h, z),
               (half_w,  half_h, z),  (-half_w, half_h, z)]
    normals = [(0, 0, 1)] * 4
    uvs     = [(0, 0), (1, 0), (1, 1), (0, 1)]

    orig = bytearray(mdx_path.read_bytes())
    new_data = bytearray()

    for i in range(4):
        x, y, zv = verts[i]
        nx, ny, nz = normals[i]
        u, v = uvs[i]
        new_data += struct.pack('<fff', x, y, zv)
        new_data += struct.pack('<fff', nx, ny, nz)
        new_data += struct.pack('<ff',  u, v)

    # Preserve any trailing data (sentinel bytes etc.)
    new_data += orig[len(new_data):]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(new_data))
    print(f"Rebuilt MDX with flat plane [{-half_w},{-half_h},z={z}] → [{half_w},{half_h}], saved to '{out_path}'.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Patch texture names in a KotOR binary MDL file."
    )
    ap.add_argument('mdl', help='Path to the .mdl file')
    ap.add_argument('texture', help='New texture name (max 32 chars, no extension)')
    ap.add_argument('--out', default=None, help='Output MDL path (default: overwrite input)')
    ap.add_argument('--flat-mdx', action='store_true',
                    help='Also rebuild the MDX as a centered flat quad at Z=0')
    ap.add_argument('--mdx', default=None, help='Path to MDX (needed with --flat-mdx)')
    ap.add_argument('--mdx-out', default=None, help='Output MDX path (default: overwrite MDX input)')
    ap.add_argument('--half-w', type=float, default=1.5, help='Half-width of flat plane (m)')
    ap.add_argument('--half-h', type=float, default=1.5, help='Half-height of flat plane (m)')
    ap.add_argument('--z', type=float, default=0.0, help='Z height of flat plane')
    args = ap.parse_args()

    n = patch_mdl_texture(args.mdl, args.texture, out_path=args.out)
    if n == 0:
        print("WARNING: no trimesh nodes were patched.")
        sys.exit(1)

    if args.flat_mdx:
        mdx_path = args.mdx or Path(args.mdl).with_suffix('.mdx')
        mdx_out  = args.mdx_out
        rebuild_mdx_flat_plane(mdx_path, mdx_out,
                                half_w=args.half_w,
                                half_h=args.half_h,
                                z=args.z)


if __name__ == '__main__':
    main()
