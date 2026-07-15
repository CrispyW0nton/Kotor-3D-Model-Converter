from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCENE_PYTHON = ROOT / "native" / "GhostRigger.Core.Scene" / "Python"
TOOLS_PYTHON = ROOT / "native" / "GhostRigger.Core.Tools" / "Python"
DISPLAY_PYTHON = ROOT / "native" / "GhostRigger.Core.GUI.Display" / "Python"

for payload_root in (TOOLS_PYTHON, DISPLAY_PYTHON, SCENE_PYTHON):
    payload_path = str(payload_root)
    if payload_path not in sys.path:
        sys.path.insert(0, payload_path)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


EXPECTED_SHELF = (
    ("reset_transform", "Reset Transformations", "reset_transform"),
    ("center_pivot", "Center Pivot", "center_pivot"),
    ("zero_pivot", "Zero Pivot", "zero_pivot"),
    ("separate", "Separate", "separate"),
    ("combine", "Combine", "combine"),
    ("fill_hole", "Fill Hole", "fill_hole"),
    ("mirror", "Mirror", "mirror"),
    ("bevel", "Bevel", "bevel"),
    ("bridge", "Bridge", "bridge"),
    ("extrude", "Extrude", "extrude"),
    ("merge", "Merge", "merge_components"),
    ("multi_cut", "Multi-Cut", "multi_cut"),
    ("insert_edge_loop", "Insert Edge Loop", "insert_edge_loop"),
    ("target_weld", "Target Weld", "target_weld"),
    ("make_hole", "Make Hole", "make_hole"),
    ("lattice", "Lattice", "lattice"),
    ("wrap", "Wrap", "wrap"),
    ("shrink_wrap", "ShrinkWrap", "shrink_wrap"),
    ("reverse_normals", "Reverse", "reverse_normals"),
    ("soften_edges", "Soften Edge", "soften_edges"),
    ("harden_edges", "Harden Edge", "harden_edges"),
    ("connect_components", "Connect", "connect_components"),
    ("boolean_difference", "Difference A-B", "boolean_a_minus_b"),
    ("bend", "Bend", "bend_tool"),
    ("delete_history", "Delete History", "delete_history"),
    ("duplicate_special_options", "Duplicate Special Options", "duplicate_special_options"),
    ("freeze_transform", "Freeze Transformations", "freeze_transform"),
    ("select_triangles", "Select Triangle Faces", "select_triangles"),
    ("select_quads", "Select Quad Faces", "select_quads"),
    ("contained_faces", "Convert Selection to Contained Faces", "convert_contained_faces"),
    ("make_live", "Make Live", "make_live"),
    ("quad_draw", "Quad Draw", "quad_draw"),
)


def test_maya_modeling_shelf_registry_has_the_exact_user_authored_order() -> None:
    from src.core.modules.map_studio_modeling_shelf import map_studio_modeling_shelf_commands

    commands = map_studio_modeling_shelf_commands()

    assert len(commands) == 32
    assert tuple((command.key, command.label, command.action_key) for command in commands) == EXPECTED_SHELF
    assert len({command.key for command in commands}) == len(commands)
    assert len({command.action_key for command in commands}) == len(commands)
    assert all(command.description.strip() for command in commands)
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", command.icon_key) for command in commands)
    shortcuts = {command.key: command.shortcut for command in commands if command.shortcut}
    assert shortcuts == {
        "fill_hole": "Ctrl+/",
        "bevel": "Ctrl+B",
        "bridge": "Ctrl+/",
        "extrude": "Ctrl+E",
        "multi_cut": "Ctrl+X",
        "duplicate_special_options": "Ctrl+Shift+D",
        "quad_draw": "Ctrl+Q",
    }


def test_maya_modeling_shelf_payload_mirrors_are_byte_identical() -> None:
    scene_registry = SCENE_PYTHON / "src/core/modules/map_studio_modeling_shelf.py"
    tools_registry = TOOLS_PYTHON / "src/core/modules/map_studio_modeling_shelf.py"
    display_widget = DISPLAY_PYTHON / "src/gui/panels/module_editor/map_studio_modeling_shelf.py"
    tools_widget = TOOLS_PYTHON / "src/gui/panels/module_editor/map_studio_modeling_shelf.py"

    assert scene_registry.read_bytes() == tools_registry.read_bytes()
    assert display_widget.read_bytes() == tools_widget.read_bytes()


