"""Build the Shadow Kinrath PLCaa test package for KOTOR 1 (T-user kinrath).

Root cause of the reported crash: the user's ``C_Kinrath05.tga`` was exported
from GIMP RLE-compressed (TGA image type 10) at 1254x1254.  Odyssey's TGA
loader only accepts uncompressed type-2 data with power-of-two dimensions, so
the engine died the moment the racetex resolved.  The user's appearance.2da
row 516 (race=C_Kinrath, racetex=C_Kinrath05, modeltype=S) and
``ke_shadowkinra.utc`` (appearance 516) were already correct and are shipped
byte-identical.

The fix re-encodes the texture: decode RLE, LANCZOS-resize to 1024x1024,
write uncompressed 24-bit bottom-left-origin TGA.  The bundled PLCaa module
starts from the user-approved clean arena and embeds the single kinrath UTC
(module-local), spawned on the proven-walkable arena spot in front of the
player entry.

Default behavior is stage only.  ``--install`` backs up and copies into the
KOTOR 1 directory; ``--zip`` writes the distributable archive (run after the
in-game test passes).  This script never launches KOTOR.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
for rel in (
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.IO/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Validation/Python",
    "native/GhostRigger.Core.Project/Python",
    "",
):
    path = str(ROOT / rel) if rel else str(ROOT)
    if path not in sys.path:
        sys.path.insert(0, path)

from scripts import deploy_lorum_ipsat_plcaa as plcaa  # noqa: E402
from src.core.assets.resource_manager import (  # noqa: E402
    ResourceManager,
    _ErfIndex,
)
from src.core.modules import module_save_pipeline as msp  # noqa: E402
from src.core.modules.module_format import WOKData  # noqa: E402
from src.core.templates.twoda import TwoDA  # noqa: E402
from src.core.validation.kotor_module_engine_contract import (  # noqa: E402
    KotorModuleEngineContractRequest,
    validate_kotor_module_engine_contract,
)
from src.formats.gff_reader import read_gff  # noqa: E402
from src.formats.gff_writer import write_gff  # noqa: E402
from src.math.walkmesh_runtime import WalkmeshRuntimeIndex  # noqa: E402


K1 = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
OUTPUT = ROOT / "artifacts" / "shadow_kinrath_plcaa_demo"
SOURCE = OUTPUT / "source"
INSTALL = OUTPUT / "install"
OVERRIDE = INSTALL / "Override"
MODULES = INSTALL / "Modules"
MODULE = MODULES / "PLCaa.mod"
README = OUTPUT / "README.txt"
MANIFEST = OUTPUT / "validation_manifest.json"
ZIP_PATH = ROOT / "artifacts" / "Shadow_Kinrath_PLCaa_Demo.zip"

CLEAN_MAP = (
    ROOT / "artifacts" / "lorum_ipsat_plcaa_clean_dev_map"
    / "Modules" / "PLCaa.mod"
)
CLEAN_MAP_SHA256 = (
    "259b7ae81852ae382d4b81ac5a937c939a78f6f8db7c166ba2ef08eb17760f0a"
)

UTC_RESREF = "ke_shadowkinra"
TEXTURE_RESREF = "C_Kinrath05"
APPEARANCE_ROW = 516
KOTOR_TEX_SIZE = 1024

RES_UTC = 2027
RESOURCE_EXTENSIONS = dict(plcaa.MODULE_EXTENSIONS)
RESOURCE_EXTENSIONS[RES_UTC] = "utc"

# Ten units in front of PLAYER_ENTRY (29, 22), facing the player — the same
# proven-walkable spot deploy_lorum_ipsat_plcaa uses for its showcase actor.
PLACEMENT = (29.0, 32.0, 0.0, 0.0, -1.0)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _fix_texture() -> tuple[bytes, dict]:
    """Decode the RLE source, resize to the KOTOR PoT grid, re-encode raw."""

    import numpy as np
    from PIL import Image

    src = SOURCE / f"{TEXTURE_RESREF}.tga"
    raw = src.read_bytes()
    src_type, = struct.unpack_from("<B", raw, 2)
    src_w, src_h = struct.unpack_from("<HH", raw, 12)
    src_bpp = raw[16]

    image = Image.open(src)
    assert image.size == (src_w, src_h)
    image = image.convert("RGB")
    if image.size != (KOTOR_TEX_SIZE, KOTOR_TEX_SIZE):
        image = image.resize((KOTOR_TEX_SIZE, KOTOR_TEX_SIZE), Image.LANCZOS)

    pixels = np.asarray(image, dtype=np.uint8)      # top-down RGB
    bottom_up_bgr = pixels[::-1, :, ::-1]           # TGA rows, BGR order
    header = struct.pack(
        "<BBBHHBHHHHBB",
        0, 0, 2,                     # no id, no colormap, uncompressed true-color
        0, 0, 0,                     # empty colormap spec
        0, 0,                        # origin
        KOTOR_TEX_SIZE, KOTOR_TEX_SIZE,
        24, 0,                       # 24 bpp, bottom-left origin
    )
    data = header + bottom_up_bgr.tobytes()
    assert len(data) == 18 + KOTOR_TEX_SIZE * KOTOR_TEX_SIZE * 3

    reread = Image.open(__import__("io").BytesIO(data))
    assert reread.size == (KOTOR_TEX_SIZE, KOTOR_TEX_SIZE)
    assert data[2] == 2 and data[16] == 24 and data[17] == 0

    return data, {
        "source": {
            "file": src.name,
            "tga_image_type": src_type,
            "size": f"{src_w}x{src_h}",
            "bits_per_pixel": src_bpp,
            "sha256": _sha256_bytes(raw),
            "defects": [
                "RLE-compressed (type 10) — Odyssey TGA loader needs type 2",
                "non-power-of-two 1254x1254",
            ],
        },
        "fixed": {
            "tga_image_type": 2,
            "size": f"{KOTOR_TEX_SIZE}x{KOTOR_TEX_SIZE}",
            "bits_per_pixel": 24,
            "descriptor": 0,
            "bytes": len(data),
            "sha256": _sha256_bytes(data),
        },
    }


def _validate_appearance() -> tuple[bytes, dict]:
    """The user's 2DA is shipped byte-identical; prove row 516 is coherent."""

    data = (SOURCE / "appearance.2da").read_bytes()
    assert data[:9] == b"2DA V2.b\n", "appearance.2da is not binary V2.b"
    table = TwoDA.from_bytes(data)
    assert len(table) == APPEARANCE_ROW + 1, len(table)
    row = {
        column: table.get(APPEARANCE_ROW, column) or ""
        for column in ("label", "race", "racetex", "modeltype", "sizecategory")
    }
    assert row["race"].lower() == "c_kinrath", row
    assert row["racetex"].lower() == TEXTURE_RESREF.lower(), row
    assert row["modeltype"].upper() == "S", row
    # The new row must be a faithful clone of the vanilla kinrath template.
    template = 88
    diffs = [
        column
        for column in table.columns
        if column not in ("label", "racetex")
        and (table.get(APPEARANCE_ROW, column) or "")
        != (table.get(template, column) or "")
    ]
    assert not diffs, diffs
    return data, {
        "source": "user appearance.2da (modded base, shipped byte-identical)",
        "row_count": len(table),
        "row": APPEARANCE_ROW,
        "cells": row,
        "clone_of_row": template,
        "sha256": _sha256_bytes(data),
    }


