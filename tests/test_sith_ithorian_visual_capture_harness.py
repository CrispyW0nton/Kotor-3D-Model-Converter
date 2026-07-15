from __future__ import annotations

import json
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from scripts import verify_sith_ithorian_all_animations as proof


def _write_row(path: Path, color: str = "#304050") -> None:
    columns = len(proof.SAMPLE_FRACTIONS) * len(proof.VIEW_SPECS)
    width = proof.LABEL_WIDTH + proof.CELL_GAP + columns * (proof.CELL_WIDTH + proof.CELL_GAP)
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (width, proof.ROW_HEIGHT), color)
    image.save(path, "JPEG")
    image.close()


def _write_verified_capture_metadata(
    output: Path,
    completed_names: list[str],
) -> dict[str, dict]:
    source = output / "captured_sources"
    source.mkdir(parents=True, exist_ok=True)
    model_files: dict[str, list[Path]] = {}
    for model in proof.DEFAULT_MODELS:
        model_files[model] = [source / f"{model}.mdl", source / f"{model}.mdx"]
        for index, path in enumerate(model_files[model]):
            path.write_bytes(f"{model}:{index}".encode("ascii"))
    renderer_files = [source / "GhostStudio.exe", source / "GhostRigger.Core.Rendering.dll"]
    for index, path in enumerate(renderer_files):
        path.write_bytes(f"renderer:{index}".encode("ascii"))
    build_files = [
        path
        for model in proof.DEFAULT_MODELS
        for path in model_files[model]
    ] + renderer_files
    build_hash = proof._hash_files(build_files)

    identities = {
        model: {
            "identity_verified": True,
            "model_hash": proof._hash_files(paths),
            "model_files": [str(path.resolve()) for path in paths],
            "build_hash": build_hash,
            "build_files": [str(path.resolve()) for path in build_files],
        }
        for model, paths in model_files.items()
    }
    captures = {}
    progress = None
    progress_path = None
    for model in proof.DEFAULT_MODELS:
        _rows, progress_path, progress, model_progress, _completed = proof._prepare_capture_output(
            output,
            model,
            resume=False,
            identity=identities[model],
        )
        captures[model] = model_progress
    assert progress is not None and progress_path is not None
    for model, model_progress in captures.items():
        model_progress["completed"] = list(completed_names)
        model_progress["inventory_count"] = len(completed_names)
        progress["models"][model] = model_progress
    proof._write_json(progress_path, progress)
    return identities


def test_nonresume_capture_resets_only_selected_model_and_derived_proof(tmp_path: Path) -> None:
    output = tmp_path / "proof"
    _write_row(output / "rows" / "c_ithlord" / "001_old.jpg")
    _write_row(output / "rows" / "c_ithlord" / "002_old.jpg")
    _write_row(output / "rows" / "c_ithschol" / "001_keep.jpg")
    _write_row(output / "strips" / "001_old.jpg")
    _write_row(output / "atlas" / "page_001.jpg")
    (output / "manifest.json").write_text("{}", encoding="utf-8")
    (output / "index.html").write_text("stale", encoding="utf-8")
    (output / "progress.json").write_text(
        json.dumps(
            {
                "version": 1,
                "models": {
                    "c_ithlord": {"completed": ["old_a", "old_b"]},
                    "c_ithschol": {"completed": ["keep"]},
                },
            }
        ),
        encoding="utf-8",
    )

    rows_dir, progress_path, _progress, model_progress, completed = proof._prepare_capture_output(
        output,
        "c_ithlord",
        resume=False,
    )

    assert list(rows_dir.glob("*.jpg")) == []
    assert (output / "rows" / "c_ithschol" / "001_keep.jpg").is_file()
    assert list((output / "strips").glob("*.jpg")) == []
    assert list((output / "atlas").glob("*.jpg")) == []
    assert not (output / "manifest.json").exists()
    assert not (output / "index.html").exists()
    assert completed == set()
    assert model_progress["completed"] == []
    persisted = json.loads(progress_path.read_text(encoding="utf-8"))
    assert persisted["models"]["c_ithlord"]["completed"] == []
    assert persisted["models"]["c_ithschol"]["completed"] == ["keep"]


