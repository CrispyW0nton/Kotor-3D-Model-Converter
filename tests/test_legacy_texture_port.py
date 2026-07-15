"""Focused contracts for exact vanilla texture staging."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
K1_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def _install_payload_paths() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_txi_dependency_parser_follows_external_material_textures() -> None:
    _install_payload_paths()
    from src.core.workflow.legacy_texture_port import _txi_dependencies

    assert _txi_dependencies(
        "envmaptexture CM_DRDYT\n"
        "bumpmaptexture normal_map\n"
        "bumpmapscaling 1.5\n"
        "envmaptexture cm_drdyt # duplicate\n"
    ) == ("CM_DRDYT", "normal_map")


@pytest.mark.skipif(
    not (K1_ROOT / "chitin.key").is_file() or not (K2_ROOT / "chitin.key").is_file(),
    reason="K1/K2 installations are required for exact vanilla texture proof",
)
def test_stage_k1_only_texture_for_k2_without_touching_installations(tmp_path: Path) -> None:
    _install_payload_paths()
    from pykotor.resource.formats.tpc import read_tpc
    from src.core.workflow.legacy_texture_port import (
        LegacyTexturePortRequest,
        stage_vanilla_texture_dependencies,
    )

    result = stage_vanilla_texture_dependencies(
        LegacyTexturePortRequest(
            source_game_root=str(K1_ROOT),
            target_game_root=str(K2_ROOT),
            texture_resrefs=("LKO_flr03",),
            output_dir=str(tmp_path),
        )
    )

    assert result.ok, result.blocking_issues
    assert [row["resref"].lower() for row in result.extracted] == ["lko_flr03"]
    output = tmp_path / "lko_flr03.tpc"
    assert output.is_file()
    assert len(output.read_bytes()) == result.extracted[0]["size"]
    read_tpc(output.read_bytes())
    assert Path(result.manifest_path).is_file()
