"""RendererSetupMixin methods for the viewport frame renderer."""

from __future__ import annotations

from .mixin_imports import (
    ArcBallCamera,
    DanglySimulator,
    Dict,
    GridMeasurement,
    KOTOR_BASE_SKELETONS,
    KotorModel,
    List,
    ModelNode,
    Optional,
    TextureCache,
    Tuple,
    UnitSystem,
    _ACCEL_AVAILABLE,
    _BG,
    _GRID,
    _INNER_GEO_SUBSTRINGS,
    _PIL,
    _TexArrayCache,
    _apply_txi_to_node,
    _clean_tex_name,
    _extract_alpha_test_from_tpc,
    _hex_to_rgb_tuple,
    _normalize,
    _warmup_jit,
    log,
)


class RendererSetupMixin:
    def __init__(self, camera: ArcBallCamera):
        self.cam            = camera
        self.model: Optional[KotorModel] = None
        self.show_bones     = True
        self.show_wireframe = False
        self.show_solid     = True
        self.show_grid      = True
        self.unit_system    = UnitSystem()
        self.grid_measurement = GridMeasurement(self.unit_system)
        self.viewport_background = _BG[:3]
        self.viewport_text = (170, 180, 195)
        self.grid_minor_color = _GRID[:3]
        self.grid_major_color = (82, 90, 102)
        self.grid_x_axis_color = (118, 54, 54)
        self.grid_y_axis_color = (62, 112, 68)
        self.grid_label_color = (174, 184, 198, 205)
        self.hud_fill = (30, 34, 40)
        self.hud_text = (213, 220, 230)
        self.hud_outline = (78, 88, 102)
        self.hud_muted_text = (165, 176, 190)
        self.hud_success_fill = (25, 43, 37)
        self.hud_success_text = (138, 230, 178)
        self.hud_warning_fill = (68, 44, 22)
        self.hud_warning_text = (255, 190, 95)
        self.gimbal_x_color = (220, 60, 60)
        self.gimbal_y_color = (60, 220, 60)
        self.gimbal_z_color = (60, 120, 220)
        self.gimbal_active_color = (255, 255, 80)
        self.gimbal_plane_xy_color = (220, 220, 60)
        self.gimbal_plane_xz_color = (60, 220, 220)
        self.gimbal_plane_yz_color = (220, 60, 220)
        self.gimbal_text_color = (200, 200, 200)
        self.show_texture   = False   # Toggle textured rendering
        self.render_mode    = "realistic"
        self.show_diffuse_map: bool = True
        self.show_lightmap_map: bool = False
        self.show_environment_map: bool = True
        self.show_specular_map: bool = True
        self.show_normal_map: bool = True
        self.lightmap_intensity: float = 0.55
        self.lightmap_mode: str = "disabled"
        self.lighting_mode: str = "scene"
        self.shader_complexity_mode: str = "off"
        self.show_light_gizmos: bool = True
        self.show_light_radius_volumes: bool = False
        self.is_interactive = False   # True while mouse dragged (enable LOD)
        # FIX (v10.4): Explicitly declare _lq_tex_mode in __init__ so that
        # getattr(self, '_lq_tex_mode', False) is never needed; the attribute
        # is always present and won't be left stale across model reloads.
        self._lq_tex_mode: bool = False
        self.selected_node: Optional[ModelNode] = None
        self.textures: Dict[str, 'Image.Image'] = {} if _PIL else {}
        self.tex_cache = TextureCache()
        self._wt_cache: Dict[int, tuple] = {}   # node id → (wp, wo, is_id)
        # Bone screen positions for click/hover selection
        self._bone_screen_positions: List[Tuple] = []  # [(sx,sy,depth,node), ...]
        self._hovered_bone: Optional[ModelNode] = None
        self.hidden_bone_name_fragments: tuple[str, ...] = ()
        # ── Rig-edit mode (Phase 22) ─────────────────────────────────────────
        # When True the renderer draws an orange "Rig Edit Mode" banner and
        # colours adjustable bone joints orange so the user knows they're live.
        self.rig_edit_mode: bool = False
        # ── Hologram preview mode (Phase G3, opt-in) ─────────────────────────
        # When True, _iter_mesh_nodes filters out any node whose parser-set
        # ``hide_in_holograms`` flag is True (K1+K2 mesh header "hologram_
        # donotdraw" / "hide_in_hologram").  Default is False so vanilla
        # rendering is untouched; wire up via ``set_hologram_mode(True)`` from
        # a UI toggle or an automated screenshot harness that wants to mirror
        # in-game hologram cutscenes.
        self.hologram_mode: bool = False
        # Callback invoked after a bone joint is dragged in rig-edit mode:
        #   on_bone_moved(node_name: str, new_pos: tuple)
        self.on_bone_moved = None
        self._outlier_skin_nodes: set = set()   # node ids to skip (accessory model proxies)
        self._outlier_model_id: int = -1            # id() of model for which outliers were computed

        # ── Acceleration layer caches (v10.5) ────────────────────────────────
        # TexArrayCache converts PIL → NumPy RGBA arrays for the accel rasterizer,
        # with LRU eviction to bound memory.  When accel is unavailable this is a
        # no-op stub, so all downstream code can call .get() unconditionally.
        self._tex_arr_cache = _TexArrayCache(max_entries=256)
        # Raise the textured triangle cap when fast rasterizer is available.
        # PIL AFFINE: 187 µs/tri → 2 k cap.  NumPy/Numba: 5–11 µs/tri → 10 k cap.
        if _ACCEL_AVAILABLE:
            self.__class__.MAX_TRIS_TEXTURED = self.__class__.MAX_TRIS_TEXTURED_ACCEL

        # ── Render-bounds cache ───────────────────────────────────────────────
        # render_bounds() is O(N*verts) — cache it per model, only recompute when
        # the model identity changes.  Called every frame from _draw_stats() so
        # without caching this adds 8–20 ms overhead per frame on large models.
        self._render_bounds_cache: Optional[tuple] = None   # ((min), (max)) or None
        self._render_bounds_model_id: int = -1

        # ── LOD hysteresis ───────────────────────────────────────────────────
        # UE-inspired: prevent rapid triangle-budget oscillation when the model
        # sits right at the boundary between two LOD tiers.  We only update the
        # current LOD cap when the newly computed cap differs from the previous
        # one by more than _LOD_HYSTERESIS_FRAC of MAX_TRIS.  This eliminates
        # the flickering "LOD pop" artefact where the budget oscillates between
        # e.g. 40 k and 50 k triangles every other frame.
        # Reference: UE ComputeLODForMeshes / USkinnedMeshComponent::UpdateLODStatus
        self._lod_prev_cap: int = self.MAX_TRIS   # last committed triangle cap
        self._LOD_HYSTERESIS_FRAC: float = 0.10   # 10% dead-band

        # KotOR-accurate lighting (two-light rig matching Odyssey engine)
        # Key light from upper-right, fill from left
        self._light_dir  = _normalize((0.55, 0.40, 0.90))  # main key light (upper right)
        self._light_dir2 = _normalize((-0.35, -0.20, 0.60)) # fill light (left)
        self._ambient    = 0.38   # raised v12.14: brighter ambient for low-RGB creature textures
        self._specular   = 0.10
        self._shininess  = 20.0

        # Animation pose (set by AnimationsPanel)
        self._anim_pose = None   # Optional[AnimPose]
        self._anim_poses_by_character: Dict[str, object] = {}
        self._anim_pose_metadata_by_character: Dict[str, dict] = {}
        self._anim_name: str = ""   # current animation name for HUD display
        self._anim_time: float = 0.0   # current animation time for HUD display
        self._anim_length: float = 0.0  # current animation length for HUD display
        self.animation_supermodel_hud_placement: str = "center"
        self._anim_base_pose = None  # Optional[AnimPose]
        self._bone_transforms_cache: Optional[Dict] = None
        self._bone_transforms_pose_id: int = -1
        self._gpu_parity_skin_uploader = None
        self._gpu_parity_skin_model_id: int = -1
        self._gpu_parity_skin_pose_id: int = -1
        self._gpu_parity_skin_verts_cache: Dict[int, List[Tuple[float, float, float]]] = {}
        self._dangly_sims: Dict[int, 'DanglySimulator'] = {}
        self._dangly_last_time: float = 0.0

        # Gimbal / transform overlay
        self.gimbal_mode: int = 1
        self.show_gimbal: bool = True
        self.gimbal_active_axis = None
        self._gimbal_handles: List[Tuple] = []
        self._gimbal_handle_lines: List[Tuple] = []

        # External skeleton and walkmesh overlays
        self._ext_skeleton = None
        self._ext_skel_offset: List[float] = [0.0, 0.0, 0.0]
        self._ext_skel_scale: float = 1.0
        self._ext_bone_screen_positions: List[Tuple] = []
        self._character_fit_overlay: Optional[Dict] = None
        self.show_walkmesh:       bool = False
        self.show_walkmesh_walk:  bool = True
        self.show_walkmesh_block: bool = True
        self._walkmesh_overlay: Optional['WalkmeshOverlay'] = None

    def set_theme_colors(self, theme) -> None:
        self.viewport_background = _hex_to_rgb_tuple(theme.color("viewport.background"), _BG[:3])
        self.viewport_text = _hex_to_rgb_tuple(theme.color("viewport.text"), (170, 180, 195))
        self.grid_minor_color = _hex_to_rgb_tuple(theme.color("viewport.gridMinor"), _GRID[:3])
        self.grid_major_color = _hex_to_rgb_tuple(theme.color("viewport.gridMajor"), (82, 90, 102))
        self.grid_x_axis_color = _hex_to_rgb_tuple(theme.color("error"), (118, 54, 54))
        self.grid_y_axis_color = _hex_to_rgb_tuple(theme.color("success"), (62, 112, 68))
        self.grid_label_color = self.viewport_text + (205,)
        self.hud_fill = _hex_to_rgb_tuple(theme.color("panel.backgroundAlt", theme.color("panel.altBackground")), (30, 34, 40))
        self.hud_text = _hex_to_rgb_tuple(theme.color("text.primary"), (213, 220, 230))
        self.hud_outline = _hex_to_rgb_tuple(theme.color("panel.border"), (78, 88, 102))
        self.hud_muted_text = _hex_to_rgb_tuple(theme.color("text.secondary"), (165, 176, 190))
        self.hud_success_fill = _hex_to_rgb_tuple(theme.color("success"), (25, 43, 37))
        self.hud_success_text = _hex_to_rgb_tuple(theme.color("selection.text"), (138, 230, 178))
        self.hud_warning_fill = _hex_to_rgb_tuple(theme.color("warning"), (68, 44, 22))
        self.hud_warning_text = _hex_to_rgb_tuple(theme.color("button.checkedText", theme.color("text.primary")), (255, 190, 95))
        self.gimbal_x_color = _hex_to_rgb_tuple(theme.color("error"), (220, 60, 60))
        self.gimbal_y_color = _hex_to_rgb_tuple(theme.color("success"), (60, 220, 60))
        self.gimbal_z_color = _hex_to_rgb_tuple(theme.color("accent.secondary"), (60, 120, 220))
        self.gimbal_active_color = _hex_to_rgb_tuple(theme.color("button.checkedText", theme.color("selection.text")), (255, 255, 80))
        self.gimbal_plane_xy_color = _hex_to_rgb_tuple(theme.color("warning"), (220, 220, 60))
        self.gimbal_plane_xz_color = _hex_to_rgb_tuple(theme.color("info"), (60, 220, 220))
        self.gimbal_plane_yz_color = _hex_to_rgb_tuple(theme.color("accent.primary"), (220, 60, 220))
        self.gimbal_text_color = _hex_to_rgb_tuple(theme.color("viewport.text"), (200, 200, 200))

    def reset_theme_colors(self) -> None:
        self.viewport_background = _BG[:3]
        self.viewport_text = (170, 180, 195)
        self.grid_minor_color = _GRID[:3]
        self.grid_major_color = (82, 90, 102)
        self.grid_x_axis_color = (118, 54, 54)
        self.grid_y_axis_color = (62, 112, 68)
        self.grid_label_color = (174, 184, 198, 205)
        self.hud_fill = (30, 34, 40)
        self.hud_text = (213, 220, 230)
        self.hud_outline = (78, 88, 102)
        self.hud_muted_text = (165, 176, 190)
        self.hud_success_fill = (25, 43, 37)
        self.hud_success_text = (138, 230, 178)
        self.hud_warning_fill = (68, 44, 22)
        self.hud_warning_text = (255, 190, 95)
        self.gimbal_x_color = (220, 60, 60)
        self.gimbal_y_color = (60, 220, 60)
        self.gimbal_z_color = (60, 120, 220)
        self.gimbal_active_color = (255, 255, 80)
        self.gimbal_plane_xy_color = (220, 220, 60)
        self.gimbal_plane_xz_color = (60, 220, 220)
        self.gimbal_plane_yz_color = (220, 60, 220)
        self.gimbal_text_color = (200, 200, 200)

    @staticmethod
    def _blend_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
        t = max(0.0, min(1.0, float(t)))
        return tuple(int(round(float(a[i]) * (1.0 - t) + float(b[i]) * t)) for i in range(3))

    @staticmethod
    def _relative_luma(color: tuple[int, int, int]) -> float:
        r, g, b = (max(0, min(255, int(v))) / 255.0 for v in color)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def set_native_palette_colors(
        self,
        *,
        window: tuple[int, int, int],
        base: tuple[int, int, int],
        text: tuple[int, int, int],
        button: tuple[int, int, int],
        button_text: tuple[int, int, int],
        mid: tuple[int, int, int],
        highlight: tuple[int, int, int],
        highlighted_text: tuple[int, int, int],
    ) -> None:
        bg = tuple(int(v) for v in base[:3])
        fg = tuple(int(v) for v in text[:3])
        button_bg = tuple(int(v) for v in button[:3])
        button_fg = tuple(int(v) for v in button_text[:3])
        mid_color = tuple(int(v) for v in mid[:3])
        highlight_bg = tuple(int(v) for v in highlight[:3])
        highlight_fg = tuple(int(v) for v in highlighted_text[:3])
        is_dark = self._relative_luma(bg) < 0.45

        self.viewport_background = bg
        self.viewport_text = fg
        self.grid_minor_color = self._blend_rgb(bg, fg, 0.12 if is_dark else 0.18)
        self.grid_major_color = self._blend_rgb(bg, fg, 0.22 if is_dark else 0.30)
        self.grid_x_axis_color = (210, 70, 70) if is_dark else (160, 30, 30)
        self.grid_y_axis_color = (70, 180, 90) if is_dark else (40, 130, 55)
        self.grid_label_color = self._blend_rgb(bg, fg, 0.70) + (205,)
        self.hud_fill = button_bg
        self.hud_text = button_fg
        self.hud_outline = mid_color
        self.hud_muted_text = self._blend_rgb(button_bg, button_fg, 0.68)
        self.hud_success_fill = highlight_bg
        self.hud_success_text = highlight_fg
        self.hud_warning_fill = (214, 151, 42) if is_dark else (255, 223, 133)
        self.hud_warning_text = (18, 18, 18) if is_dark else (72, 48, 0)
        self.gimbal_active_color = highlight_bg
        self.gimbal_text_color = fg

    def set_anim_base_pose(self, base_pose):
        """Set the animation's first-frame (t=0) pose for GPU skinning.

        FIX-SKIN-ANIM-D3: The GPU skinning palette needs the animation's
        t=0 pose as the bind reference (xoreos approach).  Call this once
        when a new animation starts, before the first set_animation_pose().
        """
        self._anim_base_pose = base_pose

    def set_animation_pose(self, pose, name: str = "", time: float = 0.0, length: float = 0.0):
        """Set the animation pose for rendering. Pass None to clear (bind pose).

        When an animated pose is supplied, advances all DanglySimulators by the
        wall-clock time since the previous call so cloth/chain nodes oscillate
        live during animation playback.  (Phase 4.6 — Dangly Verlet wiring.)
        """
        import time as _time_mod
        now = _time_mod.perf_counter()

        # Advance dangly simulators when we have an active pose and a model
        if pose is not None and self.model is not None and DanglySimulator is not None:
            if self._dangly_last_time <= 0.0:
                # First tick — initialise so we don’t get a huge dt on the second
                self._dangly_last_time = now
                dt = 0.0
            else:
                dt = now - self._dangly_last_time
            self._dangly_last_time = now

            if dt > 0.0:
                for n in self.model.all_nodes():
                    # Retained scene composition may include lightweight
                    # helper/wrapper nodes (for example ``SimpleNamespace``
                    # roots) alongside full ``ModelNode`` instances.  Dangly
                    # simulation is optional, so only opt in nodes that
                    # explicitly expose both the flag and geometry instead of
                    # aborting the entire animation tick on a helper node.
                    if not bool(getattr(n, "is_dangly", False)) or not getattr(n, "vertices", None):
                        continue
                    nid = id(n)
                    if nid not in self._dangly_sims:
                        try:
                            self._dangly_sims[nid] = DanglySimulator(n)
                        except Exception:
                            continue
                    try:
                        self._dangly_sims[nid].step(dt)
                    except Exception:
                        pass
        elif pose is None:
            # Pose cleared — reset simulators to bind pose
            for sim in self._dangly_sims.values():
                try:
                    sim.reset()
                except Exception:
                    pass
            self._dangly_last_time = 0.0

        self._anim_pose = pose
        self._anim_poses_by_character.clear()
        self._anim_pose_metadata_by_character.clear()
        self._anim_name = name
        self._anim_time = time
        self._anim_length = length
        # FIX-SKIN-ANIM-D3: Clear base pose when animation is cleared.
        if pose is None:
            self._anim_base_pose = None
        self._wt_cache.clear()  # force re-evaluation with new pose
        # Invalidate per-pose bone-transforms cache
        self._bone_transforms_cache = None
        self._bone_transforms_pose_id = -1
        self._gpu_parity_skin_pose_id = -1
        self._gpu_parity_skin_verts_cache = {}
        # Ensure next frame renders at full quality (not LOD/interactive mode)
        self.is_interactive = False
        # Request a redraw so every animation frame is actually rendered.
        # Without this the viewport only redraws on the next idle 33 ms tick,
        # causing animation to appear frozen or heavily frame-dropped.
        # Use getattr for safe call — FrameRenderer may be instantiated standalone
        # (e.g. in unit tests) without the ModelViewport parent widget that owns
        # _request_render().  In that case silently skip the redraw request.
        _req = getattr(self, '_request_render', None)
        if _req is not None:
            try:
                _req(fast=True)
            except Exception:
                pass

    # ── Base skeleton names (supermodels that ARE the main skeleton) ──────
    # Use the shared KOTOR_BASE_SKELETONS constant from model_data to ensure
    # consistent behaviour across viewport rendering, compute_bounds, and render_bounds.
    _BASE_SKELETONS = KOTOR_BASE_SKELETONS

    def set_character_animation_pose(
        self,
        character_instance_id: str,
        pose,
        name: str = "",
        time: float = 0.0,
        length: float = 0.0,
        *,
        request_render: bool = True,
    ):
        """Set one character's pose without disturbing other sequence poses."""

        self.set_character_animation_poses(
            ((character_instance_id, pose, name, time, length),),
            request_render=request_render,
        )

    def set_character_animation_poses(self, rows, *, request_render: bool = True):
        """Commit many scoped character poses with one cache invalidation.

        Runtime previews can contain dozens of retained Odyssey actors.  The
        historical one-at-a-time path rebuilt the composed pose set, cleared
        all skin/transform caches, and queued a repaint for every actor.  This
        batch contract performs those shared operations once, allowing the Qt
        viewport to submit exactly one coherent animation/transform/camera
        frame after every pose has been staged.
        """

        changed = False
        for row in tuple(rows or ()):
            try:
                character_instance_id, pose, name, time, length = row
            except (TypeError, ValueError):
                continue
            character_id = str(character_instance_id or "").strip()
            if not character_id:
                continue
            changed = True
            if pose is None:
                self._anim_poses_by_character.pop(character_id, None)
                self._anim_pose_metadata_by_character.pop(character_id, None)
            else:
                self._anim_poses_by_character[character_id] = pose
                self._anim_pose_metadata_by_character[character_id] = {
                    "name": str(name or getattr(pose, "_gr_animation_name", "") or ""),
                    "time": float(time),
                    "length": float(length),
                }
        if not changed:
            return
        scoped_pose = self._compose_scoped_animation_pose_set()
        if scoped_pose is None:
            for sim in self._dangly_sims.values():
                try:
                    sim.reset()
                except Exception:
                    pass
            self._dangly_last_time = 0.0
            self._anim_base_pose = None
            self._anim_pose = None
            self._anim_name = ""
            self._anim_time = 0.0
            self._anim_length = 0.0
            self._invalidate_animation_pose_caches(request_render=request_render)
            return
        self._anim_pose = scoped_pose
        metadata = list(self._anim_pose_metadata_by_character.values())
        names = [str(item.get("name", "") or "") for item in metadata if str(item.get("name", "") or "")]
        self._anim_name = " + ".join(names[:3]) + (" ..." if len(names) > 3 else "")
        self._anim_time = max((float(item.get("time", 0.0) or 0.0) for item in metadata), default=0.0)
        self._anim_length = max((float(item.get("length", 0.0) or 0.0) for item in metadata), default=0.0)
        self._invalidate_animation_pose_caches(request_render=request_render)

    def clear_character_animation_pose(self, character_instance_id: str) -> None:
        self.set_character_animation_pose(character_instance_id, None)

    def _compose_scoped_animation_pose_set(self):
        poses = {character_id: pose for character_id, pose in self._anim_poses_by_character.items() if pose is not None}
        if not poses:
            return None
        try:
            from src.core.rendering.mesh_render_data import ScopedAnimationPoseSet

            return ScopedAnimationPoseSet(poses)
        except Exception:
            return None

    def _invalidate_animation_pose_caches(self, *, request_render: bool = True) -> None:
        self._wt_cache.clear()
        self._bone_transforms_cache = None
        self._bone_transforms_pose_id = -1
        self._gpu_parity_skin_pose_id = -1
        self._gpu_parity_skin_verts_cache = {}
        self.is_interactive = False
        _req = getattr(self, '_request_render', None)
        if request_render and _req is not None:
            try:
                _req(fast=True)
            except Exception:
                pass

    def set_model(self, m: Optional[KotorModel]):
        self.model = m
        self._wt_cache: Dict[int, tuple] = {}   # node id → (wp, wo, is_id)
        self._cached_model_id = id(m) if m else -1  # track for cache invalidation
        self._anim_pose = None   # clear animation pose when model changes
        self._anim_poses_by_character.clear()
        self._anim_pose_metadata_by_character.clear()
        self._bone_transforms_cache = None   # invalidate bone-transform cache
        self._bone_transforms_pose_id = -1
        self._gpu_parity_skin_uploader = None
        self._gpu_parity_skin_model_id = -1
        self._gpu_parity_skin_pose_id = -1
        self._gpu_parity_skin_verts_cache = {}
        self._outlier_skin_nodes: set = set()   # node ids to skip for accessory models
        # Clear dangly simulators: new model may have different nodes
        self._dangly_sims = {}
        self._dangly_last_time = 0.0
        # Invalidate render-bounds cache
        self._render_bounds_cache = None
        self._render_bounds_model_id = id(m) if m else -1
        # Reset LOD hysteresis so the new model gets a fresh cap evaluation
        self._lod_prev_cap = self.MAX_TRIS
        # FIX (v10.4): Reset _lq_tex_mode on model change so a stale LQ flag
        # from a previous drag cannot survive into the new model's first render.
        self._lq_tex_mode = False
        # v20: Reset model-scale bounding diagonal (used by LBS explosion guard).
        # Must be cleared on model change so the new model's size is recomputed.
        self._lbs_model_diag = None
        # Compute skin-proxy node id set for deformation-helper detection.
        # Non-skin nodes whose texture has an exclusive skin-mesh counterpart
        # (exactly 1 skin mesh uses that texture in the whole model) are deformation
        # reference proxies — they should not render separately.
        self._skin_proxy_ids: set = set()
        if m is not None:
            self._skin_proxy_ids = self._compute_skin_proxy_ids(m)
        # Clear per-model texture dict so stale PIL images from the previous
        # model don't linger (stale RGBA-converted refs waste memory and can
        # shadow newly loaded textures after a tex_cache clear).
        self.textures.clear()
        # Clear mip-bias cache (old texture images may be replaced)
        self.tex_cache.clear_mip_cache()
        # Clear TexArrayCache so stale PIL→NumPy conversions are evicted (v10.5)
        self._tex_arr_cache.clear()
        if m:
            # Use render_bounds (visible nodes only) for camera framing so that
            # deformation-helper skeleton meshes don't push the camera too far back.
            prepared_bounds = getattr(m, "_gr_render_bounds", None)
            if prepared_bounds:
                rbb_min, rbb_max = prepared_bounds
            else:
                rbb_min, rbb_max = m.render_bounds()
            # Cache the result immediately so _draw_stats() doesn't recompute it
            self._render_bounds_cache = (rbb_min, rbb_max)
            self.cam.frame_bounds(rbb_min, rbb_max)
            # Pre-compute outlier skin nodes for accessory models (e.g. ad_saul)
            self._compute_outlier_skin_nodes(m)
            # Load and apply TXI metadata for all mesh nodes
            # This populates txi_blending, txi_cube, txi_proceduretype, etc.
            # so that the renderer can apply flipbook / additive blending / clamp modes.
            if getattr(m, "_gr_defer_txi_metadata", False):
                log.debug("Deferring TXI metadata load for %s", getattr(m, "name", "?"))
            else:
                self._load_txi_metadata_for_model(m)
            # Trigger Numba JIT warmup in background so the first drag frame is fast
            # (v10.5): warmup_jit() is a no-op if already warmed or if Numba is absent.
            import threading as _t
            _t.Thread(target=_warmup_jit, daemon=True,
                      name="accel-jit-warmup").start()

    @staticmethod
    def _compute_skin_proxy_ids(model: 'KotorModel') -> set:
        """
        v12.14: Build the set of node ids that are SkinMesh deformation proxies.

        In KotOR, some non-skin trimesh nodes (e.g. 'head_Hair' on the bantha)
        serve as simplified reference geometry that drives SkinMesh deformation.
        They share a texture with a skin mesh and should NOT be rendered separately
        because the skin mesh (bthair / btBody_front) already provides the visible
        geometry in the correct world-space position.

        Rule: A non-skin node N is a proxy if and only if:
          1. N is NOT a skin node.
          2. N has a real (non-null) texture.
          3. N has UV coordinates.
          4. The texture is used by EXACTLY ONE skin mesh in the whole model.
          5. That skin mesh has MORE vertices than N.

        This correctly identifies 'head_Hair' (61 verts, c_banthh01) as a proxy
        of 'bthair' (320 verts, c_banthh01), while NOT marking 'btRhorn' as a
        proxy because c_bantha01 is shared by TWO skin meshes (btBody_front,
        btBodyback), so condition 4 is not met.

        Returns a set of Python id()s for proxy nodes.
        """
        proxy_ids: set = set()
        try:
            all_nodes = model.all_nodes()

            # Build tex → [(skin_node, vert_count)] mapping for skin meshes
            skin_tex_verts: dict = {}
            for n in all_nodes:
                # KotOR skin nodes have both is_skin=True and is_mesh=True (flags 0x61).
                # Accept any node that is a skin (is_skin=True) regardless of is_mesh.
                if not n.is_skin:
                    continue
                tex = (_clean_tex_name(getattr(n, 'texture', '')) or '').lower()
                if not tex or tex == 'null':
                    continue
                nv = len(getattr(n, 'vertices', []))
                if nv == 0:
                    continue
                if tex not in skin_tex_verts:
                    skin_tex_verts[tex] = []
                skin_tex_verts[tex].append((n, nv))

            # Check each non-skin, non-null, UV-having node
            for n in all_nodes:
                if not n.is_mesh or n.is_skin:
                    continue
                tex = (_clean_tex_name(getattr(n, 'texture', '')) or '').lower()
                if not tex or tex == 'null':
                    continue
                if not getattr(n, 'uvs', []):
                    continue  # already handled by no-UVs check
                nv = len(getattr(n, 'vertices', []))

                # BUG FIX v26: NEVER mark inner-geometry nodes (eyes, eyelids,
                # teeth, tongue, jaw, gum) as skin proxies.  These are real
                # renderable meshes; even when they share a texture with a skin
                # mesh they must be drawn independently so the eyeball / teeth
                # appear inside the head socket.  Without this exemption, models
                # like n_brejikh whose eye nodes share c_bantha01 (or equivalent)
                # with exactly one skin mesh would have their eyes silenced.
                _n_lower = n.name.lower()
                if any(s in _n_lower for s in _INNER_GEO_SUBSTRINGS):
                    continue

                skin_matches = skin_tex_verts.get(tex, [])
                # Condition 4: exactly ONE skin mesh uses this texture
                if len(skin_matches) != 1:
                    continue
                skin_node, skin_verts = skin_matches[0]
                # Condition 5: skin mesh has more vertices than this node
                if skin_verts <= nv:
                    continue

                proxy_ids.add(id(n))
                log.debug(
                    f"Skin proxy: '{n.name}' (non-skin, {nv}v, tex='{tex}') "
                    f"→ covered by '{skin_node.name}' (skin, {skin_verts}v)"
                )
        except Exception as e:
            log.debug(f"_compute_skin_proxy_ids error: {e}")
        return proxy_ids

    def _load_txi_metadata_for_model(self, m: 'KotorModel') -> None:
        """
        Load TXI metadata for all mesh nodes in the model and apply to node fields.

        Iterates over all mesh nodes, looks up TXI data for each node's primary
        texture (and secondary textures), then updates the TXI fields on each node
        (txi_blending, txi_cube, txi_proceduretype, etc.) via _apply_txi_to_node().

        FIX-ALPHATEST: Also extracts the per-texture alpha_test_threshold from the
        TPC header bytes [4-7] and stores it as node.txi_alpha_test so the GPU
        renderer can use the per-node discard threshold instead of a global 0.5.
        References: Kotor.NET TPC.cs, xoreos tpc.cpp, PyKotor io_tpc.py.

        This is called once when a model is loaded (set_model) and only affects
        nodes whose primary texture has TXI data in the cache or on disk.
        """
        if m is None:
            return
        try:
            for node in m.all_nodes():
                if not node.is_mesh:
                    continue
                tex_name = _clean_tex_name(node.texture)
                if not tex_name or tex_name.upper() in ('NULL', ''):
                    continue
                txi_str = self.tex_cache.get_txi(tex_name)
                # FIX-ALPHATEST: extract alpha_test_threshold from raw TPC header
                alpha_test = 0.5  # Aurora engine default
                try:
                    raw = self.tex_cache.get_raw_header(tex_name)
                    if raw:
                        alpha_test = _extract_alpha_test_from_tpc(raw)
                except Exception:
                    pass
                # Always call _apply_txi_to_node to set txi_alpha_test even
                # when there is no TXI string (punchthrough threshold comes from TPC).
                _apply_txi_to_node(node, txi_str or '', alpha_test)
        except Exception as e:
            log.debug(f"_load_txi_metadata_for_model error: {e}")

    def _get_render_bounds(self):
        """Return cached render bounds for the current model.
        Recomputes only when the model identity changes (O(N*verts) avoided per frame)."""
        if self.model is None:
            return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        model_id = id(self.model)
        if self._render_bounds_cache is not None and self._render_bounds_model_id == model_id:
            return self._render_bounds_cache
        # Recompute (model was replaced without calling set_model, e.g. node was modified)
        try:
            rbb_min, rbb_max = self.model.render_bounds()
        except Exception:
            rbb_min, rbb_max = (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
        self._render_bounds_cache = (rbb_min, rbb_max)
        self._render_bounds_model_id = model_id
        return rbb_min, rbb_max

    def _compute_outlier_skin_nodes(self, m: 'KotorModel'):
        """
        For accessory models (non-standard supermodel), identify skin proxy meshes
        that should not be rendered — they belong to the parent skeleton, not the
        accessory itself.

        Two detection strategies are tried:

        Strategy A – Z-distance (works when skin proxy verts are raw/unshifted):
          Anchor = Z centroid of non-skin visible nodes.
          Outlier if skin node centroid is > 1.5 units away from anchor.

        Strategy B – Vertex count ratio (works for ad_saul-style face overlays):
          In face/head overlay accessories, the non-skin "anchor" pieces are
          tiny (< 50 verts each). Any skin node with > 5× the max non-skin
          vertex count is a body proxy that should be hidden.

        Guard: only triggers for non-standard supermodels; skip if > 50% outliers.
        """
        self._outlier_skin_nodes = set()
        super_upper = m.supermodel.strip().upper()
        if super_upper in self._BASE_SKELETONS:
            return   # base character model – no outlier filtering needed
        # Also skip for creature/droid models (self-contained, no accessory proxy meshes)
        # Model names starting with C_ (creature), N_ (creature NPC), or the model's
        # own supermodel matching its own name prefix means it IS the base skeleton.
        model_upper = (m.name or '').strip().upper()
        # Expanded creature/NPC prefixes to prevent outlier-check crashes on all creature models
        creature_prefixes = ('C_', 'N_WARD', 'WARDROID', 'N_', 'P_', 'G_')
        if any(model_upper.startswith(p) for p in creature_prefixes):
            return
        if any(super_upper.startswith(p) for p in creature_prefixes):
            return
        # If supermodel is 'NULL' or empty, model is self-contained → skip outlier check
        if not super_upper or super_upper in ('NULL', 'NONE', '0'):
            return

        # Collect visible non-skin nodes (the "anchor geometry")
        # PERFORMANCE: Sample at most 100 vertices per node for Z-centroid
        # (full iteration is O(total_verts) and too slow for high-poly models)
        _MAX_SAMPLE = 100
        ns_zs = []
        ns_visible = []
        for n in m.mesh_nodes():
            if n.is_skin or not n.vertices:
                continue
            if self._is_deformation_helper(n):
                continue
            wp = n.world_position()
            verts = n.vertices
            step = max(1, len(verts) // _MAX_SAMPLE)
            for v in verts[::step]:
                ns_zs.append(v[2] + wp[2])
            ns_visible.append(n)

        # Require at least 3 non-skin visible nodes for a reliable anchor
        if len(ns_visible) < 3:
            return

        anchor_z = sum(ns_zs) / len(ns_zs)

        # Collect skin nodes
        skin_nodes = []
        for n in m.mesh_nodes():
            if not n.is_skin or not n.vertices:
                continue
            if self._is_deformation_helper(n):
                continue
            # Determine if this model is an accessory (non-base supermodel).
            # For accessory models, skin vertices are in bone-local space and
            # need the node's world-position Z added to get world Z.
            # For standalone models (NULL supermodel / base skeleton), skin
            # vertices are already in world/model space.
            verts = n.vertices
            step = max(1, len(verts) // _MAX_SAMPLE)
            raw_zs = [v[2] for v in verts[::step]]

            # All skin nodes store vertices in node-local space.
            # Always add the node's world Z to get world Z for outlier detection.
            wp_s = n.world_position()
            zs = [v + wp_s[2] for v in raw_zs]
            node_cz = sum(zs) / len(zs) if zs else 0.0
            skin_nodes.append((n, node_cz, abs(node_cz - anchor_z)))

        if not skin_nodes:
            return

        # ── Strategy A: Z-distance outlier ──────────────────────────────────
        candidates_a = [item for item in skin_nodes if item[2] > 1.5]

        # ── Strategy B: vertex-count ratio (face-overlay proxy detection) ───
        # If non-skin pieces are all tiny (≤50 verts), a skin node with
        # > 5× the max non-skin vertex count is a body proxy.
        # EXCEPTION: skin nodes with a real texture AND UVs are never
        # body proxies; they are the primary visible geometry (e.g. ad_saul body).
        max_ns_verts = max(len(n.vertices) for n in ns_visible)
        candidates_b = []
        if max_ns_verts <= 50:
            vcount_threshold = max(max_ns_verts * 5, 100)
            for n, cz, dist in skin_nodes:
                if len(n.vertices) < vcount_threshold:
                    continue
                # Skip if the node has a real texture with UVs (it's renderable geometry)
                tex = _clean_tex_name(n.texture)
                if tex and tex.upper() not in ('NULL', '') and n.uvs:
                    continue  # real textured skin node – keep it
                candidates_b.append((n, cz, dist))

        # Merge candidates (union of both strategies)
        candidate_ids = {id(n) for n, _, _ in candidates_a}
        candidate_ids |= {id(n) for n, _, _ in candidates_b}
        candidates = [(n, cz, d) for n, cz, d in skin_nodes if id(n) in candidate_ids]

        # Guard: don't filter if more than half of skin nodes would be hidden
        if len(candidates) > len(skin_nodes) * 0.5:
            return

        for n, cz, dist in candidates:
            self._outlier_skin_nodes.add(id(n))

    def _is_outlier_skin(self, node: 'ModelNode') -> bool:
        """Return True if this node is a far-outlier skin proxy in an accessory model."""
        return id(node) in self._outlier_skin_nodes
