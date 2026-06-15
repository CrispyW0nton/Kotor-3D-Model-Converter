"""RendererGeometryMixin methods for the viewport frame renderer."""

from __future__ import annotations

from .mixin_imports import (
    DanglySimulator,
    Dict,
    List,
    Optional,
    Tuple,
    _MatrixPaletteUploader,
    _NUMPY,
    _SKIN_MAX_BONES,
    _clamp,
    _compute_screen_size_ratio,
    _cross,
    _gr_probe,
    _normalize,
    _quat_rotate,
    _sub,
    log,
    math,
    np,
)


class RendererGeometryMixin:
    def _face_normal(v0, v1, v2):
        e1 = _sub(v1, v0)
        e2 = _sub(v2, v0)
        return _normalize(_cross(e1, e2))

    @staticmethod
    def _compute_area_weighted_normals(
        faces: list, world_verts: list
    ) -> list:
        """
        Compute per-vertex normals via area-weighted face-normal accumulation.

        Inspired by UE5's SkeletalMesh normal recomputation:  each face
        contributes to its three vertices with a weight equal to the triangle's
        area (‖e1 × e2‖ / 2).  Larger triangles therefore dominate the vertex
        normal, which produces smoother lighting gradients on curved surfaces
        compared to plain averaging.

        Returns a list of (nx, ny, nz) tuples, one per world-space vertex.
        Falls back to (0, 1, 0) for degenerate vertices with zero accumulated
        weight.  Only uses faces whose vertex indices are within bounds.

        UE reference: SkeletalRenderCPUSkin.cpp – SkinVertices, tangent
        accumulation loops (lines ~750-880 in the analysed source).
        """
        nv = len(world_verts)
        if nv == 0 or not faces:
            return []

        accum = [[0.0, 0.0, 0.0] for _ in range(nv)]

        for face in faces:
            if len(face) < 3:
                continue
            i0, i1, i2 = face[0], face[1], face[2]
            if i0 >= nv or i1 >= nv or i2 >= nv:
                continue
            # Skip degenerate faces with repeated vertex indices
            if i0 == i1 or i1 == i2 or i0 == i2:
                continue
            v0 = world_verts[i0]
            v1 = world_verts[i1]
            v2 = world_verts[i2]
            # Unweighted cross product — its magnitude equals twice the
            # triangle area, so this IS the area-weighted normal.
            e1x = v1[0]-v0[0]; e1y = v1[1]-v0[1]; e1z = v1[2]-v0[2]
            e2x = v2[0]-v0[0]; e2y = v2[1]-v0[1]; e2z = v2[2]-v0[2]
            cx = e1y*e2z - e1z*e2y
            cy = e1z*e2x - e1x*e2z
            cz = e1x*e2y - e1y*e2x
            accum[i0][0] += cx; accum[i0][1] += cy; accum[i0][2] += cz
            accum[i1][0] += cx; accum[i1][1] += cy; accum[i1][2] += cz
            accum[i2][0] += cx; accum[i2][1] += cy; accum[i2][2] += cz

        result = []
        for a in accum:
            ax, ay, az = a
            length = math.sqrt(ax*ax + ay*ay + az*az)
            if length > 1e-9:
                result.append((ax/length, ay/length, az/length))
            else:
                result.append((0.0, 1.0, 0.0))
        return result

    def _node_world_transform(self, node: 'ModelNode'):
        """
        Return (wp, wo, is_identity_rot) for ``node`` with per-frame caching.

        Conventions (audited Phase G1 against xoreos + KotorBlender + KotOR.js)
        ──────────────────────────────────────────────────────────────────────
        * Quaternion order is ``[x, y, z, w]`` (see ``_quat_mul`` /
          ``_quat_rotate`` in ``model_data.py``).
        * Composition is the standard SRT parent chain:
              world = world(parent) ⋅ T(local_pos) ⋅ R(local_rot)
          implemented in quaternion form as
              wp_child = wp_parent + rotate(wo_parent, local_pos_child)
              wo_child = wo_parent ⊗ local_rot_child
          which corresponds to xoreos ``ModelNode::computeTransforms`` and
          KotOR.js ``OdysseyModel3D.updateMatrixWorld``.
        * The walk is iterative (root→leaf) with a ``_visited_chain`` cycle
          guard for malformed MDLs.
        * When ``self._anim_pose is not None`` the animated position /
          rotation from ``AnimPose.nodes[name.lower()]`` is substituted for
          every node that has a pose entry; nodes without keyframes keep
          their bind-pose local transform.  This is critical — a leaf bone
          with no keyframes must still re-accumulate if its *parent* moved.
        * Non-leaf parent rotations go through ``_quat_normalize_bind`` which
          collapses the NWN X-axis 180° coord-flip quaternion ``[1,0,0,0]``
          to identity.  Actual animation keyframes don't match that exact
          pattern, so they're preserved unchanged.
        * Results are cached in ``self._wt_cache`` keyed by ``id(node)``.
          The cache is cleared in ``set_animation_pose`` and ``set_model``
          so pose changes always re-evaluate.
        """
        nid = id(node)
        cached = self._wt_cache.get(nid)
        if cached is not None:
            return cached
        import math as _math
        try:
            from src.core.geometry.model_data import (_quat_rotate as _qr, _quat_normalize_bind,
                                           _quat_normalize, _quat_mul)
        except ImportError:
            from core.geometry.model_data import (_quat_rotate as _qr, _quat_normalize_bind,  # type: ignore
                                         _quat_normalize, _quat_mul)

        bas_root = self._bas_attachment_root_for_node(node)
        if bas_root is not None:
            result = self._bas_attachment_world_transform(node, bas_root, _qr, _quat_normalize_bind, _quat_normalize, _quat_mul)
            self._wt_cache[nid] = result
            return result

        if self._anim_pose is not None:
            # Always walk the full ancestor chain when a pose is active.
            # Substitute animated values for nodes that have pose entries;
            # use bind-pose local transform for nodes that don't.
            chain = []
            n = node
            _visited_chain: set = set()
            while n is not None:
                nid_c = id(n)
                if nid_c in _visited_chain or len(chain) > 512:
                    break  # cycle guard for corrupted MDL data
                _visited_chain.add(nid_c)
                chain.append(n)
                n = n.parent
            chain.reverse()

            wx, wy, wz = 0.0, 0.0, 0.0
            parent_orientation = [0.0, 0.0, 0.0, 1.0]
            last_i = len(chain) - 1

            for ci, chain_node in enumerate(chain):
                is_leaf = (ci == last_i)
                pn = self._anim_pose.nodes.get(chain_node.name.lower())
                if pn:
                    lx, ly, lz = pn.position
                    # NaN guard: fall back to bind-pose position if animated value is non-finite
                    if not (_math.isfinite(lx) and _math.isfinite(ly) and _math.isfinite(lz)):
                        lx, ly, lz = chain_node.position
                    rot = list(pn.rotation)
                    # NaN guard on rotation
                    if not all(_math.isfinite(v) for v in rot):
                        rot = list(chain_node.rotation)
                    # Parent nodes in the chain (non-leaf): apply _quat_normalize_bind
                    # to collapse the NWN X-axis 180° coord-flip rotation to identity,
                    # exactly as the bind-pose path does.  This is critical: the root
                    # node often carries [1,0,0,0] (180° about X) in both its bind pose
                    # AND in the animation pose (since there's no keyframe that changes
                    # it).  Without collapsing it here, all descendant positions are
                    # rotated 180° around X during animation, causing the mesh to
                    # invert/explode.  _quat_normalize_bind only collapses PURE X-axis
                    # 180° rotations — actual animation keyframes produce rotations that
                    # won't match this pattern, so they are preserved unchanged.
                    #
                    # Leaf node: preserve the actual rotation for vertex transform
                    # (used to orient the mesh node in world space).
                    if not is_leaf:
                        node_rot = _quat_normalize_bind(rot)
                    else:
                        l2 = rot[0]*rot[0]+rot[1]*rot[1]+rot[2]*rot[2]+rot[3]*rot[3]
                        if l2 > 1e-9:
                            l = _math.sqrt(l2)
                            rot = [rot[0]/l, rot[1]/l, rot[2]/l, rot[3]/l]
                        node_rot = rot
                else:
                    lx, ly, lz = chain_node.position
                    rot = list(chain_node.rotation)
                    # Bind-pose parent nodes: collapse 180°-about-axis NWN convention
                    # Leaf node: preserve actual rotation for vertex transform
                    if is_leaf:
                        node_rot = _quat_normalize(rot)
                    else:
                        node_rot = _quat_normalize_bind(rot)

                rx, ry, rz = _qr(parent_orientation, (lx, ly, lz))
                wx += rx; wy += ry; wz += rz
                parent_orientation = _quat_mul(parent_orientation, node_rot)

            # Explosion guard: if accumulated world position is non-finite or
            # unreasonably large, fall back to the bind-pose transform.  This
            # catches bad animation keyframes that produce runaway positions.
            if not (_math.isfinite(wx) and _math.isfinite(wy) and _math.isfinite(wz)):
                wp_b, wo_b = node.world_transform()
                wo_rot_b = _math.sqrt(wo_b[0]*wo_b[0] + wo_b[1]*wo_b[1] + wo_b[2]*wo_b[2])
                result = (wp_b, wo_b, wo_rot_b < 0.001)
                self._wt_cache[nid] = result
                return result

            wp = (wx, wy, wz)
            wo = tuple(parent_orientation)
            # Ensure orientation quaternion is unit-length (guards against
            # accumulated float error across long parent chains)
            wo_len2 = wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2] + wo[3]*wo[3]
            if wo_len2 > 1e-9 and abs(wo_len2 - 1.0) > 1e-4:
                _s = 1.0 / _math.sqrt(wo_len2)
                wo = (wo[0]*_s, wo[1]*_s, wo[2]*_s, wo[3]*_s)
            wo_rot = _math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
            is_id  = (wo_rot < 0.001)
            result = (wp, wo, is_id)
            self._wt_cache[nid] = result
            return result

        # Default: bind pose (no animation active)
        wp, wo = node.world_transform()
        wo_rot = _math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
        is_id  = (wo_rot < 0.001)
        result = (wp, wo, is_id)
        self._wt_cache[nid] = result
        return result

    @staticmethod
    def _bas_attachment_root_for_node(node):
        current = node
        visited = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            if bool(getattr(current, "_gr_bas_attachment_root", False)):
                return current
            current = getattr(current, "parent", None)
        return None

    def _bas_attachment_socket_node(self, bas_root):
        socket_name = str(getattr(bas_root, "_gr_bas_socket_name", "") or "").lower()
        body_root = getattr(bas_root, "parent", None)
        if body_root is None or not socket_name:
            return None
        if str(getattr(body_root, "name", "") or "").lower() == socket_name:
            return body_root
        stack = [body_root]
        visited = {id(bas_root)}
        while stack:
            current = stack.pop()
            if current is None or id(current) in visited:
                continue
            visited.add(id(current))
            if str(getattr(current, "name", "") or "").lower() == socket_name:
                return current
            for child in reversed(getattr(current, "children", []) or []):
                if bool(getattr(child, "_gr_bas_attachment_root", False)):
                    continue
                stack.append(child)
        return None

    def _bas_attachment_world_transform(self, node, bas_root, _qr, _quat_normalize_bind, _quat_normalize, _quat_mul):
        socket = self._bas_attachment_socket_node(bas_root)
        if socket is not None:
            socket_wp, socket_wo, _ = self._node_world_transform(socket)
            wx, wy, wz = socket_wp
            parent_orientation = list(socket_wo)
        else:
            wx = wy = wz = 0.0
            parent_orientation = [0.0, 0.0, 0.0, 1.0]

        chain = []
        current = node
        visited = set()
        while current is not None:
            if id(current) in visited or len(chain) > 512:
                break
            visited.add(id(current))
            chain.append(current)
            if current is bas_root:
                break
            current = getattr(current, "parent", None)
        chain.reverse()
        last_i = len(chain) - 1
        for index, chain_node in enumerate(chain):
            is_leaf = index == last_i
            lx, ly, lz = getattr(chain_node, "position", (0.0, 0.0, 0.0))
            rot = list(getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0)))
            node_rot = _quat_normalize(rot) if is_leaf else _quat_normalize_bind(rot)
            rx, ry, rz = _qr(parent_orientation, (lx, ly, lz))
            wx += rx
            wy += ry
            wz += rz
            parent_orientation = _quat_mul(parent_orientation, node_rot)

        import math as _math

        wo = tuple(parent_orientation)
        wo_len2 = wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2] + wo[3]*wo[3]
        if wo_len2 > 1e-9 and abs(wo_len2 - 1.0) > 1e-4:
            scale = 1.0 / _math.sqrt(wo_len2)
            wo = (wo[0]*scale, wo[1]*scale, wo[2]*scale, wo[3]*scale)
        wo_rot = _math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
        return ((float(wx), float(wy), float(wz)), wo, wo_rot < 0.001)

    def _bas_attachment_local_transform(self, node, bas_root, _qr, _quat_normalize_bind, _quat_normalize, _quat_mul):
        wx = wy = wz = 0.0
        parent_orientation = [0.0, 0.0, 0.0, 1.0]
        chain = []
        current = node
        visited = set()
        while current is not None:
            if id(current) in visited or len(chain) > 512:
                break
            visited.add(id(current))
            chain.append(current)
            if current is bas_root:
                break
            current = getattr(current, "parent", None)
        chain.reverse()
        last_i = len(chain) - 1
        for index, chain_node in enumerate(chain):
            is_leaf = index == last_i
            lx, ly, lz = getattr(chain_node, "position", (0.0, 0.0, 0.0))
            rot = list(getattr(chain_node, "rotation", (0.0, 0.0, 0.0, 1.0)))
            node_rot = _quat_normalize(rot) if is_leaf else _quat_normalize_bind(rot)
            rx, ry, rz = _qr(parent_orientation, (lx, ly, lz))
            wx += rx
            wy += ry
            wz += rz
            parent_orientation = _quat_mul(parent_orientation, node_rot)

        import math as _math

        wo = tuple(parent_orientation)
        wo_len2 = wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2] + wo[3]*wo[3]
        if wo_len2 > 1e-9 and abs(wo_len2 - 1.0) > 1e-4:
            scale = 1.0 / _math.sqrt(wo_len2)
            wo = (wo[0]*scale, wo[1]*scale, wo[2]*scale, wo[3]*scale)
        wo_rot = _math.sqrt(wo[0]*wo[0] + wo[1]*wo[1] + wo[2]*wo[2])
        return ((float(wx), float(wy), float(wz)), wo, wo_rot < 0.001)

    @staticmethod
    def _apply_vertex_transform(node: 'ModelNode', v, wp, wo, is_identity_rot: bool):
        """
        Transform vertex v from node-local/bind-pose to world space.

        KotOR MDL vertex storage rules (verified empirically against full K1+K2 model set):
          - Skin nodes: vertices are stored in SKIN-NODE-LOCAL space.
            For models with identity skin-node rotation (most common), only add wp.
            For models with a non-identity rotation on the skin mesh node itself
            (e.g. p_bastilabb / p_bastilaba which carry a 180° X or Y rotation
            inherited from the NWN co-ordinate-flip exporter), the rotation MUST be
            applied before the translation so that vertices end up correctly oriented
            in world space.  Applying the rotation to identity-rotation nodes is
            a no-op (wo = (0,0,0,1) → _quat_rotate returns v unchanged), so the
            same branch is safe for both cases.
          - Non-skin (trimesh/dangly) + identity orientation → translate by wp only.
          - Non-skin + non-identity orientation → full world transform (rotate + translate).
        """
        if is_identity_rot:
            return (v[0] + wp[0], v[1] + wp[1], v[2] + wp[2])
        rx, ry, rz = _quat_rotate(wo, v)
        return (rx + wp[0], ry + wp[1], rz + wp[2])

    def _get_vertex_world(self, node: 'ModelNode', vi: int):
        """Get a vertex in world space using cached world transform."""
        v = node.vertices[vi]
        wp, wo, is_id = self._node_world_transform(node)
        return self._apply_vertex_transform(node, v, wp, wo, is_id)

    # ── Linear Blend Skinning (animated mesh deformation) ─────────────

    def _build_bone_transforms(self, node: 'ModelNode') -> Optional[Dict]:
        """
        Build a dict mapping compact bone index → (bind_world_pos, bind_world_quat,
        anim_world_pos, anim_world_quat) for all bones in this skin node's bone_map.

        Also stores the skin node's own bind-pose world position under the special
        key -1 so _lbs_vertex can convert skin-local vertices to world space.

        PERFORMANCE: A shared per-pose name-keyed cache (_bone_transforms_by_name) holds
        the transform for every unique bone name in the model.  Each call for a skin node
        builds its compact-index dict by looking up names in that shared cache, so the
        expensive bind-pose/anim-pose passes run only ONCE per animation frame across all
        skin nodes, instead of once per skin node.

        Returns None if the node has no bone_map or no valid bones.
        """
        if not node.is_skin or not node.bone_map or not node.skin_data:
            return None

        model = self.model
        if model is None:
            return None

        # ── Per-pose shared cache keyed by bone NAME ─────────────────────
        # id() of the pose object changes on every animation tick (new AnimPose),
        # which correctly invalidates the cache each frame.
        pose_key = id(self._anim_pose) if self._anim_pose is not None else 0

        if (self._bone_transforms_cache is None or
                self._bone_transforms_pose_id != pose_key):
            # First call this frame: build the full name-keyed cache.
            self._bone_transforms_cache = {}   # name_lower → (bind_wp, bind_wo, anim_wp, anim_wo)
            self._bone_transforms_pose_id = pose_key

            # Build name → node map, preferring non-skin (bone/joint) nodes over
            # skin-mesh nodes when duplicate names exist.  KotOR models frequently
            # use the same name for a bone joint (non-skin, small vertex count or
            # no vertices) AND the deformable skin mesh it drives (e.g. "torso" is
            # both the joint and the 907-vertex skin mesh in N_sithpraet).  For LBS
            # we must reference the JOINT's world transform, not the skin mesh's.
            node_by_name: Dict[str, 'ModelNode'] = {}
            for n in model.all_nodes():
                key = n.name.lower()
                existing = node_by_name.get(key)
                if existing is None:
                    node_by_name[key] = n
                elif existing.is_skin and not n.is_skin:
                    # Replace skin mesh with the non-skin bone/joint node
                    node_by_name[key] = n
                # else: keep existing (first non-skin wins, or first if both skin)

            # Collect unique bone names across all skin nodes
            all_bone_names: set = set()
            for mn in model.all_nodes():
                if mn.is_skin and mn.bone_map:
                    for bname in mn.bone_map:
                        if bname:
                            all_bone_names.add(bname.lower())

            saved_pose = self._anim_pose

            # ── Pass 1: compute all bind-pose transforms ────────────────────
            # THREAD-SAFETY: Don't modify self._anim_pose or self._wt_cache here
            # because the main thread may call set_animation_pose() concurrently.
            # Instead, compute bind-pose transforms by calling _node_world_transform
            # with a temporarily overridden pose variable using a local approach.
            # We create a fresh local wt_cache for the bind pass so we don't
            # corrupt the per-frame cache used by the current animation pass.
            saved_anim_cache = dict(self._wt_cache)
            self._anim_pose = None   # switch to bind pose for Pass 1
            self._wt_cache = {}      # isolated cache for bind-pose pass

            bind_by_name: Dict[str, tuple] = {}
            for bname_lower in all_bone_names:
                bone_node = node_by_name.get(bname_lower)
                if bone_node is None:
                    continue
                wp, wo, _ = self._node_world_transform(bone_node)
                bind_by_name[bname_lower] = (wp, wo)

            # Restore animation pose and wt_cache for animated pass
            self._anim_pose = saved_pose
            self._wt_cache = saved_anim_cache

            # ── Pass 2: compute all animated transforms ─────────────────────
            for bname_lower, (bind_wp, bind_wo) in bind_by_name.items():
                bone_node = node_by_name.get(bname_lower)
                if bone_node is None:
                    continue
                anim_wp, anim_wo, _ = self._node_world_transform(bone_node)
                self._bone_transforms_cache[bname_lower] = (bind_wp, bind_wo, anim_wp, anim_wo)

        # ── Build this node's compact-index → transforms dict ──────────
        # Note: key -1 (skin node bind-pose world position) is no longer stored
        # here as a separate entry; _lbs_vertex reads skin_wp directly via
        # _node_world_transform(node) and adds it to v_local before LBS.
        bone_transforms: Dict = {}

        for bi, bone_name in enumerate(node.bone_map):
            if not bone_name:
                continue
            key = bone_name.lower()
            bt = self._bone_transforms_cache.get(key)
            if bt is not None:
                bone_transforms[bi] = bt

        return bone_transforms if bone_transforms else None

    def _lbs_vertex(self, node: 'ModelNode', vi: int,
                    bone_transforms: Dict) -> Tuple[float, float, float]:
        """
        Apply Linear Blend Skinning to vertex vi of the given skin node.

        KotOR skin vertices are authored in the model-root bind frame consumed
        by the skinning palette. Do not apply the skin node's own hierarchy
        transform before LBS; in bind pose the xoreos skin formula collapses
        back to the authored vertex coordinate.

        Standard LBS formula:
            v_world_anim = sum_i( w_i * (R_anim_i * R_bind_i^-1 * (v_bind_world - T_bind_i) + T_anim_i) )

        Where:
          v_bind_world = authored skin bind coordinate
          T_bind_i     = bone i world position at bind pose
          R_bind_i     = bone i world rotation at bind pose
          T_anim_i     = bone i world position at animated pose
          R_anim_i     = bone i world rotation at animated pose

        If no valid bone influences found, falls back to the bind-pose world
        position (the authored skin bind coordinate).
        """
        try:
            from src.core.geometry.model_data import _quat_rotate as _qr, _quat_conjugate
        except ImportError:
            from core.geometry.model_data import _quat_rotate as _qr, _quat_conjugate  # type: ignore

        v = node.vertices[vi]

        wp_s, wo_s, is_id_s = self._node_world_transform(node)
        if vi == 0:
            _gr_probe('CPU-LBS', node, wp_s, wo_s, is_id_s)
        vbx, vby, vbz = v[0], v[1], v[2]

        def _bind_fallback():
            """Return bind-pose world position."""
            return (vbx, vby, vbz)

        if vi >= len(node.skin_data):
            # No skin data: return bind-pose world position
            return _bind_fallback()

        sd = node.skin_data[vi]
        influences = sd.influences

        if not influences:
            # No influences: return bind-pose world position
            return _bind_fallback()

        import math as _math_lbs
        rx_total = ry_total = rz_total = 0.0
        total_weight = 0.0
        # Explosion guard: if animated position is more than _MAX_BONE_DIST units away
        # from the bind position, the bone transform is degenerate (NaN propagation from
        # bad animation keyframes, or un-collapsed 180°-axis root rotations in the chain).
        # Skip that influence and fall back to bind-pose contribution instead.
        #
        # v20.0 FIX: Threshold scaled by model bounding-box size to handle large creatures.
        # Previous hard-coded 8.0 unit limit was too small for creatures like c_brith
        # (Drexl) whose wings span ~30 units and travel 15+ units during flight animations,
        # causing clipped/missing wing geometry during animation playback.
        #
        # Strategy: scale by max(model_bbox_diagonal * 0.6, 8.0) to:
        #   - Keep the 8-unit floor for human-scale characters (prevents usecomp distortions)
        #   - Allow large creature wings/limbs to deform correctly (c_brith, c_bosdrexl, etc.)
        # The 0.6 factor means a bone can travel up to 60% of the model's bounding diagonal
        # before being treated as degenerate.  For c_brith (~55-unit diagonal): 33 units.
        # For S_Female02 human scale (~4.0-unit diagonal): floor 8.0 applies.
        _model_diag = getattr(self, '_lbs_model_diag', None)
        if _model_diag is None:
            # Compute bounding diagonal once per model and cache it
            m = self.model
            if m is not None:
                try:
                    bmin, bmax = m.bounding_box()
                    dx = bmax[0]-bmin[0]; dy = bmax[1]-bmin[1]; dz = bmax[2]-bmin[2]
                    _model_diag = _math_lbs.sqrt(dx*dx + dy*dy + dz*dz)
                except Exception:
                    _model_diag = 10.0
            else:
                _model_diag = 10.0
            self._lbs_model_diag = _model_diag
        _MAX_BONE_DIST = max(8.0, _model_diag * 0.6)

        for bw in influences:
            if bw.weight <= 0.0:
                continue
            bt = bone_transforms.get(bw.bone_index)
            if bt is None:
                continue
            bind_wp, bind_wo, anim_wp, anim_wo = bt
            w = bw.weight

            # Sanity-check anim_wp: skip bones with non-finite or extreme positions
            # (explosion guard — catches bad keyframes and un-collapsed root rotations)
            awx, awy, awz = anim_wp
            if not (_math_lbs.isfinite(awx) and _math_lbs.isfinite(awy) and _math_lbs.isfinite(awz)):
                # Non-finite: fall back to bind-pose contribution for this influence
                rx_total += w * vbx; ry_total += w * vby; rz_total += w * vbz
                total_weight += w
                continue
            bwx, bwy, bwz = bind_wp
            bone_travel = _math_lbs.sqrt((awx-bwx)**2 + (awy-bwy)**2 + (awz-bwz)**2)
            if bone_travel > _MAX_BONE_DIST:
                # Bone moved impossibly far: treat as bind-pose for this influence
                rx_total += w * vbx; ry_total += w * vby; rz_total += w * vbz
                total_weight += w
                continue

            # Step 1: transform vertex from bind-pose world space to bone-local space
            # v_bone_local = R_bind^-1 * (v_bind_world - T_bind_bone)
            vx = vbx - bwx
            vy = vby - bwy
            vz = vbz - bwz
            # Inverse of bind rotation quaternion = conjugate (since unit quaternion)
            bind_inv = _quat_conjugate(bind_wo)
            lx, ly, lz = _qr(bind_inv, (vx, vy, vz))

            # Step 2: transform from bone-local space to animated world space
            # v_anim_world = R_anim * v_bone_local + T_anim_bone
            ax, ay, az = _qr(anim_wo, (lx, ly, lz))
            rx_total += w * (ax + awx)
            ry_total += w * (ay + awy)
            rz_total += w * (az + awz)
            total_weight += w

        if total_weight < 0.001:
            # No valid bones – fall back to bind-pose world position
            return _bind_fallback()

        # Normalize by total weight (handles partial weight sums)
        inv_w = 1.0 / total_weight
        rx, ry, rz = rx_total * inv_w, ry_total * inv_w, rz_total * inv_w

        # Final explosion guard: if LBS result is more than _MAX_BONE_DIST*2 away
        # from the bind-pose vertex, the deformation is too extreme — return bind pose.
        # Multiplied by 2 here (vs per-bone check) because compound deformations from
        # multiple valid bones can legitimately sum to larger displacements than any
        # single bone travel (e.g. c_brith wingtip = root travel + wing-fold travel).
        if (_math_lbs.sqrt((rx-vbx)**2 + (ry-vby)**2 + (rz-vbz)**2) > _MAX_BONE_DIST * 2.0):
            return _bind_fallback()
        return (rx, ry, rz)

    def _gpu_parity_skinned_world_verts_for_node(self, node: 'ModelNode') -> Optional[List[Tuple[float, float, float]]]:
        """Return animated skin verts using the same palette contract as GPU draws."""
        if (
            _MatrixPaletteUploader is None
            or not _NUMPY
            or self.model is None
            or self._anim_pose is None
            or not getattr(node, "is_skin", False)
            or not getattr(node, "bone_map", None)
            or not getattr(node, "skin_data", None)
            or not getattr(node, "vertices", None)
        ):
            return None

        model_id = id(self.model)
        pose_id = (
            id(self._anim_pose),
            id(getattr(self, "_anim_base_pose", None)),
        )
        node_id = id(node)
        if (
            self._gpu_parity_skin_model_id == model_id
            and self._gpu_parity_skin_pose_id == pose_id
            and node_id in self._gpu_parity_skin_verts_cache
        ):
            return self._gpu_parity_skin_verts_cache[node_id]

        if self._gpu_parity_skin_model_id != model_id or self._gpu_parity_skin_uploader is None:
            try:
                uploader = _MatrixPaletteUploader(max_bones=_SKIN_MAX_BONES)
                uploader.build_inverse_bind_pose(self.model)
            except Exception as exc:
                log.debug("GPU-parity overlay skin uploader build failed: %s", exc)
                self._gpu_parity_skin_uploader = None
                self._gpu_parity_skin_model_id = -1
                return None
            self._gpu_parity_skin_uploader = uploader
            self._gpu_parity_skin_model_id = model_id
            self._gpu_parity_skin_pose_id = -1
            self._gpu_parity_skin_verts_cache = {}

        if self._gpu_parity_skin_pose_id != pose_id:
            self._gpu_parity_skin_pose_id = pose_id
            self._gpu_parity_skin_verts_cache = {}

        try:
            uploader = self._gpu_parity_skin_uploader
            uploader.compute_skin_node_palette(
                node,
                self._anim_pose,
                anim_base_pose=getattr(self, "_anim_base_pose", None),
            )
            palette = uploader.as_numpy_array()
        except Exception as exc:
            log.debug("GPU-parity overlay skin palette failed for %s: %s", getattr(node, "name", "?"), exc)
            return None
        if palette is None or len(palette) == 0:
            return None

        arrays = self._skin_numpy_arrays_for_node(node)
        if arrays is None:
            return None
        vertices_h, bone_indices, weights = arrays
        bone_count = int(palette.shape[0])
        if bone_count <= 0:
            return None

        skinned = np.zeros_like(vertices_h, dtype=np.float32)
        weight_total = np.zeros((vertices_h.shape[0],), dtype=np.float32)
        for slot in range(min(4, bone_indices.shape[1])):
            slot_weights = weights[:, slot]
            valid = (slot_weights >= np.float32(0.0001)) & (bone_indices[:, slot] >= 0) & (bone_indices[:, slot] < bone_count)
            if not bool(np.any(valid)):
                continue
            matrices = palette[bone_indices[valid, slot]]
            transformed = np.einsum("nij,nj->ni", matrices, vertices_h[valid], optimize=True)
            skinned[valid] += slot_weights[valid, None] * transformed
            weight_total[valid] += slot_weights[valid]

        fallback = weight_total < np.float32(0.0001)
        if bool(np.any(fallback)):
            skinned[fallback] = vertices_h[fallback]
        result = [tuple(float(value) for value in row[:3]) for row in skinned]
        self._gpu_parity_skin_verts_cache[node_id] = result
        return result

    def _skin_numpy_arrays_for_node(self, node: 'ModelNode'):
        """Return cached homogeneous vertices, bone indices, and weights.

        Imported FBX preview meshes can be large (Mixamo's X Bot is ~147k
        vertices). Building these compact arrays once keeps focused playback
        from spending most of its frame budget walking Python skin structures.
        """

        vertices = getattr(node, "vertices", []) or []
        skin_data = list(getattr(node, "skin_data", []) or [])
        vertex_count = len(vertices)
        if vertex_count <= 0 or len(skin_data) < vertex_count:
            return None
        cache_key = (id(vertices), id(getattr(node, "skin_data", None)), vertex_count, len(skin_data))
        cache = getattr(node, "_gr_skin_numpy_arrays_cache", None)
        if isinstance(cache, tuple) and len(cache) == 2 and cache[0] == cache_key:
            return cache[1]
        try:
            verts = np.asarray(vertices, dtype=np.float32)
        except Exception:
            return None
        if verts.ndim != 2 or verts.shape[0] == 0 or verts.shape[1] < 3:
            return None
        vertices_h = np.ones((verts.shape[0], 4), dtype=np.float32)
        vertices_h[:, :3] = verts[:, :3]
        bone_indices = np.full((verts.shape[0], 4), -1, dtype=np.int32)
        weights = np.zeros((verts.shape[0], 4), dtype=np.float32)
        for vi, skin in enumerate(skin_data[: verts.shape[0]]):
            for slot, influence in enumerate(list(getattr(skin, "influences", []) or [])[:4]):
                try:
                    bone_indices[vi, slot] = int(getattr(influence, "bone_index", -1))
                    weights[vi, slot] = float(getattr(influence, "weight", 0.0))
                except Exception:
                    bone_indices[vi, slot] = -1
                    weights[vi, slot] = 0.0
        arrays = (vertices_h, bone_indices, weights)
        try:
            setattr(node, "_gr_skin_numpy_arrays_cache", (cache_key, arrays))
        except Exception:
            pass
        return arrays

    def _get_world_verts_for_node(self, node: 'ModelNode') -> List[Tuple]:
        """
        Get all world-space vertices for a node, using LBS when an animation
        pose is active and the node has skin_data, or bind pose otherwise.

        KotOR MDL vertex space convention — Phase 17 (verified against KotorBlender,
        PyKotor, and direct binary analysis of c_bantha, c_terantanak, p_bastilabb,
        N_sithpraet and 50+ other models):

        Non-skin trimesh/dangly nodes — BIND POSE:
          Vertices are stored in NODE-LOCAL space (relative to the node's own
          pivot point in the hierarchy).  The full parent-chain world transform
          (translation + rotation accumulated root→leaf) must always be applied.

          KotorBlender (base.py): set_object_data() sets obj.location = self.position
          (LOCAL, not world); vertices uploaded raw without any pre-transform.
          Blender scene graph applies parent-chain transforms automatically.

          PyKotor: vertex_positions read raw from binary MDL, no world-space pre-baking.

          c_bantha direct binary analysis:
            btBody_front local verts Y=[1.117, 3.391], node world pivot Y=-1.163
            → correct world Y = [-0.046, 2.228] (body covers torso, anatomy correct)
            "as-is" gave Y=[1.117, 3.391] (body floating forward in front of skeleton)

          btRhorn: local verts Y=[1.851,2.955], pivot (Y=-0.890,Z=1.469)
            World verts Y=[0.961,2.065] — curved upward/forward above the head. ✓

        Skin nodes — BIND POSE:
          Vertices use the same node-local import contract as trimeshes. This
          matters for binary head/accessory models such as ad_saul, where the
          binary reader marks head/tongue meshes as skin but the matching ASCII
          import keeps the same raw vertices under the node transform.

        SKIN nodes — ANIMATED POSE:
          Use Linear Blend Skinning (LBS) with bone_transforms.
          LBS starts from the authored bind coordinate and applies bone deltas.
        """
        verts = node.vertices
        if not verts:
            return []

        # Imported FBX skins are stored in model/world bind coordinates, but
        # still need LBS when a live pose is driving their bone_map.
        is_bas_attachment = bool(getattr(node, "_gr_bas_attachment_layer", False))
        if node.is_skin and self._anim_pose is not None and node.bone_map and node.skin_data and not is_bas_attachment:
            gpu_parity_verts = self._gpu_parity_skinned_world_verts_for_node(node)
            if gpu_parity_verts is not None:
                return gpu_parity_verts
            bone_transforms = self._build_bone_transforms(node)
            if bone_transforms:
                return [self._lbs_vertex(node, i, bone_transforms)
                        for i in range(len(verts))]

        # ── Imported WORLD-space geometry: already pre-transformed ────────────
        # Phase G1 safeguard.  ``vertex_space.py`` classifies every node at
        # load time.  Standard KotOR MDL nodes are NODE_LOCAL (apply the
        # parent-chain transform), but externally-imported OBJ/FBX meshes
        # carry ``_imported=True`` and land in ``VertexSpace.WORLD`` — their
        # vertices are *already* in model-root space.  Running them through
        # ``_node_world_transform`` would apply the hierarchy a second time,
        # producing a double-transform bug.  Short-circuit here and return
        # the raw tuples unchanged.  Animated imported skins already had their
        # bone_map-driven LBS chance above.
        vs = getattr(node, 'vertex_space', None)
        if vs is not None:
            try:
                from src.core.geometry.vertex_space import VertexSpace
                if int(vs) == int(VertexSpace.WORLD):
                    return [tuple(v) for v in verts]
            except Exception:
                pass  # defensive: if the enum import fails, fall through

        # ── SKIN nodes: authored bind frame, optionally deformed by LBS ───────
        if node.is_skin:
            if self._anim_pose is not None and node.bone_map and node.skin_data and not is_bas_attachment:
                gpu_parity_verts = self._gpu_parity_skinned_world_verts_for_node(node)
                if gpu_parity_verts is not None:
                    return gpu_parity_verts
                bone_transforms = self._build_bone_transforms(node)
                if bone_transforms:
                    return [self._lbs_vertex(node, i, bone_transforms)
                            for i in range(len(verts))]
            if is_bas_attachment:
                bas_root = self._bas_attachment_root_for_node(node)
                if bas_root is not None:
                    try:
                        from src.core.geometry.model_data import (
                            _quat_mul,
                            _quat_normalize,
                            _quat_normalize_bind,
                            _quat_rotate as _qr,
                        )
                    except ImportError:
                        from core.geometry.model_data import (  # type: ignore
                            _quat_mul,
                            _quat_normalize,
                            _quat_normalize_bind,
                            _quat_rotate as _qr,
                        )
                    local_wp, local_wo, local_is_id = self._bas_attachment_local_transform(
                        node,
                        bas_root,
                        _qr,
                        _quat_normalize_bind,
                        _quat_normalize,
                        _quat_mul,
                    )
                    root_wp, root_wo, root_is_id = self._node_world_transform(bas_root)
                    xfm = self._apply_vertex_transform
                    root_local = [xfm(node, v, local_wp, local_wo, local_is_id) for v in verts]
                    return [xfm(node, v, root_wp, root_wo, root_is_id) for v in root_local]
            wp, wo, is_id = self._node_world_transform(node)
            _gr_probe('CPU-skin-bind', node, wp, wo, is_id)
            xfm = self._apply_vertex_transform
            result = [xfm(node, v, wp, wo, is_id) for v in verts]
            off = getattr(node, '_composite_nonskin_offset', None)
            if off is not None:
                ox, oy, oz = float(off[0]), float(off[1]), float(off[2])
                if abs(ox) > 1e-6 or abs(oy) > 1e-6 or abs(oz) > 1e-6:
                    result = [(x + ox, y + oy, z + oz) for x, y, z in result]
            return result

        # ── Non-skin trimesh/dangly: apply full world transform ───────────────
        wp, wo, is_id = self._node_world_transform(node)
        _gr_probe('CPU-bind', node, wp, wo, is_id)
        xfm = self._apply_vertex_transform

        # ── DanglySimulator path ──────────────────────────────────────────────
        if node.is_dangly and node.dangly_constraints:
            constraints = node.dangly_constraints
            sim = self._dangly_sims.get(id(node)) if self._anim_pose is not None else None
            result = []
            for i, v in enumerate(verts):
                c = constraints[i] if i < len(constraints) else 0.0
                is_pinned = (c >= (DanglySimulator.PIN_THRESHOLD
                                   if DanglySimulator is not None else 0.95))
                if sim is not None and not is_pinned and i < len(sim.positions):
                    result.append(sim.positions[i])
                else:
                    result.append(xfm(node, v, wp, wo, is_id))
            return result

        return [xfm(node, v, wp, wo, is_id) for v in verts]

    def _get_world_normals_for_node(self, node: 'ModelNode') -> List[Optional[Tuple]]:
        """
        Return world-space normals for a node.

        All nodes (skin and non-skin) with identity world orientation: normals are
          already oriented correctly in world space — return as-is (no rotation needed).
        Any node with non-identity world orientation: rotate each normal by the
          node's world orientation quaternion.  This correctly orients normals for:
          - Non-skin trimesh nodes with non-identity bind-pose rotation
          - Skin nodes that carry a non-identity orientation (e.g. 180° X/Y on
            p_bastilabb/p_bastilaba from the NWN coord-flip exporter)

        Returns a list parallel to node.normals.  Empty list if no normals.
        """
        norms = node.normals
        if not norms:
            return []

        # Check if rotation is identity — skip transform when not needed
        wp, wo, is_id = self._node_world_transform(node)
        if is_id:
            return list(norms)

        # Rotate normals by world orientation (rotation-only, no translation).
        # This handles both non-skin trimesh nodes AND skin nodes that carry a
        # non-identity rotation (NWN coord-flip exporter artefact on mesh nodes).
        result = []
        for n in norms:
            rn = _quat_rotate(wo, n)
            # Re-normalise
            nl = math.sqrt(rn[0]*rn[0] + rn[1]*rn[1] + rn[2]*rn[2])
            if nl > 1e-9:
                result.append((rn[0]/nl, rn[1]/nl, rn[2]/nl))
            else:
                result.append(n)
        return result

    def _screen_size_lod_cap(self, W: int, H: int) -> int:
        """
        UE-inspired screen-size driven triangle cap with LOD hysteresis.

        Computes what fraction of the viewport the model occupies (like UE's
        ComputeBoundsScreenSize / USkeletalMeshComponent::UpdateLODStatus) and
        scales the triangle budget accordingly.  A hysteresis dead-band of
        _LOD_HYSTERESIS_FRAC × MAX_TRIS prevents rapid oscillation when the
        camera sits right at a LOD boundary (eliminates "LOD-pop" flicker).

        Returns a triangle count cap in the range:
          [MAX_TRIS_INTERACTIVE (10k) .. MAX_TRIS (80k)]
        """
        if self.model is None:
            cap = self.MAX_TRIS_INTERACTIVE if self.is_interactive else self.MAX_TRIS
            self._lod_prev_cap = cap
            return cap

        try:
            bmin, bmax = self._get_render_bounds()
        except Exception:
            cap = self.MAX_TRIS_INTERACTIVE if self.is_interactive else self.MAX_TRIS
            self._lod_prev_cap = cap
            return cap

        # FIX-CAMEYE: safely handle both callable (ArcBallCamera) and
        # tuple/list (duck-typed camera) for the eye attribute.
        _eye = self.cam.eye
        eye_pos = _eye() if callable(_eye) else _eye
        fov_rad = math.radians(self.cam.fov)

        # Compute screen-size ratio using UE's formula
        ratio = _compute_screen_size_ratio(bmin, bmax, eye_pos, fov_rad, H)

        # Scale triangle cap proportionally to screen coverage:
        # - ratio ≥ 0.5 → full detail
        # - ratio ≤ 0.05 → minimum detail (interactive cap)
        ratio_clamped = _clamp(ratio, 0.05, 0.5)
        t = (ratio_clamped - 0.05) / (0.5 - 0.05)  # 0..1

        base_cap = self.MAX_TRIS_INTERACTIVE if self.is_interactive else self.MAX_TRIS
        min_cap  = self.MAX_TRIS_INTERACTIVE
        new_cap  = int(min_cap + t * (base_cap - min_cap))

        # ── LOD hysteresis dead-band ────────────────────────────────────────
        # Only commit a new cap when it differs from the last committed value
        # by more than the hysteresis threshold.  This prevents per-frame
        # oscillation of the triangle budget when the camera distance hovers
        # near a tier boundary.  Mirrors UE's LOD hysteresis in UpdateLODStatus.
        hysteresis_band = int(self._LOD_HYSTERESIS_FRAC * self.MAX_TRIS)
        if abs(new_cap - self._lod_prev_cap) > hysteresis_band:
            self._lod_prev_cap = new_cap
        return self._lod_prev_cap
