"""Autodesk FBX SDK setup assistant dialog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets
from src.io.fbx.fbx_sdk_paths import (
    FBX_DOWNLOAD_URL,
    likely_sdk_files,
    normalize_fbx_sdk_settings,
    test_fbx_sdk_configuration,
)
from src.io.fbx.fbx_sdk_setup import LICENCE_NOTICE, compatibility_guidance, save_successful_configuration


class FbxSdkSetupDialog(QtWidgets.QDialog):
    configurationSaved = QtCore.Signal(dict)

    def __init__(self, settings_data: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.settings_data = settings_data if settings_data is not None else {}
        self.fbx_settings = normalize_fbx_sdk_settings(self.settings_data.get("fbx_sdk") or {})
        self.setWindowTitle("FBX SDK Setup Assistant")
        self.resize(820, 640)
        self._build_ui()
        self._load_fields()
        self._refresh_status()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        notice = QtWidgets.QLabel(LICENCE_NOTICE)
        notice.setWordWrap(True)
        notice.setObjectName("FbxSdkLicenceNotice")
        root.addWidget(notice)

        self.status_text = QtWidgets.QPlainTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMinimumHeight(160)
        root.addWidget(self.status_text, 1)

        form_group = QtWidgets.QGroupBox("Local SDK Paths")
        form = QtWidgets.QGridLayout(form_group)
        self.sdk_root_edit = QtWidgets.QLineEdit()
        self.bindings_edit = QtWidgets.QLineEdit()
        self.fbxcommon_edit = QtWidgets.QLineEdit()
        self.library_edit = QtWidgets.QLineEdit()
        rows = [
            ("SDK root", self.sdk_root_edit, self._browse_sdk_root),
            ("Python bindings folder", self.bindings_edit, self._browse_bindings),
            ("FbxCommon.py folder", self.fbxcommon_edit, self._browse_fbxcommon),
            ("SDK library/bin folder", self.library_edit, self._browse_library),
        ]
        for row, (label, edit, callback) in enumerate(rows):
            form.addWidget(QtWidgets.QLabel(label), row, 0)
            form.addWidget(edit, row, 1)
            browse = QtWidgets.QPushButton("Browse")
            browse.clicked.connect(callback)
            form.addWidget(browse, row, 2)
        root.addWidget(form_group)

        self.result_text = QtWidgets.QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(120)
        root.addWidget(self.result_text)

        buttons = QtWidgets.QHBoxLayout()
        self.open_download_button = QtWidgets.QPushButton("Open Autodesk FBX SDK Download Page")
        self.open_download_button.clicked.connect(self._open_download_page)
        self.scan_button = QtWidgets.QPushButton("Scan Root")
        self.scan_button.clicked.connect(self._scan_root)
        self.test_button = QtWidgets.QPushButton("Test Selected Path")
        self.test_button.clicked.connect(self._test_configuration)
        self.save_button = QtWidgets.QPushButton("Save Configuration")
        self.save_button.clicked.connect(self._save_configuration)
        self.clear_button = QtWidgets.QPushButton("Clear Configuration")
        self.clear_button.clicked.connect(self._clear_configuration)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)
        for button in (
            self.open_download_button,
            self.scan_button,
            self.test_button,
            self.save_button,
            self.clear_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    def _load_fields(self) -> None:
        self.sdk_root_edit.setText(str(self.fbx_settings.get("sdk_root") or ""))
        self.bindings_edit.setText(str(self.fbx_settings.get("python_bindings_path") or ""))
        self.fbxcommon_edit.setText(str(self.fbx_settings.get("fbxcommon_path") or ""))
        self.library_edit.setText(";".join(str(item) for item in self.fbx_settings.get("library_paths") or []))

    def _collect_settings(self) -> dict[str, Any]:
        data = normalize_fbx_sdk_settings(self.fbx_settings)
        data.update(
            {
                "sdk_root": self.sdk_root_edit.text().strip(),
                "python_bindings_path": self.bindings_edit.text().strip(),
                "fbxcommon_path": self.fbxcommon_edit.text().strip(),
                "library_paths": [item.strip() for item in self.library_edit.text().split(";") if item.strip()],
            }
        )
        return data

    def _refresh_status(self) -> None:
        self.status_text.setPlainText(compatibility_guidance(self._collect_settings()))

    def _browse_sdk_root(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Autodesk FBX SDK Root", self.sdk_root_edit.text())
        if path:
            self.sdk_root_edit.setText(path)
            self._scan_root()

    def _browse_bindings(self) -> None:
        start = self.bindings_edit.text() or self.sdk_root_edit.text()
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select fbx Python Binding",
            start,
            "FBX Python binding (fbx.pyd fbx.so fbx.dylib);;All files (*.*)",
        )
        if file_path:
            self.bindings_edit.setText(str(Path(file_path).parent))

    def _browse_fbxcommon(self) -> None:
        start = self.fbxcommon_edit.text() or self.sdk_root_edit.text()
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select FbxCommon.py",
            start,
            "FbxCommon.py (FbxCommon.py);;Python files (*.py);;All files (*.*)",
        )
        if file_path:
            self.fbxcommon_edit.setText(str(Path(file_path).parent))

    def _browse_library(self) -> None:
        start = self.library_edit.text().split(";", 1)[0] or self.sdk_root_edit.text()
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Autodesk FBX SDK Library/Bin Folder", start)
        if path:
            self.library_edit.setText(path)

    def _scan_root(self) -> None:
        root = self.sdk_root_edit.text().strip()
        if not root:
            return
        found = likely_sdk_files(root)
        if found["bindings"] and not self.bindings_edit.text().strip():
            self.bindings_edit.setText(str(Path(found["bindings"][0]).parent))
        if found["fbxcommon"] and not self.fbxcommon_edit.text().strip():
            self.fbxcommon_edit.setText(str(Path(found["fbxcommon"][0]).parent))
        if found["libraries"] and not self.library_edit.text().strip():
            library_dirs = []
            for path in found["libraries"]:
                parent = str(Path(path).parent)
                if parent not in library_dirs:
                    library_dirs.append(parent)
            self.library_edit.setText(";".join(library_dirs[:3]))
        self.result_text.setPlainText(
            "\n".join(
                [
                    f"Found binding files: {len(found['bindings'])}",
                    f"Found FbxCommon.py files: {len(found['fbxcommon'])}",
                    f"Found likely SDK libraries: {len(found['libraries'])}",
                    "",
                    "First matches:",
                    *(found["bindings"][:3] + found["fbxcommon"][:3] + found["libraries"][:3]),
                ]
            )
        )
        self._refresh_status()

    def _test_configuration(self):
        data = self._collect_settings()
        result = test_fbx_sdk_configuration(data)
        lines = [
            f"Success: {result.success}",
            f"fbx import: {result.fbx_import_ok}",
            f"FbxCommon import: {result.fbxcommon_import_ok}",
            f"SDK manager create: {result.manager_create_ok}",
            f"Empty scene create: {result.scene_create_ok}",
            f"SDK version: {result.detected_sdk_version or 'unknown'}",
        ]
        if result.tested_paths:
            lines.extend(["Tested paths:", *(f"- {path}" for path in result.tested_paths)])
        if result.error_message:
            lines.append(f"Error: {result.error_message}")
        if result.recommended_fix:
            lines.append(f"Recommended fix: {result.recommended_fix}")
        if result.traceback_text:
            lines.extend(["", "Details:", result.traceback_text])
        self.result_text.setPlainText("\n".join(lines))
        return result

    def _save_configuration(self) -> None:
        data = self._collect_settings()
        result = self._test_configuration()
        saved = save_successful_configuration(data, result)
        saved["enabled"] = bool(result.success)
        self.settings_data["fbx_sdk"] = saved
        self.fbx_settings = saved
        self.configurationSaved.emit(saved)
        self._refresh_status()
        title = "FBX SDK Setup"
        if result.success:
            QtWidgets.QMessageBox.information(self, title, "FBX SDK configuration verified and saved.")
        else:
            QtWidgets.QMessageBox.warning(self, title, "Configuration saved, but FBX SDK verification failed. FBX import/export remains disabled.")

    def _clear_configuration(self) -> None:
        self.fbx_settings = normalize_fbx_sdk_settings({})
        self.settings_data["fbx_sdk"] = self.fbx_settings
        self._load_fields()
        self.result_text.setPlainText("FBX SDK configuration cleared.")
        self.configurationSaved.emit(self.fbx_settings)
        self._refresh_status()

    def _open_download_page(self) -> None:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(FBX_DOWNLOAD_URL))
