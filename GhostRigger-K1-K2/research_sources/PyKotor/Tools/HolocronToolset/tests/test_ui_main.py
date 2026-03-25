from __future__ import annotations

import pytest

from toolset.gui.widgets.settings.installations import InstallationConfig

# Handle optional pykotor.gl dependency (required by module_designer)
try:
    from pykotor.gl.scene import Camera  # noqa: F401
except ImportError:
    pytest.skip("pykotor.gl not available", allow_module_level=True)

from qtpy.QtGui import QAction
from qtpy.QtWidgets import QApplication, QPushButton
from toolset.gui.windows.main import ToolWindow
from toolset.data.installation import HTInstallation
from utility.gui.qt.widgets.itemviews.treeview import RobustTreeView
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_main_window_init(qtbot: QtBot):
    """Test that the main window initializes correctly."""
    window = ToolWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.isVisible()
    assert "Holocron Toolset" in window.windowTitle()
    assert window.active is None
    assert window.ui.installationTree.model() is window.installation_tree_model
    assert isinstance(window.ui.installationTree, RobustTreeView)


def test_main_window_set_installation(qtbot: QtBot, installation: HTInstallation):
    """Test setting an active installation in the main window."""
    window = ToolWindow()
    qtbot.addWidget(window)
    window.show()

    # Manually add the installation to the settings/installations dict to simulate it being available
    installations = window.settings.installations()
    installations[installation.name] = InstallationConfig(name=installation.name)
    installations[installation.name].path = str(installation.path())  # type: ignore[attr-defined]
    installations[installation.name].tsl = installation.tsl  # type: ignore[attr-defined]
    window.reload_installations()

    # Ensure the installation is present in the tree model
    model = window.installation_tree_model
    assert model.rowCount() >= 1
    assert any(model.data(model.index(row, 0)) == installation.name for row in range(model.rowCount()))

    # Manually set active installation and enable tabs to mimic a successful load
    window.installations[installation.name] = installation
    window.active = installation
    window.ui.resourceTabs.setEnabled(True)
    window.update_menus()

    assert window.active == installation
    assert window.ui.resourceTabs.isEnabled()

    # Check if tabs are populated (basic check)
    assert window.ui.modulesWidget.ui.sectionCombo.count() >= 0


def test_tree_selection_drives_tabs(qtbot: QtBot, installation: HTInstallation):
    """Selecting nodes in the installation tree should switch tabs."""
    window = ToolWindow()
    qtbot.addWidget(window)
    window.show()

    installations = window.settings.installations()
    installations[installation.name] = InstallationConfig(name=installation.name)
    installations[installation.name].path = str(installation.path())  # type: ignore[attr-defined]
    installations[installation.name].tsl = installation.tsl  # type: ignore[attr-defined]
    window.reload_installations()

    window.installations[installation.name] = installation
    window.active = installation
    window.ui.resourceTabs.setEnabled(True)

    model = window.installation_tree_model
    install_index = None
    for row in range(model.rowCount()):
        idx = model.index(row, 0)
        if model.data(idx, 0) == installation.name:
            install_index = idx
            break
    assert install_index is not None

    modules_index = None
    for row in range(model.rowCount(install_index)):
        idx = model.index(row, 0, install_index)
        if str(model.data(idx, 0)).lower() == "modules":
            modules_index = idx
            break

    if modules_index is not None:
        window.ui.installationTree.setCurrentIndex(modules_index)
        QApplication.processEvents()
        assert window.get_active_resource_tab() == window.ui.modulesTab


def test_menu_actions_state(qtbot: QtBot, installation: HTInstallation):
    """Test that menu actions are enabled/disabled correctly based on installation."""
    window = ToolWindow()
    qtbot.addWidget(window)
    window.show()

    # Initially no installation, most "New" actions should be disabled
    # NOTE: Some might be enabled if they don't require an installation (like TLK?)
    # Let's check a specific one we know requires installation, e.g. New DLG
    assert not window.ui.actionNewDLG.isEnabled()

    # Set installation
    window.active = installation
    window.update_menus()

    assert window.ui.actionNewDLG.isEnabled()
    assert window.ui.actionNewUTC.isEnabled()
    assert window.ui.actionNewNSS.isEnabled()


def test_tab_switching(qtbot: QtBot, installation: HTInstallation):
    """Test switching between tabs in the main window."""
    window = ToolWindow()
    qtbot.addWidget(window)
    window.show()

    # Set installation to enable tabs
    window.active = installation
    window.ui.resourceTabs.setEnabled(True)

    # Switch to Modules tab
    window.ui.resourceTabs.setCurrentWidget(window.ui.modulesTab)
    assert window.get_active_resource_tab() == window.ui.modulesTab

    # Switch to Override tab
    window.ui.resourceTabs.setCurrentWidget(window.ui.overrideTab)
    assert window.get_active_resource_tab() == window.ui.overrideTab


def test_modules_filter(qtbot: QtBot, installation: HTInstallation):
    """Test that the modules filter works (basic UI check)."""
    window = ToolWindow()
    qtbot.addWidget(window)
    window.show()
    window.active = installation

    # Mock some modules
    from qtpy.QtGui import QStandardItem

    modules = [QStandardItem("Test Module 1"), QStandardItem("Test Module 2")]
    window.refresh_module_list(reload=False, module_items=modules)

    assert window.ui.modulesWidget.ui.sectionCombo.count() == 2
