"""Provider-backed Qt models for KOTOR resource browser surfaces.

The models in this module are intentionally UI-light. They expose
``GameResourceProvider`` records through Qt model/view roles so Retarget,
Character, Module, and Map panels can share one resource table without each
studio inventing its own resref/restype/layer plumbing.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Iterable

from PySide6 import QtCore

from src.core.project.resource_address import ResourceAddress
from src.core.ports import (
    GameResourceProvider,
    GameResourceQuery,
    GameResourceRecord,
)


class ResourceBrowserColumn(IntEnum):
    RESREF = 0
    RESTYPE = 1
    GAME = 2
    MODULE = 3
    LAYER = 4
    SOURCE = 5
    SIZE = 6


class ResourceBrowserRole(IntEnum):
    ADDRESS = int(QtCore.Qt.UserRole) + 1
    RECORD = int(QtCore.Qt.UserRole) + 2
    RESREF = int(QtCore.Qt.UserRole) + 3
    RESTYPE = int(QtCore.Qt.UserRole) + 4
    GAME = int(QtCore.Qt.UserRole) + 5
    MODULE = int(QtCore.Qt.UserRole) + 6
    LAYER = int(QtCore.Qt.UserRole) + 7
    SOURCE = int(QtCore.Qt.UserRole) + 8
    SIZE = int(QtCore.Qt.UserRole) + 9
    SCHEME = int(QtCore.Qt.UserRole) + 10
    STABLE_KEY = int(QtCore.Qt.UserRole) + 11


class ResourceRecordTableModel(QtCore.QAbstractTableModel):
    """Table model over ``GameResourceRecord`` values."""

    HEADERS = ("ResRef", "Type", "Game", "Module", "Layer", "Source", "Size")

    def __init__(
        self,
        records: Iterable[GameResourceRecord] | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._records = list(records or [])

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.DisplayRole,
    ):
        if orientation != QtCore.Qt.Horizontal or role != QtCore.Qt.DisplayRole:
            return None
        if 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return None

    def roleNames(self) -> dict[int, QtCore.QByteArray]:
        names = {
            int(ResourceBrowserRole.ADDRESS): b"resourceAddress",
            int(ResourceBrowserRole.RECORD): b"resourceRecord",
            int(ResourceBrowserRole.RESREF): b"resref",
            int(ResourceBrowserRole.RESTYPE): b"restype",
            int(ResourceBrowserRole.GAME): b"game",
            int(ResourceBrowserRole.MODULE): b"module",
            int(ResourceBrowserRole.LAYER): b"layer",
            int(ResourceBrowserRole.SOURCE): b"source",
            int(ResourceBrowserRole.SIZE): b"size",
            int(ResourceBrowserRole.SCHEME): b"scheme",
            int(ResourceBrowserRole.STABLE_KEY): b"stableKey",
        }
        return {role: QtCore.QByteArray(name) for role, name in names.items()}

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None
        record = self._records[index.row()]
        address = record.address
        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            return self._display_value(record, index.column())
        if role == QtCore.Qt.ToolTipRole:
            return self._tooltip(record)
        if role == int(ResourceBrowserRole.ADDRESS):
            return address
        if role == int(ResourceBrowserRole.RECORD):
            return record
        if role == int(ResourceBrowserRole.RESREF):
            return address.resref or ""
        if role == int(ResourceBrowserRole.RESTYPE):
            return address.restype or ""
        if role == int(ResourceBrowserRole.GAME):
            return address.game or ""
        if role == int(ResourceBrowserRole.MODULE):
            return address.module_id or ""
        if role == int(ResourceBrowserRole.LAYER):
            return address.layer or ""
        if role == int(ResourceBrowserRole.SOURCE):
            return record.source or record.source_path or ""
        if role == int(ResourceBrowserRole.SIZE):
            return record.size
        if role == int(ResourceBrowserRole.SCHEME):
            return address.scheme or ""
        if role == int(ResourceBrowserRole.STABLE_KEY):
            return address.stable_key()
        return None

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlag:
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def set_records(self, records: Iterable[GameResourceRecord]) -> None:
        self.beginResetModel()
        self._records = list(records or [])
        self.endResetModel()

    def load_from_provider(
        self,
        provider: GameResourceProvider,
        query: GameResourceQuery | ResourceAddress | None = None,
    ) -> list[GameResourceRecord]:
        records = provider.list_resources(query)
        self.set_records(records)
        return records

    def record_at(self, row: int) -> GameResourceRecord | None:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def address_at(self, row: int) -> ResourceAddress | None:
        record = self.record_at(row)
        return record.address if record else None

    def records(self) -> list[GameResourceRecord]:
        return list(self._records)

    def _display_value(self, record: GameResourceRecord, column: int) -> str:
        address = record.address
        if column == ResourceBrowserColumn.RESREF:
            return address.resref or ""
        if column == ResourceBrowserColumn.RESTYPE:
            return address.restype or ""
        if column == ResourceBrowserColumn.GAME:
            return address.game or ""
        if column == ResourceBrowserColumn.MODULE:
            return address.module_id or ""
        if column == ResourceBrowserColumn.LAYER:
            return address.layer or ""
        if column == ResourceBrowserColumn.SOURCE:
            return record.source or record.source_path or ""
        if column == ResourceBrowserColumn.SIZE:
            return str(record.size)
        return ""

    def _tooltip(self, record: GameResourceRecord) -> str:
        pieces = [record.address.display_name(), record.address.stable_key()]
        if record.source:
            pieces.append(record.source)
        if record.source_path:
            pieces.append(record.source_path)
        return "\n".join(piece for piece in pieces if piece)


class ResourceRecordFilterProxyModel(QtCore.QSortFilterProxyModel):
    """Filter/sort proxy for provider-backed resource records."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._text_filter = ""
        self._restypes: set[str] = set()
        self._layers: set[str] = set()
        self._modules: set[str] = set()
        self._games: set[str] = set()
        self._include_local_files = True
        self.setDynamicSortFilter(True)

    def set_text_filter(self, text: str | None) -> None:
        self._text_filter = str(text or "").strip().lower()
        self._invalidate_filter()

    def set_restype_filter(self, restypes: str | Iterable[str] | None) -> None:
        self._restypes = {str(value).strip().upper().lstrip(".") for value in _as_iter(restypes) if str(value).strip()}
        self._invalidate_filter()

    def set_layer_filter(self, layers: str | Iterable[str] | None) -> None:
        self._layers = {str(value).strip().lower() for value in _as_iter(layers) if str(value).strip()}
        self._invalidate_filter()

    def set_module_filter(self, modules: str | Iterable[str] | None) -> None:
        self._modules = {str(value).strip().lower() for value in _as_iter(modules) if str(value).strip()}
        self._invalidate_filter()

    def set_game_filter(self, games: str | Iterable[str] | None) -> None:
        self._games = {str(value).strip().lower() for value in _as_iter(games) if str(value).strip()}
        self._invalidate_filter()

    def set_include_local_files(self, include: bool) -> None:
        self._include_local_files = bool(include)
        self._invalidate_filter()

    def filterAcceptsRow(self, source_row: int, source_parent: QtCore.QModelIndex) -> bool:
        source = self.sourceModel()
        if source is None:
            return False
        index = source.index(source_row, 0, source_parent)
        if not index.isValid():
            return False
        scheme = _role_text(source, index, ResourceBrowserRole.SCHEME).lower()
        if not self._include_local_files and scheme == "local_file":
            return False
        if self._restypes and _role_text(source, index, ResourceBrowserRole.RESTYPE).upper() not in self._restypes:
            return False
        if self._layers and _role_text(source, index, ResourceBrowserRole.LAYER).lower() not in self._layers:
            return False
        if self._modules and _role_text(source, index, ResourceBrowserRole.MODULE).lower() not in self._modules:
            return False
        if self._games and _role_text(source, index, ResourceBrowserRole.GAME).lower() not in self._games:
            return False
        if self._text_filter and self._text_filter not in self._search_text(source, index):
            return False
        return True

    def lessThan(self, left: QtCore.QModelIndex, right: QtCore.QModelIndex) -> bool:
        if left.column() == ResourceBrowserColumn.SIZE and right.column() == ResourceBrowserColumn.SIZE:
            return int(left.data(int(ResourceBrowserRole.SIZE)) or 0) < int(right.data(int(ResourceBrowserRole.SIZE)) or 0)
        return str(left.data(QtCore.Qt.DisplayRole) or "").casefold() < str(right.data(QtCore.Qt.DisplayRole) or "").casefold()

    def _search_text(self, source: QtCore.QAbstractItemModel, index: QtCore.QModelIndex) -> str:
        fields = [
            _role_text(source, index, ResourceBrowserRole.RESREF),
            _role_text(source, index, ResourceBrowserRole.RESTYPE),
            _role_text(source, index, ResourceBrowserRole.GAME),
            _role_text(source, index, ResourceBrowserRole.MODULE),
            _role_text(source, index, ResourceBrowserRole.LAYER),
            _role_text(source, index, ResourceBrowserRole.SOURCE),
            _role_text(source, index, ResourceBrowserRole.SCHEME),
            _role_text(source, index, ResourceBrowserRole.STABLE_KEY),
        ]
        return " ".join(fields).lower()

    def _invalidate_filter(self) -> None:
        begin_change = getattr(self, "beginFilterChange", None)
        end_change = getattr(self, "endFilterChange", None)
        if callable(begin_change) and callable(end_change):
            begin_change()
            end_change(QtCore.QSortFilterProxyModel.Direction.Rows)
        else:  # pragma: no cover - compatibility with older Qt bindings
            self.invalidateFilter()


def _role_text(
    model: QtCore.QAbstractItemModel,
    index: QtCore.QModelIndex,
    role: ResourceBrowserRole,
) -> str:
    value = model.data(index, int(role))
    return "" if value is None else str(value)


def _as_iter(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)
