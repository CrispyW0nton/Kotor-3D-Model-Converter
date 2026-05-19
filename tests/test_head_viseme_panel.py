"""M6 / T603 — Viseme Test Panel tests.

Validates that the inspector's HEAD-mode Step-5 page exposes a
16-button viseme palette (one per :class:`lip_reader.LIPShape`),
that visibility toggles in lock-step with the Head Facial Palette,
and that clicking a button emits ``applyVisemeRequested`` with the
correct integer index.

Test harness mirrors :mod:`tests.test_head_inspector` — a duck-typed
FakeMode object lets us assert HEAD-mode behaviour without depending
on the pykotor-importing :mod:`core` package.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.panels.qt_inspector_panel import QtInspectorPanel


# ── Fixtures ─────────────────────────────────────────────────────────


class _FakeHeadMode:
    name = "HEAD"
    value = "head"

    def __str__(self) -> str:
        return "head"


class _FakeBodyMode:
    name = "HEADLESS_BODY"
    value = "headless_body"

    def __str__(self) -> str:
        return "headless_body"


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def inspector(qapp):
    ip = QtInspectorPanel()
    # Step 5 = Face / LIP-Phoneme test page.
    ip.set_step(5)
    yield ip
    ip.deleteLater()


# ── Tests ────────────────────────────────────────────────────────────


def test_t603_viseme_panel_hidden_by_default(inspector):
    """The viseme panel is hidden until HEAD mode is activated."""
    assert inspector._head_viseme_panel is not None
    assert inspector._head_viseme_panel.isHidden() is True


def test_t603_viseme_panel_revealed_in_head_mode(inspector):
    """Setting HEAD mode reveals both palette and viseme panel."""
    inspector.set_active_mode(_FakeHeadMode())
    assert inspector._head_face_palette.isHidden() is False
    assert inspector._head_viseme_panel.isHidden() is False


def test_t603_viseme_panel_hidden_in_body_mode(inspector):
    """Switching back to BODY mode hides the viseme panel again."""
    inspector.set_active_mode(_FakeHeadMode())
    inspector.set_active_mode(_FakeBodyMode())
    assert inspector._head_viseme_panel.isHidden() is True


def test_t603_viseme_panel_hidden_when_mode_none(inspector):
    """Clearing the mode (None) hides the viseme panel."""
    inspector.set_active_mode(_FakeHeadMode())
    inspector.set_active_mode(None)
    assert inspector._head_viseme_panel.isHidden() is True


def test_t603_viseme_panel_exposes_16_buttons(inspector):
    """The panel renders one button per :class:`LIPShape` value."""
    btns = inspector.head_viseme_buttons()
    assert len(btns) == 16
    assert sorted(btns.keys()) == list(range(16))


def test_t603_viseme_button_dict_is_a_copy(inspector):
    """``head_viseme_buttons()`` returns a shallow copy."""
    first = inspector.head_viseme_buttons()
    first[99] = None                                        # type: ignore[assignment]
    second = inspector.head_viseme_buttons()
    assert 99 not in second


def test_t603_clicking_button_emits_index(inspector):
    """Clicking a viseme button emits ``applyVisemeRequested(index)``."""
    btns = inspector.head_viseme_buttons()
    captured: list[int] = []
    inspector.applyVisemeRequested.connect(captured.append)
    btns[3].click()
    assert captured == [3]


def test_t603_each_button_emits_its_own_index(inspector):
    """Every button emits its corresponding LIPShape index."""
    btns = inspector.head_viseme_buttons()
    captured: list[int] = []
    inspector.applyVisemeRequested.connect(captured.append)
    for idx in (0, 5, 8, 15):
        btns[idx].click()
    assert captured == [0, 5, 8, 15]


def test_t603_signal_exists_with_int_type(inspector):
    """``applyVisemeRequested`` is a signal accepting an int."""
    sig = getattr(inspector, "applyVisemeRequested", None)
    assert sig is not None
    # Smoke-emit to confirm the signal carries int payloads.
    captured: list[int] = []
    sig.connect(captured.append)
    sig.emit(7)
    assert captured == [7]


def test_t603_button_label_contains_index_and_name(inspector):
    """Each button's label includes both the index and the LIPShape name."""
    btns = inspector.head_viseme_buttons()
    txt0 = btns[0].text()
    # Expect index "0" and the canonical NEUTRAL name in the label.
    assert "0" in txt0
    assert "NEUTRAL" in txt0.upper()


def test_t603_button_tooltip_mentions_lipshape(inspector):
    """Tooltips reference the LIPShape index for traceability."""
    btns = inspector.head_viseme_buttons()
    assert "LIPShape" in btns[0].toolTip()


def test_t603_set_viseme_status_updates_label(inspector):
    """``set_viseme_status`` mutates the status label safely."""
    inspector.set_active_mode(_FakeHeadMode())              # reveal panel
    inspector.set_viseme_status("Applied viseme 3 (EE)", kind="ok")
    assert "EE" in inspector._viseme_status.text()
    inspector.set_viseme_status("No head loaded", kind="error")
    assert "head loaded" in inspector._viseme_status.text().lower()


def test_t603_set_viseme_status_unknown_kind_falls_back(inspector):
    """Unknown ``kind`` values are tolerated (treated as info)."""
    inspector.set_viseme_status("misc", kind="bogus")
    assert "misc" in inspector._viseme_status.text()


def test_t603_set_active_mode_is_idempotent_for_viseme(inspector):
    """Re-applying HEAD mode keeps the viseme panel visible."""
    inspector.set_active_mode(_FakeHeadMode())
    inspector.set_active_mode(_FakeHeadMode())
    assert inspector._head_viseme_panel.isHidden() is False
