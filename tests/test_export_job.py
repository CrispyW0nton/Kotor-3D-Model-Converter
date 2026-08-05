"""Shared ExportJob transaction helper tests."""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.export.export_job import (
    ExportJobContext,
    ExportJobRequest,
    ExportJobStatus,
    ExportOutputSpec,
    run_export_job,
)
from src.core.ports import FileWriterPort
from src.core.validation.validation_bus import (
    ValidationBus,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
    ValidationSubsystem,
)


def _blocking_report(message: str = "blocked") -> ValidationReport:
    return ValidationReport(
        source="test.export",
        issues=[
            ValidationIssue(
                severity=ValidationSeverity.BLOCKING,
                subsystem=ValidationSubsystem.EXPORT,
                code="test.blocking",
                message=message,
            )
        ],
    )


def _request(output: Path, **kwargs) -> ExportJobRequest:
    return ExportJobRequest(
        job_id=kwargs.pop("job_id", "job1"),
        kind=kwargs.pop("kind", "test_export"),
        outputs=kwargs.pop("outputs", [ExportOutputSpec(output, "txt")]),
        **kwargs,
    )


def test_successful_export_writes_staging_then_promotes(tmp_path: Path) -> None:
    final = tmp_path / "out" / "test.txt"
    seen_staged: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        staged = context.staged_path_for(final)
        assert not final.exists()
        assert isinstance(context, FileWriterPort)
        context.write_text(final, "hello", encoding="utf-8")
        seen_staged.append(staged)

    result = run_export_job(_request(final), writer=writer)

    assert result.succeeded is True
    assert result.status == ExportJobStatus.SUCCEEDED
    assert final.read_text(encoding="utf-8") == "hello"
    assert seen_staged and not seen_staged[0].parent.exists()


def test_export_context_file_writer_port_writes_bytes_to_staging(tmp_path: Path) -> None:
    final = tmp_path / "out" / "payload.bin"
    seen_staged: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        assert isinstance(context, FileWriterPort)
        staged = context.staged_path_for(final)
        context.write_bytes(final, b"payload")
        seen_staged.append(staged)
        assert staged.exists()
        assert final.exists() is False

    result = run_export_job(_request(final), writer=writer)

    assert result.succeeded is True
    assert final.read_bytes() == b"payload"
    assert seen_staged and not seen_staged[0].parent.exists()


def test_preflight_blocking_report_prevents_writer_call(tmp_path: Path) -> None:
    final = tmp_path / "blocked.txt"
    called = False
    request = _request(final, preflight_report=_blocking_report())

    def writer(_context: ExportJobContext) -> None:
        nonlocal called
        called = True

    result = run_export_job(request, writer=writer)

    assert result.status == ExportJobStatus.PREFLIGHT_FAILED
    assert called is False
    assert not final.exists()


def test_overwrite_false_blocks_existing_output_before_writer(tmp_path: Path) -> None:
    final = tmp_path / "exists.txt"
    final.write_text("original", encoding="utf-8")
    called = False

    def writer(_context: ExportJobContext) -> None:
        nonlocal called
        called = True

    result = run_export_job(_request(final, overwrite=False), writer=writer)

    assert result.status == ExportJobStatus.PREFLIGHT_FAILED
    assert called is False
    assert final.read_text(encoding="utf-8") == "original"
    assert any(issue.code == "export.output.exists" for issue in result.validation_report.issues)


def test_verifier_failure_prevents_promotion(tmp_path: Path) -> None:
    final = tmp_path / "verified.txt"

    def writer(context: ExportJobContext) -> None:
        context.staged_path_for(final).write_text("staged", encoding="utf-8")

    result = run_export_job(
        _request(final),
        writer=writer,
        verifier=lambda _context: _blocking_report("verification failed"),
    )

    assert result.status == ExportJobStatus.FAILED
    assert not final.exists()
    assert any("verification failed" in issue.message for issue in result.validation_report.issues)


