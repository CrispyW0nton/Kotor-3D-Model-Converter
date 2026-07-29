from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_wcag_contrast_math_and_packaged_theme_pairs() -> None:
    from src.gui.libtheme.accessibility_audit import (
        audit_theme_contrast,
        contrast_ratio,
    )
    from src.gui.libtheme.theme_loader import ThemeLoader

    assert contrast_ratio("#000000", "#FFFFFF") == 21.0
    assert round(contrast_ratio("#777777", "#FFFFFF"), 2) == 4.48

    themes = ThemeLoader().load_dir(ROOT / "config" / "themes" / "themes")
    assert themes
    for theme in themes.values():
        assert audit_theme_contrast(theme) == (), theme.id
        assert not [
            warning
            for warning in theme.warnings
            if warning.startswith("Accessibility contrast:")
        ], theme.id


def test_accessibility_auditor_catches_icon_names_targets_and_focus() -> None:
    app = _qt_app()

    from PySide6 import QtCore, QtWidgets
    from src.gui.libtheme.accessibility_audit import AccessibilityAuditor

    root = QtWidgets.QWidget()
    root.setWindowTitle("Audit fixture")
    layout = QtWidgets.QVBoxLayout(root)
    button = QtWidgets.QPushButton(root)
    button.setIcon(root.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton))
    button.setFixedSize(20, 20)
    button.setFocusPolicy(QtCore.Qt.NoFocus)
    layout.addWidget(button)
    try:
        report = AccessibilityAuditor().audit_widget_tree(root)
        codes = {issue.code for issue in report.issues}
        assert {
            "control.missing_name",
            "control.missing_tooltip",
            "control.small_target",
            "control.not_keyboard_focusable",
        }.issubset(codes)

        button.setAccessibleName("Open scene")
        button.setAccessibleDescription("Choose a scene file to open")
        button.setToolTip("Open scene")
        button.setFixedSize(32, 32)
        button.setFocusPolicy(QtCore.Qt.StrongFocus)
        button.setProperty("ghostFrequentAction", True)
        app.processEvents()

        fixed_report = AccessibilityAuditor().audit_widget_tree(root)
        fixed_codes = {issue.code for issue in fixed_report.issues}
        assert "control.missing_name" not in fixed_codes
        assert "control.missing_tooltip" not in fixed_codes
        assert "control.small_target" not in fixed_codes
        assert "control.not_keyboard_focusable" not in fixed_codes
    finally:
        root.close()


def test_accessibility_auditor_reports_duplicate_active_shortcuts() -> None:
    _qt_app()

    from PySide6 import QtGui, QtWidgets
    from src.gui.libtheme.accessibility_audit import AccessibilityAuditor

    root = QtWidgets.QWidget()
    first = QtGui.QAction("First action", root)
    first.setShortcut("Ctrl+Alt+9")
    second = QtGui.QAction("Second action", root)
    second.setShortcut("Ctrl+Alt+9")
    try:
        report = AccessibilityAuditor().audit_widget_tree(root)
        duplicates = [
            issue for issue in report.issues if issue.code == "shortcut.duplicate"
        ]
        assert len(duplicates) == 1
        assert "First action" in duplicates[0].message
        assert "Second action" in duplicates[0].message
    finally:
        root.close()


def test_late_created_native_controls_inherit_minimum_targets() -> None:
    app = _qt_app()

    from PySide6 import QtWidgets
    from src.gui.libtheme.accessibility_audit import install_accessibility_defaults

    install_accessibility_defaults(app)
    root = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(root)
    button = QtWidgets.QPushButton("Continue", root)
    button.setFixedHeight(18)
    layout.addWidget(button)
    tree = QtWidgets.QTreeWidget(root)
    tree.setHeaderHidden(True)
    item = QtWidgets.QTreeWidgetItem(["Open Map Studio"])
    item.setIcon(0, root.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon))
    tree.addTopLevelItem(item)
    layout.addWidget(tree)
    try:
        root.show()
        app.processEvents()
        assert button.minimumHeight() >= 24
        assert button.maximumHeight() >= 24
        assert tree.iconSize().height() >= 24
        assert tree.visualItemRect(item).height() >= 24
    finally:
        root.close()


