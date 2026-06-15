"""Pydantic v2 input models for MCP tool arguments.

Falls back gracefully if pydantic is not installed (uses a simple dict-based shim).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
    _PYDANTIC = True
except ImportError:
    _PYDANTIC = False

    class BaseModel:  # type: ignore[no-redef]
        """Minimal shim when pydantic is not installed."""
        def __init__(self, **kwargs: Any):
            for k, v in kwargs.items():
                setattr(self, k, v)

        @classmethod
        def model_validate(cls, data: Dict[str, Any]):
            instance = cls.__new__(cls)
            for k, v in data.items():
                setattr(instance, k, v)
            # Set defaults from annotations
            for attr, annotation in cls.__annotations__.items():
                if not hasattr(instance, attr):
                    setattr(instance, attr, None)
            return instance

    def Field(default=None, **kwargs):  # type: ignore[misc]
        return default


# ── Input models ──────────────────────────────────────────────────────────────

class LoadInstallationInput(BaseModel):
    game: str = Field(..., description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")


class ListResourcesInput(BaseModel):
    game: str = Field(..., description="Game alias: k1 or k2")
    location: str = Field(default="all")
    moduleFilter: Optional[str] = Field(None)  # noqa: N815
    resourceTypes: Optional[List[str]] = Field(None)  # noqa: N815
    resrefQuery: Optional[str] = Field(None)  # noqa: N815
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class DescribeResourceInput(BaseModel):
    game: str = Field(..., description="Game alias: k1 or k2")
    resref: str = Field(...)
    restype: str = Field(...)
    order: Optional[List[str]] = Field(None)


class JournalOverviewInput(BaseModel):
    game: str = Field(...)


class Lookup2daInput(BaseModel):
    game: str = Field(...)
    table_name: str = Field(...)
    row_index: Optional[int] = Field(None)
    column: Optional[str] = Field(None)
    value_search: Optional[str] = Field(None)


class LookupTlkInput(BaseModel):
    game: str = Field(...)
    strref: int = Field(...)


class FindResourceInput(BaseModel):
    game: str = Field(...)
    query: str = Field(...)
    order: Optional[List[str]] = Field(None)
    all_locations: bool = Field(default=True)


class SearchResourcesInput(BaseModel):
    game: str = Field(...)
    pattern: str = Field(...)
    location: str = Field(default="all")
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class ListModulesInput(BaseModel):
    game: str = Field(...)


class DescribeModuleInput(BaseModel):
    game: str = Field(...)
    module_root: str = Field(...)


class ModuleResourcesInput(BaseModel):
    game: str = Field(...)
    module_root: str = Field(...)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class ListArchiveInput(BaseModel):
    file_path: str = Field(...)
    key_file: Optional[str] = Field(None)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class ExtractResourceInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    restype: str = Field(...)
    output_path: str = Field(...)
    source: Optional[str] = Field(None)


class ReadGffInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    restype: str = Field(...)
    field_paths: Optional[List[str]] = Field(None)
    max_depth: Optional[int] = Field(None)
    max_fields: Optional[int] = Field(None)


class Read2daInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    row_start: Optional[int] = Field(None)
    row_end: Optional[int] = Field(None)
    columns: Optional[List[str]] = Field(None)


class ReadTlkInput(BaseModel):
    game: str = Field(...)
    strref_start: Optional[int] = Field(None)
    strref_end: Optional[int] = Field(None)
    text_search: Optional[str] = Field(None)
    limit: int = Field(default=100)


class ListReferencesInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    restype: str = Field(...)
    path: Optional[str] = Field(None)


class FindReferrersInput(BaseModel):
    game: str = Field(...)
    value: str = Field(...)
    reference_kind: str = Field(default="resref")
    path: Optional[str] = Field(None)
    module_root: Optional[str] = Field(None)
    partial_match: bool = Field(default=False)
    case_sensitive: bool = Field(default=False)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class FindStrrefReferrersInput(BaseModel):
    game: str = Field(...)
    strref: int = Field(...)
    path: Optional[str] = Field(None)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class DescribeDlgInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    path: Optional[str] = Field(None)


class DescribeJrlInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    path: Optional[str] = Field(None)


class DescribeResourceRefsInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    restype: str = Field(...)
    path: Optional[str] = Field(None)
