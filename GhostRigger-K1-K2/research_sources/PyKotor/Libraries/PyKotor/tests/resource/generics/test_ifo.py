from __future__ import annotations

import os
import pathlib
import sys
import unittest

from unittest import TestCase

THIS_SCRIPT_PATH = pathlib.Path(__file__).resolve()
PYKOTOR_PATH = THIS_SCRIPT_PATH.parents[4].joinpath("src")
UTILITY_PATH = THIS_SCRIPT_PATH.parents[6].joinpath("Libraries", "Utility", "src")


def add_sys_path(p: pathlib.Path):
    working_dir = str(p)
    if working_dir not in sys.path:
        sys.path.append(working_dir)


if PYKOTOR_PATH.joinpath("pykotor").exists():
    add_sys_path(PYKOTOR_PATH)
if UTILITY_PATH.joinpath("utility").exists():
    add_sys_path(UTILITY_PATH)

from typing import TYPE_CHECKING

from pykotor.resource.formats.gff import read_gff
from pykotor.resource.generics.ifo import construct_ifo, dismantle_ifo
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.resource.generics.ifo import IFO

TEST_IFO_XML = """<gff3>
  <struct id="-1">
    <data label="Mod_ID">UjrlnuNzcR0P8GmcuWGfpw==</data>
    <sint32 label="Mod_Creator_ID">2</sint32>
    <uint32 label="Mod_Version">3</uint32>
    <exostring label="Mod_VO_ID">262</exostring>
    <uint16 label="Expansion_Pack">0</uint16>
    <locstring label="Mod_Name" strref="83947" />
    <exostring label="Mod_Tag">262TEL</exostring>
    <exostring label="Mod_Hak" />
    <locstring label="Mod_Description" strref="-1" />
    <byte label="Mod_IsSaveGame">0</byte>
    <resref label="Mod_Entry_Area">262tel</resref>
    <float label="Mod_Entry_X">2.5811009407043457</float>
    <float label="Mod_Entry_Y">41.46979522705078</float>
    <float label="Mod_Entry_Z">21.372770309448242</float>
    <float label="Mod_Entry_Dir_X">1.5099580252808664e-07</float>
    <float label="Mod_Entry_Dir_Y">-1.0</float>
    <list label="Mod_Expan_List" />
    <byte label="Mod_DawnHour">6</byte>
    <byte label="Mod_DuskHour">18</byte>
    <byte label="Mod_MinPerHour">2</byte>
    <byte label="Mod_StartMonth">6</byte>
    <byte label="Mod_StartDay">1</byte>
    <byte label="Mod_StartHour">13</byte>
    <uint32 label="Mod_StartYear">1372</uint32>
    <byte label="Mod_XPScale">10</byte>
    <resref label="Mod_OnHeartbeat">heartbeat</resref>
    <resref label="Mod_OnModLoad">load</resref>
    <resref label="Mod_OnModStart">start</resref>
    <resref label="Mod_OnClientEntr">enter</resref>
    <resref label="Mod_OnClientLeav">leave</resref>
    <resref label="Mod_OnActvtItem">activate</resref>
    <resref label="Mod_OnAcquirItem">acquire</resref>
    <resref label="Mod_OnUsrDefined">user</resref>
    <resref label="Mod_OnUnAqreItem">unacquire</resref>
    <resref label="Mod_OnPlrDeath">death</resref>
    <resref label="Mod_OnPlrDying">dying</resref>
    <resref label="Mod_OnPlrLvlUp">levelup</resref>
    <resref label="Mod_OnSpawnBtnDn">spawn</resref>
    <resref label="Mod_OnPlrRest" />
    <resref label="Mod_StartMovie" />
    <list label="Mod_CutSceneList" />
    <list label="Mod_GVar_List" />
    <list label="Mod_Area_list">
      <struct id="6">
        <resref label="Area_Name">262tel</resref>
        </struct>
      </list>
    </struct>
  </gff3>
"""