def test_window_size_clamps_to_logical_screen_at_high_dpi() -> None:
    from PySide6 import QtCore
    from src.gui.libtheme.layout_applier import (
        fit_window_geometry_to_available_screen,
        fit_window_size_to_available_screen,
    )

    fitted = fit_window_size_to_available_screen(
        QtCore.QSize(1650, 920),
        QtCore.QSize(853, 480),
        QtCore.QSize(640, 360),
    )
    assert fitted == QtCore.QSize(853, 480)

    smaller_request = fit_window_size_to_available_screen(
        QtCore.QSize(600, 300),
        QtCore.QSize(1280, 720),
        QtCore.QSize(640, 360),
    )
    assert smaller_request == QtCore.QSize(640, 360)

    centered_above_screen = fit_window_geometry_to_available_screen(
        QtCore.QRect(85, -15, 1196, 799),
        QtCore.QRect(0, 0, 1366, 1040),
    )
    assert centered_above_screen == QtCore.QRect(85, 0, 1196, 799)

    oversized = fit_window_geometry_to_available_screen(
        QtCore.QRect(-40, -20, 1700, 1200),
        QtCore.QRect(0, 0, 1366, 1040),
        margin=8,
    )
    assert oversized == QtCore.QRect(8, 8, 1350, 1024)


def test_theme_editor_dense_pages_scroll_instead_of_forcing_window_offscreen() -> None:
    app = _qt_app()

    from PySide6 import QtWidgets
    from src.gui.libtheme.layout_manager import LayoutManager
    from src.gui.libtheme.theme_editor_window import ThemeEditorWindow
    from src.gui.libtheme.theme_manager import ThemeManager

    editor = ThemeEditorWindow(
        ThemeManager(ROOT, {"theme_layout": {"selected_theme": "default"}}),
        LayoutManager(ROOT, {"theme_layout": {"selected_layout": "default"}}),
    )
    try:
        editor.resize(900, 600)
        editor.show()
        app.processEvents()
        assert editor.width() <= 900
        assert editor.height() <= 600
        responsive_scrolls = [
            scroll
            for scroll in editor.findChildren(QtWidgets.QScrollArea)
            if scroll.objectName().startswith("ThemeEditor")
        ]
        assert len(responsive_scrolls) == 8
        assert all(scroll.widgetResizable() for scroll in responsive_scrolls)
    finally:
        editor.close()


def test_packaged_layouts_meet_shared_target_size_contracts() -> None:
    from src.gui.libtheme.layout_loader import LayoutLoader

    layouts = LayoutLoader().load_dir(ROOT / "config" / "themes" / "layouts")
    assert layouts["compact"].main_width <= 1280
    assert layouts["compact"].main_height <= 720
    for layout in layouts.values():
        assert not layout.warnings, (layout.id, layout.warnings)
        assert layout.toolbar("main").height >= 24
        assert layout.toolbar("viewport").height >= 32
        assert layout.spacing_value("inputHeight") >= 24
        assert layout.spacing_value("comboHeight") >= 24
        assert layout.spacing_value("spinboxHeight") >= 24
        assert layout.spacing_value("tabHeight") >= 24
        assert layout.spacing_value("tableRowHeight") >= 24
        assert layout.spacing_value("treeRowHeight") >= 24
        assert layout.spacing_value("viewportToolbarHeight") >= 32
        assert layout.spacing_value("transformBarHeight") >= 32


def test_shared_viewport_frequent_controls_are_named_and_32_pixels() -> None:
    _qt_app()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    viewport = QtViewportWidget(compact_controls=True)
    try:
        frequent = [
            widget
            for widget in viewport.findChildren(QtWidgets.QWidget)
            if bool(widget.property("ghostFrequentAction"))
            and widget.isEnabled()
            and not widget.isHidden()
        ]
        assert frequent
        for widget in frequent:
            effective_width = max(widget.minimumWidth(), widget.sizeHint().width())
            effective_height = max(widget.minimumHeight(), widget.sizeHint().height())
            assert effective_width >= 32, (widget.objectName(), effective_width)
            assert effective_height >= 32, (widget.objectName(), effective_height)
            assert widget.accessibleName(), widget.objectName()
    finally:
        viewport.close()


def test_responsive_layout_keeps_profile_dock_groups_collapsed() -> None:
    app = _qt_app()

    from PySide6 import QtCore, QtWidgets
    from src.gui.libtheme.layout_applier import LayoutApplier
    from src.gui.libtheme.layout_loader import LayoutLoader

    layout = LayoutLoader().load_file(
        ROOT / "config" / "themes" / "layouts" / "profile_lighting.xml"
    )
    assert layout is not None
    window = QtWidgets.QMainWindow()
    window._ghost_responsive_compact = True  # type: ignore[attr-defined]
    window._detachable_panels = {}  # type: ignore[attr-defined]
    for key in ("scene", "lighting", "cameras", "properties"):
        dock = QtWidgets.QDockWidget(key, window)
        dock.setWidget(QtWidgets.QLabel(key))
        window.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)
        dock.show()
        window._detachable_panels[key] = dock  # type: ignore[attr-defined]
    try:
        LayoutApplier()._apply_panels(layout, window)
        app.processEvents()
        assert all(
            dock.isHidden()
            for dock in window._detachable_panels.values()  # type: ignore[attr-defined]
        )
    finally:
        window.close()
