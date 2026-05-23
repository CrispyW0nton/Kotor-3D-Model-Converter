"""Provider-backed Qt resource browser model tests."""

from __future__ import annotations

from PySide6 import QtCore

from src.core.project.resource_address import ResourceAddress
from src.core.resources.game_resource_provider import (
    GameResourceQuery,
    GameResourceRecord,
    InMemoryGameResourceProvider,
)
from src.gui.qt_lib.panels.qt_resource_browser_model import (
    ResourceBrowserColumn,
    ResourceBrowserRole,
    ResourceRecordFilterProxyModel,
    ResourceRecordTableModel,
)


def _record(
    resref: str,
    restype: str,
    *,
    game: str = "k1",
    module_id: str | None = None,
    layer: str = "base",
    scheme: str = "game_resource",
    source: str = "chitin",
    size: int = 10,
) -> GameResourceRecord:
    return GameResourceRecord(
        address=ResourceAddress(
            scheme=scheme,
            game=game,
            module_id=module_id,
            resref=resref,
            restype=restype,
            layer=layer,
        ),
        source=source,
        size=size,
    )


def test_resource_table_model_displays_provider_records_and_roles() -> None:
    record = _record("PMBAM", "MDL", module_id="tar_m09aa", layer="override", source="Override/pmbam.mdl")
    model = ResourceRecordTableModel([record])

    assert model.rowCount() == 1
    assert model.columnCount() == len(ResourceRecordTableModel.HEADERS)
    assert model.headerData(ResourceBrowserColumn.RESREF, QtCore.Qt.Horizontal) == "ResRef"
    assert model.data(model.index(0, ResourceBrowserColumn.RESREF)) == "PMBAM"
    assert model.data(model.index(0, ResourceBrowserColumn.RESTYPE)) == "MDL"
    assert model.data(model.index(0, ResourceBrowserColumn.MODULE)) == "tar_m09aa"
    assert model.data(model.index(0, 0), int(ResourceBrowserRole.ADDRESS)) == record.address
    assert model.data(model.index(0, 0), int(ResourceBrowserRole.RECORD)) == record
    assert model.data(model.index(0, 0), int(ResourceBrowserRole.RESREF)) == "PMBAM"
    assert model.data(model.index(0, 0), int(ResourceBrowserRole.SOURCE)) == "Override/pmbam.mdl"
    assert "PMBAM.mdl" in model.data(model.index(0, 0), QtCore.Qt.ToolTipRole)


def test_resource_table_model_loads_from_provider_query() -> None:
    provider = InMemoryGameResourceProvider(
        [
            (_record("PMBAM", "MDL", layer="base"), b"mdl"),
            (_record("PMBAM", "MDX", layer="base"), b"mdx"),
        ]
    )
    model = ResourceRecordTableModel()

    records = model.load_from_provider(provider, GameResourceQuery(resref="pmbam", restype="MDL"))

    assert len(records) == 1
    assert model.rowCount() == 1
    assert model.address_at(0).restype == "MDL"


def test_filter_proxy_filters_by_restype_layer_module_game_and_text() -> None:
    model = ResourceRecordTableModel(
        [
            _record("PMBAM", "MDL", module_id="tar_m09aa", layer="override", source="Override"),
            _record("dan13_jedi", "UTC", module_id="danm13", layer="module", source="danm13_s.rim"),
            _record("global", "2DA", game="k2", layer="base", source="2da.bif"),
        ]
    )
    proxy = ResourceRecordFilterProxyModel()
    proxy.setSourceModel(model)

    proxy.set_restype_filter("utc")
    assert proxy.rowCount() == 1
    assert proxy.index(0, ResourceBrowserColumn.RESREF).data() == "dan13_jedi"

    proxy.set_restype_filter(None)
    proxy.set_layer_filter("override")
    assert proxy.rowCount() == 1
    assert proxy.index(0, ResourceBrowserColumn.RESREF).data() == "PMBAM"

    proxy.set_layer_filter(None)
    proxy.set_module_filter("danm13")
    assert proxy.rowCount() == 1
    assert proxy.index(0, ResourceBrowserColumn.RESREF).data() == "dan13_jedi"

    proxy.set_module_filter(None)
    proxy.set_game_filter("k2")
    assert proxy.rowCount() == 1
    assert proxy.index(0, ResourceBrowserColumn.RESREF).data() == "global"

    proxy.set_game_filter(None)
    proxy.set_text_filter("pmb")
    assert proxy.rowCount() == 1
    assert proxy.index(0, ResourceBrowserColumn.RESREF).data() == "PMBAM"


def test_filter_proxy_can_exclude_local_files() -> None:
    model = ResourceRecordTableModel(
        [
            _record("PMBAM", "MDL", scheme="game_resource", layer="base"),
            GameResourceRecord(
                address=ResourceAddress(scheme="local_file", path="C:/imports/custom.fbx"),
                source="local file",
                size=100,
            ),
        ]
    )
    proxy = ResourceRecordFilterProxyModel()
    proxy.setSourceModel(model)

    assert proxy.rowCount() == 2
    proxy.set_include_local_files(False)

    assert proxy.rowCount() == 1
    assert proxy.index(0, ResourceBrowserColumn.RESREF).data() == "PMBAM"


def test_filter_proxy_sorts_size_numerically() -> None:
    model = ResourceRecordTableModel(
        [
            _record("small", "MDL", size=10),
            _record("large", "MDL", size=200),
            _record("medium", "MDL", size=50),
        ]
    )
    proxy = ResourceRecordFilterProxyModel()
    proxy.setSourceModel(model)
    proxy.sort(ResourceBrowserColumn.SIZE, QtCore.Qt.DescendingOrder)

    assert proxy.index(0, ResourceBrowserColumn.RESREF).data() == "large"
    assert proxy.index(1, ResourceBrowserColumn.RESREF).data() == "medium"
    assert proxy.index(2, ResourceBrowserColumn.RESREF).data() == "small"


def test_qt_lib_alias_exposes_resource_browser_model() -> None:
    from src.gui.qt_lib.panels.qt_resource_browser_model import ResourceRecordTableModel as AliasModel

    assert AliasModel.__name__ == "ResourceRecordTableModel"
    assert hasattr(AliasModel, "load_from_provider")
