"""RendererOverlayMixin methods for the viewport frame renderer."""

from __future__ import annotations

from .mixin_imports import (
    Iterable,
    Optional,
    WalkmeshLoader,
    WalkmeshOverlay,
    _AXIS_X,
    _AXIS_Y,
    _AXIS_Z,
    _BG,
    _clean_tex_name,
    _dot,
    _quat_rotate,
    is_animation_supermodel,
    log,
    math,
)


class RendererOverlayMixin:
    def hit_test_bone(self, sx: int, sy: int, radius: int = 8) -> Optional['ModelNode']:
        """Return the nearest bone within `radius` pixels of screen coord (sx, sy)."""
        best_node = None
        best_dist2 = radius * radius
        for bsx, bsy, depth, node in self._bone_screen_positions:
            d2 = (bsx - sx)**2 + (bsy - sy)**2
            if d2 <= best_dist2:
                best_dist2 = d2
                best_node = node
        return best_node

    def _iter_mesh_nodes(self):
        """Yield all renderable mesh and skin nodes in the model (depth-first).

        Draw-list contract (audited Phase G1)
        ─────────────────────────────────────
        * Traversal:     iterative DFS over ``root_node.children`` with a
                         ``visited`` cycle guard.  Capped implicitly by the
                         guard to prevent render-thread stalls on malformed
                         MDLs that contain shared-child sub-graphs.
        * Filter:        yields nodes with ``is_mesh`` OR ``is_skin``.  The
                         SKIN flag (0x0040) does NOT set ``is_mesh``; without
                         including it we would drop every character body
                         mesh (``bthair`` / ``btBody_front`` / …).
        * AABB walkmesh nodes (flag 0x0200) are excluded because
                         ``is_mesh`` is False for them.  See ``vertex_space.py``.
        * Non-rendered inner-head geometry (eyeRA / teethU / tongue …)
                         gets a force-render override downstream in
                         ``_render_one_node`` via ``_INNER_GEO_SUBSTRINGS``,
                         so we must keep yielding them here even when their
                         ``render`` flag is False.
        * Vertices are transformed downstream by
                         ``_get_world_verts_for_node`` which handles both
                         the LBS (animated skin) path and the bind / trimesh
                         path.
        """
        if not self.model or not self.model.root_node:
            return
        stack = [self.model.root_node]
        visited: set = set()
        while stack:
            n = stack.pop()
            if n is None:
                continue
            nid = id(n)
            if nid in visited:
                continue
            visited.add(nid)
            if n.is_mesh or n.is_skin:
                # Hologram-mode filter (Phase G3, opt-in).  Nodes whose MDL
                # mesh header marks them "hologram_donotdraw" / "hide_in_
                # hologram" are skipped here *only* when hologram_mode is
                # enabled, preserving default rendering exactly.
                if self.hologram_mode and getattr(n, 'hide_in_holograms', False):
                    stack.extend(c for c in reversed(n.children) if c is not None)
                    continue
                yield n
            stack.extend(c for c in reversed(n.children) if c is not None)

    def set_hologram_mode(self, enabled: bool) -> None:
        """Enable or disable the hologram-preview render filter.

        When enabled, ``_iter_mesh_nodes`` drops any node with
        ``hide_in_holograms == True``.  Intended for UI toggles that want to
        mirror in-game hologram cutscenes, or for screenshot tools that need
        parity with the engine's ``holoGram`` camera pass.

        This is a data-only flag change — callers are responsible for
        scheduling a re-render afterwards (e.g. ``viewport.request_redraw()``
        or the widget's own refresh hook).
        """
        self.hologram_mode = bool(enabled)

    def set_hidden_bone_name_fragments(self, fragments: Iterable[str]) -> None:
        self.hidden_bone_name_fragments = tuple(
            sorted({
                str(fragment or "").strip().lower()
                for fragment in fragments
                if str(fragment or "").strip()
            })
        )

    def is_hidden_bone_name(self, name: str) -> bool:
        key = str(name or "").strip().lower()
        return bool(key) and any(fragment in key for fragment in self.hidden_bone_name_fragments)

    # ── Bones ─────────────────────────────────────────────────────────

    def _draw_bones(self, draw: 'ImageDraw.Draw', W: int, H: int):
        """
        Draw bone/skeleton overlay.

        In KotOR models, the skeleton consists of BOTH true dummy nodes (0x0001)
        AND deformation-helper trimesh nodes (0x0021, _g suffix).  Both types
        carry position/orientation data and are referenced by skin node bone_maps.
        We show all of them as joints.

        Bone categories:
          • Root / body joints      – large gold dots (r=4), connected
          • Deform-helper trimesh   – small green dots (r=3), connected
          • Leaf joints             – small amber dots (r=2)
          • Effect attachment nodes – tiny dim-blue dots (r=2), no lines
            (hook, conjure, camerahook – these are VFX attachment points)
          • Selected joint          – teal (r=7) + name label
          • Hovered joint           – bright yellow (r=5) + name label
        """
        if not self.model or not self.model.root_node:
            return

        # Keep the base skeleton neutral and slender. Selection/hover and the
        # Qt joint overlay carry interaction color; the bone bodies themselves
        # should read like Unreal-style rig bones, not fat orange debug lines.
        _BONE_COL   = (164, 176, 190)
        _BONE_DEFORM= (126, 146, 164)
        _BONE_LEAF  = (140, 152, 166)
        _BONE_LINE  = (132, 146, 164)
        _DEFORM_LINE= (110, 130, 148)
        _SEL_COL    = (255, 218, 40)
        _KEY_COL    = (58, 150, 255)
        _EFF_COL    = ( 50, 120, 180)      # dim blue for effect nodes

        # Clear bone screen positions for this frame (hit-test tracking)
        self._bone_screen_positions = []
        self._bone_screen_axis_angles = {}

        skeleton_name_keys: set[str] = set()
        try:
            nodes_for_skeleton = list(self.model.all_nodes()) if hasattr(self.model, "all_nodes") else []
        except Exception:
            nodes_for_skeleton = []
        for candidate in nodes_for_skeleton:
            for bone_name in getattr(candidate, "bone_map", None) or []:
                key = str(bone_name or "").strip().lower()
                if key:
                    skeleton_name_keys.add(key)

        def _scene_node_kind(node) -> str:
            return str(getattr(node, "_gr_scene_node_kind", "") or "").strip().lower()

        def _node_has_skeleton_context(node) -> bool:
            kind = _scene_node_kind(node)
            if kind == "joint":
                return True
            asset_kind = str(getattr(node, "_gr_scene_asset_kind", "") or "").strip().lower()
            animation_kind = str(getattr(node, "_gr_scene_animation_kind", "") or "").strip().lower()
            if asset_kind in {"placeable", "static_mesh", "door"} and animation_kind in {"", "static", "rigid"}:
                return False
            name_key = str(getattr(node, "name", "") or "").strip().lower()
            if name_key in skeleton_name_keys:
                return True
            if kind in {"mesh", "skin_mesh", "dummy", "animated_dummy", "animated_node", "node"}:
                return bool(skeleton_name_keys)
            try:
                model_type = int(getattr(self.model, "model_type", 4))
            except Exception:
                model_type = 4
            if model_type in {8, 32} and not skeleton_name_keys:
                return False
            return True

        def _is_bone_node(node) -> bool:
            """Return True if this node is a skeleton joint (dummy OR deform-helper)."""
            if getattr(node, '_hide_skeleton_overlay', False):
                return False
            if not _node_has_skeleton_context(node):
                return False
            nl = (getattr(node, "name", "") or "").lower()
            if self.is_hidden_bone_name(nl):
                return False
            if nl.startswith("ik_") or nl in {"interaction", "center_of_mass"}:
                return False
            if "hook" in nl:
                return False
            if node.is_dummy:
                return True
            # Root node is always treated as a bone (skeleton root)
            if node.parent is None:
                return True
            # Deform-helper trimesh nodes (_g, _dum suffixes) ARE skeleton joints
            # in KotOR's Odyssey engine – they carry bone transforms
            if node.is_mesh and not node.is_skin:
                nl = node.name.lower()
                if (nl.endswith('_g') or nl.endswith('_g0') or
                        nl.endswith('_dum') or nl.endswith('dummy')):
                    return True
            return False

        def _nearest_bone_ancestor(node):
            """Walk parent chain and return the first bone ancestor, or None."""
            p = node.parent
            _visited = set()
            while p is not None:
                pid = id(p)
                if pid in _visited:
                    break   # cycle guard
                _visited.add(pid)
                if _is_bone_node(p):
                    return p
                p = p.parent
            return None

        def _draw_bone_segment(pp_child, pp_parent, color, selected: bool = False) -> None:
            """Draw a slim tapered bone body between projected joint points."""
            dx = float(pp_child[0] - pp_parent[0])
            dy = float(pp_child[1] - pp_parent[1])
            length = math.sqrt(dx * dx + dy * dy)
            if length < 1.0:
                return
            if length < 8.0:
                draw.line([pp_parent[0], pp_parent[1], pp_child[0], pp_child[1]],
                          fill=color, width=2 if selected else 1)
                return

            nx = -dy / length
            ny = dx / length
            base_w = 3.0 if selected else 2.2
            tip_w = 1.0 if selected else 0.7
            root_t = 0.16
            base_x = pp_parent[0] + dx * root_t
            base_y = pp_parent[1] + dy * root_t
            polygon = [
                (int(round(base_x + nx * base_w)), int(round(base_y + ny * base_w))),
                (int(round(pp_child[0] + nx * tip_w)), int(round(pp_child[1] + ny * tip_w))),
                (int(round(pp_child[0] - nx * tip_w)), int(round(pp_child[1] - ny * tip_w))),
                (int(round(base_x - nx * base_w)), int(round(base_y - ny * base_w))),
            ]
            try:
                draw.polygon(polygon, fill=color)
                highlight = tuple(min(255, c + 38) for c in color)
                draw.line([pp_parent[0], pp_parent[1], pp_child[0], pp_child[1]],
                          fill=highlight, width=1)
            except Exception:
                draw.line([pp_parent[0], pp_parent[1], pp_child[0], pp_child[1]],
                          fill=color, width=2 if selected else 1)

        def _bone_world_pos(node):
            # Use the renderer's cached world-transform for animated poses so
            # joint dots track the animation correctly.  For bind pose use
            # bone_world_position() which applies full 180°-collapse on ALL
            # nodes including the leaf — this gives the correct pivot point for
            # joint dots (independent of mesh vertex orientation).
            if self._anim_pose is not None:
                wp, _, _ = self._node_world_transform(node)
                return wp
            external_wp = getattr(node, 'external_world_position', None)
            if external_wp is not None:
                return external_wp
            return node.bone_world_position()

        def _record_local_axis_angle(node, wp, pp) -> None:
            try:
                _node_wp, node_wo, _is_id = self._node_world_transform(node)
                axis = _quat_rotate(node_wo, (0.0, 1.0, 0.0))
                scale = 0.35
                ep = (wp[0] + axis[0] * scale, wp[1] + axis[1] * scale, wp[2] + axis[2] * scale)
                pp_axis = self._proj(*ep, W, H)
                if not pp_axis:
                    return
                dx = float(pp_axis[0] - pp[0])
                dy = float(pp_axis[1] - pp[1])
                if (dx * dx + dy * dy) < 1.0:
                    return
                target_angle = math.atan2(dy, dx)
                self._bone_screen_axis_angles[id(node)] = -math.degrees(target_angle + math.pi * 0.5)
            except Exception:
                return

        def _process_bone_node(node):
            """Draw one bone joint + its connection line to the nearest bone ancestor."""
            is_bone = _is_bone_node(node)
            if not is_bone:
                return

            # ── Classify this joint ────────────────────────────────
            name_lw = node.name.lower()
            is_effect_attach = any(s in name_lw for s in
                ('hook', 'conjure', 'camerahook'))
            is_deform_helper = (node.is_mesh and not node.is_dummy)
            is_key_joint = name_lw in self._KEY_JOINT_NAMES

            # ── World position → screen position ──────────────────
            wp  = _bone_world_pos(node)
            pp  = self._proj(*wp, W, H)

            # Count bone children (for leaf detection)
            bone_children = [c for c in node.children if _is_bone_node(c)]
            has_joint_children = bool(bone_children)
            is_sel     = (node is self.selected_node)
            is_hovered = (node is self._hovered_bone and not is_sel)

            # Draw the bone body before the joint anchor so the anchor stays
            # crisp and readable on top of the tapered segment.
            if pp and not is_effect_attach:
                par_bone = _nearest_bone_ancestor(node)
                if par_bone is not None:
                    par_wp = _bone_world_pos(par_bone)
                    pp2    = self._proj(*par_wp, W, H)
                    if pp2:
                        dx = pp[0] - pp2[0]; dy = pp[1] - pp2[1]
                        line_len = math.sqrt(dx*dx + dy*dy)
                        if 4.0 < line_len < max(W, H) * 0.5:
                            if is_sel:
                                line_col = _SEL_COL
                            elif is_deform_helper:
                                line_col = _DEFORM_LINE
                            else:
                                line_col = _BONE_LINE
                            _draw_bone_segment(pp, pp2, line_col, selected=is_sel)

            if pp:
                # Record for click hit-testing
                self._bone_screen_positions.append((pp[0], pp[1], pp[2], node))
                _record_local_axis_angle(node, wp, pp)

                # Dot appearance
                if is_sel:
                    dot_color    = _SEL_COL
                    outline_col  = (255, 255, 100)
                    r = 5
                elif is_key_joint:
                    dot_color    = _KEY_COL
                    outline_col  = (215, 235, 255)
                    r = 4
                elif is_hovered:
                    dot_color    = (255, 220, 80)
                    outline_col  = (255, 255, 180)
                    r = 4
                elif is_effect_attach:
                    dot_color    = _EFF_COL
                    outline_col  = None
                    r = 1
                elif is_deform_helper:
                    dot_color    = _BONE_DEFORM
                    outline_col  = None
                    r = 2 if has_joint_children else 1
                else:
                    dot_color    = _BONE_COL if has_joint_children else _BONE_LEAF
                    outline_col  = None
                    r = 2 if has_joint_children else 1

                draw.ellipse([pp[0]-r, pp[1]-r, pp[0]+r, pp[1]+r],
                             fill=dot_color, outline=outline_col)

                # Bone name label for selected or hovered nodes
                if is_sel or is_hovered:
                    try:
                        lx = pp[0] + r + 3
                        ly = pp[1] - 7
                        label_col = _SEL_COL if is_sel else (255, 240, 120)
                        draw.text((lx+1, ly+1), node.name, fill=(0, 0, 0))
                        draw.text((lx,   ly),   node.name, fill=label_col)
                    except Exception:
                        pass

        # Iterative BFS traversal — avoids Python recursion limit on deep models
        # such as c_brith (601 nodes) and other RARE_CHAR type-64 models.
        _stack = [self.model.root_node]
        _visited_ids: set = set()
        while _stack:
            node = _stack.pop()
            nid = id(node)
            if nid in _visited_ids:
                continue
            _visited_ids.add(nid)
            _process_bone_node(node)
            # Push children in reverse order so left-most child is processed first
            for c in reversed(node.children):
                if id(c) not in _visited_ids:
                    _stack.append(c)

        # ── Post-pass: skin influence lines for selected node ──────────────
        # When a skin mesh node is selected, draw dashed lines from the skin
        # node's world position to each of its referenced bone joints.
        # This makes the bone/mesh relationship visible for debugging rigging.
        sel = self.selected_node
        if sel is not None and sel.is_skin and sel.bone_map:
            sel_wp = _bone_world_pos(sel)
            sel_sp = self._proj(*sel_wp, W, H)
            INFL_LINE = (100, 200, 255)   # light blue — influence connection
            for bone_name in sel.bone_map[:16]:   # limit to 16 for performance
                bone_node = self.model.find_node(bone_name) if self.model else None
                if bone_node is None:
                    continue
                b_wp = _bone_world_pos(bone_node)
                b_sp = self._proj(*b_wp, W, H)
                if sel_sp and b_sp:
                    # Dashed influence line
                    x0, y0 = sel_sp[0], sel_sp[1]
                    x1, y1 = b_sp[0],  b_sp[1]
                    dx, dy = x1-x0, y1-y0
                    length = math.sqrt(dx*dx+dy*dy)
                    if 5 < length < max(W, H) * 0.7:
                        steps = max(2, int(length / 8))
                        for s in range(steps):
                            if s % 2 == 0:
                                tx = int(x0 + dx * s / steps)
                                ty = int(y0 + dy * s / steps)
                                tx2= int(x0 + dx * (s+1) / steps)
                                ty2= int(y0 + dy * (s+1) / steps)
                                draw.line([tx, ty, tx2, ty2],
                                          fill=INFL_LINE, width=1)




    # ── AcuRig guide overlay ─────────────────────────────────────────────────

    def set_acurig_guides(self, guides: dict):
        """Register an AcuRig guide dict for viewport overlay rendering.

        Parameters
        ----------
        guides : dict
            Mapping of guide_name → RigGuide (or any object with .position tuple).
            Pass None or {} to clear the overlay.
        """
        self._acurig_guides_overlay = guides or {}
        self._acurig_selected_guide: str = ''
        redraw = getattr(self, "redraw", None)
        if callable(redraw):
            redraw()

    def _draw_acurig_guides(self, draw: 'ImageDraw.Draw', W: int, H: int):
        """Draw AcuRig guide handles as coloured circles with name labels.

        Guides are rendered as:
          • Normal guides     – teal circle (r=7) with white name label
          • Selected guide    – bright yellow circle (r=9) with bold label
          • Left-side (l_*)   – left-colour (cornflower blue)
          • Right-side (r_*)  – right-colour (hot pink)
          • Centre (c_*/mid)  – green

        The overlay is drawn on top of the bone skeleton so modders can
        clearly see guide positions relative to the rig.
        """
        guides = getattr(self, '_acurig_guides_overlay', None)
        if not guides:
            return

        selected = getattr(self, '_acurig_selected_guide', '')

        _TEAL   = (0, 220, 180)
        _YELLOW = (255, 220, 0)
        _BLUE   = (100, 160, 255)
        _PINK   = (255, 80, 160)
        _GREEN  = (80, 220, 80)

        for name, guide in guides.items():
            pos = getattr(guide, 'position', None)
            if pos is None:
                continue
            if len(pos) < 3:
                continue

            sp = self._proj(pos[0], pos[1], pos[2], W, H)
            if sp is None:
                continue
            sx, sy, _ = sp

            nl = name.lower()
            if nl.startswith('l_') or nl.endswith('_l'):
                col = _BLUE
            elif nl.startswith('r_') or nl.endswith('_r'):
                col = _PINK
            elif nl.startswith('c_') or 'mid' in nl or 'center' in nl or 'centre' in nl:
                col = _GREEN
            else:
                col = _TEAL

            is_sel = (name == selected)
            r = 9 if is_sel else 7
            outline = _YELLOW if is_sel else col
            fill    = tuple(max(0, c - 80) for c in col)

            draw.ellipse([sx-r, sy-r, sx+r, sy+r], fill=fill, outline=outline, width=2)

            # Diamond crosshair for selected guide
            if is_sel:
                d = 14
                draw.line([sx-d, sy, sx+d, sy], fill=_YELLOW, width=1)
                draw.line([sx, sy-d, sx, sy+d], fill=_YELLOW, width=1)

            # Name label
            try:
                label_col = _YELLOW if is_sel else (200, 230, 255)
                draw.text((sx + r + 3, sy - 6), name, fill=label_col)
            except Exception:
                pass

    def hit_test_acurig_guide(self, mx: int, my: int, radius: int = 14) -> str:
        """
        Return the name of the AcuRig guide whose projected screen circle
        contains the pixel (mx, my), or '' if none.

        We store projected positions during _draw_acurig_guides in a lightweight
        parallel list so this test runs in O(n) without re-projecting.
        """
        guides = getattr(self, '_acurig_guides_overlay', None)
        if not guides:
            return ''
        W = self._last_W if hasattr(self, '_last_W') else 800
        H = self._last_H if hasattr(self, '_last_H') else 600
        best_name = ''
        best_dist2 = radius * radius + 1
        for name, guide in guides.items():
            pos = getattr(guide, 'position', None)
            if pos is None or len(pos) < 3:
                continue
            sp = self._proj(pos[0], pos[1], pos[2], W, H)
            if sp is None:
                continue
            sx, sy, _ = sp
            d2 = (mx - sx) ** 2 + (my - sy) ** 2
            if d2 < best_dist2:
                best_dist2 = d2
                best_name = name
        return best_name

    def _draw_gimbal(self, draw, W: int, H: int):
        """
        Draw a 3-axis translate/rotate gimbal centred on the selected node.

        Translate mode (gimbal_mode==1):
          - Red/Green/Blue axis arrows with arrowheads (X/Y/Z)
          - Yellow/Cyan/Magenta square plane handles (XY, XZ, YZ)
        Rotate mode (gimbal_mode==2):
          - Colour-coded arc rings around each axis
        Scale mode (gimbal_mode==3):
          - White/yellow cube handles; imported root meshes scale uniformly

        Handle screen positions are stored in self._gimbal_handles for
        ViewportWidget hit-testing.
        """
        import math as _gm
        node = self.selected_node
        if not node:
            return
        if self.is_hidden_bone_name(getattr(node, "name", "")):
            self.selected_node = None
            self._gimbal_handles = []
            return
        ext_skel = getattr(self, "_ext_skeleton", None)
        ext_node_ids = set()
        if ext_skel is not None:
            try:
                ext_node_ids = {id(_n) for _n in ext_skel.all_nodes()}
            except Exception:
                ext_node_ids = set()
        if ext_skel is not None and id(node) in ext_node_ids:
            try:
                ox, oy, oz = self._ext_skel_offset
                scale = float(getattr(self, "_ext_skel_scale", 1.0) or 1.0)
                p = node.bone_world_position()
                wp = (p[0] * scale + ox, p[1] * scale + oy, p[2] * scale + oz)
            except Exception:
                wp, _, _ = self._node_world_transform(node)
        elif self.model is not None and node is getattr(self.model, 'root_node', None):
            try:
                bb_min, bb_max = self._get_render_bounds()
                wp = (
                    (float(bb_min[0]) + float(bb_max[0])) * 0.5,
                    (float(bb_min[1]) + float(bb_max[1])) * 0.5,
                    (float(bb_min[2]) + float(bb_max[2])) * 0.5,
                )
            except Exception:
                wp, _, _ = self._node_world_transform(node)
        else:
            wp, _, _ = self._node_world_transform(node)
        cp = self._proj(*wp, W, H)
        if cp is None:
            return
        cx, cy, cz = cp
        self._gimbal_handles = []
        self._gimbal_handle_lines = []

        # Gimbal arm in world units (constant screen size regardless of distance)
        HANDLE_PX = 80
        dist = max(0.5, cz)
        fov_rad = _gm.radians(self.cam.fov)
        world_per_px = (2.0 * dist * _gm.tan(fov_rad * 0.5)) / max(H, 1)
        arm = HANDLE_PX * world_per_px

        axis_colors = {
            'X': getattr(self, "gimbal_x_color", (220, 60, 60)),
            'Y': getattr(self, "gimbal_y_color", (60, 220, 60)),
            'Z': getattr(self, "gimbal_z_color", (60, 120, 220)),
        }
        active_color = getattr(self, "gimbal_active_color", (255, 255, 80))
        active = self.gimbal_active_axis

        if self.gimbal_mode == 1:   # ── Translate ──────────────────
            for name, col in axis_colors.items():
                dx = arm if name == 'X' else 0.0
                dy = arm if name == 'Y' else 0.0
                dz = arm if name == 'Z' else 0.0
                sp = self._proj(wp[0]+dx, wp[1]+dy, wp[2]+dz, W, H)
                if sp is None:
                    continue
                sx, sy, _ = sp
                draw_col = active_color if active == name else col
                lw = 3 if active == name else 2
                draw.line([cx, cy, sx, sy], fill=draw_col, width=lw)
                # Arrowhead
                ddx, ddy = sx - cx, sy - cy
                ll = _gm.sqrt(ddx*ddx + ddy*ddy)
                if ll > 1:
                    ndx, ndy = ddx/ll, ddy/ll
                    px2, py2 = -ndy * 5, ndx * 5
                    draw.polygon([
                        (sx, sy),
                        (int(sx - ndx*10 + px2), int(sy - ndy*10 + py2)),
                        (int(sx - ndx*10 - px2), int(sy - ndy*10 - py2)),
                    ], fill=draw_col)
                self._gimbal_handles.append((sx, sy, name))

            # Plane handles (small squares)
            plane_cfg = {
                'XY': (arm*0.45, arm*0.45, 0.0,      getattr(self, "gimbal_plane_xy_color", (220, 220, 60))),
                'XZ': (arm*0.45, 0.0,      arm*0.45,  getattr(self, "gimbal_plane_xz_color", (60, 220, 220))),
                'YZ': (0.0,      arm*0.45, arm*0.45,  getattr(self, "gimbal_plane_yz_color", (220, 60, 220))),
            }
            for pname, (pdx, pdy, pdz, pcol) in plane_cfg.items():
                sp = self._proj(wp[0]+pdx, wp[1]+pdy, wp[2]+pdz, W, H)
                if sp is None:
                    continue
                px2, py2, _ = sp
                c = active_color if active == pname else pcol
                draw.rectangle([px2-6, py2-6, px2+6, py2+6],
                                fill=c, outline=(255, 255, 255))
                self._gimbal_handles.append((px2, py2, pname))

        elif self.gimbal_mode == 2:   # ── Rotate ─────────────────────
            radius = 50

            def _rotated_ellipse_points(rx: float, ry: float, angle_deg: float, steps: int = 80):
                angle = _gm.radians(angle_deg)
                ca = _gm.cos(angle)
                sa = _gm.sin(angle)
                pts = []
                for i in range(steps + 1):
                    t = (2.0 * _gm.pi * i) / steps
                    ex = rx * _gm.cos(t)
                    ey = ry * _gm.sin(t)
                    pts.append((
                        int(round(cx + ex * ca - ey * sa)),
                        int(round(cy + ex * sa + ey * ca)),
                    ))
                return pts

            def _draw_polyline(points, color, width: int, axis_name: Optional[str] = None) -> None:
                for p0, p1 in zip(points, points[1:]):
                    draw.line([p0[0], p0[1], p1[0], p1[1]], fill=color, width=width)
                    if axis_name:
                        self._gimbal_handle_lines.append((p0[0], p0[1], p1[0], p1[1], axis_name))

            def _draw_hatch(angle_deg: float, color) -> None:
                angle = _gm.radians(angle_deg)
                ux, uy = _gm.cos(angle), _gm.sin(angle)
                vx, vy = -uy, ux
                for offset in range(-radius + 6, radius - 5, 8):
                    half = _gm.sqrt(max(0.0, radius * radius - offset * offset))
                    x0 = cx + vx * offset - ux * half
                    y0 = cy + vy * offset - uy * half
                    x1 = cx + vx * offset + ux * half
                    y1 = cy + vy * offset + uy * half
                    draw.line([int(x0), int(y0), int(x1), int(y1)], fill=color, width=1)

            # Light cross-hatch inside the rotation sphere so it reads as a
            # manipulable volume rather than three unrelated screen arcs.
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                outline=(78, 86, 96),
                width=1,
            )
            _draw_hatch(35.0, (58, 64, 72))
            _draw_hatch(-35.0, (42, 48, 56))

            ring_cfg = {
                'X': (radius * 0.42, radius,      -14.0, axis_colors['X'], "Rot X", 0.75),
                'Y': (radius * 0.42, radius,       14.0, axis_colors['Y'], "Rot Y", 0.25),
                'Z': (radius,        radius * 0.34,  0.0, axis_colors['Z'], "Rot Z", 0.00),
            }
            for name, (rx, ry, angle_deg, col, label, handle_t) in ring_cfg.items():
                pts = _rotated_ellipse_points(rx, ry, angle_deg)
                shadow = tuple(max(0, c - 90) for c in col)
                ring_col = active_color if active == name else col
                _draw_polyline(pts, shadow, 5 if active == name else 4)
                _draw_polyline(pts, ring_col, 3 if active == name else 2, name)

                hi = int(round(handle_t * (len(pts) - 1))) % (len(pts) - 1)
                hx, hy = pts[hi]
                draw.ellipse([hx - 5, hy - 5, hx + 5, hy + 5],
                             fill=ring_col, outline=(20, 22, 26))
                self._gimbal_handles.append((hx, hy, name))
                try:
                    draw.text((hx + 7, hy - 7), label, fill=ring_col)
                except Exception:
                    pass

        elif self.gimbal_mode == 3:   # ── Scale ──────────────────────
            for name, col in axis_colors.items():
                dx = arm if name == 'X' else 0.0
                dy = arm if name == 'Y' else 0.0
                dz = arm if name == 'Z' else 0.0
                sp = self._proj(wp[0]+dx, wp[1]+dy, wp[2]+dz, W, H)
                if sp is None:
                    continue
                sx, sy, _ = sp
                draw_col = active_color if active == name else col
                draw.line([cx, cy, sx, sy], fill=draw_col, width=2)
                draw.rectangle([sx-6, sy-6, sx+6, sy+6],
                               fill=draw_col, outline=(255, 255, 255))
                self._gimbal_handles.append((sx, sy, name))
            draw.rectangle([cx-7, cy-7, cx+7, cy+7],
                           fill=(255, 255, 255), outline=(255, 212, 0))
            self._gimbal_handles.append((cx, cy, 'S'))

        # Centre dot
        draw.ellipse([cx-4, cy-4, cx+4, cy+4],
                      fill=(255, 255, 255), outline=(150, 150, 150))
        mode_lbl = {1: "Translate", 2: "Rotate", 3: "Scale"}.get(self.gimbal_mode, "Translate")
        try:
            draw.text((cx+6, cy-14), f"[{mode_lbl}] {node.name}",
                       fill=getattr(self, "gimbal_text_color", (200, 200, 200)))
        except Exception:
            pass

    def hit_test_gimbal(self, sx: int, sy: int, radius: int = 10):
        """Return axis/plane name if (sx,sy) is within radius of a gimbal handle, else None."""
        best_axis = None
        best_d2   = radius * radius
        for hx, hy, axis in self._gimbal_handles:
            d2 = (hx - sx)**2 + (hy - sy)**2
            if d2 < best_d2:
                best_d2 = d2
                best_axis = axis
        line_radius2 = best_d2 if best_axis is not None else (radius + 4) * (radius + 4)
        for x0, y0, x1, y1, axis in getattr(self, "_gimbal_handle_lines", []) or []:
            vx = x1 - x0
            vy = y1 - y0
            seg_len2 = vx * vx + vy * vy
            if seg_len2 <= 1e-6:
                continue
            t = ((sx - x0) * vx + (sy - y0) * vy) / seg_len2
            if t < 0.0 or t > 1.0:
                continue
            px = x0 + t * vx
            py = y0 + t * vy
            d2 = (px - sx) ** 2 + (py - sy) ** 2
            if d2 < line_radius2:
                line_radius2 = d2
                best_axis = axis
        return best_axis

    # ── Character Builder fit evidence overlay ───────────────────────

    def set_character_fit_overlay(self, overlay: dict | None):
        """Register Character Builder auto-fit evidence for viewport drawing."""
        self._character_fit_overlay = overlay if isinstance(overlay, dict) else None
        redraw = getattr(self, "redraw", None)
        if callable(redraw):
            redraw()

    def _draw_character_fit_overlay(self, draw, W: int, H: int):
        """Draw headless auto-fit axes and landmarks from core report metadata."""
        overlay = getattr(self, "_character_fit_overlay", None)
        if not isinstance(overlay, dict):
            return

        source = overlay.get("source") if isinstance(overlay.get("source"), dict) else None
        target = overlay.get("target") if isinstance(overlay.get("target"), dict) else None
        if source is None and target is None:
            return

        source_col = tuple(getattr(self, "gimbal_active_color", (255, 255, 80)))[:3]
        target_col = tuple(getattr(self, "gimbal_plane_yz_color", (220, 60, 220)))[:3]
        text_col = tuple(getattr(self, "gimbal_text_color", getattr(self, "viewport_text", (200, 200, 200))))[:3]

        def _point(value):
            try:
                if value is None or len(value) < 3:
                    return None
                return (float(value[0]), float(value[1]), float(value[2]))
            except Exception:
                return None

        def _axis_color(axis_label: str):
            axis = str(axis_label or "").lower()[-1:]
            if axis == "x":
                return tuple(getattr(self, "gimbal_x_color", (220, 60, 60)))[:3]
            if axis == "y":
                return tuple(getattr(self, "gimbal_y_color", (60, 220, 60)))[:3]
            if axis == "z":
                return tuple(getattr(self, "gimbal_z_color", (60, 120, 220)))[:3]
            return text_col

        def _draw_group(group: dict, label: str, landmark_col):
            origin = _point(group.get("origin"))
            if origin is not None:
                sp = self._proj(origin[0], origin[1], origin[2], W, H)
                if sp:
                    sx, sy, _ = sp
                    draw.ellipse([sx - 5, sy - 5, sx + 5, sy + 5], outline=landmark_col, width=2)
                    try:
                        draw.text((sx + 7, sy - 7), label, fill=landmark_col)
                    except Exception:
                        pass
            axes = group.get("axes") if isinstance(group.get("axes"), dict) else {}
            for axis_name, axis in axes.items():
                if not isinstance(axis, dict):
                    continue
                end = _point(axis.get("end"))
                if origin is None or end is None:
                    continue
                osp = self._proj(origin[0], origin[1], origin[2], W, H)
                esp = self._proj(end[0], end[1], end[2], W, H)
                if not (osp and esp):
                    continue
                col = _axis_color(str(axis.get("axis_label") or axis_name))
                draw.line([osp[0], osp[1], esp[0], esp[1]], fill=col, width=2)
                try:
                    draw.text((esp[0] + 4, esp[1] - 6), str(axis_name)[:1].upper(), fill=col)
                except Exception:
                    pass
            landmarks = group.get("landmarks") if isinstance(group.get("landmarks"), list) else []
            for item in landmarks[:12]:
                if not isinstance(item, dict):
                    continue
                pos = _point(item.get("position"))
                if pos is None:
                    continue
                sp = self._proj(pos[0], pos[1], pos[2], W, H)
                if not sp:
                    continue
                sx, sy, _ = sp
                draw.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=landmark_col, outline=text_col)

        if source is not None:
            _draw_group(source, "fit source", source_col)
        if target is not None:
            _draw_group(target, "KOTOR base", target_col)

    # ── External skeleton overlay ─────────────────────────────────────

    def _draw_ext_skeleton(self, draw, W: int, H: int):
        """
        Render an external skeleton (loaded from a separate MDL file) as
        a ghost overlay in purple, offset by _ext_skel_offset.
        Used for the 'Load External Skeleton' rigging workflow.
        """
        if not self._ext_skeleton or not self._ext_skeleton.root_node:
            self._ext_bone_screen_positions = []
            return
        ox, oy, oz = self._ext_skel_offset
        scale = float(getattr(self, '_ext_skel_scale', 1.0) or 1.0)
        EXT_DOT  = (180,  80, 255)
        EXT_LINE = (130,  50, 200)
        EXT_SEL  = (255, 200,  80)
        ext_selected = getattr(self, '_ext_skel_selected_node', None)
        ext_selected_ids = set(getattr(self, "_ext_skel_selected_ids", set()) or set())
        self._ext_bone_screen_positions = []

        def _bp(node):
            p = node.bone_world_position()
            return (p[0]*scale+ox, p[1]*scale+oy, p[2]*scale+oz)

        def _draw_ext_bone(node):
            """Draw one ext-skeleton bone node."""
            wp2 = _bp(node)
            sp  = self._proj(*wp2, W, H)
            is_sel = (node is ext_selected)
            col = EXT_SEL if is_sel else EXT_DOT
            if sp:
                self._ext_bone_screen_positions.append((sp[0], sp[1], sp[2], node))
                is_multi_sel = is_sel or id(node) in ext_selected_ids
                r = 5 if is_multi_sel else 3
                col = EXT_SEL if is_multi_sel else EXT_DOT
                draw.ellipse([sp[0]-r, sp[1]-r, sp[0]+r, sp[1]+r],
                              fill=col, outline=None)
                if is_multi_sel:
                    try:
                        draw.text((sp[0]+4, sp[1]-6), node.name,
                                   fill=(160, 100, 220))
                    except Exception:
                        pass
            if node.parent:
                pp2 = _bp(node.parent)
                spp = self._proj(*pp2, W, H)
                if sp and spp:
                    draw.line([sp[0], sp[1], spp[0], spp[1]],
                               fill=EXT_LINE, width=1)

        # Iterative BFS — avoid recursion limit on deep ext-skeleton hierarchies
        _ext_stack = [self._ext_skeleton.root_node]
        _ext_visited: set = set()
        while _ext_stack:
            _n = _ext_stack.pop()
            _nid = id(_n)
            if _nid in _ext_visited:
                continue
            _ext_visited.add(_nid)
            _draw_ext_bone(_n)
            for c in reversed(_n.children):
                if id(c) not in _ext_visited:
                    _ext_stack.append(c)

    # ── Walkmesh overlay (Phase 16.1) ─────────────────────────────────

    def _draw_walkmesh_overlay(self, draw: 'ImageDraw.Draw', W: int, H: int):
        """
        Draw the loaded walkmesh overlay as semi-transparent colored triangles.
        Surface types are color-coded (green=walkable, red=blocked, blue=water, etc.).
        Called after mesh/bone rendering so it appears on top.
        """
        overlay = self._walkmesh_overlay
        if overlay is None or not WalkmeshOverlay:
            return
        proxy_node = getattr(overlay, "_gr_module_node", None)
        if proxy_node is not None and getattr(proxy_node, "_gr_hidden", False):
            return
        try:
            faces = overlay.faces_for_render(
                show_walkable=self.show_walkmesh_walk,
                show_non_walkable=self.show_walkmesh_block)
        except Exception:
            return
        if not faces:
            return

        _bg_for_blend = tuple(getattr(self, "viewport_background", _BG[:3]))
        _BG_R, _BG_G, _BG_B = _bg_for_blend[0], _bg_for_blend[1], _bg_for_blend[2]

        for face in faces:
            try:
                p0 = self._proj(face.v0[0], face.v0[1], face.v0[2], W, H)
                p1 = self._proj(face.v1[0], face.v1[1], face.v1[2], W, H)
                p2 = self._proj(face.v2[0], face.v2[1], face.v2[2], W, H)
            except Exception:
                continue
            if not (p0 and p1 and p2):
                continue

            # face.color is (R,G,B,A) with components in [0.0, 1.0]
            # Blend fill color with background for semi-transparency
            cr, cg, cb, ca = face.color
            # ca is already 0.0-1.0; scale RGB channels to 0-255 for blending
            cr8 = int(cr * 255); cg8 = int(cg * 255); cb8 = int(cb * 255)
            alpha = ca  # 0.0-1.0
            fr = int(cr8 * alpha + _BG_R * (1.0 - alpha))
            fg = int(cg8 * alpha + _BG_G * (1.0 - alpha))
            fb = int(cb8 * alpha + _BG_B * (1.0 - alpha))
            pts = [p0[0], p0[1], p1[0], p1[1], p2[0], p2[1]]
            try:
                draw.polygon(pts, fill=(fr, fg, fb), outline=(cr8, cg8, cb8))
            except Exception:
                pass

    def load_walkmesh(self, wok_data_or_path, world_offset=(0.0, 0.0, 0.0)):
        """
        Load a walkmesh overlay from a WOKData object or file path.
        Stores it in self._walkmesh_overlay; toggled with show_walkmesh.

        Parameters
        ----------
        wok_data_or_path : WOKData instance, file path string, or None to clear.
        world_offset     : (x, y, z) offset to apply to all vertices.
        """
        if not WalkmeshOverlay or not WalkmeshLoader:
            log.debug("walkmesh_renderer not available – walkmesh overlay skipped")
            self._walkmesh_overlay = None
            return
        if wok_data_or_path is None:
            self._walkmesh_overlay = None
            return
        try:
            if isinstance(wok_data_or_path, str):
                loader = WalkmeshLoader()
                overlay = loader.from_file(wok_data_or_path, world_offset)
            else:
                loader = WalkmeshLoader()
                overlay = loader.from_wok_data(wok_data_or_path, world_offset)
            self._walkmesh_overlay = overlay
            log.info(f"Walkmesh loaded: {overlay.summary() if overlay else 'none'}")
        except Exception as e:
            log.warning(f"Walkmesh load failed: {e}")
            self._walkmesh_overlay = None

    def clear_walkmesh(self):
        """Remove the walkmesh overlay."""
        self._walkmesh_overlay = None

    def toggle_walkmesh(self):
        """Toggle walkmesh overlay visibility."""
        self.show_walkmesh = not self.show_walkmesh
        self._request_render()

    # ── Rig-edit mode banner (Phase 22) ──────────────────────────────

    def _draw_rig_edit_banner(self, draw: 'ImageDraw.Draw', W: int, H: int):
        """
        Draw a prominent orange banner at the top of the viewport when in
        rig-edit mode, reminding the user to drag bones and confirm.
        """
        try:
            bh = 26
            # Semi-transparent orange strip
            draw.rectangle([0, 0, W, bh], fill=(180, 80, 0))
            msg = (
                "  ✦ RIG EDIT MODE  –  Drag bone joints to adjust  ·  "
                "Click 'Confirm Rig' in the Retarget panel when done"
            )
            draw.text((6, 5), msg, fill=(255, 230, 140))
        except Exception:
            pass

    # ── Axes gizmo ────────────────────────────────────────────────────

    def _draw_axes(self, draw: 'ImageDraw.Draw', W: int, H: int):
        ox, oy = 42, H - 42
        L      = 26
        right, up, fwd, _ = self._cam_view_matrix()

        def axis_end(ax):
            dx = _dot(ax, right)
            dy = _dot(ax, up)
            return int(ox + dx*L), int(oy - dy*L)

        x_end = axis_end((1,0,0))
        y_end = axis_end((0,1,0))
        z_end = axis_end((0,0,1))

        draw.ellipse([ox - 25, oy - 25, ox + 25, oy + 25], fill=(12, 14, 16), outline=(68, 76, 86))
        draw.line([ox,oy, x_end[0],x_end[1]], fill=_AXIS_X[:3], width=2)
        draw.line([ox,oy, y_end[0],y_end[1]], fill=_AXIS_Y[:3], width=2)
        draw.line([ox,oy, z_end[0],z_end[1]], fill=_AXIS_Z[:3], width=2)

        try:
            draw.text((x_end[0]+3, x_end[1]-6), "X", fill=_AXIS_X[:3])
            draw.text((y_end[0]+3, y_end[1]-6), "Y", fill=_AXIS_Y[:3])
            draw.text((z_end[0]+3, z_end[1]-6), "Z↑", fill=_AXIS_Z[:3])
        except Exception:
            pass

    # ── Stats HUD ─────────────────────────────────────────────────────

    @staticmethod
    def _hud_text_width(text: str) -> int:
        return max(18, len(str(text)) * 6)

    def _fit_hud_text(self, text: str, max_width: int | None, *, pad_x: int = 7) -> str:
        text = str(text or "")
        if max_width is None or max_width <= 0:
            return text
        content_width = max(18, int(max_width) - pad_x * 2)
        if self._hud_text_width(text) <= content_width:
            return text
        ellipsis = "..."
        if content_width <= self._hud_text_width(ellipsis):
            return ellipsis
        max_chars = max(1, (content_width - self._hud_text_width(ellipsis)) // 6)
        return text[:max_chars].rstrip() + ellipsis

    def _hud_pill_width(self, text: str, *, max_width: int | None = None, pad_x: int = 7) -> int:
        fitted = self._fit_hud_text(text, max_width, pad_x=pad_x)
        width = self._hud_text_width(fitted) + pad_x * 2
        if max_width is not None:
            width = min(width, max(1, int(max_width)))
        return width

    def _draw_hud_pill(
        self,
        draw: 'ImageDraw.Draw',
        x: int,
        y: int,
        text: str,
        *,
        fill=(30, 34, 40),
        fg=(213, 220, 230),
        outline=(78, 88, 102),
        max_width: int | None = None,
    ) -> int:
        pad_x = 7
        text = self._fit_hud_text(text, max_width, pad_x=pad_x)
        width = self._hud_pill_width(text, max_width=max_width, pad_x=pad_x)
        height = 17
        draw.rectangle([x, y, x + width, y + height], fill=fill, outline=outline)
        draw.text((x + pad_x, y + 4), text, fill=fg)
        return width

    def _draw_hud_panel_lines(
        self,
        draw: 'ImageDraw.Draw',
        W: int,
        H: int,
        lines: list[str],
        *,
        placement: str = "center",
        fill=(18, 22, 27),
        fg=(132, 205, 255),
        outline=(45, 105, 155),
    ) -> None:
        lines = [str(line or "") for line in lines if str(line or "")]
        if not lines:
            return
        pad_x = 10
        pad_y = 7
        line_h = 15
        width = max(self._hud_text_width(line) for line in lines) + pad_x * 2
        height = pad_y * 2 + line_h * len(lines)
        x = max(8, (W - width) // 2)
        if placement == "bottom":
            y = max(44, H - height - 18)
        else:
            y = max(8, (H - height) // 2)
        draw.rectangle([x, y, x + width, y + height], fill=fill, outline=outline)
        for index, line in enumerate(lines):
            text_x = x + max(pad_x, (width - self._hud_text_width(line)) // 2)
            text_y = y + pad_y + index * line_h
            draw.text((text_x, text_y), line, fill=fg)

    def _draw_stats(self, draw: 'ImageDraw.Draw', W: int, H: int):
        hud_fill = getattr(self, "hud_fill", (30, 34, 40))
        hud_text = getattr(self, "hud_text", (213, 220, 230))
        hud_outline = getattr(self, "hud_outline", (78, 88, 102))
        hud_muted = getattr(self, "hud_muted_text", (165, 176, 190))
        success_fill = getattr(self, "hud_success_fill", (25, 43, 37))
        success_text = getattr(self, "hud_success_text", (138, 230, 178))
        warning_fill = getattr(self, "hud_warning_fill", (68, 44, 22))
        warning_text = getattr(self, "hud_warning_text", (255, 190, 95))
        if not self.model:
            self._draw_hud_pill(draw, 12, 12, "Empty Scene", fill=hud_fill, fg=hud_muted, outline=hud_outline)
            return
        vc = bc = fc = tex_ok = tex_total = uv_ok = 0
        # Cache visible mesh nodes list for this stats call (avoid 3× iteration)
        visible_nodes = list(self._iter_visible_mesh_nodes())
        # Use _iter_visible_mesh_nodes so outlier skin proxies are excluded from V/F counts
        for n in visible_nodes:
            vc += len(n.vertices)
            fc += len(n.faces)
            if n.texture and _clean_tex_name(n.texture).upper() not in ('NULL',''):
                tex_total += 1
                if self._get_tex(n):
                    tex_ok += 1
            if len(n.uvs) == len(n.vertices) and n.vertices:
                uv_ok += 1
        stack = [self.model.root_node]
        _bc_visited: set = set()
        while stack:
            n = stack.pop()
            if n is None:
                continue
            nid = id(n)
            if nid in _bc_visited:
                continue
            _bc_visited.add(nid)
            if not n.is_mesh:
                bc += 1
            stack.extend(c for c in n.children if c is not None)
        skin_nodes = sum(1 for n in visible_nodes if n.is_skin)
        mode_str = "Textured" if (self.show_texture and self.show_solid and not self.is_interactive) else \
                   "Fast shaded" if (self.show_texture and self.show_solid and self.is_interactive) else \
                   "Flat"
        uv_mesh  = sum(1 for n in visible_nodes if n.vertices)
        # Game version string
        try:
            from src.core.geometry.model_data import GameVersion
        except ImportError:
            from core.geometry.model_data import GameVersion  # type: ignore
        gv_str = "K1" if self.model.game_version == GameVersion.K1 else "K2"
        model_name = str(getattr(self.model, "name", "model") or "model")
        if len(model_name) > 34:
            model_name = model_name[:31] + "..."
        hud_left = 12
        hud_gap = 6
        hud_row_step = 22
        # Keep top-left HUD content out of the viewcube lane on typical widths,
        # while still using most of the canvas on compact/offscreen captures.
        hud_right_limit = max(hud_left + 120, W - 172)
        hud_max_width = max(96, hud_right_limit - hud_left)
        x = hud_left
        y = 12
        model_label = f"{model_name}  [{gv_str}]"
        mode_width = self._hud_pill_width(mode_str)
        model_max_width = max(64, hud_right_limit - x - mode_width - hud_gap)
        x += self._draw_hud_pill(
            draw,
            x,
            y,
            model_label,
            fill=hud_fill,
            fg=hud_text,
            outline=hud_outline,
            max_width=model_max_width,
        ) + hud_gap
        if x + mode_width > hud_right_limit:
            x = hud_left
            y += hud_row_step
        x += self._draw_hud_pill(draw, x, y, mode_str, fill=success_fill, fg=success_text, outline=hud_outline) + hud_gap
        if self.show_bones:
            bones_txt = f"Bones {bc}"
            bones_width = self._hud_pill_width(bones_txt)
            if x + bones_width > hud_right_limit:
                x = hud_left
                y += hud_row_step
            x += self._draw_hud_pill(draw, x, y, bones_txt, fill=warning_fill, fg=warning_text, outline=hud_outline) + hud_gap
        stats_row_y = y + hud_row_step
        compact_stats = f"V {vc:,}  F {fc:,}  Skin {skin_nodes}  UV {uv_ok}/{uv_mesh}  Tex {tex_ok}/{tex_total}"
        self._draw_hud_pill(
            draw,
            hud_left,
            stats_row_y,
            compact_stats,
            fill=hud_fill,
            fg=hud_muted,
            outline=hud_outline,
            max_width=hud_max_width,
        )
        animation_row_y = stats_row_y + hud_row_step
        if self._anim_pose is not None and self._anim_name:
            anim_txt = f"\u25b6 {self._anim_name}"
            if self._anim_length > 0:
                pct = int(100 * self._anim_time / self._anim_length)
                anim_txt += f"  {self._anim_time:.3f}/{self._anim_length:.3f}s  [{pct}%]"
            self._draw_hud_pill(
                draw,
                12,
                animation_row_y,
                anim_txt,
                fill=success_fill,
                fg=success_text,
                outline=hud_outline,
                max_width=hud_max_width,
            )
        # Show render bounds info — use CACHED value (not recomputed every frame)
        rbb_min, rbb_max = self._get_render_bounds()
        dx = rbb_max[0]-rbb_min[0]; dy = rbb_max[1]-rbb_min[1]; dz = rbb_max[2]-rbb_min[2]
        bounds_txt = f"{dx:.2f} x {dy:.2f} x {dz:.2f} m"
        bounds_max_width = max(80, min(220, W - 24))
        bounds_width = self._hud_pill_width(bounds_txt, max_width=bounds_max_width)
        self._draw_hud_pill(
            draw,
            max(12, W - bounds_width - 12),
            max(12, H - 28),
            bounds_txt,
            fill=hud_fill,
            fg=hud_muted,
            outline=hud_outline,
            max_width=bounds_max_width,
        )
        if vc == 0:
            if is_animation_supermodel(self.model):
                self._draw_hud_panel_lines(
                    draw,
                    W,
                    H,
                    ["Animation supermodel loaded", "Skeleton and clips only"],
                    placement=getattr(self, "animation_supermodel_hud_placement", "center"),
                    fill=hud_fill,
                    fg=hud_text,
                    outline=hud_outline,
                )
                return
            # Context-aware "no geometry" message:
            # Check if ALL mesh nodes have render=False (intentional invisible model)
            # vs. model truly has no geometry at all
            #
            # FIX Phase 16.2: Detect reference-only models (NodeFlags.REFERENCE = 0x0010).
            # These are compound models that delegate geometry to external MDL files.
            # Show an informative "⊕ References external model(s):" message instead of
            # the generic "No renderable geometry" warning.
            try:
                _ref_names = [
                    n.emitter_params.get('ref_model', n.name)
                    for n in self.model.all_nodes()
                    if getattr(n, 'is_reference', False)
                ]
            except Exception:
                _ref_names = []
            if _ref_names:
                ref_list = ', '.join(_ref_names[:3])
                if len(_ref_names) > 3:
                    ref_list += f' (+{len(_ref_names)-3} more)'
                draw.text((W//2 - 200, H//2 - 16),
                          "⊕ Reference model – geometry loaded at runtime",
                          fill=(120, 200, 255))
                draw.text((W//2 - 200, H//2),
                          f"  References: {ref_list}",
                          fill=(100, 170, 220))
                return
            all_mesh = list(self._iter_mesh_nodes())
            has_any_verts = any(getattr(n,'vertices',None) for n in all_mesh)
            all_render_false = has_any_verts and all(
                not getattr(n,'render',True) for n in all_mesh
                if getattr(n,'vertices',None)
            )
            name_lower = self.model.name.lower() if self.model and self.model.name else ''
            # Broad non-visual classification — covers VFX, cameras, lights, mini-game
            # helpers, stunt-room scaffolding, level-only environment helpers, and
            # special purpose models that intentionally contain zero renderable geometry.
            # Patterns observed in K1/K2 game data (748 models total):
            #   v_*, fx_*, fx* → VFX / weapon beam / muzzle flash
            #   *cam, *camera → camera placeholder
            #   *_light, *_intlight, *_sun, *light → light dummy
            #   *_mgm*, *_mgt*, *_mgo*, *_mgv*, *mg_* → mini-game sequence models
            #   stuntroom* → cutscene stunt-room scaffolding
            #   mgb_null, mgg_null, *_null → null/placeholder entries
            #   empty, galaxy → engine special placeholders
            #   Numbered area models (e.g. 102perz2, 302narli, 601dand, 421dxn*)
            #     → area-specific environment / camera helpers with no visible mesh
            #   plc_* (smoke/spark/steam/mist/emitter placeables) → all-emitter, no mesh
            #   c_lightsaber → lightsaber blade is pure VFX emitter
            #   w_lfire_* → laser fire beam VFX
            #   w_null_* → weapon null placeholder
            #   m##_set, m##_hd, m##light, m##_camera, m##_char* → level sub-models
            import re as _re
            is_nonvisual = (
                name_lower.startswith('fx_')
                or name_lower.startswith('fx')   # fxmuzzle, fxsmoke, etc.
                or name_lower.startswith('v_')
                or name_lower.startswith('w_laser')
                or name_lower.startswith('w_lfire')  # w_lfire_pb_b1 etc.
                or name_lower.startswith('w_null')
                or name_lower == 'c_lightsaber'  # pure VFX emitter
                or name_lower.endswith('cam')
                or name_lower.endswith('_cam')
                or name_lower.endswith('camera')
                or name_lower.endswith('_light')
                or name_lower.endswith('_intlight')
                or name_lower.endswith('_sun')
                or name_lower.endswith('light')   # m14light etc.
                or '_mgt' in name_lower
                or '_mgo' in name_lower
                or '_mgm' in name_lower
                or '_mgv' in name_lower
                or '_mg_' in name_lower            # m03mg_01b, m26mg_01c
                or name_lower.endswith('_null')
                or name_lower in ('empty', 'galaxy', 'mgb_null', 'mgg_null',
                                  'mg_distort', 'lmg_distort')
                or name_lower.startswith('stuntroom')
                # plc_ models that are pure emitter/VFX (smoke, sparks, steam, mist)
                # — all confirmed to have 0 mesh nodes in audit
                or name_lower.startswith('plc_')
                # Numbered area helpers: 3+ digit prefix then letter code (e.g. 102perz2)
                or bool(_re.match(r'^\d{3}[a-z]', name_lower))
                # Level sub-models: *_set, *_hd, m##_char*, m##mg* (mini-game level)
                or bool(_re.match(r'^m\d+[a-z]*_(set|hd|char)', name_lower))
                or bool(_re.match(r'^m\d+mg', name_lower))   # m03mg_01b, m26mg_01c
                or name_lower.endswith('_set')                # m05aa_set, m28ac_set
                or name_lower.endswith('_hd')                 # m26ad_hd
                # Module area instance models:
                #   m##xx_##x  (e.g. m13aa_01f, m14ab_02d, m22aa_06a)
                #   m##xx_##   (e.g. m34aa_09, m37aa_17, m38aa_12)
                #   m##xx_c##_char##  (e.g. m13aa_c01_char04)
                # These are environment/sound/event scaffolding with no mesh
                or bool(_re.match(r'^m\d{2}[a-z]{2,4}_\d{2}[a-z]?$', name_lower))
                or bool(_re.match(r'^m\d{2}[a-z]{2}_c\d+_char\d+$', name_lower))
                # NPC dummy markers
                or name_lower == 'n_admoff'
                # Weapon LOD placeholder slots (e.g. w_blstrcrbn_006, w_ionrfl_004)
                or bool(_re.match(r'^w_.+_0{1,2}[346]$', name_lower))
            )
            if is_nonvisual or (len(all_mesh) == 0):
                warn = "ℹ Non-visual model (VFX / camera / helper – no display geometry)"
                warn_col = (100, 150, 220)
            elif all_render_false:
                warn = "ℹ All geometry has render=False (engine-internal LOD / collision proxy)"
                warn_col = (150, 180, 100)
            else:
                warn = "⚠ No renderable geometry – check MDL/MDX paths"
                warn_col = (255, 120, 80)
            bbox = draw.textbbox((0, 0), warn)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.text(((W - text_w) // 2, max(12, H - 72 - text_h)), warn, fill=warn_col)
        elif self.show_texture and tex_ok == 0 and tex_total > 0:
            warn = f"⚠ {tex_total} texture(s) referenced but none loaded – set texture directory"
            warn_y = animation_row_y + hud_row_step if (self._anim_pose is not None and self._anim_name) else stats_row_y + hud_row_step
            self._draw_hud_pill(
                draw,
                hud_left,
                warn_y,
                warn,
                fill=warning_fill,
                fg=warning_text,
                outline=hud_outline,
                max_width=hud_max_width,
            )

        # Show animation progress without overlapping the bottom-right FPS indicator.
        if self._anim_pose is not None and self._anim_name:
            bar_h = 4
            bar_y = H - bar_h
            draw.rectangle([0, bar_y, W, H], fill=hud_fill)
            if self._anim_length > 0:
                bar_w = int(W * min(1.0, self._anim_time / self._anim_length))
                draw.rectangle([0, bar_y, bar_w, H], fill=success_text)
        elif not self._anim_pose:
            # Show "Bind Pose" indicator when in rest position
            pose_txt = "Bind pose"
            self._draw_hud_pill(
                draw,
                max(12, W - self._hud_text_width(pose_txt) - 26),
                12,
                pose_txt,
                fill=hud_fill,
                fg=hud_muted,
                outline=hud_outline,
            )
