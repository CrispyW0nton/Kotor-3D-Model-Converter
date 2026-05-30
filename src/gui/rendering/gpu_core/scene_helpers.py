from __future__ import annotations

from .renderer import *  # noqa: F401,F403
def _compute_model_bounds(model) -> dict:
    """
    D20-M: Walk all renderable mesh nodes and return the world-space AABB,
    using the per-node vertex_space contract (same as _build_vbo_data).

    Returns dict with keys: min_x, max_x, min_y, max_y, min_z, max_z,
    center_x/y/z, extent_x/y/z, max_extent, radius.
    Falls back to the model's stored bb_min/bb_max if no vertex data is found.

    No centroid heuristics, no _WORLDSPACE_THRESHOLD, no accessory detection.
    References:
      xoreos model_kotor.cpp readMesh — verts are node-local
      KotOR.js OdysseyModel3D.ts      — matrixWorld for GPU transform
    """
    # Detect module/area/tile models for renderable no-UV geometry.
    _bounds_model_cls  = (str(getattr(model, 'classification', 'character') or 'character')).lower()
    _bounds_model_type_raw = getattr(model, 'model_type', None)
    _bounds_model_type = int(_bounds_model_type_raw) if _bounds_model_type_raw is not None else 4
    _bounds_is_module  = (_bounds_model_cls in ('effect', 'tile', 'other') or
                          _bounds_model_type in (0, 2))

    all_pts = []

    _all_nodes_fn = getattr(model, 'all_nodes', None)
    nodes = list(_all_nodes_fn()) if _all_nodes_fn else getattr(model, 'nodes', [])

    for node in nodes:
        verts = getattr(node, 'vertices', None) or []
        if not verts:
            continue
        uvs = getattr(node, 'uvs', []) or []
        has_uvs = bool(uvs)

        # Skip deformation-helper nodes (same rules as _is_deform_helper)
        if not has_uvs and not _bounds_is_module:
            continue
        if node.name.lower().endswith(('_g', '_g0', '_dum')):
            continue
        try:
            import numpy as _np
            v_arr = _np.array(verts, dtype=np.float64)
        except Exception:
            continue

        # D20-M: Use vertex_space contract — no centroid checks
        _node_vs = getattr(node, 'vertex_space', 0)  # default NODE_LOCAL

        if _node_vs == 0:  # NODE_LOCAL — apply full world transform
            try:
                wt = node.world_transform()
                wp = np.array(wt[0], dtype=np.float64)
                wo = np.array(wt[1], dtype=np.float64)
                qlen = np.linalg.norm(wo)
                if qlen > 1e-9:
                    wo = wo / qlen
                is_id_rot = (abs(wo[3]) > 0.9999 and
                             abs(wo[0]) < 1e-6 and
                             abs(wo[1]) < 1e-6 and
                             abs(wo[2]) < 1e-6)
                if not is_id_rot:
                    v_arr = _quat_rotate_batch(wo, v_arr)
                v_arr = v_arr + wp
            except Exception:
                pass
        elif _node_vs == 1:  # WORLD — already in world space, use as-is
            pass
        # _node_vs == 2 (AABB_WALK) — skip walkmesh
        elif _node_vs == 2:
            continue

        all_pts.append(v_arr)

    if all_pts:
        all_v = np.vstack(all_pts)
        mn_x, mn_y, mn_z = float(all_v[:, 0].min()), float(all_v[:, 1].min()), float(all_v[:, 2].min())
        mx_x, mx_y, mx_z = float(all_v[:, 0].max()), float(all_v[:, 1].max()), float(all_v[:, 2].max())
    else:
        # Fall back to stored model bounds
        bb_min = getattr(model, 'bb_min', (-1, -1, -1)) or (-1, -1, -1)
        bb_max = getattr(model, 'bb_max', ( 1,  1,  1)) or ( 1,  1,  1)
        mn_x, mn_y, mn_z = float(bb_min[0]), float(bb_min[1]), float(bb_min[2])
        mx_x, mx_y, mx_z = float(bb_max[0]), float(bb_max[1]), float(bb_max[2])

    cx = (mn_x + mx_x) * 0.5
    cy = (mn_y + mx_y) * 0.5
    cz = (mn_z + mx_z) * 0.5
    ext_x = mx_x - mn_x
    ext_y = mx_y - mn_y
    ext_z = mx_z - mn_z
    max_ext = max(ext_x, ext_y, ext_z, 0.01)
    radius  = math.sqrt(ext_x**2 + ext_y**2 + ext_z**2) * 0.5

    return {
        'min_x': mn_x, 'max_x': mx_x,
        'min_y': mn_y, 'max_y': mx_y,
        'min_z': mn_z, 'max_z': mx_z,
        'center_x': cx, 'center_y': cy, 'center_z': cz,
        'extent_x': ext_x, 'extent_y': ext_y, 'extent_z': ext_z,
        'max_extent': max_ext,
        'radius': radius,
    }


