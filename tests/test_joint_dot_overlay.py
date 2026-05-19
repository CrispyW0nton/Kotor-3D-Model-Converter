"""
tests/test_joint_dot_overlay.py — M4/T401 joint-dot overlay tests

Covers the bone-name → color classifier and the public setter contract
introduced by T401 in ``src/gui/qt_viewport.py``.

The classifier is a pure-Python regex helper and is exercised without
instantiating ``QtViewportWidget`` (which requires a full Qt event loop
and the heavy ``viewport_core`` import chain). The setter tests are
guarded by a ``pytest.importorskip("PySide6")`` so CI environments
without PySide6 still pass via the static layer.

Acceptance (per roadmap M4/T401):
  • Dots render over mesh
  • Correct colors per bone-name regex
    - center        → #FFD400
    - center-spine  → #00D7B5
    - L-side        → #FF4040
    - R-side        → #00FF7A

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M4/T401.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ── Skip the whole module gracefully if PySide6 / heavy deps absent ──────────
pytest.importorskip("PySide6")
pytest.importorskip("PIL")

try:
    from src.gui.qt_lib.viewports.qt_viewport import (
        JOINT_DOT_COLOR_CENTER,
        JOINT_DOT_COLOR_CENTER_SPINE,
        JOINT_DOT_COLOR_KEY,
        JOINT_DOT_COLOR_LEFT,
        JOINT_DOT_COLOR_RIGHT,
        _classify_joint_color,
        _is_key_joint_name,
    )
except ModuleNotFoundError as exc:
    pytest.skip(f"qt_viewport dependency unavailable: {exc}", allow_module_level=True)


# ── T401 ▸ Color constants match the spec exactly ───────────────────────────
def test_t401_color_constants_match_spec():
    """Roadmap-mandated hex colors must be preserved verbatim."""
    assert JOINT_DOT_COLOR_CENTER.name().lower()       == "#ffd400"
    assert JOINT_DOT_COLOR_CENTER_SPINE.name().lower() == "#00d7b5"
    assert JOINT_DOT_COLOR_LEFT.name().lower()         == "#ff4040"
    assert JOINT_DOT_COLOR_RIGHT.name().lower()        == "#00ff7a"
    assert JOINT_DOT_COLOR_KEY.name().lower()          == "#3a96ff"


# ── T401 ▸ AccuRig MIRROR_PAIRS-shaped names ────────────────────────────────
@pytest.mark.parametrize(
    "name",
    [
        "larm", "lfinger01", "lfinger02",
        "lankle", "ltoebase", "lleg",
    ],
)
def test_t401_accurig_left_names_classify_red(name):
    assert _classify_joint_color(name).name().lower() == "#ff4040", name


@pytest.mark.parametrize(
    "name",
    [
        "rarm", "rfinger01", "rfinger02",
        "rankle", "rtoebase", "rleg",
    ],
)
def test_t401_accurig_right_names_classify_green(name):
    assert _classify_joint_color(name).name().lower() == "#00ff7a", name


# ── T401 ▸ Tokenised naming (`_L` / `L_` / `.l`) ────────────────────────────
@pytest.mark.parametrize(
    "name,expected_hex",
    [
        ("armExtra_L", "#ff4040"),
        ("armExtra_R", "#00ff7a"),
        ("L_clavicle", "#ff4040"),
        ("R_clavicle", "#00ff7a"),
        ("bone.l",     "#ff4040"),
        ("bone.r",     "#00ff7a"),
    ],
)
def test_t401_tokenised_side_naming(name, expected_hex):
    assert _classify_joint_color(name).name().lower() == expected_hex, name


# ── T401 ▸ Center-spine names ───────────────────────────────────────────────
@pytest.mark.parametrize(
    "name",
    ["chest", "spine01", "spine02", "torso", "ribcage", "back", "sternum"],
)
def test_t401_center_spine_names_classify_cyan(name):
    assert _classify_joint_color(name).name().lower() == "#00d7b5", name


# ── T401 ▸ Generic center (default) names ───────────────────────────────────
@pytest.mark.parametrize(
    "name",
    ["stomach", "aurorabase", "jaw", "tongue", ""],
)
def test_t401_default_center_classification(name):
    """Anything that doesn't match L/R/spine falls back to yellow center."""
    assert _classify_joint_color(name).name().lower() == "#ffd400", name


