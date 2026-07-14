"""Game-directory texture browser with preview thumbnails for Map Studio.

Presentation-only dialog: lists every texture resref the connected KOTOR
resource manager can see (Override, ERF texture packs, KEY/BIF) with decoded
thumbnail previews, a substring filter, and double-click/OK selection.  Used
by the GModeler "Set Texture" face action; owns no texture policy.

Thumbnails decode lazily in QTimer batches so opening the dialog stays
instant even with thousands of TPC textures.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

THUMBNAIL_SIZE = 64
GRID_SIZE = 92
PAGE_SIZE = 400
DECODE_BATCH = 12


def _pil_to_pixmap(image) -> QtGui.QPixmap | None:
    try:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        qimage = QtGui.QImage(rgba.tobytes(), width, height, width * 4, QtGui.QImage.Format_RGBA8888).copy()
        return QtGui.QPixmap.fromImage(
            qimage.scaled(
                THUMBNAIL_SIZE,
                THUMBNAIL_SIZE,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
        )
    except Exception:
        return None


class MapStudioTextureBrowserDialog(QtWidgets.QDialog):
    """Pick one texture resref from the game directory, with previews."""

    def __init__(
        self,
        resource_manager,
        parent: QtWidgets.QWidget | None = None,
        *,
        project=None,
        game: str = "",
        initial_filter: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("mapStudioTextureBrowserDialog")
        self.setWindowTitle("Set Face Texture — Game + Project Textures")
        self.resize(720, 520)
        self._resource_manager = resource_manager
        self._project = project
        self._game = str(game or getattr(project, "game", "") or "all").upper()
        self._all_textures: tuple[tuple[str, str, str], ...] = ()
        self._pending_thumbnails: list[QtWidgets.QListWidgetItem] = []
        self._pixmap_cache: dict[tuple[str, str, str], QtGui.QPixmap | None] = {}
        self._placeholder = self._placeholder_icon()

        layout = QtWidgets.QVBoxLayout(self)
        self.filter_edit = QtWidgets.QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter textures (e.g. lda_, wall, grate)...")
        self.filter_edit.setText(str(initial_filter or ""))
        self.filter_edit.textChanged.connect(self._repopulate)
        layout.addWidget(self.filter_edit)

        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setViewMode(QtWidgets.QListView.IconMode)
        self.list_widget.setResizeMode(QtWidgets.QListView.Adjust)
        self.list_widget.setMovement(QtWidgets.QListView.Static)
        self.list_widget.setIconSize(QtCore.QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self.list_widget.setGridSize(QtCore.QSize(GRID_SIZE, GRID_SIZE + 18))
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())
        layout.addWidget(self.list_widget, 1)

        self.status_label = QtWidgets.QLabel(self)
        layout.addWidget(self.status_label)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._thumbnail_timer = QtCore.QTimer(self)
        self._thumbnail_timer.setInterval(0)
        self._thumbnail_timer.timeout.connect(self._decode_thumbnail_batch)

        self._load_texture_names()
        self._repopulate()

    # ------------------------------------------------------------------ API

    def selected_texture(self) -> str:
        item = self.list_widget.currentItem()
        return str(item.data(QtCore.Qt.UserRole) or "") if item is not None else ""

    @staticmethod
    def pick_texture(
        resource_manager,
        parent: QtWidgets.QWidget | None = None,
        *,
        project=None,
        game: str = "",
        initial_filter: str = "",
    ) -> str:
        """Open the browser modally; return the chosen resref or ''."""

        dialog = MapStudioTextureBrowserDialog(
            resource_manager,
            parent,
            project=project,
            game=game,
            initial_filter=initial_filter,
        )
        try:
            if dialog.exec() == QtWidgets.QDialog.Accepted:
                return dialog.selected_texture()
            return ""
        finally:
            dialog.deleteLater()

    # ------------------------------------------------------------ internals

    def _placeholder_icon(self) -> QtGui.QIcon:
        pixmap = QtGui.QPixmap(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        pixmap.fill(self.palette().color(QtGui.QPalette.Mid))
        return QtGui.QIcon(pixmap)

    def _load_texture_names(self) -> None:
        manager = self._resource_manager
        rows: dict[str, tuple[str, str, str]] = {}
        project = self._project
        project_path = Path(str(getattr(project, "path", "") or "")) if project is not None else None
        for texture in tuple(getattr(project, "textures", ()) or ()):
            name = str(getattr(texture, "resref", "") or "").strip().lower()
            path_text = str(getattr(texture, "path", "") or "").strip()
            path = Path(path_text) if path_text else None
            if path is not None and not path.is_absolute() and project_path is not None and str(project_path):
                path = project_path.parent / path
            if name:
                rows[name] = (name, "Project", str(path) if path is not None else "")
        if manager is not None:
            try:
                entries = manager.list_textures(self._game if self._game in {"K1", "K2"} else "all") or ()
            except Exception:
                entries = ()
            for entry in entries:
                if isinstance(entry, (tuple, list)) and entry:
                    name = str(entry[0] or "").strip().lower()
                    game = str(entry[1] or self._game or "Game") if len(entry) > 1 else str(self._game or "Game")
                else:
                    name = str(entry or "").strip().lower()
                    game = str(self._game or "Game")
                if name:
                    rows.setdefault(name, (name, game, ""))
        self._all_textures = tuple(sorted(rows.values(), key=lambda row: (row[0], row[1])))
        if not self._all_textures:
            self.status_label.setText(
                "No textures available. Connect a KOTOR game directory or use File > Import Texture to Project."
            )

    def _repopulate(self) -> None:
        wanted = str(self.filter_edit.text() or "").strip().lower()
        matches = [row for row in self._all_textures if wanted in row[0].lower()] if wanted else list(self._all_textures)
        shown = matches[:PAGE_SIZE]
        self.list_widget.clear()
        self._pending_thumbnails.clear()
        for name, source, path in shown:
            item = QtWidgets.QListWidgetItem(self._placeholder, name)
            item.setData(QtCore.Qt.UserRole, name)
            item.setData(QtCore.Qt.UserRole + 1, source)
            item.setData(QtCore.Qt.UserRole + 2, path)
            item.setToolTip(f"{name} — {source}")
            self.list_widget.addItem(item)
            self._pending_thumbnails.append(item)
        suffix = f" (showing first {PAGE_SIZE} — refine the filter)" if len(matches) > PAGE_SIZE else ""
        if self._all_textures:
            self.status_label.setText(f"{len(matches)} of {len(self._all_textures)} textures{suffix}")
        if self._pending_thumbnails:
            self._thumbnail_timer.start()

    def _decode_thumbnail_batch(self) -> None:
        manager = self._resource_manager
        batch = 0
        while self._pending_thumbnails and batch < DECODE_BATCH:
            item = self._pending_thumbnails.pop(0)
            batch += 1
            name = str(item.data(QtCore.Qt.UserRole) or "")
            source = str(item.data(QtCore.Qt.UserRole + 1) or "")
            path = str(item.data(QtCore.Qt.UserRole + 2) or "")
            cache_key = (name, source, path)
            if cache_key in self._pixmap_cache:
                pixmap = self._pixmap_cache[cache_key]
            else:
                pixmap = None
                if source == "Project" and path:
                    try:
                        from PIL import Image

                        with Image.open(path) as source_image:
                            pixmap = _pil_to_pixmap(source_image.copy())
                    except Exception:
                        pixmap = None
                elif manager is not None:
                    try:
                        image = manager.load_texture_image(name, source if source in {"K1", "K2"} else self._game)
                    except Exception:
                        image = None
                    if image is not None:
                        pixmap = _pil_to_pixmap(image)
                self._pixmap_cache[cache_key] = pixmap
            if pixmap is not None:
                item.setIcon(QtGui.QIcon(pixmap))
        if not self._pending_thumbnails:
            self._thumbnail_timer.stop()