def _apply_txi_from_textures_to_model(model, textures: dict) -> None:
    """
    Apply TXI metadata extracted from texture sources to model nodes.

    KotOR TPC files embed TXI metadata (blending mode, env map, etc.) as an
    ASCII trailer after the pixel data.  The MDL binary parser does not read
    these TPC-embedded TXI strings — it only processes standalone .txi files.
    This function bridges that gap by extracting TXI from available TPC bytes
    and applying the metadata to all mesh nodes that use each texture.

    Typical usage: call before GPU rendering when the TPC raw bytes are
    available in the 'textures' dict (as PIL Images with _txi_str attribute
    set by a TPC-aware loader, or via the viewport's TXI cache).

    When textures dict contains PIL.Image objects without TXI attributes,
    this function is a no-op (no TXI metadata available to apply).

    This fixes: creature meshes using DXT5 textures with 'blending 2' TXI
    (punchthrough alpha) so that hair, fur edges, and eye cutouts render
    correctly.  Without this fix, txi_blending stays 0 and the shader
    forces final_alpha=1.0 for all fragments, making the DXT5 alpha channel
    (which encodes the cut-out shape) invisible — resulting in solid-block
    hair/fur geometry ('teeth on the rail' artefact).
    """
    if not textures:
        return
    _extract_txi_from_tpc = None
    _parse_txi_string = None
    _apply_txi_to_node = None
    for _import_path in ('src.gui.viewports.frame_renderer', 'src.gui.qt_lib.viewports.frame_renderer'):
        try:
            import importlib as _il
            _m = _il.import_module(_import_path)
            _extract_txi_from_tpc = getattr(_m, '_extract_txi_from_tpc', None)
            _parse_txi_string     = getattr(_m, '_parse_txi_string', None)
            _apply_txi_to_node    = getattr(_m, '_apply_txi_to_node', None)
            if _extract_txi_from_tpc and _parse_txi_string and _apply_txi_to_node:
                break
        except ImportError:
            pass
    _have_txi_tools = bool(_extract_txi_from_tpc and _parse_txi_string and _apply_txi_to_node)

    if not _have_txi_tools:
        return

    # Build tex_name → TXI string and alpha_test mappings from available sources.
    # FIX-ALPHATEST: Also capture per-texture alpha_test from TPC header (bytes 4-7).
    # The TPC header field at offset 4 stores the engine's intended alpha-test
    # threshold for punchthrough blending (e.g. 0.9333 for c_bantha01, 0.7176 for
    # c_banthh01).  _load_tpc_bytes() now sets img._txi_alpha_test from this field;
    # we read it here and pass it to _apply_txi_to_node() so the shader receives the
    # correct threshold instead of the generic 0.5 default.
    _txi_cache: dict = {}
    _at_cache: dict  = {}   # tex_name → float alpha_test (from TPC header)
    for tex_name, tex_obj in textures.items():
        # Collect alpha_test from image attribute (set by _load_tpc_bytes)
        _img_at = getattr(tex_obj, '_txi_alpha_test', None)
        if _img_at is not None:
            try:
                _at_v = float(_img_at)
                if 0.0 < _at_v <= 1.0:
                    _at_cache[tex_name] = _at_v
            except (TypeError, ValueError):
                pass

        if tex_name in _txi_cache:
            continue
        # Option 1: PIL Image has _txi_str attribute set by a TPC-aware loader
        txi_str = getattr(tex_obj, '_txi_str', None)
        if txi_str:
            _txi_cache[tex_name] = txi_str
            continue
        # Option 2: PIL Image has _tpc_raw attribute (raw TPC bytes)
        raw = getattr(tex_obj, '_tpc_raw', None)
        if raw:
            try:
                txi_str = _extract_txi_from_tpc(raw)
                if txi_str:
                    _txi_cache[tex_name] = txi_str
                # Also try to read alpha_test from raw TPC header if not already set
                if tex_name not in _at_cache and len(raw) >= 8:
                    import struct as _st
                    _at_v = _st.unpack_from('<f', raw, 4)[0]
                    if 0.0 < _at_v <= 1.0:
                        _at_cache[tex_name] = _at_v
            except Exception:
                pass

    # Apply TXI and alpha_test to each mesh node.
    # NOTE: We apply even when _txi_cache is empty — nodes still need txi_alpha_test
    # set from the TPC header for correct punchthrough threshold on hair/fur meshes.
    #
    # FIX-MULTITEX-TXI: Also apply TXI for ALL texture_names entries, not just
    # the primary node.texture.  Multi-texture nodes (tex_count > 1) may have
    # secondary textures with TXI metadata (punchthrough, env-map, etc.) that
    # must be applied to the node for correct rendering of each material slot.
    try:
        all_nodes_fn = getattr(model, 'all_nodes', None)
        nodes = list(all_nodes_fn()) if all_nodes_fn else getattr(model, 'nodes', [])
        for node in nodes:
            if not getattr(node, 'is_mesh', False):
                continue
            # Collect all texture names used by this node
            _all_tex_names = set()
            tex_name = str(getattr(node, 'texture', '') or '').strip().lower()
            if tex_name and tex_name not in ('null', '', 'none'):
                _all_tex_names.add(tex_name)
            # Also include all entries from texture_names[]
            for _tn in getattr(node, 'texture_names', []):
                _tn_clean = str(_tn or '').strip().lower()
                if _tn_clean and _tn_clean not in ('null', '', 'none'):
                    _all_tex_names.add(_tn_clean)

            if not _all_tex_names:
                continue

            # Apply TXI from primary texture first (most important)
            _primary_txi = _txi_cache.get(tex_name, '') if tex_name else ''
            _primary_at = _at_cache.get(tex_name,
                                         float(getattr(node, 'txi_alpha_test', 0.5)))
            if _primary_txi or _primary_at != 0.5:
                try:
                    _apply_txi_to_node(node, _primary_txi, _primary_at)
                except Exception:
                    pass

            # Apply TXI from secondary textures (env-map, bump, specular, etc.)
            # These may set txi_envmaptexture, txi_bumpmaptexture, etc.
            for _sec_name in _all_tex_names:
                if _sec_name == tex_name:
                    continue  # already applied above
                _sec_txi = _txi_cache.get(_sec_name, '')
                if _sec_txi:
                    try:
                        # Apply secondary TXI but keep the primary alpha_test
                        _apply_txi_to_node(node, _sec_txi,
                                           float(getattr(node, 'txi_alpha_test', 0.5)))
                    except Exception:
                        pass
    except Exception as e:
        log.debug(f'_apply_txi_from_textures_to_model error: {e}')


