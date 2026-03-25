"""
GhostRigger Test Suite — conftest.py

Shared fixtures and helpers for all pytest tests.
"""
import os
import sys
import struct
import pytest

# Ensure the project root is on the path
_ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, _ROOT)
# Also add src/ so that bare imports like `import kotormcp` resolve correctly
sys.path.insert(0, os.path.join(_ROOT, 'src'))

# ─── Pre-import real PIL so test_v41's _stub_pil() setdefault() calls find
# the genuine package already in sys.modules and leave it intact.
# This prevents the fake PIL stub from replacing PIL.Image when real
# Pillow is installed, which would cause AttributeError on Image.new() in
# tests that rely on genuine PIL (e.g. test_v43 UV-flip tests).
try:
    import PIL
    import PIL.Image
    import PIL.ImageDraw
    import PIL.ImageFont
    # PIL.ImageTk requires a Tk display; skip it here — test_v41 will stub
    # only this sub-module since the others are already present.
except ImportError:
    pass  # PIL not installed — stubs will be used as intended


# ─── Sample binary GFF builder ────────────────────────────────────────────────

def build_minimal_gff(file_type: str = "UTC ", **string_fields) -> bytes:
    """
    Build a minimal valid GFF V3.2 binary with the given string fields.
    Used for round-trip testing without requiring real game files.
    """
    import io
    from src.formats.gff_types import GffFieldType, GffFile, GffStruct, LocString, ResRef
    from src.formats.gff_writer import write_gff

    gff = GffFile(file_type=file_type, file_version="V3.2")
    for label, value in string_fields.items():
        gff.set(label, GffFieldType.CEXOSTRING, value)

    return write_gff(gff)


@pytest.fixture
def sample_utc_bytes():
    """A minimal UTC GFF with Tag and TemplateResRef."""
    from src.formats.gff_types import GffFieldType, GffFile, LocString, ResRef
    from src.formats.gff_writer import write_gff

    gff = GffFile(file_type="UTC ", file_version="V3.2")
    gff.set("Tag",            GffFieldType.CEXOSTRING,    "test_creature")
    gff.set("TemplateResRef", GffFieldType.RESREF,        ResRef("test_cr"))
    loc = LocString()
    loc.english = "Test Creature"
    gff.set("FirstName",      GffFieldType.CEXOLOCSTRING, loc)
    gff.set("MaxHitPoints",   GffFieldType.INT16,         40)
    gff.set("Str",            GffFieldType.BYTE,          14)
    gff.set("Dex",            GffFieldType.BYTE,          12)
    return write_gff(gff)


@pytest.fixture
def sample_utp_bytes():
    """A minimal UTP GFF for a placeable."""
    from src.formats.gff_types import GffFieldType, GffFile, LocString, ResRef
    from src.formats.gff_writer import write_gff

    gff = GffFile(file_type="UTP ", file_version="V3.2")
    gff.set("Tag",            GffFieldType.CEXOSTRING,    "plc_container01")
    gff.set("TemplateResRef", GffFieldType.RESREF,        ResRef("plc_c01"))
    loc = LocString()
    loc.english = "Storage Container"
    gff.set("LocalizedName",  GffFieldType.CEXOLOCSTRING, loc)
    gff.set("Appearance",     GffFieldType.UINT32,        4)
    gff.set("Useable",        GffFieldType.BYTE,          1)
    return write_gff(gff)


@pytest.fixture
def sample_utd_bytes():
    """A minimal UTD GFF for a door."""
    from src.formats.gff_types import GffFieldType, GffFile, LocString, ResRef
    from src.formats.gff_writer import write_gff

    gff = GffFile(file_type="UTD ", file_version="V3.2")
    gff.set("Tag",            GffFieldType.CEXOSTRING,    "door_001")
    gff.set("TemplateResRef", GffFieldType.RESREF,        ResRef("door001"))
    loc = LocString()
    loc.english = "Heavy Door"
    gff.set("LocalizedName",  GffFieldType.CEXOLOCSTRING, loc)
    gff.set("GenericType",    GffFieldType.BYTE,          0)
    gff.set("MaxHP",          GffFieldType.INT16,         30)
    return write_gff(gff)
