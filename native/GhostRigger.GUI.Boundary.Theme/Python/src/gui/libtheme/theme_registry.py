"""Small ordered registry for themes and layouts."""

from __future__ import annotations


class Registry(dict):
    def names(self) -> list[tuple[str, str]]:
        return [(key, getattr(value, "name", key)) for key, value in sorted(self.items())]
