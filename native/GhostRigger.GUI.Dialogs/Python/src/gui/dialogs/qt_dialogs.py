"""Small Qt dialogs used by the migrated GhostRigger shell."""

from __future__ import annotations

import platform
import sys
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src.core.rendering.viewport_navigation import VIEWPORT_NAVIGATION_HELP


class QtAboutDialog(QtWidgets.QDialog):
    """Theme-aware About dialog for the main GhostRigger shell."""

    COMPANY_CREDITS = (
        ("BioWare", "Original Knights of the Old Republic developer.", "https://www.bioware.com/"),
        ("Obsidian", "Knights of the Old Republic II developer.", "https://www.obsidian.net/"),
        ("LucasArts", "Original Star Wars games publisher; linked via Lucasfilm Games.", "https://www.lucasfilm.com/what-we-do/games/"),
    )
    DEVELOPER_CREDITS = (
        (
            "LordVaderCW",
            "Qt shell direction, Default-derived themes, docking and layout work, WGPU/D3D renderer stages, viewport HUD and interaction fixes, KMAX scene/module tooling, lighting/lightmap systems, Sequence Editor, and content-browser/UI workflows.",
        ),
        (
            "CrispyW0nton / ShaolinGhost",
            "Original GhostRigger line, roadmap and architecture work, retargeting/export/validation/project foundations, Character Builder pipeline, KOTOR resource and MDL pipeline fixes, MCP/test harnesses, and module/resource tooling.",
        ),
        (
            "genspark-ai-developer[bot]",
            "Automated support commit recorded in local git history.",
        ),
    )
    TOOL_CREDITS = (
        ("PyKotor / OpenKotOR", "KOTOR resource, MDL, TPC, ERF, BIF, and GFF ecosystem support."),
        ("MDLOps", "Historical Odyssey MDL compile/decompile reference and workflow bridge."),
        ("Blender", "External DCC and FBX/glTF inspection/export workflow support."),
        ("Autodesk FBX SDK", "Optional external FBX import/export backend."),
        ("KotorBlender / KOTORMax", "Community workflow references for KOTOR model and animation editing."),
    )
    LIBRARY_CREDITS = (
        "PySide6 / Qt",
        "WGPU, rendercanvas, glfw",
        "ModernGL, PyOpenGL",
        "Pillow, NumPy, imageio, OpenCV headless",
        "PyKotor",
        "trimesh, pygltflib, xatlas, embreex",
        "qtawesome, superqt, pyqtgraph, qtpy, darkdetect, qasync",
        "Flask, requests, MCP, pydantic, uvicorn",
        "watchdog, platformdirs, py-cpuinfo, PyInstaller",
    )

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("AboutGhostRiggerDialog")
        self.setWindowTitle("About GhostRigger")
        self.setModal(True)
        self.setMinimumSize(980, 700)
        self.resize(1040, 760)
        self.setSizeGripEnabled(False)
        self._company_buttons: list[QtWidgets.QPushButton] = []

        version = str(getattr(parent, "APP_VERSION", "") or "6.1.0")
        app_title = str(getattr(parent, "APP_TITLE", "") or "GhostRigger-K1-K2")
        title = app_title.split("//", 1)[0].strip() or "GhostRigger"
        subtitle = "Odyssey Engine Pipeline  //  KotOR 1 & 2 TSL"
        renderer = self._renderer_status(parent)
        theme = self._theme_status(parent)
        app_root = str(getattr(parent, "app_root", "") or "")
        ipc = "GhostRigger IPC: port 7001"

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)

        icon_label = QtWidgets.QLabel()
        icon_label.setObjectName("AboutLogo")
        icon_label.setFixedSize(42, 42)
        icon = self._window_icon(parent)
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(42, 42))
        else:
            icon_label.setText("GR")
            icon_label.setAlignment(QtCore.Qt.AlignCenter)
        header.addWidget(icon_label, 0, QtCore.Qt.AlignTop)

        title_stack = QtWidgets.QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(3)
        title_label = QtWidgets.QLabel(title.upper())
        title_label.setObjectName("AboutTitle")
        subtitle_label = QtWidgets.QLabel(subtitle)
        subtitle_label.setObjectName("AboutSubtitle")
        version_label = QtWidgets.QLabel(f"Version {version}")
        version_label.setObjectName("AboutVersionValue")
        title_stack.addWidget(title_label)
        title_stack.addWidget(subtitle_label)
        title_stack.addWidget(version_label)
        header.addLayout(title_stack, 1)
        root.addLayout(header)

        content_scroll = QtWidgets.QScrollArea()
        content_scroll.setObjectName("AboutScrollArea")
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_scroll.setWidget(content)
        root.addWidget(content_scroll, 1)

        details = QtWidgets.QFrame()
        details.setObjectName("AboutDetailsPanel")
        details_layout = QtWidgets.QGridLayout(details)
        details_layout.setContentsMargins(14, 12, 14, 12)
        details_layout.setHorizontalSpacing(16)
        details_layout.setVerticalSpacing(7)
        rows = [
            ("Renderer", renderer, "AboutRendererValue"),
            ("Theme", theme, "AboutThemeValue"),
            ("Qt", QtCore.qVersion(), "AboutQtValue"),
            ("Python", f"{platform.python_version()} ({platform.architecture()[0]})", "AboutPythonValue"),
            ("IPC", ipc, "AboutIpcValue"),
        ]
        if app_root:
            rows.append(("Workspace", app_root, "AboutWorkspaceValue"))
        for row, (label, value, object_name) in enumerate(rows):
            label_widget = QtWidgets.QLabel(label)
            label_widget.setObjectName("AboutDetailsLabel")
            value_widget = QtWidgets.QLabel(value)
            value_widget.setObjectName(object_name)
            value_widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            value_widget.setWordWrap(True)
            details_layout.addWidget(label_widget, row, 0, QtCore.Qt.AlignTop)
            details_layout.addWidget(value_widget, row, 1)
        details_layout.setColumnStretch(1, 1)
        content_layout.addWidget(details)

        content_layout.addWidget(self._build_company_credits())
        content_layout.addWidget(self._build_developer_credits())
        content_layout.addWidget(self._build_tools_credits())
        content_layout.addWidget(self._build_library_credits())

        notice = QtWidgets.QLabel(
            "Fan-made modding tool for Odyssey Engine assets. Not affiliated with BioWare, "
            "Obsidian, Lucasfilm, or Disney."
        )
        notice.setObjectName("AboutNotice")
        notice.setWordWrap(True)
        content_layout.addWidget(notice)
        content_layout.addStretch(1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.setObjectName("AboutButtons")
        copy_button = buttons.addButton("Copy Details", QtWidgets.QDialogButtonBox.ActionRole)
        copy_button.setObjectName("AboutCopyDetailsButton")
        copy_button.clicked.connect(self.copy_details)
        buttons.rejected.connect(self.reject)
        buttons.button(QtWidgets.QDialogButtonBox.Close).clicked.connect(self.accept)
        root.addWidget(buttons)

        self._details_text = "\n".join(
            [
                title,
                subtitle,
                f"Version: {version}",
                f"Renderer: {renderer}",
                f"Theme: {theme}",
                f"Qt: {QtCore.qVersion()}",
                f"Python: {sys.version.split()[0]}",
                ipc,
                f"Workspace: {app_root}" if app_root else "",
                "",
                "Developers:",
                *[f"- {name}: {text}" for name, text in self.DEVELOPER_CREDITS],
                "",
                "Tools:",
                *[f"- {name}: {text}" for name, text in self.TOOL_CREDITS],
                "",
                "Libraries:",
                *[f"- {name}" for name in self.LIBRARY_CREDITS],
            ]
        ).strip()

    def copy_details(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._details_text)

    def apply_ghost_theme(self, theme) -> None:
        self.setStyleSheet(
            f"""
            QDialog#AboutGhostRiggerDialog {{
                background: {theme.color('window.background')};
                color: {theme.color('text.primary')};
            }}
            QLabel#AboutTitle {{
                color: {theme.color('accent.primary')};
                font-size: 18pt;
                font-weight: 700;
            }}
            QLabel#AboutSubtitle, QLabel#AboutNotice {{
                color: {theme.color('text.secondary')};
            }}
            QLabel#AboutVersionValue {{
                color: {theme.color('text.primary')};
                font-weight: 600;
            }}
            QFrame#AboutDetailsPanel {{
                background: {theme.color('panel.background')};
                border: 1px solid {theme.color('panel.border')};
                border-radius: {theme.metric('border.radius')}px;
            }}
            QLabel#AboutDetailsLabel {{
                color: {theme.color('text.secondary')};
                font-weight: 600;
            }}
            QLabel#AboutLogo {{
                background: {theme.color('panel.background')};
                border: 1px solid {theme.color('panel.border')};
                border-radius: {theme.metric('border.radius')}px;
                color: {theme.color('accent.primary')};
                font-weight: 700;
            }}
            QFrame#AboutCreditPanel {{
                background: {theme.color('panel.background')};
                border: 1px solid {theme.color('panel.border')};
                border-radius: {theme.metric('border.radius')}px;
            }}
            QLabel#AboutSectionTitle {{
                color: {theme.color('accent.primary')};
                font-size: 11pt;
                font-weight: 700;
            }}
            QLabel#AboutCreditName {{
                color: {theme.color('text.primary')};
                font-weight: 700;
            }}
            QLabel#AboutCreditText {{
                color: {theme.color('text.secondary')};
            }}
            QPushButton#AboutCompanyBioWareButton,
            QPushButton#AboutCompanyObsidianButton,
            QPushButton#AboutCompanyLucasArtsButton {{
                background: {theme.color('window.background')};
                color: {theme.color('text.primary')};
                border: 1px solid {theme.color('panel.border')};
                border-radius: {theme.metric('border.radius')}px;
                padding: 10px 16px;
                min-height: 68px;
                font-weight: 700;
                font-size: 12pt;
            }}
            QPushButton#AboutCompanyBioWareButton:hover,
            QPushButton#AboutCompanyObsidianButton:hover,
            QPushButton#AboutCompanyLucasArtsButton:hover {{
                border-color: {theme.color('accent.primary')};
                color: {theme.color('accent.primary')};
            }}
            """
        )

    def _build_company_credits(self) -> QtWidgets.QFrame:
        panel, layout = self._credit_panel("Original Game Credits")
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        for name, description, url in self.COMPANY_CREDITS:
            button = QtWidgets.QPushButton(name)
            button.setObjectName(f"AboutCompany{name.replace(' ', '')}Button")
            button.setProperty("aboutCompanyButton", True)
            button.setProperty("creditUrl", url)
            button.setToolTip(description)
            button.setMinimumHeight(68)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, target=url: self._open_credit_url(target))
            self._company_buttons.append(button)
            row.addWidget(button)
        layout.addLayout(row)
        note = QtWidgets.QLabel(
            "These credits acknowledge the studios and publisher history behind the KOTOR games. "
            "Logo placeholders open the respective official pages."
        )
        note.setObjectName("AboutCreditText")
        note.setWordWrap(True)
        layout.addWidget(note)
        return panel

    def _build_developer_credits(self) -> QtWidgets.QFrame:
        panel, layout = self._credit_panel("GhostRigger Developers")
        for name, description in self.DEVELOPER_CREDITS:
            layout.addLayout(self._credit_row(name, description))
        return panel

    def _build_tools_credits(self) -> QtWidgets.QFrame:
        panel, layout = self._credit_panel("Tools And Community References")
        for name, description in self.TOOL_CREDITS:
            layout.addLayout(self._credit_row(name, description))
        return panel

    def _build_library_credits(self) -> QtWidgets.QFrame:
        panel, layout = self._credit_panel("Python And Runtime Libraries")
        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        for index, name in enumerate(self.LIBRARY_CREDITS):
            label = QtWidgets.QLabel(name)
            label.setObjectName("AboutCreditText")
            label.setWordWrap(True)
            grid.addWidget(label, index // 2, index % 2)
        layout.addLayout(grid)
        return panel

    def _credit_panel(self, title: str) -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
        panel = QtWidgets.QFrame()
        panel.setObjectName("AboutCreditPanel")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(9)
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("AboutSectionTitle")
        layout.addWidget(title_label)
        return panel, layout

    def _credit_row(self, name: str, text: str) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        name_label = QtWidgets.QLabel(name)
        name_label.setObjectName("AboutCreditName")
        name_label.setMinimumWidth(170)
        name_label.setWordWrap(True)
        text_label = QtWidgets.QLabel(text)
        text_label.setObjectName("AboutCreditText")
        text_label.setWordWrap(True)
        row.addWidget(name_label, 0, QtCore.Qt.AlignTop)
        row.addWidget(text_label, 1)
        return row

    def _open_credit_url(self, url: str) -> None:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    @staticmethod
    def _window_icon(parent: Optional[QtWidgets.QWidget]) -> QtGui.QIcon:
        icon = QtGui.QIcon()
        if parent is not None:
            icon_provider = getattr(parent, "_icon", None)
            if callable(icon_provider):
                icon = icon_provider("logo", 42)
            if icon.isNull():
                icon = parent.windowIcon()
        return icon

    @staticmethod
    def _renderer_status(parent: Optional[QtWidgets.QWidget]) -> str:
        viewport = getattr(parent, "viewport", None)
        if viewport is not None and hasattr(viewport, "render_state_status_text"):
            try:
                return str(viewport.render_state_status_text())
            except Exception:
                pass
        return "Renderer: unavailable"

    @staticmethod
    def _theme_status(parent: Optional[QtWidgets.QWidget]) -> str:
        manager = getattr(parent, "theme_manager", None)
        if manager is not None and hasattr(manager, "get_theme"):
            try:
                theme = manager.get_theme()
                return f"{theme.name} ({theme.id})"
            except Exception:
                pass
        return "Default"


def show_about(parent: Optional[QtWidgets.QWidget] = None) -> None:
    dialog = QtAboutDialog(parent)
    manager = getattr(parent, "theme_manager", None)
    if manager is not None and hasattr(manager, "get_theme"):
        try:
            dialog.apply_ghost_theme(manager.get_theme())
        except Exception:
            pass
    dialog.exec()



def show_format_reference(parent: Optional[QtWidgets.QWidget] = None) -> None:
    QtWidgets.QMessageBox.information(
        parent,
        "KotOR MDL Format Reference",
        "The full MDL/MDX format reference will be migrated into a Qt document viewer.",
    )


def show_viewport_navigation_reference(parent: Optional[QtWidgets.QWidget] = None) -> None:
    QtWidgets.QMessageBox.information(
        parent,
        "Viewport Navigation Controls",
        VIEWPORT_NAVIGATION_HELP,
    )


def show_ipc_info(parent: Optional[QtWidgets.QWidget] = None) -> None:
    QtWidgets.QMessageBox.information(
        parent,
        "IPC Protocol Info",
        "GhostRigger IPC runs on port 7001. It accepts MDL loads, UTC/UTP/UTD blueprint opens, viewport refreshes, panel and workbench open requests, renderer/helper controls, viewport captures, and module mesh selection for visible QA.",
    )