class _FakeAction:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def isEnabled(self) -> bool:
        return self.enabled

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)


class _FakeWidget:
    def __init__(self, title: str, visible: bool = True) -> None:
        self.title = title
        self.visible = visible

    def windowTitle(self) -> str:
        return self.title

    def isVisible(self) -> bool:
        return self.visible


class _FakeApp:
    def __init__(self, widgets=()) -> None:
        self.widgets = list(widgets)

    def topLevelWidgets(self):
        return list(self.widgets)


def test_map_studio_capture_guard_disables_action_and_restores_it() -> None:
    action = _FakeAction(enabled=True)
    window = SimpleNamespace(module_editor_window=None, modules_action=action)
    app = _FakeApp()

    restore = proof._begin_map_studio_capture_guard(window, app)
    assert action.enabled is False
    restore()
    restore()
    assert action.enabled is True

    window.module_editor_window = object()
    with pytest.raises(RuntimeError, match="restart the Debug app"):
        proof._begin_map_studio_capture_guard(window, app)

    window.module_editor_window = None
    app.widgets.append(_FakeWidget("Ghost-Studio Map Studio - Level Editor"))
    with pytest.raises(RuntimeError, match="Map Studio must be closed"):
        proof._begin_map_studio_capture_guard(window, app)


def test_exact_compose_requires_sequential_matching_rows_and_clears_stale_outputs(tmp_path: Path) -> None:
    output = tmp_path / "proof"
    _write_verified_capture_metadata(output, ["alpha", "beta"])
    for model, color in (("c_ithlord", "#443322"), ("c_ithschol", "#334422")):
        _write_row(output / "rows" / model / "001_alpha.jpg", color)
        _write_row(output / "rows" / model / "002_beta.jpg", color)
    _write_row(output / "strips" / "999_stale.jpg")
    _write_row(output / "atlas" / "page_999.jpg")

    manifest = proof.compose_proof(
        output,
        expected_animation_count=2,
        strips_per_page=1,
    )

    assert manifest["animation_count"] == 2
    assert manifest["exact_count_verified"] is True
    assert manifest["integrity"] == {
        "source_rows_per_model": 2,
        "paired_strips": 2,
        "atlas_pages": 2,
        "html_entries": 2,
    }
    assert not (output / "strips" / "999_stale.jpg").exists()
    assert not (output / "atlas" / "page_999.jpg").exists()

    _write_row(output / "rows" / "c_ithschol" / "003_extra.jpg")
    with pytest.raises(RuntimeError, match="expected exactly 2 proof rows"):
        proof.compose_proof(output, expected_animation_count=2)


def test_exact_compose_rejects_mixed_capture_generations(tmp_path: Path) -> None:
    output = tmp_path / "proof"
    identities = _write_verified_capture_metadata(output, ["alpha", "beta"])
    for model in proof.DEFAULT_MODELS:
        _write_row(output / "rows" / model / "001_alpha.jpg")
        _write_row(output / "rows" / model / "002_beta.jpg")

    progress_path = output / "progress.json"
    before = json.loads(progress_path.read_text(encoding="utf-8"))
    old_generation = before["active_capture_generation"]["id"]
    _rows, _path, progress, lord_progress, _completed = proof._prepare_capture_output(
        output,
        "c_ithlord",
        resume=False,
        identity=identities["c_ithlord"],
    )
    new_generation = progress["active_capture_generation"]["id"]
    assert new_generation != old_generation
    lord_progress["completed"] = ["alpha", "beta"]
    lord_progress["inventory_count"] = 2
    proof._write_json(progress_path, progress)
    _write_row(output / "rows" / "c_ithlord" / "001_alpha.jpg")
    _write_row(output / "rows" / "c_ithlord" / "002_beta.jpg")

    with pytest.raises(RuntimeError, match="capture generation"):
        proof.compose_proof(output, expected_animation_count=2)


