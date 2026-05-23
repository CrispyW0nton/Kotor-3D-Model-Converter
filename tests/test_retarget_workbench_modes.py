"""Mode contract coverage for the Retarget Workbench shell."""

from __future__ import annotations

from src.core.retargeting.retarget_modes import RetargetMode, get_retarget_mode_spec, list_retarget_mode_specs


def test_all_three_mode_specs_exist() -> None:
    specs = list_retarget_mode_specs()
    modes = {spec.mode for spec in specs}

    assert modes == {
        RetargetMode.KOTOR_TO_KOTOR,
        RetargetMode.KOTOR_TO_UNREAL,
        RetargetMode.UNREAL_TO_KOTOR,
    }
    for spec in specs:
        assert spec.label
        assert spec.description
        assert spec.source_kind
        assert spec.target_kind
        assert spec.output_kind
        assert spec.required_inputs


def test_unreal_to_kotor_mode_is_implemented() -> None:
    spec = get_retarget_mode_spec(RetargetMode.UNREAL_TO_KOTOR)

    assert spec.label == "Unreal → KOTOR"
    assert spec.implemented is True
    assert spec.supports_preview is True
    assert spec.supports_export is True
    assert spec.source_kind == "ue_fbx_source_clip"
    assert spec.output_kind == "kotor_mdl_mdx_animation_override"


def test_kotor_to_kotor_is_implemented_and_kotor_to_unreal_is_pending() -> None:
    kotor_to_kotor = get_retarget_mode_spec(RetargetMode.KOTOR_TO_KOTOR)
    kotor_to_unreal = get_retarget_mode_spec(RetargetMode.KOTOR_TO_UNREAL)

    assert kotor_to_kotor.implemented is True
    assert kotor_to_kotor.supports_preview is True
    assert kotor_to_kotor.supports_export is True
    assert "verified GhostRigger preview/export pipeline" in kotor_to_kotor.description

    assert kotor_to_unreal.implemented is False
    assert kotor_to_unreal.supports_preview is False
    assert kotor_to_unreal.supports_export is False
    assert "UE-compatible FBX" in kotor_to_unreal.description
    assert "KOTOR source animation sampler is available" in kotor_to_unreal.description
