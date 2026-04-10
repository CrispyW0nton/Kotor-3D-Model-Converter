"""
test_utc_fields.py — UTC / UTP / UTD field-level validation tests.

Tests per GHOSTWORKS_BLUEPRINT.md Section 10:
  "UTC field round-trip: create UTC GFF, write, read back, check all fields"
  "UTP field round-trip: same for placeables"
  "UTD field round-trip: same for doors"
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.formats.gff_types import (
    GffFieldType, GffFile, GffStruct, LocString, ResRef,
    UTC_FIELDS, UTP_FIELDS, UTD_FIELDS,
)
from src.formats.gff_reader import read_gff
from src.formats.gff_writer import write_gff


def make_full_utc() -> GffFile:
    """Create a GFF with all UTC fields populated."""
    gff = GffFile(file_type="UTC ")
    gff.set("Tag",              GffFieldType.CEXOSTRING,    "malak_01")
    gff.set("TemplateResRef",   GffFieldType.RESREF,        ResRef("malak"))
    loc = LocString(strref=-1); loc.english = "Darth Malak"
    gff.set("FirstName",        GffFieldType.CEXOLOCSTRING, loc)
    gff.set("Appearance_Type",  GffFieldType.UINT16,        171)
    gff.set("Gender",           GffFieldType.BYTE,          0)
    gff.set("Race",             GffFieldType.BYTE,          6)
    gff.set("Class1",           GffFieldType.BYTE,          3)     # Jedi Guardian
    gff.set("Level",            GffFieldType.BYTE,          20)
    gff.set("MaxHitPoints",     GffFieldType.INT16,         500)
    gff.set("CurrentHitPoints", GffFieldType.INT16,         500)
    gff.set("MaxFP",            GffFieldType.INT16,         200)
    gff.set("CurrentFP",        GffFieldType.INT16,         200)
    gff.set("fortbonus",        GffFieldType.CHAR,          12)
    gff.set("refbonus",         GffFieldType.CHAR,          8)
    gff.set("willbonus",        GffFieldType.CHAR,          15)
    gff.set("Str",              GffFieldType.BYTE,          20)
    gff.set("Dex",              GffFieldType.BYTE,          18)
    gff.set("Con",              GffFieldType.BYTE,          16)
    gff.set("Int",              GffFieldType.BYTE,          14)
    gff.set("Wis",              GffFieldType.BYTE,          12)
    gff.set("Cha",              GffFieldType.BYTE,          10)
    gff.set("FactionID",        GffFieldType.UINT32,        2)     # Hostile
    gff.set("Conversation",     GffFieldType.RESREF,        ResRef("malak_conv"))
    gff.set("OnSpawn",          GffFieldType.RESREF,        ResRef("malak_sp"))
    gff.set("OnDeath",          GffFieldType.RESREF,        ResRef("malak_de"))
    gff.set("WillNotRender",    GffFieldType.BYTE,          0)
    gff.set("IsPC",             GffFieldType.BYTE,          0)
    return gff


def make_full_utp() -> GffFile:
    """Create a GFF with all UTP fields populated."""
    gff = GffFile(file_type="UTP ")
    gff.set("Tag",           GffFieldType.CEXOSTRING,    "plc_pedestal")
    gff.set("TemplateResRef",GffFieldType.RESREF,        ResRef("plc_peds01"))
    loc = LocString(); loc.english = "Ancient Pedestal"
    gff.set("LocalizedName", GffFieldType.CEXOLOCSTRING, loc)
    gff.set("Appearance",    GffFieldType.UINT32,        99)
    gff.set("MaxHP",         GffFieldType.INT16,         10)
    gff.set("CurrentHP",     GffFieldType.INT16,         10)
    gff.set("Static",        GffFieldType.BYTE,          1)
    gff.set("Useable",       GffFieldType.BYTE,          1)
    gff.set("HasInventory",  GffFieldType.BYTE,          0)
    gff.set("Faction",       GffFieldType.UINT32,        1)
    gff.set("OnUsed",        GffFieldType.RESREF,        ResRef("plc_used"))
    gff.set("OnOpen",        GffFieldType.RESREF,        ResRef("plc_open"))
    return gff


def make_full_utd() -> GffFile:
    """Create a GFF with all UTD fields populated."""
    gff = GffFile(file_type="UTD ")
    gff.set("Tag",           GffFieldType.CEXOSTRING,    "door_vault")
    gff.set("TemplateResRef",GffFieldType.RESREF,        ResRef("door_vlt"))
    loc = LocString(); loc.english = "Vault Door"
    gff.set("LocalizedName", GffFieldType.CEXOLOCSTRING, loc)
    gff.set("GenericType",   GffFieldType.BYTE,          2)
    gff.set("LinkedTo",      GffFieldType.CEXOSTRING,    "VAULT_EXIT")
    gff.set("LinkedToFlags", GffFieldType.BYTE,          1)
    gff.set("MaxHP",         GffFieldType.INT16,         50)
    gff.set("CurrentHP",     GffFieldType.INT16,         50)
    gff.set("Locked",        GffFieldType.BYTE,          1)
    gff.set("LockDC",        GffFieldType.BYTE,          28)
    gff.set("KeyRequired",   GffFieldType.BYTE,          0)
    gff.set("Static",        GffFieldType.BYTE,          0)
    gff.set("OnOpen",        GffFieldType.RESREF,        ResRef("door_open"))
    gff.set("OnClosed",      GffFieldType.RESREF,        ResRef("door_cls"))
    gff.set("OnDeath",       GffFieldType.RESREF,        ResRef("door_die"))
    return gff


class TestUTCFields:

    def test_utc_tag(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("Tag") == "malak_01"

    def test_utc_resref(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert str(gff.get("TemplateResRef")) == "malak"

    def test_utc_name_english(self):
        gff  = read_gff(write_gff(make_full_utc()))
        name = gff.get("FirstName")
        assert name.english == "Darth Malak"

    def test_utc_appearance_type(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("Appearance_Type") == 171

    def test_utc_gender(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("Gender") == 0  # Male

    def test_utc_class_and_level(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("Class1") == 3
        assert gff.get("Level")  == 20

    def test_utc_hp(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("MaxHitPoints") == 500

    def test_utc_fp(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("MaxFP") == 200

    def test_utc_saves(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("fortbonus") == 12
        assert gff.get("willbonus") == 15

    def test_utc_attributes(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("Str") == 20
        assert gff.get("Dex") == 18
        assert gff.get("Con") == 16

    def test_utc_faction(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("FactionID") == 2  # Hostile

    def test_utc_conversation_resref(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert str(gff.get("Conversation")) == "malak_conv"

    def test_utc_script_slots(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert str(gff.get("OnSpawn")) == "malak_sp"
        assert str(gff.get("OnDeath")) == "malak_de"

    def test_utc_flags(self):
        gff = read_gff(write_gff(make_full_utc()))
        assert gff.get("WillNotRender") == 0
        assert gff.get("IsPC")          == 0


class TestUTPFields:

    def test_utp_tag(self):
        gff = read_gff(write_gff(make_full_utp()))
        assert gff.get("Tag") == "plc_pedestal"

    def test_utp_resref(self):
        gff = read_gff(write_gff(make_full_utp()))
        assert str(gff.get("TemplateResRef")) == "plc_peds01"

    def test_utp_name(self):
        gff  = read_gff(write_gff(make_full_utp()))
        name = gff.get("LocalizedName")
        assert name.english == "Ancient Pedestal"

    def test_utp_appearance(self):
        gff = read_gff(write_gff(make_full_utp()))
        assert gff.get("Appearance") == 99

    def test_utp_hp(self):
        gff = read_gff(write_gff(make_full_utp()))
        assert gff.get("MaxHP") == 10

    def test_utp_flags(self):
        gff = read_gff(write_gff(make_full_utp()))
        assert gff.get("Static")      == 1
        assert gff.get("Useable")     == 1
        assert gff.get("HasInventory") == 0

    def test_utp_scripts(self):
        gff = read_gff(write_gff(make_full_utp()))
        assert str(gff.get("OnUsed")) == "plc_used"
        assert str(gff.get("OnOpen")) == "plc_open"


class TestUTDFields:

    def test_utd_tag(self):
        gff = read_gff(write_gff(make_full_utd()))
        assert gff.get("Tag") == "door_vault"

    def test_utd_resref(self):
        gff = read_gff(write_gff(make_full_utd()))
        assert str(gff.get("TemplateResRef")) == "door_vlt"

    def test_utd_name(self):
        gff  = read_gff(write_gff(make_full_utd()))
        name = gff.get("LocalizedName")
        assert name.english == "Vault Door"

    def test_utd_generic_type(self):
        gff = read_gff(write_gff(make_full_utd()))
        assert gff.get("GenericType") == 2

    def test_utd_linked_to(self):
        gff = read_gff(write_gff(make_full_utd()))
        assert gff.get("LinkedTo") == "VAULT_EXIT"
        assert gff.get("LinkedToFlags") == 1

    def test_utd_hp(self):
        gff = read_gff(write_gff(make_full_utd()))
        assert gff.get("MaxHP") == 50

    def test_utd_lock(self):
        gff = read_gff(write_gff(make_full_utd()))
        assert gff.get("Locked")    == 1
        assert gff.get("LockDC")    == 28
        assert gff.get("KeyRequired") == 0

    def test_utd_scripts(self):
        gff = read_gff(write_gff(make_full_utd()))
        assert str(gff.get("OnOpen"))   == "door_open"
        assert str(gff.get("OnClosed")) == "door_cls"
        assert str(gff.get("OnDeath"))  == "door_die"


class TestGffTypes:
    """Unit tests for the GFF type helpers."""

    def test_resref_normalize(self):
        rr = ResRef("C_GAMORREAN_01")
        assert rr.value == "c_gamorrean_01"

    def test_resref_max_length(self):
        rr = ResRef("a" * 30)
        assert len(rr.value) <= 16

    def test_resref_equality(self):
        assert ResRef("test") == ResRef("TEST")
        assert ResRef("test") == "test"

    def test_locstring_english(self):
        loc = LocString()
        loc.english = "Hello"
        assert loc.english == "Hello"
        assert loc.get_text(0) == "Hello"

    def test_locstring_strref(self):
        loc = LocString(strref=42001)
        assert loc.strref == 42001

    def test_gffstruct_get_default(self):
        s = GffStruct()
        assert s.get("missing_field", default=99) == 99

    def test_gffstruct_set_get(self):
        s = GffStruct()
        s.set("Str", GffFieldType.BYTE, 14)
        assert s.get("Str") == 14

    def test_gfffile_field_count(self):
        gff = GffFile(file_type="UTC ")
        gff.set("A", GffFieldType.CEXOSTRING, "alpha")
        gff.set("B", GffFieldType.CEXOSTRING, "beta")
        assert len(gff.root.fields) == 2