def test_exact_compose_rejects_corrupt_or_wrong_size_rows(tmp_path: Path) -> None:
    output = tmp_path / "proof"
    _write_verified_capture_metadata(output, ["alpha"])
    for model in proof.DEFAULT_MODELS:
        _write_row(output / "rows" / model / "001_alpha.jpg")
    wrong = output / "rows" / "c_ithschol" / "001_alpha.jpg"
    Image.new("RGB", (20, 20), "#111111").save(wrong, "JPEG")

    with pytest.raises(RuntimeError, match="has size"):
        proof.compose_proof(output, expected_animation_count=1)

    _write_row(wrong)
    wrong.write_bytes(b"not a jpeg")
    with pytest.raises(RuntimeError, match="unreadable proof row"):
        proof.compose_proof(output, expected_animation_count=1)


def test_pending_resume_rows_invalidate_all_derived_output(tmp_path: Path) -> None:
    output = tmp_path / "proof"
    _write_row(output / "strips" / "001_old.jpg")
    _write_row(output / "atlas" / "page_001.jpg")
    (output / "manifest.json").write_text("{}", encoding="utf-8")
    (output / "index.html").write_text("stale", encoding="utf-8")

    assert proof._invalidate_derived_if_rows_pending(
        output,
        [output / "rows" / "c_ithlord" / "002_missing.jpg"],
    ) is True
    assert list((output / "strips").glob("*.jpg")) == []
    assert list((output / "atlas").glob("*.jpg")) == []
    assert not (output / "manifest.json").exists()
    assert not (output / "index.html").exists()


def test_targeted_compose_inventory_keeps_filename_intersection_behavior(tmp_path: Path) -> None:
    output = tmp_path / "proof"
    _write_row(output / "rows" / "c_ithlord" / "021_c2a1.jpg")
    _write_row(output / "rows" / "c_ithlord" / "027_c2d1.jpg")
    _write_row(output / "rows" / "c_ithschol" / "027_c2d1.jpg")

    assert proof._inventory_from_rows(output, proof.DEFAULT_MODELS) == ["027_c2d1.jpg"]


def test_set2_acceptance_contract_uses_true_endpoints_and_fail_closed_gates() -> None:
    source = Path(proof.__file__).read_text(encoding="utf-8")

    assert proof.SAMPLE_FRACTIONS == (0.0, 0.20, 0.40, 0.60, 0.80, 1.0)
    assert proof.VIEW_SPECS == (("front", 90.0), ("right", 0.0))
    assert 'clips = ("c2d1", "c2d2", "c2d3", "c2d4", "c2d5")' in source
    assert "not math.isclose(exact_fraction, 0.8015" in source
    assert "process_identity = _assert_fresh_debug_process(identity)" in source
    assert "EnumProcessModules" in source
    assert "GetModuleFileNameW" in source
    assert "import psutil" not in source
    assert 'require_moderngl=True' in source
    assert 'f"w_lghtsbr_002.{extension}"' in source
    assert 'prefer_base_archive=True' in source
    assert "loaded_model_bytes != deployed_model_bytes" in source
    assert "animation has an invalid playback length" in source
    assert "_assert_rendered_sample(" in source
    acceptance_source = inspect.getsource(proof.capture_set2_acceptance_current)
    assert "for model_name in (resref,)" in acceptance_source
    assert "for model_name in DEFAULT_MODELS" not in acceptance_source
    assert "process_image = _current_process_image()" in acceptance_source
    assert 'sync_body_engine = getattr(window, "_sync_bas_body_animation_engine", None)' in acceptance_source
    assert acceptance_source.count("sync_body_engine(preview)") == 2


