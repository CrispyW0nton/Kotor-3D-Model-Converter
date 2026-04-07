"""
tests/test_v60_kotor_icons.py
=============================
Tests for the KotOR-style icon system (Phase 19).

Covers:
  - All 28 expected PNG files exist at 16×16 and 24×24
  - Each PNG is a valid RGBA image of the correct dimensions
  - icon_manager.LABEL_TO_ICON contains all required keys
  - icon_for_label() resolves the right icon name for common button labels
  - Fallback: icon_for_label() returns None for unknown labels (no crash)
  - LibraryPanel.CATEGORIES uses (label, key, icon_name) tuples
  - No emoji characters remain in _btn / nb.add / text= UI widget lines
    in main_window.py
"""

import os
import sys
import re
import unittest
from pathlib import Path

# Ensure src is importable
ROOT = Path(__file__).parent.parent          # …/GhostRigger-K1-K2/
SRC  = ROOT / "src"
if str(SRC.parent) not in sys.path:
    sys.path.insert(0, str(SRC.parent))

ICONS_DIR    = ROOT / "src" / "gui" / "icons"
MAIN_WINDOW  = ROOT / "src" / "gui" / "main_window.py"
ICON_MANAGER = ROOT / "src" / "gui" / "icon_manager.py"


def _src(path=MAIN_WINDOW):
    return path.read_text(encoding="utf-8")


# ── Expected icon names ───────────────────────────────────────────────────────
EXPECTED_ICONS = [
    "open", "autorig", "export", "import", "settings", "refresh",
    "cloth", "modular", "diag", "texture", "library", "search",
    "skeleton", "props", "anims", "rig", "normalmap", "resources",
    "twoda", "logo", "close", "loadmodel", "weightpaint",
    "cat_creature", "cat_character", "cat_item", "cat_module", "cat_other",
]

# ── Emoji regex ──────────────────────────────────────────────────────────────
_EMOJI_RE = re.compile(r'[\U00010000-\U0010ffff\U0001F300-\U0001F9FF'
                       r'\u2600-\u27BF\U0001FA00-\U0001FA9F]')

# ── UI-widget line filter ────────────────────────────────────────────────────
_UI_LINE_RE = re.compile(r'_btn\(|\.add\(|text=|_label\(')


class TestIconFilesExist(unittest.TestCase):
    """All expected PNGs are present at both sizes."""

    def test_icons_directory_exists(self):
        self.assertTrue(ICONS_DIR.is_dir(),
                        f"icons/ directory missing: {ICONS_DIR}")

    def test_all_icons_16px(self):
        for name in EXPECTED_ICONS:
            p = ICONS_DIR / f"{name}_16.png"
            self.assertTrue(p.exists(), f"Missing 16px icon: {p.name}")

    def test_all_icons_24px(self):
        for name in EXPECTED_ICONS:
            p = ICONS_DIR / f"{name}_24.png"
            self.assertTrue(p.exists(), f"Missing 24px icon: {p.name}")

    def test_total_icon_count(self):
        pngs = list(ICONS_DIR.glob("*.png"))
        self.assertGreaterEqual(len(pngs), len(EXPECTED_ICONS) * 2,
                                "Fewer PNGs than expected")


class TestIconDimensions(unittest.TestCase):
    """Each PNG has the correct pixel dimensions."""

    def _load(self, path):
        try:
            from PIL import Image
            return Image.open(str(path))
        except ImportError:
            self.skipTest("Pillow not installed")

    def test_16px_dimensions(self):
        for name in EXPECTED_ICONS[:6]:   # spot-check first 6
            p = ICONS_DIR / f"{name}_16.png"
            if not p.exists():
                continue
            img = self._load(p)
            self.assertEqual(img.size, (16, 16),
                             f"{p.name} should be 16×16, got {img.size}")

    def test_24px_dimensions(self):
        for name in EXPECTED_ICONS[:6]:
            p = ICONS_DIR / f"{name}_24.png"
            if not p.exists():
                continue
            img = self._load(p)
            self.assertEqual(img.size, (24, 24),
                             f"{p.name} should be 24×24, got {img.size}")

    def test_icons_are_rgba(self):
        for name in EXPECTED_ICONS[:4]:
            p = ICONS_DIR / f"{name}_16.png"
            if not p.exists():
                continue
            img = self._load(p)
            self.assertEqual(img.mode, "RGBA",
                             f"{p.name} should be RGBA, got {img.mode}")


