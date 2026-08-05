"""GameResourceProvider foundation tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.project.resource_address import ResourceAddress
from src.core.resources.game_resource_provider import (
    CompositeGameResourceProvider,
    GameResourceNotFoundError,
    GameResourceQuery,
    GameResourceRecord,
    InMemoryGameResourceProvider,
    LocalFileResourceProvider,
    ResourceManagerGameResourceProvider,
)
from src.core.resources.placeable_library import discover_placeable_library_rows
from src.core.project.placeable_asset import PlaceableAsset, save_placeable_asset


def _record(
    *,
    resref: str = "pmbam",
    restype: str = "MDL",
    layer: str = "base",
    priority: int = 40,
    module_id: str | None = None,
    source: str | None = None,
) -> GameResourceRecord:
    return GameResourceRecord(
        address=ResourceAddress(
            scheme="module_resource" if module_id else "game_resource",
            game="k1",
            module_id=module_id,
            resref=resref,
            restype=restype,
            layer=layer,
        ),
        source=source or layer,
        priority=priority,
        size=0,
    )


def test_placeable_library_discovery_returns_map_studio_utp_rows_and_project_priority(tmp_path: Path) -> None:
    asset = PlaceableAsset(
        game="K1",
        template_resref="plc_bench",
        tag="custom_bench",
        display_name="Custom Bench",
        category="decor",
        appearance_id=12,
    )
    save_placeable_asset(asset, tmp_path / "plc_bench.ghostplaceable.json")
    provider = InMemoryGameResourceProvider(
        [
            (
                _record(resref="plc_bench", restype="UTP", layer="base", priority=40, source="chitin:templates.bif"),
                b"stock-utp",
            ),
            (
                _record(resref="plc_terminal", restype="UTP", layer="base", priority=40, source="chitin:templates.bif"),
                b"stock-terminal",
            ),
        ]
    )

    rows = discover_placeable_library_rows(asset_roots=(tmp_path,), provider=provider, game="K1")
    by_resref = {row["resref"]: row for row in rows}

    assert set(by_resref) == {"plc_bench", "plc_terminal"}
    custom = by_resref["plc_bench"]
    assert custom["source"] == "placeable_builder"
    assert custom["restype"] == "utp"
    assert custom["kind"] == "placeable"
    assert custom["subcategory"] == "Decor"
    assert custom["engine_ready"] is False
    assert custom["metadata"]["shadowed"][0]["source"] == "chitin:templates.bif"
    stock = by_resref["plc_terminal"]
    assert stock["confidence"] == "stock_template"
    assert "not proven" in stock["warning"]


def test_interactive_library_exposes_true_utd_rows_and_rejects_unbacked_door_models() -> None:
    from src.core.modules.authored_gameplay_palette import gameplay_palette_entry_from_library_row

    provider = InMemoryGameResourceProvider(
        [
            (
                _record(
                    resref="door_narshad01",
                    restype="UTD",
                    layer="module",
                    module_id="301nar_s",
                    priority=80,
                    source="module:301NAR_s.rim",
                ),
                b"utd-bytes",
            ),
        ]
    )

    rows = discover_placeable_library_rows(provider=provider, game="K1")
    door = next(row for row in rows if row["resref"] == "door_narshad01")
    entry = gameplay_palette_entry_from_library_row(door)
    enriched_model_entry = gameplay_palette_entry_from_library_row(
        {
            "game": "K1",
            "resref": "dor_nar01",
            "category": "Doors",
            "door_template_resref": "door_narshad01",
            "source": "models.bif",
        }
    )

    assert door["restype"] == "utd"
    assert door["kind"] == "door"
    assert door["metadata"]["address"]["module_id"] == "301nar_s"
    assert entry is not None and entry.template_resref == "door_narshad01"
    assert entry.confidence == "template"
    assert enriched_model_entry is not None
    assert enriched_model_entry.template_resref == "door_narshad01"
    assert gameplay_palette_entry_from_library_row(
        {"game": "K1", "resref": "dor_nar01", "category": "Doors", "source": "models.bif"}
    ) is None


def test_creature_palette_requires_a_real_utc_instead_of_advertising_a_model() -> None:
    from src.core.modules.authored_gameplay_palette import gameplay_palette_entry_from_library_row

    gizka_model = gameplay_palette_entry_from_library_row(
        {
            "game": "K1",
            "resref": "c_gizka",
            "restype": "mdl",
            "category": "Creatures",
            "subcategory": "Gizka",
            "source": "models.bif",
        }
    )
    gizka_utc = gameplay_palette_entry_from_library_row(
        {
            "game": "K1",
            "resref": "tat_gizka_01",
            "restype": "utc",
            "category": "Creatures",
            "subcategory": "Gizka",
            "source": "module:tat_m17aa.rim",
        }
    )

    assert gizka_model is None
    assert gizka_utc is not None
    assert gizka_utc.kind == "creature"
    assert gizka_utc.template_resref == "tat_gizka_01"
    assert gizka_utc.confidence == "template"


def test_non_core_interactive_templates_bundle_declared_utp_utd_dlg_ncs_uti_graph() -> None:
    from pykotor.common.misc import InventoryItem, ResRef
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, bytes_dlg
    from pykotor.resource.generics.utd import UTD, bytes_utd
    from pykotor.resource.generics.utp import UTP, bytes_utp
    from src.core.workflow.placeable_builder_service import referenced_interactive_resource_report

    terminal = UTP()
    terminal.resref = ResRef("puzzle_terminal")
    terminal.tag = "puzzle_terminal"
    terminal.appearance_id = 1
    terminal.conversation = ResRef("puzzle_dialog")
    terminal.on_used = ResRef("puzzle_start")
    terminal.has_inventory = True
    terminal.inventory = [InventoryItem(ResRef("puzzle_key"))]

    dialog = DLG()
    entry = DLGEntry()
    entry.script1 = ResRef("puzzle_action")
    dialog.starters = [DLGLink(entry)]

    door = UTD()
    door.resref = ResRef("puzzle_door")
    door.tag = "puzzle_door"
    door.appearance_id = 1
    door.on_open = ResRef("door_opened")
    door.key_required = True
    door.key_name = "puzzle_key"

    module_id = "source_s"
    records = [
        (_record(resref="puzzle_terminal", restype="UTP", layer="module", module_id=module_id, priority=80), bytes_utp(terminal)),
        (_record(resref="puzzle_door", restype="UTD", layer="module", module_id=module_id, priority=80), bytes_utd(door)),
        (_record(resref="puzzle_dialog", restype="DLG", layer="module", module_id="source_dlg", priority=80), bytes_dlg(dialog)),
        (_record(resref="puzzle_start", restype="NCS", layer="module", module_id=module_id, priority=80), b"ncs-start"),
        (_record(resref="puzzle_action", restype="NCS", layer="module", module_id="source_dlg", priority=80), b"ncs-action"),
        (_record(resref="door_opened", restype="NCS", layer="module", module_id=module_id, priority=80), b"ncs-door"),
        (_record(resref="puzzle_key", restype="UTI", layer="module", module_id=module_id, priority=80), b"uti-key"),
    ]
    report = referenced_interactive_resource_report(
        "",
        (("puzzle_terminal", "UTP"), ("puzzle_door", "UTD")),
        game="K1",
        provider=InMemoryGameResourceProvider(records),
    )

    keys = {(resref, restype.lower().lstrip(".")) for resref, restype, _data in report.resources}
    assert keys == {
        ("puzzle_terminal", "utp"),
        ("puzzle_door", "utd"),
        ("puzzle_dialog", "dlg"),
        ("puzzle_start", "ncs"),
        ("puzzle_action", "ncs"),
        ("door_opened", "ncs"),
        ("puzzle_key", "uti"),
    }
    assert report.has_blocking is False
    assert any(issue.code == "compiled_script_graph_requires_game_proof" for issue in report.issues)

    missing = referenced_interactive_resource_report(
        "",
        (("puzzle_terminal", "UTP"),),
        game="K1",
        provider=InMemoryGameResourceProvider(records[:-3]),
    )
    assert missing.has_blocking is True
    assert any(issue.code == "missing_interactive_dependency" for issue in missing.issues)


def test_in_memory_provider_resolves_resource_address_with_provenance() -> None:
    provider = InMemoryGameResourceProvider(
        [
            (_record(resref="pmbam", restype="MDL", layer="base", priority=40, source="chitin:models.bif"), b"mdl"),
        ]
    )
    address = ResourceAddress(scheme="game_resource", game="K1", resref="PMBAM", restype=".mdl")

    result = provider.resolve(address)

    assert result.data == b"mdl"
    assert result.record.address.resref == "pmbam"
    assert result.record.restype == "MDL"
    assert result.record.source == "chitin:models.bif"
    assert result.record.address.stable_key() == "game_resource:k1:base:MDL:pmbam"


def test_layer_priority_returns_override_and_reports_shadowed_records() -> None:
    provider = InMemoryGameResourceProvider(
        [
            (_record(layer="base", priority=40, source="chitin:models.bif"), b"base"),
            (_record(layer="module", priority=80, module_id="tar_m02aa", source="module:tar_m02aa.rim"), b"module"),
            (_record(layer="override", priority=100, source="override"), b"override"),
        ]
    )

    result = provider.resolve(GameResourceQuery(game="k1", resref="pmbam", restype="mdl"))

    assert result.data == b"override"
    assert result.record.layer == "override"
    assert [record.layer for record in result.shadowed_records] == ["module", "base"]
    assert "shadows 2 lower-priority" in result.warnings[0]


def test_module_resource_filter_requires_matching_module() -> None:
    provider = InMemoryGameResourceProvider(
        [
            (_record(resref="g_sithtroop002", restype="UTC", module_id="tar_m02aa", layer="module", priority=80), b"tar"),
            (_record(resref="g_sithtroop002", restype="UTC", module_id="danm13aa", layer="module", priority=80), b"dan"),
        ]
    )

    result = provider.resolve(
        ResourceAddress(
            scheme="module_resource",
            game="k1",
            module_id="danm13aa",
            resref="g_sithtroop002",
            restype="UTC",
        )
    )

    assert result.data == b"dan"
    assert result.record.address.module_id == "danm13aa"


def test_provider_exposes_module_hydration_compatible_methods() -> None:
    provider = InMemoryGameResourceProvider(
        [
            (
                _record(resref="g_sithtroop002", restype="UTC", module_id="tar_m02aa", layer="module", priority=80),
                b"utc",
            ),
        ]
    )

    records = provider.list_module_resources("tar_m02aa", game="k1")
    data = provider.read_resource("g_sithtroop002", "utc", module_root="tar_m02aa", game="k1")

    assert records[0].resref == "g_sithtroop002"
    assert records[0].restype == "UTC"
    assert data == b"utc"


def test_local_file_provider_reads_path_without_game_resource_layer(tmp_path: Path) -> None:
    path = tmp_path / "imported_mesh.fbx"
    path.write_bytes(b"fbx")
    provider = LocalFileResourceProvider()

    result = provider.resolve(ResourceAddress(scheme="local_file", path=str(path)))

    assert result.data == b"fbx"
    assert result.record.address.scheme == "local_file"
    assert result.record.address.resref == "imported_mesh"
    assert result.record.address.restype == "FBX"
    assert result.record.layer == "local"


def test_composite_provider_selects_highest_priority_across_providers() -> None:
    base = InMemoryGameResourceProvider([(_record(layer="base", priority=40), b"base")])
    project = InMemoryGameResourceProvider([(_record(layer="project", priority=110), b"project")])
    provider = CompositeGameResourceProvider([base, project])

    result = provider.resolve(GameResourceQuery(game="k1", resref="pmbam", restype="mdl"))

    assert result.data == b"project"
    assert result.record.layer == "project"
    assert [record.layer for record in result.shadowed_records] == ["base"]


def test_missing_resource_fails_clearly() -> None:
    provider = InMemoryGameResourceProvider()

    with pytest.raises(GameResourceNotFoundError, match="missing.utc"):
        provider.resolve(GameResourceQuery(game="k1", resref="missing", restype="utc"))


def test_resource_manager_adapter_reads_public_manager_and_reports_record() -> None:
    class FakeManager:
        def get(self, name, res_type, game="K1"):
            assert name == "pmbam"
            assert game == "K1"
            assert res_type > 0
            return b"mdl"

        def get_k1(self):
            return None

        def get_k2(self):
            return None

    provider = ResourceManagerGameResourceProvider(FakeManager())

    result = provider.resolve(GameResourceQuery(game="k1", resref="pmbam", restype="mdl"))

    assert result.data == b"mdl"
    assert result.record.address.resref == "pmbam"
    assert result.record.address.restype == "MDL"
    assert result.record.source == "resource_manager"


def test_explicit_game_query_uses_strict_manager_lookup_without_cross_game_fallback() -> None:
    calls: list[tuple[str, int, str]] = []

    class FakeManager:
        def get_strict(self, name, res_type, game="K1"):
            calls.append((name, res_type, game))
            return None

        def get(self, *_args, **_kwargs):
            raise AssertionError("Explicit Map Studio game queries must not use cross-game fallback.")

        def get_k1(self):
            return None

        def get_k2(self):
            return None

    provider = ResourceManagerGameResourceProvider(FakeManager())

    with pytest.raises(GameResourceNotFoundError):
        provider.resolve(GameResourceQuery(game="k2", resref="k1_only_prop", restype="utp"))

    assert calls and calls[0][0] == "k1_only_prop"
    assert calls[0][2] == "K2"


def test_resource_manager_adapter_can_list_indexed_override_records(tmp_path: Path) -> None:
    override_file = tmp_path / "pmbam.mdl"
    override_file.write_bytes(b"mdl")
    inst = SimpleNamespace(_override={"pmbam:2002": str(override_file)}, _mod_erfs=[], _tex_erfs=[], _key_map={})
    manager = SimpleNamespace(get_k1=lambda: inst, get_k2=lambda: None)
    provider = ResourceManagerGameResourceProvider(manager)

    records = provider.list_resources(GameResourceQuery(game="k1", resref="pmbam", restype="mdl"))

    assert len(records) == 1
    assert records[0].layer == "override"
    assert records[0].source_path == str(override_file)


def test_resource_manager_adapter_reads_exact_selected_module_archive(tmp_path: Path) -> None:
    class FakeErf:
        def __init__(self, path: Path, payload: bytes) -> None:
            self.path = str(path)
            self.payload = payload
            self._index = {"shared_terminal:2044": (0, len(payload))}

        def read(self, name: str, restype: int):
            return self.payload if (name.lower(), restype) == ("shared_terminal", 2044) else None

    first = FakeErf(tmp_path / "first_s.rim", b"first-module-utp")
    second = FakeErf(tmp_path / "second_s.rim", b"second-module-utp")
    inst = SimpleNamespace(
        _override={},
        _mod_erfs=[first, second],
        _tex_erfs=[],
        _key_map={},
    )

    class FakeManager:
        get_k1 = lambda self: inst
        get_k2 = lambda self: None
        get_strict = lambda self, *_args, **_kwargs: b"wrong-global-priority-result"

    provider = ResourceManagerGameResourceProvider(FakeManager())
    result = provider.resolve(
        ResourceAddress(
            scheme="module_resource",
            game="K1",
            module_id="second_s",
            resref="shared_terminal",
            restype="UTP",
            layer="module",
            path=second.path,
        )
    )

    assert result.data == b"second-module-utp"
    assert result.address.module_id == "second_s"
    assert result.record.source_path == second.path


def test_exact_module_address_never_falls_back_to_shadowing_global_resource(tmp_path: Path) -> None:
    class FakeErf:
        path = str(tmp_path / "selected_s.rim")
        _index = {"shared_terminal:2044": (0, 8)}

        @staticmethod
        def read(_name: str, _restype: int):
            return None

    archive = FakeErf()
    inst = SimpleNamespace(_override={}, _mod_erfs=[archive], _tex_erfs=[], _key_map={})

    class FakeManager:
        get_k1 = lambda self: inst
        get_k2 = lambda self: None
        get_strict = lambda self, *_args, **_kwargs: b"wrong-global-priority-result"

    provider = ResourceManagerGameResourceProvider(FakeManager())
    with pytest.raises(GameResourceNotFoundError):
        provider.resolve(
            ResourceAddress(
                scheme="module_resource",
                game="K1",
                module_id="selected_s",
                resref="shared_terminal",
                restype="UTP",
                layer="module",
                path=archive.path,
            )
        )
