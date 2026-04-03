"""Comprehensive reference finding utilities for KotOR resources.

This module provides functions to find references to scripts, tags, resrefs, conversations,
and other values across GFF files, NCS bytecode, and 2DA files in a KotOR installation.

Based on the functionality of the KotOR findrefs utility, integrated into PyKotor.
"""

from __future__ import annotations

import fnmatch
import re

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.gff import GFFFieldType, GFFList, GFFStruct, read_gff
from pykotor.resource.formats.ncs import NCSByteCode, NCSInstructionQualifier
from pykotor.resource.type import ResourceType

if TYPE_CHECKING:
    from pykotor.extract.file import FileResource
    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.gff import GFF


@dataclass(frozen=True)
class ReferenceSearchResult:
    """Result of a reference search operation.

    Attributes:
    ----------
        file_resource: The FileResource where the reference was found
        field_path: GFF field path where match was found (e.g., "ScriptHeartbeat", "ItemList[0].InventoryRes")
        matched_value: The value that was matched
        file_type: The file type abbreviation (e.g., "UTC", "UTD", "NCS")
        byte_offset: Optional byte offset for NCS matches
    """

    file_resource: FileResource
    field_path: str
    matched_value: str
    file_type: str
    byte_offset: int | None = None


def _field_type_int(field_type: GFFFieldType | int) -> int:
    """Convert a GFF field type enum/int to integer form for fast comparisons."""
    return field_type.value if isinstance(field_type, GFFFieldType) else field_type


def _safe_read_gff(resource: FileResource) -> GFF | None:
    """Safely read a GFF file, returning None on failure."""
    try:
        return read_gff(resource.data())
    except (ValueError, OSError):
        return None


def _build_field_path(path_prefix: str, label: str) -> str:
    """Build a field path string, handling empty prefix."""
    return f"{path_prefix}.{label}" if path_prefix else label


def _recurse_nested_gff_field(
    field_type_int: int,
    value: Any,
    label: str,
    path_prefix: str,
    recurse_struct: Callable[[GFFStruct, str], None],
    *,
    struct_type: int,
    list_type: int,
) -> None:
    """Recurse into nested GFF Struct/List fields."""
    if field_type_int == struct_type and isinstance(value, GFFStruct):
        new_path = _build_field_path(path_prefix, label)
        recurse_struct(value, new_path)
    elif field_type_int == list_type and isinstance(value, GFFList):
        base_path = _build_field_path(path_prefix, label)
        for idx, item in enumerate(value):
            if isinstance(item, GFFStruct):
                list_path = f"{base_path}[{idx}]"
                recurse_struct(item, list_path)


def find_script_references(
    installation: Installation,
    script_resref: str,
    *,
    partial_match: bool = False,
    case_sensitive: bool = False,
    file_pattern: str | None = None,
    file_types: set[str] | None = None,
    logger: Callable[[str], None] | None = None,
) -> list[ReferenceSearchResult]:
    """Find all references to a script (NCS/NSS) resref in GFF files and NCS bytecode.

    Args:
    ----
        installation: The installation to search
        script_resref: The script resref to search for (without extension)
        partial_match: If True, allow partial matches (e.g., "test" matches "testscript")
        case_sensitive: If True, perform case-sensitive matching
        file_pattern: Optional file pattern to filter results (e.g., "*.mod", "*_s.rim")
        file_types: Optional set of file type abbreviations to search (e.g., {"UTC", "UTD", "ARE"})
        logger: Optional logging function

    Returns:
    -------
        List of ReferenceSearchResult objects
    """
    return find_resref_references(
        installation=installation,
        resref=script_resref,
        field_types={GFFFieldType.ResRef},
        search_ncs=True,
        partial_match=partial_match,
        case_sensitive=case_sensitive,
        file_pattern=file_pattern,
        file_types=file_types,
        logger=logger,
    )


