"""GFF (Generic File Format) data structures and utilities.

GFF is the primary structured data format used throughout KotOR for storing
game data, including character templates, areas, dialogs, and more.

References:
----------
    Based on unified K1 (swkotor.exe) and TSL (swkotor2.exe) GFF implementation.
    Addresses: (K1: swkotor.exe, TSL: swkotor2.exe Aspyr build).

    - CResGFF::CreateGFFFile
        K1: 0x00411260, TSL: 0x00626530
        Creates new GFF file with file_type and version.
        * Sets file_type from 4-character string (e.g., "UTI ", "DLG ", "ARE ")
        * Sets file_version from GFFVersion string "V3.2" (see below)
        * Creates root struct with AddStruct(this, 0xffffffff)

    - CResGFF::WriteGFFFile
        K1: 0x00413030, TSL: 0x00626700
        Writes GFF data to file.
        * Opens file with "wb" mode
        * Calls Pack() to prepare data
        * Calls WriteGFFData() to write binary format

    - CResGFF::WriteGFFData
        K1: 0x004113d0, TSL: 0x006267d0
        Writes GFF header and data sections.
        * Writes 0x38 byte header
        * Writes structs (12 bytes each), fields (12 bytes each), labels (16 bytes each)
        * Writes field_data, field_indices, list_indices

    - GFFVersion string "V3.2" (hardcoded GFF version identifier)
        K1: 0x0073e2c8, TSL: 0x0099794c (CreateGFFFile uses pointer at 0x009f44d8)

    - "gff" string (GFF format/extension identifier, resource extension table)
        K1: 0x0074dd00 (referenced by CreateResourceExtensionTable @ 0x005e6d20)
        TSL: TODO: locate in swkotor2.exe (resource table layout differs)

    Dialog (DLG) loading (GFF-based):
        - CSWSDialog::LoadDialog (loads dialog from GFF structure): K1: 0x005a2ae0, TSL: TODO
        - CSWSDialog::LoadDialogBase (loads dialog base properties): K1: 0x0059f5f0, TSL: TODO
        - CSWSDialog::LoadDialogLinkedNode (loads linked dialog nodes; called from LoadDialog): K1: 0x0059ec10, TSL: TODO

    Note: GFF is used for all structured game data; critical to understand for modding.
    All game resources (UTM, GUI, UTI, UTP, UTC, UTD, UTW, UTT, UTS, UTE, PTH, JRL, IFO, ARE, FAC, DLG)
    are stored as GFF files with different 4-character type identifiers.
"""

from __future__ import annotations

import difflib
import math

from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import PureWindowsPath
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

from loggerplus import RobustLogger  # type: ignore[import-untyped]  # pyright: ignore[reportMissingTypeStubs]
from pykotor.common.language import LocalizedString
from pykotor.common.misc import ResRef
from pykotor.resource.formats._base import ComparableMixin
from pykotor.resource.type import ResourceType
from utility.common.geometry import Vector3, Vector4
from utility.common.misc_string.util import format_text
from utility.error_handling import safe_repr  # pyright: ignore[reportMissingImports]
from utility.string_util import normalize_string

if TYPE_CHECKING:
    import os

    from collections.abc import Callable, Generator, Iterator

    from typing_extensions import Self

T = TypeVar("T")
U = TypeVar("U")
GFFStructType = TypeVar("GFFStructType", bound="GFFStruct")


# Max lines per side for difflib; larger inputs use a short summary to avoid O(n*m) timeout
_FORMAT_DIFF_MAX_LINES = 4000


def format_diff(
    old_value: object,
    new_value: object,
    name: str,
    *,
    format_type: str = "unified",
) -> str:
    # Convert values to strings if they aren't already
    str_old_value: list[str] = str(old_value).splitlines(keepends=True)
    str_new_value: list[str] = str(new_value).splitlines(keepends=True)

    # Avoid difflib on huge inputs (SequenceMatcher is O(n*m), can timeout)
    if len(str_old_value) > _FORMAT_DIFF_MAX_LINES or len(str_new_value) > _FORMAT_DIFF_MAX_LINES:
        return (
            f"(old){name}: {len(str_old_value)} lines\n"
            f"(new){name}: {len(str_new_value)} lines\n"
            "(diff omitted: value too large)"
        )

    # Generate diff based on format type
    if format_type == "unified":
        diff: Iterator[str] = difflib.unified_diff(
            str_old_value,
            str_new_value,
            fromfile=f"(old){name}",
            tofile=f"(new){name}",
            lineterm="",
        )
    elif format_type == "context":
        diff = difflib.context_diff(
            str_old_value,
            str_new_value,
            fromfile=f"(old){name}",
            tofile=f"(new){name}",
            lineterm="",
        )
    else:  # default to unified for unsupported formats
        diff = difflib.unified_diff(
            str_old_value,
            str_new_value,
            fromfile=f"(old){name}",
            tofile=f"(new){name}",
            lineterm="",
        )

    # Return formatted diff
    return "\n".join(diff)


class GFFContent(Enum):
    """The different resources that the GFF can represent."""

    GFF = "GFF "
    BIC = "BIC "
    BTC = "BTC "
    BTD = "BTD "  # guess
    BTE = "BTE "  # guess
    BTI = "BTI "
    BTP = "BTP "  # guess
    BTM = "BTM "  # guess
    BTT = "BTT "  # guess
    UTC = "UTC "
    UTD = "UTD "
    UTE = "UTE "
    UTI = "UTI "
    UTP = "UTP "
    UTS = "UTS "
    UTM = "UTM "
    UTT = "UTT "
    UTW = "UTW "
    ARE = "ARE "
    DLG = "DLG "
    FAC = "FAC "
    GIT = "GIT "
    GUI = "GUI "
    IFO = "IFO "
    ITP = "ITP "
    JRL = "JRL "
    PTH = "PTH "
    NFO = "NFO "  # savenfo.res
    PT = "PT  "  # partytable.res
    GVT = "GVT "  # GLOBALVARS.res
    INV = "INV "  # inventory in SAVEGAME.res

    @classmethod
    def has_value(
        cls,
        value: GFFContent | str,  # noqa: E501
    ) -> bool:
        if isinstance(value, GFFContent):
            value = value.value
        if not isinstance(value, str):
            raise TypeError(value)
        return any(gff_content.value == value.upper() for gff_content in cls)

    @classmethod
    def get_valid_types(cls) -> set[str]:
        return {x.name for x in cls}

    @classmethod
    def get_extensions(cls) -> set[str]:
        gff_extensions: set[str] = set()
        res_contents: set[GFFContent] = {cls.PTH, cls.NFO, cls.PT, cls.GVT, cls.INV}
        for content_enum in cls:
            if content_enum in res_contents:
                gff_extensions.add("res")
                continue
            gff_extensions.add(normalize_string(content_enum.value))
        return gff_extensions

    @classmethod
    def get_restypes(cls) -> set[ResourceType]:
        gff_restypes: set[ResourceType] = set()
        res_contents: set[GFFContent] = {cls.PTH, cls.NFO, cls.PT, cls.GVT, cls.INV}
        for content_enum in cls:
            if content_enum in res_contents:
                gff_restypes.add(ResourceType.RES)
                continue
            gff_restypes.add(ResourceType.from_extension(normalize_string(content_enum.value)).target_type())
        return gff_restypes

    @classmethod
    def from_res(cls, resname: str) -> GFFContent | None:
        lower_resname = resname.lower()
        gff_content = None
        if lower_resname == "savenfo":
            gff_content = GFFContent.NFO
        elif lower_resname == "partytable":
            gff_content = GFFContent.PT
        elif lower_resname == "globalvars":
            gff_content = GFFContent.GVT
        elif lower_resname == "inventory":
            gff_content = GFFContent.INV
        return gff_content


def _normalize_string_for_compare(value: object) -> str:
    """Normalize string for comparison to avoid false positives from whitespace/line endings.

    Engine behavior: GFF string fields are compared byte-wise; trailing whitespace and
    CRLF vs LF can differ between tools. Normalizing allows semantically equal values
    to match. Used in GFFStruct.compare for String and LocalizedString fields.
    """
    if not isinstance(value, str):
        return str(value) if value is not None else ""
    # Normalize line endings to \n, strip trailing whitespace from each line and overall
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")).rstrip()


@dataclass
class GFFListSemanticConfig:
    """Configuration for semantic identity matching of GFF list elements.

    Used to correctly detect modified entries (same logical item, different fields)
    vs added/removed entries. Prevents false "2 added + 2 removed" when the same
    structs have optional fields added (e.g., GuaranteedCount in UTE CreatureList).

    Attributes:
    ----------
        identity_fields: Field names that uniquely identify a list entry. Used to
            match structs across old/new (e.g., ResRef+CR+Appearance for creature spawns).
        default_when_absent: Map field_name -> default value. When a field is absent
            in one side, treat it as this default for identity and comparison.
            E.g., {"GuaranteedCount": 0} for UTE CreatureList (K2 field, default 0).
        ignorable_when_value: Map field_name -> value(s). When a field is added with
            this value (or removed when the effective value would be this), treat as
            no change. E.g., {"GuaranteedCount": 0} - adding GuaranteedCount=0 is
            ignorable (K2 default; engine reads 0 when absent).
    """

    identity_fields: tuple[str, ...]
    default_when_absent: dict[str, Any] = field(default_factory=dict)
    ignorable_when_value: dict[str, Any] = field(default_factory=dict)