class TestIFO(TestCase):
    def setUp(self):
        self.log_messages: list[str] = [os.linesep]

    def log_func(self, message: str = ""):
        self.log_messages.append(message)

    def test_gff_reconstruct(self):
        gff = read_gff(TEST_IFO_XML.encode())
        reconstructed_gff = dismantle_ifo(construct_ifo(gff))
        assert gff.compare(reconstructed_gff, self.log_func), os.linesep.join(self.log_messages)

    def test_io_construct(self):
        gff = read_gff(TEST_IFO_XML.encode())
        ifo = construct_ifo(gff)
        self.validate_io(ifo)

    def test_io_reconstruct(self):
        gff = read_gff(TEST_IFO_XML.encode())
        gff = dismantle_ifo(construct_ifo(gff))
        ifo = construct_ifo(gff)
        self.validate_io(ifo)

    def validate_io(self, ifo: IFO):
        assert ifo.mod_id == b"R:\xe5\x9e\xe3sq\x1d\x0f\xf0i\x9c\xb9a\x9f\xa7"
        assert ifo.creator_id == 2
        assert ifo.version == 3
        assert ifo.vo_id == "262"
        assert ifo.expansion_id == 0
        assert ifo.mod_name.stringref == 83947
        assert ifo.tag == "262TEL"
        assert ifo.hak == ""
        assert ifo.description.stringref == -1
        assert ifo.resref == "262tel"
        assert ifo.entry_position.x == 2.5811009407043457
        assert ifo.entry_position.y == 41.46979522705078
        assert ifo.entry_position.z == 21.372770309448242
        assert ifo.dawn_hour == 6
        assert ifo.dusk_hour == 18
        assert ifo.time_scale == 2
        assert ifo.start_month == 6
        assert ifo.start_day == 1
        assert ifo.start_hour == 13
        assert ifo.start_year == 1372
        assert ifo.xp_scale == 10
        assert ifo.on_heartbeat == "heartbeat"
        assert ifo.on_load == "load"
        assert ifo.on_start == "start"
        assert ifo.on_enter == "enter"
        assert ifo.on_leave == "leave"
        assert ifo.on_activate_item == "activate"
        assert ifo.on_acquire_item == "acquire"
        assert ifo.on_user_defined == "user"
        assert ifo.on_unacquire_item == "unacquire"
        assert ifo.on_player_death == "death"
        assert ifo.on_player_dying == "dying"
        assert ifo.on_player_levelup == "levelup"
        assert ifo.on_player_respawn == "spawn"
        assert ifo.on_player_rest == ""
        assert ifo.start_movie == ""
        self.assertAlmostEqual(-1.571, ifo.entry_direction, 3)

    def test_ifo_missing_field_defaults(self) -> None:
        """Test defaults when IFO fields are omitted (K1 0x004c9050, TSL 0x0072aaa0)."""
        minimal_ifo_xml = """<gff3>
          <struct id="-1">
            <exostring label="Mod_Tag">OnlyTag</exostring>
          </struct>
        </gff3>
        """
        gff = read_gff(minimal_ifo_xml.encode(), file_format=ResourceType.GFF_XML)
        ifo = construct_ifo(gff)
        self.assertEqual(ifo.tag, "OnlyTag")
        self.assertEqual(ifo.mod_id, b"")
        self.assertEqual(ifo.vo_id, "")
        self.assertEqual(ifo.mod_name.stringref, -1)
        self.assertEqual(ifo.resref, "")
        self.assertEqual(ifo.entry_position.x, 0.0)
        self.assertEqual(ifo.entry_position.y, 0.0)
        self.assertEqual(ifo.entry_position.z, 0.0)
        self.assertEqual(ifo.creator_id, 0)
        self.assertEqual(ifo.version, 0)
        self.assertEqual(ifo.expansion_id, 0)
        self.assertEqual(ifo.dawn_hour, 0)
        self.assertEqual(ifo.dusk_hour, 0)
        self.assertEqual(ifo.time_scale, 0)
        self.assertEqual(ifo.start_year, 0)
        self.assertEqual(ifo.on_heartbeat, "")
        self.assertEqual(ifo.on_load, "")
        self.assertEqual(ifo.area_name, "")
        # Mod_Area_list omitted → empty list, so area_name stays blank
        gff_empty_list = read_gff(
            """<gff3><struct id="-1"><list label="Mod_Area_list" /></struct></gff3>""".encode(),
            file_format=ResourceType.GFF_XML,
        )
        ifo2 = construct_ifo(gff_empty_list)
        self.assertEqual(ifo2.area_name, "")

    def test_ifo_empty_roundtrip(self) -> None:
        """Empty/minimal root struct round-trip: construct_ifo → dismantle_ifo → construct_ifo."""
        empty_xml = """<gff3><struct id="-1"></struct></gff3>"""
        gff = read_gff(empty_xml.encode(), file_format=ResourceType.GFF_XML)
        ifo = construct_ifo(gff)
        self.assertEqual(ifo.tag, "")
        self.assertEqual(ifo.mod_id, b"")
        self.assertEqual(ifo.area_name, "")
        gff2 = dismantle_ifo(ifo)
        ifo2 = construct_ifo(gff2)
        self.assertEqual(ifo2.tag, "")
        self.assertEqual(ifo2.mod_id, b"")
        # dismantle_ifo writes one Mod_Area_list entry; area_name may be blank
        self.assertIsNotNone(ifo2.area_name)


if __name__ == "__main__":
    unittest.main()