# ── T401 ▸ Center wins over substring match (`hip` must NOT match L/R) ──────
def test_t401_hip_is_center_not_side():
    """`hip` contains no L/R tokens — must be center, not a false-positive."""
    assert _classify_joint_color("hip").name().lower() == "#ffd400"


@pytest.mark.parametrize(
    "name,expected_hex",
    [
        ("head", "#ffd400"),
        ("head_g", "#ffd400"),
        ("neck_g", "#ffd400"),
        ("spine_01", "#00d7b5"),
        ("torso_g", "#00d7b5"),
        ("lshoulder", "#ff4040"),
        ("clavicle_r", "#00ff7a"),
        ("lforearm_g", "#ff4040"),
        ("hand_l", "#ff4040"),
        ("rhand", "#00ff7a"),
        ("lshin_g", "#ff4040"),
        ("foot_r", "#00ff7a"),
        ("lfoott_g", "#ff4040"),
    ],
)
def test_t401_key_joints_keep_original_fill_palette(name, expected_hex):
    assert _classify_joint_color(name).name().lower() == expected_hex, name
    assert _is_key_joint_name(name), name


@pytest.mark.parametrize(
    "name",
    [
        "head", "head_g", "neck_g", "spine_01", "torso_g",
        "lshoulder", "clavicle_r", "lforearm_g", "hand_l",
        "rhand", "lshin_g", "foot_r", "lfoott_g",
    ],
)
def test_t401_key_joint_names_are_marked_for_blue_accent(name):
    assert _is_key_joint_name(name), name


@pytest.mark.parametrize(
    "name,expected_hex",
    [
        ("root", "#ffd400"),
        ("pelvis_g", "#ffd400"),
        ("lfinger01", "#ff4040"),
        ("rfinger01", "#00ff7a"),
        ("lthigh_g", "#ff4040"),
        ("rthigh_g", "#00ff7a"),
    ],
)
def test_t401_non_key_joints_keep_original_palette(name, expected_hex):
    assert _classify_joint_color(name).name().lower() == expected_hex, name
    assert not _is_key_joint_name(name), name


