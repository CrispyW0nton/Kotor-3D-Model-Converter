"""
test_gff_roundtrip.py — GFF V3.2 read/write round-trip tests.

Tests per GHOSTWORKS_BLUEPRINT.md Section 10:
  "GFF round-trip: write a GFF with all field types, read it back,
   assert all values identical"
"""
import struct
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.formats.gff_types import (
    GffFieldType, GffField, GffStruct, GffFile,
    LocString, ResRef,
)
from src.formats.gff_reader import read_gff
from src.formats.gff_writer import write_gff


# ─── Helper ──────────────────────────────────────────────────────────────────

def roundtrip(gff: GffFile) -> GffFile:
    data = write_gff(gff)
    return read_gff(data)


# ─── Basic tests ─────────────────────────────────────────────────────────────

class TestGffRoundtrip:

    def test_file_type_preserved(self):
        gff = GffFile(file_type="UTC ")
        rt  = roundtrip(gff)
        assert rt.file_type == "UTC "

    def test_version_preserved(self):
        gff = GffFile(file_type="UTC ", file_version="V3.2")
        rt  = roundtrip(gff)
        assert rt.file_version == "V3.2"

    def test_cexostring_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Tag", GffFieldType.CEXOSTRING, "test_tag_01")
        rt  = roundtrip(gff)
        assert rt.get("Tag") == "test_tag_01"

    def test_cexostring_empty(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Tag", GffFieldType.CEXOSTRING, "")
        rt  = roundtrip(gff)
        assert rt.get("Tag") == ""

    def test_resref_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("TemplateResRef", GffFieldType.RESREF, ResRef("c_gamorrean"))
        rt  = roundtrip(gff)
        rr  = rt.get("TemplateResRef")
        assert isinstance(rr, ResRef)
        assert str(rr) == "c_gamorrean"

    def test_resref_max_16_chars(self):
        gff = GffFile(file_type="UTC ")
        gff.set("TemplateResRef", GffFieldType.RESREF, ResRef("this_is_a_very_long_name"))
        rt  = roundtrip(gff)
        rr  = rt.get("TemplateResRef")
        assert len(str(rr)) <= 16

    def test_byte_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Str", GffFieldType.BYTE, 18)
        rt  = roundtrip(gff)
        assert rt.get("Str") == 18

    def test_byte_zero(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Dex", GffFieldType.BYTE, 0)
        rt  = roundtrip(gff)
        assert rt.get("Dex") == 0

    def test_byte_max(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Dex", GffFieldType.BYTE, 255)
        rt  = roundtrip(gff)
        assert rt.get("Dex") == 255

    def test_int16_positive(self):
        gff = GffFile(file_type="UTC ")
        gff.set("MaxHitPoints", GffFieldType.INT16, 100)
        rt  = roundtrip(gff)
        assert rt.get("MaxHitPoints") == 100

    def test_int16_negative(self):
        gff = GffFile(file_type="UTC ")
        gff.set("CurHitPoints", GffFieldType.INT16, -5)
        rt  = roundtrip(gff)
        assert rt.get("CurHitPoints") == -5

    def test_uint16_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Appearance_Type", GffFieldType.UINT16, 147)
        rt  = roundtrip(gff)
        assert rt.get("Appearance_Type") == 147

    def test_uint32_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("FactionID", GffFieldType.UINT32, 2)
        rt  = roundtrip(gff)
        assert rt.get("FactionID") == 2

    def test_int32_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Gold", GffFieldType.INT32, 500)
        rt  = roundtrip(gff)
        assert rt.get("Gold") == 500

    def test_float_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("XP", GffFieldType.FLOAT, 1.5)
        rt  = roundtrip(gff)
        val = rt.get("XP")
        assert abs(val - 1.5) < 1e-5

    def test_locstring_english_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        loc = LocString()
        loc.english = "Darth Malak"
        gff.set("FirstName", GffFieldType.CEXOLOCSTRING, loc)
        rt  = roundtrip(gff)
        loc2 = rt.get("FirstName")
        assert isinstance(loc2, LocString)
        assert loc2.english == "Darth Malak"

    def test_locstring_strref_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        loc = LocString(strref=12345)
        gff.set("FirstName", GffFieldType.CEXOLOCSTRING, loc)
        rt  = roundtrip(gff)
        loc2 = rt.get("FirstName")
        assert loc2.strref == 12345

    def test_locstring_multi_language(self):
        gff = GffFile(file_type="UTC ")
        loc = LocString()
        loc.set_text("English Name", 0)
        loc.set_text("Nom Français", 2)
        gff.set("FirstName", GffFieldType.CEXOLOCSTRING, loc)
        rt  = roundtrip(gff)
        loc2 = rt.get("FirstName")
        assert loc2.get_text(0) == "English Name"
        assert loc2.get_text(2) == "Nom Français"

    def test_multiple_fields(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Tag",            GffFieldType.CEXOSTRING, "malak_01")
        gff.set("MaxHitPoints",   GffFieldType.INT16,      500)
        gff.set("Str",            GffFieldType.BYTE,       20)
        gff.set("FactionID",      GffFieldType.UINT32,     2)
        rt  = roundtrip(gff)
        assert rt.get("Tag")          == "malak_01"
        assert rt.get("MaxHitPoints") == 500
        assert rt.get("Str")          == 20
        assert rt.get("FactionID")    == 2

    def test_position_roundtrip(self):
        gff = GffFile(file_type="GIT ")
        gff.set("Position", GffFieldType.POSITION, (1.5, 2.5, -3.0))
        rt  = roundtrip(gff)
        pos = rt.get("Position")
        assert pos is not None
        assert abs(pos[0] - 1.5) < 1e-5
        assert abs(pos[1] - 2.5) < 1e-5
        assert abs(pos[2] - (-3.0)) < 1e-5

    def test_rotation_roundtrip(self):
        gff = GffFile(file_type="GIT ")
        quat = (0.0, 0.0, 0.7071, 0.7071)
        gff.set("Bearing", GffFieldType.ROTATION, quat)
        rt  = roundtrip(gff)
        q2  = rt.get("Bearing")
        assert q2 is not None
        for a, b in zip(quat, q2):
            assert abs(a - b) < 1e-5

    def test_binary_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        raw = b'\xDE\xAD\xBE\xEF\x00\x01\x02\x03'
        gff.set("RawData", GffFieldType.BINARY, raw)
        rt  = roundtrip(gff)
        assert rt.get("RawData") == raw

    def test_nested_struct_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        inner = GffStruct(type_id=5)
        inner.set("Slot", GffFieldType.INT32, 0)
        inner.set("EquippedRes", GffFieldType.RESREF, ResRef("w_blstrpstl"))
        gff.set("Equipment", GffFieldType.STRUCT, inner)
        rt  = roundtrip(gff)
        eq  = rt.get("Equipment")
        assert isinstance(eq, GffStruct)
        assert eq.get("Slot") == 0
        assert str(eq.get("EquippedRes")) == "w_blstrpstl"

    def test_list_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        items = []
        for i in range(3):
            s = GffStruct(type_id=1)
            s.set("ItemIndex", GffFieldType.INT32, i)
            s.set("ItemTag",   GffFieldType.CEXOSTRING, f"item_{i:02d}")
            items.append(s)
        gff.set("ItemList", GffFieldType.LIST, items)
        rt  = roundtrip(gff)
        lst = rt.get("ItemList")
        assert isinstance(lst, list)
        assert len(lst) == 3
        assert lst[0].get("ItemIndex") == 0
        assert lst[2].get("ItemTag")   == "item_02"

    def test_uint64_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("BigNum", GffFieldType.UINT64, 0xDEADBEEFCAFEBABE)
        rt  = roundtrip(gff)
        assert rt.get("BigNum") == 0xDEADBEEFCAFEBABE

    def test_double_roundtrip(self):
        gff = GffFile(file_type="UTC ")
        gff.set("Precision", GffFieldType.DOUBLE, 3.141592653589793)
        rt  = roundtrip(gff)
        assert abs(rt.get("Precision") - 3.141592653589793) < 1e-12

    def test_empty_gff(self):
        gff = GffFile(file_type="UTC ")
        rt  = roundtrip(gff)
        assert rt.file_type == "UTC "
        assert len(rt.root.fields) == 0

    def test_gff_header_magic(self):
        """The first 8 bytes must be the file type + 'V3.2'."""
        gff  = GffFile(file_type="UTC ")
        data = write_gff(gff)
        assert data[:4] == b'UTC '
        assert data[4:8] == b'V3.2'

    def test_struct_type_id_preserved(self):
        gff = GffFile(file_type="UTC ")
        gff.root.type_id = 0xFFFFFFFF
        rt  = roundtrip(gff)
        assert rt.root.type_id == 0xFFFFFFFF


# ─── UTC-specific round-trip tests ───────────────────────────────────────────

class TestUTCFieldRoundtrip:

    def test_utc_tag_and_resref(self, sample_utc_bytes):
        gff = read_gff(sample_utc_bytes)
        assert gff.file_type.strip() == "UTC"
        assert gff.get("Tag") == "test_creature"
        assert str(gff.get("TemplateResRef")) == "test_cr"

    def test_utc_name_locstring(self, sample_utc_bytes):
        gff  = read_gff(sample_utc_bytes)
        name = gff.get("FirstName")
        assert isinstance(name, LocString)
        assert name.english == "Test Creature"

    def test_utc_hp_stat(self, sample_utc_bytes):
        gff = read_gff(sample_utc_bytes)
        assert gff.get("MaxHitPoints") == 40

    def test_utc_attributes(self, sample_utc_bytes):
        gff = read_gff(sample_utc_bytes)
        assert gff.get("Str") == 14
        assert gff.get("Dex") == 12

    def test_utc_write_read_cycle(self, sample_utc_bytes):
        """Full write → read → write → read cycle must be stable."""
        gff1  = read_gff(sample_utc_bytes)
        data2 = write_gff(gff1)
        gff2  = read_gff(data2)
        assert gff2.get("Tag") == gff1.get("Tag")
        assert str(gff2.get("TemplateResRef")) == str(gff1.get("TemplateResRef"))
        assert gff2.get("MaxHitPoints") == gff1.get("MaxHitPoints")


class TestUTPFieldRoundtrip:

    def test_utp_tag(self, sample_utp_bytes):
        gff = read_gff(sample_utp_bytes)
        assert gff.file_type.strip() == "UTP"
        assert gff.get("Tag") == "plc_container01"

    def test_utp_name(self, sample_utp_bytes):
        gff  = read_gff(sample_utp_bytes)
        name = gff.get("LocalizedName")
        assert isinstance(name, LocString)
        assert name.english == "Storage Container"

    def test_utp_appearance(self, sample_utp_bytes):
        gff = read_gff(sample_utp_bytes)
        assert gff.get("Appearance") == 4

    def test_utp_useable_flag(self, sample_utp_bytes):
        gff = read_gff(sample_utp_bytes)
        assert gff.get("Useable") == 1


class TestUTDFieldRoundtrip:

    def test_utd_tag(self, sample_utd_bytes):
        gff = read_gff(sample_utd_bytes)
        assert gff.file_type.strip() == "UTD"
        assert gff.get("Tag") == "door_001"

    def test_utd_name(self, sample_utd_bytes):
        gff  = read_gff(sample_utd_bytes)
        name = gff.get("LocalizedName")
        assert isinstance(name, LocString)
        assert name.english == "Heavy Door"

    def test_utd_hp(self, sample_utd_bytes):
        gff = read_gff(sample_utd_bytes)
        assert gff.get("MaxHP") == 30

    def test_utd_generic_type(self, sample_utd_bytes):
        gff = read_gff(sample_utd_bytes)
        assert gff.get("GenericType") == 0