def _validate_utc() -> tuple[bytes, dict]:
    data = (SOURCE / f"{UTC_RESREF}.utc").read_bytes()
    root = read_gff(data).root
    resref = str(root.fields["TemplateResRef"].value).lower()
    assert resref == UTC_RESREF, resref
    assert str(root.fields["Tag"].value).lower() == UTC_RESREF
    assert int(root.fields["Appearance_Type"].value) == APPEARANCE_ROW
    detail = {
        "resref": resref,
        "appearance": APPEARANCE_ROW,
        "faction": int(root.fields["FactionID"].value),
        "hit_points": int(root.fields["MaxHitPoints"].value),
        "challenge_rating": float(root.fields["ChallengeRating"].value),
        "sha256": _sha256_bytes(data),
        "shipped": "byte-identical user UTC, embedded module-local",
    }
    return data, detail


def _assess_donor_model() -> dict:
    """Ghost Studio assessment: the retail C_Kinrath donor must parse clean."""

    manager = ResourceManager()
    assert manager.set_k1_dir(str(K1))
    model = manager.load_model("c_kinrath", "K1")
    assert model is not None, "retail c_kinrath failed to load"
    nodes = list(model.all_nodes())
    textures = sorted({
        str(getattr(node, "texture", "") or "").lower()
        for node in nodes
        if str(getattr(node, "texture", "") or "")
    })
    return {
        "model": "c_kinrath (retail, untouched — racetex swap only)",
        "node_count": len(nodes),
        "animation_count": len(model.animations or []),
        "textures": textures,
    }


