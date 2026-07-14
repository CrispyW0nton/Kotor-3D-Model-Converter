"""Preservation-safe typed GFF and KOTOR blueprint authoring.

The legacy Ghost Scripter blueprint viewer exposed the whole GFF tree.  This
module provides that capability without converting a blueprint into a partial
schema or a JSON surrogate.  A :class:`BlueprintGFFDocument` keeps PyKotor's
complete parsed graph alive and replaces only a specifically addressed scalar
field.  Unknown fields, nested structs, list order, list struct IDs, and the
GFF content type therefore survive edits.

Stable paths use a small JSON-Pointer-like grammar.  ``$`` is the root struct,
field labels are slash-separated with RFC 6901 escaping, and list elements are
written as ``#<index>``.  For example, ``$/ItemList/#0/InventoryRes`` addresses
the ``InventoryRes`` field of the first list struct.

PyKotor rewrites the binary GFF tables when serializing, so byte offsets and
padding are not promised to remain identical.  GhostStudio verifies semantic
equality after PyKotor readback before committing a file.  Retail KOTOR runtime
acceptance still belongs to the normal package-and-game-test workflow.
"""

from __future__ import annotations

import json
import math
import os
import re
import struct
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4


BLUEPRINT_RESOURCE_TYPES = frozenset(
    {
        "bic",
        "btc",
        "btd",
        "bte",
        "bti",
        "btm",
        "btp",
        "btt",
        "utc",
        "utd",
        "ute",
        "uti",
        "utm",
        "utp",
        "uts",
        "utt",
        "utw",
    }
)

_INTEGER_RANGES: dict[str, tuple[int, int]] = {
    "UInt8": (0, (1 << 8) - 1),
    "Int8": (-(1 << 7), (1 << 7) - 1),
    "UInt16": (0, (1 << 16) - 1),
    "Int16": (-(1 << 15), (1 << 15) - 1),
    "UInt32": (0, (1 << 32) - 1),
    "Int32": (-(1 << 31), (1 << 31) - 1),
    "UInt64": (0, (1 << 64) - 1),
    "Int64": (-(1 << 63), (1 << 63) - 1),
}
_STRUCTURAL_TYPES = frozenset({"Struct", "List"})
_LIST_TOKEN = re.compile(r"#(0|[1-9][0-9]*)\Z")


@dataclass(frozen=True)
class BlueprintGFFDiagnostic:
    severity: str
    code: str
    message: str
    path: str = "$"

    @property
    def blocking(self) -> bool:
        return self.severity.casefold() in {"blocking", "error"}


@dataclass(frozen=True)
class BlueprintGFFField:
    """Immutable presentation snapshot for one field or list element."""

    path: str
    parent_path: str
    label: str
    field_type: str
    kind: str
    display_value: str
    edit_text: str
    editable: bool
    depth: int
    struct_id: int | None = None
    child_count: int = 0

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BlueprintGFFSummary:
    content_type: str
    resource_type: str
    source_path: str
    root_struct_id: int
    field_count: int
    editable_field_count: int
    dirty: bool
    is_blueprint: bool

    def as_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BlueprintGFFCheckpoint:
    """Verified in-memory state used to roll back a rejected edit."""

    data: bytes
    source_path: str
    dirty: bool


@dataclass(frozen=True)
class _ResolvedField:
    parent: Any
    label: str
    field_type: Any
    value: Any


