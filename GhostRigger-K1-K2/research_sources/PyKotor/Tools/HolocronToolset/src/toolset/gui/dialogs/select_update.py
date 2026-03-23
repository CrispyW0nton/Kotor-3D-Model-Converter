"""Update selection dialog: check for updates, pick release, and run installer."""

from __future__ import annotations

import gc
import multiprocessing
import os
import pathlib
import platform
import sys

from contextlib import suppress
from multiprocessing import Queue
from typing import TYPE_CHECKING, Any, NoReturn

import markdown

# Handle optional requests dependency
try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment, unused-ignore]

from qtpy.QtCore import QThread, Qt
from qtpy.QtGui import QColor, QFont, QPalette
from qtpy.QtWidgets import QApplication, QDialog, QMessageBox, QStyle

from loggerplus import RobustLogger
from toolset.config import LOCAL_PROGRAM_INFO, is_remote_version_newer, toolset_tag_to_version, version_to_toolset_tag
from toolset.gui.common.localization import translate as tr
from toolset.gui.dialogs.asyncloader import ProgressDialog
from utility.misc import ProcessorArchitecture
from utility.system.app_process.shutdown import terminate_child_processes
from utility.updater.github import GithubRelease
from utility.updater.update import AppUpdate

if TYPE_CHECKING:
    from qtpy.QtGui import QIcon

    from utility.updater.github import Asset


if __name__ == "__main__":
    with suppress(Exception):

        def update_sys_path(path: pathlib.Path):
            working_dir = str(path)
            if working_dir not in sys.path:
                sys.path.append(working_dir)

        file_absolute_path = pathlib.Path(__file__).resolve()

        pykotor_path = file_absolute_path.parents[6] / "Libraries" / "PyKotor" / "src" / "pykotor"
        if pykotor_path.exists():
            update_sys_path(pykotor_path.parent)
        pykotor_gl_path = file_absolute_path.parents[6] / "Libraries" / "PyKotorGL" / "src" / "pykotor"
        if pykotor_gl_path.exists():
            update_sys_path(pykotor_gl_path.parent)
        utility_path = file_absolute_path.parents[6] / "Libraries" / "Utility" / "src"
        if utility_path.exists():
            update_sys_path(utility_path)
        toolset_path = file_absolute_path.parents[3] / "toolset"
        if toolset_path.exists():
            update_sys_path(toolset_path.parent)
            if __name__ == "__main__":
                os.chdir(toolset_path)


def convert_markdown_to_html(md_text: str, widget: QWidget | None = None) -> str:
    """Convert Markdown text to HTML with theme-aware styling.

    Args:
        md_text: Markdown text to convert
        widget: Optional widget to get palette from (defaults to QApplication)

    Returns:
        HTML string with embedded CSS styles using palette colors
    """
    from toolset.gui.common.palette_helpers import wrap_html_with_palette_styles

    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "codehilite"])
    return wrap_html_with_palette_styles(html_body, widget)