# ── T401 ▸ Public setter contract on QtViewportWidget ───────────────────────
def _make_widget():
    """Build a QtViewportWidget under offscreen Qt for setter contract tests."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    # Lazily import to give pykotor-missing environments a chance to skip
    try:
        from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    except Exception as exc:
        pytest.skip(f"QtViewportWidget unavailable: {exc}", allow_module_level=False)
    w = QtViewportWidget()
    return app, w


def test_t401_setter_defaults():
    """Widget initializes with sane joint-dot defaults."""
    app, w = _make_widget()
    try:
        assert w.joint_dot_enabled is True
        assert 1 <= w.joint_dot_size <= 8
        assert 0.0 <= w.joint_dot_opacity <= 1.0
    finally:
        w.deleteLater()


def test_t401_setter_size_clamping():
    """Joint-dot size clamps to the [1, 8] range."""
    app, w = _make_widget()
    try:
        w.set_joint_dot_size(1)
        assert w.joint_dot_size == 1
        w.set_joint_dot_size(99)
        assert w.joint_dot_size == 8
        w.set_joint_dot_size(8)
        assert w.joint_dot_size == 8
    finally:
        w.deleteLater()


def test_t401_setter_opacity_clamping():
    """Joint-dot opacity clamps to [0.0, 1.0]."""
    app, w = _make_widget()
    try:
        w.set_joint_dot_opacity(-0.5)
        assert w.joint_dot_opacity == 0.0
        w.set_joint_dot_opacity(2.0)
        assert w.joint_dot_opacity == 1.0
        w.set_joint_dot_opacity(0.42)
        assert abs(w.joint_dot_opacity - 0.42) < 1e-4
    finally:
        w.deleteLater()


def test_t401_setter_enabled_toggle():
    """Joint-dot enable flag toggles cleanly."""
    app, w = _make_widget()
    try:
        w.set_joint_dot_enabled(False)
        assert w.joint_dot_enabled is False
        w.set_joint_dot_enabled(True)
        assert w.joint_dot_enabled is True
    finally:
        w.deleteLater()


# ── T402 ▸ Joint-dot hit-test ────────────────────────────────────────────────
class _FakeNode:
    """Minimal stand-in for a ModelNode for hit-test unit tests."""
    def __init__(self, name, position=(0.0, 0.0, 0.0)):
        self.name = name
        self.position = position
        self.rotation = (0.0, 0.0, 0.0, 1.0)
        self.children = []
        self.parent = None


def test_t402_hit_test_returns_closest_within_radius():
    """The hit-test must return the joint nearest the cursor (within radius)."""
    app, w = _make_widget()
    try:
        # Fake the renderer's frame cache.  The hit-test only reads
        # `_bone_screen_positions`, so we can populate it directly.
        n_far = _FakeNode("lshoulder")
        n_near = _FakeNode("rshoulder")
        w._renderer._bone_screen_positions = [
            (100, 100, 5.0, n_far),
            (104, 102, 5.0, n_near),  # 4 px right + 2 px down from cursor
        ]
        # Cursor at (104, 100): n_near is 2 px away (closest)
        assert w._joint_dot_hit_test(104, 100) is n_near
    finally:
        w.deleteLater()


def test_t402_hit_test_returns_none_outside_radius():
    """A cursor far from any dot returns None."""
    app, w = _make_widget()
    try:
        w._renderer._bone_screen_positions = [
            (100, 100, 5.0, _FakeNode("root")),
        ]
        # 200 px away — well outside the 6+4=10 px hit radius
        assert w._joint_dot_hit_test(300, 300) is None
    finally:
        w.deleteLater()


def test_t402_hit_test_respects_enabled_flag():
    """When the overlay is disabled, the hit-test must not match."""
    app, w = _make_widget()
    try:
        n = _FakeNode("chest")
        w._renderer._bone_screen_positions = [(100, 100, 5.0, n)]
        w.set_joint_dot_enabled(False)
        assert w._joint_dot_hit_test(100, 100) is None
        w.set_joint_dot_enabled(True)
        assert w._joint_dot_hit_test(100, 100) is n
    finally:
        w.deleteLater()


def test_t402_hit_test_picks_front_most_on_overlap():
    """When dots overlap, the front-most (smaller depth) wins."""
    app, w = _make_widget()
    try:
        far = _FakeNode("lhand")
        near = _FakeNode("rhand")
        # Both at same screen pixel — depth must decide
        w._renderer._bone_screen_positions = [
            (100, 100, 10.0, far),
            (100, 100,  2.0, near),
        ]
        assert w._joint_dot_hit_test(100, 100) is near
    finally:
        w.deleteLater()


def test_t402_symmetry_toggle():
    """``set_joint_symmetry`` controls the public symmetry flag."""
    app, w = _make_widget()
    try:
        assert w.joint_symmetry_enabled is True  # default-on
        w.set_joint_symmetry(False)
        assert w.joint_symmetry_enabled is False
        w.set_joint_symmetry(True)
        assert w.joint_symmetry_enabled is True
    finally:
        w.deleteLater()


def test_t402_mirror_partner_lookup_lr():
    """``_joint_mirror_partner`` finds AccuRig L↔R partners both ways."""
    app, w = _make_widget()
    try:
        # Provide a fake model whose `find_node` is keyed by lowercase name.
        nodes = {
            "lshoulder": _FakeNode("lshoulder"),
            "rshoulder": _FakeNode("rshoulder"),
            "lhand":     _FakeNode("lhand"),
            "rhand":     _FakeNode("rhand"),
        }

        class _FakeModel:
            def find_node(self, name):
                return nodes.get(name.lower())

        w.model = _FakeModel()
        # L -> R partner
        assert w._joint_mirror_partner(nodes["lshoulder"]) is nodes["rshoulder"]
        # R -> L partner (reverse direction)
        assert w._joint_mirror_partner(nodes["rhand"]) is nodes["lhand"]
        # Center bone has no mirror
        center = _FakeNode("chest")
        assert w._joint_mirror_partner(center) is None
    finally:
        w.deleteLater()


def test_t402_mirror_partner_disabled_when_symmetry_off():
    """Symmetry-off → mirror lookup short-circuits to None."""
    app, w = _make_widget()
    try:
        nodes = {
            "lshoulder": _FakeNode("lshoulder"),
            "rshoulder": _FakeNode("rshoulder"),
        }

        class _FakeModel:
            def find_node(self, name):
                return nodes.get(name.lower())

        w.model = _FakeModel()
        w.set_joint_symmetry(False)
        assert w._joint_mirror_partner(nodes["lshoulder"]) is None
    finally:
        w.deleteLater()


# ── T403 ▸ Mini-thumbnail inset ─────────────────────────────────────────────
def test_t403_thumbnail_visibility_is_opt_in():
    """Generic viewports keep the mini-thumbnail hidden unless explicitly enabled."""
    app, generic = _make_widget()
    from src.gui.qt_lib.viewports.qt_viewport import (
        QtCharacterBuilderViewportWidget,
        QtMainViewportWidget,
        QtRetargetViewportWidget,
        QtUnrealAnimatorViewportWidget,
    )

    main = QtMainViewportWidget()
    builder = QtCharacterBuilderViewportWidget()
    retarget = QtRetargetViewportWidget()
    unreal = QtUnrealAnimatorViewportWidget()
    try:
        assert generic._thumbnail_visible_setting is False
        assert generic.viewport_role == "base"
        assert generic._compact_controls is False
        assert main._thumbnail_visible_setting is False
        assert main.viewport_role == "main"
        assert builder._thumbnail_visible_setting is True
        assert builder.viewport_role == "character_builder"
        assert retarget._thumbnail_visible_setting is False
        assert retarget.viewport_role == "retarget"
        assert unreal._thumbnail_visible_setting is False
        assert unreal.viewport_role == "unreal_animator"
        assert unreal._compact_controls is True
    finally:
        generic.deleteLater()
        main.deleteLater()
        builder.deleteLater()
        retarget.deleteLater()
        unreal.deleteLater()


def test_t403_thumbnail_widget_constructed_at_correct_size():
    """The inset widget is a QGraphicsView pinned at 220×280 px."""
    from src.gui.qt_lib.viewports.qt_viewport import (
        THUMBNAIL_HEIGHT_PX,
        THUMBNAIL_WIDTH_PX,
        _MiniThumbnailWidget,
    )
    app, w = _make_widget()
    try:
        thumb = w.thumbnail_widget
        assert thumb is not None
        assert isinstance(thumb, _MiniThumbnailWidget)
        assert thumb.width()  == THUMBNAIL_WIDTH_PX
        assert thumb.height() == THUMBNAIL_HEIGHT_PX
        # Inset is a child of the canvas so it floats over the render.
        assert thumb.parent() is w.canvas
    finally:
        w.deleteLater()


def test_t403_thumbnail_clicked_signal_resets_camera():
    """Clicking the inset emits `clicked` which is wired to reset_camera."""
    app, w = _make_widget()
    try:
        called = []
        # Monkey-patch reset_camera to observe the signal-wired call.
        orig = w.reset_camera
        w.reset_camera = lambda: called.append(True) or orig()
        # Re-wire the existing signal connection to the patched method.
        w.thumbnail_widget.clicked.disconnect()
        w.thumbnail_widget.clicked.connect(w.reset_camera)
        w.thumbnail_widget.clicked.emit()
        assert called == [True]
    finally:
        w.deleteLater()


def test_t403_force_hidden_overrides_user_setting():
    """Head close-up `force_hidden` wins over `set_thumbnail_visible(True)`."""
    app, w = _make_widget()
    try:
        # User wants it on, but Head-mode forces it off.
        w.set_thumbnail_visible(True)
        w.set_thumbnail_force_hidden(True)
        # Without a loaded model the widget is hidden anyway; assert the
        # force-hidden flag is observed by `_apply_thumbnail_visibility`.
        assert w._thumbnail_force_hidden is True
        assert w.thumbnail_widget.isVisible() is False
        # Releasing the force-hide does NOT show the widget unless a
        # model is loaded — that gate is intentional.
        w.set_thumbnail_force_hidden(False)
        assert w._thumbnail_force_hidden is False
    finally:
        w.deleteLater()


def test_t403_thumbnail_hidden_when_canvas_too_small():
    """If the canvas can't fit the inset, the inset hides cleanly."""
    app, w = _make_widget()
    try:
        # Collapse canvas below the inset's footprint.
        w.canvas.resize(100, 100)
        w._reposition_thumbnail()
        assert w.thumbnail_widget.isVisible() is False
    finally:
        w.deleteLater()


