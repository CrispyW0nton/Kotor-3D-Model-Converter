"""
tests/test_head_inspector.py — M6 / T602 Head Inspector palette tests.

Covers the M6 additions to :class:`gui.qt_inspector_panel.QtInspectorPanel`:

  * :meth:`set_active_mode` toggles the Face-Rig page between the
    legacy mask / midpoint controls and the new Head Facial Palette.
  * The palette exposes a button per canonical KotOR facial bone
    (REQUIRED ∪ RECOMMENDED ∪ FACE_RIG_BONES).
  * Clicking a bone button emits ``headFacialBoneSelected(name)``.
  * The new ``rigHeadRequested`` / ``rigFaceRequested`` signals fire
    when the Rig Head / Rig Face buttons are clicked.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M6/T602.
"""

from __future__ import annotations

import importlib.util as _il_util
import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


pytest.importorskip("PySide6")


def _load_module_direct(name: str, path: pathlib.Path):
    """Direct-file import that side-steps ``core/__init__``."""
    spec = _il_util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:                  # pragma: no cover
        raise ImportError(f"cannot create import spec for {path}")
    module = _il_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    md = _load_module_direct(
        "ghostrigger_md_for_head_inspector",
        _SRC_DIR / "core" / "model_data.py",
    )
    hw = _load_module_direct(
        "ghostrigger_head_workflow_for_inspector",
        _SRC_DIR / "core" / "head_workflow.py",
    )
except Exception as exc:                                     # pragma: no cover
    pytest.skip(f"model_data / head_workflow unavailable: {exc}",
                allow_module_level=True)


# Set offscreen platform *before* QApplication is created.
import os                                                    # noqa: E402
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets                        # noqa: E402

try:
    from gui.qt_inspector_panel import QtInspectorPanel
except Exception as exc:                                     # pragma: no cover
    pytest.skip(f"QtInspectorPanel unavailable: {exc}",
                allow_module_level=True)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


@pytest.fixture
def inspector(qapp):
    p = QtInspectorPanel()
    yield p
    p.deleteLater()


# ──────────────────────────────────────────────────────────────────────
#  T602 ▸ Mode-aware page composition
# ──────────────────────────────────────────────────────────────────────

def test_t602_inspector_starts_with_legacy_face_layout(inspector):
    """Without set_active_mode, the legacy face controls are visible."""
    assert inspector.active_mode() is None
    assert inspector._face_legacy_widgets, "expected at least one legacy widget"
    assert not inspector._face_legacy_widgets[0].isHidden()
    # Head palette is built but hidden by default.
    assert inspector._head_face_palette is not None
    assert inspector._head_face_palette.isHidden()


def test_t602_set_active_mode_head_shows_palette_hides_legacy(inspector):
    inspector.set_active_mode(md.CharacterMode.HEAD)
    assert inspector.active_mode() == md.CharacterMode.HEAD
    # Palette becomes visible.
    assert not inspector._head_face_palette.isHidden()
    # Legacy controls retired (M5 invariant #4).
    for w in inspector._face_legacy_widgets:
        assert w.isHidden(), f"legacy widget {w} should be hidden in HEAD mode"


def test_t602_set_active_mode_body_restores_legacy(inspector):
    inspector.set_active_mode(md.CharacterMode.HEAD)
    inspector.set_active_mode(md.CharacterMode.HEADLESS_BODY)
    assert inspector.active_mode() == md.CharacterMode.HEADLESS_BODY
    assert inspector._head_face_palette.isHidden()
    for w in inspector._face_legacy_widgets:
        assert not w.isHidden()


def test_t602_set_active_mode_none_restores_legacy(inspector):
    inspector.set_active_mode(md.CharacterMode.HEAD)
    inspector.set_active_mode(None)
    assert inspector.active_mode() is None
    assert inspector._head_face_palette.isHidden()


def test_t602_set_active_mode_creature_does_not_show_palette(inspector):
    inspector.set_active_mode(md.CharacterMode.CREATURE)
    # CREATURE keeps legacy controls (faces of creatures use a different rig).
    assert inspector._head_face_palette.isHidden()
    for w in inspector._face_legacy_widgets:
        assert not w.isHidden()


