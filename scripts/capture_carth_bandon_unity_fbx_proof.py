"""Export and visibly validate Carth/Bandon facial animation in Unity 2022."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402

for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))


DEFAULT_K1_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
DEFAULT_UNITY_EXE = Path(
    r"C:\Program Files\Unity\Hub\Editor\2022.3.62f1\Editor\Unity.exe"
)
DEFAULT_UNITY_PROJECT = ROOT / "artifacts" / "qa" / "unity_import_project"
DEFAULT_PROOF_DIR = ROOT / "artifacts" / "qa" / "carth_bandon_facial_export"
FIXTURES = (
    ("carth", "p_carthbb", "p_carthh"),
    ("darth_bandon", "n_darthband", "darthband_h"),
)


class _ResourceTextureCache:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def get(self, texture_name: str):
        return self._manager.load_texture_image(texture_name, "K1", max_size=0)


def _export_fixtures(k1_dir: Path, proof_dir: Path, unity_project: Path) -> dict[str, Any]:
    from src.converters.mesh_converter import FBXExporter, OBJExporter
    from src.core.animation.animation_engine import SuperModelResolver
    from src.core.animation.fbx_animation_selection import (
        prepare_fbx_animation_export_model,
    )
    from src.core.assets.resource_manager import ResourceManager
    from src.systems.bas.preview_composer import (
        build_bas_preview_model,
        prepare_bas_composed_export_model,
    )

    manager = ResourceManager()
    if not manager.set_k1_dir(str(k1_dir)):
        raise RuntimeError(f"KOTOR 1 installation could not be indexed: {k1_dir}")
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(manager)
    texture_cache = _ResourceTextureCache(manager)
    results = []
    for label, body_resref, head_resref in FIXTURES:
        body = manager.load_model_strict(body_resref, "K1")
        head = manager.load_model_strict(head_resref, "K1")
        if body is None or head is None:
            raise RuntimeError(f"Could not load {body_resref} + {head_resref} from K1")
        preview = build_bas_preview_model(
            body_model=body,
            attachment_models={"head": head},
            name=f"{body_resref}_{head_resref}",
        )
        composed, composition_report = prepare_bas_composed_export_model(
            preview,
            require_unique_body_names=True,
        )
        supermodel = str(getattr(body, "supermodel", "") or "").strip()
        base_skeleton = (
            manager.load_model_strict(supermodel, "K1")
            if supermodel and supermodel.casefold() not in {"null", "none", "****"}
            else None
        )
        prepared = prepare_fbx_animation_export_model(
            composed,
            ("tlknorm",),
            game="K1",
            resource_manager=manager,
            base_skeleton_model=base_skeleton,
            supplemental_models=(head,),
        )
        prepared.name = f"{body_resref}_{head_resref}"
        fixture_dir = proof_dir / label
        fixture_dir.mkdir(parents=True, exist_ok=True)
        fbx_path = fixture_dir / f"{label}_tlknorm.fbx"
        if not FBXExporter().export(
            prepared,
            str(fbx_path),
            tex_cache=texture_cache,
            export_rigging=True,
            base_skeleton_model=base_skeleton,
            compatibility_profile="unity",
        ):
            raise RuntimeError(f"FBX export failed: {fbx_path}")

        track_names = [
            str(getattr(node, "name", "") or "")
            for node in prepared.animations[0].nodes
        ]
        attached_track_names = [name for name in track_names if "__head" in name.casefold()]
        suppressed = [
            str(getattr(node, "name", "") or "")
            for node in prepared.all_nodes()
            if bool(getattr(node, "_gr_bas_geometry_replaced_by_attachment", False))
        ]
        renderable_rigid = [
            str(getattr(node, "name", "") or "")
            for node in prepared.all_nodes()
            if OBJExporter._is_renderable(node)
            and any(
                token in str(getattr(node, "name", "") or "").casefold()
                for token in ("eye", "lid", "teeth", "tooth")
            )
        ]
        results.append({
            "label": label,
            "body": body_resref,
            "head": head_resref,
            "fbx": str(fbx_path),
            "composition": composition_report,
            "animation_tracks": track_names,
            "attached_head_animation_tracks": attached_track_names,
            "suppressed_body_geometry": suppressed,
            "renderable_rigid_facial_geometry": renderable_rigid,
        })

        unity_asset_dir = unity_project / "Assets" / "FacialProof" / label
        unity_asset_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fbx_path, unity_asset_dir / fbx_path.name)
        manifest_path = fbx_path.with_suffix(".ghostrigger.json")
        if manifest_path.exists():
            shutil.copy2(manifest_path, unity_asset_dir / manifest_path.name)
        textures = fixture_dir / "textures"
        if textures.exists():
            shutil.copytree(
                textures,
                unity_asset_dir / "textures",
                dirs_exist_ok=True,
            )

    source_audit = {"status": "pass", "characters": results}
    (proof_dir / "source_fbx_facial_export_proof.json").write_text(
        json.dumps(source_audit, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return source_audit


def run(
    *,
    k1_dir: Path,
    unity_exe: Path,
    unity_project: Path,
    proof_dir: Path,
    skip_unity: bool = False,
) -> dict[str, Any]:
    proof_dir.mkdir(parents=True, exist_ok=True)
    source_audit = _export_fixtures(k1_dir, proof_dir, unity_project)
    editor_dir = unity_project / "Assets" / "Editor"
    editor_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / "scripts" / "unity" / "GhostRiggerFacialExportProof.cs",
        editor_dir / "GhostRiggerFacialExportProof.cs",
    )
    if skip_unity:
        return {"source": source_audit, "unity": {"status": "skipped"}}
    log_path = proof_dir / "unity_facial_export_proof.log"
    command = [
        str(unity_exe),
        "-batchmode",
        "-quit",
        "-projectPath",
        str(unity_project),
        "-executeMethod",
        "GhostRiggerFacialExportProof.Run",
        "-facialProofOutput",
        str(proof_dir),
        "-logFile",
        str(log_path),
    ]
    completed = subprocess.run(command, check=False, timeout=600)
    unity_report_path = proof_dir / "unity_facial_export_proof.json"
    unity_report = (
        json.loads(unity_report_path.read_text(encoding="utf-8"))
        if unity_report_path.exists()
        else {"passed": False, "returncode": completed.returncode}
    )
    if completed.returncode != 0 or not bool(unity_report.get("passed", False)):
        raise RuntimeError(
            f"Unity facial export proof failed (exit {completed.returncode}); see {log_path}"
        )
    return {"source": source_audit, "unity": unity_report}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k1-dir", type=Path, default=DEFAULT_K1_DIR)
    parser.add_argument("--unity-exe", type=Path, default=DEFAULT_UNITY_EXE)
    parser.add_argument("--unity-project", type=Path, default=DEFAULT_UNITY_PROJECT)
    parser.add_argument("--proof-dir", type=Path, default=DEFAULT_PROOF_DIR)
    parser.add_argument("--skip-unity", action="store_true")
    args = parser.parse_args()
    report = run(
        k1_dir=args.k1_dir,
        unity_exe=args.unity_exe,
        unity_project=args.unity_project,
        proof_dir=args.proof_dir,
        skip_unity=args.skip_unity,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