def run_progress_dialog(
    progress_queue: Queue,
    title: str = "Operation Progress",
) -> NoReturn:
    """Call this with multiprocessing.Process."""
    app = QApplication(sys.argv)
    dialog = ProgressDialog(progress_queue, title)
    app_style: QStyle | None = app.style()
    if app_style is not None:
        icon: QIcon | None = app_style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        if icon is not None:
            dialog.setWindowIcon(icon)
    dialog.show()
    sys.exit(app.exec())


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog  # pyright: ignore[reportAttributeAccessIssue]
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinMaxButtonsHint & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.remote_info: dict[str, Any] = {}
        self.releases: list[GithubRelease] = []
        self.forks_cache: dict[str, list[GithubRelease]] = {}
        from toolset.gui.common.localization import translate as tr

        self.init_ui()
        self.setWindowTitle(tr("Update Application"))
        self.init_config()

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def include_prerelease(self) -> bool:
        return self.ui.preReleaseCheckbox.isChecked()

    def set_prerelease(self, value):
        return self.ui.preReleaseCheckbox.setChecked(value)

    def init_ui(self):
        from toolset.uic.qtpy.dialogs.select_update import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # Connect signals
        self.ui.preReleaseCheckbox.stateChanged.connect(self.on_pre_release_changed)
        self.ui.fetchReleasesButton.clicked.connect(self.init_config)
        self.ui.forkComboBox.currentIndexChanged.connect(self.on_fork_changed)
        self.ui.releaseComboBox.currentIndexChanged.connect(self.on_release_changed)
        self.ui.installSelectedButton.clicked.connect(self.on_install_selected)
        self.ui.updateLatestButton.clicked.connect(self.on_update_latest_clicked)

        # Populate the releaseComboBox with releases (if any exist)
        for release in self.releases:
            self.ui.releaseComboBox.addItem(release.tag_name, release)
            if release.tag_name == version_to_toolset_tag(LOCAL_PROGRAM_INFO["currentVersion"]):
                index = self.ui.releaseComboBox.count() - 1
                self.ui.releaseComboBox.setItemData(index, QFont("Arial", 10, QFont.Weight.Bold), Qt.ItemDataRole.FontRole)

        # Update current version display
        self._update_current_version_display()

    def init_config(self):
        self.set_prerelease(False)
        self.fetch_and_cache_forks_with_releases()
        self.forks_cache["th3w1zard1/PyKotor"] = self.fetch_fork_releases("th3w1zard1/PyKotor", include_all=True)
        self.populate_fork_combo_box()
        self.on_fork_changed(self.ui.forkComboBox.currentIndex())

    def fetch_and_cache_forks_with_releases(self):
        self.forks_cache.clear()
        forks_url = "https://api.github.com/repos/th3w1zard1/PyKotor/forks"
        if requests is None:
            RobustLogger().warning("requests library not available, cannot fetch forks")
            return
        try:
            forks_response: requests.Response = requests.get(forks_url, timeout=15)
            forks_response.raise_for_status()
            forks_json: list[dict[str, Any]] = forks_response.json()
            for fork in forks_json:
                fork_owner_login: str = fork["owner"]["login"]
                fork_full_name: str = f"{fork_owner_login}/{fork['name']}"
                self.forks_cache[fork_full_name] = self.fetch_fork_releases(fork_full_name, include_all=True)
        except requests.HTTPError as e:
            RobustLogger().exception(f"Failed to fetch forks: {e}")

    def fetch_fork_releases(
        self,
        fork_full_name: str,
        *,
        include_all: bool = False,
    ) -> list[GithubRelease]:
        url = f"https://api.github.com/repos/{fork_full_name}/releases"
        if requests is None:
            RobustLogger().warning("requests library not available, cannot fetch fork releases")
            return []
        try:
            response: requests.Response = requests.get(url, timeout=15)
            response.raise_for_status()
            releases_json: list[dict[str, Any]] = response.json()
            if include_all:
                return [GithubRelease.from_json(r) for r in releases_json]
            return [GithubRelease.from_json(r) for r in releases_json if not r["draft"] and (self.include_prerelease() or not r["prerelease"])]
        except requests.HTTPError as e:
            RobustLogger().exception(f"Failed to fetch releases for {fork_full_name}: {e}")
            return []

    def populate_fork_combo_box(self):
        self.ui.forkComboBox.clear()
        self.ui.forkComboBox.addItem("th3w1zard1/PyKotor")
        for fork in self.forks_cache:
            self.ui.forkComboBox.addItem(fork)

    def on_pre_release_changed(
        self,
        state: bool,  # noqa: FBT001
    ):
        self.filter_releases_based_on_prerelease()

    def filter_releases_based_on_prerelease(self):
        selected_fork = self.ui.forkComboBox.currentText()
        if selected_fork in self.forks_cache:
            self.releases = [
                release
                for release in self.forks_cache[selected_fork]
                if not release.draft and "toolset" in release.tag_name.lower() and (self.include_prerelease() or not release.prerelease)
            ]
        else:
            self.releases = []

        if not self.include_prerelease() and not self.releases:  # Don't show empty release comboboxes.
            print("No releases found, attempt to try again with prereleases")
            self.set_prerelease(True)
            return
        self.releases.sort(key=lambda x: bool(is_remote_version_newer("0.0.0", x.tag_name)))

        # Update Combo Box
        self.ui.releaseComboBox.clear()
        self.ui.changeLogEdit.clear()
        for release in self.releases:
            self.ui.releaseComboBox.addItem(release.tag_name, release)
        self.on_release_changed(self.ui.releaseComboBox.currentIndex())
        self._update_current_version_display()

    def on_fork_changed(
        self,
        index: int,  # noqa: FBT001
    ):
        if index < 0:
            return
        self.filter_releases_based_on_prerelease()

    def get_selected_tag(self) -> str:
        release: GithubRelease = self.ui.releaseComboBox.itemData(self.ui.releaseComboBox.currentIndex())
        return release.tag_name if release else ""

    def on_release_changed(
        self,
        index: int,  # noqa: FBT001
    ):
        if index < 0 or index >= len(self.releases):
            return
        release: GithubRelease = self.ui.releaseComboBox.itemData(index)
        if not release:
            return
        changelog_html: str = convert_markdown_to_html(release.body, self)
        self.ui.changeLogEdit.setHtml(changelog_html)
        self._update_current_version_display()

    def _update_current_version_display(self):
        """Update the current version label with color coding."""
        # Get semantic colors from palette
        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            palette = QPalette()
        else:
            palette = app.palette()

        link_color = palette.color(QPalette.ColorRole.Link)
        mid_color = palette.color(QPalette.ColorRole.Mid)

        # Warning color (for outdated): Use mid color with adjustment
        warning_color = QColor(mid_color)
        if warning_color.lightness() < 128:  # Dark theme
            warning_color = warning_color.lighter(130)
        else:  # Light theme
            warning_color = warning_color.darker(120)

        # Success color (for up-to-date): Use link color
        success_color = link_color

        current_version = LOCAL_PROGRAM_INFO["currentVersion"]
        try:
            selected_tag = self.get_selected_tag()
            version_color: str = warning_color.name() if is_remote_version_newer(current_version, toolset_tag_to_version(selected_tag)) else success_color.name()
        except Exception:
            version_color = success_color.name()
        version_text = f"<span style='font-size:16px; font-weight:bold; color:{version_color};'>{current_version}</span>"
        self.ui.currentVersionLabel.setText(f"Holocron Toolset Current Version: {version_text}")

    def get_latest_release(self) -> GithubRelease | None:
        if self.releases:
            return self.releases[0]
        self.set_prerelease(True)
        return self.releases[0] if self.releases else None

    def on_update_latest_clicked(self):
        latest_release: GithubRelease | None = self.get_latest_release()
        if not latest_release:
            print("No toolset releases found?")
            return
        self.start_update(latest_release)

    def on_install_selected(self):
        release = self.ui.releaseComboBox.currentData()
        if not release:
            from toolset.gui.common.localization import translate as tr

            QMessageBox(QMessageBox.Icon.Information, tr("Select a release"), tr("No release selected, select one first.")).exec()
            return
        self.start_update(release)

    def start_update(
        self,
        release: GithubRelease,
    ):
        # sourcery skip: remove-unreachable-code
        os_name: str = platform.system().lower()
        proc_arch: str = ProcessorArchitecture.from_os().get_machine_repr()
        asset: Asset | None = next((a for a in release.assets if proc_arch in a.name.lower() and os_name in a.name.lower()), None)

        if asset:
            download_url: str = asset.browser_download_url
            links: list[str] = [download_url]
        else:
            # TODO(th3w1zard1): compile from src.
            # Realistically wouldn't be that hard, just run ./install_powershell.ps1 and ./compile/compile_toolset.ps1 and run the exe.
            # The difficult part would be finishing LibUpdate, currently only AppUpdate is working.
            return
            result = QMessageBox(  # noqa: F841
                QMessageBox.Icon.Question,
                tr("No asset found for this release."),
                tr("There are no binaries available for download for release '{tag}'.", tag=release.tag_name),  # Would you like to compile this release from source instead?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                None,
                flags=Qt.WindowType.Window | Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint,
            ).exec()

        progress_queue = Queue()
        progress_process = multiprocessing.Process(
            target=run_progress_dialog,
            args=(
                progress_queue,
                "Holocron Toolset is updating and will restart shortly...",
            ),
        )
        progress_process.start()
        self.hide()

        def download_progress_hook(
            data: dict[str, Any],
            progress_queue: Queue = progress_queue,
        ):
            # get_root_logger().debug("progress data: %s", data)
            progress_queue.put(data)

        def exitapp(kill_self_here: bool):  # noqa: FBT001
            packaged_data = {"action": "shutdown", "data": {}}
            progress_queue.put(packaged_data)
            ProgressDialog.monitor_and_terminate(progress_process)
            gc.collect()
            for obj in gc.get_objects():
                if isinstance(obj, QThread) and obj.isRunning():
                    RobustLogger().debug(f"Terminating QThread: {obj}")
                    obj.terminate()
                    obj.wait()
            terminate_child_processes()
            if kill_self_here:
                sys.exit(0)

        def expected_archive_filenames() -> list[str]:
            return [asset.name]

        updater = AppUpdate(
            links,
            "HolocronToolset",
            LOCAL_PROGRAM_INFO["currentVersion"],
            toolset_tag_to_version(release.tag_name),
            downloader=None,
            progress_hooks=[download_progress_hook],
            exithook=exitapp,
            version_to_tag_parser=version_to_toolset_tag,
        )
        updater.get_archive_names = expected_archive_filenames

        try:
            progress_queue.put({"action": "update_status", "text": "Downloading update..."})
            updater.download(background=False)
            progress_queue.put({"action": "update_status", "text": "Restarting and Applying update..."})
            updater.extract_restart()
            progress_queue.put({"action": "update_status", "text": "Cleaning up..."})
            updater.cleanup()
        except Exception:  # noqa: BLE001
            RobustLogger().exception("Error occurred while downloading/installing the toolset.")
        finally:
            exitapp(kill_self_here=True)
