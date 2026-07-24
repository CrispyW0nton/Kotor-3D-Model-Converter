"""Focused read-only installation verification tests for Head Builder."""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.core.project.resource_address import ResourceAddress
from src.core.resources.game_resource_provider import (
    GameResourceRecord,
    InMemoryGameResourceProvider,
)
from src.core.resources.head_donor_catalog import HeadDonorCatalog
from src.core.resources.head_game_install import verify_head_game_install


def _record(restype: str) -> GameResourceRecord:
    return GameResourceRecord(
        address=ResourceAddress(
            scheme="game_resource",
            game="k2",
            resref="PFHA04",
            restype=restype,
            layer="base",
            path=r"H:\K2\data\models.bif",
        ),
        source="chitin:models.bif",
        source_path=r"H:\K2\data\models.bif",
        priority=40,
    )


def _catalog() -> HeadDonorCatalog:
    return HeadDonorCatalog(
        InMemoryGameResourceProvider(
            [
                (_record("MDL"), b"stock-mdl"),
                (_record("MDX"), b"stock-mdx"),
            ]
        )
    )


def test_install_verification_fingerprints_files_and_reads_stock_pair_only(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "swkotor2.exe"
    chitin = tmp_path / "chitin.key"
    executable.write_bytes(b"MZ" + b"\0" * 32)
    chitin.write_bytes(b"KEY V1  " + b"\0" * 32)
    before = {
        executable: executable.read_bytes(),
        chitin: chitin.read_bytes(),
    }

    result = verify_head_game_install(
        game="K2",
        install_dir=tmp_path,
        donor_catalog=_catalog(),
    )

    assert result.verified is True
    assert result.executable_sha256 == hashlib.sha256(
        before[executable]
    ).hexdigest()
    assert result.chitin_key_sha256 == hashlib.sha256(before[chitin]).hexdigest()
    assert result.chitin_signature == "KEY V1  "
    assert result.resource_probe_resref == "PFHA04"
    assert result.resource_probe_mdl_sha256 == hashlib.sha256(
        b"stock-mdl"
    ).hexdigest()
    assert result.resource_probe_source == "chitin:models.bif"
    assert result.fingerprint_sha256
    assert result.issues == ()
    assert executable.read_bytes() == before[executable]
    assert chitin.read_bytes() == before[chitin]


def test_missing_executable_and_bad_key_signature_are_blocking(
    tmp_path: Path,
) -> None:
    (tmp_path / "chitin.key").write_bytes(b"NOT A KEY")

    result = verify_head_game_install(
        game="K2",
        install_dir=tmp_path,
        donor_catalog=_catalog(),
    )
    checks = {issue.check_id for issue in result.issues}

    assert result.verified is False
    assert "head.install.executable" in checks
    assert "head.install.chitin_signature" in checks


def test_resource_provider_is_required_for_a_verified_install(
    tmp_path: Path,
) -> None:
    (tmp_path / "swkotor.exe").write_bytes(b"MZ-k1")
    (tmp_path / "chitin.key").write_bytes(b"KEY V1  ")

    result = verify_head_game_install(
        game="K1",
        install_dir=tmp_path,
        donor_catalog=None,
    )

    assert result.verified is False
    assert result.resource_probe_readable is False
    assert "head.install.resource_provider" in {
        issue.check_id for issue in result.issues
    }


def test_wrong_game_executable_name_does_not_cross_fallback(
    tmp_path: Path,
) -> None:
    (tmp_path / "swkotor.exe").write_bytes(b"MZ-k1")
    (tmp_path / "chitin.key").write_bytes(b"KEY V1  ")

    result = verify_head_game_install(
        game="K2",
        install_dir=tmp_path,
        donor_catalog=_catalog(),
    )

    assert result.verified is False
    assert result.executable_path.endswith("swkotor2.exe")
    assert "head.install.executable" in {
        issue.check_id for issue in result.issues
    }
