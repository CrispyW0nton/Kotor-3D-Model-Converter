"""Update dialog: show release notes, compare versions, and start the update process."""

from __future__ import annotations

import platform
from datetime import datetime

from typing import TYPE_CHECKING, Any

import markdown

from qtpy import QtCore
from qtpy.QtCore import QUrl
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication, QDialog, QMessageBox
from qtpy.QtGui import QDesktopServices

from loggerplus import RobustLogger
from toolset.config import LOCAL_PROGRAM_INFO, is_remote_version_newer, toolset_tag_to_version
from toolset.gui.dialogs.update_github import fetch_and_cache_forks, fetch_fork_releases, filter_releases
from toolset.gui.dialogs.update_process import start_update_process
from utility.misc import ProcessorArchitecture
from utility.updater.github import GithubRelease

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

    from utility.updater.github import Asset, GithubRelease


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


class UpdateDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Dialog  # pyright: ignore[reportArgumentType]
            | QtCore.Qt.WindowType.WindowCloseButtonHint  # pyright: ignore[reportArgumentType]
            | QtCore.Qt.WindowType.WindowMinMaxButtonsHint  # pyright: ignore[reportArgumentType]
            & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint  # pyright: ignore[reportArgumentType]
        )
        self.remoteInfo: dict[str, Any] = {}
        self.releases: list[GithubRelease] = []
        self.forks_cache: dict[str, list[GithubRelease]] = {}
        self.setFixedSize(800, 600)

        from toolset.uic.qtpy.dialogs.update_dialog import Ui_Dialog

        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.init_ui()
        self.init_config()

        # Setup event filter to prevent scroll wheel interaction with controls
        from toolset.gui.common.filters import NoScrollEventFilter

        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(parent_widget=self)

    def include_prerelease(self) -> bool:
        return self.ui.preReleaseCheckBox.isChecked()

    def set_prerelease(self, value: bool) -> None:  # noqa: FBT001
        return self.ui.preReleaseCheckBox.setChecked(value)

    def init_ui(self):
        # Connect signals
        self.ui.preReleaseCheckBox.stateChanged.connect(self.on_pre_release_changed)
        self.ui.refreshButton.clicked.connect(self.init_config)
        self.ui.forkComboBox.currentIndexChanged.connect(self.on_fork_changed)
        self.ui.releaseComboBox.currentIndexChanged.connect(self.on_release_changed)
        self.ui.ignoreButton.clicked.connect(self.reject)
        self.ui.checkoutButton.clicked.connect(self.on_checkout_clicked)
        self.ui.installButton.clicked.connect(self.on_install_selected)

        # Changelog: transparent background and no border so it blends with the dialog
        self.ui.changelogEdit.setStyleSheet("background: transparent; border: none;")

        # Title label shows rich text (version number colored via palette)
        self.ui.titleLabel.setTextFormat(QtCore.Qt.RichText)

        # Update current version label (will be updated after releases are loaded)
        self.update_version_label()

    def init_config(self):
        self.set_prerelease(False)
        self.forks_cache = fetch_and_cache_forks()
        self.forks_cache["th3w1zard1/PyKotor"] = fetch_fork_releases("th3w1zard1/PyKotor", include_all=True)
        self.populate_fork_combo_box()
        self.on_fork_changed(self.ui.forkComboBox.currentIndex())

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
        selected_fork: str = self.ui.forkComboBox.currentText()
        if selected_fork in self.forks_cache:
            self.releases = filter_releases(self.forks_cache[selected_fork], include_prerelease=self.include_prerelease())
        else:
            self.releases = []

        if not self.include_prerelease() and not self.releases:
            RobustLogger().info("No releases found, attempt to try again with prereleases")
            self.set_prerelease(True)
            return
        self.releases.sort(key=lambda x: bool(is_remote_version_newer("0.0.0", x.tag_name)))

        # Update Combo Box
        self.ui.releaseComboBox.clear()
        self.ui.changelogEdit.clear()
        for release in self.releases:
            self.ui.releaseComboBox.addItem(release.tag_name, release)
        self.on_release_changed(self.ui.releaseComboBox.currentIndex())

    def on_fork_changed(
        self,
        index: int,  # noqa: FBT001
    ):
        if index < 0:
            return
        self.filter_releases_based_on_prerelease()

    def get_selected_tag(self) -> str:
        release: GithubRelease | None = self.ui.releaseComboBox.itemData(self.ui.releaseComboBox.currentIndex())
        return release.tag_name if release else ""

    def update_version_label(self):
        """Update the current version label with dynamic color based on selected release."""
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

        current_version: str = LOCAL_PROGRAM_INFO["currentVersion"]
        selected_tag: str = self.get_selected_tag()
        if selected_tag:
            version_color: str = warning_color.name() if is_remote_version_newer(current_version, toolset_tag_to_version(selected_tag)) else success_color.name()
        else:
            version_color: str = success_color.name()
        version_text: str = f"<span style='font-size:16px; font-weight:bold; color:{version_color};'>{current_version}</span>"
        from toolset.gui.common.localization import trf

        self.ui.currentVersionLabel.setText(trf("Holocron Toolset Current Version: {version}", version=version_text))

    def on_release_changed(
        self,
        index: int,  # noqa: FBT001
    ):
        if index < 0 or index >= len(self.releases):
            self.ui.titleLabel.setText("What is new in version ")
            return
        release: GithubRelease = self.ui.releaseComboBox.itemData(index)
        if not release:
            return
        changelog_html: str = convert_markdown_to_html(release.body, self)
        self.ui.changelogEdit.setHtml(changelog_html)
        self._update_title_label(release)
        self.update_version_label()

    def _update_title_label(self, release: GithubRelease) -> None:
        """Set titleLabel to 'What is new in version {tag} ({date})' with version colored from palette."""
        app = QApplication.instance()
        if app is None or not isinstance(app, QApplication):
            palette = QPalette()
        else:
            palette = app.palette()
        highlight_color = palette.color(QPalette.ColorRole.Highlight)
        if not highlight_color.isValid():
            highlight_color = palette.color(QPalette.ColorRole.Link)
        color_hex = highlight_color.name()
        tag = release.tag_name
        date_str = ""
        if release.published_at:
            try:
                # ISO format e.g. 2024-01-15T12:00:00Z
                dt = datetime.fromisoformat(release.published_at.replace("Z", "+00:00"))
                date_str = f"{dt.year}/{dt.month}/{dt.day}"
            except (ValueError, TypeError):
                date_str = release.published_at[:10] if len(release.published_at) >= 10 else release.published_at
        if date_str:
            title = f'What is new in version <span style="color:{color_hex}; font-weight:bold;">{tag}</span> ({date_str})'
        else:
            title = f'What is new in version <span style="color:{color_hex}; font-weight:bold;">{tag}</span>'
        self.ui.titleLabel.setText(title)

    def on_checkout_clicked(self) -> None:
        """Open the selected release's web page in the default browser."""
        release = self.ui.releaseComboBox.currentData()
        if not release or not getattr(release, "html_url", None):
            return
        QDesktopServices.openUrl(QUrl(release.html_url))

    def get_latest_release(self) -> GithubRelease | None:
        if self.releases:
            return self.releases[0]
        self.set_prerelease(True)
        return self.releases[0] if self.releases else None

    def on_update_latest_clicked(self):
        latest_release: GithubRelease | None = self.get_latest_release()
        if not latest_release:
            RobustLogger().warning("No toolset releases found")
            return
        self.start_update(latest_release)

    def on_install_selected(self):
        release = self.ui.releaseComboBox.currentData()
        if not release:
            from toolset.gui.common.localization import translate as tr

            QMessageBox(QMessageBox.Icon.Information, tr("Select a release"), tr("No release selected, select one first.")).exec()
            return
        self.start_update(release)

    def start_update(self, release: GithubRelease):
        os_name: str = platform.system().lower()
        proc_arch: str = ProcessorArchitecture.from_os().get_machine_repr()
        asset: Asset | None = next((a for a in release.assets if proc_arch in a.name.lower() and os_name in a.name.lower()), None)

        if not asset:
            from toolset.gui.common.localization import translate as tr, trf

            QMessageBox(
                QMessageBox.Icon.Information,
                tr("No asset found"),
                trf("There are no binaries available for download for release '{tag}'.", tag=release.tag_name),
            ).exec()
            return

        download_url: str = asset.browser_download_url
        self.hide()
        start_update_process(release, download_url)
