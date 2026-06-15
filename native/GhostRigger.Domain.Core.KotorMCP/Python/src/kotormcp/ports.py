"""
KotorMCP Ports — abstract contracts (interfaces) for external dependencies.

Derived from "Balancing Coupling in Software Design" (Khononov, 2025):

  Coupling Taxonomy Applied
  ─────────────────────────
  • Integration Strength goal: Contract Coupling across module boundaries
    (strongest acceptable form between distant modules that change independently)
  • Distance rule: high-volatility impl details (pykotor API, filesystem layout)
    are kept behind ports; only stable abstractions cross the boundary
  • Volatility principle: these port interfaces are LOW volatility — callers depend
    on them, not on the high-volatility adapters

Port contracts defined here:
  - InstallationPort   : read KotOR installation metadata & resources
  - ModelLocatorPort   : find & load raw MDL/MDX bytes by resref / path
  - ModelParserPort    : parse raw bytes into an abstract KotorModel
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple


# ── Value objects (stable data contracts) ─────────────────────────────────────

@dataclass(frozen=True)
class ResourceEntry:
    """Stable representation of a single KotOR resource (Contract Coupling)."""
    resref: str
    restype: str          # e.g. "MDL", "UTC", "2DA"
    extension: str        # e.g. "mdl", "utc", "2da"
    size: int
    source: str           # e.g. "override", "chitin", "module:205tel"
    data: bytes = field(default=b"", repr=False, compare=False)


@dataclass(frozen=True)
class ModelInfo:
    """Stable contract: structured information about a parsed KotOR model."""
    resref: str
    path: str
    node_count: int
    mesh_node_count: int
    total_vertices: int
    total_faces: int
    bone_count: int
    bones: List[str]
    animations: List[str]
    bounding_box_min: Optional[List[float]]
    bounding_box_max: Optional[List[float]]
    classification: str
    supermodel: Optional[str]


@dataclass
class AuditResult:
    """Stable contract: integrity-check result for a parsed KotOR model."""
    resref: str
    status: str                       # "ok" or "issues_found"
    node_count: int
    mesh_node_count: int
    bounding_box_ok: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ── Ports (abstract contracts / interfaces) ───────────────────────────────────

class InstallationPort(ABC):
    """
    Port: read-only access to a KotOR installation.

    Callers depend on this contract, not on pykotor internals.
    This is Contract Coupling — the minimum knowledge boundary
    between the MCP tool layer and the data-access layer.
    """

    @abstractmethod
    def path(self) -> str:
        """Return the root path of the installation as a string."""

    @abstractmethod
    def game_name(self) -> str:
        """Return canonical game name: 'K1' or 'K2'."""

    @abstractmethod
    def module_names(self) -> List[str]:
        """Return list of available module names."""

    @abstractmethod
    def override_count(self) -> int:
        """Return number of resources in the override directory."""

    @abstractmethod
    def iter_resources(
        self,
        location: str = "all",
        module_filter: Optional[str] = None,
    ) -> Iterator[ResourceEntry]:
        """Yield ResourceEntry objects for every accessible resource."""

    @abstractmethod
    def get_resource(
        self,
        resref: str,
        restype: str,
        order: Optional[List[str]] = None,
    ) -> Optional[ResourceEntry]:
        """Return the highest-priority matching resource or None."""

    @abstractmethod
    def talktable_string(self, strref: int) -> str:
        """Return the dialog text for a TLK string-reference."""


class ModelLocatorPort(ABC):
    """
    Port: find and return raw MDL+MDX byte pairs.

    Decouples the 'where to find model bytes' concern from
    'how to parse model bytes' and 'what tools call the model'.
    """

    @abstractmethod
    def locate(
        self,
        resref: str,
        game_alias: Optional[str] = None,
        game_path: Optional[str] = None,
    ) -> Tuple[str, bytes, bytes]:
        """
        Locate an MDL model.

        Returns (path_label, mdl_bytes, mdx_bytes).
        Raises FileNotFoundError when the model cannot be found.
        """


class ModelParserPort(ABC):
    """
    Port: parse raw MDL/MDX bytes into an abstract model object.

    The returned object's API is internal to kotormcp — external
    callers only ever see ModelInfo / AuditResult (data contracts).
    """

    @abstractmethod
    def parse(self, mdl: bytes, mdx: bytes, path_label: str) -> Any:
        """Parse MDL+MDX bytes; return internal model object."""


class InstallationRegistryPort(ABC):
    """
    Port: resolve game aliases and cache installations.

    Replaces the module-level INSTALLATIONS global dict (Common Coupling)
    with a Contract Coupling boundary.  Tool handlers receive this port
    via constructor injection rather than importing the global directly.
    """

    @abstractmethod
    def resolve(self, label: Optional[str]) -> Optional[Any]:
        """Resolve a game alias string to the internal Game enum or None."""

    @abstractmethod
    def load(
        self,
        game: Any,
        explicit_path: Optional[str] = None,
    ) -> InstallationPort:
        """
        Load and return an installation adapter.

        Raises ValueError if the installation cannot be located.
        """

    @abstractmethod
    def clear(self) -> None:
        """Evict all cached installations (test helper)."""