@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_maya_modeling_shelf_buttons_are_compact_icon_only_and_accessible(qt_app) -> None:
    from PySide6 import QtCore, QtWidgets
    from src.gui.panels.module_editor.map_studio_modeling_shelf import MapStudioModelingShelf

    shelf = MapStudioModelingShelf()
    shelf.show()
    qt_app.processEvents()

    assert shelf.height() == 34
    assert list(shelf.buttons) == [entry[0] for entry in EXPECTED_SHELF]
    assert len(shelf.buttons) == 32
    for key, label, _action_key in EXPECTED_SHELF:
        button = shelf.button(key)
        assert button is not None
        assert button.size() == QtCore.QSize(35, 34)
        assert button.toolButtonStyle() == QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
        assert button.accessibleName() == label
        assert button.accessibleDescription().strip()
        assert button.toolTip().startswith(label)
        assert not button.icon().isNull()
        icon_image = button.icon().pixmap(28, 28).toImage()
        assert not icon_image.isNull()
        assert any(
            icon_image.pixelColor(x, y).alpha() > 0
            for y in range(icon_image.height())
            for x in range(icon_image.width())
        )
        assert button.focusPolicy() == QtCore.Qt.FocusPolicy.StrongFocus
        assert button.cursor().shape() == QtCore.Qt.CursorShape.PointingHandCursor
        assert isinstance(button, QtWidgets.QToolButton)

    shelf.close()
    shelf.deleteLater()
    qt_app.processEvents()


def test_maya_modeling_shelf_emits_run_and_double_click_options_signals(qt_app) -> None:
    from PySide6 import QtCore, QtTest
    from src.gui.panels.module_editor.map_studio_modeling_shelf import MapStudioModelingShelf

    shelf = MapStudioModelingShelf()
    shelf.show()
    qt_app.processEvents()
    commands: list[str] = []
    options: list[str] = []
    shelf.commandRequested.connect(commands.append)
    shelf.optionsRequested.connect(options.append)

    bevel = shelf.button("bevel")
    assert bevel is not None
    QtTest.QTest.mouseClick(bevel, QtCore.Qt.MouseButton.LeftButton)
    QtTest.QTest.mouseDClick(bevel, QtCore.Qt.MouseButton.LeftButton)
    qt_app.processEvents()

    assert commands and commands[0] == "bevel"
    assert options == ["bevel"]

    shelf.close()
    shelf.deleteLater()
    qt_app.processEvents()


def test_maya_modeling_shelf_uses_only_clean_room_runtime_artwork() -> None:
    """Guard against accidentally packaging the Maya shelf's proprietary image files."""

    widget_source = (
        DISPLAY_PYTHON / "src/gui/panels/module_editor/map_studio_modeling_shelf.py"
    ).read_text(encoding="utf-8")
    proprietary_maya_images = {
        "menuIconModify.png",
        "polySeparate.png",
        "polyUnite.png",
        "polyCloseBorder.png",
        "polyMirrorGeometry.png",
        "polyBevel.png",
        "polyBridge.png",
        "polyExtrudeFacet.png",
        "polyMerge.png",
        "multiCut_NEX32.png",
        "polySplitEdgeRing.png",
        "weld_NEX32.png",
        "polyMergeFacet.png",
        "lattice.png",
        "wrap.png",
        "shrinkwrap.png",
        "polyNormal.png",
        "polySoftEdge.png",
        "polyHardEdge.png",
        "polyConnectComponents.png",
        "polyBooleansDifference.png",
        "bendNLD.png",
        "menuIconEdit.png",
        "commandButton.png",
        "makeLive.png",
        "quadDraw_NEX32.png",
    }

    casefolded_source = widget_source.casefold()
    assert all(name.casefold() not in casefolded_source for name in proprietary_maya_images)
    assert not re.search(r"QPixmap\s*\(\s*['\"]", widget_source)
    assert "QIcon.fromTheme" not in widget_source
    assert ".addFile(" not in widget_source
    assert "QImage(" not in widget_source
    assert "QPainter(pixmap)" in widget_source