# Registry: (GFFContent, list_field_name) -> semantic config for list comparison.
# When present, list entries are matched by identity_fields + default_when_absent,
# so "same creature, new optional field" is reported as MODIFIED not ADDED+REMOVED.
# Engine: K1 ReadEncounterFromGff @ 0x00592430 reads ResRef, CR, SingleSpawn only (no Appearance).
# TSL FUN_007eb810 reads ResRef, CR, SingleSpawn, GuaranteedCount. Appearance is toolset-only.
_GFF_LIST_SEMANTIC_REGISTRY: dict[tuple[GFFContent, str], GFFListSemanticConfig] = {
    # Engine: K1 ReadEncounterFromGff @ 0x00592430, TSL FUN_007eb810 read ResRef, CR, SingleSpawn (+ GuaranteedCount TSL).
    # Appearance is toolset-only; use ResRef+CR+SingleSpawn for identity so K1/TSL files match correctly.
    (GFFContent.UTE, "CreatureList"): GFFListSemanticConfig(
        identity_fields=("ResRef", "CR", "SingleSpawn"),
        default_when_absent={"GuaranteedCount": 0, "Appearance": 0},
        ignorable_when_value={"GuaranteedCount": 0},
    ),
}

# Registry of ignorable field values, keyed by (GFFContent, list_field_name | None).
# list_field_name: apply only when comparing structs inside that list (e.g. "CreatureList").
# None: apply to root/toplevel struct fields.
# Used when comparing GFFs: fields added/removed with these values are treated as no-change.
# Prefer GFFContent enum; never use raw strings for content type.
#
# Engine references:
#   K1 SaveEncounter @ 0x00591350: CreatureList writes ResRef, CR, SingleSpawn only.
#   TSL FUN_007ed770: CreatureList writes ResRef, CR, SingleSpawn, GuaranteedCount.
#   K1 lacks GuaranteedCount; TSL default 0 when absent. Ignorable for diff.
_GFF_IGNORABLE_FIELD_VALUES: dict[tuple[GFFContent, str | None], dict[str, frozenset[Any]]] = {
    (GFFContent.UTE, "CreatureList"): {"GuaranteedCount": frozenset({0})},
}


def _build_ignorable_for_content(content: GFFContent) -> dict[str, set[Any]] | None:
    """Merge all ignorable field values for a GFF content type.

    Merges entries keyed by (content, list_field) and (content, None).
    Returns None if no ignorable entries exist.
    """
    merged: dict[str, set[Any]] = {}
    for (gff_content, _list_field), field_map in _GFF_IGNORABLE_FIELD_VALUES.items():
        if gff_content != content:
            continue
        for label, values in field_map.items():
            existing = merged.get(label)
            vals = set(values)
            merged[label] = (existing | vals) if existing else vals
    return merged if merged else None


def _infer_gff_content_from_path(path: PureWindowsPath | str | None) -> GFFContent | None:
    """Infer GFF content type from path (e.g., 'foo.ute' -> GFFContent.UTE)."""
    if path is None:
        return None
    parts = PureWindowsPath(str(path)).parts
    if not parts:
        return None
    first = parts[0]
    if "." in first:
        ext = normalize_string(first.split(".")[-1])
        for content in GFFContent:
            if normalize_string(content.value) == ext:
                return content
    return None


def _list_field_name_from_path(path: PureWindowsPath | str | None) -> str | None:
    """Extract the list field name from path (e.g., 'root/CreatureList' -> 'CreatureList')."""
    if path is None:
        return None
    parts = PureWindowsPath(str(path)).parts
    return parts[-1] if parts else None


class GFFFieldType(IntEnum):
    """The different types of fields based off what kind of data it stores."""

    UInt8 = 0
    Int8 = 1
    UInt16 = 2
    Int16 = 3
    UInt32 = 4
    Int32 = 5
    UInt64 = 6
    Int64 = 7
    Single = 8
    Double = 9
    String = 10
    ResRef = 11
    LocalizedString = 12
    Binary = 13
    Struct = 14
    List = 15
    Vector4 = 16
    Vector3 = 17

    def return_type(  # noqa: C901, PLR0911
        self,
    ) -> type[int | str | ResRef | Vector3 | Vector4 | LocalizedString | GFFStruct | GFFList | bytes | float]:  # type: ignore[valid-type]
        if self in {
            GFFFieldType.UInt8,
            GFFFieldType.UInt16,
            GFFFieldType.UInt32,
            GFFFieldType.UInt64,
            GFFFieldType.Int8,
            GFFFieldType.Int16,
            GFFFieldType.Int32,
            GFFFieldType.Int64,
        }:
            return int
        if self == GFFFieldType.String:
            return str
        if self == GFFFieldType.ResRef:
            return ResRef
        if self == GFFFieldType.Vector3:
            return Vector3
        if self == GFFFieldType.Vector4:
            return Vector4
        if self == GFFFieldType.LocalizedString:
            return LocalizedString
        if self == GFFFieldType.Struct:
            return GFFStruct
        if self == GFFFieldType.List:
            return GFFList
        if self == GFFFieldType.Binary:
            return bytes
        if self in {GFFFieldType.Double, GFFFieldType.Single}:
            return float
        raise ValueError(self)


@dataclass(frozen=True)
class GFFFieldView:
    """Lightweight view over a GFF field (label, type, value).

    Returns immutable tuples instead of exposing internal storage directly.
    """

    label: str
    type: GFFFieldType
    value: Any


class Difference:
    def __init__(
        self,
        path: PureWindowsPath | str,
        old_value: object,
        new_value: object,
    ):
        """Initializes a Difference instance representing a specific difference between two GFFStructs.

        Args:
        ----
            path (PureWindowsPath | str): The path to the value within the GFFStruct where the difference was found.
            old_value (object): The value from the original GFFStruct at the specified path.
            new_value (object): The value from the compared GFFStruct at the specified path.
        """
        self.path: PureWindowsPath = PureWindowsPath(path)
        self.old_value: object = old_value
        self.new_value: object = new_value

    def __repr__(self):
        return f"Difference(path={self.path}, old_value={self.old_value}, new_value={self.new_value})"


class GFFComparisonResult:
    """Class to store comprehensive results of a GFF comparison."""

    def __init__(self):
        self.field_stats: dict[str, dict[str, int]] = {
            "extra": {},  # Fields present in target but not source
            "mismatched": {},  # Fields present in both but with different values
            "missing": {},  # Fields missing in the target GFF
            "used": {},  # Fields that were successfully compared
        }
        self.struct_id_mismatches: list[tuple[str, int, int]] = []  # (path, source_id, target_id)
        self.field_count_mismatches: list[tuple[str, int, int]] = []  # (path, source_count, target_count)
        self.value_mismatches: list[tuple[str, str, Any, Any]] = []  # (path, field_type, source_val, target_val)

    def __bool__(self) -> bool:
        return self.is_identical

    @property
    def is_identical(self) -> bool:
        return not (self.struct_id_mismatches or self.field_count_mismatches or self.value_mismatches)

    def has_field_differences(self) -> bool:
        """Return True if any extra/missing/mismatched field stats were recorded."""
        return any(self.field_stats.get(category) for category in ("missing", "extra", "mismatched"))

    def add_field_stat(self, category: str, field_name: str) -> None:
        """Increment the count for a field in a given category."""
        self.field_stats[category][field_name] = self.field_stats[category].get(field_name, 0) + 1

    def add_struct_id_mismatch(
        self,
        path: str,
        source_id: int,
        target_id: int,
    ) -> None:
        """Record a struct ID mismatch."""
        self.struct_id_mismatches.append((path, source_id, target_id))

    def add_field_count_mismatch(
        self,
        path: str,
        source_count: int,
        target_count: int,
    ) -> None:
        """Record a field count mismatch."""
        self.field_count_mismatches.append((path, source_count, target_count))

    def add_value_mismatch(
        self,
        path: str,
        field_type: str,
        source_val: Any,
        target_val: Any,
    ) -> None:
        """Record a value mismatch."""
        self.value_mismatches.append((path, field_type, source_val, target_val))


