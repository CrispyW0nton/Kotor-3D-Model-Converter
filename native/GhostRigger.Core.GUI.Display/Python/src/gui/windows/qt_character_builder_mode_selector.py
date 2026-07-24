"""Beginner-facing Character Builder product selector."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets


CHARACTER_BUILDER_MODES = (
    "native_kotor_character",
    "native_kotor_head",
    "custom_rigged_character",
)


class _ModeCard(QtWidgets.QGroupBox):
    activated = QtCore.Signal(str)

    def __init__(
        self,
        mode: str,
        title: str,
        description: str,
        *,
        badge: str = "",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.setObjectName(f"characterBuilderModeCard_{mode}")
        self.setProperty("ghostLayoutId", f"characterBuilderMode.{mode}")
        layout = QtWidgets.QVBoxLayout(self)
        heading = QtWidgets.QLabel(title)
        font = heading.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        heading.setFont(font)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        if badge:
            badge_label = QtWidgets.QLabel(badge)
            badge_label.setObjectName("characterBuilderModeBadge")
            badge_label.setProperty("role", "badge")
            badge_label.setToolTip(
                "Basic idle, walk, and run can use KOTOR's existing behavior names. "
                "The patch registers genuinely new actions without replacing vanilla animations."
            )
            layout.addWidget(badge_label, 0, QtCore.Qt.AlignLeft)
        copy = QtWidgets.QLabel(description)
        copy.setWordWrap(True)
        copy.setMinimumWidth(310)
        layout.addWidget(copy)
        layout.addStretch(1)
        button = QtWidgets.QPushButton(f"Choose {title}")
        button.setDefault(mode == "custom_rigged_character")
        button.clicked.connect(lambda _checked=False: self.activated.emit(self.mode))
        layout.addWidget(button)


class QtCharacterBuilderModeSelector(QtWidgets.QDialog):
    """Beginner-facing welcome screen for the independent builder products."""

    modeSelected = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Character Builder — Choose a character type")
        self.setObjectName("characterBuilderModeSelector")
        self.setProperty("ghostLayoutId", "characterBuilderModeSelector")
        self.setModal(False)
        self.resize(780, 440)

        outer = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("What kind of character are you building?")
        font = title.font()
        font.setPointSize(font.pointSize() + 5)
        font.setBold(True)
        title.setFont(font)
        outer.addWidget(title)
        intro = QtWidgets.QLabel(
            "Choose the workflow that matches your source. You can return here without changing either project."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        cards = QtWidgets.QHBoxLayout()
        native = _ModeCard(
            "native_kotor_character",
            "Native KOTOR Character",
            "Build a character using KOTOR-compatible body models, heads, equipment, and native animation conventions.",
            parent=self,
        )
        head = _ModeCard(
            "native_kotor_head",
            "Custom KOTOR Head",
            "Fit custom OBJ or FBX head art to a native KOTOR donor, preserve its attachment and animation contracts, and prepare a modular head package.",
            badge="Modular Head Builder",
            parent=self,
        )
        custom = _ModeCard(
            "custom_rigged_character",
            "Custom Rigged Character",
            "Convert a creature with its own skeleton, mesh, textures, and animations into a self-contained KOTOR model.",
            badge="Custom Animation Patch",
            parent=self,
        )
        native.activated.connect(self._choose)
        head.activated.connect(self._choose)
        custom.activated.connect(self._choose)
        cards.addWidget(native, 1)
        cards.addWidget(head, 1)
        cards.addWidget(custom, 1)
        outer.addLayout(cards, 1)

        close_button = QtWidgets.QPushButton("Cancel")
        close_button.clicked.connect(self.reject)
        outer.addWidget(close_button, 0, QtCore.Qt.AlignRight)

    def _choose(self, mode: str) -> None:
        self.modeSelected.emit(mode)
        self.accept()

    def apply_ghost_theme(self, _theme: object) -> None:
        """Use the application palette; no workflow-specific colors are fixed."""

        self.update()

    def apply_ghost_layout(self, _layout: object) -> None:
        self.adjustSize()


__all__ = ["CHARACTER_BUILDER_MODES", "QtCharacterBuilderModeSelector"]
