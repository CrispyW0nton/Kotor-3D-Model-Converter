"""Regression tests comparing GhostRigger's loader against raw PyKotor.

These tests reuse the KotorMCP-Ghost comparison helpers.  They skip gracefully
when local game files or the sibling KotorMCP checkout are unavailable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


WORKSPACES = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces")
KOTORMCP_SRC = WORKSPACES / "KotorMCP" / "src"
PYKOTOR_SRC = WORKSPACES / "PyKotor" / "Libraries" / "PyKotor" / "src"
UTILITY_SRC = WORKSPACES / "PyKotor" / "Libraries" / "Utility" / "src"

for path in (KOTORMCP_SRC, PYKOTOR_SRC, UTILITY_SRC):
    text = str(path)
    if path.exists() and text not in sys.path:
        sys.path.insert(0, text)

K1_PATH = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
K2_PATH = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")

has_k1 = K1_PATH.is_dir()
has_k2 = K2_PATH.is_dir()
has_kotormcp = (KOTORMCP_SRC / "kotormcp" / "tools" / "ghostrigger_tools.py").is_file()

skip_no_k1 = pytest.mark.skipif(not has_k1, reason="K1 game files not found")
skip_no_k2 = pytest.mark.skipif(not has_k2, reason="K2 game files not found")
skip_no_kotormcp = pytest.mark.skipif(not has_kotormcp, reason="KotorMCP-Ghost tools not found")


@skip_no_kotormcp
@skip_no_k1
@pytest.mark.parametrize(
    "resref",
    [
        "pfhc01",
        "ad_saul",
        "c_bantha",
        "N_AdmrlSaulKar",
        "PFHB05",
        "c_brith",       # bonemap overflow slot 16 regression
        "c_drdprobe",    # q/-q quaternion sign-equivalence regression
        "c_kraytdragon",
        "n_commf",
        "n_tuskanf",
    ],
)
def test_k1_model_pipeline_match(resref):
    from kotormcp.tools.ghostrigger_tools import compare_model_pipelines

    os.environ["K1_PATH"] = str(K1_PATH)
    result = compare_model_pipelines("k1", resref)
    assert result["match"], (
        f"{resref}: {len(result['discrepancies'])} discrepancies: "
        + "; ".join(
            f"{d['node']}.{d['field']}: {d['pykotor']} vs {d['ghostrigger']}"
            for d in result["discrepancies"][:5]
        )
    )


@skip_no_kotormcp
@skip_no_k2
@pytest.mark.parametrize(
    "resref",
    [
        "c_cannok",
        "c_hssiss",
        "c_zakkeg",
        "c_brith",
        "c_drdprobe",
        "c_bosdrexl",
    ],
)
def test_k2_model_pipeline_match(resref):
    from kotormcp.tools.ghostrigger_tools import compare_model_pipelines

    os.environ["K2_PATH"] = str(K2_PATH)
    result = compare_model_pipelines("k2", resref)
    assert result["match"], f"{resref}: {len(result['discrepancies'])} discrepancies"


@skip_no_kotormcp
@skip_no_k1
@pytest.mark.parametrize("resref", ["pfhc01", "ad_saul", "c_bantha", "c_brith"])
def test_k1_skinning_valid(resref):
    from kotormcp.tools.ghostrigger_tools import inspect_skinning

    os.environ["K1_PATH"] = str(K1_PATH)
    result = inspect_skinning("k1", resref)
    for skin in result["skin_nodes"]:
        assert skin["out_of_range_indices"] == 0, (
            f"{resref}/{skin['name']}: {skin['out_of_range_indices']} out-of-range bone indices"
        )
        assert skin["vertices_with_zero_weight"] == 0, (
            f"{resref}/{skin['name']}: {skin['vertices_with_zero_weight']} zero-weight vertices"
        )
        wmin, wmax = skin["weight_sum_range"]
        assert wmin >= 0.98 and wmax <= 1.02, (
            f"{resref}/{skin['name']}: weight sums [{wmin:.3f}, {wmax:.3f}] outside [0.98, 1.02]"
        )


@skip_no_kotormcp
@skip_no_k1
@pytest.mark.parametrize("resref", ["pfhc01", "ad_saul", "c_bantha", "c_brith"])
def test_k1_textures_all_loadable(resref):
    from kotormcp.tools.ghostrigger_tools import validate_textures

    os.environ["K1_PATH"] = str(K1_PATH)
    result = validate_textures("k1", resref)
    assert result["all_found"], (
        f"{resref}: missing textures: "
        + ", ".join(t for t, info in result["textures"].items() if not info["found"])
    )
    assert result["all_loadable"], (
        f"{resref}: unloadable textures: "
        + ", ".join(t for t, info in result["textures"].items() if not info.get("loadable"))
    )