def find_tag_references(
    installation: Installation,
    tag: str,
    *,
    partial_match: bool = False,
    case_sensitive: bool = False,
    file_pattern: str | None = None,
    file_types: set[str] | None = None,
    logger: Callable[[str], None] | None = None,
) -> list[ReferenceSearchResult]:
    """Find all references to a tag in GFF files.

    Args:
    ----
        installation: The installation to search
        tag: The tag value to search for
        partial_match: If True, allow partial matches
        case_sensitive: If True, perform case-sensitive matching
        file_pattern: Optional file pattern to filter results
        file_types: Optional set of file type abbreviations to search
        logger: Optional logging function

    Returns:
    -------
        List of ReferenceSearchResult objects
    """
    return find_field_value_references(
        installation=installation,
        search_value=tag,
        field_names={"Tag"},
        field_types={GFFFieldType.String},
        partial_match=partial_match,
        case_sensitive=case_sensitive,
        file_pattern=file_pattern,
        file_types=file_types,
        logger=logger,
    )


def find_template_resref_references(
    installation: Installation,
    template_resref: str,
    *,
    partial_match: bool = False,
    case_sensitive: bool = False,
    file_pattern: str | None = None,
    file_types: set[str] | None = None,
    logger: Callable[[str], None] | None = None,
) -> list[ReferenceSearchResult]:
    """Find all references to a TemplateResRef in GFF files.

    Searches for TemplateResRef fields and InventoryRes fields within ItemList structures
    (for UTC, UTP, UTM files).

    Args:
    ----
        installation: The installation to search
        template_resref: The template resref to search for
        partial_match: If True, allow partial matches
        case_sensitive: If True, perform case-sensitive matching
        file_pattern: Optional file pattern to filter results
        file_types: Optional set of file type abbreviations to search
        logger: Optional logging function

    Returns:
    -------
        List of ReferenceSearchResult objects
    """
    # Include InventoryRes to search ItemList structures in UTC/UTP/UTM
    return find_resref_references(
        installation=installation,
        resref=template_resref,
        field_names={"TemplateResRef", "InventoryRes"},
        field_types={GFFFieldType.ResRef},
        partial_match=partial_match,
        case_sensitive=case_sensitive,
        file_pattern=file_pattern,
        file_types=file_types,
        logger=logger,
    )


def find_quest_journal_references(
    installation: Installation,
    quest_tag: str,
    *,
    partial_match: bool = False,
    case_sensitive: bool = False,
    file_pattern: str | None = None,
    file_types: set[str] | None = None,
    logger: Callable[[str], None] | None = None,
) -> list[ReferenceSearchResult]:
    """Find all DLG nodes and scripts that reference a quest tag.

    Searches for:
    - DLG GFF files where a node's ``Quest`` string field equals ``quest_tag``
      (dialogue nodes use AddJournalQuestEntry via the Quest/QuestEntry fields)
    - NCS/NSS script bytecode where the tag string appears as a constant

    Args:
    ----
        installation: The installation to search
        quest_tag: The quest tag to search for (e.g. "tar_mq01")
        partial_match: If True, allow partial matches
        case_sensitive: If True, perform case-sensitive matching
        file_pattern: Optional file pattern to filter results
        file_types: Optional set of file type abbreviations to search
        logger: Optional logging function

    Returns:
    -------
        List of ReferenceSearchResult objects
    """
    dlg_results = find_field_value_references(
        installation=installation,
        search_value=quest_tag,
        field_names={"Quest"},
        field_types={GFFFieldType.String},
        partial_match=partial_match,
        case_sensitive=case_sensitive,
        file_pattern=file_pattern,
        file_types=file_types if file_types is not None else {"DLG"},
        logger=logger,
    )
    script_results = find_resref_references(
        installation=installation,
        resref=quest_tag,
        field_types={GFFFieldType.String},
        search_ncs=True,
        partial_match=partial_match,
        case_sensitive=case_sensitive,
        file_pattern=file_pattern,
        file_types=file_types if file_types is not None else {"NCS", "NSS"},
        logger=logger,
    )
    seen: set[tuple[str, str, str]] = set()
    combined: list[ReferenceSearchResult] = []
    for r in dlg_results + script_results:
        key = (str(r.file_resource.filepath()), r.field_path, r.matched_value)
        if key not in seen:
            seen.add(key)
            combined.append(r)
    return combined