class GFF(ComparableMixin):
    """Represents the data of a GFF file."""

    BINARY_TYPE: ResourceType = ResourceType.GFF
    COMPARABLE_FIELDS = ("content", "root")

    def __init__(
        self,
        content: GFFContent = GFFContent.GFF,
    ):
        self.content: GFFContent = content
        self.root: GFFStruct = GFFStruct(-1)

    def fields(self) -> list[GFFFieldView]:
        """Return the root struct fields in insertion order.

        Returns immutable views at the file level for convenience.
        """
        return self.root.fields()

    def print_tree(
        self,
        root: GFFStruct | None = None,
        indent: int = 0,
        column_len: int = 40,
    ):
        if root is None:
            root = self.root

        for label, field_type, value in root:
            length_or_id: int = -2
            gff_struct: GFFStruct = value
            gff_list: GFFList = value
            if field_type == GFFFieldType.Struct:
                length_or_id = gff_struct.struct_id
            if field_type == GFFFieldType.List:
                length_or_id = len(gff_list)

            print(("  " * indent + label).ljust(column_len), " ", length_or_id)

            if field_type == GFFFieldType.Struct:
                self.print_tree(value, indent + 1)
            if field_type == GFFFieldType.List:
                for i, gff_struct in enumerate(value):
                    print(
                        f"  {'  ' * indent}[Struct {i}]".ljust(column_len),
                        " ",
                        gff_struct.struct_id,
                    )
                    self.print_tree(gff_struct, indent + 2)

    def compare(  # noqa: C901, PLR0911, PLR0912, PLR0913, PLR0915
        self,
        other: object,
        log_func: Callable[..., Any] = print,
        path: PureWindowsPath | None = None,
        ignore_default_changes: bool = False,  # noqa: FBT001, FBT002
        comparison_result: GFFComparisonResult | None = None,
        format_type: str = "structured",
    ) -> bool:
        """Compare two GFF objects.

        Args:
        ----
            self: The GFF object to compare from
            other: {object}: The GFF object to compare to
            log_func: Function used to log comparison messages (default print)
            path: Optional path to write comparison report to
            ignore_default_changes: Whether to ignore default/empty changes

        Returns:
        -------
            bool: True if structures are the same, False otherwise

        Processing Logic:
        ----------------
            - Compare root nodes of both GFFs
            - Recursively compare child nodes
            - Collect statistics about field usage and mismatches
            - Return comprehensive comparison results
        """
        # For unified diff format, skip structured logging and just return comparison result
        if format_type == "unified":
            if not isinstance(other, GFF):
                return False
            comparison_result = comparison_result or GFFComparisonResult()
            ign = _build_ignorable_for_content(self.content)
            return self.root.compare(
                other.root,
                log_func,
                path,
                ignore_default_changes,
                ignore_values=ign,
                comparison_result=comparison_result,
                format_type=format_type,
                gff_content=self.content,
            )

        if not isinstance(other, GFF):
            log_func("", message_type="diff")
            log_func("", message_type="diff")
            return False

        # Build ignorable field values from content type (e.g. UTE CreatureList GuaranteedCount=0)
        ignorable = _build_ignorable_for_content(self.content)

        # Always do the full recursive comparison via GFFStruct.compare() so that
        # every added/removed/changed field is reported with its full GFF-internal
        # path (e.g. "c_dewback2.utc/FeatList/[2]/Feat").  GFFStruct.compare()
        # already handles field-count mismatches itself and continues the diff.
        comparison_result = comparison_result or GFFComparisonResult()
        return self.root.compare(
            other.root,
            log_func,
            path,
            ignore_default_changes,
            ignore_values=ignorable or None,
            comparison_result=comparison_result,
            format_type=format_type,
            gff_content=self.content,
        )

    def __str__(self) -> str:
        """Return a human-readable string representation of the GFF."""
        return str(self.root)


class _GFFField:
    """Read-only data structure for items stored in GFFStruct."""

    INTEGER_TYPES: ClassVar[set[GFFFieldType]] = {
        GFFFieldType.Int8,
        GFFFieldType.UInt8,
        GFFFieldType.Int16,
        GFFFieldType.UInt16,
        GFFFieldType.Int32,
        GFFFieldType.UInt32,
        GFFFieldType.Int64,
        GFFFieldType.UInt64,
    }
    STRING_TYPES: ClassVar[set[GFFFieldType]] = {
        GFFFieldType.String,
        GFFFieldType.ResRef,
    }
    FLOAT_TYPES: ClassVar[set[GFFFieldType]] = {
        GFFFieldType.Single,
        GFFFieldType.Double,
    }

    def __init__(
        self,
        field_type: GFFFieldType,
        value: Any,
    ):
        self._field_type: GFFFieldType = field_type
        self._value: Any = value
        if field_type in self.INTEGER_TYPES:
            self._value = int(value)
        else:
            self._value = value

    def field_type(self) -> GFFFieldType:
        """Returns the field type.

        Returns:
        -------
            The field's field_type.
        """
        return self._field_type

    def value(self) -> Any:
        """Returns the value.

        Returns:
        -------
            The field's value.
        """
        return self._value


