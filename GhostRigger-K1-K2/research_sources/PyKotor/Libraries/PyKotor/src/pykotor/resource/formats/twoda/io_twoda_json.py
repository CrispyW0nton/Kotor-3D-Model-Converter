"""JSON read/write for 2DA; used for tooling and round-trip."""

from __future__ import annotations

import json

from typing import TYPE_CHECKING

from pykotor.resource.formats.twoda.twoda_data import TwoDA
from pykotor.resource.type import ResourceReader, ResourceWriter, autoclose
from pykotor.tools.encoding import decode_bytes_with_fallbacks

if TYPE_CHECKING:
    from pykotor.resource.type import SOURCE_TYPES, TARGET_TYPES


class TwoDAJSONReader(ResourceReader):
    def __init__(
        self,
        source: SOURCE_TYPES,
        offset: int = 0,
        size: int = 0,
    ):
        super().__init__(source, offset, size)
        self._json = {}
        self._twoda: TwoDA | None = None

    @autoclose
    def load(self, *, auto_close: bool = True) -> TwoDA:  # noqa: FBT001, FBT002, ARG002
        self._twoda = TwoDA()
        self._json = json.loads(decode_bytes_with_fallbacks(self._reader.read_bytes(self._reader.size())))

        # Support both legacy format (rows with "_id" and header keys) and the
        # newer format (top-level "headers" list and rows containing "label" and "cells").
        if isinstance(self._json, dict) and "headers" in self._json and "rows" in self._json:
            headers = self._json.get("headers", [])
            for header in headers:
                self._twoda.add_column(header)

            for row in self._json.get("rows", []):
                label = row.get("label")
                cells = row.get("cells", [])
                cell_map = {h: (cells[i] if i < len(cells) else "") for i, h in enumerate(self._twoda.get_headers())}
                self._twoda.add_row(str(label), cell_map)
            return self._twoda

        # Fallback to legacy behavior
        for row in self._json.get("rows", []):
            row_label = row["_id"]
            del row["_id"]

            for header in row:
                if header not in self._twoda.get_headers():
                    self._twoda.add_column(header)

            self._twoda.add_row(row_label, row)

        return self._twoda


class TwoDAJSONWriter(ResourceWriter):
    def __init__(
        self,
        twoda: TwoDA,
        target: TARGET_TYPES,
    ):
        super().__init__(target)
        self._twoda: TwoDA = twoda
        self._json: dict[str, list] = {"rows": []}

    @autoclose
    def write(self, *, auto_close: bool = True) -> None:  # noqa: FBT001, FBT002, ARG002  # pyright: ignore[reportUnusedParameters]
        # Write using the newer schema expected by the Toolset tests:
        # {
        #   "headers": [ ... ],
        #   "rows": [ {"label": "0", "cells": [ ... ] }, ... ]
        # }
        headers = self._twoda.get_headers()
        self._json["headers"] = headers

        for row in self._twoda:
            json_row: dict[str, list | str] = {"label": row.label(), "cells": []}
            for header in headers:
                json_row["cells"].append(row.get_string(header))
            self._json["rows"].append(json_row)

        json_dump: str = json.dumps(self._json, indent=4)
        self._writer.write_bytes(json_dump.encode())