def find_conversation_references(
    installation: Installation,
    conversation_resref: str,
    *,
    partial_match: bool = False,
    case_sensitive: bool = False,
    file_pattern: str | None = None,
    file_types: set[str] | None = None,
    logger: Callable[[str], None] | None = None,
) -> list[ReferenceSearchResult]:
    """Find all references to a conversation (DLG) resref in GFF files.

    Args:
    ----
        installation: The installation to search
        conversation_resref: The conversation resref to search for
        partial_match: If True, allow partial matches
        case_sensitive: If True, perform case-sensitive matching
        file_pattern: Optional file pattern to filter results
        file_types: Optional set of file type abbreviations to search
        logger: Optional logging function

    Returns:
    -------
        List of ReferenceSearchResult objects
    """
    return find_resref_references(
        installation=installation,
        resref=conversation_resref,
        field_names={"Conversation"},
        field_types={GFFFieldType.ResRef},
        partial_match=partial_match,
        case_sensitive=case_sensitive,
        file_pattern=file_pattern,
        file_types=file_types,
        logger=logger,
    )


def find_resref_references(
    installation: Installation,
    resref: str,
    *,
    field_names: set[str] | None = None,
    field_types: set[GFFFieldType] | None = None,
    search_ncs: bool = False,
    partial_match: bool = False,
    case_sensitive: bool = False,
    file_pattern: str | None = None,
    file_types: set[str] | None = None,
    logger: Callable[[str], None] | None = None,
) -> list[ReferenceSearchResult]:
    """Find all references to a ResRef in GFF files and optionally NCS bytecode.

    Args:
    ----
        installation: The installation to search
        resref: The resref to search for
        field_names: Optional set of specific field names to search (e.g., {"ScriptHeartbeat", "Conversation"})
        field_types: Set of GFF field types to search (default: {GFFFieldType.ResRef})
        search_ncs: If True, also search NCS bytecode for string constants
        partial_match: If True, allow partial matches
        case_sensitive: If True, perform case-sensitive matching
        file_pattern: Optional file pattern to filter results
        file_types: Optional set of file type abbreviations to search
        logger: Optional logging function

    Returns:
    -------
        List of ReferenceSearchResult objects
    """
    if field_types is None:
        field_types = {GFFFieldType.ResRef}

    search_pattern = _build_search_pattern(resref, partial_match, case_sensitive)

    if search_ncs:
        gff_resources, ncs_resources = _partition_resources_by_gff_and_ncs(
            installation,
            file_pattern=file_pattern,
            file_types=file_types,
        )
        results = _search_gff_resources_with_cache(
            installation,
            file_pattern=file_pattern,
            file_types=file_types,
            exclude_types=None,
            search_with_gff=lambda resource, gff, file_type: _search_gff_for_resref_with_gff(
                resource,
                gff,
                resref,
                search_pattern,
                field_names,
                field_types,
                file_type,
                case_sensitive,
                logger,
            ),
            resources=gff_resources,
        )
        for resource in ncs_resources:
            results.extend(_search_ncs_for_string(resource, resref, search_pattern, case_sensitive, logger))
    else:
        results = _search_gff_resources_with_cache(
            installation,
            file_pattern=file_pattern,
            file_types=file_types,
            exclude_types={ResourceType.NCS},
            search_with_gff=lambda resource, gff, file_type: _search_gff_for_resref_with_gff(
                resource,
                gff,
                resref,
                search_pattern,
                field_names,
                field_types,
                file_type,
                case_sensitive,
                logger,
            ),
        )

    return results


def find_field_value_references(
    installation: Installation,
    search_value: str,
    *,
    field_names: set[str] | None = None,
    field_types: set[GFFFieldType] | None = None,
    partial_match: bool = False,
    case_sensitive: bool = False,
    file_pattern: str | None = None,
    file_types: set[str] | None = None,
    logger: Callable[[str], None] | None = None,
) -> list[ReferenceSearchResult]:
    """Find all references to a field value in GFF files.

    This is a generic function that can search for any string or resref value in GFF fields.

    Args:
    ----
        installation: The installation to search
        search_value: The value to search for
        field_names: Optional set of specific field names to search
        field_types: Set of GFF field types to search (default: {GFFFieldType.String, GFFFieldType.ResRef})
        partial_match: If True, allow partial matches
        case_sensitive: If True, perform case-sensitive matching
        file_pattern: Optional file pattern to filter results
        file_types: Optional set of file type abbreviations to search
        logger: Optional logging function

    Returns:
    -------
        List of ReferenceSearchResult objects
    """
    if field_types is None:
        field_types = {GFFFieldType.String, GFFFieldType.ResRef}

    search_pattern: re.Pattern[str] = _build_search_pattern(search_value, partial_match, case_sensitive)

    return _search_gff_resources_with_cache(
        installation,
        file_pattern=file_pattern,
        file_types=file_types,
        exclude_types=None,
        search_with_gff=lambda resource, gff, file_type: _search_gff_for_value_with_gff(
            resource,
            gff,
            search_value,
            search_pattern,
            field_names,
            field_types,
            file_type,
            case_sensitive,
            logger,
        ),
    )


