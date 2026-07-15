"""Build the portable K1 dual Sith-Ithorian PLCaa fight demo.

This package deliberately treats the retail-proven ``c_ithlord`` MDL/MDX as
immutable animation truth.  The purple-eyed variant is an equal-length binary
identity/texture rename to ``c_ithpurp``; no node, hierarchy, controller,
animation, hook, mesh, or MDX data is regenerated.

The bundled PLCaa module starts from the user-approved clean arena and embeds
four uniquely named UTCs: two Jedi Knights on stock faction 16 and the two
Ithorians on stock faction 17.  Those factions are mutually hostile, friendly
to themselves, and neutral to the player, so the fight starts through K1's
default AI without module scripts.

Default behavior is stage/package only.  This script never installs files,
launches KOTOR, clears currentgame, or changes the accepted source package.
"""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile


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
from scripts.build_dathomir_rancor import twoda_to_binary_v2b  # noqa: E402
from src.core.assets.resource_manager import (  # noqa: E402
    RES_2DA,
    RES_NCS,
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
SOURCE_PACKAGE = Path(
    r"C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters"
    r"\SithIthorianScholar\MDL"
)
CLEAN_MAP = (
    ROOT / "artifacts" / "lorum_ipsat_plcaa_clean_dev_map"
    / "Modules" / "PLCaa.mod"
)
OUTPUT = ROOT / "artifacts" / "sith_ithorian_dual_variant_demo"
INSTALL = OUTPUT / "install"
OVERRIDE = INSTALL / "Override"
MODULES = INSTALL / "Modules"
MODULE = MODULES / "PLCaa.mod"
README = OUTPUT / "README.txt"
MANIFEST = OUTPUT / "validation_manifest.json"
ZIP_PATH = ROOT / "artifacts" / "Sith_Ithorian_Dual_Variant_PLCaa_Demo.zip"

# T2573: golden/purple hashes advanced when the engine death-variant slots
# (die1/dead1/die3/dead3) were routed to the native Ithorian cdie/cdead.
# T2574: advanced again when getupdead/getupdead1 were routed to cgustandb.
# T2575: advanced again when the cpause2 chin-touch left arm was IK-corrected
# to the vanilla head-relative contact (pause2 alias refreshed with it).
GOLDEN_MDL_SHA256 = (
    "fcd161709ed5e87daba335cab984099f3f15af067fc525a1bd80ab9494c7eb0e"
)
GOLDEN_MDX_SHA256 = (
    "be156cc8ccd0f2e225d66f385ae37713f52874f957cfeb3e74c5f981ec4677b1"
)
PURPLE_MDL_SHA256 = (
    "c3fa3cd6dffd9c1a516c6f5ae4892967a84228e52ee751aaf7f43627a97cca86"
)
CLEAN_MAP_SHA256 = (
    "259b7ae81852ae382d4b81ac5a937c939a78f6f8db7c166ba2ef08eb17760f0a"
)
LORD_TEXTURE_SHA256 = (
    "078c9e050d966302b2da1fb4700a3acb1bdb469229c917e989a98427e7fc55e8"
)
PURPLE_TEXTURE_SHA256 = (
    "3081c74071bd0611cb58da70ba29c6d79214b13e026bbbaf48cb524fe9d8e230"
)

RES_UTC = 2027
RESOURCE_EXTENSIONS = dict(plcaa.MODULE_EXTENSIONS)
RESOURCE_EXTENSIONS[RES_UTC] = "utc"

LORD_RESREF = "c_ithlord"
PURPLE_RESREF = "c_ithpurp"
LORD_TEXTURE = "c_ithlord_t00"
PURPLE_TEXTURE = "c_ithpurp_t00"
LORUM_RED_SABER = "g_w_lghtsbr06"
APPEARANCE_TEMPLATE_ROW = 72

JEDI_FACTION = 16
ITHORIAN_FACTION = 17
PLAYER_FACTION = 0

PLACEMENTS = (
    # Unique module-local UTC, display role, X, Y, Z, facing X, facing Y.
    ("li_jedi_a", "Jedi Knight - Blue", 26.0, 36.0, 0.0, 0.0, 1.0),
    ("li_jedi_b", "Jedi Knight - Green", 32.0, 36.0, 0.0, 0.0, 1.0),
    ("li_ith_purple", "Violet-Eyed Sith", 26.0, 43.0, 0.0, 0.0, -1.0),
    ("li_ith_lord", "Lorum Ipsat", 32.0, 43.0, 0.0, 0.0, -1.0),
)

NATIVE_ITHORIAN_CLIPS = {
    "cdamages", "cdead", "cdie", "cdodgeg", "cgustandb",
    "chturnl", "chturnr", "cpause1", "cpause2", "crun", "ctaunt",
    "cvictory", "cwalk", "cwalkinj", "listen", "tlknorm",
}
REQUIRED_MALAK_COMBAT_CLIPS = {
    *(f"c2a{i}" for i in range(1, 7)),
    *(f"c2p{i}" for i in range(1, 6)),
    *(f"c2d{i}" for i in range(1, 6)),
    *(f"c2n{i}" for i in range(1, 3)),
    *(f"f2a{i}" for i in range(1, 5)),
    *(f"f2d{i}" for i in range(1, 4)),
    *(f"f2p{i}" for i in range(1, 4)),
    "g2r1", "g2w1", "tlkforce",
    "castout1", "castout2", "castout3",
    "castoutlp1", "castoutlp2", "castoutlp3",
    "choke", "fear", "horror", "sleep", "whirlwind",
    "throwsab", "throwsablp", "catchsab",
    "g1x1", "g1y1", "g1z1", "taunt", "kd",
    "g0a1", "g0a2", "creadyr",
}
MALAK_COMBAT_ALIASES = {
    "g0a1": "c2a1",
    "g0a2": "c2a2",
    "creadyr": "g2r1",
    "c2a6": "c2a5",
}
MODELTYPE_F_NATIVE_STATE_ALIASES = {
    "pause1": "cpause1",
    "pause2": "cpause2",
    "die": "cdie",
    "dead": "cdead",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _set_scalar(root, label: str, value) -> None:
    field = root.fields[label]
    current = field.value
    if isinstance(current, float):
        field.value = float(value)
    elif isinstance(current, int):
        field.value = int(value)
    elif isinstance(current, str):
        field.value = str(value)
    else:
        field.value = type(current)(value)


def _set_resref(root, label: str, value: str) -> None:
    field = root.fields[label]
    field.value = type(field.value)(value)


def _set_name(root, text: str) -> None:
    name = root.fields["FirstName"].value
    name.strref = -1
    name.strings.clear()
    name.set_text(text, name.LANG_ENGLISH)
    last = root.fields.get("LastName")
    if last is not None and hasattr(last.value, "strings"):
        last.value.strref = -1
        last.value.strings.clear()


def _set_equipment(root, slot: int, resref: str) -> None:
    matches = []
    for item in root.fields["Equip_ItemList"].value:
        if int(getattr(item, "type_id", -1)) != int(slot):
            continue
        equipped = item.fields["EquippedRes"]
        equipped.value = type(equipped.value)(resref)
        matches.append(str(equipped.value).lower())
    assert matches == [resref.lower()], (slot, resref, matches)


def _rim_resource_bytes(rim_path: Path, resref: str, restype: int) -> bytes:
    data = rim_path.read_bytes()
    assert data[:8] == b"RIM V1.0", rim_path
    count, table_offset = struct.unpack_from("<II", data, 0x0C)
    for index in range(count):
        entry = table_offset + index * 32
        name = data[entry:entry + 16].split(b"\0", 1)[0].decode("ascii")
        entry_type, _resource_id, offset, size = struct.unpack_from(
            "<IIII", data, entry + 16
        )
        if entry_type == restype and name.lower() == resref.lower():
            return data[offset:offset + size]
    raise AssertionError((rim_path, resref, restype))


def _clone_purple_model(golden_mdl: bytes) -> tuple[bytes, dict]:
    """Rename nine equal-length fixed fields without rewriting the model."""

    old = LORD_RESREF.encode("ascii")
    new = PURPLE_RESREF.encode("ascii")
    assert len(old) == len(new) == 9
    assert _sha256_bytes(golden_mdl) == GOLDEN_MDL_SHA256
    assert golden_mdl.count(old) == 9
    assert golden_mdl[20:20 + len(old)] == old

    clone = golden_mdl.replace(old, new)
    differences = [
        index
        for index, (before, after) in enumerate(
            zip(golden_mdl, clone, strict=True)
        )
        if before != after
    ]
    assert len(clone) == len(golden_mdl)
    assert clone.count(old) == 0
    assert clone.count(new) == 9
    assert clone[20:20 + len(new)] == new
    assert len(differences) == 27, differences
    assert _sha256_bytes(clone) == PURPLE_MDL_SHA256
    return clone, {
        "strategy": "equal_length_fixed_field_binary_clone",
        "source_resref": LORD_RESREF,
        "target_resref": PURPLE_RESREF,
        "replaced_fixed_fields": 9,
        "changed_bytes": len(differences),
        "changed_offsets": differences,
        "sha256": _sha256_bytes(clone),
    }


def _model_parent_map(model) -> dict[str, str]:
    return {
        str(node.name or "").lower(): (
            str(node.parent.name or "").lower()
            if getattr(node, "parent", None) is not None else ""
        )
        for node in model.all_nodes()
    }


def _animation_payload_signature(animation) -> tuple:
    return (
        float(getattr(animation, "length", 0.0) or 0.0),
        float(getattr(animation, "transition_time", 0.0) or 0.0),
        str(getattr(animation, "anim_root", "") or ""),
        tuple(
            (float(event.time), str(event.name))
            for event in (animation.events or [])
        ),
        tuple(
            (
                str(getattr(node, "name", "") or ""),
                str(getattr(getattr(node, "parent", None), "name", "") or ""),
                int(getattr(node, "flags", 0) or 0),
                tuple(float(value) for value in (getattr(node, "position", ()) or ())),
                tuple(float(value) for value in (getattr(node, "rotation", ()) or ())),
                tuple(getattr(node, "controllers", ()) or ()),
            )
            for node in (animation.nodes or [])
        ),
    )


def _model_contract(mdl: bytes, mdx: bytes, expected_name: str) -> dict:
    from src.core.game.kotor_loader import load_model_from_bytes

    model = load_model_from_bytes(mdl, mdx)
    assert model is not None
    assert str(model.name or "").lower() == expected_name.lower()
    nodes = list(model.all_nodes())
    parent_map = _model_parent_map(model)
    animations = list(model.animations or [])
    animation_names = [str(animation.name or "").lower() for animation in animations]
    assert len(animation_names) == len(set(animation_names))
    assert len(animation_names) >= 284
    assert NATIVE_ITHORIAN_CLIPS <= set(animation_names)
    assert REQUIRED_MALAK_COMBAT_CLIPS <= set(animation_names)
    animation_by_name = dict(zip(animation_names, animations, strict=True))
    for target_name, source_name in MODELTYPE_F_NATIVE_STATE_ALIASES.items():
        assert _animation_payload_signature(
            animation_by_name[target_name]
        ) == _animation_payload_signature(animation_by_name[source_name]), (
            target_name, source_name)
    for target_name, source_name in MALAK_COMBAT_ALIASES.items():
        target_signature = _animation_payload_signature(animation_by_name[target_name])
        source_signature = _animation_payload_signature(animation_by_name[source_name])
        if target_name in {"g0a1", "g0a2"}:
            # Solo fallback aliases intentionally omit synchronized clash cues.
            target_signature = target_signature[:3] + target_signature[4:]
            source_signature = source_signature[:3] + source_signature[4:]
        assert target_signature == source_signature, (target_name, source_name)
    assert all(
        str(animation.anim_root or "").lower() == "c_ithorian"
        for animation in animations
    )

    mismatches = []
    for animation in animations:
        for node in animation.nodes or []:
            name = str(node.name or "").lower()
            parent = getattr(node, "parent", None)
            actual_parent = str(parent.name or "").lower() if parent else ""
            if name not in parent_map or actual_parent != parent_map[name]:
                mismatches.append((str(animation.name), name, actual_parent))
    assert not mismatches, mismatches[:10]

    hook_contract = {}
    for hook_name, parent_name in (("rhand", "rhand_g"), ("lhand", "lhand_g")):
        hook = model.find_node(hook_name)
        assert hook is not None
        assert str(hook.parent.name or "").lower() == parent_name
        controller_types = sorted({
            int(controller.get("type", controller.get("controller_type", 0)) or 0)
            for controller in hook.controllers
        })
        assert {8, 20} <= set(controller_types), (hook_name, controller_types)
        hook_contract[hook_name] = {
            "parent": parent_name,
            "controller_types": controller_types,
        }

    textures = sorted({
        str(getattr(node, "texture", "") or "").lower()
        for node in nodes
        if str(getattr(node, "texture", "") or "")
    })
    expected_texture = f"{expected_name}_t00".lower()
    assert expected_texture in textures, (expected_texture, textures)
    return {
        "name": str(model.name),
        "node_count": len(nodes),
        "animation_count": len(animations),
        "unique_animation_count": len(set(animation_names)),
        "animation_parent_mismatches": 0,
        "native_dialogue_idle_clips": sorted(NATIVE_ITHORIAN_CLIPS),
        "required_malak_combat_clips": sorted(REQUIRED_MALAK_COMBAT_CLIPS),
        "malak_combat_aliases": dict(MALAK_COMBAT_ALIASES),
        "hooks": hook_contract,
        "textures": textures,
    }


def _validate_tga(path: Path, expected_sha256: str) -> dict:
    data = path.read_bytes()
    assert _sha256_bytes(data) == expected_sha256, path
    assert len(data) >= 18
    width, height = struct.unpack_from("<HH", data, 12)
    bits_per_pixel = data[16]
    assert (width, height, bits_per_pixel) == (2048, 2048, 32)
    return {
        "size": len(data),
        "sha256": expected_sha256,
        "width": width,
        "height": height,
        "bits_per_pixel": bits_per_pixel,
    }


def _build_appearance() -> tuple[bytes, dict]:
    manager = ResourceManager()
    assert manager.set_k1_dir(str(K1))
    vanilla = manager.get_k1().get_bif("appearance", RES_2DA)
    assert vanilla
    table = TwoDA.from_bytes(vanilla)
    assert len(table) == 509, len(table)
    for resref in (LORD_RESREF, PURPLE_RESREF):
        assert not any(
            str(table.get(index, "race") or "").lower() == resref
            for index in range(len(table))
        )

    race_col = table.col_index("race")
    label_col = table.col_index("label")
    modeltype_col = table.col_index("modeltype")
    hasarms_col = table.col_index("hasarms")
    normalhead_col = table.col_index("normalhead")
    racetex_col = table.col_index("racetex")
    rows = {}
    for resref, label in (
        (LORD_RESREF, "Alien_Ithorian_SithLord"),
        (PURPLE_RESREF, "Alien_Ithorian_PurpleEyes"),
    ):
        row = len(table)
        table._rows.append(list(table._rows[APPEARANCE_TEMPLATE_ROW]))
        table._rows[row][race_col] = resref
        table._rows[row][label_col] = label
        table._rows[row][modeltype_col] = "F"
        table._rows[row][hasarms_col] = "1"
        table._rows[row][normalhead_col] = ""
        table._rows[row][racetex_col] = ""
        rows[resref] = row
    assert rows == {LORD_RESREF: 509, PURPLE_RESREF: 510}

    data = twoda_to_binary_v2b(table)
    check = TwoDA.from_bytes(data)
    assert len(check) == 511
    vanilla_check = TwoDA.from_bytes(vanilla)
    for row in range(len(vanilla_check)):
        for column in vanilla_check.columns:
            assert (check.get(row, column) or "") == (
                vanilla_check.get(row, column) or ""
            ), (row, column)
    for resref, row in rows.items():
        assert str(check.get(row, "race") or "").lower() == resref
        assert str(check.get(row, "modeltype") or "").upper() == "F"
        assert str(check.get(row, "hasarms") or "") == "1"
        assert not str(check.get(row, "normalhead") or "")
        assert not str(check.get(row, "racetex") or "")
    return data, {
        "source": "K1:CHITIN:appearance.2da",
        "row_count": len(check),
        "rows": rows,
        "modeltype": "F",
        "hasarms": "1",
        "sha256": _sha256_bytes(data),
    }


def _normalise_combatant(
    root,
    *,
    resref: str,
    display_name: str,
    faction: int,
    appearance: int,
    alignment: int,
) -> None:
    _set_resref(root, "TemplateResRef", resref)
    _set_scalar(root, "Tag", resref)
    _set_name(root, display_name)
    _set_scalar(root, "Appearance_Type", appearance)
    _set_scalar(root, "FactionID", faction)
    _set_scalar(root, "GoodEvil", alignment)
    _set_scalar(root, "HitPoints", 100)
    _set_scalar(root, "CurrentHitPoints", 100)
    _set_scalar(root, "MaxHitPoints", 100)
    if "ForcePoints" in root.fields:
        _set_scalar(root, "ForcePoints", 64)
    if "CurrentForce" in root.fields:
        _set_scalar(root, "CurrentForce", 64)
    if "ChallengeRating" in root.fields:
        _set_scalar(root, "ChallengeRating", 8.0)
    for label in ("Plot", "Min1HP", "NoPermDeath"):
        if label in root.fields:
            _set_scalar(root, label, 0)
    _set_resref(root, "ScriptSpawn", "k_def_spawn01")
    _set_resref(root, "ScriptUserDefine", "k_def_userdef01")


def _build_creature_templates() -> tuple[dict[tuple[str, int], bytes], dict]:
    lord_source = read_gff((SOURCE_PACKAGE / "sithlord01.utc").read_bytes())
    jedi_source = read_gff(_rim_resource_bytes(
        K1 / "modules" / "sta_m45aa_s.rim", "sta_jedi001", RES_UTC
    ))

    templates = {}
    details = {}

    for resref, display, appearance in (
        ("li_ith_lord", "Lorum Ipsat", 509),
        ("li_ith_purple", "Violet-Eyed Sith", 510),
    ):
        utc = copy.deepcopy(lord_source)
        root = utc.root
        _normalise_combatant(
            root,
            resref=resref,
            display_name=display,
            faction=ITHORIAN_FACTION,
            appearance=appearance,
            alignment=10,
        )
        _set_equipment(root, 16, LORUM_RED_SABER)
        data = write_gff(utc)
        templates[(resref, RES_UTC)] = data
        details[resref] = _creature_contract(data)

    for resref, display, appearance, saber in (
        ("li_jedi_a", "Jedi Knight - Blue", 205, "g_w_lghtsbr01"),
        ("li_jedi_b", "Jedi Knight - Green", 216, "g_w_lghtsbr03"),
    ):
        utc = copy.deepcopy(jedi_source)
        root = utc.root
        _normalise_combatant(
            root,
            resref=resref,
            display_name=display,
            faction=JEDI_FACTION,
            appearance=appearance,
            alignment=90,
        )
        classes = root.fields["ClassList"].value
        assert len(classes) == 1
        _set_scalar(classes[0], "ClassLevel", 8)
        _set_equipment(root, 16, saber)
        data = write_gff(utc)
        templates[(resref, RES_UTC)] = data
        details[resref] = _creature_contract(data)

    assert set(details) == {row[0] for row in PLACEMENTS}
    return templates, details


def _creature_contract(data: bytes) -> dict:
    root = read_gff(data).root
    resref = str(root.fields["TemplateResRef"].value).lower()
    name = root.fields["FirstName"].value
    classes = root.fields["ClassList"].value
    assert name.strref == -1 and name.english
    assert str(root.fields["Tag"].value).lower() == resref
    assert int(root.fields["HitPoints"].value) == 100
    assert int(root.fields["CurrentHitPoints"].value) == 100
    assert int(root.fields["MaxHitPoints"].value) == 100
    perception_range = int(root.fields["PerceptionRange"].value)
    assert perception_range == 11
    assert str(root.fields["ScriptSpawn"].value).lower() == "k_def_spawn01"
    assert str(root.fields["ScriptUserDefine"].value).lower() == "k_def_userdef01"
    assert int(root.fields.get("Plot").value or 0) == 0
    assert int(root.fields.get("Min1HP").value or 0) == 0
    equipment = {
        int(item.type_id): str(item.fields["EquippedRes"].value).lower()
        for item in root.fields["Equip_ItemList"].value
    }
    return {
        "resref": resref,
        "name": name.english,
        "appearance": int(root.fields["Appearance_Type"].value),
        "faction": int(root.fields["FactionID"].value),
        "alignment": int(root.fields["GoodEvil"].value),
        "class": int(classes[0].fields["Class"].value),
        "level": int(classes[0].fields["ClassLevel"].value),
        "hit_points": int(root.fields["MaxHitPoints"].value),
        "force_points": int(root.fields.get("ForcePoints").value or 0),
        "perception_range": perception_range,
        "right_hand": equipment.get(16, ""),
        "spawn_script": str(root.fields["ScriptSpawn"].value),
        "user_defined_script": str(root.fields["ScriptUserDefine"].value),
        "sha256": _sha256_bytes(data),
    }


def _validate_reputation() -> dict:
    manager = ResourceManager()
    assert manager.set_k1_dir(str(K1))
    table = TwoDA.from_bytes(manager.get("repute", RES_2DA, "K1"))
    assert str(table.get(PLAYER_FACTION, "gizka_1")) == "50"
    assert str(table.get(PLAYER_FACTION, "gizka_2")) == "50"
    assert str(table.get(2, "gizka_1")) == "50"
    assert str(table.get(2, "gizka_2")) == "50"
    assert str(table.get(JEDI_FACTION, "gizka_1")) == "100"
    assert str(table.get(JEDI_FACTION, "gizka_2")) == "0"
    assert str(table.get(ITHORIAN_FACTION, "gizka_1")) == "0"
    assert str(table.get(ITHORIAN_FACTION, "gizka_2")) == "100"
    return {
        "source": "K1:CHITIN:repute.2da",
        "player_to_jedi": 50,
        "player_to_ithorian": 50,
        "party_to_jedi": 50,
        "party_to_ithorian": 50,
        "jedi_to_jedi": 100,
        "ithorian_to_ithorian": 100,
        "jedi_to_ithorian": 0,
        "ithorian_to_jedi": 0,
    }


def _validate_default_scripts() -> list[str]:
    manager = ResourceManager()
    assert manager.set_k1_dir(str(K1))
    scripts = (
        "k_def_spawn01", "k_def_userdef01", "k_def_heartbt01",
        "k_def_percept01", "k_def_spellat01", "k_def_attacked01",
        "k_def_damage01", "k_def_disturb01", "k_def_combend01",
        "k_def_dialogue01", "k_def_death01", "k_def_blocked01",
    )
    for resref in scripts:
        assert manager.get(resref, RES_NCS, "K1"), resref
    return list(scripts)


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


def _build_module(
    templates: dict[tuple[str, int], bytes],
) -> tuple[bytes, dict]:
    assert CLEAN_MAP.is_file(), CLEAN_MAP
    assert _sha256_file(CLEAN_MAP) == CLEAN_MAP_SHA256
    base = plcaa._resource_map(CLEAN_MAP)
    assert len(base) == 9
    resources = dict(base)

    git = read_gff(resources[("plcaa", plcaa.RES_GIT)])
    for label in plcaa.DYNAMIC_GIT_LISTS:
        if label in git.root.fields:
            git.root.fields[label].value[:] = []
    donor = plcaa._vanilla_creature_instance()
    for resref, _display, x, y, z, facing_x, facing_y in PLACEMENTS:
        instance = copy.deepcopy(donor)
        fields = instance.fields
        fields["TemplateResRef"].value = type(
            fields["TemplateResRef"].value
        )(resref)
        fields["XPosition"].value = float(x)
        fields["YPosition"].value = float(y)
        fields["ZPosition"].value = float(z)
        fields["XOrientation"].value = float(facing_x)
        fields["YOrientation"].value = float(facing_y)
        git.root.fields["Creature List"].value.append(instance)
    resources[("plcaa", plcaa.RES_GIT)] = write_gff(git)
    resources.update(templates)

    wok = WOKData.from_bytes(resources[("plcaa", plcaa.RES_WOK)])
    runtime = WalkmeshRuntimeIndex(wok, game="K1")
    placement_details = []
    for resref, display, x, y, z, facing_x, facing_y in PLACEMENTS:
        sample = runtime.sample_at(x, y, z)
        assert sample is not None, (resref, x, y, z)
        placement_details.append({
            "template": resref,
            "display": display,
            "position": [x, y, z],
            "facing": [facing_x, facing_y],
            "wok_face": int(sample.face_index),
            "surface": int(sample.surface_id),
        })
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
                else "dual-demo-module-local-UTC"
            ),
            changed=(restype in {plcaa.RES_GIT, RES_UTC}),
            serializer="sith_ithorian_dual_demo",
            warning=None,
        ))
    module_bytes = msp.build_erf_v1_archive(entries, archive_type="MOD")

    # All eight non-GIT resources from the approved map must be byte-identical.
    for key, data in base.items():
        if key != ("plcaa", plcaa.RES_GIT):
            assert resources[key] == data, key

    visual_cleanup = plcaa._validate_disabled_stock_demo_visuals(
        resources[("plcaa", plcaa.RES_MDL)],
        resources[("plcaa", plcaa.RES_MDX)],
    )
    return module_bytes, {
        "base_module": str(CLEAN_MAP),
        "base_sha256": CLEAN_MAP_SHA256,
        "resource_count": len(resources),
        "preserved_non_git_resource_count": 8,
        "placements": placement_details,
        "player_entry": {
            "position": list(plcaa.PLAYER_ENTRY[:3]),
            "facing": list(plcaa.PLAYER_ENTRY[3:]),
            "wok_face": int(player_sample.face_index),
            "surface": int(player_sample.surface_id),
        },
        "visual_cleanup": visual_cleanup,
        "engine_contract": _engine_contract(resources),
    }


