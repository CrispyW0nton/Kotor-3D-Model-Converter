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