def _build_search_pattern(value: str, partial_match: bool, case_sensitive: bool) -> re.Pattern[str]:
    """Build a regex pattern for searching."""
    if partial_match:
        pattern = re.escape(value)
    else:
        pattern = rf"\b{re.escape(value)}\b"

    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(pattern, flags)


def _should_search_resource(
    resource: FileResource,
    file_pattern: str | None,
    file_types: set[str] | None,
    exclude_types: set[ResourceType] | None,
) -> bool:
    """Check if a resource should be searched based on filters."""
    if exclude_types and resource.restype() in exclude_types:
        return False

    if file_pattern:
        filename = resource.filename()
        if not fnmatch.fnmatch(filename.lower(), file_pattern.lower()):
            return False

    return True


def _search_gff_resources_with_cache(
    installation: Installation,
    *,
    file_pattern: str | None,
    file_types: set[str] | None,
    exclude_types: set[ResourceType] | None,
    search_with_gff: Callable[[FileResource, GFF, str], list[ReferenceSearchResult]],
    resources: list[FileResource] | None = None,
) -> list[ReferenceSearchResult]:
    """Search GFF resources with a per-call parse cache to avoid repeated read_gff work.

    When resources is provided, installation is not iterated (single-pass use with NCS search).
    """
    results: list[ReferenceSearchResult] = []
    gff_cache: dict[FileResource, GFF | None] = {}
    iterable = resources if resources is not None else installation

    for resource in iterable:
        if resources is None:
            if not _should_search_resource(resource, file_pattern, file_types, exclude_types):
                continue

        restype = resource.restype()
        if not restype.is_gff():
            continue

        file_type = restype.extension.upper()
        if file_types and file_type not in file_types:
            continue

        if resource not in gff_cache:
            gff_cache[resource] = _safe_read_gff(resource)

        cached_gff = gff_cache[resource]
        if cached_gff is None:
            continue

        results.extend(search_with_gff(resource, cached_gff, file_type))

    return results


def _partition_resources_by_gff_and_ncs(
    installation: Installation,
    *,
    file_pattern: str | None,
    file_types: set[str] | None,
) -> tuple[list[FileResource], list[FileResource]]:
    """Single pass over installation: return (gff_resources, ncs_resources) for ref search."""
    gff_list: list[FileResource] = []
    ncs_list: list[FileResource] = []

    for resource in installation:
        if file_pattern and not fnmatch.fnmatch(resource.filename().lower(), file_pattern.lower()):
            continue
        restype = resource.restype()
        if file_types and restype.extension.upper() not in file_types:
            continue
        if restype == ResourceType.NCS:
            ncs_list.append(resource)
        elif restype.is_gff():
            gff_list.append(resource)

    return gff_list, ncs_list


def _is_value_match(
    candidate: str,
    target: str,
    search_pattern: re.Pattern[str],
    *,
    case_sensitive: bool,
    is_partial: bool,
) -> bool:
    """Return whether candidate matches target using fast direct checks then regex fallback."""
    if not case_sensitive:
        candidate_cmp = candidate.lower()
        target_cmp = target.lower()
        direct_match = target_cmp in candidate_cmp if is_partial else candidate_cmp == target_cmp
    else:
        direct_match = target in candidate if is_partial else candidate == target

    return direct_match or bool(search_pattern.search(candidate))


def _append_gff_match_result(
    results: list[ReferenceSearchResult],
    *,
    resource: FileResource,
    path_prefix: str,
    label: str,
    matched_value: str,
    file_type: str,
    logger: Callable[[str], None] | None,
    search_term: str,
) -> None:
    """Append a GFF match result and emit optional log entry."""
    field_path = _build_field_path(path_prefix, label)
    results.append(
        ReferenceSearchResult(
            file_resource=resource,
            field_path=field_path,
            matched_value=matched_value,
            file_type=file_type,
        ),
    )
    if logger is not None:
        logger(f"Found '{search_term}' in {resource.filename()} at {field_path}")