class GFFStruct(ComparableMixin, dict):
    """Stores a collection of GFFFields in a GFF tree node.

    GFFStruct represents a single structure (node) in the GFF tree hierarchy. Each struct
    has a user-defined ID and contains named fields that can be primitives, other structs,
    or lists of structs.

    References:
    ----------
        Based on unified K1/TSL GFF structure. See module docstring for full addresses.
        - CResGFF::CreateGFFFile (K1: 0x00411260, TSL: 0x00626530)
        - CResGFF::WriteGFFFile (K1: 0x00413030, TSL: 0x00626700)
        - CResGFF::WriteGFFData (K1: 0x004113d0, TSL: 0x006267d0)
        - GFFVersion "V3.2" (K1: 0x0073e2c8, TSL: 0x0099794c)
        GFF struct format specification



    Attributes:
    ----------
        struct_id: User-defined struct type ID (uint32 in binary format)
            Used to differentiate struct types (e.g., creature vs door stats)
            Typical values: 0 for most structs, specific IDs for template types

        _fields: Dictionary mapping field labels to _GFFField instances
            Labels are ASCII strings (max 16 chars) that identify fields
            Field order matters for binary compatibility (maintains insertion order in Python 3.7+)
            Empty structs are valid (field count = 0)

    Binary Format Notes:
    -------------------
        Each struct in binary is 12 bytes:
            - 4 bytes: struct_id (uint32)
            - 4 bytes: DataOrDataOffset (int32) - field index or field indices array offset
            - 4 bytes: FieldCount (uint32) - number of fields in struct

        Reference: https://github.com/th3w1zard1/Kotor.NET/tree/master/GFFBinaryStructure.cs:159-164, KotOR_IO/GFF.cs:114-152

        Field count optimization (Kotor.NET/GFFBinaryWriter.cs:59-72):
            - If FieldCount == 0: DataOrDataOffset = -1 (empty struct)
            - If FieldCount == 1: DataOrDataOffset = field array index directly
            - If FieldCount > 1: DataOrDataOffset = byte offset into field indices array
    """

    COMPARABLE_FIELDS = ("struct_id", "_fields")

    def __init__(
        self,
        struct_id: int = 0,
    ):
        # Initialize dict first
        super().__init__()

        # User-defined struct type identifier (uint32 in binary)
        self.struct_id: int = struct_id

        # Ordered dictionary of field labels to field instances
        self._fields: dict[str, _GFFField] = {}

    def __copy__(self) -> Self:
        """Support `copy.copy(GFFStruct)` without going through `dict` reconstruction.

        `GFFStruct` subclasses `dict` for historical compatibility, but direct item-setting is
        intentionally forbidden via `__setitem__`. The stdlib `copy` module will otherwise try
        to reconstruct the dict portion by iterating `items()` and assigning, which triggers
        our `__setitem__` guard and breaks callers (including PyKotor's own tests).
        """
        new_obj = self.__class__(self.struct_id)
        # Shallow copy: preserves field objects/values but isolates the container.
        new_obj._fields = self._fields.copy()
        return new_obj

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        """Support `copy.deepcopy(GFFStruct)`."""
        new_obj = self.__class__(self.struct_id)
        memo[id(self)] = new_obj
        new_obj._fields = deepcopy(self._fields, memo)
        return new_obj

    @classmethod
    def _from_reduce(
        cls,
        struct_id: int,
        fields: dict[str, _GFFField],
    ) -> Self:
        obj = cls(struct_id)
        obj._fields = fields  # TODO: determimne if deepcopy is needed here
        return obj

    def __reduce_ex__(self, protocol: int):
        """Override dict's reduce to avoid dict-item reconstruction via `__setitem__`."""
        # Shallow-copy semantics for `copy.copy`: the `copy` module uses reduce for built-ins.
        return (self.__class__._from_reduce, (self.struct_id, self._fields.copy()))

    def __getitem__(self, key: str) -> Any:
        """Get field value by label, supporting both dict-style and existing API access."""
        if isinstance(key, str):
            return self._fields[key].value()
        return NotImplemented  # type: ignore[no-any-return]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set field value by label. For backwards compatibility, this is not allowed directly."""
        # For backwards compatibility, we don't allow direct dict-style setting
        # Users should use the typed setter methods (set_string, set_int32, etc.)
        raise TypeError("Cannot set GFF field values directly. Use typed setter methods like set_string(), set_int32(), etc.")

    def __delitem__(self, key: str) -> None:
        """Remove field by label."""
        if isinstance(key, str):
            if key in self._fields:
                del self._fields[key]
        else:
            raise TypeError("GFFStruct keys must be strings")

    def __contains__(self, key: object) -> bool:
        """Check if field exists."""
        return isinstance(key, str) and key in self._fields

    def __len__(self) -> int:
        """Return number of fields in this struct.

        `GFFStruct` stores its fields in `_fields` (not the inherited `dict` storage), but many
        callers (including the binary writer) use `len(struct)` to determine field counts.
        """
        return len(self._fields)

    def keys(self):
        """Return field labels (dict compatibility)."""
        return self._fields.keys()

    def values(self):
        """Return field values (dict compatibility)."""
        for field in self._fields.values():
            yield field.value()

    def items(self):
        """Return field label-value pairs (dict compatibility)."""
        for label, field in self._fields.items():
            yield label, field.value()

    def get(self, key: str, default=None):
        """Get field value with default (dict compatibility)."""
        if key in self._fields:
            return self._fields[key].value()
        return default

    def __repr__(self) -> str:
        if not self._fields:
            return f"GFFStruct(struct_id={self.struct_id}, fields=[])"

        summary_items = []
        for idx, (label, field) in enumerate(self._fields.items()):
            if idx >= 3:
                summary_items.append(f"... ({len(self._fields) - 3} more)")
                break
            field_label = label or f"<unnamed:{idx}>"
            summary_items.append(f"{field_label}:{field.field_type().name}")

        summary = ", ".join(summary_items)
        return f"GFFStruct(struct_id={self.struct_id}, fields=[{summary}])"

    def __str__(self) -> str:
        def _format_value(value: Any) -> str:
            if isinstance(value, GFFStruct):
                return f"<Struct#{value.struct_id}>"
            if isinstance(value, GFFList):
                return f"<List[{len(value)}]>"
            if isinstance(value, bytes):
                return f"<bytes len={len(value)}>"
            value_str = repr(value) if isinstance(value, (str, int, float, bool)) else str(value)
            return value_str if len(value_str) <= 80 else f"{value_str[:77]}..."

        lines: list[str] = [f"GFFStruct #{self.struct_id} ({len(self._fields)} fields)"]
        if not self._fields:
            lines.append("  <empty>")
            return "\n".join(lines)

        for label, field in self._fields.items():
            field_label = label or "<unnamed>"
            field_type = field.field_type().name
            value = field.value()
            lines.append(f"  {field_label} ({field_type}): {_format_value(value)}")

        return "\n".join(lines)

    def __iter__(self) -> Generator[tuple[str, GFFFieldType, Any], Any, None]:
        """Iterates through the stored fields yielding each field's (label, type, value)."""
        for label, field in self._fields.items():
            yield label, field.field_type(), field.value()

    def fields(self) -> list[GFFFieldView]:
        """Return lightweight field views preserving insertion order.

        Returns immutable views so callers cannot mutate `_fields` directly.
        """
        return [GFFFieldView(label or "", field.field_type(), field.value()) for label, field in self._fields.items()]

    def remove(
        self,
        label: str,
    ):
        """Removes the field with the specified label.

        Args:
        ----
            label: The field label.
        """
        if label in self._fields:
            self._fields.pop(label)

    def exists(
        self,
        label: str,
    ) -> bool:
        """Returns the type of the field with the specified label.

        Args:
        ----
            label: The field label.

        Returns:
        -------
            A boolean result of whether the field exists or not.
        """
        return label in self._fields

    def compare(  # noqa: C901, PLR0911, PLR0912, PLR0913, PLR0915
        self,
        other: object,
        log_func: Callable = print,  # noqa: FBT001
        current_path: PureWindowsPath | os.PathLike | str | None = None,
        ignore_default_changes: bool = False,  # noqa: FBT001, FBT002
        ignore_values: dict[str, set[Any]] | None = None,
        comparison_result: GFFComparisonResult | None = None,
        format_type: str = "structured",
        gff_content: GFFContent | None = None,
    ) -> bool:
        """Recursively compares two GFFStructs.

        Functionally similar to __eq__, but collects comprehensive comparison statistics

        Args:
        ----
            other: {object}: GFFStruct to compare against
            log_func: {Callable}: Function to log differences. Defaults to print.
            current_path: {PureWindowsPath | os.PathLike | str | None}: Path of structure being compared
            ignore_default_changes: {bool}: Whether to ignore default/empty changes
            ignore_values: {dict[str, set[Any]] | None}: Dictionary of field labels and their ignorable values
            comparison_result: {GFFComparisonResult | None}: Object to store comparison statistics

        Returns:
        -------
            bool: True if structures are the same, False otherwise
        """
        # For unified diff format, use a no-op logger to skip structured logging
        if format_type == "unified":

            def noop_log_func(*args, **kwargs):
                pass

            log_func = noop_log_func

        ignore_labels: set[str] = {
            "KTInfoDate",
            "KTGameVerIndex",
            "KTInfoVersion",
            "EditorInfo",
        }
        ignore_values = ignore_values or {}
        comparison_result = comparison_result or GFFComparisonResult()

        def is_ignorable_value(label: str, v: Any) -> bool:
            """Check if a value is ignorable for a specific label."""
            return not v or str(v) in {"0", "-1"} or (label in ignore_values and v in ignore_values[label])

        def is_ignorable_comparison(
            label: str,
            old_value: object,
            new_value: object,
        ) -> bool:
            return is_ignorable_value(label, old_value) and is_ignorable_value(label, new_value)

        current_path = PureWindowsPath(current_path or "GFFRoot")
        if not isinstance(other, GFFStruct):
            log_func(f"GFFStruct counts have changed at '{current_path}': '{len(self)}' --> '<unknown>'", message_type="diff")
            log_func("", message_type="diff")
            comparison_result.add_field_count_mismatch(str(current_path), len(self), 0)
            return False
        # Create dictionaries for both old and new structures (needed for field count check with ignore_default_changes)
        old_dict_pre: dict[str, tuple[GFFFieldType, Any]] = {
            label or f"gffstruct({idx})": (ftype, value) for idx, (label, ftype, value) in enumerate(self) if label not in ignore_labels
        }
        new_dict_pre: dict[str, tuple[GFFFieldType, Any]] = {
            label or f"gffstruct({idx})": (ftype, value) for idx, (label, ftype, value) in enumerate(other) if label not in ignore_labels
        }

        # Check field count difference, but only report if not ignoring default changes or if extra fields are non-default
        if len(old_dict_pre) != len(new_dict_pre):
            if not ignore_default_changes:
                log_func("", message_type="diff")
                log_func(f"GFFStruct: number of fields have changed at '{current_path}': '{len(old_dict_pre)}' --> '{len(new_dict_pre)}'", message_type="diff")
                comparison_result.add_field_count_mismatch(str(current_path), len(old_dict_pre), len(new_dict_pre))
            else:
                # When ignoring default changes, check if extra fields in old/new are all default/empty
                extra_in_old = set(old_dict_pre.keys()) - set(new_dict_pre.keys())
                extra_in_new = set(new_dict_pre.keys()) - set(old_dict_pre.keys())

                # If no extra fields in either direction, no mismatch
                if not extra_in_old and not extra_in_new:
                    pass  # Field counts match after filtering
                else:
                    # Check if extra fields in old are all ignorable (empty sets return True from all())
                    all_extra_ignorable = not extra_in_old or all(is_ignorable_value(label, old_dict_pre[label][1]) for label in extra_in_old)

                    # Check if extra fields in new are all ignorable
                    all_new_extra_ignorable = not extra_in_new or all(is_ignorable_value(label, new_dict_pre[label][1]) for label in extra_in_new)

                    # Only report mismatch if extra fields are non-default
                    if not all_extra_ignorable or not all_new_extra_ignorable:
                        log_func("", message_type="diff")
                        log_func(f"GFFStruct: number of fields have changed at '{current_path}': '{len(old_dict_pre)}' --> '{len(new_dict_pre)}'", message_type="diff")
                        comparison_result.add_field_count_mismatch(str(current_path), len(old_dict_pre), len(new_dict_pre))

        if self.struct_id != other.struct_id:
            log_func("", message_type="diff")
            comparison_result.add_struct_id_mismatch(str(current_path), self.struct_id, other.struct_id)

        # Use the dictionaries already created above
        old_dict: dict[str, tuple[GFFFieldType, Any]] = old_dict_pre
        new_dict: dict[str, tuple[GFFFieldType, Any]] = new_dict_pre

        # Union of labels from both old and new structures
        all_labels: set[str] = set(old_dict.keys()) | set(new_dict.keys())

        for label in all_labels:
            child_path: PureWindowsPath = current_path / str(label)  # pyright: ignore[reportOperatorIssue]
            old_ftype, old_value = old_dict.get(label, (None, None))
            new_ftype, new_value = new_dict.get(label, (None, None))

            if ignore_default_changes and is_ignorable_comparison(label, old_value, new_value):
                continue

            # Check for missing fields/values in either structure
            if old_ftype is None or old_value is None:
                if new_ftype is None:
                    msg: str = f"new_ftype shouldn't be None here. Relevance: old_ftype={old_ftype!r}, old_value={old_value!r}, new_value={new_value!r}"
                    raise RuntimeError(msg)
                # When ignore_default_changes: treat "field added with default value" as ignorable
                if ignore_default_changes and is_ignorable_value(label, new_value):
                    continue
                log_func(f"Field '{label}' ({new_ftype.name}) added: {format_text(safe_repr(new_value))}", message_type="diff")
                comparison_result.add_field_stat("extra", label)
                continue

            if new_value is None or new_ftype is None:
                log_func(f"Missing '{old_ftype.name}' field at '{child_path}': {format_text(safe_repr(old_value))}", message_type="diff")
                comparison_result.add_field_stat("missing", label)
                continue

            # Check if field types have changed
            if old_ftype != new_ftype:
                log_func("", message_type="diff")
                comparison_result.add_field_stat("mismatched", label)
                comparison_result.add_value_mismatch(str(child_path), "field_type", old_ftype.name, new_ftype.name)
                continue

            # Compare values depending on their types
            if old_ftype == GFFFieldType.Struct:
                assert isinstance(new_value, GFFStruct), f"{type(new_value).__name__}: {new_value}"
                cur_struct_this: GFFStruct = old_value
                if cur_struct_this.struct_id != new_value.struct_id:
                    log_func("", message_type="diff")
                    comparison_result.add_struct_id_mismatch(str(child_path), cur_struct_this.struct_id, new_value.struct_id)

                if not cur_struct_this.compare(
                    new_value,
                    log_func,
                    child_path,
                    ignore_default_changes=ignore_default_changes,
                    ignore_values=ignore_values,
                    comparison_result=comparison_result,
                    format_type=format_type,
                    gff_content=gff_content,
                ):
                    continue
            elif old_ftype == GFFFieldType.List:
                gff_list: GFFList = old_value
                if not gff_list.compare(
                    new_value,
                    log_func,
                    child_path,
                    ignore_default_changes=ignore_default_changes,
                    ignore_values=ignore_values,
                    comparison_result=comparison_result,
                    format_type=format_type,
                    gff_content=gff_content,
                ):
                    continue
            elif old_ftype == GFFFieldType.String and isinstance(old_value, str) and isinstance(new_value, str):
                # Normalize to avoid false positives from CRLF vs LF, trailing whitespace
                if _normalize_string_for_compare(old_value) == _normalize_string_for_compare(new_value):
                    comparison_result.add_field_stat("used", label)
                    continue
                log_func("", message_type="diff")
                log_func(format_diff(old_value, new_value, label), message_type="diff")
                comparison_result.add_field_stat("mismatched", label)
                comparison_result.add_value_mismatch(str(child_path), old_ftype.name, old_value, new_value)
                continue
            elif old_value != new_value:
                if isinstance(old_value, float) and isinstance(new_value, float) and math.isclose(old_value, new_value, rel_tol=1e-4, abs_tol=1e-4):
                    comparison_result.add_field_stat("used", label)
                    continue

                if str(old_value) == str(new_value):
                    log_func(
                        f"Field '{old_ftype.name}' is different at '{child_path}': String representations match, but have other properties that don't (such as a lang id difference)."
                    )  # noqa: E501
                    continue
                log_func("", message_type="diff")
                log_func(format_diff(old_value, new_value, label), message_type="diff")
                comparison_result.add_field_stat("mismatched", label)
                comparison_result.add_value_mismatch(str(child_path), old_ftype.name, old_value, new_value)
                continue

            comparison_result.add_field_stat("used", label)

        return bool(comparison_result)

    def what_type(
        self,
        label: str,
    ) -> GFFFieldType:
        return self._fields[label].field_type()

    def acquire(
        self,
        label: str,
        default: T,
        object_type: type[U | T] | tuple[type[U], ...] | None = None,
    ) -> T | U:
        """Gets the value from the specified field.

        Args:
        ----
            label: The field label.
            default: Default value to return if value does not match object_type.
            object_type: The type of the field value. If not specified it will match the default's type.

        Returns:
        -------
            The field value. If the field does not exist or the value type does not match the specified type then the default is returned instead.
        """
        default_cls = default.__class__
        assert isinstance(default, object), f"{default_cls.__name__}: {default}"
        value: T = default
        if object_type is None:
            object_type = default_cls
        if (
            self.exists(label)
            and object_type is not None
        ):
            value = self[label]
            try:
                print(f"value: {value} cls: {value.__class__} (isinstance? {isinstance(value, object_type)} {object_type})")
            except Exception:
                ...
        if object_type is bool and issubclass(value.__class__, int):
            value = bool(value)
        return value

    def value(
        self,
        label: str,
    ) -> Any:
        return self._fields[label].value()

    def merge(
        self,
        other: GFFStruct,
    ):
        """Updates this GFFStruct with any missing fields from the other GFFStruct, deepcopying their values.

        Args:
        ----
            other: The GFFStruct from which missing fields will be sourced.
        """
        self._add_missing(self, other)

    @staticmethod
    def _add_missing(
        target: GFFStruct,
        source: GFFStruct,
        relpath: PureWindowsPath | None = None,
    ):  # noqa: C901, PLR0912
        """Static method to update target with missing fields from source, handling nested structures.

        Args:
        ----
            target: The GFFStruct to which fields will be added if they are missing.
            source: The GFFStruct from which missing fields will be sourced.
        """
        relpath = PureWindowsPath(".") if relpath is None else relpath
        for label, field_type, value in source:
            if target.exists(label):
                if field_type == GFFFieldType.Struct:
                    assert isinstance(value, GFFStruct)
                    value._add_missing(value, source.get_struct(label, GFFStruct()), relpath.joinpath(label))  # noqa: SLF001  # pyright: ignore[reportOptionalMemberAccess]
                elif field_type == GFFFieldType.List:
                    assert isinstance(value, GFFList)
                    target_list: GFFList = target.get_list(label, GFFList())
                    for i, (target_item, source_item) in enumerate(zip(target_list, value)):
                        assert isinstance(target_item, GFFStruct)
                        target_item._add_missing(target_item, source_item, relpath.joinpath(label, str(i)))  # noqa: SLF001  # pyright: ignore[reportOptionalMemberAccess]
            else:
                RobustLogger().debug(f"Adding {field_type!r} '{relpath.joinpath(label)}' to target.")  # pyright: ignore[reportOptionalMemberAccess]
                if field_type == GFFFieldType.UInt8:
                    target.set_uint8(label, deepcopy(value))
                elif field_type == GFFFieldType.UInt16:
                    target.set_uint16(label, deepcopy(value))
                elif field_type == GFFFieldType.UInt32:
                    target.set_uint32(label, deepcopy(value))
                elif field_type == GFFFieldType.UInt64:
                    target.set_uint64(label, deepcopy(value))
                elif field_type == GFFFieldType.Int8:
                    target.set_int8(label, deepcopy(value))
                elif field_type == GFFFieldType.Int16:
                    target.set_int16(label, deepcopy(value))
                elif field_type == GFFFieldType.Int32:
                    target.set_int32(label, deepcopy(value))
                elif field_type == GFFFieldType.Int64:
                    target.set_int64(label, deepcopy(value))
                elif field_type == GFFFieldType.Single:
                    target.set_single(label, deepcopy(value))
                elif field_type == GFFFieldType.Double:
                    target.set_double(label, deepcopy(value))
                elif field_type == GFFFieldType.ResRef:
                    target.set_resref(label, deepcopy(value))
                elif field_type == GFFFieldType.String:
                    target.set_string(label, deepcopy(value))
                elif field_type == GFFFieldType.LocalizedString:
                    target.set_locstring(label, deepcopy(value))
                elif field_type == GFFFieldType.Binary:
                    target.set_binary(label, deepcopy(value))
                elif field_type == GFFFieldType.Vector3:
                    target.set_vector3(label, deepcopy(value))
                elif field_type == GFFFieldType.Vector4:
                    target.set_vector4(label, deepcopy(value))
                elif field_type == GFFFieldType.Struct:
                    target.set_struct(label, deepcopy(value))
                elif field_type == GFFFieldType.List:
                    target.set_list(label, deepcopy(value))

    def set_uint8(
        self,
        label: str,
        value: int,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.UInt8, value)

    def set_uint16(
        self,
        label: str,
        value: int,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.UInt16, value)

    def set_uint32(
        self,
        label: str,
        value: int,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.UInt32, value)

    def set_uint64(
        self,
        label: str,
        value: int,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.UInt64, value)

    def set_int8(
        self,
        label: str,
        value: int,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Int8, value)

    def set_int16(
        self,
        label: str,
        value: int,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Int16, value)

    def set_int32(
        self,
        label: str,
        value: int,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Int32, value)

    def set_int64(
        self,
        label: str,
        value: int,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Int64, value)

    def set_single(
        self,
        label: str,
        value: float,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Single, value)

    def set_double(
        self,
        label: str,
        value: float,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Double, value)

    def set_resref(
        self,
        label: str,
        value: ResRef,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.ResRef, value)

    def set_string(
        self,
        label: str,
        value: str,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.String, value)

    def set_locstring(
        self,
        label: str,
        value: LocalizedString,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.LocalizedString, value)

    def set_binary(
        self,
        label: str,
        value: bytes,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Binary, value)

    def set_vector3(
        self,
        label: str,
        value: Vector3,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Vector3, value)

    def set_vector4(
        self,
        label: str,
        value: Vector4,
    ):
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.
        """
        self._fields[label] = _GFFField(GFFFieldType.Vector4, value)

    def set_struct(
        self,
        label: str,
        value: GFFStruct,
    ) -> GFFStruct:
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.

        Returns:
        -------
            The value that was passed to the method.
        """
        self._fields[label] = _GFFField(GFFFieldType.Struct, value)
        return value

    def set_list(
        self,
        label: str,
        value: GFFList,
    ) -> GFFList:
        """Sets the value and field type of the field with the specified label.

        Args:
        ----
            label: The field label.
            value: The new field value.

        Returns:
        -------
            The value that was passed to the method.
        """
        self._fields[label] = _GFFField(GFFFieldType.List, value)
        return value

    def get_uint8(
        self,
        label: str,
        default: T = 0,
    ) -> int | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a UInt8.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.UInt8:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_uint16(
        self,
        label: str,
        default: T = 0,
    ) -> int | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a UInt16.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.UInt16:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_uint32(
        self,
        label: str,
        default: T = 0,
    ) -> int | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a UInt32.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.UInt32:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_uint64(
        self,
        label: str,
        default: T = 0,
    ) -> int | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a UInt64.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.UInt64:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_int8(
        self,
        label: str,
        default: T = 0,
    ) -> int | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not an Int8.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Int8:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_int16(
        self,
        label: str,
        default: T = 0,
    ) -> int | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not an Int16.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Int16:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_int32(
        self,
        label: str,
        default: T = 0,
    ) -> int | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not an Int32.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Int32:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_int64(
        self,
        label: str,
        default: T = 0,
    ) -> int | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not an Int64.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Int64:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_single(
        self,
        label: str,
        default: T = 0.0,
    ) -> float | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a Single.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Single:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_double(
        self,
        label: str,
        default: T = 0.0,
    ) -> float | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a Double.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Double:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_resref(
        self,
        label: str,
        default: T = None,
    ) -> ResRef | T:
        """Returns a copy of the value from the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a ResRef.

        Returns:
        -------
            A copy of the field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.ResRef:
                return default
            return deepcopy(self._fields[label].value())
        except KeyError:
            return default

    def get_string(
        self,
        label: str,
        default: T = "",
    ) -> str | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a String.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.String:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_locstring(
        self,
        label: str,
        default: T = None,
    ) -> LocalizedString | T:
        """Returns a copy of the value from the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a LocalizedString.

        Returns:
        -------
            A copy of the field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.LocalizedString:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_vector3(
        self,
        label: str,
        default: T = None,
    ) -> Vector3 | T:
        """Returns a copy of the value from the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a Vector3.

        Returns:
        -------
            A copy of the field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Vector3:
                return default
            return copy(self._fields[label].value())
        except KeyError:
            return default

    def get_vector4(
        self,
        label: str,
        default: T = None,
    ) -> Vector4 | T:
        """Returns a copy of the value from the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a Vector4.

        Returns:
        -------
            A copy of the field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Vector4:
                return default
            return copy(self._fields[label].value())
        except KeyError:
            return default

    def get_binary(
        self,
        label: str,
        default: T = None,
    ) -> bytes | T:
        """Returns the value of the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not Binary.

        Returns:
        -------
            The field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Binary:
                return default
            return self._fields[label].value()
        except KeyError:
            return default

    def get_struct(
        self,
        label: str,
        default: T = None,
    ) -> GFFStruct | T:
        """Returns a copy of the value from the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a Struct.

        Returns:
        -------
            A copy of the field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.Struct:
                return default
            return copy(self._fields[label].value())
        except KeyError:
            return default

    def get_list(
        self,
        label: str,
        default: T = None,
    ) -> GFFList | T:
        """Returns a copy of the value from the field with the specified label.

        Args:
        ----
            label: The field label.
            default: The default value to return if the field does not exist or is not a List.

        Returns:
        -------
            A copy of the field value or the default value.
        """
        try:
            if self._fields[label].field_type() != GFFFieldType.List:
                return default
            return copy(self._fields[label].value())
        except KeyError:
            return default

    @contextmanager
    def batch_update(self):
        """Context manager for batch updates with validation and rollback on error.

        If an exception occurs during the batch update, all changes are rolled back.

        Example:
        -------
            with struct.batch_update():
                struct.set_string("Name", "New Value")
                struct.set_int32("Level", 10)
                # If any error occurs, all changes are rolled back
        """
        original_fields = deepcopy(self._fields)
        try:
            yield self
        except Exception:
            # Rollback on error
            self._fields = original_fields
            raise

    def get_nested_struct(
        self,
        *path: str,
        default: T = None,
    ) -> GFFStruct | T:
        """Safely navigate nested struct paths.

        Args:
        ----
            *path: Variable-length path of field labels to navigate.
            default: Default value to return if path doesn't exist.

        Returns:
        -------
            The nested GFFStruct at the path, or default if path is invalid.

        Example:
        -------
            # Navigate: root -> Appearance -> Model
            model_struct = struct.get_nested_struct("Appearance", "Model")
        """
        current: GFFStruct | Any = self
        for segment in path:
            if not isinstance(current, GFFStruct):
                return default
            if not current.exists(segment) or current.what_type(segment) != GFFFieldType.Struct:
                return default
            current = current.get_struct(segment)
        return current if isinstance(current, GFFStruct) else default

    def get_nested_string(
        self,
        *path: str,
        default: str = "",
    ) -> str:
        """Get string value from nested path.

        Args:
        ----
            *path: Variable-length path ending with a String field label.
            default: Default value to return if path doesn't exist.

        Returns:
        -------
            The string value at the path, or default if path is invalid.

        Example:
        -------
            # Get: root -> Appearance -> ModelName
            model_name = struct.get_nested_string("Appearance", "ModelName", default="unknown")
        """
        if not path:
            return default
        if len(path) == 1:
            return self.get_string(path[0], default)

        parent_path = path[:-1]
        field_name = path[-1]

        parent = self.get_nested_struct(*parent_path)
        if parent is None:
            return default

        return parent.get_string(field_name, default)

    def get_nested_int32(
        self,
        *path: str,
        default: int = 0,
    ) -> int:
        """Get Int32 value from nested path.

        Args:
        ----
            *path: Variable-length path ending with an Int32 field label.
            default: Default value to return if path doesn't exist.

        Returns:
        -------
            The Int32 value at the path, or default if path is invalid.

        Example:
        -------
            # Get: root -> Stats -> Level
            level = struct.get_nested_int32("Stats", "Level", default=1)
        """
        if not path:
            return default
        if len(path) == 1:
            return self.get_int32(path[0], default)

        parent_path = path[:-1]
        field_name = path[-1]

        parent = self.get_nested_struct(*parent_path)
        if parent is None:
            return default

        return parent.get_int32(field_name, default)

    def get_nested_uint32(
        self,
        *path: str,
        default: int = 0,
    ) -> int:
        """Get UInt32 value from nested path.

        Args:
        ----
            *path: Variable-length path ending with a UInt32 field label.
            default: Default value to return if path doesn't exist.

        Returns:
        -------
            The UInt32 value at the path, or default if path is invalid.
        """
        if not path:
            return default
        if len(path) == 1:
            return self.get_uint32(path[0], default)

        parent_path = path[:-1]
        field_name = path[-1]

        parent = self.get_nested_struct(*parent_path)
        if parent is None:
            return default

        return parent.get_uint32(field_name, default)

    def find_fields(
        self,
        field_name: str,
        field_type: GFFFieldType | None = None,
    ) -> list[tuple[str, Any]]:
        """Find all fields matching the given name and optionally type, recursively.

        Args:
        ----
            field_name: The field label to search for.
            field_type: Optional field type to filter by.

        Returns:
        -------
            List of (path, value) tuples where path is the dot-separated path to the field.

        Example:
        -------
            # Find all "ModelName" fields in the struct tree
            results = struct.find_fields("ModelName")
            # Returns: [("Appearance.ModelName", "model_001"), ("Alternate.ModelName", "model_002")]
        """
        results: list[tuple[str, Any]] = []

        def _search_recursive(
            current: GFFStruct | GFFList,
            current_path: str = "",
        ) -> None:
            if isinstance(current, GFFStruct):
                for label, ftype, value in current:
                    full_path = f"{current_path}.{label}" if current_path else label
                    if label == field_name and (field_type is None or ftype == field_type):
                        results.append((full_path, value))
                    if ftype == GFFFieldType.Struct and isinstance(value, GFFStruct):
                        _search_recursive(value, full_path)
                    elif ftype == GFFFieldType.List and isinstance(value, GFFList):
                        _search_recursive(value, full_path)
            elif isinstance(current, GFFList):
                for idx, struct in enumerate(current):
                    list_path = f"{current_path}[{idx}]" if current_path else f"[{idx}]"
                    _search_recursive(struct, list_path)

        _search_recursive(self)
        return results


