"""Focused UTC/NCS contracts for authored Map Studio creatures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
K1_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


@pytest.mark.parametrize(
    ("game", "installation_root", "template_resref"),
    (
        ("K1", K1_ROOT, "gr_roam_k1"),
        ("K2", K2_ROOT, "gr_roam_k2"),
    ),
)
def test_vanilla_utc_patch_builds_hostile_free_roam_resources(
    game: str,
    installation_root: Path,
    template_resref: str,
) -> None:
    """A copied vanilla UTC gains faction/dialog/free-roam without losing its spawn setup."""

    if not installation_root.is_dir():
        pytest.skip(f"{game} installation is unavailable")
    _configure_native_python_roots()

    from pykotor.common import scriptdefs
    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.gff import read_gff
    from pykotor.resource.formats.ncs import read_ncs
    from pykotor.resource.formats.ncs.ncs_data import NCSInstructionType
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_creature_behavior import build_authored_creature_behavior_resources

    source = Installation(installation_root).resource("g_darkjedi01", ResourceType.UTC)
    assert source is not None
    build = build_authored_creature_behavior_resources(
        source.data,
        game=game,
        template_resref=template_resref,
        instance_tag="gr_enemy_actor",
        faction_role="hostile",
        conversation_resref="gr_roam_dlg",
        movement_mode="free_roam",
    )

    assert build.faction_id == 1  # repute.2da Hostile_1 in both games
    assert build.source_spawn_script == "k_def_spawn01"
    assert build.spawn_script_resref.endswith("_roam")
    assert build.resources[0][:2] == (template_resref, "utc")
    assert build.resources[1][:2] == (build.spawn_script_resref, "ncs")

    utc = read_gff(build.resources[0][2]).root
    assert utc.what_type("TemplateResRef").name == "ResRef"
    assert utc.what_type("FactionID").name == "UInt16"
    assert utc.what_type("Conversation").name == "ResRef"
    assert utc.what_type("ScriptSpawn").name == "ResRef"
    assert str(utc.get("TemplateResRef")) == template_resref
    assert utc.get("Tag") == "gr_enemy_actor"
    assert int(utc.get("FactionID")) == 1
    assert str(utc.get("Conversation")) == "gr_roam_dlg"
    assert str(utc.get("ScriptSpawn")) == build.spawn_script_resref

    ncs = read_ncs(build.resources[1][2])
    functions = scriptdefs.KOTOR_FUNCTIONS if game == "K1" else scriptdefs.TSL_FUNCTIONS
    action_ids = {
        int(instruction.args[0])
        for instruction in ncs.instructions
        if instruction.ins_type == NCSInstructionType.ACTION
    }
    random_walk_id = next(index for index, function in enumerate(functions) if function.name == "ActionRandomWalk")
    execute_script_id = next(index for index, function in enumerate(functions) if function.name == "ExecuteScript")
    assert {random_walk_id, execute_script_id} <= action_ids
    assert 'ExecuteScript("k_def_spawn01", OBJECT_SELF)' in build.nss_source
    assert "ActionRandomWalk();" in build.nss_source


def test_stationary_behavior_patch_preserves_source_on_spawn_and_emits_only_utc() -> None:
    """A non-roaming patch must not silently erase vanilla/custom OnSpawn logic."""

    if not K2_ROOT.is_dir():
        pytest.skip("K2 installation is unavailable")
    _configure_native_python_roots()

    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.gff import read_gff
    from pykotor.resource.type import ResourceType
    from src.core.modules.authored_creature_behavior import build_authored_creature_behavior_resources

    source = Installation(K2_ROOT).resource("g_darkjedi01", ResourceType.UTC)
    assert source is not None
    build = build_authored_creature_behavior_resources(
        source.data,
        game="K2",
        template_resref="gr_still_npc",
        faction_role="neutral",
        conversation_resref=None,
        movement_mode="stationary",
    )

    assert tuple((resref, restype) for resref, restype, _data in build.resources) == (("gr_still_npc", "utc"),)
    utc = read_gff(build.resources[0][2]).root
    assert int(utc.get("FactionID")) == 5
    assert str(utc.get("ScriptSpawn")) == "k_def_spawn01"
    assert build.spawn_script_resref == ""
    assert build.nss_source == ""