class _CompositeModel:
    """
    Lightweight wrapper that merges two KotorModel objects for combined rendering.

    FIX-SUPERMODEL-BODY: KotOR head-only models (ad_saul, comm_b_f, etc.) store
    only the head mesh.  The body geometry lives in their supermodel
    (e.g. N_AdmrlSaulKar).  Ghost Rigger renders models standalone, so the body
    is normally absent.

    This wrapper combines ``head_model.all_nodes()`` and ``body_model.all_nodes()``
    into a single iterable, while forwarding all other attributes to head_model so
    the GPU renderer sees a single coherent model object.

    Body nodes are tagged with ``_model_ref = body_model`` so that
    ``_build_vbo_data`` can apply the correct world-space treatment (body skin
    meshes are already in world space → no extra transform).
    The head nodes keep their original ``_model_ref`` (or are tagged to head_model)
    so the accessory-skin transform heuristic still applies correctly.

    Bounding-box attributes (bb_min, bb_max, radius) are expanded to cover both
    models so ``_compute_model_bounds`` can fall back to them if no vertex data
    is available.
    """

    def __init__(self, head_model, body_model):
        self._head = head_model
        self._body = body_model

        # Expand stored AABB to cover both models
        def _bb(m, attr, default):
            v = getattr(m, attr, None)
            return v if v is not None else default

        h_min = _bb(head_model, 'bb_min', (-1, -1, -1))
        h_max = _bb(head_model, 'bb_max', ( 1,  1,  1))
        b_min = _bb(body_model, 'bb_min', (-1, -1, -1))
        b_max = _bb(body_model, 'bb_max', ( 1,  1,  1))
        self.bb_min = (min(h_min[0], b_min[0]), min(h_min[1], b_min[1]), min(h_min[2], b_min[2]))
        self.bb_max = (max(h_max[0], b_max[0]), max(h_max[1], b_max[1]), max(h_max[2], b_max[2]))
        dx = self.bb_max[0] - self.bb_min[0]
        dy = self.bb_max[1] - self.bb_min[1]
        dz = self.bb_max[2] - self.bb_min[2]
        import math as _math
        self.radius = _math.sqrt(dx*dx + dy*dy + dz*dz) * 0.5

        # FIX-NONSKIN-OFFSET: Compute the offset to apply to non-skin nodes from
        # the head accessory model so they render at their correct world positions
        # (i.e., at the head bone's position in the body skeleton, not at the
        # model-root's local position).
        #
        # Method: find a shared skeleton bone name that appears in BOTH models
        # (e.g. 'head_g', 'Hturn_g') and compute:
        #   offset = body_bone_world_pos - head_bone_world_pos
        # Then any non-skin head node's world_pos is corrected by adding this offset.
        #
        # If no shared bone is found, fall back to offset = (0,0,0) (no correction).
        self._nonskin_head_offset = (0.0, 0.0, 0.0)
        try:
            # Candidate anchor bone names in priority order
            _ANCHOR_BONES = ('head_g', 'Hturn_g', 'neck_g', 'necklwr_g', 'headhook')

            # Build name → world_pos maps for both models
            _body_bones: dict = {}
            _body_all = list(body_model.all_nodes()) if hasattr(body_model,'all_nodes') else list(getattr(body_model,'nodes',[]))
            for _bn in _body_all:
                try:
                    _bwp, _ = _bn.world_transform()
                    _body_bones[_bn.name.lower()] = _bwp
                except Exception:
                    pass

            _head_bones: dict = {}
            _head_all = list(head_model.all_nodes()) if hasattr(head_model,'all_nodes') else list(getattr(head_model,'nodes',[]))
            for _hn in _head_all:
                try:
                    _hwp, _ = _hn.world_transform()
                    _head_bones[_hn.name.lower()] = _hwp
                except Exception:
                    pass

            # Find the best matching anchor bone
            for _anchor in _ANCHOR_BONES:
                _bwp = _body_bones.get(_anchor)
                _hwp = _head_bones.get(_anchor)
                if _bwp is not None and _hwp is not None:
                    self._nonskin_head_offset = (
                        float(_bwp[0]) - float(_hwp[0]),
                        float(_bwp[1]) - float(_hwp[1]),
                        float(_bwp[2]) - float(_hwp[2]),
                    )
                    log.debug(f"_CompositeModel: anchor bone '{_anchor}' "
                              f"body={tuple(round(x,3) for x in _bwp)} "
                              f"head={tuple(round(x,3) for x in _hwp)} "
                              f"offset={tuple(round(x,3) for x in self._nonskin_head_offset)}")
                    break
        except Exception as _e:
            log.debug(f"_CompositeModel: could not compute non-skin offset: {_e}")

    # Forward scalar model attributes to the head model
    def __getattr__(self, name):
        return getattr(self._head, name)

    def all_nodes(self):
        """Return head nodes first, then body nodes (for correct depth ordering)."""
        head_nodes = []
        _h_fn = getattr(self._head, 'all_nodes', None)
        if _h_fn:
            head_nodes = list(_h_fn())
        else:
            head_nodes = list(getattr(self._head, 'nodes', []))

        body_nodes = []
        _b_fn = getattr(self._body, 'all_nodes', None)
        if _b_fn:
            body_nodes = list(_b_fn())
        else:
            body_nodes = list(getattr(self._body, 'nodes', []))

        # Tag each body node so _build_vbo_data uses the correct model context
        for _bn in body_nodes:
            try:
                _bn._model_ref = self._body
            except (AttributeError, TypeError):
                pass

        # Tag each head node with:
        # - _model_ref = head model (for accessory-skin detection)
        # - _composite_nonskin_offset = world-space offset to apply to non-skin
        #   nodes so they render at the correct position in the body skeleton
        #   (= body_head_g_world - head_head_g_local)
        _off = self._nonskin_head_offset
        for _hn in head_nodes:
            try:
                _hn._model_ref = self._head
            except (AttributeError, TypeError):
                pass
            try:
                _hn._composite_nonskin_offset = _off
            except (AttributeError, TypeError):
                pass

        return head_nodes + body_nodes

    @property
    def nodes(self):
        return self.all_nodes()


