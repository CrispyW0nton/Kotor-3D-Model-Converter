from __future__ import annotations

import os
import pathlib
import sys
import unittest

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
from pykotor.resource.generics.pth import construct_pth, dismantle_pth
from pykotor.resource.type import ResourceType
from utility.common.geometry import Vector2

if TYPE_CHECKING:
    from pykotor.resource.generics.pth import PTH

TEST_PTH_XML = """<gff3>
  <struct id="-1">
    <list label="Path_Points">
      <struct id="2">
        <uint32 label="Conections">2</uint32>
        <uint32 label="First_Conection">0</uint32>
        <float label="X">0.0</float>
        <float label="Y">0.0</float>
        </struct>
      <struct id="2">
        <uint32 label="Conections">3</uint32>
        <uint32 label="First_Conection">2</uint32>
        <float label="X">0.0</float>
        <float label="Y">1.0</float>
        </struct>
      <struct id="2">
        <uint32 label="Conections">2</uint32>
        <uint32 label="First_Conection">5</uint32>
        <float label="X">1.0</float>
        <float label="Y">1.0</float>
        </struct>
      <struct id="2">
        <uint32 label="Conections">1</uint32>
        <uint32 label="First_Conection">7</uint32>
        <float label="X">0.0</float>
        <float label="Y">2.0</float>
        </struct>
      </list>
    <list label="Path_Conections">
      <struct id="3">
        <uint32 label="Destination">1</uint32>
        </struct>
      <struct id="3">
        <uint32 label="Destination">2</uint32>
        </struct>
      <struct id="3">
        <uint32 label="Destination">0</uint32>
        </struct>
      <struct id="3">
        <uint32 label="Destination">2</uint32>
        </struct>
      <struct id="3">
        <uint32 label="Destination">3</uint32>
        </struct>
      <struct id="3">
        <uint32 label="Destination">0</uint32>
        </struct>
      <struct id="3">
        <uint32 label="Destination">1</uint32>
        </struct>
      <struct id="3">
        <uint32 label="Destination">1</uint32>
        </struct>
      </list>
    </struct>
  </gff3>
"""


class TestPTH(unittest.TestCase):
    def setUp(self):
        self.log_messages = [os.linesep]

    def log_func(self, message=""):
        self.log_messages.append(message)

    def test_gff_reconstruct(self):
        gff = read_gff(TEST_PTH_XML.encode(), file_format=ResourceType.GFF_XML)
        reconstructed_gff = dismantle_pth(construct_pth(gff))
        assert gff.compare(reconstructed_gff, self.log_func), os.linesep.join(self.log_messages)

    def test_io_construct(self):
        gff = read_gff(TEST_PTH_XML.encode(), file_format=ResourceType.GFF_XML)
        pth = construct_pth(gff)
        self.validate_io(pth)

    def test_io_reconstruct(self):
        gff = read_gff(TEST_PTH_XML.encode(), file_format=ResourceType.GFF_XML)
        gff = dismantle_pth(construct_pth(gff))
        pth = construct_pth(gff)
        self.validate_io(pth)

    def validate_io(self, pth: PTH):
        assert pth.get(0) == Vector2(0.0, 0.0)
        assert pth.get(1) == Vector2(0.0, 1.0)
        assert pth.get(2) == Vector2(1.0, 1.0)
        assert pth.get(3) == Vector2(0.0, 2.0)

        assert len(pth.outgoing(0)) == 2
        assert pth.is_connected(0, 1)
        assert pth.is_connected(0, 2)

        assert len(pth.outgoing(1)) == 3
        assert pth.is_connected(1, 0)
        assert pth.is_connected(1, 2)
        assert pth.is_connected(1, 3)

        assert len(pth.outgoing(2)) == 2
        assert pth.is_connected(2, 0)
        assert pth.is_connected(2, 1)

        assert len(pth.outgoing(3)) == 1
        assert pth.is_connected(3, 1)

    def test_pth_missing_field_defaults(self) -> None:
        """Test defaults when PTH fields are omitted (K1 0x00508400, TSL 0x00721db0)."""
        minimal_pth_xml = """<gff3>
          <struct id="-1">
            <list label="Path_Points">
              <struct id="2">
                <float label="X">2.5</float>
              </struct>
            </list>
            <list label="Path_Conections" />
          </struct>
        </gff3>
        """
        gff = read_gff(minimal_pth_xml.encode(), file_format=ResourceType.GFF_XML)
        pth = construct_pth(gff)
        self.assertEqual(len(pth), 1)
        pt = pth.get(0)
        self.assertIsNotNone(pt)
        self.assertEqual(pt.x, 2.5)
        self.assertEqual(pt.y, 0.0)
        self.assertEqual(len(pth.outgoing(0)), 0)
        # One point with one connection; Destination omitted → default 0
        one_conn_xml = """<gff3>
          <struct id="-1">
            <list label="Path_Points">
              <struct id="2">
                <float label="X">0.0</float>
                <float label="Y">1.0</float>
                <uint32 label="Conections">1</uint32>
                <uint32 label="First_Conection">0</uint32>
              </struct>
            </list>
            <list label="Path_Conections">
              <struct id="3" />
            </list>
          </struct>
        </gff3>
        """
        gff2 = read_gff(one_conn_xml.encode(), file_format=ResourceType.GFF_XML)
        pth2 = construct_pth(gff2)
        self.assertEqual(len(pth2), 1)
        self.assertEqual(len(pth2.outgoing(0)), 1)
        self.assertEqual(pth2.outgoing(0)[0].target, 0)

    def test_pth_empty_roundtrip(self) -> None:
        """Empty root struct: no Path_Points/Path_Conections → 0 points; round-trip preserves empty."""
        empty_xml = """<gff3><struct id="-1"></struct></gff3>"""
        gff = read_gff(empty_xml.encode(), file_format=ResourceType.GFF_XML)
        pth = construct_pth(gff)
        self.assertEqual(len(pth), 0)
        gff2 = dismantle_pth(pth)
        pth2 = construct_pth(gff2)
        self.assertEqual(len(pth2), 0)


if __name__ == "__main__":
    unittest.main()