def test_lorum_set4_acceptance_captures_every_assigned_and_dialogue_slot() -> None:
    remaps = proof.LORUM_SET4_PAYLOAD_REMAPS
    expected = {
        *remaps.keys(),
        *remaps.values(),
        *proof.LORUM_SET4_RUNTIME_ALIASES,
        *proof.LORUM_NATIVE_DIALOGUE_CLIPS,
    }

    assert len(remaps) == 41
    assert len(set(remaps.values())) == 41
    assert set(proof.LORUM_SET4_RUNTIME_ALIASES) == {
        "g0a1", "g0a2", "creadyr",
    }
    assert set(proof.LORUM_NATIVE_DIALOGUE_CLIPS) == {
        "cpause1", "cpause2", "tlknorm", "listen",
    }
    assert len(proof.LORUM_SET4_VISUAL_CLIPS) == 89
    assert set(proof.LORUM_SET4_VISUAL_CLIPS) == expected

    setup_source = inspect.getsource(
        proof._prepare_sith_ithorian_acceptance_current
    )
    capture_source = inspect.getsource(
        proof.capture_lorum_set4_acceptance_current
    )
    assert "for model_name in (resref,)" in setup_source
    assert "package_models=(resref,)" in setup_source
    assert 'prefer_base_archive=True' in setup_source
    assert "process_identity = _assert_fresh_debug_process(identity)" in setup_source
    assert 'sync_body_engine = getattr(window, "_sync_bas_body_animation_engine", None)' in setup_source
    assert "_prepare_sith_ithorian_acceptance_current(" in capture_source
    assert "only=LORUM_SET4_VISUAL_CLIPS" in capture_source
    assert "resume=False" in capture_source
    assert "reframe_each_sample=True" in capture_source
    assert "require_moderngl=True" in capture_source
    assert "identity_models=(resref,)" in capture_source


def test_force_visible_render_propagates_renderer_failure() -> None:
    class FailingViewport:
        def _request_render(self, **_kwargs) -> None:
            return None

        def _render_now(self) -> None:
            raise ValueError("synthetic render failure")

    class FakeApp:
        def processEvents(self) -> None:
            return None

    with pytest.raises(RuntimeError, match="visible render failed.*synthetic render failure"):
        proof._force_visible_render(FailingViewport(), FakeApp(), "test frame")


def test_force_visible_render_rejects_internally_swallowed_gpu_failure() -> None:
    class FakePixmap:
        def isNull(self) -> bool:
            return False

        def cacheKey(self) -> int:
            return 2

    class FakeCanvas:
        def text(self) -> str:
            return "GPU render unavailable\nsynthetic model"

        def width(self) -> int:
            return 640

        def height(self) -> int:
            return 480

    class SwallowingViewport:
        def __init__(self) -> None:
            self._last_render_wall = 0.0
            self._pixmap = None
            self._last_rendered_canvas_size = (0, 0)
            self.canvas = FakeCanvas()

        def _request_render(self, **_kwargs) -> None:
            return None

        def _render_now(self) -> None:
            # Mirrors the production catch path: no exception escapes, but the
            # canvas is replaced by the diagnostic fallback.
            self._last_render_wall = 1.0
            self._pixmap = FakePixmap()

    class FakeApp:
        def processEvents(self) -> None:
            return None

    with pytest.raises(RuntimeError, match="GPU render unavailable"):
        proof._force_visible_render(
            SwallowingViewport(),
            FakeApp(),
            "swallowed failure",
        )


def test_moderngl_renderer_gate_rejects_backend_fallback() -> None:
    active = SimpleNamespace(name="WGPU")
    renderer = SimpleNamespace(
        backend_id="wgpu_d3d12",
        active_renderer=active,
        get_diagnostics=lambda: {
            "backend_id": "wgpu_d3d12",
            "name": "WGPU",
            "available": True,
        },
    )
    viewport = SimpleNamespace(_gpu_renderer=renderer)

    with pytest.raises(RuntimeError, match="requires the ModernGL renderer"):
        proof._require_moderngl_renderer(viewport)