def _validate_module(path: Path) -> dict:
    resources = plcaa._resource_map(path)
    expected_templates = {row[0] for row in PLACEMENTS}
    assert len(resources) == 13
    assert {
        resref for (resref, restype) in resources if restype == RES_UTC
    } == expected_templates

    git = read_gff(resources[("plcaa", plcaa.RES_GIT)])
    counts = {
        label: len(git.root.fields[label].value)
        if label in git.root.fields else 0
        for label in plcaa.DYNAMIC_GIT_LISTS
    }
    refs = [
        str(item.fields["TemplateResRef"].value).lower()
        for item in git.root.fields["Creature List"].value
    ]
    assert refs == [row[0] for row in PLACEMENTS], refs
    expected_instance_fields = {
        "TemplateResRef", "XPosition", "YPosition", "ZPosition",
        "XOrientation", "YOrientation",
    }
    for instance, placement in zip(
        git.root.fields["Creature List"].value, PLACEMENTS, strict=True
    ):
        assert set(instance.fields) == expected_instance_fields
        _resref, _display, x, y, z, facing_x, facing_y = placement
        assert (
            float(instance.fields["XPosition"].value),
            float(instance.fields["YPosition"].value),
            float(instance.fields["ZPosition"].value),
            float(instance.fields["XOrientation"].value),
            float(instance.fields["YOrientation"].value),
        ) == (x, y, z, facing_x, facing_y)
    assert counts["Creature List"] == 4
    assert all(
        count == 0 for label, count in counts.items()
        if label != "Creature List"
    ), counts

    template_contracts = {
        resref: _creature_contract(resources[(resref, RES_UTC)])
        for resref in sorted(expected_templates)
    }
    assert {
        template_contracts["li_jedi_a"]["faction"],
        template_contracts["li_jedi_b"]["faction"],
    } == {JEDI_FACTION}
    assert {
        template_contracts["li_ith_lord"]["faction"],
        template_contracts["li_ith_purple"]["faction"],
    } == {ITHORIAN_FACTION}
    assert template_contracts["li_ith_lord"]["appearance"] == 509
    assert template_contracts["li_ith_purple"]["appearance"] == 510
    assert all(
        contract["perception_range"] == 11
        for contract in template_contracts.values()
    )

    wok = WOKData.from_bytes(resources[("plcaa", plcaa.RES_WOK)])
    runtime = WalkmeshRuntimeIndex(wok, game="K1")
    assert all(
        runtime.sample_at(row[2], row[3], row[4]) is not None
        for row in PLACEMENTS
    )

    ifo = read_gff(resources[("module", plcaa.RES_IFO)])
    are = read_gff(resources[("plcaa", plcaa.RES_ARE)])
    assert str(ifo.root.fields["Mod_Entry_Area"].value).lower() == "plcaa"
    assert all(
        not str(ifo.root.fields[label].value)
        for label in plcaa.IFO_EVENT_FIELDS if label in ifo.root.fields
    )
    assert all(
        not str(are.root.fields[label].value)
        for label in plcaa.ARE_EVENT_FIELDS if label in are.root.fields
    )
    assert not any(restype == 2010 for _resref, restype in resources)

    visual_cleanup = plcaa._validate_disabled_stock_demo_visuals(
        resources[("plcaa", plcaa.RES_MDL)],
        resources[("plcaa", plcaa.RES_MDX)],
    )
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": _sha256_file(path),
        "resource_count": len(resources),
        "creature_refs": refs,
        "dynamic_git_counts": counts,
        "templates": template_contracts,
        "module_and_area_event_scripts_blank": True,
        "custom_script_resource_count": 0,
        "visual_cleanup": visual_cleanup,
        "engine_contract": _engine_contract(resources),
    }