def _search_gff_for_resref(
    resource: FileResource,
    resref: str,
    search_pattern: re.Pattern[str],
    field_names: set[str] | None,
    field_types: set[GFFFieldType],
    file_type: str,
    case_sensitive: bool,
    logger: Callable[[str], None] | None,
) -> list[ReferenceSearchResult]:
    """Search a GFF file for ResRef references."""
    gff = _safe_read_gff(resource)
    if gff is None:
        return []
    return _search_gff_for_resref_with_gff(resource, gff, resref, search_pattern, field_names, field_types, file_type, case_sensitive, logger)


def _search_gff_for_resref_with_gff(
    resource: FileResource,
    gff: GFF,
    resref: str,
    search_pattern: re.Pattern[str],
    field_names: set[str] | None,
    field_types: set[GFFFieldType],
    file_type: str,
    case_sensitive: bool,
    logger: Callable[[str], None] | None,
) -> list[ReferenceSearchResult]:
    """Search a parsed GFF file for ResRef references."""
    results: list[ReferenceSearchResult] = []

    # Detect if this is a partial match pattern (no word boundaries)
    pattern_str = search_pattern.pattern
    is_partial = "\\b" not in pattern_str
    # Pre-compute ResRef and String type checks (most common case)
    check_resref = GFFFieldType.ResRef in field_types
    check_string = GFFFieldType.String in field_types
    # Use integer comparisons for field types (optimization: avoid enum lookups)
    STRUCT_TYPE = 14  # GFFFieldType.Struct
    LIST_TYPE = 15  # GFFFieldType.List
    RESREF_TYPE = 11  # GFFFieldType.ResRef
    STRING_TYPE = 10  # GFFFieldType.String
    field_type_ints = {_field_type_int(ft) for ft in field_types}

    def recurse_struct(gff_struct: GFFStruct, path_prefix: str = "") -> None:
        """Recursively search GFF struct for ResRef matches."""
        # Use direct field access instead of iteration when possible for better performance
        for label, field_type, value in gff_struct:
            # Use integer comparison for field type (optimization)
            field_type_int = _field_type_int(field_type)

            # Check field name filter
            name_matches = field_names is None or label in field_names
            # Check field type filter using integer comparison (faster than enum)
            type_matches = field_type_int in field_type_ints

            # If name doesn't match, only recurse into nested structures
            if not name_matches:
                _recurse_nested_gff_field(
                    field_type_int,
                    value,
                    label,
                    path_prefix,
                    recurse_struct,
                    struct_type=STRUCT_TYPE,
                    list_type=LIST_TYPE,
                )
                continue

            # If type doesn't match, only recurse into nested structures
            if not type_matches:
                _recurse_nested_gff_field(
                    field_type_int,
                    value,
                    label,
                    path_prefix,
                    recurse_struct,
                    struct_type=STRUCT_TYPE,
                    list_type=LIST_TYPE,
                )
                continue

            # At this point, we know the field name and type match - check the value
            # Optimize string conversion based on field type using integer comparison
            resref_str: str | None = None
            if field_type_int == RESREF_TYPE and check_resref:
                # ResRef is already a string subclass, direct access is fastest
                resref_str = value  # type: ignore[assignment]
            elif field_type_int == STRING_TYPE and check_string:
                resref_str = str(value)

            # If we couldn't extract a string value, recurse and continue
            if resref_str is None:
                _recurse_nested_gff_field(
                    field_type_int,
                    value,
                    label,
                    path_prefix,
                    recurse_struct,
                    struct_type=STRUCT_TYPE,
                    list_type=LIST_TYPE,
                )
                continue

            match_found = _is_value_match(
                resref_str,
                resref,
                search_pattern,
                case_sensitive=case_sensitive,
                is_partial=is_partial,
            )

            if match_found:
                _append_gff_match_result(
                    results,
                    resource=resource,
                    path_prefix=path_prefix,
                    label=label,
                    matched_value=resref_str,
                    file_type=file_type,
                    logger=logger,
                    search_term=resref,
                )

            # Recurse into nested structures (only once, not multiple times)
            _recurse_nested_gff_field(
                field_type_int,
                value,
                label,
                path_prefix,
                recurse_struct,
                struct_type=STRUCT_TYPE,
                list_type=LIST_TYPE,
            )

    recurse_struct(gff.root)
    return results