class GFFList(ComparableMixin, list):
    """A collection of GFFStructs."""

    COMPARABLE_SEQUENCE_FIELDS = ("_structs",)

    def __init__(self):
        # Initialize list first
        super().__init__()
        self._structs: list[GFFStruct] = []

    def __copy__(self) -> "GFFList":
        """Support `copy.copy(GFFList)` safely.

        `GFFList` subclasses `list`, but stores its real content in `_structs`. The default
        `list` reduce/copy path will copy `__dict__`/state in a way that can transiently share
        `_structs` between source and destination during reconstruction, and then populate the
        destination by iterating the source — which becomes unbounded if `_structs` is shared.
        """
        new_obj = GFFList()
        new_obj._structs = self._structs.copy()
        return new_obj

    def __deepcopy__(self, memo: dict[int, object]) -> "GFFList":
        new_obj = GFFList()
        memo[id(self)] = new_obj
        new_obj._structs = deepcopy(self._structs, memo)
        return new_obj

    @staticmethod
    def _from_reduce(structs: list[GFFStruct]) -> "GFFList":
        obj = GFFList()
        obj._structs = structs
        return obj

    def __reduce_ex__(self, protocol: int):
        """Override list's reduce to avoid shared `_structs` during reconstruction."""
        return (GFFList._from_reduce, (self._structs.copy(),))

    def __getitem__(self, index: int) -> GFFStruct:
        """Returns the struct at the specified index."""
        return self._structs[index]

    def __setitem__(self, index: int, value: GFFStruct) -> None:
        """Set struct at specified index."""
        if not isinstance(value, GFFStruct):
            raise TypeError("GFFList elements must be GFFStruct instances")
        self._structs[index] = value

    def __delitem__(self, index: int) -> None:
        """Remove struct at specified index."""
        del self._structs[index]

    def __iter__(self):
        """Iterate through structs."""
        return iter(self._structs)

    def __len__(self) -> int:
        """Returns the number of elements in _structs."""
        return len(self._structs)

    def append(self, struct: GFFStruct) -> None:
        """Appends an existing struct to the list without creating a copy.

        Args:
        ----
            struct: The `GFFStruct` instance to append.

        Raises:
        ------
            TypeError: If `struct` is not an instance of `GFFStruct`.
        """
        if not isinstance(struct, GFFStruct):
            struct_type = type(struct)
            RobustLogger().error(f"Failed to append struct; expected GFFStruct, received {struct_type!r}.")
            msg = f"The struct must be a GFFStruct instance, got {struct_type!r} instead."
            raise TypeError(msg)

        self._structs.append(struct)
        RobustLogger().debug(f"Appended Struct#{struct.struct_id} to GFFList; list_length={len(self._structs)}.")

    def extend(self, other):
        """Extend list with another iterable of GFFStructs."""
        for item in other:
            self.append(item)

    def insert(self, index: int, struct: GFFStruct) -> None:
        """Insert struct at specified index."""
        if not isinstance(struct, GFFStruct):
            raise TypeError("GFFList elements must be GFFStruct instances")
        self._structs.insert(index, struct)

    def __repr__(self) -> str:
        """Returns a detailed string representation of the GFFList."""
        if not self._structs:
            return "GFFList([])"

        # Show summary with struct IDs
        struct_ids = [f"Struct#{s.struct_id}" for s in self._structs[:3]]
        preview = ", ".join(struct_ids)
        if len(self._structs) > 3:  # noqa: PLR2004
            preview += f", ... ({len(self._structs) - 3} more)"

        return f"GFFList([{preview}], total={len(self._structs)})"

    def __str__(self) -> str:
        """Returns a human-readable string representation of the GFFList."""
        if not self._structs:
            return "GFFList (empty)"

        lines = [f"GFFList with {len(self._structs)} structs:"]
        for i, struct in enumerate(self._structs):
            lines.append(f"  [{i}] Struct#{struct.struct_id} ({len(struct)} fields)")
            # Show first few fields of each struct
            max_fields_preview = 3
            for field_count, (label, field_type, value) in enumerate(struct):
                if field_count >= max_fields_preview:
                    lines.append(f"      ... ({len(struct) - max_fields_preview} more fields)")
                    break
                # Format value based on type
                if field_type == GFFFieldType.Struct:
                    value_str = f"<Struct#{value.struct_id}>"
                elif field_type == GFFFieldType.List:
                    value_str = f"<List[{len(value)}]>"
                elif isinstance(value, (str, int, float)):
                    value_str = repr(value)
                else:
                    value_str = str(value)
                lines.append(f"      {label}: {value_str}")

        return "\n".join(lines)

    def add(
        self,
        struct_id: int,
    ) -> GFFStruct:
        """Adds a new struct into the list.

        Args:
        ----
            struct_id: The StructID of the new struct.
        """
        new_struct = GFFStruct(struct_id)
        self._structs.append(new_struct)
        return new_struct

    def at(
        self,
        index: int,
    ) -> GFFStruct | None:
        """Returns the struct at the index if it exists, otherwise returns None.

        Args:
        ----
            index: The index of the desired struct.

        Returns:
        -------
            The corresponding GFFList or None.
        """
        return self._structs[index] if index < len(self._structs) else None

    def remove(
        self,
        index: int,
    ):
        """Removes the struct at the specified index.

        Args:
        ----
            index: The index of the desired struct.
        """
        self._structs.pop(index)

    def compare(
        self,
        other: object,
        log_func: Callable[..., Any] = print,  # noqa: FBT001
        current_path: PureWindowsPath | None = None,
        *,
        ignore_default_changes: bool = False,
        ignore_values: dict[str, set[Any]] | None = None,
        comparison_result: GFFComparisonResult | None = None,
        format_type: str = "structured",
        gff_content: GFFContent | None = None,
    ) -> bool:
        """Compare two GFFLists with semantic identity matching and merge-aware output.

        Uses a registry of known list types (e.g., UTE CreatureList) to match entries by
        identity fields (ResRef, CR, etc.) rather than raw field set. This correctly
        reports "N modified (field X added)" instead of false "N added + N removed"
        when the same entries have optional fields added (e.g., GuaranteedCount in K2).

        Output format (canonical, industry-standard):
        - MODIFIED: Same logical entry, different fields (field-level diff); merge-safe
        - ADDED: Entry present only in new
        - REMOVED: Entry present only in old
        - REORDERED: Same entry, different index
        - Summary: X modified, Y added, Z removed, W reordered
        """
        if format_type == "unified":

            def noop_log_func(*args, **kwargs): ...

            log_func = noop_log_func

        current_path = PureWindowsPath(str(current_path or "GFFList"))
        comparison_result = comparison_result or GFFComparisonResult()

        if not isinstance(other, GFFList):
            log_func(
                f"GFFList '{current_path}': type mismatch (old has {len(self)} entries, new is not a GFFList)",
                message_type="diff",
            )
            log_func("", message_type="diff")
            return False

        len1, len2 = len(self), len(other)
        path_str = str(current_path)

        # Helpers for hashable/normalized values (used by both semantic and content keys)
        _FLOAT_KEY_PRECISION = 6

        def _hashable_value(value: Any) -> Any:
            from pykotor.common.language import LocalizedString
            from pykotor.common.misc import ResRef
            from utility.common.geometry import Vector3, Vector4

            if value is None or isinstance(value, (int, str, bool, bytes)):
                return value
            if isinstance(value, float):
                return round(value, _FLOAT_KEY_PRECISION)
            if isinstance(value, ResRef):
                return ("ResRef", str(value))
            if isinstance(value, Vector3):
                return ("Vector3", round(value.x, _FLOAT_KEY_PRECISION), round(value.y, _FLOAT_KEY_PRECISION), round(value.z, _FLOAT_KEY_PRECISION))
            if isinstance(value, Vector4):
                return (
                    "Vector4",
                    round(value.x, _FLOAT_KEY_PRECISION),
                    round(value.y, _FLOAT_KEY_PRECISION),
                    round(value.z, _FLOAT_KEY_PRECISION),
                    round(value.w, _FLOAT_KEY_PRECISION),
                )
            if isinstance(value, LocalizedString):
                return ("LocalizedString", value.stringref, tuple((lang, gender, text) for lang, gender, text in value))
            if isinstance(value, GFFStruct):
                return struct_key(value)
            if isinstance(value, GFFList):
                return tuple(sorted(struct_key(s) for s in value))
            if isinstance(value, (list, tuple, set)):
                return tuple(_hashable_value(item) for item in value)
            if isinstance(value, dict):
                return tuple(sorted((key, _hashable_value(val)) for key, val in value.items()))
            return ("repr", repr(value))

        def struct_key(struct: GFFStruct) -> tuple[int, tuple[tuple[str, GFFFieldType, Any], ...]]:
            return (
                struct.struct_id,
                tuple(sorted((label, field_type, _hashable_value(value)) for label, field_type, value in struct)),
            )

        # Semantic config: match by identity fields + default_when_absent.
        # Prefer explicit gff_content from caller (GFF.compare); fallback to path inference.
        content_for_lookup = gff_content or _infer_gff_content_from_path(current_path)
        list_field = _list_field_name_from_path(current_path)
        semantic_config: GFFListSemanticConfig | None = None
        if content_for_lookup and list_field:
            semantic_config = _GFF_LIST_SEMANTIC_REGISTRY.get((content_for_lookup, list_field))

        def _get_field_val(struct: GFFStruct, label: str, defaults: dict[str, Any]) -> Any:
            for lbl, ftype, val in struct:
                if lbl == label:
                    return _hashable_value(val)
            return _hashable_value(defaults.get(label))

        def semantic_identity_key(struct: GFFStruct, config: GFFListSemanticConfig) -> tuple[Any, ...]:
            return tuple((label, _get_field_val(struct, label, config.default_when_absent)) for label in config.identity_fields)

        # Use semantic matching when config exists
        if semantic_config is not None:
            old_sem_map: dict[tuple[Any, ...], list[tuple[int, GFFStruct]]] = {}
            new_sem_map: dict[tuple[Any, ...], list[tuple[int, GFFStruct]]] = {}
            for idx, s in enumerate(self):
                key = semantic_identity_key(s, semantic_config)
                old_sem_map.setdefault(key, []).append((idx, s))
            for idx, s in enumerate(other):
                key = semantic_identity_key(s, semantic_config)
                new_sem_map.setdefault(key, []).append((idx, s))

            matched_keys = set(old_sem_map.keys()) & set(new_sem_map.keys())
            added_keys = set(new_sem_map.keys()) - set(old_sem_map.keys())
            removed_keys = set(old_sem_map.keys()) - set(new_sem_map.keys())

            modified_count = 0
            added_count = 0
            removed_count = 0
            reordered_count = 0

            # Report size mismatch
            if len1 != len2:
                log_func(
                    f"GFFList '{path_str}': length {len1} -> {len2} (diff: {len2 - len1:+d})",
                    message_type="diff",
                )
                comparison_result.add_field_count_mismatch(path_str, len1, len2)

            # MODIFIED or REORDERED: same semantic identity
            for key in sorted(matched_keys, key=lambda k: (new_sem_map[k][0][0],) + k):
                old_entries = old_sem_map[key]
                new_entries = new_sem_map[key]
                for (old_idx, old_struct), (new_idx, new_struct) in zip(old_entries, new_entries):
                    full_old_key = struct_key(old_struct)
                    full_new_key = struct_key(new_struct)
                    if full_old_key != full_new_key:
                        child_result = GFFComparisonResult()
                        old_struct.compare(
                            new_struct,
                            lambda *a, **k: None,  # no-op during probe
                            current_path / str(new_idx),
                            ignore_default_changes=ignore_default_changes,
                            ignore_values=ignore_values,
                            comparison_result=child_result,
                            format_type=format_type,
                            gff_content=gff_content,
                        )
                        if child_result.has_field_differences():
                            modified_count += 1
                            log_func(
                                f"\nGFFList '{path_str}': entry [old:{old_idx}] <-> [new:{new_idx}] MODIFIED (same logical entry, field changes; merge-safe)",
                                message_type="diff",
                            )
                            old_struct.compare(
                                new_struct,
                                log_func,
                                current_path / str(new_idx),
                                ignore_default_changes=ignore_default_changes,
                                ignore_values=ignore_values,
                                comparison_result=comparison_result,
                                format_type=format_type,
                                gff_content=gff_content,
                            )
                    elif old_idx != new_idx:
                        reordered_count += 1
                        log_func(
                            f"GFFList '{path_str}': entry moved [old:{old_idx}] -> [new:{new_idx}] (REORDERED, no field change)",
                            message_type="diff",
                        )

            # ADDED: only in new (not mergeable—new entry)
            for key in sorted(added_keys, key=lambda k: new_sem_map[k][0][0]):
                for idx, struct in new_sem_map[key]:
                    added_count += 1
                    log_func(f"\nGFFList '{path_str}': entry [new:{idx}] ADDED (present only in new file; merge-safe to add):", message_type="diff")
                    for label, field_type, val in struct:
                        log_func(f"  + {field_type.name} {label}: {format_text(val)}", message_type="diff")
                    comparison_result.add_field_stat("extra", path_str)

            # REMOVED: only in old (not mergeable—deleted entry)
            for key in sorted(removed_keys, key=lambda k: old_sem_map[k][0][0]):
                for idx, struct in old_sem_map[key]:
                    removed_count += 1
                    log_func(f"\nGFFList '{path_str}': entry [old:{idx}] REMOVED (present only in old file; merge-safe to delete):", message_type="diff")
                    for label, field_type, val in struct:
                        log_func(f"  - {field_type.name} {label}: {format_text(val)}", message_type="diff")
                    comparison_result.add_field_stat("missing", path_str)

            has_diff = bool(modified_count or added_count or removed_count or reordered_count or len1 != len2)
            if has_diff:
                parts: list[str] = []
                if modified_count:
                    parts.append(f"{modified_count} modified (same logical entry, field changes; merge-safe)")
                if added_count:
                    parts.append(f"{added_count} added (only in new)")
                if removed_count:
                    parts.append(f"{removed_count} removed (only in old)")
                if reordered_count:
                    parts.append(f"{reordered_count} reordered")
                log_func(
                    f"\nGFFList '{path_str}' Summary: {', '.join(parts)}",
                    message_type="diff",
                )
            return not has_diff

        # Fallback: full content key (no semantic config)
        old_map: dict[tuple[Any, ...], list[int]] = {}
        new_map: dict[tuple[Any, ...], list[int]] = {}
        for idx, s in enumerate(self):
            k = struct_key(s)
            old_map.setdefault(k, []).append(idx)
        for idx, s in enumerate(other):
            k = struct_key(s)
            new_map.setdefault(k, []).append(idx)

        added_keys = set(new_map.keys()) - set(old_map.keys())
        removed_keys = set(old_map.keys()) - set(new_map.keys())
        common_keys = set(old_map.keys()) & set(new_map.keys())

        if len1 != len2:
            log_func(f"GFFList '{path_str}': length {len1} -> {len2} (diff: {len2 - len1:+d})", message_type="diff")
            comparison_result.add_field_count_mismatch(path_str, len1, len2)

        reported_old: set[int] = set()
        reported_new: set[int] = set()
        modified_count = 0
        moved_count = 0

        for key in sorted(added_keys, key=lambda k: new_map[k][0]):
            for idx in new_map[key]:
                log_func(f"\nGFFList '{path_str}': entry [new:{idx}] ADDED:", message_type="diff")
                for label, ftype, val in other[idx]:
                    log_func(f"  + {ftype.name} {label}: {format_text(val)}", message_type="diff")
                comparison_result.add_field_stat("extra", path_str)
                reported_new.add(idx)

        for key in sorted(removed_keys, key=lambda k: old_map[k][0]):
            for idx in old_map[key]:
                log_func(f"\nGFFList '{path_str}': entry [old:{idx}] REMOVED:", message_type="diff")
                for label, ftype, val in self[idx]:
                    log_func(f"  - {ftype.name} {label}: {format_text(val)}", message_type="diff")
                comparison_result.add_field_stat("missing", path_str)
                reported_old.add(idx)

        for key in common_keys:
            oidxs, nidxs = old_map[key], new_map[key]
            if set(oidxs) != set(nidxs):
                moved_count += 1
                log_func(
                    f"GFFList '{path_str}': entry REORDERED [{sorted(oidxs)}] -> [{sorted(nidxs)}]",
                    message_type="diff",
                )
                reported_old.update(oidxs)
                reported_new.update(nidxs)

        max_idx = min(len1, len2)
        for idx in range(max_idx):
            if idx in reported_old or idx in reported_new:
                continue
            if struct_key(self[idx]) != struct_key(other[idx]):
                modified_count += 1
                log_func(f"\nGFFList '{path_str}': entry [{idx}] MODIFIED:", message_type="diff")
                self[idx].compare(
                    other[idx],
                    log_func,
                    current_path / str(idx),
                    ignore_default_changes=ignore_default_changes,
                    comparison_result=comparison_result,
                    format_type=format_type,
                    gff_content=gff_content,
                )
                comparison_result.add_field_stat("mismatched", path_str)

        for idx in range(max_idx):
            if idx in reported_old or idx in reported_new:
                continue
            self[idx].compare(
                other[idx],
                log_func,
                current_path / str(idx),
                ignore_default_changes=ignore_default_changes,
                comparison_result=comparison_result,
                format_type=format_type,
                gff_content=gff_content,
            )

        has_diff = bool(added_keys or removed_keys or moved_count or modified_count or len1 != len2)
        if has_diff:
            log_func(
                f"\nGFFList '{path_str}' Summary: {modified_count} modified, {len(added_keys)} added, {len(removed_keys)} removed, {moved_count} reordered",
                message_type="diff",
            )
        return not has_diff