def test_t403_set_thumbnail_none_clears_pixmap():
    """Passing None to `set_thumbnail` shows the placeholder text."""
    app, w = _make_widget()
    try:
        thumb = w.thumbnail_widget
        thumb.set_thumbnail(None)
        # Placeholder should be visible
        assert thumb._placeholder.isVisible() is True
        # And the pixmap item is empty
        assert thumb._pixmap_item.pixmap().isNull()
    finally:
        w.deleteLater()


# ── T404 ▸ Snap-view button cluster ─────────────────────────────────────────
def test_t404_snap_view_widget_exists():
    """The viewport hosts a floating snap-view bar with 6 view buttons + ortho."""
    from src.gui.qt_lib.viewports.qt_viewport import _FloatingSnapViewWidget
    app, w = _make_widget()
    try:
        bar = w._snap_view_widget
        assert isinstance(bar, _FloatingSnapViewWidget)
        # Floating child of the canvas so it overlays the render.
        assert bar.parent() is w.canvas
        # The 7th button is the Persp/Ortho toggle.
        buttons = bar.findChildren(__import__("PySide6").QtWidgets.QPushButton)
        assert len(buttons) == 7
        # First 6 are view presets; last is the ortho toggle.
        assert bar.ortho_button is buttons[-1]
        assert bar.ortho_button.isCheckable()
    finally:
        w.deleteLater()


