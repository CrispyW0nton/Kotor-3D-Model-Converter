"""Recover the second KSE-edited LorumTest save without overwriting either source slot.

KSE 3.3.7a treated zero localized-string offsets in the first repaired SAV as a
relative base.  Its next commit displaced both the outer and nested SAV
directories by 0xA0 bytes, overwriting the tail of ARE and truncating the
otherwise unchanged END_M01AA and REPUTE payloads.  The edited inventory and
player IFO remain intact and are recovered here.

The script is deliberately pinned to the forensically verified input hash and
refuses to overwrite an existing backup, manifest, or destination slot.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
from datetime import datetime
from pathlib import Path
from typing import Any

from pykotor.resource.formats.erf import bytes_erf, read_erf
from pykotor.resource.formats.gff import bytes_gff, read_gff
from pykotor.resource.type import ResourceType


WORKSPACE = Path(r"C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Ghost-Studio")
SAVES = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor\saves")
PRISTINE_SLOT = SAVES / "000004 - Game3"
BROKEN_SLOT = SAVES / "000005 - Game4"
REPAIRED_SLOT = SAVES / "000006 - Game5"
STAGING = WORKSPACE / "Saved" / "GameTestStaging" / "lorumtest_repair"
BACKUP_SLOT = STAGING / "20260714T141848_game4_second_kse_edit_original"
MANIFEST = STAGING / "20260714T141848_second_repair_manifest.json"

EXPECTED_BROKEN_SAVE_HASH = "773405c75bd066757475713de478e417a98ca1958a4b3b62906c3f50d574b2bc"
EXPECTED_PRISTINE_SAVE_HASH = "2ed3768610b4cf4ef30ae7dab8c059d34521e70693fc2e00368d0fcc8da77e71"

# Verified physical anchors in the malformed second KSE output.
INVENTORY_START = 0x8A05C
PLC_START = 0x8BE18
GIT_START = 0x8BFB8
ARE_START = 0x8F2ED
IFO_START = 0x8FC20
IFO_END = 0x92792


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def slot_hashes(path: Path) -> dict[str, dict[str, Any]]:
    return {
        child.name: {"size": child.stat().st_size, "sha256": sha256_file(child)}
        for child in sorted(path.iterdir(), key=lambda item: item.name.lower())
        if child.is_file()
    }


def resource_data(erf: Any, resref: str, restype: ResourceType) -> bytes:
    for resource in erf:
        if str(resource.resref).lower() == resref.lower() and resource.restype == restype:
            return resource.data
    raise RuntimeError(f"Missing {resref}.{restype.extension} resource")


def make_kse_compatible_sav(erf: Any) -> bytes:
    """Serialize canonically and retain KSE's expected empty locstring offset."""
    output = bytearray(bytes_erf(erf, ResourceType.SAV))
    language_count, localized_size = struct.unpack_from("<II", output, 8)
    if language_count != 0 or localized_size != 0:
        raise RuntimeError("Unexpected localized strings in save archive")
    struct.pack_into("<I", output, 20, 160)
    return bytes(output)


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(f"{path.name}.repair-tmp")
    if temporary.exists():
        raise FileExistsError(f"Refusing to reuse temporary file: {temporary}")
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def player_from_ifo(ifo_bytes: bytes) -> Any:
    ifo = read_gff(ifo_bytes)
    players = ifo.root.get_list("Mod_PlayerList")
    if len(players) != 1:
        raise RuntimeError(f"Expected one active player, found {len(players)}")
    return ifo, players[0]


def feat_ids(player: Any) -> list[int]:
    return [entry.get_uint16("Feat") for entry in player.get_list("FeatList")]


def class_rows(player: Any) -> list[tuple[int, int]]:
    return [
        (entry.get_int32("Class"), entry.get_int16("ClassLevel"))
        for entry in player.get_list("ClassList")
    ]


def inventory_tags(inventory_bytes: bytes) -> list[str]:
    inventory = read_gff(inventory_bytes)
    return [entry.get_string("Tag") for entry in inventory.root.get_list("ItemList")]


