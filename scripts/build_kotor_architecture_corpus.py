"""Build local, training-ready text sequences from installed KOTOR rooms.

This tool never edits the game installation and never checks retail geometry
into Ghost Studio.  It flattens each selected Odyssey room into labeled,
OBJ-like text beside a compact manifest that records semantic-role confidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _install_import_paths() -> None:
    roots = (
        ROOT / "native" / "GhostRigger.Core.Scene" / "Python",
        ROOT / "native" / "GhostRigger.Core.Resources" / "Python",
        ROOT / "native" / "GhostRigger.Core.Math" / "Python",
        ROOT / "native" / "GhostRigger.Core.Rendering" / "Python",
        ROOT / "native" / "GhostRigger.Core.Tools" / "Python",
        ROOT,
        ROOT.parent / "PyKotor" / "Libraries" / "PyKotor" / "src",
        ROOT.parent / "PyKotor" / "Libraries" / "PyKotorGL" / "src",
        ROOT.parent / "PyKotor" / "Libraries" / "Utility" / "src",
    )
    for path in reversed(roots):
        if path.exists() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _default_output() -> Path:
    local = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    root = Path(local) if local else ROOT / "artifacts"
    return root / "GhostStudio" / "cache" / "architecture_training" / "v1"


def _configured_k1_dir() -> str:
    try:
        payload = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        payload = {}
    return str(payload.get("k1_dir") or os.environ.get("K1_PATH") or "")


def _configured_k2_dir() -> str:
    try:
        payload = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        payload = {}
    return str(payload.get("k2_dir") or os.environ.get("K2_PATH") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        action="append",
        choices=(
            "endar_spire",
            "taris_apartments",
            "harbinger",
            "shadowlands",
            "korriban_tombs",
            "korriban_caves_k1",
            "korriban_tombs_k2",
            "korriban_caves_k2",
        ),
        help="Profile to extract. Repeat for several; defaults to all proof kits.",
    )
    parser.add_argument("--k1-dir", default=_configured_k1_dir(), help="Installed Knights of the Old Republic directory.")
    parser.add_argument("--k2-dir", default=_configured_k2_dir(), help="Installed Knights of the Old Republic II directory.")
    parser.add_argument("--output", type=Path, default=_default_output(), help="Local output directory.")
    args = parser.parse_args()
    profiles = tuple(args.profile or ("endar_spire", "taris_apartments", "harbinger"))
    _install_import_paths()

    from src.core.assets.resource_manager import ResourceManager
    from src.core.modules.map_studio_pascal_building import (
        architecture_training_room_specs,
        architecture_training_game,
        serialize_architecture_model_text,
    )

    manager = ResourceManager()
    required_games = {architecture_training_game(profile) for profile in profiles}
    if "K1" in required_games and not manager.set_k1_dir(str(args.k1_dir or "")):
        raise SystemExit("Configure a valid KOTOR 1 installation before building the architecture corpus.")
    if "K2" in required_games and not manager.set_k2_dir(str(args.k2_dir or "")):
        raise SystemExit("Configure a valid KOTOR 2 installation before building the architecture corpus.")
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, object]] = []
    for profile in profiles:
        profile_game = architecture_training_game(profile)
        profile_dir = output / profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        for module_resref, room_resref in architecture_training_room_specs(profile):
            model = manager.load_model_strict(room_resref, profile_game, prefer_base_archive=True)
            if model is None:
                raise SystemExit(f"Could not load {profile_game} room model {room_resref} ({module_resref}).")
            sequence, summary = serialize_architecture_model_text(
                model,
                game=profile_game,
                module_resref=module_resref,
                room_resref=room_resref,
                profile=profile,
            )
            target = profile_dir / f"{room_resref}.mesh.txt"
            target.write_text(sequence, encoding="utf-8")
            manifest_rows.append({**summary, "sequence_path": str(target.relative_to(output)).replace("\\", "/")})
            print(
                f"{profile}: {module_resref}/{room_resref} -> "
                f"{summary['surface_count']} surfaces, {summary['triangle_count']} triangles"
            )
    manifest = {
        "schema": "ghostrigger.kotor-architecture-corpus/v1",
        "representation": "labeled OBJ-compatible text sequence",
        "games": sorted(required_games),
        "profiles": list(profiles),
        "room_count": len(manifest_rows),
        "rooms": manifest_rows,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Architecture corpus written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
