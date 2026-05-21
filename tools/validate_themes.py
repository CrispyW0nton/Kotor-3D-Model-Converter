"""Validate GhostRigger packaged/user themes and layouts."""

from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gui.libtheme.layout_loader import LayoutLoader
from src.gui.libtheme.layout_validator import LayoutValidator
from src.gui.libtheme.qt_stylesheet_builder import QtStylesheetBuilder
from src.gui.libtheme.style_tokens import FALLBACK_COLORS, FALLBACK_METRICS, VALID_BUTTON_MODES
from src.gui.libtheme.theme_loader import ThemeLoader
from src.gui.libtheme.theme_validator import ThemeValidator


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.strip().lstrip("#")
    return tuple(int(value[index:index + 2], 16) / 255.0 for index in (0, 2, 4))


def _linear(component: float) -> float:
    return component / 12.92 if component <= 0.03928 else ((component + 0.055) / 1.055) ** 2.4


def _contrast(a: str, b: str) -> float:
    ar, ag, ab = (_linear(c) for c in _hex_to_rgb(a))
    br, bg, bb = (_linear(c) for c in _hex_to_rgb(b))
    la = 0.2126 * ar + 0.7152 * ag + 0.0722 * ab
    lb = 0.2126 * br + 0.7152 * bg + 0.0722 * bb
    high, low = max(la, lb), min(la, lb)
    return (high + 0.05) / (low + 0.05)


def main() -> int:
    theme_dir = ROOT / "config" / "themes" / "themes"
    layout_dir = ROOT / "config" / "themes" / "layouts"
    themes = ThemeLoader().load_dir(theme_dir)
    layouts = LayoutLoader().load_dir(layout_dir)
    failures: list[str] = []

    print(f"Themes: {len(themes)}")
    for theme in themes.values():
        warnings = [w for w in ThemeValidator().validate_theme(theme) if "missing recommended" not in w]
        stylesheet = QtStylesheetBuilder().build(theme)
        missing_tokens = [token for token in FALLBACK_COLORS if not theme.color(token)]
        if warnings:
            failures.extend(f"{theme.id}: {warning}" for warning in warnings)
        if missing_tokens:
            failures.append(f"{theme.id}: missing tokens {', '.join(missing_tokens)}")
        if theme.is_native():
            if stylesheet != "":
                failures.append(f"{theme.id}: native theme should not build a stylesheet")
        elif "QMainWindow" not in stylesheet:
            failures.append(f"{theme.id}: stylesheet did not build")
        if theme.id in {"light", "classic"}:
            pairs = [
                ("text.primary", "window.background"),
                ("text.secondary", "panel.background"),
                ("input.text", "input.background"),
                ("button.text", "button.background"),
                ("spinbox.arrow", "spinbox.buttonBackground"),
                ("selection.text", "selection.background"),
                ("table.headerText", "table.headerBackground"),
            ]
            for fg, bg in pairs:
                ratio = _contrast(theme.color(fg), theme.color(bg))
                if ratio < 3.0:
                    failures.append(f"{theme.id}: low contrast {fg} on {bg}: {ratio:.2f}")
        print(f"  OK theme {theme.id}")

    print(f"Layouts: {len(layouts)}")
    for layout in layouts.values():
        warnings = LayoutValidator().validate_xml(ET.parse(layout.source_path).getroot())
        failures.extend(f"{layout.id}: {warning}" for warning in warnings)
        required_metrics = ["margin", "panelSpacing", "toolbarSpacing", "splitterHandleWidth", "inputHeight", "tabHeight", "tableRowHeight", "treeRowHeight"]
        for metric in required_metrics:
            if metric not in layout.spacing:
                failures.append(f"{layout.id}: missing layout metric {metric}")
        for toolbar in layout.toolbars.values():
            if toolbar.button_mode not in VALID_BUTTON_MODES:
                failures.append(f"{layout.id}: invalid button mode {toolbar.button_mode}")
        if layout.toolbar("main").height <= 0 or layout.panel("library").preferred_width <= 0:
            failures.append(f"{layout.id}: impossible size metric")
        print(f"  OK layout {layout.id}")

    if failures:
        print("\nFAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nAll theme/layout validation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
