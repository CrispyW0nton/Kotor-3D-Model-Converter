from __future__ import annotations

from .diagnostics import *  # noqa: F401,F403
@dataclass
class ModuleDrawItem:
    """Render record capturing per-node material/texture state for debugging.

    One ModuleDrawItem is created per draw call (per material slot for
    multi-texture nodes).  The collection can be printed as a table to
    verify that every visible surface uses the correct bitmap and material.

    Fields:
        node_name     : ModelNode.name
        node_type     : 'trimesh', 'skin', 'dangly', etc.
        bitmap        : Primary diffuse texture name used for this draw call
        lightmap      : Lightmap texture name ('' if none)
        envmap        : Environment-map texture name ('' if none)
        txi_blending  : TXI blend mode (0=none, 1=additive, 2=punchthrough)
        txi_decal     : Whether this is a decal surface
        txi_wateralpha: Water alpha multiplier
        txi_alpha_test: Punchthrough alpha threshold
        tri_count     : Number of triangles in this draw call
        mat_slot      : Material slot index (0 for single-tex; 0..N-1 for multi)
        transform     : (world_pos, world_orient) tuple
        pass_name     : 'opaque', 'cutout', or 'transparent'
    """
    node_name:      str   = ''
    node_type:      str   = ''
    bitmap:         str   = ''
    lightmap:       str   = ''
    envmap:         str   = ''
    txi_blending:   int   = 0
    txi_decal:      bool  = False
    txi_wateralpha: float = 1.0
    txi_alpha_test: float = 0.5
    tri_count:      int   = 0
    mat_slot:       int   = 0
    transform:      tuple = ()
    pass_name:      str   = 'opaque'


def debug_draw_table(model, textures: dict = None) -> str:
    """Return a human-readable table of per-node material/texture assignments.

    This is a diagnostic tool: call it with a loaded KotorModel to inspect
    the bitmap→node ownership before rendering.  Useful for verifying that
    module surfaces have correct texture assignments.

    Returns a multi-line string suitable for logging or UI display.
    """
    lines = []
    lines.append(f"{'Node':<30s} {'Type':<12s} {'Bitmap':<25s} {'Lightmap':<20s} "
                 f"{'EnvMap':<20s} {'Blend':>5s} {'Decal':>5s} {'WAlpha':>6s} "
                 f"{'ATest':>5s} {'Tris':>6s} {'Slots':>5s}")
    lines.append('-' * 160)

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    total_tris = 0
    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        n_name = str(getattr(node, 'name', '?'))[:29]
        n_type = str(getattr(node, 'type_label', '?'))[:11]
        bitmap = str(getattr(node, 'texture', '') or '').strip()[:24]
        lm = str(getattr(node, 'lightmap', '') or '').strip()[:19]
        env = str(getattr(node, 'txi_envmaptexture', '') or '').strip()[:19]
        blend = int(getattr(node, 'txi_blending', 0))
        decal = bool(getattr(node, 'txi_decal', False))
        walpha = float(getattr(node, 'txi_wateralpha', 1.0))
        atest = float(getattr(node, 'txi_alpha_test', 0.5))
        n_faces = len(getattr(node, 'faces', []))
        tc = int(getattr(node, 'tex_count', 1))
        total_tris += n_faces

        lines.append(f"{n_name:<30s} {n_type:<12s} {bitmap:<25s} {lm:<20s} "
                     f"{env:<20s} {blend:>5d} {'Y' if decal else 'N':>5s} "
                     f"{walpha:>6.2f} {atest:>5.2f} {n_faces:>6d} {tc:>5d}")

        # Show multi-texture slot details
        tex_names = getattr(node, 'texture_names', [])
        if tc > 1 and tex_names:
            for si, tn in enumerate(tex_names):
                _tn = str(tn or '').strip()[:24]
                _in_dict = '✓' if (textures and _tn.lower() in textures) else '?'
                lines.append(f"  └─ slot {si}: {_tn} [{_in_dict}]")

    lines.append('-' * 160)
    lines.append(f"Total mesh nodes: {sum(1 for n in nodes if getattr(n, 'is_mesh', False))}, "
                 f"Total triangles: {total_tris}")
    return '\n'.join(lines)