def assert_archive_header(data: bytes, entry_count: int, resource_offset: int) -> None:
    fields = struct.unpack_from("<6I", data, 8)
    expected = (0, 0, entry_count, 160, 160, resource_offset)
    if fields != expected:
        raise RuntimeError(f"Archive header mismatch: got {fields}, expected {expected}")


def build_repair() -> tuple[bytes, bytes, dict[str, Any]]:
    pristine_save = (PRISTINE_SLOT / "SAVEGAME.sav").read_bytes()
    broken_save = (BROKEN_SLOT / "SAVEGAME.sav").read_bytes()
    if sha256_bytes(pristine_save) != EXPECTED_PRISTINE_SAVE_HASH:
        raise RuntimeError("Pristine Game3 hash changed; refusing to guess")
    if sha256_bytes(broken_save) != EXPECTED_BROKEN_SAVE_HASH:
        raise RuntimeError("Broken Game4 hash changed; re-run the forensic inspection")

    pristine_outer = read_erf(pristine_save)
    pristine_end = resource_data(pristine_outer, "END_M01AA", ResourceType.SAV)
    pristine_repute = resource_data(pristine_outer, "REPUTE", ResourceType.FAC)
    pristine_plc = resource_data(pristine_outer, "plcaa", ResourceType.SAV)
    pristine_nested = read_erf(pristine_plc)
    pristine_git = resource_data(pristine_nested, "plcaa", ResourceType.GIT)
    pristine_are = resource_data(pristine_nested, "plcaa", ResourceType.ARE)

    current_inventory = broken_save[INVENTORY_START:PLC_START]
    current_git = broken_save[GIT_START:ARE_START]
    truncated_are = broken_save[ARE_START:IFO_START]
    current_ifo = broken_save[IFO_START:IFO_END]

    if current_git != pristine_git:
        raise RuntimeError("Current GIT is not the verified pristine GIT")
    if truncated_are != pristine_are[: len(truncated_are)]:
        raise RuntimeError("Current ARE prefix does not match the pristine ARE")
    if sha256_bytes(current_inventory) != "287bfe101683cb02e167fc697a1d30ce3ef4df0e8ba5ec4267fb4e933052bbf6":
        raise RuntimeError("Recovered inventory hash changed")
    if sha256_bytes(current_ifo) != "d79285c13daac4edde23c40dafede127cd50447370abef6ac346ed419a54eaea":
        raise RuntimeError("Recovered player IFO hash changed")

    ifo, player = player_from_ifo(current_ifo)
    feats_before = feat_ids(player)
    if feats_before != [4, 5, 6, 28, 29, 39, 40, 42, 44, 30, 43, 116]:
        raise RuntimeError(f"Unexpected current feat list: {feats_before}")
    if class_rows(player) != [(0, 1)] or len(player.get_list("LvlStatList")) != 1:
        raise RuntimeError("Player class history is no longer Soldier 1 / one level row")

    # KSE added Force Sensitive (116), which is not an equipment prerequisite.
    # Replace it in-place with Jedi Defense (55), required by K1 Jedi robes.
    replaced = 0
    for feat in player.get_list("FeatList"):
        if feat.get_uint16("Feat") == 116:
            feat.set_uint16("Feat", 55)
            replaced += 1
    if replaced != 1:
        raise RuntimeError(f"Expected to replace one Force Sensitive feat, replaced {replaced}")
    repaired_ifo = bytes_gff(ifo)
    if len(repaired_ifo) != len(current_ifo):
        raise RuntimeError("One-for-one feat repair unexpectedly changed IFO size")

    pristine_nested.set_data("plcaa", ResourceType.GIT, pristine_git)
    pristine_nested.set_data("plcaa", ResourceType.ARE, pristine_are)
    pristine_nested.set_data("Module", ResourceType.IFO, repaired_ifo)
    repaired_plc = make_kse_compatible_sav(pristine_nested)
    assert_archive_header(repaired_plc, entry_count=3, resource_offset=232)

    pristine_outer.set_data("END_M01AA", ResourceType.SAV, pristine_end)
    pristine_outer.set_data("INVENTORY", ResourceType.RES, current_inventory)
    pristine_outer.set_data("plcaa", ResourceType.SAV, repaired_plc)
    pristine_outer.set_data("REPUTE", ResourceType.FAC, pristine_repute)
    repaired_save = make_kse_compatible_sav(pristine_outer)
    assert_archive_header(repaired_save, entry_count=4, resource_offset=256)

    # Full round-trip validation of both archive layers and every GFF payload.
    checked_outer = read_erf(repaired_save)
    lengths = {
        f"{resource.resref}.{resource.restype.extension}": len(resource.data)
        for resource in checked_outer
    }
    expected_lengths = {
        "END_M01AA.sav": 565052,
        "INVENTORY.res": 7612,
        "plcaa.sav": 27002,
        "REPUTE.fac": 27758,
    }
    if lengths != expected_lengths:
        raise RuntimeError(f"Outer resource lengths mismatch: {lengths}")
    checked_nested = read_erf(resource_data(checked_outer, "plcaa", ResourceType.SAV))
    nested_lengths = {
        f"{resource.resref}.{resource.restype.extension}": len(resource.data)
        for resource in checked_nested
    }
    expected_nested_lengths = {"plcaa.git": 13109, "plcaa.are": 2515, "Module.ifo": 11122}
    if nested_lengths != expected_nested_lengths:
        raise RuntimeError(f"Nested resource lengths mismatch: {nested_lengths}")
    read_gff(resource_data(checked_nested, "plcaa", ResourceType.GIT))
    read_gff(resource_data(checked_nested, "plcaa", ResourceType.ARE))
    checked_ifo = resource_data(checked_nested, "Module", ResourceType.IFO)
    _, checked_player = player_from_ifo(checked_ifo)
    feats_after = feat_ids(checked_player)
    if feats_after != [4, 5, 6, 28, 29, 39, 40, 42, 44, 30, 43, 55]:
        raise RuntimeError(f"Repaired feat list mismatch: {feats_after}")
    tags = inventory_tags(resource_data(checked_outer, "INVENTORY", ResourceType.RES))
    if [tag.lower() for tag in tags] != ["g_a_kghtrobe01", "g_w_lghtsbr03", "g_a_class6005"]:
        raise RuntimeError(f"Recovered inventory mismatch: {tags}")
    read_gff(resource_data(checked_outer, "REPUTE", ResourceType.FAC))

    savenfo = read_gff((BROKEN_SLOT / "savenfo.res").read_bytes())
    old_display_name = savenfo.root.get_string("SAVEGAMENAME")
    savenfo.root.set_string("SAVEGAMENAME", "LorumTest Repaired 2")
    repaired_savenfo = bytes_gff(savenfo)
    if read_gff(repaired_savenfo).root.get_string("SAVEGAMENAME") != "LorumTest Repaired 2":
        raise RuntimeError("Save display-name round trip failed")

    details = {
        "display_name_before": old_display_name,
        "display_name_after": "LorumTest Repaired 2",
        "feats_before": feats_before,
        "feats_after": feats_after,
        "classes_after": class_rows(checked_player),
        "level_history_rows_after": len(checked_player.get_list("LvlStatList")),
        "inventory_tags_after": tags,
        "outer_resource_lengths": lengths,
        "nested_resource_lengths": nested_lengths,
        "payload_hashes": {
            "END_M01AA": sha256_bytes(resource_data(checked_outer, "END_M01AA", ResourceType.SAV)),
            "INVENTORY": sha256_bytes(resource_data(checked_outer, "INVENTORY", ResourceType.RES)),
            "plcaa": sha256_bytes(resource_data(checked_outer, "plcaa", ResourceType.SAV)),
            "REPUTE": sha256_bytes(resource_data(checked_outer, "REPUTE", ResourceType.FAC)),
            "plcaa_GIT": sha256_bytes(resource_data(checked_nested, "plcaa", ResourceType.GIT)),
            "plcaa_ARE": sha256_bytes(resource_data(checked_nested, "plcaa", ResourceType.ARE)),
            "Module_IFO": sha256_bytes(checked_ifo),
        },
    }
    return repaired_save, repaired_savenfo, details