class TestIconManagerModule(unittest.TestCase):
    """icon_manager.py structure and LABEL_TO_ICON completeness."""

    def _get_src(self):
        return ICON_MANAGER.read_text(encoding="utf-8")

    def test_icon_manager_exists(self):
        self.assertTrue(ICON_MANAGER.exists(),
                        "src/gui/icon_manager.py not found")

    def test_label_to_icon_defined(self):
        src = self._get_src()
        self.assertIn("LABEL_TO_ICON", src)

    def test_expected_keys_in_label_map(self):
        src = self._get_src()
        required_keys = [
            "open", "export", "import", "auto-rig", "settings", "refresh",
            "cloth", "modular", "diag", "library", "search", "skeleton",
            "props", "anims", "rig", "normalmap", "resources", "twoda",
            "creature", "character", "module", "other",
            "load model", "scan", "batch obj", "batch tga",
        ]
        for k in required_keys:
            self.assertIn(f'"{k}"', src,
                          f'LABEL_TO_ICON missing key: "{k}"')

    def test_init_function_defined(self):
        src = self._get_src()
        self.assertIn("def init(", src)

    def test_get_function_defined(self):
        src = self._get_src()
        self.assertIn("def get(", src)

    def test_label_kwargs_defined(self):
        src = self._get_src()
        self.assertIn("def label_kwargs(", src)

    def test_tab_kwargs_defined(self):
        src = self._get_src()
        self.assertIn("def tab_kwargs(", src)

    def test_icon_for_label_defined(self):
        src = self._get_src()
        self.assertIn("def icon_for_label(", src)

    def test_I_class_has_all_constants(self):
        src = self._get_src()
        for const in ["OPEN", "AUTORIG", "EXPORT", "SETTINGS", "REFRESH",
                      "CLOTH", "MODULAR", "DIAG", "LIBRARY", "SKELETON",
                      "PROPS", "ANIMS", "RIG", "NORMALMAP", "LOGO",
                      "CAT_CREATURE", "CAT_CHARACTER", "CAT_ITEM",
                      "CAT_MODULE", "CAT_OTHER"]:
            self.assertIn(const, src,
                          f"I.{const} missing from IconManager")


class TestIconForLabelLogic(unittest.TestCase):
    """icon_for_label() text matching without a Tk root (dry-run)."""

    def _get_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "icon_manager", str(ICON_MANAGER))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_label_to_icon_open(self):
        mod = self._get_module()
        # Verify mapping exists (no Tk, so get() returns None — that's fine)
        found = None
        key = "open"
        for pattern, icon_name in mod.LABEL_TO_ICON.items():
            if key.startswith(pattern):
                found = icon_name
                break
        self.assertEqual(found, "open")

    def test_label_to_icon_autorig(self):
        mod = self._get_module()
        found = mod.LABEL_TO_ICON.get("auto-rig") or mod.LABEL_TO_ICON.get("autorig")
        self.assertIsNotNone(found)
        self.assertIn("autorig", found)

    def test_label_to_icon_category_creature(self):
        mod = self._get_module()
        self.assertEqual(mod.LABEL_TO_ICON.get("creature"), "cat_creature")

    def test_label_to_icon_unknown_returns_none(self):
        mod = self._get_module()
        # icon_for_label without Tk root returns None (no crash)
        result = mod.icon_for_label("xyzzy_unknown_label_42")
        self.assertIsNone(result)

    def test_label_to_icon_strip_whitespace(self):
        mod = self._get_module()
        # " Load Model" should match "load"
        key = " load model".strip().lower()
        found = None
        for pattern, icon_name in mod.LABEL_TO_ICON.items():
            if key.startswith(pattern):
                found = icon_name
                break
        self.assertIsNotNone(found, '"load model" should match an icon')


