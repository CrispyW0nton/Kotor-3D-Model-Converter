"""
tests/test_skeleton_template_picker.py - M12/T1201 picker service tests.

The service stays Qt-free and MCP-free: canonical KOTOR resrefs are listed
without touching the GUI, and game-install rows are passed in as simple
dictionaries.
"""

from __future__ import annotations

import importlib.util as _il_util
import pathlib
import sys

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_module_direct(name: str, path: pathlib.Path):
    spec = _il_util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot create import spec for {path}")
    module = _il_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


try:
    picker = _load_module_direct(
        "ghostrigger_skeleton_template_picker_under_test",
        _SRC_DIR / "core" / "skeleton_template_picker.py",
    )
except Exception as exc:  # pragma: no cover
    pytest.skip(f"skeleton_template_picker unavailable: {exc}",
                allow_module_level=True)


def test_t1201_canonical_sources_include_common_game_bases():
    result = picker.list_skeleton_templates()

    assert result.ok is True
    keys = {opt.key for opt in result.options}
    assert "canonical:k1:body:pmbam" in keys
    assert "canonical:k1:body:n_sithsoldier" in keys
    assert "canonical:k2:body:c_female02" in keys
    assert "canonical:k2:supermodel:s_female03" in keys
    assert all(opt.exists for opt in result.options)


def test_t1201_canonical_body_option_uses_real_game_resref():
    result = picker.list_skeleton_templates(game="k1", part="body")

    assert result.ok is True
    by_resref = {opt.resref: opt for opt in result.options}
    opt = by_resref["pmbam"]
    assert opt.game == "K1"
    assert opt.part == "body"
    assert opt.source == "canonical"
    assert opt.source_resref == "pmbam"
    assert opt.supermodel == "S_Male02"
    assert opt.classification == "character"
    assert opt.path == "installation:pmbam.mdl"


def test_t1201_query_filters_canonical_sources():
    result = picker.list_skeleton_templates(query="sith", part="body")

    assert result.ok is True
    assert {opt.source_resref for opt in result.options} == {"n_sithsoldier"}
    assert all(opt.part == "body" for opt in result.options)


def test_t1201_invalid_game_returns_structured_error():
    result = picker.list_skeleton_templates(game="k3")

    assert result.ok is False
    assert result.code == "invalid_game"
    assert "K1 or K2" in result.message


def test_t1201_game_model_rows_become_picker_options():
    rows = [
        {"resref": "pfbcm", "source": "core", "size": 201846},
        {"resref": "pfhc01", "source": "core", "size": 110000},
    ]
    metadata = {
        "pfbcm": {
            "node_count": 61,
            "supermodel": "S_Female02",
            "classification": "character",
        },
        "pfhc01": {
            "node_count": 33,
            "supermodel": "S_Female02",
            "classification": "character",
        },
    }

    result = picker.list_skeleton_templates(
        game="k1",
        part="body",
        include_canonical=False,
        include_bundled=False,
        game_models=rows,
        metadata_by_resref=metadata,
    )

    assert result.ok is True
    assert len(result.options) == 1
    opt = result.options[0]
    assert opt.source == "core"
    assert opt.game == "K1"
    assert opt.part == "body"
    assert opt.resref == "pfbcm"
    assert opt.node_count == 61
    assert opt.supermodel == "S_Female02"
    assert opt.warnings == []


def test_t1201_game_rows_warn_when_metadata_missing():
    result = picker.list_skeleton_templates(
        game="k1",
        include_canonical=False,
        include_bundled=False,
        game_models=[{"resref": "weird_custom", "source": "override"}],
    )

    assert result.ok is True
    opt = result.options[0]
    assert opt.part == "unknown"
    assert any("Could not infer" in w for w in opt.warnings)
    assert any("Node count unavailable" in w for w in opt.warnings)
    assert any("Supermodel unavailable" in w for w in opt.warnings)


def test_t1201_dedupes_duplicate_game_rows():
    rows = [
        {"resref": "pfbcm", "source": "core", "size": 1},
        {"resref": "pfbcm", "source": "core", "size": 1},
        {"resref": "pfbcm", "source": "chitin", "size": 1},
    ]

    result = picker.list_skeleton_templates(
        game="k1",
        include_canonical=False,
        include_bundled=False,
        game_models=rows,
    )

    assert result.ok is True
    assert [(opt.resref, opt.source) for opt in result.options] == [
        ("pfbcm", "core"),
        ("pfbcm", "chitin"),
    ]


def test_t1201_option_summary_is_compact_for_ui():
    opt = picker.list_skeleton_templates(game="k1", part="body").options[0]

    summary = picker.option_summary(opt)

    assert "K1" in summary
    assert "body" in summary
    assert "pmbam" in summary
    assert "super=S_Male02" in summary