def _engine_contract(resources: dict[tuple[str, int], bytes]) -> dict:
    mapped = {
        (resref, RESOURCE_EXTENSIONS[restype]): data
        for (resref, restype), data in resources.items()
    }
    report = validate_kotor_module_engine_contract(
        KotorModuleEngineContractRequest(
            game="K1",
            module_resref="plcaa",
            resources=mapped,
            expected_room_resrefs=("plcaa",),
        )
    )
    assert report.export_ready, "\n".join(report.blocking_issues)
    return report.to_dict()


def _build_module(utc_bytes: bytes) -> tuple[bytes, dict]:
    assert CLEAN_MAP.is_file(), CLEAN_MAP
    assert _sha256_file(CLEAN_MAP) == CLEAN_MAP_SHA256
    base = plcaa._resource_map(CLEAN_MAP)
    assert len(base) == 9
    resources = dict(base)

    git = read_gff(resources[("plcaa", plcaa.RES_GIT)])
    for label in plcaa.DYNAMIC_GIT_LISTS:
        if label in git.root.fields:
            git.root.fields[label].value[:] = []
    instance = copy.deepcopy(plcaa._vanilla_creature_instance())
    fields = instance.fields
    fields["TemplateResRef"].value = type(
        fields["TemplateResRef"].value
    )(UTC_RESREF)
    x, y, z, facing_x, facing_y = PLACEMENT
    fields["XPosition"].value = float(x)
    fields["YPosition"].value = float(y)
    fields["ZPosition"].value = float(z)
    fields["XOrientation"].value = float(facing_x)
    fields["YOrientation"].value = float(facing_y)
    git.root.fields["Creature List"].value.append(instance)
    resources[("plcaa", plcaa.RES_GIT)] = write_gff(git)
    resources[(UTC_RESREF, RES_UTC)] = utc_bytes

    wok = WOKData.from_bytes(resources[("plcaa", plcaa.RES_WOK)])
    runtime = WalkmeshRuntimeIndex(wok, game="K1")
    sample = runtime.sample_at(x, y, z)
    assert sample is not None, PLACEMENT
    player_sample = runtime.sample_at(*plcaa.PLAYER_ENTRY[:3])
    assert player_sample is not None

    entries = []
    for (resref, restype), data in sorted(resources.items()):
        extension = RESOURCE_EXTENSIONS[restype]
        entries.append(msp.ModuleArchiveEntry(
            resref=resref,
            restype=extension,
            data=data,
            archive_role=(
                msp._archive_role(extension)
                if hasattr(msp, "_archive_role") else "module"
            ),
            source=(
                "user-approved-clean-PLCaa"
                if (resref, restype) in base
                else "shadow-kinrath-module-local-UTC"
            ),
            changed=(restype in {plcaa.RES_GIT, RES_UTC}),
            serializer="shadow_kinrath_demo",
            warning=None,
        ))
    module_bytes = msp.build_erf_v1_archive(entries, archive_type="MOD")

    for key, data in base.items():
        if key != ("plcaa", plcaa.RES_GIT):
            assert resources[key] == data, key

    return module_bytes, {
        "base_module": str(CLEAN_MAP),
        "base_sha256": CLEAN_MAP_SHA256,
        "resource_count": len(resources),
        "placement": {
            "template": UTC_RESREF,
            "position": [x, y, z],
            "facing": [facing_x, facing_y],
            "wok_face": int(sample.face_index),
            "surface": int(sample.surface_id),
        },
        "player_entry": list(plcaa.PLAYER_ENTRY),
        "engine_contract": _engine_contract(resources),
    }


def _validate_module(path: Path) -> dict:
    resources = plcaa._resource_map(path)
    assert len(resources) == 10
    assert (UTC_RESREF, RES_UTC) in resources
    git = read_gff(resources[("plcaa", plcaa.RES_GIT)])
    refs = [
        str(item.fields["TemplateResRef"].value).lower()
        for item in git.root.fields["Creature List"].value
    ]
    assert refs == [UTC_RESREF], refs
    counts = {
        label: len(git.root.fields[label].value)
        if label in git.root.fields else 0
        for label in plcaa.DYNAMIC_GIT_LISTS
    }
    assert counts["Creature List"] == 1
    assert all(
        count == 0 for label, count in counts.items()
        if label != "Creature List"
    ), counts
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": _sha256_file(path),
        "resource_count": len(resources),
        "creature_refs": refs,
    }