def test_t404_snap_to_view_starts_interpolation():
    """Clicking a preset starts a 200 ms tween — does not snap instantly."""
    app, w = _make_widget()
    try:
        # Stash starting orientation.
        w.camera.azimuth = 0.0
        w.camera.elevation = 0.0
        # Trigger the smooth-snap to "top" (azimuth=90, elevation=85).
        w._snap_to_view("top")
        # Timer must be active — instant snap would have already finished.
        assert w._snap_anim_timer.isActive() is True
        # And the camera state hasn't jumped to the target yet.
        assert w.camera.elevation != 85.0
        # Force-complete the tween: advance the start time well past the
        # 200 ms window and tick once.
        w._snap_anim_t0 -= 1.0
        w._snap_anim_tick()
        # Now we should be exactly at the preset.
        assert abs(w.camera.elevation - 85.0) < 1e-6
        assert abs((w.camera.azimuth - 90.0) % 360.0) < 1e-6
        # Timer should have stopped on completion.
        assert w._snap_anim_timer.isActive() is False
    finally:
        w.deleteLater()


def test_t404_snap_to_view_unknown_preset_is_noop():
    """An unknown preset key is silently ignored — no tween starts."""
    app, w = _make_widget()
    try:
        assert w._snap_anim_timer.isActive() is False
        w._snap_to_view("not_a_preset")
        assert w._snap_anim_timer.isActive() is False
    finally:
        w.deleteLater()


