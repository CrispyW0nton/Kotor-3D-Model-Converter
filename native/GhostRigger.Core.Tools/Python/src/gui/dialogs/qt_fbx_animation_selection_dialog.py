"""Qt dialog for choosing the animation takes embedded in an FBX export.

The dialog owns presentation only.  Animation discovery and materialisation
remain in the Character Workflow layer; callers pass the already-resolved
catalog rows and read back the checked animation names.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Sequence, Tuple

from PySide6 import QtCore, QtWidgets


_PROFILE_LABELS = {
    "standard": "Standard FBX",
    "unity": "Unity-Compatible FBX",
    "unreal": "Unreal Engine-Compatible FBX",
    "unreal_engine": "Unreal Engine-Compatible FBX",
    "3ds_max": "3ds Max-Compatible FBX",
    "3dsmax": "3ds Max-Compatible FBX",
}

_NAME_ROLE = int(QtCore.Qt.ItemDataRole.UserRole)
_IS_LOCAL_ROLE = _NAME_ROLE + 1


def _row_value(row: object, *names: str, default: Any = None) -> Any:
    """Return the first available field from a mapping or row dataclass."""
    if isinstance(row, Mapping):
        for name in names:
            if name in row:
                return row[name]
        return default
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return default


def _duration_text(row: object) -> str:
    value = _row_value(
        row,
        "duration_seconds",
        "duration",
        "length_seconds",
        "length",
        default=None,
    )
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.3f} s"
    return str(value)


class QtFbxAnimationSelectionDialog(QtWidgets.QDialog):
    """Select the ordered animation takes to embed in a target-profile FBX."""

    def __init__(
        self,
        rows: Sequence[object],
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        profile: str = "standard",
        initial_selected_names: Optional[Sequence[str]] = None,
        current_animation_name: str = "",
    ) -> None:
        super().__init__(parent)
        self.setModal(True)

        profile_key = str(profile or "standard").strip().lower()
        self._profile_label = _PROFILE_LABELS.get(profile_key, str(profile or "Standard FBX"))
        self._current_animation_name = str(current_animation_name or "").strip()
        self.setWindowTitle(f"Select FBX Animation Sets — {self._profile_label}")

        initial = {
            str(name).strip().casefold()
            for name in (initial_selected_names or ())
            if str(name).strip()
        }

        layout = QtWidgets.QVBoxLayout(self)

        intro = QtWidgets.QLabel(
            f"Choose the animation sets to embed in the {self._profile_label} file. "
            "Only checked takes are exported."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._search_edit = QtWidgets.QLineEdit()
        self._search_edit.setObjectName("fbxAnimationSearchEdit")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setPlaceholderText("Search animation, source model, or scope…")
        self._search_edit.setToolTip("Filter the available animation-set catalog.")
        layout.addWidget(self._search_edit)

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setObjectName("fbxAnimationSetList")
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(("Animation", "Source", "Scope", "Duration"))
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(False)
        self._tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._tree.setToolTip(
            "Checked animations are embedded as separate FBX takes in the displayed order."
        )
        header = self._tree.header()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self._tree, 1)

        seen_names: set[str] = set()
        for row in rows:
            name = str(_row_value(row, "name", "animation_name", default="") or "").strip()
            folded_name = name.casefold()
            if not name or folded_name in seen_names:
                continue
            seen_names.add(folded_name)

            source = str(
                _row_value(
                    row,
                    "source_model_name",
                    "source_model",
                    "source",
                    default="",
                )
                or ""
            ).strip()
            inherited = bool(_row_value(row, "inherited", "is_inherited", default=False))
            scope_value = _row_value(row, "scope", default=None)
            scope = str(scope_value or ("Inherited" if inherited else "Local")).strip()
            explicit_local = _row_value(row, "is_local", default=None)
            is_local = (
                bool(explicit_local)
                if explicit_local is not None
                else (not inherited and scope.casefold() == "local")
            )

            item = QtWidgets.QTreeWidgetItem((name, source, scope, _duration_text(row)))
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                0,
                QtCore.Qt.CheckState.Checked
                if folded_name in initial
                else QtCore.Qt.CheckState.Unchecked,
            )
            item.setData(0, _NAME_ROLE, name)
            item.setData(0, _IS_LOCAL_ROLE, is_local)
            self._tree.addTopLevelItem(item)

        selection_row = QtWidgets.QHBoxLayout()
        self._select_current_button = QtWidgets.QPushButton("Select Current")
        self._select_current_button.setObjectName("fbxAnimationSelectCurrentButton")
        self._select_current_button.setEnabled(bool(self._current_animation_name))
        self._select_current_button.setToolTip(
            "Check only the animation currently selected in the Animation Browser."
        )
        selection_row.addWidget(self._select_current_button)

        self._select_local_button = QtWidgets.QPushButton("Select Local")
        self._select_local_button.setObjectName("fbxAnimationSelectLocalButton")
        self._select_local_button.setToolTip("Check animations stored directly on this model.")
        selection_row.addWidget(self._select_local_button)

        self._select_all_button = QtWidgets.QPushButton("Select All")
        self._select_all_button.setObjectName("fbxAnimationSelectAllButton")
        self._select_all_button.setToolTip(
            "Check every animation visible under the current filter and clear hidden rows."
        )
        selection_row.addWidget(self._select_all_button)

        self._select_none_button = QtWidgets.QPushButton("Clear")
        self._select_none_button.setObjectName("fbxAnimationSelectNoneButton")
        self._select_none_button.setToolTip("Export the mesh and rig without animation clips.")
        selection_row.addWidget(self._select_none_button)
        selection_row.addStretch(1)
        layout.addLayout(selection_row)

        self._summary_label = QtWidgets.QLabel()
        self._summary_label.setObjectName("fbxAnimationSelectionSummary")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        ok_button = buttons.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setText("Continue")
            ok_button.setProperty("accent", True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._search_edit.textChanged.connect(self._apply_filter)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._select_current_button.clicked.connect(self._select_current)
        self._select_local_button.clicked.connect(self._select_local)
        self._select_all_button.clicked.connect(self._select_all)
        self._select_none_button.clicked.connect(self._select_none)
        self._update_summary()

    def selected_animation_names(self) -> Tuple[str, ...]:
        """Return checked animation names in the stable displayed order."""
        names = []
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            if item.checkState(0) == QtCore.Qt.CheckState.Checked:
                names.append(str(item.data(0, _NAME_ROLE) or item.text(0)))
        return tuple(names)

    def _set_checked(self, predicate) -> None:
        self._tree.blockSignals(True)
        try:
            for index in range(self._tree.topLevelItemCount()):
                item = self._tree.topLevelItem(index)
                item.setCheckState(
                    0,
                    QtCore.Qt.CheckState.Checked
                    if predicate(item)
                    else QtCore.Qt.CheckState.Unchecked,
                )
        finally:
            self._tree.blockSignals(False)
        self._update_summary()

    @QtCore.Slot(str)
    def _apply_filter(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        for index in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(index)
            searchable = " ".join(item.text(column) for column in range(4)).casefold()
            item.setHidden(bool(query and query not in searchable))

    @QtCore.Slot(QtWidgets.QTreeWidgetItem, int)
    def _on_item_changed(self, _item: QtWidgets.QTreeWidgetItem, column: int) -> None:
        if column == 0:
            self._update_summary()

    @QtCore.Slot()
    def _select_current(self) -> None:
        current = self._current_animation_name.casefold()
        self._set_checked(
            lambda item: str(item.data(0, _NAME_ROLE) or "").casefold() == current
        )

    @QtCore.Slot()
    def _select_local(self) -> None:
        self._set_checked(lambda item: bool(item.data(0, _IS_LOCAL_ROLE)))

    @QtCore.Slot()
    def _select_all(self) -> None:
        # Filtering is an export-selection tool, not merely a visual search.
        # Clear hidden rows so a user can filter to one supermodel/source and
        # export exactly that visible subset with a single click.
        self._set_checked(lambda item: not item.isHidden())

    @QtCore.Slot()
    def _select_none(self) -> None:
        self._set_checked(lambda _item: False)

    def _update_summary(self) -> None:
        count = len(self.selected_animation_names())
        if count == 0:
            self._summary_label.setText(
                "0 animation clips selected — the FBX will contain the mesh and rig only."
            )
            return
        noun = "clip" if count == 1 else "clips"
        self._summary_label.setText(
            f"{count} animation {noun} selected for {self._profile_label}."
        )


__all__ = ["QtFbxAnimationSelectionDialog"]