def _write_readme() -> None:
    README.write_text(
        """Shadow Kinrath PLCaa Test Package - KOTOR 1
============================================

What was wrong
--------------
The original C_Kinrath05.tga was exported from GIMP with RLE compression
(TGA image type 10) at 1254x1254. KOTOR 1's TGA loader only accepts
uncompressed (type 2) textures with power-of-two dimensions, so the game
crashed as soon as the racetex was resolved. The appearance.2da row (516)
and ke_shadowkinra.utc were already correct and ship byte-identical.

The fix
-------
C_Kinrath05.tga re-encoded: RLE decoded, LANCZOS-resized to 1024x1024,
written as uncompressed 24-bit bottom-left-origin TGA.

Contents
--------
- Override/C_Kinrath05.tga    (fixed texture)
- Override/appearance.2da     (user's table, row 516 = ke_shadowkinrath)
- Modules/PLCaa.mod           (clean arena + one hostile Shadow Kinrath)

Game test
---------
1. Close KOTOR 1, install the two folders over the game directory.
2. Load a save made OUTSIDE PLCaa (or start a new game); enable cheats.
3. Use: warp plcaa
4. The kinrath spawns 10 m in front of you, faction Hostile - it will
   attack on sight. Verify the Korriban-style texture renders correctly.

Do not load a save made inside an older PLCaa: KOTOR restores the saved
module state over the new GIT.

Compatibility
-------------
appearance.2da here is the user's own modded table (517 rows). On another
install, merge row 516 instead of overwriting.
""",
        encoding="utf-8",
    )


def _install() -> dict:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    actions = []
    for staged, target in (
        (OVERRIDE / f"{TEXTURE_RESREF}.tga", K1 / "Override" / f"{TEXTURE_RESREF}.tga"),
        (OVERRIDE / "appearance.2da", K1 / "Override" / "appearance.2da"),
        (MODULE, K1 / "Modules" / "PLCaa.mod"),
    ):
        if target.is_file():
            backup = target.with_name(f"{target.name}.pre_kinrath_{stamp}.bak")
            shutil.copy2(target, backup)
            actions.append({"backed_up": str(target), "to": backup.name})
        shutil.copy2(staged, target)
        actions.append({"installed": str(target), "sha256": _sha256_file(target)})
    stale = K1 / "currentgame" / "PLCaa.mod"
    if stale.is_file():
        stale.unlink()
        actions.append({"removed_stale": str(stale)})
    return {"timestamp": stamp, "actions": actions}


def _write_zip(expected_files: list[Path]) -> dict:
    import zipfile

    with zipfile.ZipFile(
        ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(expected_files, key=lambda item: item.as_posix().lower()):
            if path.is_relative_to(INSTALL):
                arcname = path.relative_to(INSTALL).as_posix()
            else:
                arcname = path.relative_to(OUTPUT).as_posix()
            archive.write(path, arcname)
    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        assert archive.testzip() is None
        names = archive.namelist()
    assert len(names) == len(set(names)) == len(expected_files)
    return {
        "path": str(ZIP_PATH),
        "size": ZIP_PATH.stat().st_size,
        "sha256": _sha256_file(ZIP_PATH),
        "entries": names,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true",
                        help="Back up and install into KOTOR 1.")
    parser.add_argument("--zip", action="store_true",
                        help="Write the distributable zip (after game test).")
    args = parser.parse_args(argv)

    assert K1.is_dir(), K1
    assert SOURCE.is_dir(), f"put the user's three files in {SOURCE}"
    OVERRIDE.mkdir(parents=True, exist_ok=True)
    MODULES.mkdir(parents=True, exist_ok=True)

    donor = _assess_donor_model()
    texture, texture_details = _fix_texture()
    (OVERRIDE / f"{TEXTURE_RESREF}.tga").write_bytes(texture)
    appearance, appearance_details = _validate_appearance()
    (OVERRIDE / "appearance.2da").write_bytes(appearance)
    utc_bytes, utc_details = _validate_utc()
    module_bytes, module_build = _build_module(utc_bytes)
    MODULE.write_bytes(module_bytes)
    module_validation = _validate_module(MODULE)
    _write_readme()

    report = {
        "schema": "shadow_kinrath_plcaa_demo_v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "game": "KOTOR 1",
        "donor_model": donor,
        "texture": texture_details,
        "appearance": appearance_details,
        "creature_template": utc_details,
        "module_build": module_build,
        "module_validation": module_validation,
    }
    if args.install:
        report["install"] = _install()
    if args.zip:
        report["zip"] = _write_zip([
            OVERRIDE / f"{TEXTURE_RESREF}.tga",
            OVERRIDE / "appearance.2da",
            MODULE,
            README,
            MANIFEST,
        ])
    MANIFEST.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "texture": texture_details["fixed"],
        "appearance_row": APPEARANCE_ROW,
        "module": module_validation["sha256"],
        "installed": bool(args.install),
        "zipped": bool(args.zip),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