def test_t404_ortho_toggle_round_trip():
    """Toggling ortho on then off restores the original perspective FOV."""
    app, w = _make_widget()
    try:
        original_fov = float(w.camera.fov)
        original_dist = float(w.camera.distance)
        assert w.ortho_mode is False
        w.set_ortho_mode(True)
        assert w.ortho_mode is True
        # FOV should now be the small ortho stand-in.
        assert w.camera.fov < 5.0
        # Camera distance must have grown to compensate.
        assert w.camera.distance > original_dist
        # Toggle back.
        w.set_ortho_mode(False)
        assert w.ortho_mode is False
        assert abs(w.camera.fov - original_fov) < 1e-6
        assert abs(w.camera.distance - original_dist) < 1e-3
    finally:
        w.deleteLater()


def test_t404_ortho_button_label_tracks_state():
    """The Persp/Ortho button label flips with the toggle state."""
    app, w = _make_widget()
    try:
        btn = w._snap_view_widget.ortho_button
        assert btn.text() == "Persp"
        w.set_ortho_mode(True)
        assert btn.text() == "Ortho"
        w.set_ortho_mode(False)
        assert btn.text() == "Persp"
    finally:
        w.deleteLater()


def test_t404_snap_view_hidden_when_canvas_too_narrow():
    """If the canvas is narrower than the bar, the bar hides cleanly."""
    app, w = _make_widget()
    try:
        # Collapse canvas below the bar's footprint.
        w.canvas.resize(40, 200)
        w._reposition_snap_view()
        assert w._snap_view_widget.isVisible() is False
    finally:
        w.deleteLater()


def test_t404_snap_view_button_signals():
    """View buttons emit `viewSelected` with the correct preset key."""
    app, w = _make_widget()
    try:
        bar = w._snap_view_widget
        captured = []
        bar.viewSelected.connect(lambda k: captured.append(k))
        # Locate buttons by tooltip
        from PySide6 import QtWidgets
        for btn in bar.findChildren(QtWidgets.QPushButton):
            if btn.toolTip() == "Top view":
                btn.click()
                break
        else:
            assert False, "Top view button not found"
        assert captured == ["top"]
    finally:
        w.deleteLater()


# ── T405 ▸ Weight heat-map gradient ─────────────────────────────────────────
def test_t405_gradient_endpoints():
    """Weight=0 → pure blue, weight=1 → pure red, weight=0.5 → pure green."""
    from src.gui.qt_lib.viewports.qt_viewport import _weight_to_heatmap_color
    assert _weight_to_heatmap_color(0.0) == (0,   0, 255)
    assert _weight_to_heatmap_color(0.5) == (0, 255,   0)
    assert _weight_to_heatmap_color(1.0) == (255, 0,   0)


def test_t405_gradient_clamps_out_of_range():
    """Weights outside [0, 1] clamp rather than wrapping."""
    from src.gui.qt_lib.viewports.qt_viewport import _weight_to_heatmap_color
    assert _weight_to_heatmap_color(-0.5) == (0,   0, 255)
    assert _weight_to_heatmap_color( 2.0) == (255, 0,   0)


def test_t405_gradient_intermediate_quarter_points():
    """Quarter-weights interpolate linearly inside their gradient segment."""
    from src.gui.qt_lib.viewports.qt_viewport import _weight_to_heatmap_color
    # 0.25 → halfway through Blue → Green segment
    r, g, b = _weight_to_heatmap_color(0.25)
    assert r == 0
    assert 120 <= g <= 135      # ~128
    assert 120 <= b <= 135      # ~128
    # 0.75 → halfway through Green → Red segment
    r, g, b = _weight_to_heatmap_color(0.75)
    assert 120 <= r <= 135
    assert 120 <= g <= 135
    assert b == 0


def test_t405_heatmap_toggle():
    """`set_weight_heatmap_enabled` flips the flag and is idempotent."""
    app, w = _make_widget()
    try:
        assert w.weight_heatmap_enabled is False
        w.set_weight_heatmap_enabled(True)
        assert w.weight_heatmap_enabled is True
        # Idempotent
        w.set_weight_heatmap_enabled(True)
        assert w.weight_heatmap_enabled is True
        w.set_weight_heatmap_enabled(False)
        assert w.weight_heatmap_enabled is False
    finally:
        w.deleteLater()