def debug_uv_channel_table(model) -> str:
    """Return a per-node UV channel audit table.

    Diagnostic function for Phase 2 of the face_uvs / tvert indexing audit.
    For each mesh node, reports:
      - node_name, texture, lightmap, tex_count, texture_names[]
      - lengths of uvs, uvs_lm, uvs_2, uvs_3, face_uvs
      - unique face_mats values
      - has_lightmap flag
      - whether face_uvs == faces (binary MDL convention)
      - which VBO path the node takes (IBO indexed vs expanded)

    Returns a multi-line string suitable for logging or UI display.
    """
    lines = []
    lines.append(f"{'Node':<28s} {'tex':>3s} {'has_lm':>6s} "
                 f"{'n_v':>5s} {'n_f':>5s} {'n_uv':>5s} {'n_lm':>5s} "
                 f"{'n_fuv':>5s} {'umat':>8s} {'fuv=f':>5s} {'path':>8s} "
                 f"{'texture':>24s} {'lightmap':>20s}")
    lines.append('-' * 170)

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        n_name  = str(getattr(node, 'name', '?'))[:27]
        texture = str(getattr(node, 'texture', '') or '').strip()[:24]
        lm      = str(getattr(node, 'lightmap', '') or '').strip()[:20]
        tc      = int(getattr(node, 'tex_count', 1))
        has_lm  = bool(getattr(node, 'has_lightmap', False))

        verts    = getattr(node, 'vertices', getattr(node, 'verts', []))
        faces    = getattr(node, 'faces', [])
        uvs      = getattr(node, 'uvs', [])
        uvs_lm   = getattr(node, 'uvs_lm', [])
        uvs_2    = getattr(node, 'uvs_2', [])
        uvs_3    = getattr(node, 'uvs_3', [])
        face_uvs = getattr(node, 'face_uvs', [])
        face_mats = getattr(node, 'face_mats', [])

        n_v = len(verts)
        n_f = len(faces)
        n_uv = len(uvs)
        n_lm = len(uvs_lm)
        n_fuv = len(face_uvs)

        # Unique face_mats
        umat = str(sorted(set(face_mats)))[:8] if face_mats else '-'

        # Check face_uvs == faces
        fuv_eq = '-'
        if n_fuv == n_f and n_f > 0:
            try:
                import numpy as _np
                _fuv = _np.asarray(face_uvs, dtype=_np.int32)
                _fv  = _np.asarray(faces, dtype=_np.int32)
                if _fuv.shape == _fv.shape:
                    fuv_eq = 'Y' if _np.array_equal(_fuv, _fv) else 'N'
            except Exception:
                fuv_eq = '?'

        # Determine VBO path
        is_skin = bool(getattr(node, 'is_skin', False))
        has_fuv = (n_fuv == n_f) and fuv_eq != 'Y'
        path = 'expand' if (has_fuv or is_skin) else 'IBO'

        lines.append(f"{n_name:<28s} {tc:>3d} {'Y' if has_lm else 'N':>6s} "
                     f"{n_v:>5d} {n_f:>5d} {n_uv:>5d} {n_lm:>5d} "
                     f"{n_fuv:>5d} {umat:>8s} {fuv_eq:>5s} {path:>8s} "
                     f"{texture:>24s} {lm:>20s}")

        # Show texture_names
        tex_names = getattr(node, 'texture_names', [])
        if tc > 1 and tex_names:
            for si, tn in enumerate(tex_names):
                role = 'diffuse' if si == 0 else ('lightmap' if (has_lm and si == 1) else f'slot{si}')
                lines.append(f"  └─ [{si}] {str(tn)[:24]} ({role})")

    lines.append('-' * 170)
    return '\n'.join(lines)


def debug_texture_cache_table(model, textures: dict = None) -> str:
    """Return a texture-cache validation table (Phase 4 diagnostic).

    For each texture referenced by the model, reports:
      - texture name
      - source image dimensions (W×H) or 'MISSING' if not in textures dict
      - cache key (id of the PIL Image object)
      - which nodes reference this texture (as diffuse, lightmap, env, spec)

    This proves that distinct textures are not sharing the same cached GPU
    upload — each unique PIL Image should have a unique id() / cache key.

    Parameters
    ----------
    model     : KotorModel
    textures  : dict mapping lowercased texture name → PIL Image

    Returns a multi-line string suitable for logging or UI display.
    """
    textures = textures or {}
    lines = []
    lines.append(f"{'Texture Name':<30s} {'Dims':>10s} {'CacheKey(id)':>16s} "
                 f"{'Role':>10s} {'Nodes Using It':<50s}")
    lines.append('-' * 130)

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    # Collect all texture references and the nodes that use them
    tex_refs: dict = {}  # name → {role: set of node names}
    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        n_name = str(getattr(node, 'name', '?'))

        tex = str(getattr(node, 'texture', '') or '').strip().lower()
        if tex and tex not in ('null', 'none', ''):
            tex_refs.setdefault(tex, {}).setdefault('diffuse', set()).add(n_name)

        lm = str(getattr(node, 'lightmap', '') or '').strip().lower()
        if lm and lm not in ('null', 'none', ''):
            tex_refs.setdefault(lm, {}).setdefault('lightmap', set()).add(n_name)

        env = str(getattr(node, 'txi_envmaptexture', '') or '').strip().lower()
        if env:
            tex_refs.setdefault(env, {}).setdefault('envmap', set()).add(n_name)

        spec = str(getattr(node, 'txi_specularcolour', '') or '').strip().lower()
        if spec:
            tex_refs.setdefault(spec, {}).setdefault('specular', set()).add(n_name)

    # Build the table
    seen_keys = set()
    for tex_name in sorted(tex_refs.keys()):
        roles = tex_refs[tex_name]
        img = textures.get(tex_name)
        if img is not None:
            try:
                dims = f"{img.size[0]}×{img.size[1]}"
            except Exception:
                dims = "?"
            cache_key = str(id(img))
            if cache_key in seen_keys:
                dims += " SHARED!"
            seen_keys.add(cache_key)
        else:
            dims = "MISSING"
            cache_key = "-"

        for role, node_set in sorted(roles.items()):
            node_list = ', '.join(sorted(node_set))
            if len(node_list) > 49:
                node_list = node_list[:46] + '...'
            lines.append(f"{tex_name:<30s} {dims:>10s} {cache_key:>16s} "
                         f"{role:>10s} {node_list:<50s}")

    lines.append('-' * 130)

    # Check for duplicate cache keys (same PIL object used for different names)
    key_to_names: dict = {}
    for tex_name in tex_refs:
        img = textures.get(tex_name)
        if img is not None:
            key = id(img)
            key_to_names.setdefault(key, []).append(tex_name)
    dups = {k: v for k, v in key_to_names.items() if len(v) > 1}
    if dups:
        lines.append("WARNING: Same PIL Image object used for multiple texture names:")
        for k, names in dups.items():
            lines.append(f"  id={k} → {', '.join(names)}")
    else:
        lines.append("OK: All texture names map to distinct PIL Image objects.")

    return '\n'.join(lines)


