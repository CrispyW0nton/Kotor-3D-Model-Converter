from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.core.characters import character_builder
from src.core.characters.character_override_package import (
    CharacterBuilderOverridePackageRequest,
    package_character_override_candidate,
)
from src.core.characters.headless_body_workflow import (
    run_external_mesh_native_template_launch_workflow,
)


_DEFAULT_BENDAK_FBX = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\BendakStarkiller\Bendak.fbx"
)


def _bendak_fixture_path() -> Path:
    return Path(os.environ.get("GHOSTRIGGER_BENDAK_FBX", str(_DEFAULT_BENDAK_FBX)))


@pytest.mark.parametrize("game", ["K1", "K2"])
def test_t1205_local_bendak_to_mandalorian_native_template_launch_proof(
    game: str,
    tmp_path: Path,
) -> None:
    """Local continual fixture: Bendak.fbx payload bound to n_mandalorian."""
    mesh_path = _bendak_fixture_path()
    if not mesh_path.exists():
        pytest.skip(f"Local Bendak fixture not present: {mesh_path}")

    native_base = character_builder.load_game_skeleton_source(
        "n_mandalorian",
        game=game,
    )
    if native_base is None:
        pytest.skip(f"Configured {game} install cannot load n_mandalorian")

    result = run_external_mesh_native_template_launch_workflow(
        str(mesh_path),
        "n_mandalorian",
        game_version=game,
        out_dir=str(tmp_path),
        formats=["kotor"],
    )

    assert result.ok is True
    assert result.code == "export_candidate_verified"
    assert result.capability_stage == "export_candidate"
    assert result.game_tested is False
    assert Path(result.mdl_path).exists()
    assert Path(result.mdx_path).exists()
    assert result.mesh_count == 1
    assert result.skin_node_count == 1
    assert result.supermodel == "S_Female02"
    assert {"rhand", "headhook"}.issubset({name.lower() for name in result.hooks})
    assert result.load_result is not None
    assert "Fit to n_mandalorian" in result.load_result.message
    assert result.apply_result is not None
    assert result.apply_result.get("ok") is True
    assert result.apply_result.get("replaced_native_render_nodes")
    built_model = result.apply_result.get("model")
    assert built_model is not None
    leaked_guides = [
        node for node in built_model.all_nodes()
        if getattr(node, "_gr_imported_armature_joint", False)
        or getattr(node, "_gr_imported_armature", False)
    ]
    assert leaked_guides == []
    assert any(
        "Removed" in warning and "imported armature/helper" in warning
        for warning in result.apply_result.get("warnings", [])
    )
    source_landmark_sources = (
        result.apply_result.get("model").metadata.get("kotor_fit_report", {})
        .get("source_frame", {})
        .get("landmark_sources", {})
    )
    assert source_landmark_sources
    assert set(source_landmark_sources.values()) == {"imported_skeleton"}
    imported_armature = (
        result.apply_result.get("model").metadata.get("kotor_fit_report", {})
        .get("source_imported_armature", {})
    )
    assert imported_armature["source"] == "imported_fbx_armature"
    assert imported_armature["guide_joint_count"] == 65
    assert imported_armature["scene_guide_joint_count"] == 65
    assert imported_armature["armature_names"] == ["Armature"]
    assert result.motion_result is not None
    assert result.motion_result.supermodel == "S_Female02"
    assert result.animation_library_result is not None
    assert result.animation_library_result.code == "listed"
    animation_names = {
        name for _label, name in result.animation_library_result.available
    }
    assert {"pause1", "pause2", "walk", "tlknorm"}.issubset(animation_names)
    assert len(animation_names) >= 100

    package = package_character_override_candidate(
        CharacterBuilderOverridePackageRequest(
            source_mdl_path=Path(result.mdl_path),
            output_dir=tmp_path / f"{game.lower()}_override_package",
            target_resref="n_mandalorian03",
            game=game,
        )
    )

    assert package.succeeded is True
    assert package.mdl_path.exists()
    assert package.mdx_path.exists()
    assert package.manifest_path.exists()
    assert package.manifest["target_resref"] == "n_mandalorian03"
    assert package.manifest["game"] == game
    assert package.manifest["capability"]["stage"] == "export_candidate"
    assert package.manifest["capability"]["game_tested"] is False