def _search_gff_for_value(
    resource: FileResource,
    search_value: str,
    search_pattern: re.Pattern[str],
    field_names: set[str] | None,
    field_types: set[GFFFieldType],
    file_type: str,
    case_sensitive: bool,
    logger: Callable[[str], None] | None,
) -> list[ReferenceSearchResult]:
    """Search a GFF file for string/value references."""
    gff = _safe_read_gff(resource)
    if gff is None:
        return []
    return _search_gff_for_value_with_gff(
        resource=resource,
        gff=gff,
        search_value=search_value,
        search_pattern=search_pattern,
        field_names=field_names,
        field_types=field_types,
        file_type=file_type,
        case_sensitive=case_sensitive,
        logger=logger,
    )


def _search_gff_for_value_with_gff(
    resource: FileResource,
    gff: GFF,
    search_value: str,
    search_pattern: re.Pattern[str],
    field_names: set[str] | None,
    field_types: set[GFFFieldType],
    file_type: str,
    case_sensitive: bool,
    logger: Callable[[str], None] | None,
) -> list[ReferenceSearchResult]:
    """Search a parsed GFF file for string/value references."""
    results: list[ReferenceSearchResult] = []

    # Detect if this is a partial match pattern (no word boundaries)
    pattern_str = search_pattern.pattern
    is_partial = "\\b" not in pattern_str
    # Pre-compute ResRef and String type checks (most common case)
    check_resref = GFFFieldType.ResRef in field_types
    check_string = GFFFieldType.String in field_types
    # Use integer comparisons for field types (optimization: avoid enum lookups)
    STRUCT_TYPE = 14  # GFFFieldType.Struct
    LIST_TYPE = 15  # GFFFieldType.List
    RESREF_TYPE = 11  # GFFFieldType.ResRef
    STRING_TYPE = 10  # GFFFieldType.String
    # Convert field_types set to integers for faster comparison
    field_type_ints = {_field_type_int(ft) for ft in field_types}

    def recurse_struct(gff_struct: GFFStruct, path_prefix: str = "") -> None:
        """Recursively search GFF struct for value matches."""
        # Use direct field access instead of iteration when possible for better performance
        for label, field_type, value in gff_struct:
            # Use integer comparison for field type (optimization)
            field_type_int = _field_type_int(field_type)

            # Check field name filter
            name_matches = field_names is None or label in field_names
            # Check field type filter using integer comparison (faster than enum)
            type_matches = field_type_int in field_type_ints

            # If name doesn't match, only recurse into nested structures
            if not name_matches:
                _recurse_nested_gff_field(
                    field_type_int,
                    value,
                    label,
                    path_prefix,
                    recurse_struct,
                    struct_type=STRUCT_TYPE,
                    list_type=LIST_TYPE,
                )
                continue

            # If type doesn't match, only recurse into nested structures
            if not type_matches:
                _recurse_nested_gff_field(
                    field_type_int,
                    value,
                    label,
                    path_prefix,
                    recurse_struct,
                    struct_type=STRUCT_TYPE,
                    list_type=LIST_TYPE,
                )
                continue

            # At this point, we know the field name and type match - check the value
            # Optimize string conversion based on field type using integer comparison
            value_str: str | None = None
            if field_type_int == RESREF_TYPE and check_resref:
                # ResRef is already a string subclass, direct access is fastest
                value_str = value  # type: ignore[assignment]
            elif field_type_int == STRING_TYPE and check_string:
                value_str = str(value)

            # If we couldn't extract a string value, recurse and continue
            if value_str is None:
                _recurse_nested_gff_field(
                    field_type_int,
                    value,
                    label,
                    path_prefix,
                    recurse_struct,
                    struct_type=STRUCT_TYPE,
                    list_type=LIST_TYPE,
                )
                continue

            match_found = _is_value_match(
                value_str,
                search_value,
                search_pattern,
                case_sensitive=case_sensitive,
                is_partial=is_partial,
            )

            if match_found:
                _append_gff_match_result(
                    results,
                    resource=resource,
                    path_prefix=path_prefix,
                    label=label,
                    matched_value=value_str,
                    file_type=file_type,
                    logger=logger,
                    search_term=search_value,
                )

            # Recurse into nested structures (only once, not multiple times)
            _recurse_nested_gff_field(
                field_type_int,
                value,
                label,
                path_prefix,
                recurse_struct,
                struct_type=STRUCT_TYPE,
                list_type=LIST_TYPE,
            )

    recurse_struct(gff.root)
    return results