def _write_readme() -> None:
    README.write_text(
        """Sith Ithorian Dual-Variant PLCaa Fight Demo - KOTOR 1
=========================================================

What this contains
------------------
- The retail-tested c_ithlord model with the orange Sith Lord texture.
- A fresh c_ithpurp clone using the purple-eye texture. Its skeleton, complete
  animation inventory, N_DarthMalak combat payload, and weapon hooks are inherited byte-for-byte
  from the working model.
- The clean PLCaa development arena.
- Two Jedi Knights versus Lorum Ipsat and the Violet-Eyed Sith.

The teams use stock KOTOR factions that are hostile to each other but neutral
to the player. No custom combat-start script is needed: enter and watch.

Recommended game test
---------------------
1. Sign into the Steam account that owns the save you intend to load.
2. Load a save made outside PLCaa (or start a new game).
3. Use: warp plcaa

Do not load a save made inside an older PLCaa before testing. KOTOR stores each
visited module's runtime creature state inside the save and will restore that
older state over the newly installed GIT. If save thumbnails are blank or white,
stop and verify the active Steam account before loading anything.

Install (clean/test KOTOR 1 setup)
----------------------------------
1. Close KOTOR 1.
2. Back up your existing Override\\appearance.2da and Modules\\PLCaa.mod.
3. Copy the contents of this package's Override folder into KOTOR's Override.
4. Copy Modules\\PLCaa.mod into KOTOR's Modules folder.
5. Remove a stale currentgame\\PLCaa.mod only if one exists from an older test.
6. Start KOTOR 1, load a save outside PLCaa, and use: warp plcaa

Compatibility warning
---------------------
This test package supplies a complete appearance.2da built from vanilla KOTOR 1
plus rows 509 and 510. On a modded installation, merge those two rows instead
of overwriting another mod's appearance.2da. The package also replaces PLCaa.mod.

Uninstall
---------
Restore your backed-up appearance.2da and PLCaa.mod, then remove these files:
c_ithlord.mdl, c_ithlord.mdx, c_ithlord_t00.tga,
c_ithpurp.mdl, c_ithpurp.mdx, c_ithpurp_t00.tga.

Validation details are in validation_manifest.json. The package is staged only;
the builder does not install files, launch KOTOR, or alter saves.
""",
        encoding="utf-8",
    )


