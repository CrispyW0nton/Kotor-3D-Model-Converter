"""ViewportConstruction methods for the Qt viewport widget."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403
from .mini_thumbnail import *  # noqa: F401,F403
from .snap_view_bar import *  # noqa: F401,F403


class ViewportConstructionMixin:
    def _build(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._root_layout = root

        tb = QtWidgets.QFrame()
        tb.setObjectName("ViewportToolbar")
        tb.setFrameShape(QtWidgets.QFrame.StyledPanel)
        tb.setLineWidth(1)
        tb.setMinimumHeight(30)
        self.viewport_toolbar = tb
        row = QtFlowLayout(
            tb,
            margin=0,
            hspacing=2 if self._compact_controls else 3,
            vspacing=2,
            horizontal_alignment=QtCore.Qt.AlignHCenter,
        )
        row.setContentsMargins(4 if self._compact_controls else 5, 3, 4 if self._compact_controls else 5, 3)

        self.renderer_button = self._icon_button(
            "GPU",
            self.toggle_gpu_renderer,
            "viewport_gpu",
            checkable=True,
            active=True,
            tooltip="GPU renderer",
        )
        self.renderer_button.setObjectName("ViewportGpuButton")
        self.renderer_button.setIcon(_gpu_icon())
        self.renderer_button.setIconSize(QtCore.QSize(28, 20))
        self.renderer_button.setFixedWidth(34)
        self.renderer_button.setMinimumWidth(34)
        self.renderer_button.setMaximumWidth(34)
        self.renderer_button.setStyleSheet("QPushButton#ViewportGpuButton { padding: 0px; }")
        self.solid_button = self._icon_button(
            "Solid",
            lambda _checked=False: self.set_shade_mode("solid"),
            "viewport_solid",
            checkable=True,
            active=True,
            tooltip="Solid mesh",
        )
        self.wire_button = self._icon_button(
            "Wire  W",
            lambda _checked=False: self.set_shade_mode("wire"),
            "viewport_wire",
            checkable=True,
            tooltip="Wireframe only (W)",
        )
        self.solid_wire_button = self._icon_button(
            "Solid + Wire",
            lambda _checked=False: self.set_shade_mode("both"),
            "viewport_solid_wire",
            checkable=True,
            tooltip="Solid mesh with wireframe overlay",
        )
        self.mesh_hover_button = self._icon_button(
            "Mesh Hover",
            self.toggle_mesh_hover,
            "viewport_mesh_hover",
            checkable=True,
            active=True,
            tooltip="Mesh hover highlight",
        )
        self.dummy_helpers_button = self._icon_button(
            "Dummy Helpers",
            self.toggle_dummy_helpers,
            "viewport_helpers",
            checkable=True,
            active=True,
            tooltip="Show or hide dummy helper markers",
        )
        self.dummy_helpers_button.setObjectName("ViewportDummyHelpersButton")
        self.light_helpers_button = self._icon_button(
            "Light Helpers + Volumes",
            self.toggle_light_helpers,
            "viewport_light_helpers",
            checkable=True,
            active=True,
            tooltip="Show or hide light helpers and volume previews",
        )
        self.light_helpers_button.setObjectName("ViewportLightHelpersButton")
        self.bones_button = self._icon_button(
            "Bones  B",
            self.toggle_bones,
            "viewport_bones",
            checkable=True,
            tooltip="Bones (B)",
        )
        self.texture_button = self._icon_button(
            "Texture  T",
            self.toggle_texture,
            "viewport_texture",
            checkable=True,
            active=True,
            tooltip="Texture (T)",
        )
        self.grid_button = self._icon_button(
            "Grid",
            self.toggle_grid,
            "viewport_grid",
            checkable=True,
            active=True,
            tooltip="Show or hide the viewport grid",
        )
        self.joint_dot_button = self._icon_button(
            "Dots",
            self.toggle_joint_dots,
            "viewport_dots",
            checkable=True,
            active=True,
            tooltip="Show or hide AccuRig joint-dot handles",
        )
        self.heatmap_button = self._icon_button(
            "Heat",
            self.toggle_weight_heatmap,
            "viewport_heat",
            checkable=True,
            tooltip="Show selected-bone weight heat-map",
        )
        self.xray_button = self._button(
            self._toolbar_text("X-Ray  Alt+X", "X"),
            self.toggle_xray,
            checkable=True,
            tooltip="X-Ray (Alt+X)",
        )
        self.xray_button.setVisible(False)
        self.xray_button.setEnabled(False)
        row.addWidget(self.renderer_button)
        row.addWidget(self.solid_button)
        row.addWidget(self.wire_button)
        row.addWidget(self.solid_wire_button)
        row.addWidget(self.mesh_hover_button)
        row.addWidget(self.dummy_helpers_button)
        row.addWidget(self.light_helpers_button)
        row.addWidget(self.bones_button)
        row.addWidget(self.texture_button)
        row.addWidget(self.grid_button)
        row.addWidget(self.joint_dot_button)
        row.addWidget(self.heatmap_button)
        row.addWidget(self._separator())

        self.render_realistic_button = self._icon_button(
            "Realistic",
            lambda _checked=False: self.set_render_mode("realistic"),
            "viewport_render_realistic",
            checkable=True,
            active=True,
            tooltip="Realistic shader",
        )
        self.render_shaded_button = self._icon_button(
            "Shaded",
            lambda _checked=False: self.set_render_mode("shaded"),
            "viewport_render_shaded",
            checkable=True,
            tooltip="Shaded shader",
        )
        self.render_flat_button = self._icon_button(
            "Flat",
            lambda _checked=False: self.set_render_mode("flat"),
            "viewport_render_flat",
            checkable=True,
            tooltip="Flat shader",
        )
        row.addWidget(self.render_realistic_button)
        row.addWidget(self.render_shaded_button)
        row.addWidget(self.render_flat_button)
        row.addWidget(self._separator())
        row.addWidget(self._icon_button("Frame  F", self.frame_all, "viewport_frame", tooltip="Frame all (F)"))
        self.center_pivot_button = self._icon_button(
            "Center Pivot",
            self.center_pivot_to_selection,
            "viewport_gimbal",
            tooltip="Center pivot on the selected object or mesh bounds",
        )
        self.center_pivot_button.setObjectName("ViewportCenterPivotButton")
        row.addWidget(self.center_pivot_button)
        self.freeze_transform_button = self._icon_button(
            "Freeze Transforms",
            self.freeze_selected_transform,
            "viewport_scale",
            tooltip="Bake the selected mesh transform into its vertices and reset transform values",
        )
        self.freeze_transform_button.setObjectName("ViewportFreezeTransformsButton")
        row.addWidget(self.freeze_transform_button)
        self.walkmesh_button = self._icon_button(
            "WalkMesh",
            self.toggle_walkmesh,
            "viewport_wire",
            checkable=True,
            tooltip="Walkmesh overlay",
        )
        self.walkmesh_button.hide()
        row.addWidget(self._separator())
        self.gimbal_button = self._icon_button(
            "Gimbal  G",
            self.toggle_gimbal,
            "viewport_gimbal",
            checkable=True,
            active=True,
            tooltip="Gimbal (G)",
        )
        row.addWidget(self.gimbal_button)
        self.gimbal_mode_button = self._icon_button(
            self._gimbal_mode_button_text(),
            self.cycle_gimbal_mode,
            self._gimbal_mode_icon_name(),
            tooltip="Cycle gimbal mode",
        )
        self._sync_gimbal_mode_button()
        row.addWidget(self.gimbal_mode_button)
        self.selection_mode_button = QtWidgets.QToolButton()
        self.selection_mode_button.setObjectName("ViewportSelectionModeButton")
        self.selection_mode_button.setProperty("_gr_ignore_layout_button_mode", True)
        self.selection_mode_button.setFixedSize(34, 22)
        self.selection_mode_button.setIconSize(QtCore.QSize(20, 18))
        self.selection_mode_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.selection_mode_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.selection_mode_button.setMenu(self._build_selection_mode_menu())
        self._sync_selection_mode_button()
        row.addWidget(self.selection_mode_button)
        self.measure_button = self._icon_button(
            "Measure",
            self.toggle_measurement_mode,
            "viewport_measure",
            checkable=True,
            tooltip="Distance measurement tool",
        )
        row.addWidget(self.measure_button)
        self.uv_button = self._icon_button(
            "UV View",
            self.open_uv_viewer,
            "viewport_uv",
            tooltip="Open UV view",
        )
        row.addWidget(self.uv_button)
        self.navigation_button = QtWidgets.QToolButton()
        self.navigation_button.setObjectName("ViewportNavigationButton")
        self.navigation_button.setProperty("_gr_ignore_layout_button_mode", True)
        self.navigation_button.setFixedSize(34, 22)
        self.navigation_button.setIconSize(QtCore.QSize(22, 18))
        self.navigation_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.navigation_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.navigation_button.setMenu(self._build_navigation_menu())
        self._sync_navigation_button()
        row.addWidget(self.navigation_button)
        self.lock_camera_button = self._icon_button(
            "Lock View To Camera",
            self.set_lock_view_to_camera,
            "viewport_lock_camera",
            checkable=True,
            tooltip="Lock viewport navigation to the active scene camera",
        )
        row.addWidget(self.lock_camera_button)
        row.addWidget(self._separator())
        self.axis_mode_control = AxisModeControl(self, compact=self._compact_controls)
        self.axis_mode_control.label.hide()
        self.axis_mode_control.axisModeChanged.connect(self.set_axis_mode)
        row.addWidget(self.axis_mode_control)

        self.canvas = RendererSurfaceHost(self)
        self.canvas.setObjectName("ViewportCanvas")
        self.canvas.setAlignment(QtCore.Qt.AlignCenter)
        self.canvas.setMinimumSize(120 if self._compact_controls else 180, 100 if self._compact_controls else 140)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Ignored if self._compact_controls else QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.canvas.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.canvas.setMouseTracking(True)
        self.canvas.setScaledContents(False)
        self.canvas.installEventFilter(self)
        self._install_label_renderer_surface("modern_gl")
        self._renderer.show_bones = self.bones_button.isChecked()
        self._renderer.show_texture = self.texture_button.isChecked()
        self._renderer.show_solid = True
        self._renderer.show_wireframe = False
        self._renderer.show_grid = self.grid_button.isChecked()
        self._renderer.show_dummy_helpers = self.dummy_helpers_button.isChecked()
        self._renderer.show_light_gizmos = self.light_helpers_button.isChecked()
        self._renderer.show_light_radius_volumes = self.light_helpers_button.isChecked()
        self._renderer.render_mode = "realistic"
        self._set_display_options(self._rebuild_display_options_from_renderer(), announce=False)
        self._sync_shade_buttons()
        self._sync_render_mode_buttons()

        toolbar_scroll = make_horizontal_overflow_area(
            tb,
            "ViewportToolbarScroll",
            height=44,
            parent=self,
        )
        toolbar_scroll.setMinimumWidth(0)
        self.viewport_toolbar_scroll = toolbar_scroll
        if self._compact_controls:
            toolbar_scroll.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
            root.addWidget(toolbar_scroll)
            self.setMinimumSize(140, 130)
            self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Expanding)
        else:
            root.addWidget(toolbar_scroll)
        root.addWidget(self.canvas, 1)
        self.transform_typein_bar = QtTransformTypeInBar(self)
        self.transform_typein_bar.transformValueEdited.connect(self._on_transform_typein_edited)
        self.transform_typein_bar.gridEdited.connect(self._on_grid_spacing_edited)
        self.transform_typein_bar.snapToggled.connect(self.toggle_snap)
        self.transform_typein_bar.angleSnapToggled.connect(self.toggle_angle_snap)
        self.transform_typein_bar.angleIncrementChanged.connect(self._on_angle_snap_increment_changed)
        self.transform_typein_bar.percentSnapToggled.connect(self.toggle_percent_snap)
        self.transform_typein_bar.percentIncrementChanged.connect(self._on_percent_snap_increment_changed)
        self.angle_snap_button = self.transform_typein_bar.angle_button
        self.angle_snap_combo = self.transform_typein_bar.angle_combo
        self.percent_snap_button = self.transform_typein_bar.percent_button
        self.percent_snap_combo = self.transform_typein_bar.percent_combo
        self.snap_button = self.transform_typein_bar.snap_button
        root.addWidget(self.transform_typein_bar)
        self._sync_transform_typein_bar()

        # ── T403: Mini-thumbnail inset (top-right) ────────────────────
        # Built as a child widget of `self.canvas` so it floats over the
        # main render and tracks canvas resize via `eventFilter`.  Click
        # the thumbnail to snap the main camera back to "frame all".
        self._thumbnail_widget = _MiniThumbnailWidget(self)
        self._thumbnail_widget.setParent(self.canvas)
        self._thumbnail_widget.clicked.connect(self.reset_camera)
        self._thumbnail_widget.hide()  # shown once a model is loaded
        self._thumbnail_force_hidden: bool = False  # set by Head close-up
        self._reposition_thumbnail()

        # ── T404: Snap-view button cluster (top-center) ────────────────
        # ViewCube overlay replaces the old visible snap buttons while
        # preserving their command layer below.
        self._viewcube_widget = ViewCubeWidget(self.canvas, camera_state=self._viewcube_camera_state)
        self._viewcube_widget.viewActionRequested.connect(self.execute_view_action)
        self._viewcube_widget.orientationRequested.connect(self.animate_to_orientation)
        self._viewcube_widget.dragOrbitRequested.connect(self.orbit_from_viewcube_drag)
        self._snap_view_widget = self._viewcube_widget
        # Animation state — driven by a QTimer at ~60 Hz for 200 ms.
        self._snap_anim_timer = QtCore.QTimer(self)
        self._snap_anim_timer.setInterval(int(1000.0 / SNAP_VIEW_INTERP_HZ))
        self._snap_anim_timer.timeout.connect(self._snap_anim_tick)
        self._snap_anim_t0: float = 0.0
        self._snap_anim_from = (0.0, 0.0)   # (azimuth, elevation)
        self._snap_anim_to = (0.0, 0.0)
        self._ortho_mode: bool = False
        self._reposition_viewcube()
        self.set_viewport_chrome_visible(
            toolbar=self._viewport_toolbar_visible,
            viewcube=self._viewcube_visible,
            transform_typein=self._transform_typein_visible,
        )

    def _install_label_renderer_surface(self, backend_id: str = "modern_gl") -> None:
        label = QtWidgets.QLabel("Empty Scene", self.canvas)
        label.setObjectName("ViewportImageSurface")
        label.setAlignment(QtCore.Qt.AlignCenter)
        label.setMinimumSize(120 if self._compact_controls else 180, 100 if self._compact_controls else 140)
        label.setSizePolicy(QtWidgets.QSizePolicy.Ignored if self._compact_controls else QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        label.setFocusPolicy(QtCore.Qt.StrongFocus)
        label.setMouseTracking(True)
        label.setScaledContents(False)
        self.canvas.set_renderer_surface(label, backend_id=backend_id, live_surface=False)
        self.canvas.install_input_bridge(self)

    def _active_renderer_backend_id(self) -> str:
        renderer = self._gpu_renderer
        if renderer is None:
            return str(getattr(self._renderer_settings.backend, "value", self._renderer_settings.backend))
        diagnostics = {}
        get_diagnostics = getattr(renderer, "get_diagnostics", None)
        if callable(get_diagnostics):
            try:
                diagnostics = get_diagnostics() or {}
            except Exception:
                diagnostics = {}
        return str(diagnostics.get("backend_id") or getattr(renderer, "backend_id", "") or "")

    @property
    def active_renderer(self):
        service = getattr(self, "renderer_service", None)
        if service is not None:
            viewport_service = getattr(service, "viewport_service", None)
            get_renderer = getattr(viewport_service, "get_active_renderer", None)
            if callable(get_renderer):
                return get_renderer()
        return self._gpu_renderer or self._renderer

    @property
    def active_renderer_backend(self) -> str:
        service = getattr(self, "active_viewport_service", None)
        get_backend = getattr(service, "get_active_renderer_backend", None)
        if callable(get_backend):
            return str(get_backend() or "")
        return self._active_renderer_backend_id()

    def request_renderer_resource_invalidation(self, reason: str = "") -> None:
        service = getattr(self, "renderer_service", None)
        invalidate = getattr(service, "request_resource_invalidation", None)
        if callable(invalidate):
            invalidate(reason or "viewport resource invalidation")
            return
        if self._gpu_renderer is not None and hasattr(self._gpu_renderer, "clear_caches"):
            self._gpu_renderer.clear_caches()
        self.refresh_view()

    def _renderer_uses_live_surface(self, backend_id: str) -> bool:
        backend = str(backend_id or "").lower()
        return backend.startswith("wgpu_") or backend == "pygfx_wgpu"

    def _sync_renderer_surface(self, *, force: bool = False) -> None:
        if self._gpu_renderer is None:
            if force or self.canvas.current_surface() is None:
                self._install_label_renderer_surface("modern_gl")
            return
        backend_id = self._active_renderer_backend_id()
        if not backend_id:
            backend_id = str(getattr(self._gpu_renderer, "backend_id", "") or "")
        live_surface = self._renderer_uses_live_surface(backend_id)
        current_surface = self.canvas.current_surface()
        if (
            current_surface is not None
            and self.canvas.surface_backend_id() == backend_id
            and self.canvas.is_live_surface() == live_surface
        ):
            active_renderer = getattr(self._gpu_renderer, "active_renderer", None) or self._gpu_renderer
            renderer_surface = getattr(active_renderer, "canvas", None) if live_surface else current_surface
            if not live_surface or renderer_surface is current_surface:
                self.canvas.install_input_bridge(self)
                return
            if not force:
                return
        if live_surface:
            create_surface = getattr(self._gpu_renderer, "create_surface_widget", None)
            if callable(create_surface):
                try:
                    surface = create_surface(self.canvas)
                    backend_id = self._active_renderer_backend_id() or backend_id
                    live_surface = self._renderer_uses_live_surface(backend_id)
                    self.canvas.set_renderer_surface(surface, backend_id=backend_id, live_surface=live_surface)
                    self.canvas.install_input_bridge(self)
                    self._apply_canvas_theme()
                    return
                except Exception as exc:
                    log.info("Live renderer surface creation failed, falling back through renderer factory: %s", exc)
        self._install_label_renderer_surface(backend_id or "modern_gl")
        self._apply_canvas_theme()

    def take_viewport_toolbar(self) -> QtWidgets.QWidget | None:
        """Detach the viewport tool strip so the application shell can host it."""

        toolbar_scroll = getattr(self, "viewport_toolbar_scroll", None)
        toolbar = getattr(self, "viewport_toolbar", None)
        if toolbar_scroll is None:
            return toolbar
        layout = getattr(self, "_root_layout", None) or self.layout()
        if layout is not None and layout.indexOf(toolbar_scroll) >= 0:
            layout.removeWidget(toolbar_scroll)
        if toolbar is not None and hasattr(toolbar_scroll, "takeWidget"):
            toolbar_scroll.takeWidget()
        toolbar_scroll.setParent(None)
        toolbar_scroll.deleteLater()
        self.viewport_toolbar_scroll = None
        return toolbar

    def set_viewport_chrome_visible(
        self,
        *,
        toolbar: bool | None = None,
        viewcube: bool | None = None,
        transform_typein: bool | None = None,
    ) -> None:
        """Show or hide optional viewport UI chrome for embedded workflows."""

        if toolbar is not None:
            self._viewport_toolbar_visible = bool(toolbar)
        if viewcube is not None:
            self._viewcube_visible = bool(viewcube)
        if transform_typein is not None:
            self._transform_typein_visible = bool(transform_typein)
        self._sync_viewport_chrome_visibility()
        self._request_render(fast=True)

    def _sync_viewport_chrome_visibility(self) -> None:
        toolbar_scroll = getattr(self, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setVisible(self._viewport_toolbar_visible)
        toolbar = self.findChild(QtWidgets.QFrame, "ViewportToolbar")
        if toolbar is not None:
            toolbar.setVisible(self._viewport_toolbar_visible)
        typein = getattr(self, "transform_typein_bar", None)
        if typein is not None:
            typein.setVisible(self._transform_typein_visible)
        cube = getattr(self, "_viewcube_widget", None)
        if cube is not None:
            if self._viewcube_visible:
                self._reposition_viewcube()
            else:
                cube.hide()

    @property
    def viewport_toolbar_chrome_visible(self) -> bool:
        return bool(self._viewport_toolbar_visible)

    @property
    def viewcube_chrome_visible(self) -> bool:
        return bool(self._viewcube_visible)

    @property
    def transform_typein_chrome_visible(self) -> bool:
        return bool(self._transform_typein_visible)

    def _button(
        self,
        text: str,
        callback,
        *,
        checkable: bool = False,
        active: bool = False,
        tooltip: Optional[str] = None,
    ) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.setProperty("_gr_full_text", text)
        button.setCheckable(checkable)
        button.setChecked(active if checkable else False)
        button.setFixedHeight(22)
        if self._compact_controls:
            width = max(24, min(58, button.fontMetrics().horizontalAdvance(text) + 16))
            button.setFixedWidth(width)
            button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        if tooltip:
            button.setToolTip(tooltip)
        button.clicked.connect(lambda checked=False: callback(checked) if checkable else callback())
        return button

    def _icon_button(
        self,
        text: str,
        callback,
        icon_name: str,
        *,
        checkable: bool = False,
        active: bool = False,
        tooltip: Optional[str] = None,
    ) -> QtWidgets.QPushButton:
        button = self._button(
            "",
            callback,
            checkable=checkable,
            active=active,
            tooltip=tooltip or text,
        )
        button.setProperty("_gr_full_text", text)
        button.setProperty("_gr_ignore_layout_button_mode", True)
        button.setIcon(_icon(icon_name))
        button.setIconSize(QtCore.QSize(18, 18))
        button.setFixedWidth(30)
        button.setMinimumWidth(30)
        button.setMaximumWidth(30)
        button.setToolTip(tooltip or text)
        return button

    def _apply_canvas_theme(self) -> None:
        theme = getattr(self, "_current_theme", None)
        if theme is None or not hasattr(self, "canvas"):
            return
        if self.canvas.is_live_surface():
            self.canvas.setAttribute(QtCore.Qt.WA_StyledBackground, False)
            self.canvas.setStyleSheet("background: transparent; border: 0;")
            return
        self.canvas.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.canvas.setStyleSheet(
            f"background:{theme.color('viewport.background')}; "
            f"color:{theme.color('viewport.text')}; "
            f"border:1px solid {theme.color('viewport.border')};"
        )

    def apply_ghost_theme(self, theme) -> None:
        self._current_theme = theme
        toolbar = self.findChild(QtWidgets.QFrame, "ViewportToolbar")
        if toolbar is not None:
            toolbar.setStyleSheet(
                f"#ViewportToolbar {{ background:{theme.color('viewportToolbar.background', theme.color('toolbar.background'))}; "
                f"border:1px solid {theme.color('viewportToolbar.border', theme.color('toolbar.border'))}; }}"
            )
        toolbar_scroll = getattr(self, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setStyleSheet(
                f"QScrollArea {{ background:{theme.color('viewportToolbar.background', theme.color('toolbar.background'))}; border:0; }}"
            )
        combo_style = (
            f"QComboBox {{ background:{theme.color('input.background')}; "
            f"color:{theme.color('input.text')}; border:1px solid {theme.color('input.border')}; "
            "padding:2px 18px 2px 7px; }"
            f"QComboBox:hover {{ border-color:{theme.color('accent.secondary')}; }}"
            "QComboBox::drop-down { border:0; width:16px; }"
            f"QComboBox QAbstractItemView {{ background:{theme.color('panel.backgroundAlt', theme.color('panel.altBackground'))}; "
            f"color:{theme.color('text.primary')}; selection-background-color:{theme.color('selection.background')}; }}"
        )
        for combo_name in ():
            combo = getattr(self, combo_name, None)
            if combo is not None:
                combo.setStyleSheet(combo_style)
        if hasattr(self, "axis_mode_control"):
            self.axis_mode_control.apply_ghost_theme(theme)
        for button in self.findChildren(QtWidgets.QPushButton):
            button.setStyleSheet("")
        for sep in self.findChildren(QtWidgets.QFrame):
            if sep.frameShape() == QtWidgets.QFrame.VLine:
                sep.setStyleSheet(f"background:{theme.color('panel.border')};")
        self._apply_canvas_theme()
        if hasattr(self._renderer, "set_theme_colors"):
            self._renderer.set_theme_colors(theme)
        if self._gpu_renderer is not None and hasattr(self._gpu_renderer, "set_theme_colors"):
            self._gpu_renderer.set_theme_colors(theme)
        if hasattr(self, "transform_typein_bar"):
            self.transform_typein_bar.apply_ghost_theme(theme)
        if hasattr(self, "_snap_view_widget"):
            self._snap_view_widget.apply_ghost_theme(theme)
        if hasattr(self, "_thumbnail_widget"):
            self._thumbnail_widget.apply_ghost_theme(theme)
        self._request_render(fast=True)

    def apply_native_theme(self) -> None:
        self._current_theme = None
        self.setStyleSheet("")
        for child in self.findChildren(QtWidgets.QWidget):
            child.setStyleSheet("")
        self._apply_native_palette_to_renderers()
        self._ensure_renderer_gimbal_state()
        self._request_render(fast=True)

    @staticmethod
    def _palette_rgb(palette: QtGui.QPalette, role: QtGui.QPalette.ColorRole) -> tuple[int, int, int]:
        color = palette.color(role)
        return (color.red(), color.green(), color.blue())

    def _apply_native_palette_to_renderers(self) -> None:
        app = QtWidgets.QApplication.instance()
        palette = app.palette() if app is not None else self.palette()
        native_colors = {
            "window": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Window),
            "base": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Base),
            "text": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Text),
            "button": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Button),
            "button_text": self._palette_rgb(palette, QtGui.QPalette.ColorRole.ButtonText),
            "mid": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Mid),
            "highlight": self._palette_rgb(palette, QtGui.QPalette.ColorRole.Highlight),
            "highlighted_text": self._palette_rgb(palette, QtGui.QPalette.ColorRole.HighlightedText),
        }
        if hasattr(self._renderer, "set_native_palette_colors"):
            self._renderer.set_native_palette_colors(**native_colors)
        elif hasattr(self._renderer, "reset_theme_colors"):
            self._renderer.reset_theme_colors()
        if self._gpu_renderer is not None:
            if hasattr(self._gpu_renderer, "set_native_palette_colors"):
                self._gpu_renderer.set_native_palette_colors(
                    base=native_colors["base"],
                    text=native_colors["text"],
                    highlight=native_colors["highlight"],
                )
            elif hasattr(self._gpu_renderer, "reset_theme_colors"):
                self._gpu_renderer.reset_theme_colors()

    def apply_ghost_layout(self, layout) -> None:
        toolbar = self.findChild(QtWidgets.QFrame, "ViewportToolbar")
        toolbar_layout = layout.toolbar("viewport")
        if toolbar is not None:
            toolbar.setVisible(self._viewport_toolbar_visible and toolbar_layout.visible and layout.viewport.toolbar_visible)
            toolbar.setMinimumHeight(toolbar_layout.height)
            toolbar.setMaximumHeight(16777215)
        toolbar_scroll = getattr(self, "viewport_toolbar_scroll", None)
        if toolbar_scroll is not None:
            toolbar_scroll.setVisible(self._viewport_toolbar_visible and toolbar_layout.visible and layout.viewport.toolbar_visible)
            toolbar_scroll.setFixedHeight(max(toolbar_layout.height + 14, toolbar_layout.height))
            parent = toolbar_scroll.parentWidget()
            if parent is not None and parent.objectName() == "ViewportToolbarBand":
                parent.setFixedHeight(toolbar_scroll.height())
        self._compact_controls = bool(layout.viewport.toolbar_compact)
        mode = getattr(layout.viewport, "toolbar_button_mode", toolbar_layout.button_mode)
        icon_size = toolbar_layout.icon_size
        from src.gui.libtheme.layout_applier import LayoutApplier

        LayoutApplier().apply_toolbar_button_mode(
            self,
            toolbar_layout.__class__(
                id=toolbar_layout.id,
                visible=toolbar_layout.visible,
                button_mode=mode,
                icon_size=icon_size,
                height=toolbar_layout.height,
            ),
        )
        self.canvas.setMinimumSize(
            max(120, layout.viewport.min_width // 4 if self._compact_controls else 180),
            100 if self._compact_controls else 140,
        )
        if hasattr(self, "transform_typein_bar"):
            self.transform_typein_bar.apply_ghost_layout(layout)
        if hasattr(self, "axis_mode_control"):
            self.axis_mode_control.apply_ghost_layout(layout)
        self._sync_viewport_chrome_visibility()

    def _separator(self) -> QtWidgets.QFrame:
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setFixedWidth(1)
        return sep

__all__ = ("ViewportConstructionMixin",)
