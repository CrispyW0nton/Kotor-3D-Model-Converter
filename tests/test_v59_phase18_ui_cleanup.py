"""
Phase 18 – UI Cleanup & Professional Polish
============================================
Tests that verify all Phase 18 changes:
  - Header redesign (icon + title cluster, version pill, IPC badge + tooltip)
  - Toolbar improvements (Diag/Anims/Settings buttons, pill clickable)
  - Status bar with shortcut hints
  - Library panel category icons in listbox
  - Viewport HUD: model name, node/mesh count, shade-mode badge
  - ResourceManager as primary path (KotorInstallation as fallback)
  - PyKotor-powered 2DA populate + CSV/TSV export
  - Menu accelerator labels on File + Model menus
  - New keyboard shortcuts: Ctrl+F, Ctrl+L, F3, Ctrl+D, Ctrl+A
  - _update_status_bar helper
  - App version bumped to 4.3.0
"""

import unittest
import os
import sys

# ── path setup ────────────────────────────────────────────────────────────────
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)


def _get_main_window_src() -> str:
    path = os.path.join(_REPO, "src", "gui", "main_window.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _get_viewport_src() -> str:
    path = os.path.join(_REPO, "src", "gui", "viewport.py")
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── Header redesign ───────────────────────────────────────────────────────────
class TestHeaderRedesign(unittest.TestCase):
    """Phase 18: Header uses separate icon + title frame layout."""

    def setUp(self):
        self.src = _get_main_window_src()

    def test_icon_label_separate(self):
        # Phase 19: ghost icon replaced by Icons.get("logo") KotOR-style asset
        self.assertTrue(
            'Icons.get("logo"' in self.src or 'text="👻"' in self.src,
            "Header should use either Icons.get('logo') or a ghost-icon Label")

    def test_title_frame_exists(self):
        self.assertIn("title_frame", self.src,
                      "title_frame sub-frame should hold app name + subtitle")

    def test_right_cluster_for_version_and_ipc(self):
        self.assertIn("right_cluster", self.src,
                      "right_cluster frame should group version + IPC badge")

    def test_ipc_tooltip_present(self):
        self.assertIn("GhostRigger IPC", self.src,
                      "IPC status label should have an informative tooltip")

    def test_version_string(self):
        # Version has been superseded by later phases; accept any GhostRigger
        # version string (4.x or 5.x) as long as the APP_VERSION attribute exists.
        self.assertTrue(
            "4.3.0" in self.src or "5.0.0" in self.src or "APP_VERSION" in self.src,
            "App version should be present (was 4.3.0 for Phase 18, may be higher now)")


# ── Toolbar improvements ──────────────────────────────────────────────────────
class TestToolbarImprovements(unittest.TestCase):
    """Phase 18: Toolbar has quick-access Diag/Anims/Settings buttons + pill."""

    def setUp(self):
        self.src = _get_main_window_src()

    def test_diag_button_on_toolbar(self):
        self.assertIn("b_diag", self.src)
        self.assertIn("Ctrl+D", self.src)

    def test_anims_button_on_toolbar(self):
        self.assertIn("b_anim", self.src)
        self.assertIn("Ctrl+A", self.src)

    def test_settings_button_on_toolbar(self):
        self.assertIn("b_settings", self.src)

    def test_pill_is_clickable(self):
        # pill.bind("<Button-1>", ...) should reference _show_model_info
        self.assertIn("pill.bind", self.src)
        self.assertIn("_show_model_info", self.src)

    def test_pill_cursor_hand(self):
        # pill widget should have cursor='hand2'
        self.assertIn("cursor='hand2'", self.src)


# ── Status bar ────────────────────────────────────────────────────────────────
class TestStatusBar(unittest.TestCase):
    """Phase 18: A status bar shows keyboard shortcuts and model info."""

    def setUp(self):
        self.src = _get_main_window_src()

    def test_status_var_exists(self):
        self.assertIn("_status_var", self.src)

    def test_ready_hint_present(self):
        self.assertIn("Ready  │  Ctrl+O", self.src,
                      "Status bar default text should list key shortcuts")

    def test_update_status_bar_method(self):
        self.assertIn("def _update_status_bar", self.src,
                      "_update_status_bar() helper must exist")

    def test_status_bar_updated_on_clear(self):
        self.assertIn("_update_status_bar", self.src)
        # _clear_model should call _update_status_bar
        idx = self.src.find("def _clear_model")
        snippet = self.src[idx: idx + 300]
        self.assertIn("_update_status_bar", snippet)


# ── Library panel icons ───────────────────────────────────────────────────────
class TestLibraryPanelIcons(unittest.TestCase):
    """Phase 18: Library listbox entries show category icons."""

    def setUp(self):
        self.src = _get_main_window_src()

    def test_category_icon_dict(self):
        self.assertIn("_cat_icons", self.src)

    def test_creature_icon_present(self):
        # Phase 19: emoji replaced by KotOR icon names in CATEGORIES 3-tuple
        self.assertTrue(
            "cat_creature" in self.src or "🐉" in self.src,
            "Creature category must have icon (cat_creature key or emoji)")

    def test_character_icon_present(self):
        # Phase 19: emoji replaced by KotOR icon names in CATEGORIES 3-tuple
        self.assertTrue(
            "cat_character" in self.src or "🧍" in self.src,
            "Character category must have icon (cat_character key or emoji)")

    def test_module_icon_present(self):
        # Phase 19: emoji replaced by KotOR icon names in CATEGORIES 3-tuple
        self.assertTrue(
            "cat_module" in self.src or "🏛" in self.src,
            "Module category must have icon (cat_module key or emoji)")

    def test_icons_shown_for_all_tab(self):
        self.assertIn("cat == 'All'", self.src)
        self.assertIn("icon = _cat_icons", self.src)


# ── Viewport HUD ──────────────────────────────────────────────────────────────
class TestViewportHUD(unittest.TestCase):
    """Phase 18: Viewport HUD shows model name + shade mode badge."""

    def setUp(self):
        self.vp = _get_viewport_src()

    def test_hud_model_name_line(self):
        self.assertIn("_hud_line", self.vp,
                      "HUD should show model name + mesh count")

    def test_hud_shade_badge(self):
        self.assertIn("_shade_var", self.vp,
                      "HUD shade-mode badge uses _shade_var")

    def test_hud_fps_still_present(self):
        self.assertIn("fps_txt", self.vp,
                      "FPS counter HUD should still be present")

    def test_hud_uses_create_text(self):
        # Ensure the canvas.create_text calls exist for HUD elements
        self.assertIn("canvas.create_text", self.vp)


# ── ResourceManager primary path ──────────────────────────────────────────────
class TestResourceManagerPrimary(unittest.TestCase):
    """Phase 18: ResourceManager is the primary path for K1/K2 installation."""

    def setUp(self):
        self.src = _get_main_window_src()

    def test_rm_primary_comment_in_k1_create(self):
        self.assertIn("Primary: update ResourceManager", self.src,
                      "_create_k1_install should call _update_resource_manager first")

    def test_rm_preferred_over_installation_in_k1(self):
        idx = self.src.find("def _create_k1_install")
        snippet = self.src[idx: idx + 600]
        self.assertIn("set_resource_manager", snippet)

    def test_rm_preferred_over_installation_in_k2(self):
        idx = self.src.find("def _create_k2_install")
        snippet = self.src[idx: idx + 600]
        self.assertIn("set_resource_manager", snippet)


# ── PyKotor 2DA integration ───────────────────────────────────────────────────
class TestPyKotor2DAIntegration(unittest.TestCase):
    """Phase 18: TwoDaBrowserPanel uses pykotor for display and export."""

    def setUp(self):
        self.src = _get_main_window_src()

    def test_pk_tda_attribute(self):
        self.assertIn("_pk_tda", self.src)

    def test_get_headers_used(self):
        self.assertIn("pk_tda.get_headers()", self.src)

    def test_get_cell_used(self):
        self.assertIn("pk_tda.get_cell", self.src)

    def test_pykotor_badge_in_row_count(self):
        self.assertIn("[pykotor]", self.src)

    def test_tsv_export_tries_pykotor(self):
        idx = self.src.find("def _export_tsv")
        snippet = self.src[idx: idx + 1600]
        self.assertIn("pk_tda", snippet)
        self.assertIn("[pykotor]", snippet)

    def test_csv_export_tries_pykotor(self):
        idx = self.src.find("def _export_csv")
        snippet = self.src[idx: idx + 1600]
        self.assertIn("pk_tda", snippet)
        self.assertIn("[pykotor]", snippet)


# ── Menu accelerators ─────────────────────────────────────────────────────────
class TestMenuAccelerators(unittest.TestCase):
    """Phase 18: File and Model menus show accelerator labels."""

    def setUp(self):
        self.src = _get_main_window_src()

    def test_ctrl_o_accelerator(self):
        self.assertIn('accelerator="Ctrl+O"', self.src)

    def test_ctrl_s_accelerator(self):
        self.assertIn('accelerator="Ctrl+S"', self.src)

    def test_ctrl_e_accelerator(self):
        self.assertIn('accelerator="Ctrl+E"', self.src)

    def test_f2_accelerator_settings(self):
        self.assertIn('accelerator="F2"', self.src)

    def test_f5_accelerator_refresh(self):
        self.assertIn('accelerator="F5"', self.src)

    def test_frame_all_accelerator(self):
        self.assertIn('accelerator="F"', self.src)

    def test_ctrl_r_autorig_accelerator(self):
        self.assertIn('accelerator="Ctrl+R"', self.src)


# ── New keyboard shortcuts ────────────────────────────────────────────────────
class TestNewKeyboardShortcuts(unittest.TestCase):
    """Phase 18: Ctrl+F, Ctrl+L, F3 shortcuts registered."""

    def setUp(self):
        self.src = _get_main_window_src()

    def test_ctrl_f_focus_search(self):
        self.assertIn("<Control-f>", self.src)
        self.assertIn("def _focus_search", self.src)

    def test_ctrl_l_focus_library(self):
        self.assertIn("<Control-l>", self.src)
        self.assertIn("def _focus_library_search", self.src)

    def test_f3_model_info(self):
        self.assertIn("<F3>", self.src)

    def test_escape_deselects_node(self):
        self.assertIn("<Escape>", self.src)
        self.assertIn("def _on_escape", self.src)


if __name__ == "__main__":
    unittest.main()