def test_writer_exception_cleans_staging(tmp_path: Path) -> None:
    final = tmp_path / "boom.txt"
    staged_parent: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        staged = context.staged_path_for(final)
        staged.write_text("partial", encoding="utf-8")
        staged_parent.append(staged.parent)
        raise RuntimeError("boom")

    result = run_export_job(_request(final), writer=writer)

    assert result.status == ExportJobStatus.FAILED
    assert not final.exists()
    assert staged_parent and not staged_parent[0].exists()
    assert any("boom" in issue.message for issue in result.validation_report.issues)


def test_duplicate_final_output_paths_fail_preflight(tmp_path: Path) -> None:
    final = tmp_path / "dup.txt"
    called = False

    def writer(_context: ExportJobContext) -> None:
        nonlocal called
        called = True

    request = _request(
        final,
        outputs=[
            ExportOutputSpec(final, "txt"),
            ExportOutputSpec(final, "txt-copy"),
        ],
    )
    result = run_export_job(request, writer=writer)

    assert result.status == ExportJobStatus.PREFLIGHT_FAILED
    assert called is False
    assert any(issue.code == "export.output.duplicate" for issue in result.validation_report.issues)


def test_validation_bus_receives_reports(tmp_path: Path) -> None:
    final = tmp_path / "bus.txt"
    bus = ValidationBus()
    request = _request(
        final,
        preflight_report=_blocking_report("bus failure"),
        validation_bus_source="export.job.test",
    )

    run_export_job(request, writer=lambda _context: None, validation_bus=bus)

    snapshot = bus.snapshot()
    assert any(issue.source == "export.job.test" for issue in snapshot.issues)
    assert any("bus failure" in issue.message for issue in snapshot.issues)


def test_non_serializable_metadata_fails_preflight(tmp_path: Path) -> None:
    final = tmp_path / "bad.txt"
    called = False

    def writer(_context: ExportJobContext) -> None:
        nonlocal called
        called = True

    result = run_export_job(_request(final, metadata={"bad": b"bytes"}), writer=writer)

    assert result.status == ExportJobStatus.PREFLIGHT_FAILED
    assert called is False
    assert any("non-JSON-serializable" in issue.message for issue in result.validation_report.issues)


def test_multi_directory_outputs_stage_and_promote_together(tmp_path: Path) -> None:
    out_a = tmp_path / "a" / "one.txt"
    out_b = tmp_path / "b" / "two.txt"
    seen_staging_dirs: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        context.write_text(out_a, "one", encoding="utf-8")
        context.write_text(out_b, "two", encoding="utf-8")
        staged_a = context.staged_path_for(out_a)
        staged_b = context.staged_path_for(out_b)
        assert staged_a.exists()
        assert staged_b.exists()
        assert staged_a.parent != staged_b.parent
        assert not out_a.exists()
        assert not out_b.exists()
        seen_staging_dirs.extend([staged_a.parent, staged_b.parent])

    result = run_export_job(
        _request(
            out_a,
            outputs=[
                ExportOutputSpec(out_a, "txt"),
                ExportOutputSpec(out_b, "txt"),
            ],
        ),
        writer=writer,
    )

    assert result.status == ExportJobStatus.SUCCEEDED
    assert out_a.read_text(encoding="utf-8") == "one"
    assert out_b.read_text(encoding="utf-8") == "two"
    assert Path(result.staged_paths[str(out_a)]).name == "one.txt"
    assert Path(result.staged_paths[str(out_b)]).name == "two.txt"
    assert seen_staging_dirs and all(not path.exists() for path in seen_staging_dirs)


