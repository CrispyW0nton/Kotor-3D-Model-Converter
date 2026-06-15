"""Retargeting test helpers.

The live KOTOR install may contain external animation artifacts from sibling
projects such as the Patch Manager. Retargeter tests that need stock inventory
assertions should either use ``tests/fixtures/kotor_stock`` or filter live
integration probes through ``filter_stock_animations``.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Pattern


EXTERNAL_ANIMATION_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^custom_.*", re.IGNORECASE),
    re.compile(r".*_smoke(_test)?$", re.IGNORECASE),
    re.compile(r".*_patch$", re.IGNORECASE),
    re.compile(r"^mixamo_.*", re.IGNORECASE),
    re.compile(r"^test_.*", re.IGNORECASE),
]


def filter_stock_animations(animation_names: Iterable[str]) -> list[str]:
    """Return names that look like stock KOTOR animation content."""

    stock: list[str] = []
    for raw_name in animation_names:
        name = str(raw_name or "")
        if not name:
            continue
        if any(pattern.match(name) for pattern in EXTERNAL_ANIMATION_PATTERNS):
            continue
        stock.append(name)
    return stock