def debug_material_role_table(model) -> str:
    """Return a material-role audit table (Phase 1 diagnostic).

    For each mesh node, shows the material-role semantics:
      - node name, texture, lightmap, tex_count, texture_names[]
      - has_lightmap flag (from MDL binary)
      - FIX-LMROLE: whether lightmap role was inferred
      - lengths of uvs, uvs_lm
      - unique face_mats
      - renderer dispatch path (single/Case A/Case B)
      - slot 1 role (lightmap vs secondary diffuse)
      - whether lightmap will be bound in _draw_node

    Returns a multi-line string suitable for logging or UI display.
    """
    lines = []
    lines.append(f"{'Node':<26s} {'texture':<20s} {'lightmap':<18s} "
                 f"{'tc':>2s} {'lm?':>3s} {'infer':>5s} "
                 f"{'uvs':>5s} {'uv_lm':>5s} {'fm':>8s} "
                 f"{'dispatch':<18s} {'slot1_role':<16s} {'lm_bind':>7s}")
    lines.append('-' * 160)

    all_fn = getattr(model, 'all_nodes', None)
    nodes = list(all_fn()) if all_fn else getattr(model, 'nodes', [])

    for node in nodes:
        if not getattr(node, 'is_mesh', False):
            continue
        n_name  = str(getattr(node, 'name', '?'))[:25]
        texture = str(getattr(node, 'texture', '') or '').strip().lower()[:19]
        lm      = str(getattr(node, 'lightmap', '') or '').strip().lower()[:17]
        tc      = int(getattr(node, 'tex_count', 1))
        has_lm  = bool(getattr(node, 'has_lightmap', False))
        tex_names = getattr(node, 'texture_names', [])

        uvs     = getattr(node, 'uvs', [])
        uvs_lm  = getattr(node, 'uvs_lm', [])
        face_mats = getattr(node, 'face_mats', [])

        n_uv  = len(uvs)
        n_lm  = len(uvs_lm)
        umat  = str(sorted(set(face_mats)))[:8] if face_mats else '-'

        # Determine if FIX-LMROLE would infer lightmap
        _inferred = False
        if (not has_lm and tc == 2 and n_lm > 0
                and n_lm == n_uv and face_mats
                and all(m == 0 for m in face_mats)):
            _inferred = True
        _effective_lm = has_lm or _inferred

        # Dispatch path
        if tc <= 1 or len(tex_names) < tc:
            dispatch = 'single-tex'
            slot1_role = 'N/A'
        elif _effective_lm:
            dispatch = 'Case A (lightmap)'
            slot1_role = 'lightmap'
        else:
            dispatch = 'Case B (multi-mat)'
            slot1_role = 'secondary diffuse'

        # Lightmap binding
        lm_bind = 'YES' if (_effective_lm and lm and n_lm > 0) else 'NO'

        lines.append(f"{n_name:<26s} {texture:<20s} {lm:<18s} "
                     f"{tc:>2d} {'Y' if has_lm else 'N':>3s} "
                     f"{'INF' if _inferred else '-':>5s} "
                     f"{n_uv:>5d} {n_lm:>5d} {umat:>8s} "
                     f"{dispatch:<18s} {slot1_role:<16s} {lm_bind:>7s}")

    lines.append('-' * 160)
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
#  Shader sources
# ─────────────────────────────────────────────────────────────────────────────


__all__ = tuple(name for name in globals() if not name.startswith("__"))
