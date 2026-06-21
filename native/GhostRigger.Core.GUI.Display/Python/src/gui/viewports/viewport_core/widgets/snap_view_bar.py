"""Floating snap-view bar for the Qt viewport."""

from __future__ import annotations

from ..shared.dependencies import Optional, QtCore, QtWidgets

# ── T404: Snap-view button cluster ─────────────────────────────────────────
# A small floating widget pinned to the top-center of the viewport canvas
# offering one-click camera presets — Front / Back / Left / Right / Top /
# Bottom — plus a Persp/Ortho projection toggle.  Each preset triggers a
# smooth 200 ms interpolation rather than an instant snap so spatial
# orientation is preserved as the user navigates.
SNAP_VIEW_INTERP_MS    = 200    # smooth tween duration per roadmap T404
SNAP_VIEW_INTERP_HZ    = 60     # tween tick frequency
SNAP_VIEW_BAR_HEIGHT   = 28
SNAP_VIEW_BAR_MARGIN   = 8

# Azimuth / elevation per preset (degrees).  Matches `_set_camera_view`.
SNAP_VIEW_PRESETS = {
    "front":  ( 90.0,   0.0),
    "back":   (270.0,   0.0),
    "left":   (180.0,   0.0),
    "right":  (  0.0,   0.0),
    "top":    ( 90.0,  85.0),
    "bottom": ( 90.0, -85.0),
}


class _FloatingSnapViewWidget(QtWidgets.QWidget):
    """Top-center floating bar with 6 view-preset buttons + Persp/Ortho.

    The host widget connects to:
      • :attr:`viewSelected(str)` — emitted with a preset key (front/back/
        left/right/top/bottom) when the user clicks a view button.
      • :attr:`orthoToggled(bool)` — emitted when the Persp/Ortho toggle
        flips state (``True`` == orthographic).
    """

    viewSelected = QtCore.Signal(str)
    orthoToggled = QtCore.Signal(bool)

    # Layout: 6 view buttons, a separator, 1 projection toggle.
    _VIEW_BUTTONS = [
        ("F", "front",  "Front view"),
        ("B", "back",   "Back view"),
        ("L", "left",   "Left view"),
        ("R", "right",  "Right view"),
        ("T", "top",    "Top view"),
        ("Bo", "bottom", "Bottom view"),
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.setStyleSheet(
            "QWidget#snapBar {"
            "  background:rgba(20,22,27,200);"
            "  border:1px solid #3a3f47;"
            "  border-radius:5px;"
            "}"
            "QPushButton {"
            "  background:#2b2e33; color:#d7dde6; border:1px solid #464b53;"
            "  padding:1px 6px; min-width:18px; font-size:10pt;"
            "}"
            "QPushButton:hover { background:#363a40; border-color:#6d747f; }"
            "QPushButton:pressed { background:#1f2227; }"
            "QPushButton:checked {"
            "  background:#35506f; color:#ffffff; border-color:#6ea0d8;"
            "}"
        )
        self.setObjectName("snapBar")

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(4)

        for label, key, tip in self._VIEW_BUTTONS:
            btn = QtWidgets.QPushButton(label)
            btn.setToolTip(tip)
            btn.setFixedHeight(20)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=key: self.viewSelected.emit(k))
            row.addWidget(btn)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("background:#4a4f58;")
        sep.setFixedWidth(1)
        row.addWidget(sep)

        self._ortho_button = QtWidgets.QPushButton("Persp")
        self._ortho_button.setCheckable(True)
        self._ortho_button.setChecked(False)
        self._ortho_button.setToolTip("Toggle perspective / orthographic projection")
        self._ortho_button.setFixedHeight(20)
        self._ortho_button.setCursor(QtCore.Qt.PointingHandCursor)
        self._ortho_button.toggled.connect(self._on_ortho_toggled)
        row.addWidget(self._ortho_button)

        self.adjustSize()

    def apply_ghost_theme(self, theme) -> None:
        panel_bg = theme.color("panel.backgroundAlt", theme.color("panel.altBackground"))
        self.setStyleSheet(
            "QWidget#snapBar {"
            f"  background:{panel_bg};"
            f"  border:1px solid {theme.color('panel.border')};"
            "  border-radius:5px;"
            "}"
            "QPushButton {"
            f"  background:{theme.color('button.background')};"
            f"  color:{theme.color('button.text')};"
            f"  border:1px solid {theme.color('panel.border')};"
            "  padding:1px 6px; min-width:18px; font-size:10pt;"
            "}"
            "QPushButton:hover {"
            f"  background:{theme.color('button.hover')};"
            f"  border-color:{theme.color('input.focusBorder')};"
            "}"
            "QPushButton:pressed {"
            f"  background:{theme.color('button.pressed')};"
            "}"
            "QPushButton:checked {"
            f"  background:{theme.color('button.checked')};"
            f"  color:{theme.color('button.checkedText', theme.color('button.accentText'))};"
            f"  border-color:{theme.color('accent.primary')};"
            "}"
        )
        for sep in self.findChildren(QtWidgets.QFrame):
            sep.setStyleSheet(f"background:{theme.color('panel.border')};")

    def _on_ortho_toggled(self, checked: bool) -> None:
        self._ortho_button.setText("Ortho" if checked else "Persp")
        self.orthoToggled.emit(bool(checked))

    @property
    def ortho_button(self) -> QtWidgets.QPushButton:
        return self._ortho_button


__all__ = tuple(name for name in globals() if not name.startswith("__"))
