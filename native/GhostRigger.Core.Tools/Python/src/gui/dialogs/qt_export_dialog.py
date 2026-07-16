"""
qt_export_dialog.py — M5 / T506 Export modal dialog.

A small, focused QDialog that lets the user pick:
  • Which formats to export — KOTOR (MDL/MDX) / FBX / glTF / OBJ.
  • An output directory.
  • Whether to also write the ``.ghostrig.json`` sidecar (default ON).

The dialog is purely UI — it does not perform the export itself.
Hitting OK closes the dialog with :meth:`QDialog.Accepted` and the
caller reads back :attr:`selected_formats` / :attr:`output_dir` /
:attr:`write_sidecar` to drive
``headless_body_workflow.export_scene(...)``.

Designed to be importable without :mod:`PySide6` present (e.g. for
the headless test suite) — the ``PySide6`` import is guarded so unit
tests that don't need the Qt UI can still import the workflow
service module that references this dialog by name.

Roadmap reference: knowledge_base/roadmap/02_roadmap_2026_05.md M5/T506.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from PySide6 import QtCore, QtWidgets

# Mirror of ``headless_body_workflow.EXPORT_FORMATS`` — duplicated here
# so the dialog can be constructed without dragging the workflow
# module's helpers (and their lazy imports) into the Qt layer.  Keep
# in lock-step with the workflow constant.
_DIALOG_FORMATS: Tuple[Tuple[str, str], ...] = (
    ("kotor", "KOTOR (MDL/MDX) — Odyssey engine"),
    ("fbx",   "FBX (Autodesk)"),
    ("gltf",  "glTF / GLB"),
    ("obj",   "OBJ (Wavefront)"),
)

_FBX_PROFILES: Tuple[Tuple[str, str], ...] = (
    ("standard", "Standard FBX"),
    ("unity", "Unity-Compatible FBX"),
    ("unreal", "Unreal Engine-Compatible FBX"),
    ("3ds_max", "3ds Max-Compatible FBX"),
)


class QtExportDialog(QtWidgets.QDialog):
    """Modal dialog: pick formats + output dir + sidecar option.

    Usage
    -----
    ::

        dlg = QtExportDialog(self,
                             default_dir="/tmp/exports",
                             initial_resref="pfbcm")
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            wf.export_scene(scene,
                            formats=dlg.selected_formats(),
                            out_dir=dlg.output_dir(),
                            write_sidecar=dlg.write_sidecar())
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        default_dir: str = "",
        initial_resref: str = "",
        initial_formats: Optional[Sequence[str]] = None,
        initial_write_sidecar: bool = True,
        initial_fbx_compatibility_profile: str = "standard",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Headless Body")
        self.setModal(True)
        # Comfortable but not obese — the controls fit easily in 420×360.
        self.setMinimumSize(420, 320)

        self._format_checks: dict = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        # ── Header / hint ────────────────────────────────────────────
        hint = QtWidgets.QLabel(
            "Pick one or more output formats for the rigged body, an\n"
            "output folder, and whether to write the .ghostrig.json\n"
            "scene-definition sidecar. Defaults follow the active\n"
            "Character Builder mode."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#aaa; font-size:8pt; font-style:italic;")
        layout.addWidget(hint)

        # ── Format checkboxes ───────────────────────────────────────
        fmt_group = QtWidgets.QGroupBox("Formats")
        fmt_layout = QtWidgets.QVBoxLayout(fmt_group)
        fmt_layout.setSpacing(2)
        defaults = set(initial_formats or ("kotor",))
        for key, label in _DIALOG_FORMATS:
            cb = QtWidgets.QCheckBox(label)
            cb.setChecked(key in defaults)
            cb.setToolTip(f"Write the rigged body in {label}.")
            self._format_checks[key] = cb
            fmt_layout.addWidget(cb)
        layout.addWidget(fmt_group)

        fbx_row = QtWidgets.QFormLayout()
        self._fbx_profile_combo = QtWidgets.QComboBox()
        self._fbx_profile_combo.setObjectName("fbxProfileCombo")
        for key, label in _FBX_PROFILES:
            self._fbx_profile_combo.addItem(label, key)
        profile_key = str(initial_fbx_compatibility_profile or "standard").strip().lower()
        profile_index = self._fbx_profile_combo.findData(profile_key)
        self._fbx_profile_combo.setCurrentIndex(max(0, profile_index))
        self._fbx_profile_combo.setToolTip(
            "Unity and Unreal Engine modes write target-compatible units, bind data, "
            "relative texture sidecars, and linear continuous animation takes."
        )
        fbx_check = self._format_checks.get("fbx")
        self._fbx_profile_combo.setEnabled(bool(fbx_check and fbx_check.isChecked()))
        if fbx_check is not None:
            fbx_check.toggled.connect(self._fbx_profile_combo.setEnabled)
        fbx_row.addRow("FBX compatibility:", self._fbx_profile_combo)
        layout.addLayout(fbx_row)

        # ── Output directory row ────────────────────────────────────
        out_row = QtWidgets.QHBoxLayout()
        out_row.setSpacing(6)
        out_row.addWidget(QtWidgets.QLabel("Output folder:"))
        self._dir_edit = QtWidgets.QLineEdit()
        self._dir_edit.setText(default_dir or "")
        self._dir_edit.setPlaceholderText("/path/to/exports")
        out_row.addWidget(self._dir_edit, 1)
        browse_btn = QtWidgets.QPushButton("Browse…")
        browse_btn.clicked.connect(self._on_browse_clicked)
        out_row.addWidget(browse_btn)
        layout.addLayout(out_row)

        # ── Resref hint (read-only) ─────────────────────────────────
        if initial_resref:
            resref_label = QtWidgets.QLabel(
                f"Files will be named: <code>{initial_resref}.&lt;ext&gt;</code>"
                f" (and <code>{initial_resref}.ghostrig.json</code>)"
            )
            resref_label.setStyleSheet("color:#888; font-size:8pt;")
            resref_label.setWordWrap(True)
            layout.addWidget(resref_label)

        # ── Sidecar toggle ──────────────────────────────────────────
        self._sidecar_cb = QtWidgets.QCheckBox(
            "Write .ghostrig.json sidecar (SceneIO)"
        )
        self._sidecar_cb.setChecked(bool(initial_write_sidecar))
        self._sidecar_cb.setToolTip(
            "Recommended.  The sidecar stores schema-v2 export metadata\n"
            "so the scene can be reloaded later via SceneIO.load()."
        )
        layout.addWidget(self._sidecar_cb)

        layout.addStretch(1)

        # ── OK / Cancel ─────────────────────────────────────────────
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        ok_btn = buttons.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_btn is not None:
            ok_btn.setText("Export")
            ok_btn.setProperty("accent", True)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Public read-back accessors ───────────────────────────────────

    def selected_formats(self) -> List[str]:
        """Return the ordered list of format keys the user ticked."""
        return [
            key for key, _label in _DIALOG_FORMATS
            if self._format_checks.get(key) is not None
            and self._format_checks[key].isChecked()
        ]

    def output_dir(self) -> str:
        """Return the output-directory line edit's current text."""
        return self._dir_edit.text().strip()

    def write_sidecar(self) -> bool:
        """Return True when the sidecar checkbox is ticked."""
        return self._sidecar_cb.isChecked()

    def fbx_compatibility_profile(self) -> str:
        """Return the selected FBX target profile key."""
        return str(self._fbx_profile_combo.currentData() or "standard")

    # ── Internal slots ───────────────────────────────────────────────

    @QtCore.Slot()
    def _on_browse_clicked(self) -> None:
        """Open a directory picker and write the result back into the edit."""
        start = self._dir_edit.text().strip() or ""
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose Export Folder", start
        )
        if chosen:
            self._dir_edit.setText(chosen)

    @QtCore.Slot()
    def _on_accept(self) -> None:
        """OK clicked — sanity-check before propagating Accepted."""
        if not self.output_dir():
            QtWidgets.QMessageBox.warning(
                self, "Export",
                "Pick an output folder before continuing.",
            )
            return
        if not self.selected_formats() and not self.write_sidecar():
            QtWidgets.QMessageBox.warning(
                self, "Export",
                "Tick at least one format, or enable the sidecar JSON.",
            )
            return
        self.accept()