def test_t602_set_active_mode_is_idempotent(inspector):
    inspector.set_active_mode(md.CharacterMode.HEAD)
    inspector.set_active_mode(md.CharacterMode.HEAD)
    inspector.set_active_mode(md.CharacterMode.HEAD)
    assert not inspector._head_face_palette.isHidden()


# ──────────────────────────────────────────────────────────────────────
#  T602 ▸ Head Facial Palette button surface
# ──────────────────────────────────────────────────────────────────────

def test_t602_palette_exposes_all_required_bones(inspector):
    btns = inspector.head_facial_bone_buttons()
    for bone in hw.REQUIRED_HEAD_BONES:
        assert bone in btns, f"required bone {bone!r} not in palette"


def test_t602_palette_exposes_all_recommended_bones(inspector):
    btns = inspector.head_facial_bone_buttons()
    for bone in hw.RECOMMENDED_HEAD_BONES:
        assert bone in btns, f"recommended bone {bone!r} not in palette"


def test_t602_palette_exposes_all_face_rig_bones(inspector):
    btns = inspector.head_facial_bone_buttons()
    for bone in hw.FACE_RIG_BONES:
        assert bone in btns, f"face-rig bone {bone!r} not in palette"


def test_t602_palette_button_dict_is_a_copy(inspector):
    """Mutating the returned dict must not affect the internal store."""
    first = inspector.head_facial_bone_buttons()
    first.clear()
    second = inspector.head_facial_bone_buttons()
    assert second                                          # still populated


# ──────────────────────────────────────────────────────────────────────
#  T602 ▸ Signal emission on button click
# ──────────────────────────────────────────────────────────────────────

def test_t602_clicking_facial_bone_button_emits_signal(inspector):
    captured: list = []
    inspector.headFacialBoneSelected.connect(captured.append)
    btns = inspector.head_facial_bone_buttons()
    btns["f_jaw_g"].click()
    assert captured == ["f_jaw_g"]


def test_t602_each_bone_button_emits_its_own_name(inspector):
    """Late-binding bug check: every button must carry its own bone name."""
    captured: list = []
    inspector.headFacialBoneSelected.connect(captured.append)
    btns = inspector.head_facial_bone_buttons()
    names_to_check = ["head_g", "f_jaw_g", "f_um_g",
                      "necklwr_g", "f_lec_g", "maskhook"]
    for name in names_to_check:
        if name in btns:
            btns[name].click()
    # Order should match the click sequence exactly.
    assert captured == [n for n in names_to_check if n in btns]


# ──────────────────────────────────────────────────────────────────────
#  T602 ▸ Rig Head / Rig Face signals
# ──────────────────────────────────────────────────────────────────────

def test_t602_rig_head_signal_exists(inspector):
    """The inspector must expose a rigHeadRequested signal."""
    sig = getattr(inspector, "rigHeadRequested", None)
    assert sig is not None
    # Smoke test: emit it manually (no receiver is fine).
    sig.emit()


def test_t602_rig_face_signal_exists(inspector):
    sig = getattr(inspector, "rigFaceRequested", None)
    assert sig is not None
    sig.emit()


def test_t602_rig_head_button_emits_signal(inspector):
    """Locate the Rig Head button by text and confirm it emits."""
    captured: list = []
    inspector.rigHeadRequested.connect(lambda: captured.append("rig_head"))
    # Find the button in the palette.
    palette = inspector._head_face_palette
    rig_head_btn = None
    for btn in palette.findChildren(QtWidgets.QPushButton):
        if btn.text() == "Rig Head":
            rig_head_btn = btn
            break
    assert rig_head_btn is not None
    rig_head_btn.click()
    assert captured == ["rig_head"]


def test_t602_rig_face_button_emits_signal(inspector):
    captured: list = []
    inspector.rigFaceRequested.connect(lambda: captured.append("rig_face"))
    palette = inspector._head_face_palette
    rig_face_btn = None
    for btn in palette.findChildren(QtWidgets.QPushButton):
        if btn.text() == "Rig Face":
            rig_face_btn = btn
            break
    assert rig_face_btn is not None
    rig_face_btn.click()
    assert captured == ["rig_face"]
