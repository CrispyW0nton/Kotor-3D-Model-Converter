"""M6 / T604 — Phoneme Calibration Panel tests.

Validates that the inspector's HEAD-mode Step-5 page exposes an
8-row phoneme calibration panel (one row per
:data:`head_workflow.PHONEME_POSES` entry), each with a viseme combo
pre-selected to the canonical mapping, and that clicking *Apply*
emits ``calibratePhonemeRequested(label, viseme_index)`` with the
combo's current viseme.

Test harness mirrors :mod:`tests.test_head_viseme_panel` — a
duck-typed FakeMode object lets us assert HEAD-mode behaviour
without depending on the pykotor-importing :mod:`core` package.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib.util as _u
import pathlib as _pl
import sys as _sys

import pytest
from PySide6 import QtCore, QtWidgets

from src.gui.qt_lib.panels.qt_inspector_panel import QtInspectorPanel


# ── Direct-file load of head_workflow (sidestep core/__init__) ────────


def _load_head_workflow_direct():
    """Load ``head_workflow`` via :mod:`importlib.util` to skip ``core/__init__``."""
    _here = _pl.Path(__file__).resolve().parents[1] / "src" / "core"
    spec = _u.spec_from_file_location(
        "_gr_hw_phoneme_test", str(_here / "head_workflow.py")
    )
    mod = _u.module_from_spec(spec)
    _sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


HW = _load_head_workflow_direct()


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
    ip.set_step(5)
    yield ip
    ip.deleteLater()


def _apply_buttons(panel: QtWidgets.QGroupBox):
    """Return the Apply buttons in row order (one per phoneme)."""
    return [
        btn for btn in panel.findChildren(QtWidgets.QPushButton)
        if btn.text() == "Apply"
    ]


# ── Tests ────────────────────────────────────────────────────────────


def test_t604_phoneme_panel_hidden_by_default(inspector):
    """Panel is hidden until HEAD mode is activated."""
    assert inspector._head_phoneme_panel is not None
    assert inspector._head_phoneme_panel.isHidden() is True


def test_t604_phoneme_panel_revealed_in_head_mode(inspector):
    """Activating HEAD mode reveals the phoneme panel."""
    inspector.set_active_mode(_FakeHeadMode())
    assert inspector._head_phoneme_panel.isHidden() is False


def test_t604_phoneme_panel_hidden_in_body_mode(inspector):
    """BODY mode hides the phoneme panel again."""
    inspector.set_active_mode(_FakeHeadMode())
    inspector.set_active_mode(_FakeBodyMode())
    assert inspector._head_phoneme_panel.isHidden() is True


def test_t604_phoneme_panel_hidden_when_mode_none(inspector):
    """Clearing the mode (None) hides the panel."""
    inspector.set_active_mode(_FakeHeadMode())
    inspector.set_active_mode(None)
    assert inspector._head_phoneme_panel.isHidden() is True


def test_t604_exposes_8_phoneme_combos(inspector):
    """One combo per :data:`PHONEME_POSES` entry (8 total)."""
    combos = inspector.head_phoneme_combos()
    assert len(combos) == 8
    expected_labels = {label for label, _ in HW.PHONEME_POSES}
    assert set(combos.keys()) == expected_labels


def test_t604_combos_default_to_canonical_visemes(inspector):
    """Each combo pre-selects the canonical viseme index for its phoneme."""
    combos = inspector.head_phoneme_combos()
    for label, expected_idx in HW.PHONEME_POSES:
        combo = combos[label]
        assert combo.currentData() == expected_idx, (
            f"{label} default = {combo.currentData()} (expected {expected_idx})"
        )


def test_t604_each_combo_has_16_visemes(inspector):
    """Each combo lists every available LIPShape viseme."""
    combos = inspector.head_phoneme_combos()
    for label, combo in combos.items():
        assert combo.count() == 16, (
            f"{label} combo has {combo.count()} items (expected 16)"
        )


def test_t604_combo_dict_is_a_copy(inspector):
    """``head_phoneme_combos()`` returns a shallow copy."""
    first = inspector.head_phoneme_combos()
    first["JUNK"] = None                                    # type: ignore[assignment]
    second = inspector.head_phoneme_combos()
    assert "JUNK" not in second


def test_t604_signal_exists_with_str_int_payload(inspector):
    """``calibratePhonemeRequested`` carries ``(str, int)``."""
    sig = getattr(inspector, "calibratePhonemeRequested", None)
    assert sig is not None
    captured: list = []
    sig.connect(lambda l, i: captured.append((l, i)))
    sig.emit("AH (open vowel)", 9)
    assert captured == [("AH (open vowel)", 9)]


def test_t604_apply_button_emits_default_viseme(inspector):
    """Clicking Apply without changing the combo emits the canonical viseme."""
    captured: list = []
    inspector.calibratePhonemeRequested.connect(
        lambda l, i: captured.append((l, i))
    )
    buttons = _apply_buttons(inspector._head_phoneme_panel)
    assert len(buttons) == 8
    # First row = "AH (open vowel)" → canonical viseme 1.
    buttons[0].click()
    assert captured == [("AH (open vowel)", 1)]


def test_t604_apply_button_emits_modified_viseme(inspector):
    """Changing a combo then clicking Apply emits the new viseme."""
    combos = inspector.head_phoneme_combos()
    captured: list = []
    inspector.calibratePhonemeRequested.connect(
        lambda l, i: captured.append((l, i))
    )
    label = "EH (mid vowel)"
    combos[label].setCurrentIndex(12)                       # arbitrary new viseme
    buttons = _apply_buttons(inspector._head_phoneme_panel)
    # EH is the second phoneme — second Apply button.
    buttons[1].click()
    expected_viseme = combos[label].currentData()
    assert captured == [(label, expected_viseme)]


def test_t604_each_apply_button_emits_its_own_label(inspector):
    """Clicking row N's Apply emits row N's phoneme label."""
    combos = inspector.head_phoneme_combos()
    expected_labels = [label for label, _ in HW.PHONEME_POSES]

    captured: list = []
    inspector.calibratePhonemeRequested.connect(
        lambda l, i: captured.append(l)
    )
    buttons = _apply_buttons(inspector._head_phoneme_panel)
    for btn in buttons:
        btn.click()
    assert captured == expected_labels


def test_t604_set_phoneme_status_updates_label(inspector):
    """``set_phoneme_status`` mutates the status label safely."""
    inspector.set_active_mode(_FakeHeadMode())
    inspector.set_phoneme_status("Calibrated AH → 7", kind="ok")
    assert "AH" in inspector._phoneme_status.text()
    inspector.set_phoneme_status("Failed: bad index", kind="error")
    assert "Failed" in inspector._phoneme_status.text()


def test_t604_set_phoneme_status_unknown_kind_falls_back(inspector):
    """Unknown ``kind`` is tolerated (treated as info)."""
    inspector.set_phoneme_status("misc note", kind="bogus")
    assert "misc note" in inspector._phoneme_status.text()


def test_t604_set_active_mode_is_idempotent_for_phoneme(inspector):
    """Re-applying HEAD keeps the phoneme panel visible."""
    inspector.set_active_mode(_FakeHeadMode())
    inspector.set_active_mode(_FakeHeadMode())
    assert inspector._head_phoneme_panel.isHidden() is False