def test_multi_directory_staging_does_not_repeat_long_absolute_paths(tmp_path: Path) -> None:
    output_root = tmp_path / ("user_selected_map_studio_package_" + ("x" * 64))
    module = output_root / "install" / "Modules" / "grstyles.mod"
    room = output_root / "source" / "resources" / "grstylesr001.mdl"
    seen_staged: list[Path] = []

    def writer(context: ExportJobContext) -> None:
        seen_staged.extend((context.staged_path_for(module), context.staged_path_for(room)))
        context.write_bytes(module, b"mod")
        context.write_bytes(room, b"mdl")

    result = run_export_job(
        _request(
            module,
            job_id="map_studio.custom_module_package.grstyles.with_a_long_descriptive_job_name",
            outputs=(
                ExportOutputSpec(module, "module_package"),
                ExportOutputSpec(room, "loose_resource"),
            ),
        ),
        writer=writer,
    )

    assert result.succeeded is True
    assert module.read_bytes() == b"mod"
    assert room.read_bytes() == b"mdl"
    assert seen_staged
    assert all(str(output_root.resolve()).lower() not in path.parent.name.lower() for path in seen_staged)


def test_manifest_writer_output_is_promoted(tmp_path: Path) -> None:
    final = tmp_path / "payload.txt"
    manifest = tmp_path / "payload.manifest.json"

    def writer(context: ExportJobContext) -> None:
        context.staged_path_for(final).write_text("payload", encoding="utf-8")

    def manifest_writer(context: ExportJobContext, result) -> Path:
        staged_manifest = context.staged_path_for(manifest)
        context.write_text(
            manifest,
            json.dumps({"job_id": result.job_id, "kind": result.kind}),
            encoding="utf-8",
        )
        return staged_manifest

    result = run_export_job(
        _request(
            final,
            outputs=[
                ExportOutputSpec(final, "txt"),
                ExportOutputSpec(manifest, "manifest"),
            ],
        ),
        writer=writer,
        manifest_writer=manifest_writer,
    )

    assert result.succeeded is True
    assert result.manifest_path == manifest
    assert manifest.exists()
    assert json.loads(manifest.read_text(encoding="utf-8"))["job_id"] == "job1"