# Base skeleton names (models that ARE the skeleton, not head accessories).
# Re-export the canonical constant from core.model_data for use by callers
# that import this module (kept for backwards-compatibility).
_BASE_SKELETONS: frozenset = _KOTOR_BASE_SKELETONS


def render_model_autoframe(
        model,
        W: int = 512,
        H: int = 512,
        textures: Optional[Dict[str, 'Image.Image']] = None,
        anim_pose=None,
        views: Optional[list] = None,
        fov: float = 45.0,
        renderer: Optional['GpuRenderer'] = None,
        supermodel_body=None,
        supermodel_textures: Optional[Dict[str, 'Image.Image']] = None,
) -> Dict[str, 'Image.Image']:
    """
    Render a KotOR model from multiple angles with an automatically computed
    camera that frames the entire model within the viewport.

    Parameters
    ----------
    model              : KotorModel (from MDLBinaryParser)
    W, H               : output image size in pixels
    textures           : dict of {name: PIL.Image} texture maps
    anim_pose          : optional AnimPose object
    views              : list of view names to render; defaults to
                         ['front', 'back', 'right', 'left', 'top', 'diag']
    fov                : camera field-of-view in degrees (default 45)
    renderer           : existing GpuRenderer to reuse (creates a new one if None)
    supermodel_body    : KotorModel for the supermodel body (e.g. N_AdmrlSaulKar
                         for ad_saul).  When provided the head model is composited
                         onto the body model for rendering.
    supermodel_textures: additional texture dict for the supermodel body textures

    Returns
    -------
    dict mapping view name → PIL.Image (RGBA)

    Camera placement
    ----------------
    KotOR uses Y-forward, Z-up.  Character/creature models face toward +Y
    (the creature's face is at the +Y end of its bounding box and the
    forward movement direction is +Y — i.e. nose/eyes point toward +Y).
    - 'front'  : camera at +Y looking toward -Y  → creature face visible
    - 'back'   : camera at -Y looking toward +Y  → creature rear/tail visible
    - 'right'  : camera at +X looking toward -X  → model right profile
    - 'left'   : camera at -X looking toward +X  → model left profile
    - 'top'    : camera straight above looking down
    - 'diag'   : 3/4 view (front-right-top), creature face visible

    FIX-LABEL: Previous versions had front/back offsets swapped (+Y/-Y),
    causing the 'front' view to show the creature's rear and vice-versa.
    Corrected to match render_stills_v12 convention (front = camera at +Y).

    Framing
    -------
    The camera distance includes both the perpendicular extent (to fit the
    model in the FOV) and the depth half-extent along the viewing axis (to
    push the camera back far enough that the nearest model face is not
    over-magnified by perspective projection).
    """
    if views is None:
        views = ['front', 'back', 'right', 'left', 'top', 'diag']

    # FIX-TXI-AUTOFRAME: Apply TXI metadata from TPC raw bytes to model nodes.
    # The MDL binary parser does not read TXI data embedded in TPC texture files.
    # When tpc_bytes dict is provided, extract TXI from each TPC and update node
    # fields (txi_blending, txi_alpha_test, txi_envmaptexture, etc.) so the GPU
    # renderer uses correct blend modes (e.g. 'blending 2' punchthrough for hair).
    if textures is not None:
        _apply_txi_from_textures_to_model(model, textures)

    # FIX-SUPERMODEL-BODY: If a supermodel body was supplied, create a composite
    # model that renders both the body and the head together.  This fixes head-only
    # models like ad_saul (supermodel = N_AdmrlSaulKar) and comm_b_f
    # (supermodel = S_Female03) that only contain the head mesh; without this the
    # render shows only a floating head with no body.
    #
    # The combined texture dict merges both head and body textures.
    _render_model = model
    _render_textures = dict(textures) if textures else {}
    if supermodel_body is not None:
        try:
            _render_model = _CompositeModel(model, supermodel_body)
            if supermodel_textures:
                _render_textures.update(supermodel_textures)
            if supermodel_textures is not None:
                _apply_txi_from_textures_to_model(supermodel_body, supermodel_textures)
            log.debug(f"render_model_autoframe: compositing head '{getattr(model,'name','?')}' "
                      f"onto body '{getattr(supermodel_body,'name','?')}'")
        except Exception as _e:
            log.warning(f"render_model_autoframe: supermodel composite failed: {_e}")
            _render_model = model

    bounds = _compute_model_bounds(_render_model)
    cx = bounds['center_x']
    cy = bounds['center_y']
    cz = bounds['center_z']
    max_ext = bounds['max_extent']

    # Per-axis extents – use per-axis distance so the camera is tight on each axis.
    ext_x = bounds['extent_x']
    ext_y = bounds['extent_y']
    ext_z = bounds['extent_z']

    half_fov_rad = math.radians(fov * 0.5)
    tan_hfov = math.tan(half_fov_rad)

    # Per-axis half-extents from bounding-box centre.
    half_x = ext_x * 0.5
    half_y = ext_y * 0.5
    half_z = ext_z * 0.5

    def _axis_dist(perp_ext: float, depth_half: float = 0.0) -> float:
        """Return camera-to-centre distance so that the model fits in the FOV.

        perp_ext   : full extent perpendicular to the view axis (width or height
                     of the model face visible from this camera direction).
        depth_half : half-extent *along* the view axis (half the model depth).
                     The camera must be placed at least this far from the centre
                     so it does not clip through the nearest model face, and the
                     near face must also fit entirely within the FOV.

        The formula uses two constraints and takes the max:
          1. FOV fit at the near face: cam_dist ≥ (perp_half / tan_hfov) + depth_half
             — guarantees that geometry at the near model face does not exceed
               the viewport edges (no clipping of horns, protruding parts, etc.).
          2. FOV fit at the centre: cam_dist ≥ (perp_half * 1.10) / tan_hfov
             — for shallow models where near-face clearance alone would push the
               camera further than needed.

        A 10 % margin (factor 1.10) leaves ~9 % padding around the model edges.
        """
        perp_half = perp_ext * 0.5
        # Constraint 1: near-face clears the FOV (exact mathematical minimum)
        near_face_min = perp_half / tan_hfov + depth_half
        # Constraint 2: centre-based FOV fit with 10% breathing room
        centre_fit = (perp_half * 1.10) / tan_hfov
        return max(near_face_min, centre_fit) + max_ext * 0.03

    # Per-view camera: (eye_offset_from_center, up_vector)
    # FIX-LABEL: KotOR creatures face +Y (nose/eyes at +Y end of bounding box).
    # Camera must be placed at +Y to look back toward -Y and see the face.
    #   'front': camera at +Y → looks toward -Y → sees creature face
    #   'back' : camera at -Y → looks toward +Y → sees creature rear/tail
    #   'right': camera at +X → right profile
    #   'left' : camera at -X → left profile
    #   'top'  : camera above (+Z) looking down
    #   'diag' : 3/4 front-right-top diagonal (face visible)
    _view_defs = {
        'front' : {'offset': ( 0,  +_axis_dist(max(ext_x, ext_z), half_y), 0),  'up': (0, 0, 1)},
        'back'  : {'offset': ( 0,  -_axis_dist(max(ext_x, ext_z), half_y), 0),  'up': (0, 0, 1)},
        'right' : {'offset': (+_axis_dist(max(ext_y, ext_z), half_x),  0, 0),   'up': (0, 0, 1)},
        'left'  : {'offset': (-_axis_dist(max(ext_y, ext_z), half_x),  0, 0),   'up': (0, 0, 1)},
        'top'   : {'offset': ( 0,  0, +_axis_dist(max(ext_x, ext_y), half_z)),  'up': (0, 1, 0)},
        'diag'  : {'offset': (+_axis_dist(max_ext, 0)*0.6, +_axis_dist(max_ext, 0)*0.6,
                               +_axis_dist(max_ext, 0)*0.3),                    'up': (0, 0, 1)},
    }

    _renderer = renderer or GpuRenderer()
    results: Dict[str, 'Image.Image'] = {}

    for view_name in views:
        if view_name not in _view_defs:
            log.warning(f"render_model_autoframe: unknown view '{view_name}', skipping")
            continue
        vdef = _view_defs[view_name]
        ox, oy, oz = vdef['offset']
        eye = (cx + ox, cy + oy, cz + oz)
        target = (cx, cy, cz)
        up = vdef['up']

        cam_dist = math.sqrt(ox**2 + oy**2 + oz**2)

        camera = type('_AutoCam', (), {
            'eye':    eye,
            'target': target,
            'up':     up,
            'fov':    fov,
            'near':   max_ext * 0.005,
            'far':    cam_dist * 5.0 + max_ext * 2.0,
        })()

        img = _renderer.render(_render_model, camera, W, H,
                               textures=_render_textures, anim_pose=anim_pose)
        if img:
            results[view_name] = img

    if renderer is None:
        _renderer.release()

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Triangle throughput benchmark
# ─────────────────────────────────────────────────────────────────────────────


__all__ = tuple(name for name in globals() if not name.startswith("__"))