def _write_zip(expected_files: list[Path]) -> dict:
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
        names = archive.namelist()
        bad = archive.testzip()
        assert bad is None, bad
        inventory = [
            {"name": info.filename, "size": info.file_size, "crc": info.CRC}
            for info in archive.infolist()
        ]
    assert len(names) == len(set(names)) == len(expected_files)
    return {
        "path": str(ZIP_PATH),
        "size": ZIP_PATH.stat().st_size,
        "sha256": _sha256_file(ZIP_PATH),
        "entry_count": len(names),
        "entries": inventory,
    }


def main() -> int:
    assert K1.is_dir(), K1
    assert SOURCE_PACKAGE.is_dir(), SOURCE_PACKAGE
    OVERRIDE.mkdir(parents=True, exist_ok=True)
    MODULES.mkdir(parents=True, exist_ok=True)

    golden_mdl = (SOURCE_PACKAGE / "c_ithlord.mdl").read_bytes()
    golden_mdx = (SOURCE_PACKAGE / "c_ithlord.mdx").read_bytes()
    assert _sha256_bytes(golden_mdl) == GOLDEN_MDL_SHA256
    assert _sha256_bytes(golden_mdx) == GOLDEN_MDX_SHA256
    purple_mdl, clone_details = _clone_purple_model(golden_mdl)

    (OVERRIDE / "c_ithlord.mdl").write_bytes(golden_mdl)
    (OVERRIDE / "c_ithlord.mdx").write_bytes(golden_mdx)
    (OVERRIDE / "c_ithpurp.mdl").write_bytes(purple_mdl)
    (OVERRIDE / "c_ithpurp.mdx").write_bytes(golden_mdx)

    lord_texture_source = SOURCE_PACKAGE / "c_ithlord_t00.tga"
    purple_texture_source = SOURCE_PACKAGE / "c_ithschol_t00.tga"
    lord_texture = lord_texture_source.read_bytes()
    purple_texture = purple_texture_source.read_bytes()
    (OVERRIDE / "c_ithlord_t00.tga").write_bytes(lord_texture)
    (OVERRIDE / "c_ithpurp_t00.tga").write_bytes(purple_texture)
    texture_details = {
        "c_ithlord_t00.tga": _validate_tga(
            OVERRIDE / "c_ithlord_t00.tga", LORD_TEXTURE_SHA256
        ),
        "c_ithpurp_t00.tga": _validate_tga(
            OVERRIDE / "c_ithpurp_t00.tga", PURPLE_TEXTURE_SHA256
        ),
    }

    appearance, appearance_details = _build_appearance()
    (OVERRIDE / "appearance.2da").write_bytes(appearance)
    templates, template_details = _build_creature_templates()
    module_bytes, module_build = _build_module(templates)
    MODULE.write_bytes(module_bytes)
    module_validation = _validate_module(MODULE)

    model_details = {
        LORD_RESREF: {
            "mdl_sha256": _sha256_bytes(golden_mdl),
            "mdx_sha256": _sha256_bytes(golden_mdx),
            "contract": _model_contract(golden_mdl, golden_mdx, LORD_RESREF),
        },
        PURPLE_RESREF: {
            "mdl_sha256": _sha256_bytes(purple_mdl),
            "mdx_sha256": _sha256_bytes(golden_mdx),
            "clone": clone_details,
            "contract": _model_contract(purple_mdl, golden_mdx, PURPLE_RESREF),
        },
    }
    assert model_details[LORD_RESREF]["contract"]["animation_count"] >= 284
    assert (
        model_details[PURPLE_RESREF]["contract"]["animation_count"]
        == model_details[LORD_RESREF]["contract"]["animation_count"]
    )

    reputation = _validate_reputation()
    default_scripts = _validate_default_scripts()
    _write_readme()

    report = {
        "schema": "sith_ithorian_dual_variant_plcaa_demo_v3",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "game": "KOTOR 1",
        "installed": False,
        "golden_source": {
            "directory": str(SOURCE_PACKAGE),
            "mdl_sha256": GOLDEN_MDL_SHA256,
            "mdx_sha256": GOLDEN_MDX_SHA256,
            "clean_map_sha256": CLEAN_MAP_SHA256,
        },
        "models": model_details,
        "textures": texture_details,
        "appearance": appearance_details,
        "creature_templates": template_details,
        "reputation": reputation,
        "resolved_default_scripts": default_scripts,
        "module_build": module_build,
        "module_validation": module_validation,
        "package_files": {},
    }
    package_files = [
        OVERRIDE / "c_ithlord.mdl",
        OVERRIDE / "c_ithlord.mdx",
        OVERRIDE / "c_ithlord_t00.tga",
        OVERRIDE / "c_ithpurp.mdl",
        OVERRIDE / "c_ithpurp.mdx",
        OVERRIDE / "c_ithpurp_t00.tga",
        OVERRIDE / "appearance.2da",
        MODULE,
        README,
    ]
    report["package_files"] = {
        (
            path.relative_to(INSTALL).as_posix()
            if path.is_relative_to(INSTALL)
            else path.relative_to(OUTPUT).as_posix()
        ): {
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in package_files
    }
    MANIFEST.write_text(json.dumps(report, indent=2), encoding="utf-8")
    package_files.append(MANIFEST)
    zip_details = _write_zip(package_files)

    result = {
        "output": str(OUTPUT),
        "zip": zip_details,
        "module": module_validation,
        "models": {
            name: {
                "mdl_sha256": details["mdl_sha256"],
                "mdx_sha256": details["mdx_sha256"],
                "animations": details["contract"]["animation_count"],
                "parent_mismatches": details["contract"][
                    "animation_parent_mismatches"
                ],
            }
            for name, details in model_details.items()
        },
        "installed": False,
    }
    (OUTPUT / "package_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