def _selected_export_triangle_model(name: str, texture: str):
    from src.core.geometry.model_data import KotorModel, ModelNode, NodeFlags

    mesh = ModelNode(
        name=f"{name}_mesh",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(math.sqrt(0.5), math.sqrt(0.5), 0.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[(0.1, 0.2), (0.8, 0.2), (0.1, 0.9)],
        faces=[(0, 1, 2)],
        face_mats=[0],
        texture=texture,
        texture_names=[texture],
        tex_count=1,
    )
    return KotorModel(name=name, classification="tile", root_node=mesh)


def test_selected_fbx_merge_bakes_transforms_and_preserves_material_uv_channels() -> None:
    from src.io.fbx.fbx_exporter import merge_selected_scene_objects

    first = _selected_export_triangle_model("first", "stone")
    first.root_node.position = (1.0, 0.0, 0.0)
    second = _selected_export_triangle_model("second", "sky")
    objects = [
        SimpleNamespace(
            name="First Room",
            metadata={"_runtime_model": first},
            transform=SimpleNamespace(
                position=(10.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0),
                scale=(2.0, 1.0, 1.0),
            ),
        ),
        SimpleNamespace(
            name="Skybox",
            metadata={"_runtime_model": second},
            transform=SimpleNamespace(
                position=(0.0, 5.0, 0.0),
                rotation=(0.0, 0.0, 90.0),
                scale=(1.0, 2.0, 1.0),
            ),
        ),
    ]

    merged = merge_selected_scene_objects(objects, name="module_selection")
    mesh = merged.root_node

    assert mesh is not None
    assert merged.name == "module_selection"
    assert len(merged.mesh_nodes()) == 1
    assert len(mesh.faces) == 2
    assert len(mesh.vertices) == 6
    expected_vertices = [
        (12.0, 0.0, 0.0),
        (14.0, 0.0, 0.0),
        (12.0, 1.0, 0.0),
        (0.0, 5.0, 0.0),
        (0.0, 6.0, 0.0),
        (-2.0, 5.0, 0.0),
    ]
    for actual, expected in zip(mesh.vertices, expected_vertices):
        assert actual == pytest.approx(expected)
    assert mesh.normals[0] == pytest.approx((math.sqrt(0.2), math.sqrt(0.8), 0.0))
    assert mesh.normals[3] == pytest.approx((-math.sqrt(0.2), math.sqrt(0.8), 0.0))
    assert mesh.uvs == first.root_node.uvs + second.root_node.uvs
    assert mesh.uvs_lm == first.root_node.uvs_lm + second.root_node.uvs_lm
    assert mesh.face_mats == [0, 1]
    assert [slot.texture for slot in mesh._gr_fbx_material_slots] == ["stone", "sky"]


def test_builtin_ascii_fbx_exports_selected_objects_as_one_multimaterial_mesh(
    tmp_path: Path,
) -> None:
    from src.converters.mesh_converter import FBXExporter
    from src.io.fbx.fbx_exporter import merge_selected_scene_objects

    selected = [
        SimpleNamespace(
            name=f"Room {index + 1}",
            metadata={
                "_runtime_model": _selected_export_triangle_model(
                    f"room_{index}",
                    texture,
                )
            },
            transform=SimpleNamespace(
                position=(float(index) * 2.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0),
                scale=(1.0, 1.0, 1.0),
            ),
        )
        for index, texture in enumerate(("stone", "sky"))
    ]
    merged = merge_selected_scene_objects(selected)
    output = tmp_path / "selection.fbx"

    assert FBXExporter().export(
        merged,
        str(output),
        export_rigging=False,
        export_manifest=False,
        force_ascii=True,
    )

    text = output.read_text(encoding="utf-8")
    assert text.count("\tGeometry:") == 1
    assert text.count("\tMaterial:") == 2
    assert 'MappingInformationType: "ByPolygon"' in text
    assert "Materials: *2" in text
    assert "\t\t\t\ta: 0,1" in text


def test_export_selected_module_routes_marquee_selection_to_one_mesh_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.gui.windows.application_core.shared import model_io

    room = SimpleNamespace(
        id="room-id",
        name="m14aa_01c",
        metadata={"module_group": {"module_root": "m14aa_01"}},
    )
    sky = SimpleNamespace(
        id="sky-id",
        name="m14aa_01h",
        metadata={"module_group": {"module_root": "m14aa_01"}},
    )
    captured: dict[str, object] = {}
    output = tmp_path / "module_selection.fbx"

    class _Harness(model_io.ModelIoMixin):
        scene_manager = SimpleNamespace(
            active_scene=SimpleNamespace(objects=[room, sky]),
            get_selected_objects=lambda: [sky],
        )
        viewport = SimpleNamespace(
            _selected_viewport_nodes=[
                SimpleNamespace(_gr_scene_object_id="room-id"),
                SimpleNamespace(_gr_scene_object_id="sky-id"),
            ]
        )
        settings_data = {"fbx_sdk": {}}

        def _get_tex_cache_for_export(self):
            return "texture-cache"

        def _run_io_async(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

        def _log(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(
        model_io.QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(output), "Standard FBX (*.fbx)"),
    )

    _Harness()._export_selected_fbx()

    args = captured["args"]
    kwargs = captured["kwargs"]
    assert args[1] is model_io._work_export_selected_fbx
    assert args[2] == [room, sky]
    assert args[3] == str(output)
    assert kwargs["tex_cache"] == "texture-cache"


def test_export_selected_single_static_room_routes_to_one_mesh_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.gui.windows.application_core.shared import model_io

    runtime_model = SimpleNamespace(name="m14aa_01g")
    room = SimpleNamespace(
        id="room-id",
        name="m14aa_01g",
        metadata={"_runtime_model": runtime_model},
    )
    captured: dict[str, object] = {}
    output = tmp_path / "m14aa_01g.fbx"

    class _Harness(model_io.ModelIoMixin):
        scene_manager = SimpleNamespace(
            active_scene=SimpleNamespace(objects=[room]),
            get_selected_objects=lambda: [room],
        )
        viewport = SimpleNamespace(
            _selected_viewport_nodes=[
                SimpleNamespace(_gr_scene_object_id="room-id"),
            ]
        )
        settings_data = {"fbx_sdk": {}}

        def _get_tex_cache_for_export(self):
            return "texture-cache"

        def _runtime_model_for_scene_object(self, _item):
            return runtime_model

        def _fbx_base_skeleton_for_export(self, _model):
            return None

        def _fbx_supplemental_animation_models(self, _model):
            return ()

        def _choose_fbx_animation_sets(self, *_args, **_kwargs):
            return ()

        def _fbx_resource_context_for_export(self, _model):
            return None, None

        def _run_io_async(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

        def _log(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(
        model_io.QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(output), "Standard FBX (*.fbx)"),
    )

    _Harness()._export_selected_fbx()

    args = captured["args"]
    kwargs = captured["kwargs"]
    assert args[1] is model_io._work_export_selected_fbx
    assert args[2] == [room]
    assert args[3] == str(output)
    assert kwargs["tex_cache"] == "texture-cache"


def test_full_module_export_resolves_every_object_in_selected_module_group() -> None:
    from src.gui.windows.application_core.shared import model_io

    module_objects = [
        SimpleNamespace(
            id=f"room-{suffix}",
            name=f"m14aa_01{suffix}",
            metadata={"module_group": {"module_root": "m14aa_01"}},
        )
        for suffix in "abcdefghi"
    ]
    unrelated = SimpleNamespace(
        id="other-room",
        name="m13aa_01a",
        metadata={"module_group": {"module_root": "m13aa_01"}},
    )
    scene_manager = SimpleNamespace(
        active_scene=SimpleNamespace(objects=[*module_objects, unrelated]),
        get_selected_objects=lambda: [module_objects[6]],
    )
    viewport = SimpleNamespace(
        _selected_viewport_nodes=[
            SimpleNamespace(_gr_scene_object_id=module_objects[6].id),
        ]
    )

    resolved = model_io._module_group_scene_objects_for_export(
        scene_manager,
        viewport,
    )

    assert resolved == module_objects


def test_export_full_module_routes_all_group_objects_to_one_mesh_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.gui.windows.application_core.shared import model_io

    module_objects = [
        SimpleNamespace(
            id=f"room-{suffix}",
            name=f"m14aa_01{suffix}",
            metadata={
                "module_group": {"module_root": "m14aa_01"},
                "_runtime_model": SimpleNamespace(name=f"m14aa_01{suffix}"),
            },
        )
        for suffix in "abcdefghi"
    ]
    output = tmp_path / "m14aa_01_full.fbx"
    captured: dict[str, object] = {}

    class _Harness(model_io.ModelIoMixin):
        scene_manager = SimpleNamespace(
            active_scene=SimpleNamespace(objects=module_objects),
            get_selected_objects=lambda: [module_objects[6]],
        )
        viewport = SimpleNamespace(
            _selected_viewport_nodes=[
                SimpleNamespace(_gr_scene_object_id=module_objects[6].id),
            ]
        )

        def _get_tex_cache_for_export(self):
            return "texture-cache"

        def _run_io_async(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

        def _log(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(
        model_io.QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(output), "Standard FBX (*.fbx)"),
    )

    _Harness()._export_full_module_fbx()

    args = captured["args"]
    kwargs = captured["kwargs"]
    assert args[1] is model_io._work_export_selected_fbx
    assert args[2] == module_objects
    assert args[3] == str(output)
    assert kwargs["tex_cache"] == "texture-cache"