def _search_ncs_for_string(
    resource: FileResource,
    search_string: str,
    search_pattern: re.Pattern[str],
    case_sensitive: bool,
    logger: Callable[[str], None] | None,
) -> list[ReferenceSearchResult]:
    """Search an NCS file for string constant references."""
    results: list[ReferenceSearchResult] = []

    try:
        ncs_data = resource.data()
        with BinaryReader.from_auto(ncs_data) as reader:
            # Skip NCS header
            if reader.read_string(4) != "NCS ":
                return results
            if reader.read_string(4) != "V1.0":
                return results
            magic_byte = reader.read_uint8()
            if magic_byte != 0x42:  # noqa: PLR2004
                return results
            total_size = reader.read_uint32(big=True)

            # Search for CONSTS (string constant) instructions
            while reader.position() < total_size and reader.remaining() > 0:
                opcode = reader.read_uint8()
                qualifier = reader.read_uint8()

                # Check if this is CONSTS (opcode=0x04, qualifier=0x05)
                if opcode == NCSByteCode.CONSTx and qualifier == NCSInstructionQualifier.String:
                    string_offset = reader.position()
                    str_len = reader.read_uint16(big=True)
                    if str_len > 0 and reader.remaining() >= str_len:
                        string_value = reader.read_string(str_len, encoding="ascii", errors="ignore")
                        if search_pattern.search(string_value):
                            results.append(
                                ReferenceSearchResult(
                                    file_resource=resource,
                                    field_path="(NCS bytecode)",
                                    matched_value=string_value,
                                    file_type="NCS",
                                    byte_offset=string_offset,
                                ),
                            )
                            if logger is not None:
                                logger(f"Found '{search_string}' in {resource.filename()} at byte offset {string_offset:#X}")

                # Skip to next instruction based on opcode/qualifier
                elif opcode == NCSByteCode.CONSTx:
                    if qualifier == NCSInstructionQualifier.Int:
                        reader.skip(4)
                    elif qualifier == NCSInstructionQualifier.Float:
                        reader.skip(4)
                    elif qualifier == NCSInstructionQualifier.String:
                        str_len = reader.read_uint16(big=True)
                        reader.skip(str_len)
                    elif qualifier == NCSInstructionQualifier.Object:
                        reader.skip(4)
                elif opcode in (NCSByteCode.CPDOWNSP, NCSByteCode.CPTOPSP, NCSByteCode.CPDOWNBP, NCSByteCode.CPTOPBP):
                    reader.skip(6)
                elif opcode == NCSByteCode.STORE_STATE:
                    reader.skip(8)
                elif opcode in (
                    NCSByteCode.CPDOWNBP,
                    NCSByteCode.CPTOPBP,
                    NCSByteCode.DECxBP,
                    NCSByteCode.DECxSP,
                    NCSByteCode.INCxBP,
                    NCSByteCode.INCxSP,
                    NCSByteCode.JMP,
                    NCSByteCode.JNZ,
                    NCSByteCode.JSR,
                    NCSByteCode.JZ,
                    NCSByteCode.MOVSP,
                ):
                    reader.skip(4)
                elif opcode == NCSByteCode.ACTION:
                    reader.skip(3)
                elif opcode == NCSByteCode.DESTRUCT:
                    reader.skip(6)
                elif opcode == NCSByteCode.EQUALxx and qualifier == NCSInstructionQualifier.StructStruct:
                    reader.skip(2)
                elif opcode == NCSByteCode.NEQUALxx and qualifier == NCSInstructionQualifier.StructStruct:
                    reader.skip(2)
                # Other instructions have no additional data

    except Exception:  # noqa: BLE001
        # If anything fails, return what we found so far
        pass

    return results
