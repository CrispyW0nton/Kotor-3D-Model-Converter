from __future__ import annotations

import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]


def _tutorial_module():
    pytest.importorskip("PySide6")
    from src.gui.qt_lib.dialogs import qt_getting_started_window

    return qt_getting_started_window


def test_tutorial_catalog_covers_every_primary_ghoststudio_pillar() -> None:
    module = _tutorial_module()
    expected = {
        "start",
        "resources",
        "scene",
        "modeling",
        "placeable_builder",
        "map_studio",
        "terrain",
        "texture_paint",
        "module_editor",
        "particle_editor",
        "scripting",
        "gui_editor",
        "head_builder",
        "character",
        "retarget",
        "game_proof",
    }

    pages = module.TUTORIAL_PAGES
    assert {page.key for page in pages} == expected
    assert len({page.route for page in pages}) == len(pages)
    for number, page in enumerate(pages, start=1):
        assert page.title.startswith(f"{number}. ")
        assert len(page.steps) >= 4
        assert page.where.strip()
        assert page.before_you_start.strip()
        assert page.goal.strip()
        assert page.outputs.strip()
        assert page.readiness.strip()
        assert page.route_label.startswith("Open ")


def test_tutorial_window_navigates_and_emits_real_workspace_route() -> None:
    module = _tutorial_module()
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = module.QtGettingStartedWindow()
    captured: list[str] = []
    window.openRequested.connect(captured.append)

    window.select_page("retarget")
    row = next(
        index
        for index in range(window.page_list.count())
        if window.page_list.item(index).data(module.QtCore.Qt.UserRole) == "retarget"
    )
    assert window.page_list.currentRow() == row
    assert window.open_button.text() == "Open Retarget Workbench"
    assert window.where_label.text().startswith("Tools → Animation Retargeting")
    assert window.before_label.text()
    assert window.back_button.text().startswith("Previous:")
    assert window.next_button.text().startswith("Next:")
    assert window.page_list.accessibleName() == "GhostStudio first-time task tutorials"
    assert window.close_button.text() == "Close Tutorial"
    window._open_current_page()
    app.processEvents()

    assert captured == ["retarget"]
    window.close()


def test_tutorial_window_smokes_every_packaged_theme_and_every_page() -> None:
    module = _tutorial_module()
    from PySide6 import QtWidgets
    from src.gui.libtheme.theme_loader import ThemeLoader

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = module.QtGettingStartedWindow()
    for path in sorted((ROOT / "config/themes/themes").glob("*.xml")):
        theme = ThemeLoader().load_file(path)
        assert theme is not None
        if theme.is_native():
            window.apply_native_theme()
        else:
            window.apply_ghost_theme(theme)
        for page in module.TUTORIAL_PAGES:
            window.select_page(page.key)
            app.processEvents()
            assert window.page_title.text() == page.title
            assert window.where_label.text() == page.where
            assert window.before_label.text() == page.before_you_start
            assert window.open_button.isEnabled()
    window.close()


def test_new_settings_profile_opens_tutorial_once_and_f1_keeps_it_discoverable() -> None:
    main_source = (
        ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/qt_main_window.py"
    ).read_text(encoding="utf-8")
    lifecycle_source = (
        ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_lifecycle.py"
    ).read_text(encoding="utf-8")
    chrome_source = (
        ROOT
        / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/window_chrome.py"
    ).read_text(encoding="utf-8")

    assert 'self.settings_data.setdefault("getting_started_seen", False)' in main_source
    assert "self._maybe_show_getting_started_on_first_launch" in main_source
    assert 'self.settings_data["getting_started_seen"] = True' in lifecycle_source
    assert 'self.getting_started_action.setShortcut("F1")' in chrome_source
    assert "help_menu.addAction(self.getting_started_action)" in chrome_source
    for route, opener in {
        '"settings"': "_open_settings_dialog",
        '"particle_editor"': "_open_particle_editor_window",
        '"scripting"': "_open_scripting_dialogue_studio_window",
        '"gui_editor"': "_open_gui_editor_window",
    }.items():
        assert route in lifecycle_source
        assert opener in lifecycle_source