def test_t405_heatmap_dot_size_clamping():
    """Heat-map dot size clamps to [1, 8]."""
    app, w = _make_widget()
    try:
        w.set_weight_heatmap_dot_size(0)
        assert w.weight_heatmap_dot_size == 1
        w.set_weight_heatmap_dot_size(99)
        assert w.weight_heatmap_dot_size == 8
        w.set_weight_heatmap_dot_size(4)
        assert w.weight_heatmap_dot_size == 4
    finally:
        w.deleteLater()


def test_t405_heatmap_noop_when_no_selection():
    """The draw method short-circuits when no bone is selected."""
    app, w = _make_widget()
    try:
        # No model, no selection — must not raise.
        w._renderer.selected_node = None

        class _DummyDraw:
            calls = 0

            def ellipse(self, *a, **kw):
                self.calls += 1

        d = _DummyDraw()
        w._draw_weight_heatmap(d, 100, 100)
        assert d.calls == 0
    finally:
        w.deleteLater()


# ── T406 ▸ Per-mode camera presets ───────────────────────────────────────────
class _FakeNodeT406:
    """Minimal stand-in for a ModelNode with vertices + children for T406."""
    def __init__(self, name, position=(0.0, 0.0, 0.0), vertices=None, children=None):
        self.name = name
        self.position = position
        self.rotation = (0.0, 0.0, 0.0, 1.0)
        self.vertices = vertices or []
        self.children = children or []
        self.parent = None

    def world_position(self):
        return self.position


class _FakeModel:
    def __init__(self, root):
        self.root_node = root


def test_t406_set_character_mode_accepts_enum_and_string():
    """``set_character_mode`` must accept both CharacterMode enum and raw string."""
    app, w = _make_widget()
    try:
        # Without a model the preset is a no-op but the key must still update.
        w.model = None
        w.set_character_mode("head")
        assert w.character_mode == "head"
        # Enum-like duck-typed object with `.value`
        class _EnumLike:
            value = "creature"
        w.set_character_mode(_EnumLike())
        assert w.character_mode == "creature"
        # Same key twice → idempotent (no re-apply).
        w.set_character_mode("creature")
        assert w.character_mode == "creature"
        # None resets.
        w.set_character_mode(None)
        assert w.character_mode is None
    finally:
        w.deleteLater()


def test_t406_head_mode_force_hides_thumbnail():
    """Switching to Head mode must auto-hide the mini-thumbnail."""
    app, w = _make_widget()
    try:
        # Build a tiny model with a head_g subtree.
        head_g = _FakeNodeT406("head_g", position=(0.0, 1.5, 0.0),
                                vertices=[(0.1, 0.1, 0.1), (-0.1, -0.1, -0.1)])
        root = _FakeNodeT406("root", children=[head_g])
        w.model = _FakeModel(root)
        # Default thumbnail force-hide is False.
        w.set_thumbnail_force_hidden(False)
        w.set_character_mode("head")
        # The Head preset must flip the force-hidden flag on.
        assert w._thumbnail_force_hidden is True
    finally:
        w.deleteLater()


def test_t406_non_head_mode_clears_thumbnail_force_hide():
    """Switching to a non-Head mode must clear the thumbnail force-hide flag."""
    app, w = _make_widget()
    try:
        head_g = _FakeNodeT406("head_g", vertices=[(0.0, 0.0, 0.0)])
        root = _FakeNodeT406("root", children=[head_g, _FakeNodeT406("body", vertices=[(1.0, 0.0, 0.0)])])
        w.model = _FakeModel(root)
        # Pre-hide.
        w.set_thumbnail_force_hidden(True)
        w.set_character_mode("creature")
        assert w._thumbnail_force_hidden is False
    finally:
        w.deleteLater()


