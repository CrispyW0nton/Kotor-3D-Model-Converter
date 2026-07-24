"""Focused stock/effective provenance tests for native head discovery."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.core.characters.head_builder_project import ResourceView
from src.core.project.resource_address import ResourceAddress
from src.core.resources.game_resource_provider import (
    GameResourceRecord,
    InMemoryGameResourceProvider,
)
from src.core.resources.head_donor_catalog import (
    HeadDonorCatalog,
    HeadDonorNotFoundError,
    looks_like_head_resref,
)


def _record(
    *,
    resref: str,
    restype: str,
    layer: str,
    priority: int,
    path: str,
) -> GameResourceRecord:
    return GameResourceRecord(
        address=ResourceAddress(
            scheme=(
                "override_resource"
                if layer == "override"
                else "game_resource"
            ),
            game="k2",
            resref=resref,
            restype=restype,
            layer=layer,
            path=path,
        ),
        source=f"{layer}:{Path(path).name}",
        source_path=path,
        priority=priority,
    )


def _provider(
    *,
    include_stock_mdx: bool = True,
    override_mdx_layer: str = "override",
) -> InMemoryGameResourceProvider:
    rows: list[tuple[GameResourceRecord, bytes]] = [
        (
            _record(
                resref="PFHA04",
                restype="MDL",
                layer="base",
                priority=40,
                path=r"H:\K2\data\models.bif",
            ),
            b"stock-mdl",
        ),
        (
            _record(
                resref="PFHA04",
                restype="MDL",
                layer="override",
                priority=100,
                path=r"H:\K2\override\pfha04.mdl",
            ),
            b"override-mdl",
        ),
        (
            _record(
                resref="PFHA04",
                restype="MDX",
                layer=override_mdx_layer,
                priority=100 if override_mdx_layer == "override" else 40,
                path=(
                    r"H:\K2\override\pfha04.mdx"
                    if override_mdx_layer == "override"
                    else r"H:\K2\data\models.bif"
                ),
            ),
            b"override-mdx" if override_mdx_layer == "override" else b"stock-mdx",
        ),
        (
            _record(
                resref="PLC_BENCH",
                restype="MDL",
                layer="base",
                priority=40,
                path=r"H:\K2\data\models.bif",
            ),
            b"not-a-head",
        ),
    ]
    if include_stock_mdx:
        rows.append(
            (
                _record(
                    resref="PFHA04",
                    restype="MDX",
                    layer="base",
                    priority=40,
                    path=r"H:\K2\data\models.bif",
                ),
                b"stock-mdx",
            )
        )
    return InMemoryGameResourceProvider(rows)


def test_stock_search_excludes_override_and_non_head_rows() -> None:
    rows = HeadDonorCatalog(_provider()).search(
        game="K2",
        resource_view=ResourceView.STOCK_ONLY,
    )

    assert [row.resref for row in rows] == ["PFHA04"]
    candidate = rows[0]
    assert candidate.stock is True
    assert candidate.effective_override is False
    assert candidate.mdl_record.layer == "base"
    assert candidate.mdx_record is not None
    assert candidate.mdx_record.layer == "base"
    assert candidate.warnings == ()


def test_effective_view_selects_override_pair_and_reports_shadowed_stock() -> None:
    candidate = HeadDonorCatalog(_provider()).search(
        game="K2",
        resource_view=ResourceView.EFFECTIVE_OVERRIDE,
        text="pfha04",
    )[0]

    assert candidate.effective_override is True
    assert candidate.mdl_record.layer == "override"
    assert candidate.mdx_record is not None
    assert candidate.mdx_record.layer == "override"
    assert [row.layer for row in candidate.shadowed_mdl] == ["base"]
    assert [row.layer for row in candidate.shadowed_mdx] == ["base"]
    assert any("user-modified" in warning for warning in candidate.warnings)


def test_resolve_reads_exact_selected_layers_and_hashes_source_bytes() -> None:
    catalog = HeadDonorCatalog(_provider())

    stock = catalog.resolve(
        game="K2",
        resref="PFHA04",
        resource_view=ResourceView.STOCK_ONLY,
    )
    effective = catalog.resolve(
        game="K2",
        resref="PFHA04",
        resource_view=ResourceView.EFFECTIVE_OVERRIDE,
    )

    assert stock.mdl_bytes == b"stock-mdl"
    assert stock.mdx_bytes == b"stock-mdx"
    assert stock.mdl_sha256 == hashlib.sha256(b"stock-mdl").hexdigest()
    assert effective.mdl_bytes == b"override-mdl"
    assert effective.mdx_bytes == b"override-mdx"
    assert effective.provenance_dict()["mdl_size"] == len(b"override-mdl")


def test_incomplete_stock_pair_is_visible_but_cannot_be_resolved() -> None:
    catalog = HeadDonorCatalog(_provider(include_stock_mdx=False))
    candidate = catalog.search(game="K2")[0]

    assert candidate.complete_pair is False
    assert candidate.warnings == ("MDX pair is missing.",)
    with pytest.raises(HeadDonorNotFoundError, match="no stock_only MDX pair"):
        catalog.resolve(game="K2", resref="PFHA04")


def test_mixed_effective_pair_is_explicitly_warned() -> None:
    candidate = HeadDonorCatalog(
        _provider(include_stock_mdx=True, override_mdx_layer="base")
    ).search(
        game="K2",
        resource_view=ResourceView.EFFECTIVE_OVERRIDE,
    )[0]

    assert candidate.mdl_record.layer == "override"
    assert candidate.mdx_record is not None
    assert candidate.mdx_record.layer == "base"
    assert any("different resource layers" in row for row in candidate.warnings)


def test_same_layer_pair_from_different_containers_is_explicitly_warned() -> None:
    provider = InMemoryGameResourceProvider(
        [
            (
                _record(
                    resref="PFHA04",
                    restype="MDL",
                    layer="base",
                    priority=40,
                    path=r"H:\K2\data\models.bif",
                ),
                b"mdl",
            ),
            (
                _record(
                    resref="PFHA04",
                    restype="MDX",
                    layer="base",
                    priority=40,
                    path=r"H:\K2\data\other_models.bif",
                ),
                b"mdx",
            ),
        ]
    )

    candidate = HeadDonorCatalog(provider).search(game="K2")[0]

    assert any("different source containers" in row for row in candidate.warnings)


@pytest.mark.parametrize(
    ("resref", "expected"),
    [
        ("PMHC01", True),
        ("PFHA04", True),
        ("P_CARTHH", True),
        ("N_CUSTOM_HEAD01", True),
        ("PLC_BENCH", False),
        ("", False),
    ],
)
def test_head_resref_hint_is_narrow_and_case_insensitive(
    resref: str,
    expected: bool,
) -> None:
    assert looks_like_head_resref(resref) is expected