class BlueprintGFFDocument:
    """An editable GFF graph that never flattens or schema-filters fields."""

    def __init__(
        self,
        gff: Any,
        *,
        source_path: str | Path | None = None,
        source_bytes: bytes | None = None,
    ) -> None:
        self._gff = gff
        self.source_path = Path(source_path) if source_path is not None else None
        self._source_bytes = bytes(source_bytes) if source_bytes is not None else None
        self._dirty = False

    @classmethod
    def load(
        cls,
        source: bytes | bytearray | memoryview | str | Path,
    ) -> "BlueprintGFFDocument":
        """Load any binary GFF resource without discarding unknown fields."""

        from pykotor.resource.formats.gff import read_gff

        if isinstance(source, (bytes, bytearray, memoryview)):
            payload = bytes(source)
            source_path = None
        else:
            source_path = Path(source)
            payload = source_path.read_bytes()
        gff = read_gff(payload)
        return cls(gff, source_path=source_path, source_bytes=payload)

    @classmethod
    def from_gff(cls, gff: Any, *, source_path: str | Path | None = None) -> "BlueprintGFFDocument":
        """Create a document from a GFF object after isolating caller state."""

        from pykotor.resource.formats.gff import bytes_gff, read_gff

        payload = bytes_gff(gff)
        return cls(read_gff(payload), source_path=source_path, source_bytes=payload)

    @property
    def content_type(self) -> str:
        return str(getattr(getattr(self._gff, "content", None), "name", "GFF"))

    @property
    def resource_type(self) -> str:
        return self.content_type.casefold()

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def is_blueprint(self) -> bool:
        return self.resource_type in BLUEPRINT_RESOURCE_TYPES

    def summary(self) -> BlueprintGFFSummary:
        fields = self.fields()
        return BlueprintGFFSummary(
            content_type=self.content_type,
            resource_type=self.resource_type,
            source_path=str(self.source_path or ""),
            root_struct_id=int(self._gff.root.struct_id),
            field_count=len(fields),
            editable_field_count=sum(field.editable for field in fields),
            dirty=self.dirty,
            is_blueprint=self.is_blueprint,
        )

    def fields(self) -> tuple[BlueprintGFFField, ...]:
        rows: list[BlueprintGFFField] = []
        self._append_struct_fields(self._gff.root, "$", 0, rows)
        return tuple(rows)

    def field(self, path: str) -> BlueprintGFFField:
        wanted = self._normalise_path(path)
        for row in self.fields():
            if row.path == wanted:
                return row
        raise KeyError(f"Unknown GFF field path: {path}")

    def search(self, query: str) -> tuple[BlueprintGFFField, ...]:
        needle = str(query or "").strip().casefold()
        if not needle:
            return self.fields()
        return tuple(
            row
            for row in self.fields()
            if needle
            in " ".join((row.path, row.label, row.field_type, row.display_value)).casefold()
        )

    def value(self, path: str) -> Any:
        """Return a defensive copy of the addressed field value."""

        resolved = self._resolve_field(path)
        return deepcopy(resolved.value)

    def checkpoint(self) -> BlueprintGFFCheckpoint:
        return BlueprintGFFCheckpoint(
            self.to_bytes(),
            str(self.source_path or ""),
            self.dirty,
        )

    def restore(self, checkpoint: BlueprintGFFCheckpoint) -> None:
        """Restore a previously verified state, including its dirty marker."""

        restored = BlueprintGFFDocument.load(checkpoint.data)
        self._gff = restored._gff
        self._source_bytes = bytes(checkpoint.data)
        self.source_path = Path(checkpoint.source_path) if checkpoint.source_path else None
        self._dirty = bool(checkpoint.dirty)

    def set_text(self, path: str, text: str) -> Any:
        """Parse editor text according to the existing field's exact GFF type."""

        resolved = self._resolve_field(path)
        type_name = resolved.field_type.name
        if type_name in _STRUCTURAL_TYPES:
            raise TypeError(f"{path} is a {type_name} container and cannot be replaced as a scalar.")
        value = self._parse_text(type_name, str(text))
        self._set_resolved(resolved, value)
        self._dirty = True
        return deepcopy(value)

    def set_value(self, path: str, value: Any) -> Any:
        """Set a scalar using native or text input while retaining its GFF type."""

        resolved = self._resolve_field(path)
        type_name = resolved.field_type.name
        if type_name in _STRUCTURAL_TYPES:
            raise TypeError(f"{path} is a {type_name} container and cannot be replaced as a scalar.")
        parsed = self._coerce_value(type_name, value)
        self._set_resolved(resolved, parsed)
        self._dirty = True
        return deepcopy(parsed)

    def to_bytes(self) -> bytes:
        """Serialize and reject any payload that fails semantic readback."""

        from pykotor.resource.formats.gff import bytes_gff, read_gff

        payload = bytes_gff(self._gff)
        written = read_gff(payload)
        differences: list[str] = []
        if not self._gff.compare(written, log_func=lambda *parts, **_kwargs: differences.append(" ".join(map(str, parts)))):
            detail = "; ".join(differences[:5]) or "PyKotor reported a structural mismatch."
            raise ValueError(f"GFF write verification failed: {detail}")
        return payload

    def save(self, path: str | Path | None = None) -> Path:
        """Verify, stage, read back, then atomically promote a GFF file."""

        from pykotor.resource.formats.gff import read_gff

        target = Path(path) if path is not None else self.source_path
        if target is None:
            raise ValueError("Choose a destination before saving this GFF document.")
        payload = self.to_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes(payload)
            staged = read_gff(temporary)
            differences: list[str] = []
            if not self._gff.compare(staged, log_func=lambda *parts, **_kwargs: differences.append(" ".join(map(str, parts)))):
                detail = "; ".join(differences[:5]) or "the staged file changed structure"
                raise ValueError(f"Staged GFF readback failed: {detail}")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        self.source_path = target
        self._source_bytes = payload
        self._dirty = False
        return target

    def validate(self) -> tuple[BlueprintGFFDiagnostic, ...]:
        diagnostics: list[BlueprintGFFDiagnostic] = []
        suffix = self.source_path.suffix.casefold().lstrip(".") if self.source_path is not None else ""
        if not self.is_blueprint:
            diagnostics.append(
                BlueprintGFFDiagnostic(
                    "warning",
                    "gff.not_blueprint_content",
                    f"{self.content_type} is a valid GFF resource but is not a KOTOR blueprint template type.",
                )
            )
        if suffix in BLUEPRINT_RESOURCE_TYPES and suffix != self.resource_type:
            diagnostics.append(
                BlueprintGFFDiagnostic(
                    "warning",
                    "gff.extension_content_mismatch",
                    f"The .{suffix} filename does not match the embedded {self.content_type} content type.",
                )
            )
        try:
            self.to_bytes()
        except Exception as exc:
            diagnostics.append(
                BlueprintGFFDiagnostic(
                    "blocking",
                    "gff.readback_failed",
                    f"PyKotor could not round-trip this GFF graph: {exc}",
                )
            )
        return tuple(diagnostics)

    def _append_struct_fields(
        self,
        current: Any,
        parent_path: str,
        depth: int,
        rows: list[BlueprintGFFField],
    ) -> None:
        for label, field_type, value in current:
            path = self._join_field(parent_path, label)
            type_name = field_type.name
            if type_name == "Struct":
                rows.append(
                    BlueprintGFFField(
                        path,
                        parent_path,
                        str(label),
                        type_name,
                        "field",
                        f"Struct {value.struct_id} ({len(value)} fields)",
                        "",
                        False,
                        depth,
                        int(value.struct_id),
                        len(value),
                    )
                )
                self._append_struct_fields(value, path, depth + 1, rows)
            elif type_name == "List":
                rows.append(
                    BlueprintGFFField(
                        path,
                        parent_path,
                        str(label),
                        type_name,
                        "field",
                        f"{len(value)} struct(s)",
                        "",
                        False,
                        depth,
                        None,
                        len(value),
                    )
                )
                for index, child in enumerate(value):
                    child_path = f"{path}/#{index}"
                    rows.append(
                        BlueprintGFFField(
                            child_path,
                            path,
                            f"[{index}]",
                            "Struct",
                            "list_item",
                            f"Struct {child.struct_id} ({len(child)} fields)",
                            "",
                            False,
                            depth + 1,
                            int(child.struct_id),
                            len(child),
                        )
                    )
                    self._append_struct_fields(child, child_path, depth + 2, rows)
            else:
                edit_text = self._format_value(type_name, value, full=True)
                rows.append(
                    BlueprintGFFField(
                        path,
                        parent_path,
                        str(label),
                        type_name,
                        "field",
                        self._ellipsize(edit_text),
                        edit_text,
                        True,
                        depth,
                    )
                )

    def _resolve_field(self, path: str) -> _ResolvedField:
        from pykotor.resource.formats.gff import GFFList, GFFStruct

        normal = self._normalise_path(path)
        tokens = self._path_tokens(normal)
        if not tokens:
            raise TypeError("The root struct is not an editable scalar field.")
        current: Any = self._gff.root
        for index, token in enumerate(tokens):
            last = index == len(tokens) - 1
            if isinstance(current, GFFStruct):
                label = self._unescape(token)
                if not current.exists(label):
                    raise KeyError(f"Unknown GFF field path: {path}")
                field_type = current.what_type(label)
                value = current.value(label)
                if last:
                    return _ResolvedField(current, label, field_type, value)
                current = value
            elif isinstance(current, GFFList):
                match = _LIST_TOKEN.fullmatch(token)
                if match is None:
                    raise KeyError(f"Expected a list index in GFF field path: {path}")
                list_index = int(match.group(1))
                if list_index >= len(current):
                    raise KeyError(f"GFF list index is out of range in path: {path}")
                current = current.at(list_index)
                if current is None:
                    raise KeyError(f"GFF list index is missing in path: {path}")
                if last:
                    raise TypeError("A list struct is not an editable scalar field.")
            else:
                raise KeyError(f"GFF path traverses through a scalar value: {path}")
        raise KeyError(f"Unknown GFF field path: {path}")

    @staticmethod
    def _set_resolved(resolved: _ResolvedField, value: Any) -> None:
        setter_name = {
            "UInt8": "set_uint8",
            "Int8": "set_int8",
            "UInt16": "set_uint16",
            "Int16": "set_int16",
            "UInt32": "set_uint32",
            "Int32": "set_int32",
            "UInt64": "set_uint64",
            "Int64": "set_int64",
            "Single": "set_single",
            "Double": "set_double",
            "String": "set_string",
            "ResRef": "set_resref",
            "LocalizedString": "set_locstring",
            "Binary": "set_binary",
            "Vector3": "set_vector3",
            "Vector4": "set_vector4",
        }.get(resolved.field_type.name)
        if setter_name is None:
            raise TypeError(f"Unsupported editable GFF type: {resolved.field_type.name}")
        getattr(resolved.parent, setter_name)(resolved.label, value)

    @classmethod
    def _parse_text(cls, type_name: str, text: str) -> Any:
        from pykotor.common.language import LocalizedString
        from pykotor.common.misc import ResRef
        from utility.common.geometry import Vector3, Vector4

        if type_name in _INTEGER_RANGES:
            try:
                value = int(text.strip(), 0)
            except ValueError as exc:
                raise ValueError(f"{type_name} requires a whole decimal or 0x-prefixed number.") from exc
            minimum, maximum = _INTEGER_RANGES[type_name]
            if not minimum <= value <= maximum:
                raise ValueError(f"{type_name} must be between {minimum} and {maximum}.")
            return value
        if type_name in {"Single", "Double"}:
            try:
                value = float(text.strip())
            except ValueError as exc:
                raise ValueError(f"{type_name} requires a number.") from exc
            if not math.isfinite(value):
                raise ValueError(f"{type_name} must be finite.")
            return cls._float32(value) if type_name == "Single" else value
        if type_name == "String":
            return text
        if type_name == "ResRef":
            return ResRef(text.strip()) if text.strip() else ResRef.from_blank()
        if type_name == "LocalizedString":
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("LocalizedString requires JSON with stringref and substrings fields.") from exc
            if not isinstance(value, Mapping):
                raise ValueError("LocalizedString JSON must be an object.")
            return LocalizedString.from_dict(dict(value))
        if type_name == "Binary":
            compact = re.sub(r"(?:0x)|[\s,:;_-]", "", text, flags=re.IGNORECASE)
            try:
                return bytes.fromhex(compact)
            except ValueError as exc:
                raise ValueError("Binary fields require hexadecimal byte pairs.") from exc
        if type_name in {"Vector3", "Vector4"}:
            count = 3 if type_name == "Vector3" else 4
            parts = [part for part in re.split(r"[\s,]+", text.strip()) if part]
            if len(parts) != count:
                raise ValueError(f"{type_name} requires {count} comma- or space-separated numbers.")
            try:
                values = [cls._float32(float(part)) for part in parts]
            except ValueError as exc:
                raise ValueError(f"{type_name} requires numeric coordinates.") from exc
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{type_name} coordinates must be finite.")
            return Vector3(*values) if count == 3 else Vector4(*values)
        raise TypeError(f"Unsupported editable GFF type: {type_name}")

    @classmethod
    def _coerce_value(cls, type_name: str, value: Any) -> Any:
        from pykotor.common.language import LocalizedString
        from pykotor.common.misc import ResRef
        from utility.common.geometry import Vector3, Vector4

        if type_name == "String" and isinstance(value, str):
            return value
        if type_name == "Binary" and isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value)
        if type_name == "LocalizedString" and isinstance(value, LocalizedString):
            return deepcopy(value)
        if type_name == "ResRef" and isinstance(value, ResRef):
            return deepcopy(value)
        vector_class = Vector3 if type_name == "Vector3" else Vector4 if type_name == "Vector4" else None
        if vector_class is not None and isinstance(value, vector_class):
            return cls._parse_text(type_name, cls._format_value(type_name, value, full=True))
        return cls._parse_text(type_name, str(value))

    @staticmethod
    def _format_value(type_name: str, value: Any, *, full: bool) -> str:
        if type_name == "LocalizedString":
            return json.dumps(value.to_dict(), ensure_ascii=False, sort_keys=True, indent=2 if full else None)
        if type_name == "Binary":
            return bytes(value).hex(" ").upper()
        if type_name == "ResRef":
            return value.get()
        if type_name in {"Vector3", "Vector4"}:
            names = ("x", "y", "z") if type_name == "Vector3" else ("x", "y", "z", "w")
            return ", ".join(repr(float(getattr(value, name))) for name in names)
        return str(value)

    @staticmethod
    def _ellipsize(value: str, limit: int = 160) -> str:
        compact = " ".join(str(value).splitlines())
        return compact if len(compact) <= limit else f"{compact[: limit - 1]}…"

    @staticmethod
    def _float32(value: float) -> float:
        return struct.unpack("<f", struct.pack("<f", value))[0]

    @classmethod
    def _normalise_path(cls, path: str) -> str:
        # Field labels may legally contain leading/trailing whitespace; a
        # stable path must preserve those bytes rather than being user-trimmed.
        value = str(path or "")
        if value == "$":
            return value
        if not value.startswith("$/"):
            raise ValueError(f"Invalid GFF field path: {path}")
        # RFC 6901 permits empty reference tokens.  GFF labels can also be an
        # empty string, so ``$/`` and consecutive slashes are meaningful and
        # must not be normalized away.
        return value

    @staticmethod
    def _path_tokens(path: str) -> tuple[str, ...]:
        return () if path == "$" else tuple(path[2:].split("/"))

    @classmethod
    def _join_field(cls, parent: str, label: str) -> str:
        escaped = cls._escape(str(label))
        return f"$/{escaped}" if parent == "$" else f"{parent}/{escaped}"

    @staticmethod
    def _escape(label: str) -> str:
        return label.replace("~", "~0").replace("/", "~1")

    @staticmethod
    def _unescape(token: str) -> str:
        # Reject malformed escape sequences instead of silently addressing a
        # different field than the path shown to the user.
        if re.search(r"~(?![01])", token):
            raise ValueError(f"Invalid escape sequence in GFF field path token: {token}")
        return token.replace("~1", "/").replace("~0", "~")


def blueprint_rows(rows: Iterable[BlueprintGFFField]) -> tuple[dict[str, Any], ...]:
    """Convert immutable core snapshots into presentation dictionaries."""

    return tuple(row.as_row() for row in rows)


__all__ = [
    "BLUEPRINT_RESOURCE_TYPES",
    "BlueprintGFFCheckpoint",
    "BlueprintGFFDiagnostic",
    "BlueprintGFFDocument",
    "BlueprintGFFField",
    "BlueprintGFFSummary",
    "blueprint_rows",
]
