"""Focused contracts for the standalone GUI Editor and PIE preview seam."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets

from src.core.rendering.kotor_gui_preview import (
    PIE_HUD_PREVIEW_SCHEMA,
    KotorGuiPreviewSnapshot,
    compile_kotor_gui_preview,
    decode_kotor_gui_texture,
)
from src.core.tools.kotor_gui_document import GUI_CONTROL_TYPES, KotorGuiDocument
from src.gui.windows.application_core.shared.gui_editor_workflow import (
    GuiEditorWorkflowMixin,
    KOTOR_GUI_RESOURCE_TYPE,
)
from src.gui.qt_lib.windows.qt_gui_editor_window import QtGuiEditorWindow
from src.io.kotor_gui_io import load_kotor_gui_document, write_kotor_gui_document


ROOT = Path(__file__).resolve().parents[1]


def _gui_fixture_bytes() -> bytes:
    from pykotor.resource.generics.gui import (
        GUI,
        GUIBorder,
        GUIButton,
        GUIControlType,
        GUIPanel,
        GUIText,
        bytes_gui,
    )
    from pykotor.common.misc import ResRef
    from utility.common.geometry import Vector2

    gui = GUI()
    root = GUIPanel()
    root.tag = "TGuiPanel"
    root.position = Vector2(0, 0)
    root.size = Vector2(640, 480)
    button = GUIButton()
    button.gui_type = GUIControlType.Button
    button.id = 7
    button.tag = "BTN_ATTACK"
    button.position = Vector2(40, 410)
    button.size = Vector2(64, 40)
    border = GUIBorder()
    border.fill = ResRef("uibit_fill_2bt")
    border.edge = ResRef("uibit_brdr_16bet")
    button.border = border
    gui_text = GUIText()
    gui_text.text = "Attack"
    gui_text.font = ResRef("dialogfont16x16")
    button.gui_text = gui_text
    root.children.append(button)
    gui.root = root
    return bytes_gui(gui)


def test_retail_gui_compiles_to_immutable_json_safe_pie_contract() -> None:
    from pykotor.resource.generics.gui import read_gui

    snapshot = compile_kotor_gui_preview(
        read_gui(_gui_fixture_bytes()),
        game="k2",
        resref="maininterface_p",
    )

    assert isinstance(snapshot, KotorGuiPreviewSnapshot)
    assert snapshot.game == "K2"
    assert snapshot.source_width == 640
    assert snapshot.source_height == 480
    assert len(snapshot.controls) == 2
    button = snapshot.controls[1]
    assert button.parent_key == snapshot.root_keys[0]
    assert button.tag == "BTN_ATTACK"
    assert (button.left, button.top, button.width, button.height) == (40.0, 410.0, 64.0, 40.0)
    assert button.texture_resrefs == ("uibit_brdr_16bet", "uibit_fill_2bt")
    assert button.text is not None and button.text.value == "Attack"

    payload = snapshot.to_pie_payload()
    assert payload["schema"] == PIE_HUD_PREVIEW_SCHEMA
    assert payload["source"] == {
        "kind": "retail_gui",
        "game": "K2",
        "resref": "maininterface_p",
        "canvas": [640, 480],
    }
    assert len(str(payload["revision"])) == 64
    json.dumps(payload)


def test_gui_editor_window_is_separate_themed_shell_and_publishes_snapshot() -> None:
    from pykotor.resource.generics.gui import read_gui

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGuiEditorWindow()
    window.set_retail_gui_catalog(("dialog_p", "maininterface_p", "container_p"))
    assert window.windowTitle() == "GhostStudio — GUI Editor (Odyssey UI)"
    assert window.objectName() == "guiEditorWindow"
    assert window.findChild(QtWidgets.QListWidget, "guiEditorCatalogList") is window.catalog_list
    assert window.findChild(QtWidgets.QWidget, "guiEditorPreviewCanvas") is window.preview_canvas
    assert window.findChild(QtWidgets.QPushButton, "guiEditorPublishPIEButton") is window.publish_pie_button
    assert window.selected_resref() == "maininterface_p"
    assert not window.publish_pie_button.isEnabled()

    snapshot = compile_kotor_gui_preview(
        read_gui(_gui_fixture_bytes()),
        game="K2",
        resref="maininterface_p",
    )
    published: list[object] = []
    window.piePreviewRequested.connect(published.append)
    window.set_preview_snapshot(snapshot)
    assert window.control_tree.topLevelItemCount() == 1
    assert window.publish_pie_button.isEnabled()
    window.publish_preview_to_pie()
    app.processEvents()
    assert published == [snapshot]
    window.close()


class _FakeInstall:
    def list_resrefs(self, resource_type: int) -> list[str]:
        assert resource_type == KOTOR_GUI_RESOURCE_TYPE
        return ["pause_p", "maininterface_p", "dialog_p"]


class _FakeResourceManager:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.requests: list[tuple[str, int, str]] = []

    def get_k2(self) -> _FakeInstall:
        return _FakeInstall()

    def get_strict(self, resref: str, resource_type: int, game: str) -> bytes:
        self.requests.append((resref, resource_type, game))
        return self.raw


class _WorkflowHost(GuiEditorWorkflowMixin):
    def __init__(self) -> None:
        self._resource_manager = _FakeResourceManager(_gui_fixture_bytes())
        self.module_editor_window = None
        self.logs: list[tuple[str, str]] = []

    def _log(self, message: str, level: str) -> None:
        self.logs.append((message, level))


def test_workflow_loads_strict_retail_gui_and_exposes_editor_free_pie_payload() -> None:
    host = _WorkflowHost()
    assert host._populate_gui_editor_catalog("K2") == ("dialog_p", "maininterface_p", "pause_p")
    snapshot = host._load_gui_editor_retail_resource("K2", "maininterface_p")
    assert snapshot is not None
    assert host._resource_manager.requests == [("maininterface_p", 2047, "K2")]
    host._publish_gui_editor_preview_to_pie(snapshot)
    payload = host.current_pie_hud_preview_payload()
    assert payload is not None
    assert payload["schema"] == PIE_HUD_PREVIEW_SCHEMA
    assert payload["source"]["resref"] == "maininterface_p"


def test_main_shell_registers_a_distinct_gui_editor_action_and_icon() -> None:
    chrome = (
        ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py"
    ).read_text(encoding="utf-8")
    main_window = (
        ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_main_window.py"
    ).read_text(encoding="utf-8")
    editor = (ROOT / "src/gui/windows/qt_gui_editor_window.py").read_text(encoding="utf-8")
    contract = (ROOT / "src/core/rendering/kotor_gui_preview.py").read_text(encoding="utf-8")

    assert '"gui_editor": "gui_editor"' in chrome
    assert 'self.gui_editor_action.triggered.connect(self._open_gui_editor_window)' in chrome
    assert 'gui_editor_button.setObjectName("CommandStripGuiEditorButton")' in chrome
    assert "GuiEditorWorkflowMixin" in main_window
    assert '"gui_editor": self._open_gui_editor_window' in main_window
    assert "map_studio" not in editor.casefold()
    assert "PySide6" not in contract
    assert "src.gui" not in contract
    assert (ROOT / "src/gui/icons/gui_editor.svg").is_file()


def test_editable_document_preserves_unknown_gff_fields_and_validates_known_fields() -> None:
    from pykotor.resource.formats.gff import bytes_gff, read_gff

    gff = read_gff(_gui_fixture_bytes())
    controls = gff.root.acquire("CONTROLS", None)
    controls[0].set_int32("COMMUNITY_FIELD", 7331)
    document = KotorGuiDocument.from_bytes(
        bytes_gff(gff),
        game="K2",
        resref="maininterface_p",
    )
    assert not document.dirty

    button_path = (0, 0)
    document.set_field(button_path, "tag", "BTN_CUSTOM")
    document.set_extent(button_path, 48, 400, 96, 44)
    assert document.dirty
    assert document.field_value(button_path, "tag") == "BTN_CUSTOM"
    assert document.field_value(button_path, "width") == 96

    reopened_gff = read_gff(document.to_bytes())
    reopened_button = reopened_gff.root.acquire("CONTROLS", None)[0]
    assert reopened_button.get_int32("COMMUNITY_FIELD") == 7331
    assert reopened_button.get_string("TAG") == "BTN_CUSTOM"

    try:
        document.set_field(button_path, "border.fill", "this_resref_is_far_too_long")
    except ValueError as exc:
        assert "16 characters" in str(exc)
    else:  # pragma: no cover - validation contract
        raise AssertionError("Invalid texture resref was accepted")


def test_document_add_delete_undo_and_roundtrip_all_known_control_types() -> None:
    document = KotorGuiDocument.new(game="K1", resref="customhud")
    assert document.to_bytes().startswith(b"GUI V3.2")
    added = [document.add_control((0,), control_type) for control_type, _label in GUI_CONTROL_TYPES]
    assert [document.control_type(path) for path in added] == [value for value, _label in GUI_CONTROL_TYPES]
    list_box = added[-1]
    fields = {spec.key for spec in document.field_specs(list_box)}
    assert {"list.padding", "list.thumb.image", "border.fill", "text.alignment"} <= fields
    document.set_field(list_box, "list.padding", 9)
    document.set_field(list_box, "list.thumb.image", "uibit_slthumb")
    progress = added[-2]
    document.set_field(progress, "progress.fill", "uibit_progress")
    progress_preview = document.preview_snapshot().control(document.key_for_path(progress))
    assert progress_preview is not None and progress_preview.progress is not None
    assert "uibit_progress" in progress_preview.texture_resrefs
    list_preview = document.preview_snapshot().control(document.key_for_path(list_box))
    assert list_preview is not None and "uibit_slthumb" in list_preview.texture_resrefs

    parent = document.delete_control(list_box)
    assert parent == (0,)
    assert len(document.preview_snapshot().controls) == len(GUI_CONTROL_TYPES)
    assert document.undo()
    assert len(document.preview_snapshot().controls) == len(GUI_CONTROL_TYPES) + 1
    assert document.redo()
    assert document.undo()

    reopened = KotorGuiDocument.from_bytes(document.to_bytes(), game="K1", resref="customhud")
    assert len(reopened.preview_snapshot().controls) == len(GUI_CONTROL_TYPES) + 1
    assert reopened.field_value(list_box, "list.padding") == 9
    assert reopened.field_value(list_box, "list.thumb.image") == "uibit_slthumb"
    assert not [issue for issue in reopened.validation_issues() if issue.severity == "error"]


def test_safe_gui_io_creates_backup_and_marks_document_clean(tmp_path: Path) -> None:
    target = tmp_path / "customhud.gui"
    document = KotorGuiDocument.new(game="K2", resref="customhud")
    document.add_control((0,), 6)
    first = write_kotor_gui_document(document, target)
    assert first.path == target
    assert first.backup_path is None
    assert not document.dirty
    first_bytes = target.read_bytes()

    document.set_field((0, 0), "tag", "BTN_CHANGED")
    second = write_kotor_gui_document(document, target)
    assert second.backup_path == target.with_suffix(".gui.bak")
    assert second.backup_path.read_bytes() == first_bytes
    assert load_kotor_gui_document(target, game="K2").field_value((0, 0), "tag") == "BTN_CHANGED"


def test_nested_controls_resolve_to_absolute_preview_extents() -> None:
    from pykotor.resource.generics.gui import GUI, GUIButton, GUIPanel
    from utility.common.geometry import Vector2

    root = GUIPanel()
    root.tag = "ROOT"
    root.position = Vector2(0, 0)
    root.size = Vector2(640, 480)
    panel = GUIPanel()
    panel.tag = "PANEL"
    panel.position = Vector2(100, 80)
    panel.size = Vector2(300, 200)
    button = GUIButton()
    button.tag = "BUTTON"
    button.position = Vector2(20, 30)
    button.size = Vector2(90, 40)
    panel.children.append(button)
    root.children.append(panel)
    gui = GUI()
    gui.root = root

    snapshot = compile_kotor_gui_preview(gui, game="K2", resref="nested")
    assert snapshot.absolute_extent("control:0.0.0") == (120.0, 110.0, 90.0, 40.0)


def test_renderer_neutral_tpc_decode_returns_rgba_pixels() -> None:
    from io import BytesIO

    from PIL import Image
    from pykotor.resource.formats.tpc import TPC, TPCTextureFormat, bytes_tpc

    texture = TPC.from_blank()
    texture.set_single(
        bytes(
            (
                255,
                0,
                0,
                255,
                0,
                255,
                0,
                255,
                0,
                0,
                255,
                255,
                255,
                255,
                255,
                255,
            )
        ),
        TPCTextureFormat.RGBA,
        2,
        2,
    )
    decoded = decode_kotor_gui_texture(bytes_tpc(texture), max_size=8)
    assert (decoded.width, decoded.height) == (2, 2)
    assert len(decoded.rgba) == 16

    tga = BytesIO()
    Image.new("RGBA", (4, 2), (12, 34, 56, 255)).save(tga, format="TGA")
    decoded_tga = decode_kotor_gui_texture(tga.getvalue(), max_size=8)
    assert (decoded_tga.width, decoded_tga.height) == (4, 2)
    assert decoded_tga.rgba[:4] == bytes((12, 34, 56, 255))


def test_gui_editor_window_enables_typed_authoring_for_editable_documents() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGuiEditorWindow()
    document = KotorGuiDocument.new(game="K2", resref="customhud")
    assert window.set_document(document)
    window.add_control(6)
    app.processEvents()

    assert len(window.active_preview_snapshot().controls) == 2
    assert window.add_control_button.isEnabled()
    assert window.save_action.isEnabled()
    assert window.undo_action.isEnabled()
    assert window.findChild(QtWidgets.QLineEdit, "guiEditorField_tag") is not None

    window.undo()
    assert len(window.active_preview_snapshot().controls) == 1
    window._document = None
    window.close()
