from __future__ import annotations

from pathlib import Path

import pytest

from pykotor.extract.installation import Installation
from pykotor.resource.formats.gff import GFFContent, read_gff
from pykotor.resource.generics.utp import read_utp
from pykotor.resource.type import ResourceType

from src.core.workflow.plcaa_manual_proof_kit import (
    PLCAA_PROOF_KIT_SCHEMA,
    build_plcaa_manual_proof_kit,
    plcaa_manual_proof_in_memory_provider,
    plcaa_manual_proof_palette_rows,
)
from src.core.resources.game_resource_provider import GameResourceQuery


GAME_ROOTS = {
    "K1": Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
    "K2": Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"),
}


def _installed_reader(game: str):
    root = GAME_ROOTS[game]
    if not root.is_dir():
        pytest.skip(f"{game} installation is not available for vanilla-structural proof.")
    installation = Installation(root)

    def read(resref: str, restype: str) -> bytes:
        resource_type = ResourceType.from_extension(restype)
        resource = installation.resource(resref, resource_type)
        if resource is None:
            raise FileNotFoundError(f"{game}:{resref}.{restype.lower()}")
        return bytes(resource.data)

    return read


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_plcaa_proof_palette_exposes_manual_functional_objects(game: str) -> None:
    rows = plcaa_manual_proof_palette_rows(game)
    by_resref = {row["resref"]: row for row in rows}
    assert {
        "gr_enemy",
        "gr_roamnpc",
        "gr_terminal",
        "gr_store",
        "gr_container",
        "gr_ped1",
        "gr_ped2",
        "gr_ped3",
        "gr_pzdoor",
        "gr_traveldoor",
        "gr_traveltrig",
        "gr_destwp",
    } <= set(by_resref)
    assert by_resref["gr_terminal"]["metadata"]["schema"] == PLCAA_PROOF_KIT_SCHEMA
    assert by_resref["gr_terminal"]["metadata"]["manual_proof_required"] is True
    assert by_resref["gr_ped1"]["metadata"]["required_with"] == [
        "gr_ped1",
        "gr_ped2",
        "gr_ped3",
        "gr_pzdoor",
    ]
    assert by_resref["gr_traveldoor"]["restype"] == "UTD"


@pytest.mark.parametrize("game", ("K1", "K2"))
def test_plcaa_proof_kit_clones_vanilla_and_compiles_target_game_scripts(game: str) -> None:
    build = build_plcaa_manual_proof_kit(game, _installed_reader(game))
    assert build.ok, build.issues
    assert build.engine_ready is False
    resources = {(resref, restype): data for resref, restype, data in build.resources}
    expected = {
        ("gr_enemy", "utc"),
        ("gr_roamnpc", "utc"),
        ("gr_roamnpc_roam", "ncs"),
        ("gr_terminal", "utp"),
        ("gr_container", "utp"),
        ("gr_ped1", "utp"),
        ("gr_ped2", "utp"),
        ("gr_ped3", "utp"),
        ("gr_pzdoor", "utd"),
        ("gr_traveldoor", "utd"),
        ("gr_store", "utm"),
        ("gr_traveltrig", "utt"),
        ("gr_destwp", "utw"),
        ("g_i_credits001", "uti"),
        ("gr_terminal", "nss"),
        ("gr_terminal", "ncs"),
        ("gr_puzzle", "nss"),
        ("gr_puzzle", "ncs"),
    }
    assert expected == set(resources)

    enemy = read_gff(resources[("gr_enemy", "utc")])
    assert enemy.content is GFFContent.UTC
    assert str(enemy.root.acquire("TemplateResRef", "")) == "gr_enemy"
    assert int(enemy.root.acquire("FactionID", -1)) == 1
    roaming_npc = read_gff(resources[("gr_roamnpc", "utc")])
    assert roaming_npc.content is GFFContent.UTC
    assert str(roaming_npc.root.acquire("TemplateResRef", "")) == "gr_roamnpc"
    assert int(roaming_npc.root.acquire("FactionID", -1)) == 2
    assert str(roaming_npc.root.acquire("ScriptSpawn", "")) == "gr_roamnpc_roam"
    assert resources[("gr_roamnpc_roam", "ncs")].startswith(b"NCS V1.0")

    terminal = read_utp(resources[("gr_terminal", "utp")])
    assert str(terminal.resref) == "gr_terminal"
    assert terminal.tag == "gr_terminal"
    assert str(terminal.on_used) == "gr_terminal"
    assert terminal.useable is True
    assert terminal.static is False

    container = read_utp(resources[("gr_container", "utp")])
    assert container.has_inventory is True
    assert [str(item.resref) for item in container.inventory] == ["g_i_credits001"]

    puzzle_switch = read_utp(resources[("gr_ped1", "utp")])
    assert str(puzzle_switch.on_used) == "gr_puzzle"
    puzzle_door = read_gff(resources[("gr_pzdoor", "utd")])
    assert puzzle_door.content is GFFContent.UTD
    assert str(puzzle_door.root.acquire("TemplateResRef", "")) == "gr_pzdoor"
    assert puzzle_door.root.acquire("Tag", "") == "gr_pzdoor"
    assert int(puzzle_door.root.acquire("Locked", 0)) == 1

    travel_door = read_gff(resources[("gr_traveldoor", "utd")])
    assert travel_door.content is GFFContent.UTD
    assert int(travel_door.root.acquire("Locked", 1)) == 0
    store = read_gff(resources[("gr_store", "utm")])
    assert store.content is GFFContent.UTM
    assert str(store.root.acquire("ResRef", "")) == "gr_store"
    trigger = read_gff(resources[("gr_traveltrig", "utt")])
    assert trigger.content is GFFContent.UTT
    assert str(trigger.root.acquire("TemplateResRef", "")) == "gr_traveltrig"
    waypoint = read_gff(resources[("gr_destwp", "utw")])
    assert waypoint.content is GFFContent.UTW
    assert waypoint.root.acquire("Tag", "") == "gr_destwp"

    assert resources[("gr_terminal", "ncs")].startswith(b"NCS V1.0")
    assert resources[("gr_puzzle", "ncs")].startswith(b"NCS V1.0")
    assert b"OpenStore" in resources[("gr_terminal", "nss")]
    assert b"SetLocked" in resources[("gr_puzzle", "nss")]

    provider = plcaa_manual_proof_in_memory_provider(build)
    terminal_record = provider.resolve(
        GameResourceQuery(game=game, module_id="plcaa", resref="gr_terminal", restype="UTP")
    )
    assert terminal_record.data == resources[("gr_terminal", "utp")]
    assert terminal_record.address.layer == "generated"
    assert terminal_record.record.source == "plcaa_manual_proof_kit"