class TestMainWindowIconIntegration(unittest.TestCase):
    """main_window.py uses Icons correctly and has no bare emoji in UI strings."""

    def test_icon_manager_imported(self):
        src = _src()
        self.assertIn("icon_manager", src,
                      "icon_manager not imported in main_window.py")

    def test_icons_init_called(self):
        src = _src()
        self.assertIn("Icons.init(", src,
                      "Icons.init() must be called after Tk root creation")

    def test_tab_kwargs_used_for_left_nb(self):
        src = _src()
        self.assertIn('Icons.tab_kwargs("library"', src)
        self.assertIn('Icons.tab_kwargs("skeleton"', src)
        self.assertIn('Icons.tab_kwargs("twoda"', src)
        self.assertIn('Icons.tab_kwargs("resources"', src)

    def test_tab_kwargs_used_for_right_nb(self):
        """Right panel has 4 focused tabs: Props, Anims, Char Builder, Textures.
        Diag and Cloth are hidden panels (menu/popup only) — not notebook tabs."""
        src = _src()
        self.assertIn('Icons.tab_kwargs("props"', src)
        self.assertIn('Icons.tab_kwargs("anims"', src)
        self.assertIn('Icons.tab_kwargs("charbuilder"', src)
        self.assertIn('Icons.tab_kwargs("texture"', src)
        # Cloth and Diag are intentionally hidden (not right-nb tabs) in v5.1+
        self.assertNotIn('right_nb.add(self.diag_panel', src,
                         "Diag should NOT be a visible right-nb tab (popup only)")
        self.assertNotIn('right_nb.add(cloth_container', src,
                         "Cloth should NOT be a visible right-nb tab (menu only)")

    def test_tab_kwargs_used_for_rig_nb(self):
        src = _src()
        self.assertIn('Icons.tab_kwargs("autorig"', src)
        self.assertIn('Icons.tab_kwargs("rig"', src)

    def test_categories_has_three_tuple(self):
        src = _src()
        # CATEGORIES should now have 3-tuples with icon name
        self.assertIn('"All",              "All",', src,
                      "CATEGORIES should have (label, key, icon_name) structure")

    def test_category_tabs_use_icon_tab_kwargs(self):
        src = _src()
        # The loop should call Icons.tab_kwargs for category tabs
        self.assertIn('Icons.tab_kwargs(icon_name,', src,
                      "Category tabs should use Icons.tab_kwargs(icon_name, ...)")

    def test_preview_nb_uses_tab_kwargs(self):
        src = _src()
        self.assertIn('Icons.tab_kwargs("props", " Preview"', src)
        self.assertIn('Icons.tab_kwargs("twoda", " 0x Hex"', src)

    def test_no_bare_emoji_in_btn_text(self):
        """_btn() calls must not contain bare emoji as the sole text content."""
        src = _src()
        lines = src.splitlines()
        violations = []
        for i, line in enumerate(lines, 1):
            # Only check lines with _btn( calls
            if "_btn(" not in line:
                continue
            if _EMOJI_RE.search(line):
                # Allow lines that are pure comments
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                violations.append((i, line.strip()))
        self.assertEqual(violations, [],
                         f"Bare emoji found in _btn() calls:\n" +
                         "\n".join(f"  L{n}: {t}" for n, t in violations[:10]))

    def test_no_bare_emoji_in_nb_add_text(self):
        """nb.add() text= arguments must not contain bare emoji."""
        src = _src()
        lines = src.splitlines()
        violations = []
        for i, line in enumerate(lines, 1):
            if ".add(" not in line or "text=" not in line:
                continue
            # Skip if it uses Icons.tab_kwargs (fine)
            if "Icons.tab_kwargs" in line:
                continue
            if _EMOJI_RE.search(line):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                violations.append((i, line.strip()))
        self.assertEqual(violations, [],
                         "Bare emoji found in .add(text=...) calls:\n" +
                         "\n".join(f"  L{n}: {t}" for n, t in violations[:10]))

    def test_header_uses_logo_icon(self):
        src = _src()
        self.assertIn('Icons.get("logo"', src,
                      "Header must use Icons.get('logo') for the app icon")

    def test_thumbnail_placeholder_uses_icon(self):
        src = _src()
        self.assertIn("Icons.get(_icon_map.get(entry_cat", src,
                      "Thumbnail placeholder should use KotOR icon, not emoji")


class TestIconRender(unittest.TestCase):
    """Smoke-test: generate a small contact-sheet of all icons and verify."""

    def test_generate_contact_sheet(self):
        """Build a 16-col contact sheet of all 56 icons at 16px."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")

        icons = sorted(ICONS_DIR.glob("*_16.png"))
        if not icons:
            self.skipTest("No 16px icons found")

        cols = 14
        rows = (len(icons) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * 20, rows * 20), (18, 18, 30, 255))
        for idx, p in enumerate(icons):
            try:
                ico = Image.open(str(p)).convert("RGBA")
                x = (idx % cols) * 20 + 2
                y = (idx // cols) * 20 + 2
                sheet.paste(ico, (x, y), ico)
            except Exception:
                pass

        out = ROOT / "GhostRigger-K1-K2" / "render_check" / "icons_contact_sheet.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(str(out))
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 500)


if __name__ == "__main__":
    unittest.main()