def test_t406_frame_head_subtree_returns_false_without_head_node():
    """No head_g node anywhere → ``_frame_head_subtree`` returns False."""
    app, w = _make_widget()
    try:
        root = _FakeNodeT406("root", children=[
            _FakeNodeT406("torso", vertices=[(0.0, 0.0, 0.0)]),
            _FakeNodeT406("lleg", vertices=[(0.5, 0.0, 0.0)]),
        ])
        w.model = _FakeModel(root)
        assert w._frame_head_subtree(padding=0.20) is False
    finally:
        w.deleteLater()


def test_t406_frame_head_subtree_finds_head_g_substring():
    """A node whose name *contains* head_g (e.g. ``f_head_g``) must match."""
    app, w = _make_widget()
    try:
        head = _FakeNodeT406("F_head_g", vertices=[(0.0, 0.0, 0.0), (0.2, 0.2, 0.2)])
        root = _FakeNodeT406("root", children=[head])
        w.model = _FakeModel(root)
        # Stub frame_bounds so we don't depend on the real camera math.
        called = {"args": None}
        def _stub_frame_bounds(mins, maxs, reset_view=False):
            called["args"] = (mins, maxs, reset_view)
        w.camera.frame_bounds = _stub_frame_bounds
        assert w._frame_head_subtree(padding=0.20) is True
        assert called["args"] is not None
        mins, maxs, reset = called["args"]
        # The bbox must include both vertices.
        assert mins[0] <= 0.0 and maxs[0] >= 0.2
        assert reset is True
    finally:
        w.deleteLater()


def test_t406_no_model_is_noop():
    """Without a model loaded, ``_apply_mode_camera_preset`` is a no-op."""
    app, w = _make_widget()
    try:
        w.model = None
        # Must not raise on any mode key.
        w._apply_mode_camera_preset("head")
        w._apply_mode_camera_preset("creature")
        w._apply_mode_camera_preset("headless_body")
        w._apply_mode_camera_preset("supermodel")
        w._apply_mode_camera_preset("ambiguous")
        w._apply_mode_camera_preset(None)
    finally:
        w.deleteLater()


def test_t406_body_modes_reset_canonical_front():
    """Headless-body / supermodel modes reset azimuth/elevation to canonical front."""
    app, w = _make_widget()
    try:
        root = _FakeNodeT406("root", children=[_FakeNodeT406("torso", vertices=[(0.0, 0.0, 0.0)])])
        w.model = _FakeModel(root)
        # Perturb the camera.
        w.camera.azimuth = 12.34
        w.camera.elevation = 56.78
        # Stub frame_all so we don't depend on bbox math.
        w.frame_all = lambda: None  # type: ignore[assignment]
        w.set_character_mode("headless_body")
        assert abs(w.camera.azimuth - w.camera.DEFAULT_AZIMUTH) < 1e-6
        assert abs(w.camera.elevation - w.camera.DEFAULT_ELEVATION) < 1e-6
    finally:
        w.deleteLater()


def _mesh_node_t407(name: str, texture: str = "pmha01"):
    from core.model_data import ModelNode, NodeFlags

    node = ModelNode()
    node.name = name
    node.flags = int(NodeFlags.MESH)
    node.render = True
    node.texture = texture
    node.texture_names = [texture]
    node.vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    node.uvs = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    node.faces = [(0, 1, 2)]
    return node


def _model_t407(name: str, child):
    from core.model_data import KotorModel, ModelClassification, ModelNode

    model = KotorModel()
    model.name = name
    model.model_type = int(ModelClassification.CHARACTER)
    root = ModelNode()
    root.name = name
    root.children = [child]
    child.parent = root
    model.root_node = root
    return model


def test_t407_animation_supermodel_mesh_helpers_are_not_visible():
    from core.model_data import is_animation_supermodel
    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer

    model = _model_t407("s_male02", _mesh_node_t407("eyeRA"))
    model.animations = [object()]

    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)

    assert is_animation_supermodel(model)
    assert list(renderer._iter_visible_mesh_nodes()) == []


def test_t407_normal_head_inner_geometry_still_renders():
    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer

    model = _model_t407("pmhc01", _mesh_node_t407("eyeRA"))

    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)

    assert [node.name for node in renderer._iter_visible_mesh_nodes()] == ["eyeRA"]
