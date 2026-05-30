"""RendererRenderLoopMixin methods for the viewport frame renderer."""

from __future__ import annotations

from .mixin_imports import *  # noqa: F401,F403


class RendererRenderLoopMixin:
    def _cam_view_matrix(self):
        """Return (right, up, fwd, eye) from the camera, supporting both
        ArcBallCamera objects (which have _view_matrix()) and duck-typed
        camera objects (which only have eye, target, up attributes).

        FIX-HEADLESS-CAM: render_model_autoframe / _render_cpu pass a plain
        namespace camera with no _view_matrix() method.  This shim computes
        the view matrix from the raw eye/target/up attributes so that
        FrameRenderer works in headless/batch mode without an ArcBallCamera.
        """
        if callable(getattr(self.cam, '_view_matrix', None)):
            return self.cam._view_matrix()
        # Duck-typed camera: compute view matrix from eye/target/up
        _eye = self.cam.eye
        if callable(_eye):
            _eye = _eye()
        target = getattr(self.cam, 'target', (0.0, 0.0, 0.0))
        world_up_hint = getattr(self.cam, 'up', (0.0, 0.0, 1.0))
        fwd = _normalize(_sub(target, _eye))
        right = _normalize(_cross(fwd, world_up_hint))
        if _dot(right, right) < 1e-6:
            # up is parallel to fwd — use fallback world-up
            _fb = (0.0, 1.0, 0.0) if abs(world_up_hint[2]) > 0.9 else (0.0, 0.0, 1.0)
            right = _normalize(_cross(fwd, _fb))
        up = _cross(right, fwd)
        return right, up, fwd, _eye

    def render(self, W: int, H: int) -> Optional['Image.Image']:
        if not _PIL:
            return None
        # Wrap the entire render in a MemoryError guard so any PIL allocation
        # failure returns None rather than propagating up to crash the app.
        try:
            return self._render_inner(W, H)
        except MemoryError:
            log.warning(f"FrameRenderer.render: MemoryError at {W}x{H} — returning None")
            return None
        except Exception as exc:
            log.warning(f"FrameRenderer.render: unhandled error: {exc}", exc_info=True)
            return None

    def render_still(self, W: int, H: int,
                     az_deg: float = -45.0, el_deg: float = 20.0,
                     fov: float = 45.0) -> Optional['Image.Image']:
        """
        High-quality offline/still render — bypasses the interactive triangle cap.

        Uses MAX_TRIS_TEXTURED_STILL (50k tris) so that every visible face is
        rendered regardless of model complexity.  Temporarily overrides the camera
        angle and restores it afterwards so the viewport state is unchanged.

        Usage:
            img = renderer.render_still(1024, 1024, az_deg=-60, el_deg=25)
            img.save("my_model.png")

        Args:
            W, H       : output image dimensions in pixels
            az_deg     : camera azimuth angle in degrees (default -45°)
            el_deg     : camera elevation angle in degrees (default 20°)
            fov        : camera field-of-view in degrees (default 45°)

        Returns:
            PIL Image in RGB mode, or None on failure.
        """
        if not _PIL:
            return None
        # Save current camera state
        _saved_az  = getattr(self.cam, 'az',  -45.0)
        _saved_el  = getattr(self.cam, 'el',   20.0)
        _saved_azimuth = getattr(self.cam, 'azimuth', None)
        _saved_elevation = getattr(self.cam, 'elevation', None)
        _saved_fov = getattr(self.cam, 'fov',  45.0)
        # Temporarily raise triangle cap to still-render budget
        _saved_cap = self.__class__.MAX_TRIS_TEXTURED
        try:
            self.__class__.MAX_TRIS_TEXTURED = self.__class__.MAX_TRIS_TEXTURED_STILL
            # Override camera angles if accessible
            if hasattr(self.cam, 'az'):
                self.cam.az = az_deg
            if hasattr(self.cam, 'azimuth'):
                self.cam.azimuth = az_deg
            if hasattr(self.cam, 'el'):
                self.cam.el = el_deg
            if hasattr(self.cam, 'elevation'):
                self.cam.elevation = el_deg
            if hasattr(self.cam, 'fov'):
                self.cam.fov = fov
            return self.render(W, H)
        except Exception as exc:
            log.warning(f"FrameRenderer.render_still: {exc}", exc_info=True)
            return None
        finally:
            # Always restore original state
            self.__class__.MAX_TRIS_TEXTURED = _saved_cap
            if hasattr(self.cam, 'az'):  self.cam.az  = _saved_az
            if hasattr(self.cam, 'el'):  self.cam.el  = _saved_el
            if _saved_azimuth is not None and hasattr(self.cam, 'azimuth'):
                self.cam.azimuth = _saved_azimuth
            if _saved_elevation is not None and hasattr(self.cam, 'elevation'):
                self.cam.elevation = _saved_elevation
            if hasattr(self.cam, 'fov'): self.cam.fov = _saved_fov

    def _render_inner(self, W: int, H: int) -> Optional['Image.Image']:
        if not _PIL:
            return None
        # Track last rendered dimensions for hit-testing (AcuRig guide drag etc.)
        self._last_W = W
        self._last_H = H
        # Only clear the world-transform cache when the model or animation
        # pose actually changes — NOT every frame.  Clearing every frame forced
        # a full O(n_bones²) parent-chain walk on every render tick, making the
        # bantha (~40 bones × ~6000 verts) extremely laggy.
        # The cache is already invalidated by set_model() and set_animation_pose().
        # Here we only clear it if the model identity has changed (safety net).
        if self.model and id(self.model) != getattr(self, '_cached_model_id', -1):
            self._wt_cache.clear()
            self._cached_model_id = id(self.model)

        # Auto-compute outlier skin nodes if not yet done for this model
        # (ensures headless/batch renders also benefit from outlier filtering)
        if self.model and id(self.model) != self._outlier_model_id:
            self._compute_outlier_skin_nodes(self.model)
            self._outlier_model_id = id(self.model)

        # Cache view matrix for this frame so _proj() doesn't recompute it
        # per-triangle (saves significant CPU for high-poly models like bantha)
        # FIX-HEADLESS-CAM: use _cam_view_matrix() shim so duck-typed cameras
        # (e.g. _AutoCam from render_model_autoframe) work without _view_matrix()
        self._frame_view = self._cam_view_matrix()  # (right, up, fwd, eye)

        # PERF-FIX (v10.2): Per-frame world-vertex and world-normal caches.
        # _get_world_verts_for_node and _get_world_normals_for_node are called
        # twice per frame when both _draw_mesh_textured and _draw_mesh_flat run
        # (not possible) OR when the same node appears in multiple passes.
        # More importantly: for static (bind-pose) models the transform is
        # identity for most nodes — caching within the frame avoids redundant
        # vertex list comprehensions.  Cache is keyed by node id and cleared
        # at the start of every frame (so stale data is never used).
        self._frame_verts_cache: dict = {}
        self._frame_norms_cache: dict = {}

        # PERF-FIX (v10.1): Use RGBA canvas so _paste_textured_triangle can use
        # the fast img.paste(patch, pos, mask) path without crop+composite overhead.
        # The RGBA alpha channel is ignored at display time (converted to RGB by
        # ImageTk.PhotoImage when drawn to the canvas).
        img  = Image.new('RGBA', (W, H), tuple(getattr(self, "viewport_background", _BG[:3])) + (255,))
        draw = ImageDraw.Draw(img)

        self._draw_grid(draw, W, H)

        if self.model:
            if self.show_texture and self.show_solid:
                # ── Render path selection (v10.5) ─────────────────────────
                # Priority order:
                #   1. Accel (Numba/NumPy) – 17–40× speedup, handles both flat
                #      and textured modes, used for interactive AND idle.
                #   2. PIL flat (interactive drag, no accel) – original fast path.
                #   3. PIL textured (idle, no accel) – original PIL AFFINE path.
                if self.is_interactive:
                    # Interactive drag: use fast flat-shade accel if available,
                    # otherwise fall back to PIL flat.
                    if _ACCEL_AVAILABLE:
                        _accel_ok = self._draw_mesh_accel(draw, img, W, H, flat_only=True)
                    else:
                        _accel_ok = False
                    if not _accel_ok:
                        self._draw_mesh_flat(draw, img, W, H)
                    draw = ImageDraw.Draw(img)
                else:
                    # Idle / release: use textured accel if available.
                    if _ACCEL_AVAILABLE:
                        _accel_ok = self._draw_mesh_accel(draw, img, W, H, flat_only=False)
                    else:
                        _accel_ok = False
                    if not _accel_ok:
                        # Fall back to PIL AFFINE path
                        self._draw_mesh_textured(draw, img, W, H)
                    # Recreate draw after any texture rendering since paste()
                    # may invalidate the draw context
                    draw = ImageDraw.Draw(img)
            else:
                # Solid / flat mode: use accel flat-shade if available
                if _ACCEL_AVAILABLE:
                    _accel_ok = self._draw_mesh_accel(draw, img, W, H, flat_only=True)
                else:
                    _accel_ok = False
                if not _accel_ok:
                    self._draw_mesh_flat(draw, img, W, H)
                draw = ImageDraw.Draw(img)

            # Bones drawn after all mesh/paste calls with a fresh draw context
            if self.show_bones:
                self._draw_bones(draw, W, H)

            # External skeleton overlay (ghost purple bones from other model)
            if self._ext_skeleton:
                self._draw_ext_skeleton(draw, W, H)

            # Gimbal transform overlay for selected node
            if self.show_gimbal and self.selected_node and not self.is_interactive:
                self._draw_gimbal(draw, W, H)

            # Walkmesh overlay (Phase 16.1 — drawn after model geometry)
            if self.show_walkmesh and self._walkmesh_overlay is not None:
                self._draw_walkmesh_overlay(draw, W, H)

            # AcuRig guide overlay — drawn last so it's always visible
            if getattr(self, '_acurig_guides_overlay', None):
                self._draw_acurig_guides(draw, W, H)

        self._draw_axes(draw, W, H)
        self._draw_stats(draw, W, H)
        # ── Rig-edit mode banner (Phase 22) ──────────────────────────────────
        if self.rig_edit_mode:
            self._draw_rig_edit_banner(draw, W, H)
        return img

    # ── projection ────────────────────────────────────────────────────

    def _proj(self, x, y, z, W, H):
        """Project world-space point to screen. Uses cached view matrix for speed."""
        fv = getattr(self, '_frame_view', None)
        if fv is None:
            return self.cam.project(x, y, z, W, H)
        right, up, fwd, eye = fv
        dx, dy, dz = x - eye[0], y - eye[1], z - eye[2]
        cx = dx*right[0] + dy*right[1] + dz*right[2]
        cy = dx*up[0]    + dy*up[1]    + dz*up[2]
        cz = dx*fwd[0]   + dy*fwd[1]   + dz*fwd[2]
        if cz < getattr(self.cam, '_near', getattr(self.cam, 'near', 0.01)):
            return None
        import math as _m
        f  = 1.0 / _m.tan(_m.radians(self.cam.fov) * 0.5)
        sx = int(W * 0.5 + (cx / cz) * f * H * 0.5)
        sy = int(H * 0.5 - (cy / cz) * f * H * 0.5)
        return sx, sy, cz

    def _proj_batch(self, world_verts, W: int, H: int):
        """
        Project a list of world-space (x,y,z) tuples to screen coords in bulk.
        Returns a list of (sx, sy, cz) or None for each vertex (None = behind camera).
        Uses numpy vectorisation when available for ~10x speedup on large meshes.

        v10.5: Eliminated the post-NumPy Python result-list loop using np.ndarray
        fancy indexing, reducing per-call overhead by ~30% on 1k-vertex meshes.
        """
        fv = getattr(self, '_frame_view', None) or self._cam_view_matrix()
        right, up, fwd, eye = fv
        near = getattr(self.cam, '_near', getattr(self.cam, 'near', 0.01))
        import math as _m
        f = 1.0 / _m.tan(_m.radians(self.cam.fov) * 0.5)
        ex, ey, ez = eye

        if _NUMPY and len(world_verts) > 8:
            arr = np.array(world_verts, dtype=np.float32)
            dx = arr[:, 0] - ex
            dy = arr[:, 1] - ey
            dz = arr[:, 2] - ez
            cx = dx*right[0] + dy*right[1] + dz*right[2]
            cy = dx*up[0]    + dy*up[1]    + dz*up[2]
            cz = dx*fwd[0]   + dy*fwd[1]   + dz*fwd[2]
            valid = cz >= near
            hw = W * 0.5
            hh = H * 0.5
            fhh = f * hh
            safe_cz = np.where(valid, cz, 1.0)
            sx = np.where(valid, (hw + (cx / safe_cz) * fhh).astype(np.int32), np.int32(-1))
            sy = np.where(valid, (hh - (cy / safe_cz) * fhh).astype(np.int32), np.int32(-1))
            # Build result list without per-element Python branching.
            # Pre-allocate None list; overwrite valid indices in bulk using numpy.
            NV = len(world_verts)
            result: list = [None] * NV
            valid_idx = np.nonzero(valid)[0]
            sx_v = sx[valid_idx].tolist()
            sy_v = sy[valid_idx].tolist()
            cz_v = cz[valid_idx].tolist()
            for k, i in enumerate(valid_idx.tolist()):
                result[i] = (sx_v[k], sy_v[k], cz_v[k])
            return result

        # Fallback: scalar loop
        result = []
        fhh = f * H * 0.5
        hw  = W * 0.5
        hh  = H * 0.5
        for vx, vy, vz in world_verts:
            dx = vx - ex; dy = vy - ey; dz = vz - ez
            cx = dx*right[0] + dy*right[1] + dz*right[2]
            cy = dx*up[0]    + dy*up[1]    + dz*up[2]
            cz = dx*fwd[0]   + dy*fwd[1]   + dz*fwd[2]
            if cz < near:
                result.append(None)
            else:
                result.append((int(hw + (cx/cz)*fhh), int(hh - (cy/cz)*fhh), cz))
        return result

    # ── Grid ──────────────────────────────────────────────────────────

    def _project_clipped_line(self, p0, p1, W: int, H: int):
        fv = getattr(self, '_frame_view', None)
        if fv is None:
            self._frame_view = self._cam_view_matrix()
            fv = self._frame_view
        right, up, fwd, eye = fv
        near = max(0.001, float(getattr(self.cam, '_near', getattr(self.cam, 'near', 0.01))))

        def to_camera(p):
            dx, dy, dz = p[0] - eye[0], p[1] - eye[1], p[2] - eye[2]
            return (
                dx * right[0] + dy * right[1] + dz * right[2],
                dx * up[0] + dy * up[1] + dz * up[2],
                dx * fwd[0] + dy * fwd[1] + dz * fwd[2],
            )

        c0 = to_camera(p0)
        c1 = to_camera(p1)
        if c0[2] < near and c1[2] < near:
            return None
        if c0[2] < near or c1[2] < near:
            denom = c1[2] - c0[2]
            if abs(denom) < 1e-9:
                return None
            t = (near - c0[2]) / denom
            clipped = (
                c0[0] + (c1[0] - c0[0]) * t,
                c0[1] + (c1[1] - c0[1]) * t,
                near,
            )
            if c0[2] < near:
                c0 = clipped
            else:
                c1 = clipped

        import math as _m
        f = 1.0 / _m.tan(_m.radians(self.cam.fov) * 0.5)

        def to_screen(c):
            sx = int(W * 0.5 + (c[0] / c[2]) * f * H * 0.5)
            sy = int(H * 0.5 - (c[1] / c[2]) * f * H * 0.5)
            return sx, sy

        return to_screen(c0), to_screen(c1)

    def _draw_grid(self, draw: 'ImageDraw.Draw', W: int, H: int):
        if not getattr(self, "show_grid", True):
            return
        grid = getattr(self, "grid_measurement", None)
        step = float(getattr(grid, "minor_spacing", 1.0) or 1.0)
        major_every = int(getattr(grid, "major_every", 5) or 5)
        extent = max(step * 20.0, float(getattr(grid, "major_spacing", step * major_every)) * 4.0)
        try:
            if self.model is not None:
                bb_min, bb_max = self._get_render_bounds()
                if grid is not None:
                    extent = grid.extent_for_bounds((bb_min, bb_max))
                else:
                    size_x = abs(float(bb_max[0]) - float(bb_min[0]))
                    size_y = abs(float(bb_max[1]) - float(bb_min[1]))
                    centre_x = (float(bb_min[0]) + float(bb_max[0])) * 0.5
                    centre_y = (float(bb_min[1]) + float(bb_max[1])) * 0.5
                    radius = max(
                        size_x,
                        size_y,
                        abs(centre_x) + size_x * 0.5,
                        abs(centre_y) + size_y * 0.5,
                        8.0,
                    ) * 1.5
                    extent = max(16.0, min(60.0, math.ceil(radius / major_every) * major_every))
        except Exception:
            pass
        x0 = math.floor(-extent / step)
        x1 = math.ceil(extent / step)
        y0 = math.floor(-extent / step)
        y1 = math.ceil(extent / step)
        minor = tuple(getattr(self, "grid_minor_color", _GRID[:3]))
        major = tuple(getattr(self, "grid_major_color", (82, 90, 102)))
        x_axis = tuple(getattr(self, "grid_x_axis_color", (118, 54, 54)))
        y_axis = tuple(getattr(self, "grid_y_axis_color", (62, 112, 68)))
        label_points = []
        for i in range(y0, y1 + 1):
            y = i * step
            segment = self._project_clipped_line((x0 * step, y, 0.0), (x1 * step, y, 0.0), W, H)
            if segment:
                p1, p2 = segment
                col = x_axis if i == 0 else major if i % major_every == 0 else minor
                draw.line([p1[0], p1[1], p2[0], p2[1]], fill=col, width=1)
                if i != 0 and i % major_every == 0:
                    label_points.append((i, y, p1, p2))
        for i in range(x0, x1 + 1):
            x = i * step
            segment = self._project_clipped_line((x, y0 * step, 0.0), (x, y1 * step, 0.0), W, H)
            if segment:
                p1, p2 = segment
                col = y_axis if i == 0 else major if i % major_every == 0 else minor
                draw.line([p1[0], p1[1], p2[0], p2[1]], fill=col, width=1)
                if i != 0 and i % major_every == 0:
                    label_points.append((i, x, p1, p2))
        if grid is None or not getattr(grid, "show_labels", True):
            return
        try:
            major_px = 80.0
            origin = self._proj(0.0, 0.0, 0.0, W, H)
            major_proj = self._proj(float(getattr(grid, "major_spacing", step * major_every)), 0.0, 0.0, W, H)
            if origin is not None and major_proj is not None:
                major_px = abs(float(major_proj[0]) - float(origin[0]))
            stride = grid.label_stride(major_px)
            drawn = 0
            for idx, value, p1, p2 in label_points:
                major_idx = int(round(idx / max(major_every, 1)))
                if major_idx % stride != 0:
                    continue
                mx = int((p1[0] + p2[0]) * 0.5)
                my = int((p1[1] + p2[1]) * 0.5)
                if mx < 12 or mx > W - 80 or my < 12 or my > H - 20:
                    continue
                label = grid.format_label(float(value))
                draw.text((mx + 4, my + 4), label, fill=getattr(self, "grid_label_color", (174, 184, 198, 205)))
                drawn += 1
                if drawn >= 16:
                    break
        except Exception:
            return