def main() -> None:
    for required in (PRISTINE_SLOT, BROKEN_SLOT):
        if not required.is_dir():
            raise FileNotFoundError(f"Missing required save slot: {required}")
    for must_not_exist in (BACKUP_SLOT, REPAIRED_SLOT, MANIFEST):
        if must_not_exist.exists():
            raise FileExistsError(f"Refusing to overwrite: {must_not_exist}")

    source_hashes_before = slot_hashes(BROKEN_SLOT)
    pristine_hashes_before = slot_hashes(PRISTINE_SLOT)
    repaired_save, repaired_savenfo, details = build_repair()

    STAGING.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BROKEN_SLOT, BACKUP_SLOT, copy_function=shutil.copy2)
    shutil.copytree(BROKEN_SLOT, REPAIRED_SLOT, copy_function=shutil.copy2)
    atomic_write(REPAIRED_SLOT / "SAVEGAME.sav", repaired_save)
    atomic_write(REPAIRED_SLOT / "savenfo.res", repaired_savenfo)

    # Prove the two input slots and immutable backup were not altered.
    if slot_hashes(BROKEN_SLOT) != source_hashes_before:
        raise RuntimeError("Broken source slot changed during repair")
    if slot_hashes(PRISTINE_SLOT) != pristine_hashes_before:
        raise RuntimeError("Pristine source slot changed during repair")
    if slot_hashes(BACKUP_SLOT) != source_hashes_before:
        raise RuntimeError("Backup copy does not match the broken source slot")

    # Re-open the actual destination files after their atomic replacement.
    destination_outer = read_erf((REPAIRED_SLOT / "SAVEGAME.sav").read_bytes())
    destination_nested = read_erf(resource_data(destination_outer, "plcaa", ResourceType.SAV))
    destination_ifo = resource_data(destination_nested, "Module", ResourceType.IFO)
    _, destination_player = player_from_ifo(destination_ifo)
    if feat_ids(destination_player)[-2:] != [43, 55]:
        raise RuntimeError("Destination player prerequisites did not persist")
    if read_gff((REPAIRED_SLOT / "savenfo.res").read_bytes()).root.get_string("SAVEGAMENAME") != "LorumTest Repaired 2":
        raise RuntimeError("Destination display name did not persist")

    manifest = {
        "timestamp_local": datetime.now().astimezone().isoformat(),
        "operation": "repair_second_kse_erf_offset_corruption_and_item_prerequisites",
        "owner": "LordVaderCW",
        "roadmap_task": "T2571",
        "pristine_source": str(PRISTINE_SLOT),
        "broken_source": str(BROKEN_SLOT),
        "immutable_backup": str(BACKUP_SLOT),
        "repaired_save": str(REPAIRED_SLOT),
        "source_slot_hashes_before_and_after": source_hashes_before,
        "pristine_slot_hashes_before_and_after": pristine_hashes_before,
        "backup_slot_hashes": slot_hashes(BACKUP_SLOT),
        "repaired_slot_hashes": slot_hashes(REPAIRED_SLOT),
        "repair": details,
        "validation": {
            "outer_erf_round_trip": True,
            "nested_plcaa_erf_round_trip": True,
            "git_are_ifo_inventory_repute_gff_round_trip": True,
            "destination_reopen": True,
            "actual_kotor_load": "pending_user_or_automation_proof",
        },
        "notes": [
            "Game3 and Game4 were preserved byte-for-byte.",
            "Game5 is a separate collision-free repaired slot.",
            "Force Sensitive 116 was replaced one-for-one with Jedi Defense 55.",
            "Lightsaber proficiency 43 and Arkanian Bond Armor were preserved.",
            "Soldier 1 already has all stock armor proficiencies required by the added armor.",
        ],
    }
    atomic_write(MANIFEST, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({
        "repaired_slot": str(REPAIRED_SLOT),
        "display_name": details["display_name_after"],
        "save_sha256": sha256_file(REPAIRED_SLOT / "SAVEGAME.sav"),
        "manifest": str(MANIFEST),
        "feats_after": details["feats_after"],
        "inventory": details["inventory_tags_after"],
    }, indent=2))


if __name__ == "__main__":
    main()
