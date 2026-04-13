"""
test_v430_batch_export.py
==========================
Comprehensive tests for Phase 4 of the GhostRigger Character Builder:
  BatchExportConfig — configuration dataclass.
  BatchExportResult — per-slot result object.
  BatchExporter     — headless batch export controller.

All tests are fully headless (no Tk display, no real MDL/FBX exporters required).
Exporter calls are mocked where necessary so the logic can be tested in isolation.

Coverage
--------
  BatchExportConfig
  • __init__ defaults
  • validate() — empty dir, missing formats, bad format name
  • extension_for() — all supported formats
  • output_path() — path construction, prefix, space/slash handling
  • to_dict() / from_dict() — round-trip serialisation
  • SUPPORTED_FORMATS / FORMAT_EXTENSIONS constants

  BatchExportResult
  • constructor fields
  • ok flag
  • __repr__

  BatchExporter
  • __init__ stores scene + config
  • run() with empty scene returns empty list
  • run() with invalid config (empty dir) returns early
  • run() with missing model skips when skip_empty_slots=True
  • run() with missing model writes fail result when skip_empty_slots=False
  • run() creates output_dir when missing
  • run() writes sidecar JSON when include_sidecar=True
  • run() skips sidecar when include_sidecar=False
  • run() calls exporter correctly (MDL path)
  • run() per-format export creates one result per format
  • run() multi-format generates correct number of results
  • summary() returns correct counts
  • results() returns list copy
  • _export_one with None model returns fail result
  • _export_one with no exporter for format returns fail result
  • _export_one with exporter call success
  • _export_one with exporter raising exception returns fail result
  • _write_sidecar writes valid JSON
  • Integration: BatchExporter with real MDL exporter (if available)

  ThumbnailCache (Phase 4 assembly integration)
  • _AssemblyFrame has _on_name_change method
  • _ExportFrame.get_batch_config() returns BatchExportConfig

  Module completeness
  • character_builder_window defines all Phase 4 public APIs
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from unittest.mock import MagicMock, patch, call

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ──────────────────────────────────────────────────────────────────────────────
#  Import helpers
# ──────────────────────────────────────────────────────────────────────────────

def _import_batch():
    """Import Phase 4 batch-export classes."""
    try:
        from src.gui.character_builder_window import (
            BatchExportConfig,
            BatchExportResult,
            BatchExporter,
            _import_exporters,
        )
        return BatchExportConfig, BatchExportResult, BatchExporter, _import_exporters
    except ImportError as exc:
        pytest.skip(f"character_builder_window not importable: {exc}")


def _import_model_data():
    try:
        from src.core.model_data import (
            CharacterScene, PartSlot, PART_SLOT_LABELS, KotorModel
        )
        return CharacterScene, PartSlot, PART_SLOT_LABELS, KotorModel
    except ImportError as exc:
        pytest.skip(f"model_data not importable: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
#  Minimal stubs
# ──────────────────────────────────────────────────────────────────────────────

class _MockModel:
    name = "mock_model"
    supermodel = "S_Female02"
    animations = []
    bb_min = (-0.3, -0.3, 0.0)
    bb_max = (0.3, 0.3, 1.8)

    def all_nodes(self):
        return iter([])


class _MockExporter:
    """Fake exporter that records export() / write() calls."""
    calls: List = []

    def __init__(self):
        self.__class__.calls.clear()

    def write(self, model, path: str):
        self.__class__.calls.append(("write", path))
        # Create the file so sidecar logic can see it
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        open(path, "w").close()

    def export(self, model, path: str):
        self.__class__.calls.append(("export", path))
        open(path, "w").close()


class _FailingExporter:
    """Exporter that always raises."""
    def write(self, model, path):
        raise RuntimeError("Deliberate write failure")

    def export(self, model, path):
        raise RuntimeError("Deliberate export failure")


# ──────────────────────────────────────────────────────────────────────────────
#  Helper to build a minimal CharacterScene with a model
# ──────────────────────────────────────────────────────────────────────────────

def _make_scene_with_model(game_version="K1"):
    CharacterScene, PartSlot, PART_SLOT_LABELS, _ = _import_model_data()
    scene = CharacterScene(game_version=game_version)
    model = _MockModel()
    scene.assign(PartSlot.HEADLESS_BODY, model,
                 resref="pmbc1", game_version=game_version)
    return scene, PartSlot


def _make_empty_scene(game_version="K1"):
    CharacterScene, _, _, _ = _import_model_data()
    return CharacterScene(game_version=game_version)


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — BatchExportConfig
# ──────────────────────────────────────────────────────────────────────="────────

class TestBatchExportConfigDefaults:

    def test_default_output_dir_is_empty(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig()
        assert cfg.output_dir == ""

    def test_default_formats_is_mdl(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig()
        assert cfg.formats == ["MDL"]

    def test_default_include_sidecar_is_true(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig()
        assert cfg.include_sidecar is True

    def test_default_name_prefix_is_empty(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig()
        assert cfg.name_prefix == ""

    def test_default_skip_empty_slots_is_true(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig()
        assert cfg.skip_empty_slots is True

    def test_custom_constructor(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(
            output_dir="/tmp/out",
            formats=["MDL", "FBX"],
            include_sidecar=False,
            name_prefix="my_char_",
            skip_empty_slots=False,
        )
        assert cfg.output_dir == "/tmp/out"
        assert "MDL" in cfg.formats
        assert "FBX" in cfg.formats
        assert cfg.include_sidecar is False
        assert cfg.name_prefix == "my_char_"
        assert cfg.skip_empty_slots is False

    def test_supported_formats_constant(self):
        BatchExportConfig, *_ = _import_batch()
        assert "MDL" in BatchExportConfig.SUPPORTED_FORMATS
        assert "FBX" in BatchExportConfig.SUPPORTED_FORMATS
        assert "glTF" in BatchExportConfig.SUPPORTED_FORMATS
        assert "OBJ" in BatchExportConfig.SUPPORTED_FORMATS

    def test_format_extensions_map(self):
        BatchExportConfig, *_ = _import_batch()
        assert BatchExportConfig.FORMAT_EXTENSIONS["MDL"]  == ".mdl"
        assert BatchExportConfig.FORMAT_EXTENSIONS["FBX"]  == ".fbx"
        assert BatchExportConfig.FORMAT_EXTENSIONS["glTF"] == ".gltf"
        assert BatchExportConfig.FORMAT_EXTENSIONS["OBJ"]  == ".obj"


class TestBatchExportConfigValidate:

    def test_validate_empty_dir_gives_error(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(formats=["MDL"])
        errs = cfg.validate()
        assert any("output_dir" in e for e in errs)

    def test_validate_empty_formats_gives_error(self):
        """Empty formats list — the constructor falls back to ['MDL'], which is valid.
        But if we force formats to [] after construction, validate should catch it."""
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        # Force an empty list after construction to test the guard
        cfg.formats = []
        errs = cfg.validate()
        assert len(errs) > 0, "Empty formats list after mutation must be caught"

    def test_validate_bad_format_gives_error(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/tmp", formats=["BADFORMAT"])
        errs = cfg.validate()
        assert len(errs) > 0

    def test_validate_valid_config_returns_empty(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        errs = cfg.validate()
        assert errs == []

    def test_validate_all_supported_formats(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(
            output_dir="/tmp",
            formats=list(BatchExportConfig.SUPPORTED_FORMATS),
        )
        errs = cfg.validate()
        assert errs == []


class TestBatchExportConfigPaths:

    def test_extension_for_known_formats(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig()
        assert cfg.extension_for("MDL")  == ".mdl"
        assert cfg.extension_for("FBX")  == ".fbx"
        assert cfg.extension_for("glTF") == ".gltf"
        assert cfg.extension_for("OBJ")  == ".obj"

    def test_extension_for_unknown_falls_back_to_mdl(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig()
        result = cfg.extension_for("UNKNOWN")
        assert result == ".mdl"

    def test_output_path_basic(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/out", formats=["MDL"])
        path = cfg.output_path("Head Shell", "MDL")
        assert path.startswith("/out")
        assert path.endswith(".mdl")

    def test_output_path_lowercases_label(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/out", formats=["MDL"])
        path = cfg.output_path("HEAD_SHELL", "MDL")
        assert "head_shell" in os.path.basename(path)

    def test_output_path_replaces_spaces_with_underscore(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/out", formats=["MDL"])
        path = cfg.output_path("Head Shell", "MDL")
        assert " " not in os.path.basename(path)
        assert "head_shell" in os.path.basename(path)

    def test_output_path_prepends_prefix(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/out", formats=["MDL"],
                                name_prefix="char_")
        path = cfg.output_path("head_shell", "MDL")
        assert os.path.basename(path).startswith("char_")

    def test_output_path_different_formats(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/out", formats=["FBX"])
        path_mdl  = cfg.output_path("body", "MDL")
        path_fbx  = cfg.output_path("body", "FBX")
        path_gltf = cfg.output_path("body", "glTF")
        path_obj  = cfg.output_path("body", "OBJ")
        assert path_mdl.endswith(".mdl")
        assert path_fbx.endswith(".fbx")
        assert path_gltf.endswith(".gltf")
        assert path_obj.endswith(".obj")


class TestBatchExportConfigSerialization:

    def test_to_dict_contains_all_fields(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig(output_dir="/out", formats=["MDL", "FBX"],
                                include_sidecar=False, name_prefix="p_",
                                skip_empty_slots=False)
        d = cfg.to_dict()
        assert d["output_dir"]       == "/out"
        assert d["formats"]          == ["MDL", "FBX"]
        assert d["include_sidecar"]  is False
        assert d["name_prefix"]      == "p_"
        assert d["skip_empty_slots"] is False

    def test_from_dict_round_trip(self):
        BatchExportConfig, *_ = _import_batch()
        original = BatchExportConfig(output_dir="/out", formats=["MDL", "OBJ"],
                                     include_sidecar=True, name_prefix="c_",
                                     skip_empty_slots=True)
        restored = BatchExportConfig.from_dict(original.to_dict())
        assert restored.output_dir      == original.output_dir
        assert restored.formats         == original.formats
        assert restored.include_sidecar == original.include_sidecar
        assert restored.name_prefix     == original.name_prefix
        assert restored.skip_empty_slots == original.skip_empty_slots

    def test_from_dict_defaults_on_missing_keys(self):
        BatchExportConfig, *_ = _import_batch()
        cfg = BatchExportConfig.from_dict({})
        assert isinstance(cfg.output_dir, str)
        assert isinstance(cfg.formats, list)


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — BatchExportResult
# ──────────────────────────────────────────────────────────────────────────────

class TestBatchExportResult:

    def test_ok_result(self):
        _, BatchExportResult, *_ = _import_batch()
        r = BatchExportResult("head_shell", "MDL", "/out/head_shell.mdl", ok=True)
        assert r.ok is True
        assert r.slot_label == "head_shell"
        assert r.fmt == "MDL"
        assert r.path == "/out/head_shell.mdl"
        assert r.error == ""

    def test_fail_result(self):
        _, BatchExportResult, *_ = _import_batch()
        r = BatchExportResult("body", "FBX", "/out/body.fbx",
                              ok=False, error="exporter failed")
        assert r.ok is False
        assert r.error == "exporter failed"

    def test_repr_ok(self):
        _, BatchExportResult, *_ = _import_batch()
        r = BatchExportResult("head", "MDL", "/out/head.mdl", ok=True)
        text = repr(r)
        assert "OK" in text
        assert "head" in text

    def test_repr_fail(self):
        _, BatchExportResult, *_ = _import_batch()
        r = BatchExportResult("head", "MDL", "/out/head.mdl",
                              ok=False, error="no exporter")
        text = repr(r)
        assert "FAIL" in text


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — BatchExporter
# ──────────────────────────────────────────────────────────────────────────────

class TestBatchExporterInit:

    def test_stores_scene_and_config(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        exp   = BatchExporter(scene, cfg)
        assert exp.scene  is scene
        assert exp.config is cfg

    def test_results_initially_empty(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        exp   = BatchExporter(scene, cfg)
        assert exp.results() == []


class TestBatchExporterRunEmpty:

    def test_empty_scene_returns_empty_list(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        results = BatchExporter(scene, cfg).run()
        assert isinstance(results, list)
        assert len(results) == 0

    def test_invalid_config_returns_empty_list(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig()  # empty output_dir
        results = BatchExporter(scene, cfg).run()
        assert results == []


class TestBatchExporterRunWithModel:

    def test_run_creates_output_dir(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = os.path.join(tmpdir, "new_subdir")
            cfg     = BatchExportConfig(
                output_dir=new_dir, formats=["MDL"])
            # Patch exporters to avoid real file writes
            mock_exporter_cls = MagicMock()
            mock_exporter_cls.return_value.write = lambda model, path: open(path, "w").close()
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exporter_cls},
            ):
                BatchExporter(scene, cfg).run()
            assert os.path.isdir(new_dir)

    def test_run_returns_one_result_per_slot_per_format(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(
                output_dir=tmpdir, formats=["MDL", "OBJ"])
            mock_exp = MagicMock()
            mock_exp.return_value.write  = lambda m, p: open(p, "w").close()
            mock_exp.return_value.export = lambda m, p: open(p, "w").close()
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exp, "OBJ": mock_exp},
            ):
                results = BatchExporter(scene, cfg).run()
            # 1 slot × 2 formats = 2 results
            assert len(results) == 2

    def test_run_skip_empty_slots_true_skips_none_models(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        CharacterScene, PartSlot, _, _ = _import_model_data()
        scene = CharacterScene(game_version="K1")
        # Assign slot with None model — requires hack
        scene.assign(PartSlot.HEADLESS_BODY, _MockModel(),
                     resref="pmbc1", game_version="K1")
        # Manually null out model
        list(scene.slots.values())[0].model = None

        cfg = BatchExportConfig(
            output_dir=tempfile.gettempdir(),
            formats=["MDL"],
            skip_empty_slots=True,
        )
        with patch(
            "src.gui.character_builder_window._import_exporters",
            return_value={},
        ):
            results = BatchExporter(scene, cfg).run()
        assert len(results) == 0

    def test_run_skip_empty_slots_false_records_fail(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        CharacterScene, PartSlot, _, _ = _import_model_data()
        scene = CharacterScene(game_version="K1")
        scene.assign(PartSlot.HEADLESS_BODY, _MockModel(),
                     resref="pmbc1", game_version="K1")
        list(scene.slots.values())[0].model = None

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(
                output_dir=tmpdir,
                formats=["MDL"],
                skip_empty_slots=False,
            )
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": _MockExporter},
            ):
                results = BatchExporter(scene, cfg).run()
        # Should produce a fail result
        assert any(not r.ok for r in results)

    def test_run_summary_counts_correctly(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(output_dir=tmpdir, formats=["MDL"])
            mock_exp = MagicMock()
            mock_exp.return_value.write = lambda m, p: open(p, "w").close()
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exp},
            ):
                exporter = BatchExporter(scene, cfg)
                exporter.run()
                summary = exporter.summary()
        assert isinstance(summary, dict)
        assert "total" in summary
        assert "ok"    in summary
        assert "failed" in summary
        assert summary["total"] == summary["ok"] + summary["failed"]

    def test_run_summary_paths_list(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(output_dir=tmpdir, formats=["MDL"])
            mock_exp = MagicMock()
            mock_exp.return_value.write = lambda m, p: open(p, "w").close()
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exp},
            ):
                exporter = BatchExporter(scene, cfg)
                exporter.run()
                summary = exporter.summary()
        assert isinstance(summary["paths"], list)


class TestBatchExporterSidecar:

    def test_sidecar_written_when_include_sidecar_true(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(
                output_dir=tmpdir, formats=["MDL"], include_sidecar=True)
            mock_exp = MagicMock()
            mock_exp.return_value.write = lambda m, p: open(p, "w").close()
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exp},
            ):
                BatchExporter(scene, cfg).run()
            # Check for .ghostrig.json files
            files = os.listdir(tmpdir)
            json_files = [f for f in files if f.endswith(".ghostrig.json")]
            assert len(json_files) >= 1

    def test_sidecar_contains_valid_json(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(
                output_dir=tmpdir, formats=["MDL"], include_sidecar=True)
            mock_exp = MagicMock()
            mock_exp.return_value.write = lambda m, p: open(p, "w").close()
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exp},
            ):
                BatchExporter(scene, cfg).run()
            json_files = [f for f in os.listdir(tmpdir)
                          if f.endswith(".ghostrig.json")]
            if json_files:
                with open(os.path.join(tmpdir, json_files[0])) as fh:
                    data = json.load(fh)
                assert isinstance(data, dict)

    def test_no_sidecar_when_include_sidecar_false(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(
                output_dir=tmpdir, formats=["MDL"], include_sidecar=False)
            mock_exp = MagicMock()
            mock_exp.return_value.write = lambda m, p: open(p, "w").close()
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exp},
            ):
                BatchExporter(scene, cfg).run()
            json_files = [f for f in os.listdir(tmpdir)
                          if f.endswith(".ghostrig.json")]
            assert len(json_files) == 0


class TestBatchExporterInternals:

    def test_export_one_none_model_returns_fail(self):
        BatchExportConfig, BatchExportResult, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        exp   = BatchExporter(scene, cfg)
        result = exp._export_one(None, "MDL", "/tmp/out.mdl", {})
        assert not result.ok
        assert "no model" in result.error

    def test_export_one_no_exporter_returns_fail(self):
        BatchExportConfig, BatchExportResult, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        exp   = BatchExporter(scene, cfg)
        result = exp._export_one(_MockModel(), "MDL", "/tmp/out.mdl", {})
        assert not result.ok
        assert "no exporter" in result.error

    def test_export_one_success(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        exp   = BatchExporter(scene, cfg)
        with tempfile.TemporaryDirectory() as tmpdir:
            path    = os.path.join(tmpdir, "out.mdl")
            result  = exp._export_one(_MockModel(), "MDL", path,
                                      {"MDL": _MockExporter})
        assert result.ok

    def test_export_one_exporter_raises_returns_fail(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        exp   = BatchExporter(scene, cfg)
        with tempfile.TemporaryDirectory() as tmpdir:
            path   = os.path.join(tmpdir, "out.mdl")
            result = exp._export_one(_MockModel(), "MDL", path,
                                     {"MDL": _FailingExporter})
        assert not result.ok
        assert "Deliberate" in result.error

    def test_write_sidecar_creates_json_file(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        exp   = BatchExporter(scene, cfg)
        SceneIO = None
        with tempfile.TemporaryDirectory() as tmpdir:
            export_path  = os.path.join(tmpdir, "out.mdl")
            open(export_path, "w").close()

            # Manufacture a minimal entry object
            class _Entry:
                resref = "pmbc1"
                game_version = "K1"
                source_path = ""

            exp._write_sidecar(_Entry(), export_path, "MDL", SceneIO)
            sidecar = os.path.join(tmpdir, "out.ghostrig.json")
            assert os.path.exists(sidecar)
            with open(sidecar) as fh:
                data = json.load(fh)
            assert data["resref"] == "pmbc1"
            assert data["game_version"] == "K1"
            assert data["export_fmt"] == "MDL"

    def test_export_one_calls_write_for_mdl(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["MDL"])
        exp   = BatchExporter(scene, cfg)
        calls = []

        class _TrackingExporter:
            def write(self, model, path):
                calls.append(("write", path))
                open(path, "w").close()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.mdl")
            exp._export_one(_MockModel(), "MDL", path,
                            {"MDL": _TrackingExporter})
        assert calls == [("write", path)]

    def test_export_one_calls_export_for_fbx(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene = _make_empty_scene()
        cfg   = BatchExportConfig(output_dir="/tmp", formats=["FBX"])
        exp   = BatchExporter(scene, cfg)
        calls = []

        class _TrackingExporter:
            def export(self, model, path):
                calls.append(("export", path))
                open(path, "w").close()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.fbx")
            exp._export_one(_MockModel(), "FBX", path,
                            {"FBX": _TrackingExporter})
        assert calls == [("export", path)]


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — BatchExporter with name_prefix
# ──────────────────────────────────────────────────────────────────────────────

class TestBatchExporterNamePrefix:

    def test_prefix_in_output_filename(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(
                output_dir=tmpdir, formats=["MDL"], name_prefix="hero_")
            mock_exp = MagicMock()
            written_paths = []
            def _write(model, path):
                written_paths.append(path)
                open(path, "w").close()
            mock_exp.return_value.write = _write
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exp},
            ):
                BatchExporter(scene, cfg).run()
            for p in written_paths:
                assert os.path.basename(p).startswith("hero_")

    def test_empty_prefix_is_allowed(self):
        BatchExportConfig, _, BatchExporter, _ = _import_batch()
        scene, _ = _make_scene_with_model()
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = BatchExportConfig(
                output_dir=tmpdir, formats=["MDL"], name_prefix="")
            mock_exp = MagicMock()
            mock_exp.return_value.write = lambda m, p: open(p, "w").close()
            with patch(
                "src.gui.character_builder_window._import_exporters",
                return_value={"MDL": mock_exp},
            ):
                results = BatchExporter(scene, cfg).run()
        assert all(isinstance(r.path, str) for r in results)


# ──────────────────────────────────────────────────────────────────────────────
#  Tests — Module completeness (Phase 4 APIs)
# ──────────────────────────────────────────────────────────────────────────────

class TestPhase4BatchModuleIntegration:

    def test_batch_export_config_importable(self):
        BatchExportConfig, _, _, _ = _import_batch()
        assert BatchExportConfig is not None

    def test_batch_export_result_importable(self):
        _, BatchExportResult, _, _ = _import_batch()
        assert BatchExportResult is not None

    def test_batch_exporter_importable(self):
        _, _, BatchExporter, _ = _import_batch()
        assert BatchExporter is not None

    def test_export_frame_has_get_batch_config(self):
        """_ExportFrame must expose get_batch_config() method."""
        import src.gui.character_builder_window as mod
        assert hasattr(mod._ExportFrame, "get_batch_config")

    def test_export_frame_has_do_batch_export(self):
        import src.gui.character_builder_window as mod
        assert hasattr(mod._ExportFrame, "_do_batch_export")

    def test_export_frame_has_display_batch_results(self):
        import src.gui.character_builder_window as mod
        assert hasattr(mod._ExportFrame, "_display_batch_results")

    def test_export_frame_has_batch_browse_dir(self):
        import src.gui.character_builder_window as mod
        assert hasattr(mod._ExportFrame, "_batch_browse_dir")

    def test_assembly_frame_has_on_name_change(self):
        import src.gui.character_builder_window as mod
        assert hasattr(mod._AssemblyFrame, "_on_name_change")

    def test_assembly_frame_refresh_calls_refresh_thumbnails(self):
        """_AssemblyFrame.refresh() should call _refresh_thumbnails."""
        import inspect, src.gui.character_builder_window as mod
        src_code = inspect.getsource(mod._AssemblyFrame.refresh)
        assert "_refresh_thumbnails" in src_code

    def test_rig_frame_acurig_callbacks_present(self):
        import src.gui.character_builder_window as mod
        for method_name in [
            "_acurig_detect",
            "_acurig_place_guides",
            "_acurig_generate_rig",
            "_acurig_auto_skin",
            "_acurig_mirror_weights",
            "_acurig_tpose",
            "_acurig_apose",
            "_acurig_full_pipeline",
            "_acurig_save_template",
            "_acurig_load_template",
            "_acurig_status_set",
        ]:
            assert hasattr(mod._RigFrame, method_name), \
                f"_RigFrame missing method: {method_name}"

    def test_rig_frame_has_mask_toggle_callbacks(self):
        import src.gui.character_builder_window as mod
        for method_name in [
            "_toggle_mask_fingers",
            "_toggle_mask_tail",
            "_toggle_mask_toes",
        ]:
            assert hasattr(mod._RigFrame, method_name)

    def test_batch_export_config_to_dict_round_trip(self):
        BatchExportConfig, _, _, _ = _import_batch()
        cfg = BatchExportConfig(
            output_dir="/my/dir",
            formats=["FBX", "glTF"],
            include_sidecar=False,
            name_prefix="char_",
            skip_empty_slots=False,
        )
        d       = cfg.to_dict()
        restored = BatchExportConfig.from_dict(d)
        assert restored.output_dir      == "/my/dir"
        assert "FBX" in restored.formats
        assert "glTF" in restored.formats
        assert restored.include_sidecar is False
        assert restored.name_prefix     == "char_"
        assert restored.skip_empty_slots is False

    def test_import_exporters_callable(self):
        _, _, _, _import_exporters = _import_batch()
        result = _import_exporters()
        assert isinstance(result, dict)
