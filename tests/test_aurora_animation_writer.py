"""Tests for Sprint 3 R3.B Aurora animation injection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.animation.animation_engine import SuperModelResolver
from src.core.game.kotor_loader import load_model_from_file
from src.core.geometry.model_data import Animation, KotorModel
from src.core.retargeting.aurora_animation_writer import (
    CTRL_ORIENTATION,
    CTRL_POSITION,
    AuroraAnimationInjectionRequest,
    AuroraAnimationWriter,
)


TARGET_MDL = Path("tests/fixtures/kotor_stock/k1/pmbam.mdl")


def _anim_node(animation, name: str):
    return next(node for node in animation.nodes if node.name.lower() == name.lower())


def _controller(node, controller_type: int):
    return next(ctrl for ctrl in node.controllers if ctrl["type"] == controller_type)


@pytest.fixture(autouse=True)
def _prime_pmbam_supermodel_slots():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    SuperModelResolver.prime_cache(
        "S_Female02",
        KotorModel(
            name="S_Female02",
            animations=[
                Animation(name="pause1"),
                Animation(name="walk"),
                Animation(name="run"),
                Animation(name="victory"),
            ],
        ),
    )
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def _write_synthetic_r3a(path: Path) -> None:
    frames = [
        {
            "frame": 1,
            "time_seconds": 0.0,
            "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
            "location_xyz": [0.0, 0.0, 0.0],
        },
        {
            "frame": 2,
            "time_seconds": 1.0 / 30.0,
            "rotation_wxyz": [0.999, 0.0, 0.0447, 0.0],
            "location_xyz": [0.0, 0.0, 0.0],
        },
    ]
    payload = {
        "schema": "sprint3_r3a_retarget_ready_animation",
        "frame_count": 2,
        "fps": 30.0,
        "duration_seconds": 2.0 / 30.0,
        "target_slot": "victory",
        "target_curves": {
            "rootdummy": {
                "target_bone": "rootdummy",
                "source_rest_world": {"rotation_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "frames": frames,
            },
            "pelvis_g": {
                "target_bone": "pelvis_g",
                "source_rest_world": {"rotation_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "frames": frames,
            },
            "torso_g": {
                "target_bone": "torso_g",
                "source_rest_world": {"rotation_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "frames": frames,
            },
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _case_sensitive_node_paths(model):
    return [
        (
            node.name,
            node.parent.name if node.parent is not None else None,
            tuple(child.name for child in node.children),
        )
        for node in model.all_nodes()
    ]


def test_request_requires_existing_files(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        AuroraAnimationInjectionRequest(
            r3a_animation_json=tmp_path / "missing.json",
            target_mdl=tmp_path / "missing.mdl",
            animation_slot="victory",
            output_mdl=tmp_path / "out.mdl",
            output_manifest=tmp_path / "manifest.json",
        )


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_build_animation_from_r3a_creates_aurora_controllers(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))

    warnings: list[str] = []
    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=True,
        warnings=warnings,
    )

    assert animation.name == "victory"
    assert animation.anim_root == "PMBAM"
    assert len(animation.nodes) == len(model.all_nodes())
    first = animation.nodes[0]
    assert {ctrl["type"] for ctrl in first.controllers} == {CTRL_POSITION, CTRL_ORIENTATION}
    orientation = _controller(first, CTRL_ORIENTATION)
    assert orientation["columns"] == 4
    assert len(orientation["times"]) == 2
    assert len(orientation["values"][0]) == 4
    assert warnings


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_build_animation_from_r3a_backfills_full_hierarchy_orientation_controllers(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    payload["target_curves"] = {
        "rbicep_g": payload["target_curves"]["pelvis_g"],
    }
    payload["target_curves"]["rbicep_g"]["target_bone"] = "rbicep_g"

    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
    )

    assert [node.name for node in animation.nodes] == [node.name for node in model.all_nodes()]
    for model_node in model.all_nodes():
        anim_node = _anim_node(animation, model_node.name)
        orientation = _controller(anim_node, CTRL_ORIENTATION)
        assert orientation["times"] == pytest.approx([0.0, 1.0 / 30.0], abs=1e-7)
        assert len(orientation["values"]) == 2
        for quat in orientation["values"]:
            assert sum(value * value for value in quat) == pytest.approx(1.0, abs=1e-5)

    for constant_name in (
        "rootdummy",
        "pelvis_g",
        "torso_g",
        "torsoUpr_g",
        "rcollar_g",
        "lcollar_g",
        "headhook",
    ):
        model_node = model.find_node(constant_name)
        orientation = _controller(_anim_node(animation, constant_name), CTRL_ORIENTATION)
        assert orientation["values"][0] == pytest.approx(list(model_node.rotation), abs=1e-6)
        assert orientation["values"][1] == pytest.approx(list(model_node.rotation), abs=1e-6)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_build_animation_from_r3a_emits_root_pelvis_position_controllers_when_root_motion_exists(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    payload["target_curves"] = {
        "rootdummy": payload["target_curves"]["rootdummy"],
    }
    payload["target_curves"]["rootdummy"]["frames"][1]["location_xyz"] = [1.0, 2.0, 3.0]

    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
    )

    root_position = _controller(_anim_node(animation, "rootdummy"), CTRL_POSITION)
    pelvis_position = _controller(_anim_node(animation, "pelvis_g"), CTRL_POSITION)
    assert root_position["values"] == [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]
    assert pelvis_position["values"][0] == pytest.approx(list(model.find_node("pelvis_g").position), abs=1e-6)
    assert pelvis_position["values"][1] == pytest.approx(list(model.find_node("pelvis_g").position), abs=1e-6)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_rest_relative_identity_delta_preserves_target_bind_rotation(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    payload["target_curves"]["pelvis_g"]["frames"][0]["rotation_wxyz"] = [1.0, 0.0, 0.0, 0.0]

    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
    )

    pelvis_anim = _anim_node(animation, "pelvis_g")
    orientation = _controller(pelvis_anim, CTRL_ORIENTATION)
    assert orientation["values"][0] == pytest.approx(list(model.find_node("pelvis_g").rotation), abs=1e-6)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_source_rest_reference_mode_uses_bind_pose_for_frame_zero_motion(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    payload["target_curves"]["pelvis_g"]["source_rest_world"]["rotation_wxyz"] = [1.0, 0.0, 0.0, 0.0]
    payload["target_curves"]["pelvis_g"]["frames"][0]["rotation_wxyz"] = [0.9238795, 0.0, 0.3826834, 0.0]
    payload["target_curves"]["pelvis_g"]["frames"][1]["rotation_wxyz"] = [0.9063078, 0.0, 0.4226183, 0.0]

    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
        source_reference_mode="source_rest",
    )

    pelvis_anim = _anim_node(animation, "pelvis_g")
    orientation = _controller(pelvis_anim, CTRL_ORIENTATION)
    assert orientation["values"][0] != pytest.approx(list(model.find_node("pelvis_g").rotation), abs=1e-3)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_default_hybrid_reference_keeps_core_frame_zero_stable(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    payload["target_curves"]["pelvis_g"]["source_rest_world"]["rotation_wxyz"] = [1.0, 0.0, 0.0, 0.0]
    payload["target_curves"]["pelvis_g"]["frames"][0]["rotation_wxyz"] = [0.9238795, 0.0, 0.3826834, 0.0]

    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
    )

    pelvis_anim = _anim_node(animation, "pelvis_g")
    orientation = _controller(pelvis_anim, CTRL_ORIENTATION)
    assert orientation["values"][0] == pytest.approx(list(model.find_node("pelvis_g").rotation), abs=1e-6)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_hybrid_limb_weight_controls_bind_pose_limb_delta(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    frames = payload["target_curves"]["pelvis_g"]["frames"]
    payload["target_curves"] = {
        "lbicep_g": {
            "target_bone": "lbicep_g",
            "source_bone": "upperarm_l",
            "source_rest_world": {"rotation_wxyz": [1.0, 0.0, 0.0, 0.0]},
            "frames": frames,
        }
    }
    payload["target_curves"]["lbicep_g"]["frames"][0]["rotation_wxyz"] = [0.9238795, 0.0, 0.3826834, 0.0]

    stable = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
        hybrid_limb_source_rest_weight=0.0,
    )
    full = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
        source_reference_mode="source_rest",
    )
    hybrid_full = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
        hybrid_limb_source_rest_weight=1.0,
    )

    stable_orientation = _controller(_anim_node(stable, "lbicep_g"), CTRL_ORIENTATION)
    full_orientation = _controller(_anim_node(full, "lbicep_g"), CTRL_ORIENTATION)
    hybrid_orientation = _controller(_anim_node(hybrid_full, "lbicep_g"), CTRL_ORIENTATION)
    assert stable_orientation["values"][0] == pytest.approx(list(model.find_node("lbicep_g").rotation), abs=1e-6)
    assert hybrid_orientation["values"][0] == pytest.approx(full_orientation["values"][0], abs=1e-6)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_hybrid_reference_treats_clavicle_as_limb_root(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    frames = payload["target_curves"]["pelvis_g"]["frames"]
    payload["target_curves"] = {
        "lcollar_g": {
            "target_bone": "lcollar_g",
            "source_bone": "clavicle_l",
            "source_rest_world": {"rotation_wxyz": [1.0, 0.0, 0.0, 0.0]},
            "frames": frames,
        }
    }
    payload["target_curves"]["lcollar_g"]["frames"][0]["rotation_wxyz"] = [0.9238795, 0.0, 0.3826834, 0.0]

    stable = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
        source_reference_mode="clip_frame_zero",
    )
    hybrid_full = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
        hybrid_limb_source_rest_weight=1.0,
    )

    stable_orientation = _controller(_anim_node(stable, "lcollar_g"), CTRL_ORIENTATION)
    hybrid_orientation = _controller(_anim_node(hybrid_full, "lcollar_g"), CTRL_ORIENTATION)
    assert stable_orientation["values"][0] == pytest.approx(list(model.find_node("lcollar_g").rotation), abs=1e-6)
    assert hybrid_orientation["values"][0] != pytest.approx(stable_orientation["values"][0], abs=1e-3)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_clip_frame_zero_reference_mode_remains_explicit_legacy_option(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    payload["target_curves"]["pelvis_g"]["source_rest_world"]["rotation_wxyz"] = [1.0, 0.0, 0.0, 0.0]
    payload["target_curves"]["pelvis_g"]["frames"][0]["rotation_wxyz"] = [0.9238795, 0.0, 0.3826834, 0.0]
    payload["target_curves"]["pelvis_g"]["frames"][1]["rotation_wxyz"] = [0.9063078, 0.0, 0.4226183, 0.0]

    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
        source_reference_mode="clip_frame_zero",
    )

    pelvis_anim = _anim_node(animation, "pelvis_g")
    orientation = _controller(pelvis_anim, CTRL_ORIENTATION)
    assert orientation["values"][0] == pytest.approx(list(model.find_node("pelvis_g").rotation), abs=1e-6)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_inject_writes_binary_mdl_and_mdx(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    output_mdl = tmp_path / "pmbam__victory__r3b.mdl"
    manifest = tmp_path / "manifest.json"

    result = AuroraAnimationWriter().inject(
        AuroraAnimationInjectionRequest(
            r3a_animation_json=r3a,
            target_mdl=TARGET_MDL,
            animation_slot="victory",
            output_mdl=output_mdl,
            output_manifest=manifest,
        )
    )

    assert result.success, result.errors
    assert output_mdl.exists()
    assert output_mdl.with_suffix(".mdx").exists()
    assert manifest.exists()
    assert result.operation == "appended_local_override"
    assert result.output_size_bytes <= result.input_size_bytes * 2.0


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_injected_mdl_reloads_with_local_victory(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    output_mdl = tmp_path / "pmbam__victory__r3b.mdl"

    result = AuroraAnimationWriter().inject(
        AuroraAnimationInjectionRequest(
            r3a_animation_json=r3a,
            target_mdl=TARGET_MDL,
            animation_slot="victory",
            output_mdl=output_mdl,
            output_manifest=tmp_path / "manifest.json",
        )
    )

    assert result.success, result.errors
    reloaded = load_model_from_file(str(output_mdl), str(output_mdl.with_suffix(".mdx")))
    assert reloaded is not None
    animation = next(anim for anim in reloaded.animations if anim.name.lower() == "victory")
    orientation_nodes = {
        node.name.lower()
        for node in animation.nodes
        if any(ctrl.get("type") == CTRL_ORIENTATION for ctrl in node.controllers)
    }
    assert len(animation.nodes) == len(reloaded.all_nodes())
    assert len(orientation_nodes) == len(reloaded.all_nodes())
    assert not {
        "rootdummy",
        "pelvis_g",
        "torso_g",
        "torsoupr_g",
        "rcollar_g",
        "lcollar_g",
    }.difference(orientation_nodes)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_injected_mdl_preserves_pmbam_node_name_case_and_inherited_slots(tmp_path: Path):
    from src.core.game.kotor_loader import resolve_animation_slot

    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    output_mdl = tmp_path / "pmbam__victory__case_preserved.mdl"
    original = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))

    result = AuroraAnimationWriter().inject(
        AuroraAnimationInjectionRequest(
            r3a_animation_json=r3a,
            target_mdl=TARGET_MDL,
            animation_slot="victory",
            output_mdl=output_mdl,
            output_manifest=tmp_path / "manifest.json",
        )
    )

    assert result.success, result.errors
    reloaded = load_model_from_file(str(output_mdl), str(output_mdl.with_suffix(".mdx")))
    assert reloaded is not None
    assert reloaded.name == original.name == "PMBAM"
    assert _case_sensitive_node_paths(reloaded) == _case_sensitive_node_paths(original)

    victory = next(anim for anim in reloaded.animations if anim.name == "victory")
    assert [node.name for node in victory.nodes] == [node.name for node in original.all_nodes()]

    for slot in ("pause1", "walk", "run"):
        resolved = resolve_animation_slot(reloaded, slot, require_valid=True)
        assert resolved.found
        assert resolved.inherited
        assert resolved.slot_name == slot


def test_result_manifest_is_json_serializable(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    target = tmp_path / "target.mdl"
    r3a.write_text("{}", encoding="utf-8")
    target.write_bytes(b"dummy")

    request = AuroraAnimationInjectionRequest(
        r3a_animation_json=r3a,
        target_mdl=target,
        animation_slot="victory",
        output_mdl=tmp_path / "out.mdl",
        output_manifest=tmp_path / "manifest.json",
    )
    result = AuroraAnimationWriter()._finish(
        result=__import__(
            "src.core.retargeting.aurora_animation_writer",
            fromlist=["AuroraAnimationInjectionResult"],
        ).AuroraAnimationInjectionResult(success=False, animation_slot="victory"),
        request=request,
    )

    assert result.success is False
    payload = json.loads(request.output_manifest.read_text(encoding="utf-8"))
    assert payload["animation_slot"] == "victory"
