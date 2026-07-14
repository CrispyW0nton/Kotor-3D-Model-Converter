"""MDL writer/readback gates for local animation override export."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.core.animation.animation_engine import (
    SuperModelResolver,
    evaluate_aurora_animation_pose,
)
from src.core.game.kotor_loader import load_model_from_file
from src.core.geometry.model_data import Animation, GameVersion, KotorModel, ModelNode
from src.core.mdl.mdl_writer import MDLBinaryWriter
from src.core.retargeting.aurora_animation_writer import (
    AuroraAnimationInjectionRequest,
    AuroraAnimationWriter,
)
from src.core.validation.animation_roundtrip_validator import (
    quaternion_angular_difference_degrees,
    verify_written_animation_override_roundtrip,
)
from src.core.validation.animation_block_validator import validate_raw_animation_footprint


def _quat_axis(axis: str, degrees: float) -> tuple[float, float, float, float]:
    radians = math.radians(degrees)
    s = math.sin(radians / 2.0)
    c = math.cos(radians / 2.0)
    if axis.upper() == "X":
        return (s, 0.0, 0.0, c)
    if axis.upper() == "Y":
        return (0.0, s, 0.0, c)
    if axis.upper() == "Z":
        return (0.0, 0.0, s, c)
    raise ValueError(axis)


def _assert_quat_close(
    actual: tuple[float, float, float, float],
    expected: tuple[float, float, float, float],
    *,
    degrees: float = 0.01,
) -> None:
    assert quaternion_angular_difference_degrees(actual, expected) <= degrees


def _anim_node(
    name: str,
    *,
    positions: list[list[float]] | None = None,
    orientations: list[list[float]] | None = None,
    times: list[float] | None = None,
) -> ModelNode:
    key_times = times or [0.0]
    controllers = []
    if positions is not None:
        controllers.append(
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": key_times,
                "values": positions,
            }
        )
    if orientations is not None:
        controllers.append(
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": key_times,
                "values": orientations,
            }
        )
    return ModelNode(name=name, controllers=controllers)


def _target_model(*, existing_length: float = 1.0) -> KotorModel:
    root = ModelNode(name="root")
    child = ModelNode(name="child", position=(1.0, 0.0, 0.0), parent=root)
    root.children = [child]
    existing = Animation(
        name="pause1",
        length=existing_length,
        anim_root="root",
        nodes=[_anim_node("root", orientations=[[0.0, 0.0, 0.0, 1.0]])],
    )
    return KotorModel(
        name="synthetic_roundtrip",
        root_node=root,
        animations=[existing],
        game_version=GameVersion.K1,
    )


def _write_target(tmp_path: Path, model: KotorModel) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    mdl_path = tmp_path / "target.mdl"
    MDLBinaryWriter().write_files(model, str(mdl_path))
    return mdl_path


def _request(tmp_path: Path, target_mdl: Path, *, replace_existing: bool = True) -> AuroraAnimationInjectionRequest:
    r3a_path = tmp_path / "clip.json"
    r3a_path.write_text(json.dumps({"frame_count": 1, "target_curves": {}}), encoding="utf-8")
    return AuroraAnimationInjectionRequest(
        r3a_animation_json=r3a_path,
        target_mdl=target_mdl,
        target_mdx=target_mdl.with_suffix(".mdx"),
        animation_slot="pause1",
        output_mdl=tmp_path / "out" / "target.mdl",
        output_manifest=tmp_path / "out" / "manifest.json",
        overwrite_existing=replace_existing,
        verify_roundtrip=True,
    )


def _inject_with_animation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    animation: Animation,
    *,
    model: KotorModel | None = None,
    replace_existing: bool = True,
):
    target_mdl = _write_target(tmp_path, model or _target_model())
    request = _request(tmp_path, target_mdl, replace_existing=replace_existing)
    monkeypatch.setattr(
        AuroraAnimationWriter,
        "build_animation_from_r3a",
        lambda self, **_kwargs: animation,
    )
    result = AuroraAnimationWriter().inject(request)
    return result, request


def _read_animation(mdl_path: Path, slot_name: str = "pause1") -> tuple[KotorModel, Animation]:
    model = load_model_from_file(str(mdl_path), str(mdl_path.with_suffix(".mdx")), GameVersion.K1)
    assert model is not None
    animations = [anim for anim in model.animations if anim.name.lower() == slot_name]
    assert len(animations) == 1
    return model, animations[0]


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_exported_local_override_exists_after_readback(monkeypatch, tmp_path: Path) -> None:
    animation = Animation(
        name="UE_Idle",
        length=1.0,
        anim_root="root",
        nodes=[_anim_node("root", orientations=[[0.0, 0.0, 0.0, 1.0]])],
    )

    result, request = _inject_with_animation(monkeypatch, tmp_path, animation)
    model, readback = _read_animation(request.output_mdl)

    assert result.success is True, result.errors
    assert readback.name == "pause1"
    assert result.animation_slot == "pause1"
    assert [anim.name for anim in model.animations].count("pause1") == 1


def test_orientation_controller_survives_writer_boundary(monkeypatch, tmp_path: Path) -> None:
    animation = Animation(
        name="UE_RootAxes",
        length=1.0,
        anim_root="root",
        nodes=[
            _anim_node(
                "root",
                orientations=[
                    [0.0, 0.0, 0.0, 1.0],
                    list(_quat_axis("X", 90.0)),
                    list(_quat_axis("Y", 90.0)),
                ],
                times=[0.0, 0.5, 1.0],
            )
        ],
    )

    result, request = _inject_with_animation(monkeypatch, tmp_path, animation)
    model, readback = _read_animation(request.output_mdl)

    assert result.success is True, result.errors
    pose_half = evaluate_aurora_animation_pose(model, readback, 0.5)
    pose_end = evaluate_aurora_animation_pose(model, readback, 1.0)
    _assert_quat_close(pose_half.local_transforms_by_node["root"].rotation, _quat_axis("X", 90.0))
    _assert_quat_close(pose_end.local_transforms_by_node["root"].rotation, _quat_axis("Y", 90.0))


def test_position_controller_survives_writer_boundary_as_rest_local_delta(monkeypatch, tmp_path: Path) -> None:
    animation = Animation(
        name="UE_Position",
        length=1.0,
        anim_root="root",
        nodes=[_anim_node("child", positions=[[2.0, 3.0, 4.0]], times=[0.5])],
    )

    result, request = _inject_with_animation(monkeypatch, tmp_path, animation)
    model, readback = _read_animation(request.output_mdl)

    assert result.success is True, result.errors
    pose = evaluate_aurora_animation_pose(model, readback, 0.5)
    readback_child = next(node for node in readback.nodes if node.name == "child")
    position_controller = next(controller for controller in readback_child.controllers if controller["name"] == "position")
    assert position_controller["values"] == [[2.0, 3.0, 4.0]]
    # Child bind position is (1, 0, 0), so Odyssey evaluates the raw key as a
    # delta and produces (3, 3, 4) in parent-local space.
    assert pose.local_transforms_by_node["child"].position == pytest.approx((3.0, 3.0, 4.0))


def test_parent_child_fk_evaluates_after_readback(monkeypatch, tmp_path: Path) -> None:
    animation = Animation(
        name="UE_FK",
        length=1.0,
        anim_root="root",
        nodes=[_anim_node("root", orientations=[list(_quat_axis("Z", 90.0))])],
    )

    result, request = _inject_with_animation(monkeypatch, tmp_path, animation)
    model, readback = _read_animation(request.output_mdl)

    assert result.success is True, result.errors
    pose = evaluate_aurora_animation_pose(model, readback, 0.0)
    assert pose.world_transforms_by_node["child"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)


def test_existing_local_animation_replacement_policy(monkeypatch, tmp_path: Path) -> None:
    replacement = Animation(
        name="UE_Replacement",
        length=2.0,
        anim_root="root",
        nodes=[_anim_node("root", orientations=[list(_quat_axis("X", 45.0))])],
    )

    result, request = _inject_with_animation(monkeypatch, tmp_path / "replace", replacement)
    model, readback = _read_animation(request.output_mdl)

    assert result.success is True, result.errors
    assert [anim.name for anim in model.animations].count("pause1") == 1
    assert readback.length == pytest.approx(2.0)

    denied_result, denied_request = _inject_with_animation(
        monkeypatch,
        tmp_path / "deny",
        replacement,
        replace_existing=False,
    )

    assert denied_result.success is False
    assert "already exists" in denied_result.errors[0]
    assert not denied_request.output_mdl.exists()
    assert not denied_request.output_mdl.with_suffix(".mdx").exists()
    assert not denied_request.output_manifest.exists()


def test_node_hierarchy_and_mdx_are_not_altered(monkeypatch, tmp_path: Path) -> None:
    animation = Animation(
        name="UE_GeometrySafe",
        length=1.0,
        anim_root="root",
        nodes=[_anim_node("root", orientations=[list(_quat_axis("Z", 10.0))])],
    )
    base_model = _target_model()

    result, request = _inject_with_animation(monkeypatch, tmp_path, animation, model=base_model)
    read_model, _readback = _read_animation(request.output_mdl)

    assert result.success is True, result.errors
    assert [node.name for node in base_model.all_nodes()] == [node.name for node in read_model.all_nodes()]
    assert [
        node.parent.name if node.parent is not None else None
        for node in base_model.all_nodes()
    ] == [
        node.parent.name if node.parent is not None else None
        for node in read_model.all_nodes()
    ]
    assert [node.position for node in base_model.all_nodes()] == pytest.approx(
        [node.position for node in read_model.all_nodes()]
    )
    assert request.target_mdx.read_bytes() == request.output_mdl.with_suffix(".mdx").read_bytes()


def test_readback_verifier_accepts_case_normalized_node_names(monkeypatch, tmp_path: Path) -> None:
    import src.core.validation.animation_roundtrip_validator as roundtrip_validator

    original_root = ModelNode(name="PMBAM")
    original_child = ModelNode(name="torsoUpr_g", position=(1.0, 0.0, 0.0), parent=original_root)
    original_root.children = [original_child]
    original = KotorModel(
        name="PMBAM",
        root_node=original_root,
        game_version=GameVersion.K1,
    )

    readback_root = ModelNode(name="pmbam")
    readback_child = ModelNode(name="torsoupr_g", position=(1.0, 0.0, 0.0), parent=readback_root)
    readback_root.children = [readback_child]
    readback = KotorModel(
        name="pmbam",
        root_node=readback_root,
        animations=[
            Animation(
                name="pause1",
                length=1.0,
                anim_root="pmbam",
                nodes=[_anim_node("torsoupr_g", orientations=[list(_quat_axis("Z", 15.0))])],
            )
        ],
        game_version=GameVersion.K1,
    )

    monkeypatch.setattr(roundtrip_validator, "load_model_from_file", lambda *_args, **_kwargs: readback)

    report = verify_written_animation_override_roundtrip(
        original_model=original,
        prepared_animation=Animation(
            name="pause1",
            length=1.0,
            anim_root="PMBAM",
            nodes=[_anim_node("torsoUpr_g", orientations=[list(_quat_axis("Z", 15.0))])],
        ),
        written_mdl_path=tmp_path / "out.mdl",
        written_mdx_path=tmp_path / "out.mdx",
        slot_name="pause1",
        game_version=GameVersion.K1,
    )

    assert report.success is True
    assert any("casing normalized" in warning.message for warning in report.warnings)


def test_post_write_readback_failure_is_reported(monkeypatch, tmp_path: Path) -> None:
    import src.core.validation.animation_roundtrip_validator as roundtrip_validator

    animation = Animation(
        name="UE_CorruptMe",
        length=1.0,
        anim_root="root",
        nodes=[
            _anim_node(
                "root",
                orientations=[[0.0, 0.0, 0.0, 1.0], list(_quat_axis("X", 90.0))],
                times=[0.0, 1.0],
            )
        ],
    )
    real_loader = roundtrip_validator.load_model_from_file

    def corrupting_loader(*args, **kwargs):
        model = real_loader(*args, **kwargs)
        if model is None:
            return None
        anim = next(a for a in model.animations if a.name.lower() == "pause1")
        root = next(node for node in anim.nodes if node.name == "root")
        orient = next(ctrl for ctrl in root.controllers if ctrl["type"] == 20)
        orient["values"][-1] = [0.0, 0.0, 0.0, 1.0]
        return model

    monkeypatch.setattr(roundtrip_validator, "load_model_from_file", corrupting_loader)

    result, request = _inject_with_animation(monkeypatch, tmp_path, animation)

    assert result.success is False
    assert "failed MDL readback verification" in result.errors[0]
    assert "orientation" in result.errors[0] or "rotation" in result.errors[0]
    assert not request.output_mdl.exists()
    assert not request.output_mdl.with_suffix(".mdx").exists()
    assert not request.output_manifest.exists()


def test_animation_only_injection_uses_vanilla_depth_first_node_order() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "kotor_stock" / "k1"
    target_mdl = fixture_dir / "pmbam.mdl"
    target_mdx = fixture_dir / "pmbam.mdx"
    reference_mdl = fixture_dir / "S_Female02.mdl"

    target_model = load_model_from_file(str(target_mdl), str(target_mdx), GameVersion.K1)
    assert target_model is not None
    root_name = target_model.root_node.name
    animation = Animation(
        name="kpmwin1",
        length=10.0666666,
        transition_time=0.25,
        anim_root=root_name,
        nodes=[
            _anim_node(
                root_name,
                orientations=[
                    [0.0, 0.0, 0.0, 1.0],
                    list(_quat_axis("Z", 5.0)),
                ],
                times=[0.0, 10.0666666],
            )
        ],
    )

    writer = MDLBinaryWriter()
    mdl_bytes, mdx_bytes = writer.inject_animation_override_bytes(
        target_model,
        target_mdl.read_bytes(),
        target_mdx.read_bytes(),
        animation,
    )

    assert mdx_bytes == target_mdx.read_bytes()

    candidate = validate_raw_animation_footprint(mdl_bytes, "kpmwin1")
    reference = validate_raw_animation_footprint(
        reference_mdl.read_bytes(),
        "f2a2",
        require_declared_count_match=False,
    )

    assert reference.success is True, reference.issues
    assert reference.depth_first_order_ok is True
    assert candidate.success is True, candidate.issues
    assert candidate.depth_first_order_ok is True
    assert candidate.declared_node_count == 61
    assert candidate.visited_node_count == 61
    assert candidate.node_names == [node.name for node in target_model.all_nodes()]


def test_raw_animation_footprint_validator_rejects_non_depth_first_child_layout() -> None:
    root = ModelNode(name="root")
    child = ModelNode(name="child", parent=root)
    root.children = [child]
    model = KotorModel(
        name="synthetic_order_gate",
        root_node=root,
        animations=[
            Animation(
                name="pause1",
                length=1.0,
                anim_root="root",
                nodes=[_anim_node("root", orientations=[[0.0, 0.0, 0.0, 1.0]])],
            )
        ],
        game_version=GameVersion.K1,
    )
    mdl_bytes, _mdx_bytes = MDLBinaryWriter().write(model)

    anim_table_rel = int.from_bytes(mdl_bytes[100:104], "little")
    anim_rel = int.from_bytes(mdl_bytes[12 + anim_table_rel:16 + anim_table_rel], "little")
    root_rel = int.from_bytes(mdl_bytes[12 + anim_rel + 0x28:12 + anim_rel + 0x2C], "little")
    root_abs = 12 + root_rel
    child_array_rel = int.from_bytes(mdl_bytes[root_abs + 0x2C:root_abs + 0x30], "little")
    child_array_abs = 12 + child_array_rel

    corrupted = bytearray(mdl_bytes)
    corrupted[child_array_abs:child_array_abs + 4] = (root_rel + 128).to_bytes(4, "little")

    report = validate_raw_animation_footprint(bytes(corrupted), "pause1")

    assert report.success is False
    assert report.depth_first_order_ok is False
    assert any("expected immediately after child array" in issue for issue in report.issues)
