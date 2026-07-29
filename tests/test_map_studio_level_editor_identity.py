from __future__ import annotations

import json
import math
import os
import sys
import time
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_t2600_map_studio_and_module_editor_are_separate_main_screen_entries() -> None:
    """Map Studio stays KMAP-focused while Module Editor opens stock MOD/RIM archives."""

    chrome_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/"
        "application_core/shared/window_chrome.py"
    )
    viewport_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/construction.py"
    )
    viewport_widget_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/viewport_widget.py"
    )
    viewport_variants_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/viewports/"
        "viewport_core/widgets/variants.py"
    )
    map_viewport_panel_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/"
        "module_editor/module_editor_viewport_panel.py"
    )
    map_window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/module_editor_window.py"
    )
    resource_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/"
        "application_core/shared/resource_panels.py"
    )
    integration_source = _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/"
        "integration/tool_integration_registry.py"
    )

    assert 'QtGui.QAction(self._icon(MAIN_ACTION_ICON_KEYS["map_studio"]), "Open Map Studio (KMAP Area Authoring)", self)' in chrome_source
    assert "self.modules_action.triggered.connect(self._open_map_studio_modeling_workspace)" in chrome_source
    assert 'QtGui.QAction(self._icon(MAIN_ACTION_ICON_KEYS["module_editor"]), "Open Module Editor (Stock MOD/RIM Patcher)", self)' in chrome_source
    assert "self.stock_module_editor_action.triggered.connect(self._open_stock_module_editor_window)" in chrome_source
    assert "def _command_launcher_groups" in chrome_source
    assert "self.modules_action," in chrome_source
    assert "self.stock_module_editor_action," in chrome_source
    assert '"CommandStripMapStudioButton"' not in chrome_source
    assert '"CommandStripModuleEditorButton"' not in chrome_source
    assert "Patch textures, walkmeshes, and objects in existing stock" in chrome_source
    main_toolbar_band_source = chrome_source.split("def _make_viewport_toolbar_band", 1)[1].split(
        "def _make_viewport_modeling_tabs",
        1,
    )[0]
    assert "ViewportToolbarMapStudioModelingButton" not in main_toolbar_band_source
    assert "ViewportToolbarMapStudioModelingTabs" not in main_toolbar_band_source
    assert "take_viewport_modeling_tabs" not in main_toolbar_band_source
    assert "DEFAULT_MAP_STUDIO_AUTHORING_CHROME = False" in viewport_widget_source
    assert "class QtMapStudioViewportWidget" in viewport_variants_source
    assert 'VIEWPORT_ROLE = "map_studio"' in viewport_variants_source
    assert "DEFAULT_MAP_STUDIO_AUTHORING_CHROME = True" in viewport_variants_source
    assert "QtMapStudioViewportWidget(self)" in map_viewport_panel_source
    assert "def _make_map_studio_modeling_tabs" in viewport_source
    assert "self.viewport_map_studio_modeling_tabs" in viewport_source
    assert "ViewportToolbarMapStudioModelingTabs" in viewport_source
    assert "ViewportToolbarMapStudioModelingScrollArea" in viewport_source
    assert "ViewportToolbarMapStudioBlockoutScrollArea" in viewport_source
    assert 'tabs.addTab(modeling_tab, "Modeling")' in viewport_source
    assert "ViewportToolbarMapStudioBlockoutTab" in viewport_source
    assert 'tabs.addTab(blockout_tab, "Blockout")' in viewport_source
    assert "def take_viewport_modeling_tabs" in viewport_source
    assert "def _open_map_studio_mode_from_toolbar" in viewport_source
    assert "def _run_map_studio_command_from_toolbar" in viewport_source
    for mode_label in ("Object", "Vertex", "Edge", "Face", "Terrain", "Walkmesh"):
        assert f'"{mode_label}"' in viewport_source
    for action_key in (
        "duplicate_selected",
        "delete_selected",
        "extrude",
        "bevel",
        "triangulate",
        "texture_paint",
        "paint_material",
        "paint_wok",
    ):
        assert f'"{action_key}"' in viewport_source
    for tool_label in ("Paint", "Material", "WOK"):
        assert f'"{tool_label}"' in viewport_source
    for blockout_key in (
        "blockout_room",
        "floor",
        "wall",
        "cube",
        "ramp",
        "stairs",
        "door_frame",
        "arch",
        "terrain_patch",
    ):
        assert f'"{blockout_key}"' in viewport_source
    for blockout_label in ("Room", "Floor", "Wall", "Cube", "Ramp", "Stairs", "Doorway", "Arch", "Terrain"):
        assert f'"{blockout_label}"' in viewport_source
    assert "def _open_map_studio_mode_from_viewport" in map_window_source
    assert "def _run_map_studio_viewport_modeling_command" in map_window_source
    assert "self.move_map_studio_authored_primitive_selection()" in map_window_source
    assert 'self._execute_map_studio_tool_belt_command("' not in chrome_source
    assert "def _open_map_studio_modeling_workspace" in resource_source
    assert "def _open_stock_module_editor_window" in resource_source
    assert "def _configure_stock_module_editor_game_library" in resource_source
    assert "set_game_library(manager, game=game)" in resource_source
    assert "configure_stock_module_editor(stock_module_editor_window)" in _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/"
        "application_core/shared/resource_loading.py"
    )
    assert "configure_stock_module_editor(stock_module_editor_window)" in _read(
        "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/"
        "application_core/shared/startup_library.py"
    )
    assert "focus_map_studio_modeling_workspace" in resource_source
    assert "Map Studio could not open" in resource_source
    assert "Module Editor opens the dedicated stock MOD/RIM archive workspace" in integration_source
    assert "Map Studio opens the existing KMAP Level Editor" in integration_source


def test_stock_module_editor_window_audits_mod_resources_with_content_browser() -> None:
    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "stock_module_editor_window.py"
    )
    archive_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_archive.py"
    )
    texture_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_textures.py"
    )
    safety_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_resource_safety.py"
    )
    tga_editor_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_tga_editor.py"
    )
    txi_editor_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_txi_editor.py"
    )
    material_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_materials.py"
    )
    git_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_git.py"
    )
    layout_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_layout.py"
    )
    logic_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_logic.py"
    )
    metadata_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_metadata.py"
    )
    template_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_templates.py"
    )
    patch_plan_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_patch_plan.py"
    )
    export_queue_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_export_queue.py"
    )
    mdl_patch_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_mdl_patch.py"
    )
    wok_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_walkmesh.py"
    )
    package_intake_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/core/stock_modules/"
        "stock_module_package_intake.py"
    )

    assert "class StockModuleEditorWindow(QtWidgets.QMainWindow)" in window_source
    assert 'self.setWindowTitle("Ghost-Studio Module Editor")' in window_source
    assert "stockModuleEditorSceneOutliner" in window_source
    assert "stockModuleEditorContentBrowser" in window_source
    assert "stockModuleEditorCenterScroll" in window_source
    assert "QtWidgets.QAbstractScrollArea.AdjustIgnored" in window_source
    assert "stockModuleEditorOnboarding" in window_source
    assert "stockModuleEditorOnboardingOpenButton" in window_source
    assert "the source archive is never overwritten" in window_source
    assert "stockModuleEditorLoadInstalledTexturesAction" in window_source
    assert "class _InstalledTextureDiscoveryWorker(QtCore.QObject)" in window_source
    assert "self._game_texture_thread = thread" in window_source
    assert "stockModuleEditorMaterialPickPanel" in window_source
    assert "stockModuleEditorMaterialBoardNavigation" in window_source
    assert "stockModuleEditorMaterialBoardPrevButton" in window_source
    assert "stockModuleEditorMaterialBoardNextButton" in window_source
    assert "stockModuleEditorMaterialBoardPageLabel" in window_source
    assert "stockModuleEditorMaterialFilter" in window_source
    assert "stockModuleEditorMaterialPicker" in window_source
    assert "stockModuleEditorMaterialPreview" in window_source
    assert "stockModuleEditorTextureCompare" in window_source
    assert "stockModuleEditorImportTextureAction" in window_source
    assert "stockModuleEditorStageMatchingTexturesAction" in window_source
    assert "stockModuleEditorTgaEditor" in window_source
    assert "stockModuleEditorTgaOutputResRef" in window_source
    assert "stockModuleEditorTgaBrightnessSpin" in window_source
    assert "stockModuleEditorTgaContrastSpin" in window_source
    assert "stockModuleEditorTgaSnowSpin" in window_source
    assert "stockModuleEditorTgaPreviewEditButton" in window_source
    assert "stockModuleEditorTxiEditor" in window_source
    assert "stockModuleEditorTxiOutputResRef" in window_source
    assert "stockModuleEditorTxiTextEdit" in window_source
    assert "stockModuleEditorTxiPreviewEditButton" in window_source
    assert "stockModuleEditorStageEditAction" in window_source
    assert "stockModuleEditorClearStagedEditsAction" in window_source
    assert "stockModuleEditorEditQueue" in window_source
    assert "stockModuleEditorWokSurfaceEditor" in window_source
    assert "stockModuleEditorWokFaceSpin" in window_source
    assert "stockModuleEditorWokSurfaceCombo" in window_source
    assert "stockModuleEditorWokPreviewPaintButton" in window_source
    assert "stockModuleEditorLayoutEditor" in window_source
    assert "stockModuleEditorLayoutTargetCombo" in window_source
    assert "stockModuleEditorLayoutFieldCombo" in window_source
    assert "stockModuleEditorLayoutValueEdit" in window_source
    assert "stockModuleEditorLayoutVisibleToggle" in window_source
    assert "stockModuleEditorLayoutPreviewEditButton" in window_source
    assert "stockModuleEditorGitObjectEditor" in window_source
    assert "stockModuleEditorGitObjectCombo" in window_source
    assert "stockModuleEditorGitFieldCombo" in window_source
    assert "stockModuleEditorGitValueEdit" in window_source
    assert "stockModuleEditorGitPreviewEditButton" in window_source
    assert "stockModuleEditorGitOpenTemplateButton" in window_source
    assert "stockModuleEditorTemplateEditor" in window_source
    assert "stockModuleEditorTemplateFieldCombo" in window_source
    assert "stockModuleEditorTemplateValueEdit" in window_source
    assert "stockModuleEditorTemplatePreviewEditButton" in window_source
    assert "stockModuleEditorMetadataEditor" in window_source
    assert "stockModuleEditorMetadataFieldCombo" in window_source
    assert "stockModuleEditorMetadataValueEdit" in window_source
    assert "stockModuleEditorMetadataPreviewEditButton" in window_source
    assert "stockModuleEditorLogicEditor" in window_source
    assert "stockModuleEditorLogicFieldCombo" in window_source
    assert "stockModuleEditorLogicValueEdit" in window_source
    assert "stockModuleEditorLogicPreviewEditButton" in window_source
    assert "stockModuleEditorCurrentTexturePreview" in window_source
    assert "stockModuleEditorReplacementTexturePreview" in window_source
    assert "read_module_archive_resources" in window_source
    assert "read_module_resource_bytes" in window_source
    assert "prepare_module_open_path" in window_source
    assert "TemporaryDirectory" in window_source
    assert "*.mod *.rim *.erf *.zip" in window_source
    assert "Source package" in window_source
    assert "Opened module path" in window_source
    assert "decode_module_texture_preview" in window_source
    assert "classify_module_resource" in window_source
    assert "summarize_resource_safety" in window_source
    assert "summarize_resource_safety_scopes" in window_source
    assert "class ModuleAuditFilterTarget" in window_source
    assert "_resource_filter_directive" in window_source
    assert "_select_audit_filter_target" in window_source
    assert "status:" in window_source
    assert "scope:" in window_source
    assert "filter the content browser" in window_source
    assert "Edit status" in window_source
    assert "Safety policy" in window_source
    assert "Export policy" in window_source
    assert "inspect_module_room_materials" in window_source
    assert "inspect_module_git" in window_source
    assert "inspect_module_layout" in window_source
    assert "inspect_module_logic" in window_source
    assert "inspect_module_metadata" in window_source
    assert "inspect_module_template" in window_source
    assert "inspect_module_wok" in window_source
    assert "_material_inventory_cache" in window_source
    assert "_git_inventory_cache" in window_source
    assert "_layout_inventory_cache" in window_source
    assert "_logic_inventory_cache" in window_source
    assert "_metadata_inventory_cache" in window_source
    assert "_template_inventory_cache" in window_source
    assert "_wok_inventory_cache" in window_source
    assert "_selected_material_slot" in window_source
    assert "_pending_texture_replacement" in window_source
    assert "_imported_texture_resources" in window_source
    assert "_create_pending_texture_replacement" in window_source
    assert "_browse_import_texture" in window_source
    assert "def import_texture" in window_source
    assert "_matching_imported_texture_sidecars" in window_source
    assert "_texture_replacement_rows" in window_source
    assert "summarize_texture_patch_preflight" in window_source
    assert "Patch preflight" in window_source
    assert "Patched resources" in window_source
    assert "Bundled resources" in window_source
    assert "_preview_tga_edit" in window_source
    assert "_register_edited_tga_resource" in window_source
    assert "_tga_edit_rows" in window_source
    assert "_preview_txi_edit" in window_source
    assert "_register_edited_txi_resource" in window_source
    assert "_txi_edit_rows" in window_source
    assert "_sync_selection_from_details" in window_source
    assert "_sync_selection_from_material_pick_panel" in window_source
    assert "_sync_selection_from_material_picker" in window_source
    assert "_select_material_slot" in window_source
    assert "_sync_material_slot_selection" in window_source
    assert "_populate_material_pick_panel" in window_source
    assert "_texture_preview_overrides_for_room" in window_source
    assert "_refresh_material_views_for_room" in window_source
    assert "_show_room_material_board" in window_source
    assert "_show_room_material_board_for_slot" in window_source
    assert "_next_room_board_page" in window_source
    assert "_previous_room_board_page" in window_source
    assert "_filtered_material_slots" in window_source
    assert "_material_filter_changed" in window_source
    assert "def eventFilter" in window_source
    assert "_select_room_board_slot_at" in window_source
    assert "_prime_texture_browser_for_material_slot" in window_source
    assert "room material board" in window_source
    assert "_room_board_slot_text" in window_source
    assert "material targets" in window_source
    assert "_texture_pick_hint" in window_source
    assert "Session texture overrides" in window_source
    assert "Session preview texture" in window_source
    assert "_material_slot_icon" in window_source
    assert "_update_material_preview" in window_source
    assert "_update_texture_compare" in window_source
    assert "_set_texture_compare_label" in window_source
    assert "_preview_wok_surface_paint" in window_source
    assert "_select_wok_surface_summary" in window_source
    assert "_wok_surface_paint_rows" in window_source
    assert "_export_wok_surface_patch_copy" in window_source
    assert "_stage_current_edit" in window_source
    assert "_stage_matching_texture_replacements" in window_source
    assert "_all_material_slots" in window_source
    assert "_texture_usage_slots" in window_source
    assert "_refresh_edit_queue" in window_source
    assert "stockModuleEditorEditQueuePreflight" in window_source
    assert "Queued export preflight" in window_source
    assert "Preserved source resources" in window_source
    assert "_export_queued_patch_copy" in window_source
    assert "_preview_layout_edit" in window_source
    assert "_layout_edit_rows" in window_source
    assert "_export_layout_patch_copy" in window_source
    assert "_preview_git_object_edit" in window_source
    assert "_populate_git_field_editor" in window_source
    assert "_git_object_edit_rows" in window_source
    assert "_export_git_object_patch_copy" in window_source
    assert "_preview_template_field_edit" in window_source
    assert "_template_field_edit_rows" in window_source
    assert "_export_template_field_patch_copy" in window_source
    assert "_preview_metadata_field_edit" in window_source
    assert "_metadata_field_edit_rows" in window_source
    assert "_export_metadata_field_patch_copy" in window_source
    assert "_preview_logic_field_edit" in window_source
    assert "_logic_field_edit_rows" in window_source
    assert "_export_logic_field_patch_copy" in window_source
    assert "choose a TGA/TPC texture" in window_source
    assert "ready for copied module export" in window_source
    assert "_find_texture_resource" in window_source
    assert "_find_texture_sidecar_resource" in window_source
    assert "_texture_sidecar_summary" in window_source
    assert "Current TXI" in window_source
    assert "Replacement TXI" in window_source
    assert "_show_texture_resource_preview" in window_source
    assert "set_game_library" in window_source
    assert "_discover_game_library_textures" in window_source
    assert "ModuleTextureLibraryResource" in window_source
    assert "ModuleTextureFileResource" in window_source
    assert "imported texture:" in window_source
    assert "write_texture_patch_export_copy" in window_source
    assert "write_queued_module_patch_export_copy" in window_source
    assert "_export_texture_patch_copy" in window_source
    assert "_module_export_default_path" in window_source
    assert "Room material workflow" in window_source
    assert "Walkmesh workflow" in window_source
    assert "face selection and surface painting target" in window_source
    assert "Door/transition faces" in window_source
    assert "GIT workflow" in window_source
    assert "placed object forms and template-reference editing target" in window_source
    assert "Placed object forms" in window_source
    assert "Layout workflow" in window_source
    assert "room placement and visibility graph editing target" in window_source
    assert "_select_layout_room_row" in window_source
    assert "_select_visibility_row" in window_source
    assert "Visibility links" in window_source
    assert "Logic workflow" in window_source
    assert "_select_logic_field" in window_source
    assert "path/dialogue/script inspection, DLG top-level edits, dependency checks, and list-preserving export target" in window_source
    assert "Metadata workflow" in window_source
    assert "area/module metadata inspection and override target" in window_source
    assert "_select_metadata_field" in window_source
    assert "Gameplay workflow" in window_source
    assert "template form inspection and override target" in window_source
    assert "_select_template_field" in window_source
    assert "Template kind" in window_source
    assert "ARE/IFO" in window_source
    assert "per-face splitting is later" in window_source
    assert "preview only; source archive bytes unchanged" in window_source
    assert "patched MDL texture refs" in window_source
    assert "Selected material from {source}; choose a TGA/TPC texture to preview replacement." in window_source
    assert "_texture_preview_cache" in window_source
    assert "_texture_icon_cache" in window_source
    assert "TGA/TPC/TXI texture replacement, WOK faces, LYT/VIS layout links, GIT objects, templates, ARE/IFO metadata, DLG top-level fields" in window_source
    assert "def discover_module_package_candidates" in package_intake_source
    assert "def prepare_module_open_path" in package_intake_source
    assert "zipfile.ZipFile" in package_intake_source
    assert "MODULE_ARCHIVE_SUFFIXES" in package_intake_source
    assert "_safe_package_member_filename" in package_intake_source
    assert "def read_module_resource_bytes" in archive_source
    assert '3007: "tpc"' in archive_source
    assert '2063: "bik"' in archive_source
    assert '4: "wav"' in archive_source
    assert "class ModuleResourceSafety" in safety_source
    assert "def classify_module_resource" in safety_source
    assert "def summarize_resource_safety" in safety_source
    assert "def summarize_resource_safety_scopes" in safety_source
    assert "unknown_binary_preserved" in safety_source
    assert "audio_movie_payload" in safety_source
    assert "source texture bytes stay unchanged" in safety_source
    assert "nested dialogue trees stay list-preserving" in safety_source
    assert "class ModuleTexturePreview" in texture_source
    assert "class ModuleTextureLibraryResource" in texture_source
    assert "class ModuleTextureFileResource" in texture_source
    assert "class ModuleTextureMemoryResource" in texture_source
    assert "def decode_module_texture_preview" in texture_source
    assert "class ModuleTgaEditDraft" in tga_editor_source
    assert "def create_tga_adjustment_draft" in tga_editor_source
    assert "format=\"TGA\"" in tga_editor_source
    assert "validation_status=\"valid\"" in tga_editor_source
    assert "class ModuleTxiEditDraft" in txi_editor_source
    assert "def create_txi_text_edit_draft" in txi_editor_source
    assert "TXI text must be ASCII" in txi_editor_source
    assert "class ModuleRoomTextureSlot" in material_source
    assert "class ModuleRoomMaterialInventory" in material_source
    assert "class ModuleRoomTextureDependency" in material_source
    assert "class ModuleRoomTexturePreviewOverride" in material_source
    assert "class ModuleTextureReplacementSidecar" in material_source
    assert "class ModuleTextureReplacementDraft" in material_source
    assert "replacement_sidecars" in material_source
    assert "def inspect_module_room_materials" in material_source
    assert "_inspect_room_materials_from_mdl_texture_fields" in material_source
    assert "texture_fields_only" in material_source
    assert "def summarize_material_inventories" in material_source
    assert "class ModuleTextureUsageSummary" in material_source
    assert "def summarize_texture_usage" in material_source
    assert "def summarize_texture_dependencies" in material_source
    assert "def find_texture_usage_slots" in material_source
    assert "def create_texture_replacement_draft" in material_source
    assert "Replacement texture resref exceeds 16 characters" in material_source
    assert "Replacement texture resref must be ASCII" in material_source
    assert "def create_texture_replacement_drafts_for_matching_slots" in material_source
    assert "def summarize_texture_preview_overrides" in material_source
    assert "def texture_preview_for_slot" in material_source
    assert "class ModuleGitInventory" in git_source
    assert "class ModuleGitObjectCount" in git_source
    assert "class ModuleGitObjectEditableField" in git_source
    assert "class ModuleGitObjectRow" in git_source
    assert "class ModuleGitObjectEditDraft" in git_source
    assert "SUPPORTED_GIT_EDIT_FIELDS" in git_source
    assert "def inspect_module_git" in git_source
    assert "def create_git_object_edit_draft" in git_source
    assert "def write_git_object_patch_export_copy" in git_source
    assert "build_module_object_inspector" in git_source
    assert 'editable_scope: str = "git_object_forms"' in git_source
    assert "class ModuleLayoutInventory" in layout_source
    assert "class ModuleLayoutRoomRow" in layout_source
    assert "class ModuleVisibilityRow" in layout_source
    assert "class ModuleLayoutEditDraft" in layout_source
    assert "def create_layout_edit_draft" in layout_source
    assert "def write_layout_patch_export_copy" in layout_source
    assert "def inspect_module_layout" in layout_source
    assert "LYTLayout.from_text" in layout_source
    assert "VISData.from_text" in layout_source
    assert 'editable_scope="room_layout"' in layout_source
    assert 'editable_scope="room_visibility"' in layout_source
    assert "class ModuleLogicInventory" in logic_source
    assert "class ModuleLogicField" in logic_source
    assert "class ModuleLogicListSummary" in logic_source
    assert "class ModuleLogicReference" in logic_source
    assert "class ModuleLogicFieldEditDraft" in logic_source
    assert "class ModuleLogicPatchExportResult" in logic_source
    assert "_nss_references" in logic_source
    assert "_gff_references" in logic_source
    assert "def inspect_module_logic" in logic_source
    assert "def create_logic_field_edit_draft" in logic_source
    assert "def write_logic_field_patch_export_copy" in logic_source
    assert "GFFReader.from_bytes" in logic_source
    assert "Compiled NCS bytecode is list-only" in logic_source
    assert "script_source_list_only" in logic_source
    assert "dlg_top_level_fields" in logic_source
    assert "class ModuleMetadataInventory" in metadata_source
    assert "class ModuleMetadataField" in metadata_source
    assert "class ModuleMetadataFieldEditDraft" in metadata_source
    assert "def create_metadata_field_edit_draft" in metadata_source
    assert "def write_metadata_field_patch_export_copy" in metadata_source
    assert "def inspect_module_metadata" in metadata_source
    assert "AREData.from_bytes" in metadata_source
    assert "IFOData.from_bytes" in metadata_source
    assert "area_metadata" in metadata_source
    assert "module_metadata" in metadata_source
    assert "class ModuleTemplateInventory" in template_source
    assert "class ModuleTemplateField" in template_source
    assert "class ModuleTemplateListSummary" in template_source
    assert "class ModuleTemplateFieldEditDraft" in template_source
    assert "def create_template_field_edit_draft" in template_source
    assert "def write_template_field_patch_export_copy" in template_source
    assert "def inspect_module_template" in template_source
    assert "GFFReader.from_bytes" in template_source
    assert "Creature/NPC" in template_source
    assert "Store/Merchant" in template_source
    assert "gameplay_template_form" in template_source
    assert "class ModuleTexturePatchPlan" in patch_plan_source
    assert "class ModuleTexturePatchPreflight" in patch_plan_source
    assert "def build_texture_patch_plan" in patch_plan_source
    assert "target_room_missing" in patch_plan_source
    assert "target_texture_field_unpatchable" in patch_plan_source
    assert "def summarize_texture_patch_preflight" in patch_plan_source
    assert "def write_texture_patch_export_copy" in patch_plan_source
    assert "replacement_sidecars" in patch_plan_source
    assert "source module preserved" in patch_plan_source
    assert "source_overwrite_refused" in patch_plan_source
    assert "archive_bytes_modified" in patch_plan_source
    assert "patch_room_mdl_texture_reference" in patch_plan_source
    assert "build_erf_v1_archive" in patch_plan_source
    assert "class ModuleQueuedPatchExportResult" in export_queue_source
    assert "class ModuleQueuedPatchPreflight" in export_queue_source
    assert "def summarize_queued_module_patch_preflight" in export_queue_source
    assert "source module preserved; copied export receives staged edits" in export_queue_source
    assert "preserved_resources" in export_queue_source
    assert "preserve_summary" in export_queue_source
    assert "def write_queued_module_patch_export_copy" in export_queue_source
    assert "QueuedModuleEditDraft" in export_queue_source
    assert "ModuleLogicFieldEditDraft" in export_queue_source
    assert '"logic"' in export_queue_source
    assert "ghostrigger.stock_module_queued_patch_plan.v1" in export_queue_source
    assert "class ModuleMDLTexturePatchResult" in mdl_patch_source
    assert "def patch_room_mdl_texture_reference" in mdl_patch_source
    assert "_MESH_TEXTURE_OFFSET = 88" in mdl_patch_source
    assert "class ModuleWokInventory" in wok_source
    assert "class ModuleWokSurfaceSummary" in wok_source
    assert "face_indices: tuple[int, ...]" in wok_source
    assert "class ModuleWokSurfacePaintDraft" in wok_source
    assert "def walkmesh_surface_options" in wok_source
    assert "def create_wok_surface_paint_draft" in wok_source
    assert "def write_wok_surface_patch_export_copy" in wok_source
    assert "def inspect_module_wok" in wok_source
    assert "build_walkmesh_workbench" in wok_source
    assert 'editable_scope: str = "walkmesh_face_surface"' in wok_source


def test_stock_module_texture_replacement_draft_is_preview_only_runtime() -> None:
    """Texture replacement state names a material slot without changing archive bytes."""

    _configure_native_python_roots()

    from src.core.stock_modules.stock_module_archive import (
        ModuleArchiveResource,
        read_module_archive_resources,
        read_module_resource_bytes,
    )
    from src.core.stock_modules.stock_module_materials import (
        ModuleRoomMaterialInventory,
        ModuleRoomTextureSlot,
        create_texture_replacement_draft,
        summarize_texture_dependencies,
        summarize_texture_preview_overrides,
        texture_preview_for_slot,
    )
    from src.core.stock_modules.stock_module_textures import ModuleTextureFileResource

    slot = ModuleRoomTextureSlot(
        room_resref="koq200_01a",
        node_name="mesh_a",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=12,
        vertex_count=24,
    )
    texture = ModuleArchiveResource(
        resref="snow_wall",
        restype_id=3,
        restype="tga",
        offset=128,
        size=4096,
    )

    draft = create_texture_replacement_draft(slot, texture)

    assert draft.status == "preview_only"
    assert draft.original_texture_resref == "lko_wal02"
    assert draft.replacement_texture_resref == "snow_wall"
    assert draft.replacement_source_label == "snow_wall.tga"
    assert "lko_wal02 -> snow_wall" in draft.summary
    inventory = ModuleRoomMaterialInventory("koq200_01a", (slot,))
    overrides = summarize_texture_preview_overrides(inventory, (draft,), staged_count=0)
    assert len(overrides) == 1
    assert overrides[0].summary == "koq200_01a.mesh_a diffuse: lko_wal02 -> snow_wall (preview)"
    assert texture_preview_for_slot(slot, overrides) == overrides[0]
    replacement = ModuleTextureFileResource(
        resref="snow_wall",
        restype="tga",
        restype_id=3,
        path="snow_wall.tga",
        size=128,
    )
    dependencies = summarize_texture_dependencies(inventory, (texture,), overrides)
    assert dependencies[0].source_status == "missing"
    assert dependencies[0].effective_texture_resref == "snow_wall"
    assert dependencies[0].effective_source_label == "module archive snow_wall.tga"
    session_dependencies = summarize_texture_dependencies(inventory, (replacement,), overrides)
    assert session_dependencies[0].source_status == "missing"
    assert session_dependencies[0].effective_source_label == "session snow_wall.tga"


def test_stock_module_material_inventory_falls_back_to_mdl_texture_fields_runtime(tmp_path: Path) -> None:
    """Room material inspection still exposes texture slots when the full model loader is unavailable."""

    _configure_native_python_roots()

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_materials import inspect_module_room_materials

    module_path = tmp_path / "rnv_like.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry(
                    "koq200_01a",
                    "mdl",
                    _minimal_room_mdl("snow_target", "lko_wal02"),
                    source="fixture",
                ),
                ModuleArchiveEntry("koq200_01a", "mdx", b"", source="fixture"),
                ModuleArchiveEntry("lko_wal02", "tga", _tiny_tga_bytes(), source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    resources = {item.label: item for item in read_module_archive_resources(module_path)}

    inventory = inspect_module_room_materials(module_path, list(resources.values()), resources["koq200_01a.mdl"])

    assert inventory.parse_status == "texture_fields_only"
    assert "full model parsing was unavailable" in inventory.warning
    assert len(inventory.slots) == 1
    slot = inventory.slots[0]
    assert slot.room_resref == "koq200_01a"
    assert slot.node_name == "snow_target"
    assert slot.slot_kind == "diffuse"
    assert slot.texture_resref == "lko_wal02"
    assert slot.editable_scope == "material_slot"


def test_stock_module_resource_safety_classifies_editable_and_preserved_runtime(tmp_path: Path) -> None:
    """Module audits name editable, list-only, preserve-only, and unknown resource policy."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_resource_safety import (
        classify_module_resource,
        summarize_resource_safety,
        summarize_resource_safety_scopes,
    )
    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    module_path = tmp_path / "safety_audit.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("snow_wall", "tga", _tiny_tga_bytes(), source="fixture"),
                ModuleArchiveEntry("snow_rows", "2da", b"2DA V2.b\n\nlabel\nrow\n", source="fixture"),
                ModuleArchiveEntry("amb_snow", "wav", b"RIFFfake-wave", source="fixture"),
                ModuleArchiveEntry("intro", "bik", b"BIKfake-movie", source="fixture"),
                ModuleArchiveEntry("custom_blob", "zzx", b"custom", source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    resources = read_module_archive_resources(module_path)
    by_label = {resource.label: resource for resource in resources}

    assert by_label["amb_snow.wav"].restype == "wav"
    assert by_label["intro.bik"].restype == "bik"
    assert classify_module_resource(by_label["snow_wall.tga"]).edit_status == "editable now"
    assert classify_module_resource(by_label["snow_rows.2da"]).edit_status == "inspect/list-only"
    assert classify_module_resource(by_label["amb_snow.wav"]).editable_scope == "audio_movie_payload"
    assert classify_module_resource(by_label["custom_blob.type_0"]).editable_scope == "unknown_binary_preserved"
    assert summarize_resource_safety(resources) == {
        "editable now": 1,
        "inspect/list-only": 1,
        "preserve-only": 3,
    }
    assert summarize_resource_safety_scopes(resources) == {
        "audio_movie_payload": 2,
        "supporting_game_resource": 1,
        "texture_preview_replacement": 1,
        "unknown_binary_preserved": 1,
    }

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(module_path)
        audit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert audit_rows["Editable now resources"] == "1"
        assert audit_rows["Inspect/list-only resources"] == "1"
        assert audit_rows["Preserve-only resources"] == "3"
        assert audit_rows["Scope texture_preview_replacement"] == "1"
        assert audit_rows["Scope supporting_game_resource"] == "1"
        assert audit_rows["Scope audio_movie_payload"] == "2"
        assert audit_rows["Scope unknown_binary_preserved"] == "1"

        audit_row_by_name = {
            window.details.item(row, 0).text(): row
            for row in range(window.details.rowCount())
        }
        audio_scope_row = audit_row_by_name["Scope audio_movie_payload"]
        assert "filter the content browser" in window.details.item(audio_scope_row, 0).toolTip()
        window.details.selectRow(audio_scope_row)
        window._sync_selection_from_details()
        assert window.content_type_combo.currentText() == "All"
        assert window.content_search.text() == "scope:audio_movie_payload"
        assert window.content_browser.count() == 2
        assert {
            window.content_browser.item(index).data(QtCore.Qt.UserRole).label
            for index in range(window.content_browser.count())
        } == {"amb_snow.wav", "intro.bik"}

        preserve_status_row = audit_row_by_name["Preserve-only resources"]
        window.details.selectRow(preserve_status_row)
        window._sync_selection_from_details()
        assert window.content_search.text() == "status:preserve-only"
        assert window.content_browser.count() == 3
        assert {
            window.content_browser.item(index).data(QtCore.Qt.UserRole).label
            for index in range(window.content_browser.count())
        } == {"amb_snow.wav", "intro.bik", "custom_blob.type_0"}

        window.content_search.setText("scope:unknown_binary_preserved")
        window._populate_content_browser()
        assert window.content_browser.count() == 1
        assert window.content_browser.item(0).data(QtCore.Qt.UserRole).label == "custom_blob.type_0"

        window.content_search.setText("amb_snow")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        assert "preserve-only" in item.toolTip()
        assert "preserved byte-for-byte" in item.toolTip()
        window.content_browser.setCurrentItem(item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["Resource"] == "amb_snow.wav"
        assert detail_rows["Edit status"] == "preserve-only"
        assert detail_rows["Editable scope"] == "audio_movie_payload"
        assert "media payloads are intentionally not edited" in detail_rows["Safety policy"]
        assert detail_rows["Preserve/list-only workflow"] == "audio/movie resource identification only"

        window.content_search.setText("custom_blob")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        refreshed_resource = item.data(QtCore.Qt.UserRole)
        assert refreshed_resource.label == "custom_blob.type_0"
        window.content_browser.setCurrentItem(item)
        window._sync_selection_from_content_browser()
        unknown_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert unknown_rows["Resource"] == "custom_blob.type_0"
        assert unknown_rows["Edit status"] == "preserve-only"
        assert unknown_rows["Editable scope"] == "unknown_binary_preserved"
        assert "unsupported payloads are preserved" in unknown_rows["Safety policy"]
    finally:
        window.close()


def test_stock_module_editor_opens_zip_wrapped_module_runtime(tmp_path: Path) -> None:
    """Delivery zips open through a session temp module without unpacking into the repo."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_package_intake import (
        discover_module_package_candidates,
        prepare_module_open_path,
    )
    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    module_payload = build_erf_v1_archive(
        [
            ModuleArchiveEntry("snow_wall", "tga", _tiny_tga_bytes(), source="fixture"),
            ModuleArchiveEntry("koq200", "are", b"ARE V3.2\x00fixture", source="fixture"),
        ],
        archive_type="MOD",
    )
    package_path = tmp_path / "RNVcanyon.zip"
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("release/RNVcanyon.mod", module_payload)

    candidates = discover_module_package_candidates(package_path)
    assert len(candidates) == 1
    assert candidates[0].display_name == "RNVcanyon.mod"
    assert candidates[0].source_kind == "zip package"

    extraction_dir = tmp_path / "open-session"
    prepared = prepare_module_open_path(package_path, extraction_dir)
    assert prepared.module_path == extraction_dir / "RNVcanyon.mod"
    assert prepared.source_label == "RNVcanyon.zip:release/RNVcanyon.mod"
    assert prepared.module_path.read_bytes() == module_payload
    resources = read_module_archive_resources(prepared.module_path)
    assert {resource.label for resource in resources} == {"snow_wall.tga", "koq200.are"}

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(package_path)
        assert window._module_source_path == package_path
        assert window._module_source_label == "RNVcanyon.zip:release/RNVcanyon.mod"
        assert window._module_path is not None
        assert window._module_path.name == "RNVcanyon.mod"
        session_tempdir = window._module_path.parent
        assert session_tempdir.exists()
        assert window._module_path.read_bytes() == module_payload
        assert window._module_export_default_path("texture_patch") == tmp_path / "RNVcanyon_texture_patch.mod"
        assert window._module_export_default_path("_queued_patch") == tmp_path / "RNVcanyon_queued_patch.mod"
        assert not str(window._module_export_default_path("texture_patch")).startswith(str(session_tempdir))
        audit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert audit_rows["Source package"] == "RNVcanyon.zip:release/RNVcanyon.mod"
        assert audit_rows["Opened module path"] == str(window._module_path)
        assert audit_rows["Resources"] == "2"

        window.content_search.setText("snow_wall")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        assert item.text() == "snow_wall.tga"
    finally:
        window.close()

    assert not session_tempdir.exists()

    direct_window = StockModuleEditorWindow()
    direct_module_path = tmp_path / "direct.mod"
    direct_module_path.write_bytes(module_payload)
    try:
        direct_window.open_module(direct_module_path)
        assert direct_window._module_export_default_path("texture_patch") == tmp_path / "direct_texture_patch.mod"
    finally:
        direct_window.close()


def test_stock_module_wok_inventory_summarizes_surfaces_runtime(tmp_path: Path) -> None:
    """Stock Module Editor WOK inspection exposes walkmesh surface/validation facts."""

    _configure_native_python_roots()

    from src.core.modules.module_format import WOKData, WOKFace
    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes
    from src.core.stock_modules.stock_module_walkmesh import (
        create_wok_surface_paint_draft,
        inspect_module_wok,
        write_wok_surface_patch_export_copy,
    )

    wok = WOKData(name="koq200_01a")
    wok.verts = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
    ]
    wok.faces = [
        WOKFace(0, 1, 2, 1, -1, 1, -1),
        WOKFace(1, 3, 2, 7, -1, -1, 0),
        WOKFace(1, 3, 2, 18, -1, -1, -1),
    ]
    module_path = tmp_path / "walkmesh.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [ModuleArchiveEntry("koq200_01a", "wok", wok.to_bytes(), source="fixture")],
            archive_type="MOD",
        )
    )
    resource = read_module_archive_resources(module_path)[0]

    inventory = inspect_module_wok(module_path, resource)

    assert inventory.ok is True
    assert inventory.editable_scope == "walkmesh_face_surface"
    assert inventory.vertex_count == 4
    assert inventory.face_count == 3
    assert inventory.walkable_face_count == 2
    assert inventory.non_walk_face_count == 1
    assert inventory.transition_face_count == 1
    surface_rows = {surface.surface_name: surface for surface in inventory.surfaces}
    assert surface_rows["DIRT"].face_count == 1
    assert surface_rows["DIRT"].walkable is True
    assert surface_rows["NON_WALK"].face_count == 1
    assert surface_rows["NON_WALK"].walkable is False
    assert surface_rows["DOOR"].face_count == 1

    parsed_source_wok = WOKData.from_bytes(read_module_resource_bytes(module_path, resource))
    non_walk_face_index = next(index for index, face in enumerate(parsed_source_wok.faces) if face.surface == 7)
    assert surface_rows["NON_WALK"].face_indices == (non_walk_face_index,)

    draft = create_wok_surface_paint_draft(module_path, resource, non_walk_face_index, 19)
    assert draft.ready is True
    assert draft.old_surfaces == {non_walk_face_index: 7}
    assert draft.new_surface_name == "NON_WALK_GRASS"
    output_path = tmp_path / "walkmesh_wok_patch.mod"
    result = write_wok_surface_patch_export_copy(module_path, output_path, draft)
    assert result.ok is True
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == "ghostrigger.stock_module_wok_surface_patch_plan.v1"
    assert manifest["patched_resources"] == ["koq200_01a.wok"]
    assert manifest["draft"]["face_indices"] == [non_walk_face_index]
    assert manifest["draft"]["old_surfaces"] == {str(non_walk_face_index): 7}
    assert manifest["draft"]["new_surface_name"] == "NON_WALK_GRASS"
    output_resources = read_module_archive_resources(output_path)
    output_wok_resource = next(item for item in output_resources if item.label == "koq200_01a.wok")
    patched_wok = WOKData.from_bytes(read_module_resource_bytes(output_path, output_wok_resource))
    assert patched_wok.faces[non_walk_face_index].surface == 19

    unsupported_path = tmp_path / "unsupported.mod"
    unsupported_path.write_bytes(
        build_erf_v1_archive(
            [ModuleArchiveEntry("ascii_walk", "wok", b"node tri ascii wok", source="fixture")],
            archive_type="MOD",
        )
    )
    unsupported_resource = read_module_archive_resources(unsupported_path)[0]
    unsupported = inspect_module_wok(unsupported_path, unsupported_resource)
    assert unsupported.parse_status == "unsupported_format"
    assert "BWM binary signature" in unsupported.warning

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(module_path)
        window.content_type_combo.setCurrentText("Rooms")
        window.content_search.setText("koq200")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        refreshed_resource = item.data(QtCore.Qt.UserRole)
        assert refreshed_resource.label == "koq200_01a.wok"
        window.content_browser.setCurrentItem(item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["WOK parse"] == "ok"
        assert detail_rows["Walkable faces"] == "2"
        assert detail_rows["Non-walk faces"] == "1"
        assert detail_rows["Door/transition faces"] == "1"
        assert detail_rows["Surface 18 DOOR"] == "1 faces; walkable"
        assert item.data(QtCore.Qt.UserRole).label == "koq200_01a.wok"
        assert window.wok_face_spin.isEnabled() is True
        assert window.wok_surface_combo.isEnabled() is True
        assert window.wok_preview_button.isEnabled() is True
        non_walk_detail_row = -1
        for row_index in range(window.details.rowCount()):
            if window.details.item(row_index, 0).text() == "Surface 7 NON_WALK":
                non_walk_detail_row = row_index
                break
        assert non_walk_detail_row >= 0
        assert f"target face {non_walk_face_index}" in window.details.item(non_walk_detail_row, 0).toolTip()
        window.details.selectRow(non_walk_detail_row)
        window._sync_selection_from_details()
        assert window.wok_face_spin.value() == non_walk_face_index
        assert int(window.wok_surface_combo.currentData()) == 7
        for index in range(window.wok_surface_combo.count()):
            if int(window.wok_surface_combo.itemData(index)) == 19:
                window.wok_surface_combo.setCurrentIndex(index)
                break
        window._preview_wok_surface_paint()
        assert window._pending_wok_surface_paint is not None
        assert window._pending_wok_surface_paint.ready is True
        assert window.save_copy_action.isEnabled() is True
        paint_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert paint_rows["Pending WOK surface paint"] == f"koq200_01a.wok face(s) {non_walk_face_index} -> NON_WALK_GRASS (19)"
        assert paint_rows["Old surfaces"] == f"{non_walk_face_index}:7"
        assert paint_rows["Export state"] == "ready for copied module export"
    finally:
        window.close()


def test_stock_module_layout_inventory_summarizes_lyt_vis_runtime(tmp_path: Path) -> None:
    """Stock Module Editor LYT/VIS inspection exposes room layout and visibility facts."""

    _configure_native_python_roots()

    from src.core.modules.module_format import LYTLayout, LYTDoorHook, LYTRoom, VISData
    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_layout import (
        create_layout_edit_draft,
        inspect_module_layout,
        write_layout_patch_export_copy,
    )

    lyt = LYTLayout(
        rooms=[
            LYTRoom("koq200_01a", 0.0, 0.0, 0.0),
            LYTRoom("koq200_01b", 10.0, 0.0, 0.0),
            LYTRoom("valsky", 0.0, 0.0, 20.0),
        ],
        doorhooks=[LYTDoorHook("door_exit", 1.0, 2.0, 3.0, 0.0, 0.0, 0.707, 0.707)],
    )
    vis = VISData(
        visibility={
            "koq200_01a": ["koq200_01b", "valsky"],
            "koq200_01b": ["koq200_01a", "missing_room"],
        }
    )
    module_path = tmp_path / "layout.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200", "lyt", lyt.to_text().encode("latin-1"), source="fixture"),
                ModuleArchiveEntry("koq200", "vis", vis.to_text().encode("latin-1"), source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    resources = {item.label: item for item in read_module_archive_resources(module_path)}

    layout_inventory = inspect_module_layout(module_path, list(resources.values()), resources["koq200.lyt"])
    visibility_inventory = inspect_module_layout(module_path, list(resources.values()), resources["koq200.vis"])

    assert layout_inventory.ok is True
    assert layout_inventory.editable_scope == "room_layout"
    assert layout_inventory.room_count == 3
    assert len(layout_inventory.doorhooks) == 1
    assert layout_inventory.rooms[1].room_resref == "koq200_01b"
    assert layout_inventory.rooms[1].position == (10.0, 0.0, 0.0)
    assert layout_inventory.doorhooks[0].rotation == (0.0, 0.0, 0.707, 0.707)

    assert visibility_inventory.ok is True
    assert visibility_inventory.editable_scope == "room_visibility"
    assert visibility_inventory.visibility_entry_count == 2
    assert visibility_inventory.visibility_link_count == 4
    assert visibility_inventory.missing_visibility_targets == ("missing_room",)
    assert visibility_inventory.unlisted_layout_rooms == ("valsky",)
    assert "not listed in the matching layout" in visibility_inventory.warning

    room_draft = create_layout_edit_draft(
        module_path,
        list(resources.values()),
        resources["koq200.lyt"],
        target_key="koq200_01b",
        field_key="x",
        value="12.5",
    )
    assert room_draft.ready is True
    assert room_draft.old_value == "10"
    assert room_draft.new_value == "12.5"
    layout_output_path = tmp_path / "layout_lyt_patch.mod"
    layout_result = write_layout_patch_export_copy(module_path, layout_output_path, room_draft)
    assert layout_result.ok is True
    layout_manifest = json.loads(Path(layout_result.manifest_path).read_text(encoding="utf-8"))
    assert layout_manifest["schema"] == "ghostrigger.stock_module_layout_patch_plan.v1"
    assert layout_manifest["patched_resources"] == ["koq200.lyt"]
    assert layout_manifest["draft"]["edit_kind"] == "room"
    patched_layout_resources = {item.label: item for item in read_module_archive_resources(layout_output_path)}
    patched_layout = inspect_module_layout(layout_output_path, list(patched_layout_resources.values()), patched_layout_resources["koq200.lyt"])
    assert patched_layout.rooms[1].position == (12.5, 0.0, 0.0)

    visibility_draft = create_layout_edit_draft(
        module_path,
        list(resources.values()),
        resources["koq200.vis"],
        target_key="koq200_01b",
        field_key="valsky",
        value="true",
    )
    assert visibility_draft.ready is True
    assert visibility_draft.old_value == "False"
    assert visibility_draft.new_value == "True"
    vis_output_path = tmp_path / "layout_vis_patch.mod"
    vis_result = write_layout_patch_export_copy(module_path, vis_output_path, visibility_draft)
    assert vis_result.ok is True
    vis_manifest = json.loads(Path(vis_result.manifest_path).read_text(encoding="utf-8"))
    assert vis_manifest["patched_resources"] == ["koq200.vis"]
    assert vis_manifest["draft"]["edit_kind"] == "visibility"
    patched_vis_resources = {item.label: item for item in read_module_archive_resources(vis_output_path)}
    patched_visibility = inspect_module_layout(vis_output_path, list(patched_vis_resources.values()), patched_vis_resources["koq200.vis"])
    patched_links = {row.room_resref: row.visible_rooms for row in patched_visibility.visibility}
    assert "valsky" in patched_links["koq200_01b"]

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(module_path)
        window.content_type_combo.setCurrentText("Rooms")
        window.content_search.setText("koq200.lyt")
        window._populate_content_browser()
        layout_item = window.content_browser.item(0)
        assert layout_item is not None
        window.content_browser.setCurrentItem(layout_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["LYT parse"] == "ok"
        assert detail_rows["Layout workflow"] == "room placement and visibility graph editing target"
        assert detail_rows["Editable scope"] == "room_layout"
        assert detail_rows["Rooms"] == "3"
        assert detail_rows["Doorhooks"] == "1"
        assert detail_rows["Room koq200_01b"] == "10.00, 0.00, 0.00"
        assert layout_item.data(QtCore.Qt.UserRole).label == "koq200.lyt"
        assert window.layout_target_combo.isEnabled() is True
        assert window.layout_field_combo.isEnabled() is True
        assert window.layout_value_edit.isEnabled() is True
        assert window.layout_visible_toggle.isEnabled() is False
        room_row = -1
        for row_index in range(window.details.rowCount()):
            if window.details.item(row_index, 0).text() == "Room koq200_01b":
                room_row = row_index
                break
        assert room_row >= 0
        assert "edit LYT room koq200_01b" in window.details.item(room_row, 0).toolTip()
        window.details.selectRow(room_row)
        window._sync_selection_from_details()
        assert window.layout_target_combo.currentData() == "koq200_01b"
        assert window.layout_field_combo.currentData() == "x"
        window.layout_value_edit.setText("12.5")
        window._preview_layout_edit()
        assert window._pending_layout_edit is not None
        assert window._pending_layout_edit.ready is True
        assert window.save_copy_action.isEnabled() is True
        edit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert edit_rows["Pending layout edit"] == "koq200.lyt room koq200_01b.X: 10 -> 12.5"
        assert edit_rows["Export state"] == "ready for copied module export"

        window.content_search.setText("koq200.vis")
        window._populate_content_browser()
        vis_item = window.content_browser.item(0)
        assert vis_item is not None
        window.content_browser.setCurrentItem(vis_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["VIS parse"] == "ok"
        assert detail_rows["Editable scope"] == "room_visibility"
        assert detail_rows["VIS rooms"] == "2"
        assert detail_rows["Visibility links"] == "4"
        assert detail_rows["Missing visibility targets"] == "missing_room"
        assert detail_rows["Layout rooms missing VIS"] == "valsky"
        assert vis_item.data(QtCore.Qt.UserRole).label == "koq200.vis"
        assert window.layout_target_combo.isEnabled() is True
        assert window.layout_field_combo.isEnabled() is True
        assert window.layout_value_edit.isEnabled() is False
        assert window.layout_visible_toggle.isEnabled() is True
        vis_row = -1
        for row_index in range(window.details.rowCount()):
            if window.details.item(row_index, 0).text() == "Visible from koq200_01b":
                vis_row = row_index
                break
        assert vis_row >= 0
        assert "edit VIS links from koq200_01b" in window.details.item(vis_row, 0).toolTip()
        window.details.selectRow(vis_row)
        window._sync_selection_from_details()
        assert window.layout_target_combo.currentData() == "koq200_01b"
        for index in range(window.layout_field_combo.count()):
            if window.layout_field_combo.itemData(index) == "valsky":
                window.layout_field_combo.setCurrentIndex(index)
                break
        assert window.layout_visible_toggle.isChecked() is False
        window.layout_visible_toggle.setChecked(True)
        window._preview_layout_edit()
        assert window._pending_layout_edit is not None
        assert window._pending_layout_edit.ready is True
        vis_edit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert vis_edit_rows["Pending layout edit"] == "koq200.vis visibility koq200_01b.valsky: False -> True"
        assert vis_edit_rows["Export state"] == "ready for copied module export"
    finally:
        window.close()


def test_stock_module_git_inventory_lists_runtime_objects(tmp_path: Path) -> None:
    """Stock Module Editor GIT inspection exposes placed object forms without editing bytes."""

    _configure_native_python_roots()

    from src.core.modules.authored_module_objects import (
        AuthoredCreatureInstance,
        AuthoredDoorInstance,
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        AuthoredSoundInstance,
        AuthoredStoreInstance,
        AuthoredTriggerInstance,
        AuthoredWaypointInstance,
        ModuleEntryPoint,
        build_git_bytes,
    )
    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_git import (
        create_git_object_edit_draft,
        inspect_module_git,
        write_git_object_patch_export_copy,
    )

    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="koq200"),
        creatures=(AuthoredCreatureInstance(template_resref="g_snowtroop", tag="SnowTrooper", position=(1.0, 2.0, 0.0)),),
        doors=(
            AuthoredDoorInstance(
                template_resref="door_snow",
                tag="CanyonDoor",
                position=(2.0, 3.0, 0.0),
                linked_to="wp_exit",
                linked_to_module="koq201",
                linked_to_flags=2,
                transition_destination=1,
            ),
        ),
        triggers=(AuthoredTriggerInstance(template_resref="tr_snow", tag="ExitTrigger", position=(0.0, 1.0, 0.0)),),
        sounds=(AuthoredSoundInstance(template_resref="snd_wind", tag="WindLoop", position=(0.0, 4.0, 0.0)),),
        stores=(AuthoredStoreInstance(template_resref="st_snow", tag="SnowMerchant"),),
        placeables=(AuthoredPlaceableInstance(template_resref="plc_crate", tag="SupplyCrate", position=(1.5, 1.5, 0.0)),),
        waypoints=(AuthoredWaypointInstance(template_resref="wp_snow", tag="wp_exit", position=(3.0, 3.0, 0.0)),),
    )
    module_path = tmp_path / "objects.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200", "git", build_git_bytes(placement), source="fixture"),
                ModuleArchiveEntry(
                    "g_snowtroop",
                    "utc",
                    _template_gff(
                        "UTC ",
                        {
                            "TemplateResRef": ("resref", "g_snowtroop"),
                            "Tag": ("string", "SnowTrooper"),
                            "FirstName": ("locstring", "Snow Trooper"),
                        },
                    ),
                    source="fixture",
                ),
            ],
            archive_type="MOD",
        )
    )
    resource = read_module_archive_resources(module_path)[0]

    inventory = inspect_module_git(module_path, resource)

    assert inventory.ok is True
    assert inventory.editable_scope == "git_object_forms"
    counts = {item.object_type: item.count for item in inventory.counts}
    assert counts["creature"] == 1
    assert counts["door"] == 1
    assert counts["placeable"] == 1
    assert counts["trigger"] == 1
    assert counts["sound"] == 1
    assert counts["store"] == 1
    assert counts["waypoint"] == 1
    assert counts["transition"] >= 1
    rows = {(item.object_type, item.template_resref): item for item in inventory.objects}
    assert rows[("creature", "g_snowtroop")].position == (1.0, 2.0, 0.0)
    assert rows[("placeable", "plc_crate")].tag == "SupplyCrate"
    assert rows[("store", "st_snow")].tag == "SnowMerchant"
    creature_row = rows[("creature", "g_snowtroop")]
    creature_fields = {field.key: field for field in creature_row.editable_fields}
    assert creature_fields["TemplateResRef"].value == "g_snowtroop"
    assert creature_fields["XPosition"].value == "1.0"
    assert creature_fields["YPosition"].value == "2.0"
    draft = create_git_object_edit_draft(
        module_path,
        resource,
        object_type=creature_row.object_type,
        index=creature_row.index,
        field_key="TemplateResRef",
        value="g_snowelite",
    )
    assert draft.ready is True
    assert draft.old_value == "g_snowtroop"
    assert draft.new_value == "g_snowelite"
    output_path = tmp_path / "objects_git_patch.mod"
    result = write_git_object_patch_export_copy(module_path, output_path, draft)
    assert result.ok is True
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == "ghostrigger.stock_module_git_object_patch_plan.v1"
    assert manifest["patched_resources"] == ["koq200.git"]
    assert manifest["draft"]["object_type"] == "creature"
    assert manifest["draft"]["field_key"] == "TemplateResRef"
    assert manifest["draft"]["old_value"] == "g_snowtroop"
    assert manifest["draft"]["new_value"] == "g_snowelite"
    patched_resource = read_module_archive_resources(output_path)[0]
    patched_inventory = inspect_module_git(output_path, patched_resource)
    patched_rows = {(item.object_type, item.template_resref): item for item in patched_inventory.objects}
    assert ("creature", "g_snowelite") in patched_rows
    position_draft = create_git_object_edit_draft(
        module_path,
        resource,
        object_type=creature_row.object_type,
        index=creature_row.index,
        field_key="XPosition",
        value="5.5",
    )
    assert position_draft.ready is True
    assert position_draft.old_value == "1.0"
    assert position_draft.new_value == "5.5"
    position_output_path = tmp_path / "objects_git_position_patch.mod"
    position_result = write_git_object_patch_export_copy(module_path, position_output_path, position_draft)
    assert position_result.ok is True
    position_resource = read_module_archive_resources(position_output_path)[0]
    position_inventory = inspect_module_git(position_output_path, position_resource)
    position_rows = {(item.object_type, item.template_resref): item for item in position_inventory.objects}
    assert position_rows[("creature", "g_snowtroop")].position == (5.5, 2.0, 0.0)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(module_path)
        window.content_type_combo.setCurrentText("Module")
        window.content_search.setText("koq200")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        window.content_browser.setCurrentItem(item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["GIT parse"] == "ok"
        assert detail_rows["Placed object forms"] == str(inventory.total_objects)
        assert detail_rows["Creature count"] == "1 utc"
        assert detail_rows["Placeable count"] == "1 utp"
        assert detail_rows["Store count"] == "1 utm"
        assert item.data(QtCore.Qt.UserRole).label == "koq200.git"
        assert window.git_object_combo.isEnabled() is True
        assert window.git_field_combo.isEnabled() is True
        assert window.git_value_edit.isEnabled() is True
        assert window.git_preview_button.isEnabled() is True
        assert window.git_open_template_button.isEnabled() is True
        for index in range(window.git_object_combo.count()):
            row = window.git_object_combo.itemData(index)
            if row.object_type == "creature" and row.template_resref == "g_snowtroop":
                window.git_object_combo.setCurrentIndex(index)
                break
        window._open_git_object_template()
        selected_template_item = window.content_browser.currentItem()
        assert selected_template_item is not None
        assert selected_template_item.data(QtCore.Qt.UserRole).label == "g_snowtroop.utc"
        assert window._selected_template_resource is not None
        assert window._selected_template_resource.label == "g_snowtroop.utc"
        assert window.template_field_combo.isEnabled() is True
        window.content_type_combo.setCurrentText("Module")
        window.content_search.setText("koq200")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        window.content_browser.setCurrentItem(item)
        window._sync_selection_from_content_browser()
        assert window.git_open_template_button.isEnabled() is True
        for index in range(window.git_object_combo.count()):
            row = window.git_object_combo.itemData(index)
            if row.object_type == "creature" and row.template_resref == "g_snowtroop":
                window.git_object_combo.setCurrentIndex(index)
                break
        assert {
            window.git_field_combo.itemData(index)
            for index in range(window.git_field_combo.count())
        } >= {"TemplateResRef", "XPosition", "YPosition", "ZPosition"}
        for index in range(window.git_field_combo.count()):
            if window.git_field_combo.itemData(index) == "TemplateResRef":
                window.git_field_combo.setCurrentIndex(index)
                break
        window.git_value_edit.setText("g_snowelite")
        window._preview_git_object_edit()
        assert window._pending_git_object_edit is not None
        assert window._pending_git_object_edit.ready is True
        assert window.save_copy_action.isEnabled() is True
        edit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert edit_rows["Pending GIT object edit"] == "koq200.git creature.0.TemplateResRef: g_snowtroop -> g_snowelite"
        assert edit_rows["Export state"] == "ready for copied module export"
        for index in range(window.git_field_combo.count()):
            if window.git_field_combo.itemData(index) == "XPosition":
                window.git_field_combo.setCurrentIndex(index)
                break
        window.git_value_edit.setText("5.5")
        window._preview_git_object_edit()
        assert window._pending_git_object_edit is not None
        assert window._pending_git_object_edit.field_key == "XPosition"
        assert window._pending_git_object_edit.ready is True
        position_edit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert position_edit_rows["Pending GIT object edit"] == "koq200.git creature.0.XPosition: 1.0 -> 5.5"
    finally:
        window.close()


def test_stock_module_git_inventory_exposes_all_object_rows_with_filter(tmp_path: Path) -> None:
    """Large GIT lists stay complete and searchable in the placed-object editor."""

    _configure_native_python_roots()

    from src.core.modules.authored_module_objects import (
        AuthoredGameplayPlacement,
        AuthoredPlaceableInstance,
        ModuleEntryPoint,
        build_git_bytes,
    )
    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_git import inspect_module_git

    placement = AuthoredGameplayPlacement(
        entry_point=ModuleEntryPoint(area_resref="koq200"),
        placeables=tuple(
            AuthoredPlaceableInstance(
                template_resref=f"plc_crate{index:02d}",
                tag=f"SupplyCrate{index:02d}",
                position=(float(index), 2.0, 0.0),
            )
            for index in range(12)
        ),
    )
    module_path = tmp_path / "many_objects.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [ModuleArchiveEntry("koq200", "git", build_git_bytes(placement), source="fixture")],
            archive_type="MOD",
        )
    )
    resource = read_module_archive_resources(module_path)[0]

    inventory = inspect_module_git(module_path, resource)

    assert inventory.ok is True
    assert inventory.total_objects == 12
    assert len(inventory.objects) == 12
    rows = {(item.object_type, item.index): item for item in inventory.objects}
    assert rows[("placeable", 11)].template_resref == "plc_crate11"

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(module_path)
        window.content_type_combo.setCurrentText("Module")
        window.content_search.setText("koq200")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        window.content_browser.setCurrentItem(item)
        window._sync_selection_from_content_browser()

        assert window.git_object_combo.count() == 12
        window.git_object_filter_edit.setText("crate09")
        assert window.git_object_combo.count() == 1
        filtered_row = window.git_object_combo.currentData()
        assert filtered_row.template_resref == "plc_crate09"
        assert filtered_row.tag == "SupplyCrate09"
        details_row = -1
        for row_index in range(window.details.rowCount()):
            if window.details.item(row_index, 0).text() == "placeable.11":
                details_row = row_index
                break
        assert details_row >= 0
        assert "edit placeable.11" in window.details.item(details_row, 0).toolTip()
        window.details.selectRow(details_row)
        window._sync_selection_from_details()
        selected_row = window.git_object_combo.currentData()
        assert selected_row.template_resref == "plc_crate11"
        assert selected_row.index == 11
        assert window.git_object_filter_edit.text() == ""
        assert window.git_object_combo.count() == 12
        window.git_object_filter_edit.clear()
        assert window.git_object_combo.count() == 12
    finally:
        window.close()


def test_stock_module_metadata_inventory_summarizes_are_ifo_runtime(tmp_path: Path) -> None:
    """Stock Module Editor ARE/IFO inspection exposes module metadata editing targets."""

    _configure_native_python_roots()

    from src.core.modules.authored_module_metadata import (
        AuthoredAreaMetadata,
        AuthoredModuleTimeMetadata,
        compile_authored_module_metadata,
    )
    from src.core.modules.authored_module_objects import ModuleEntryPoint
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_metadata import (
        create_metadata_field_edit_draft,
        inspect_module_metadata,
        write_metadata_field_patch_export_copy,
    )

    compiled = compile_authored_module_metadata(
        AuthoredModuleMetadata(
            module_root="koq200",
            display_name="Rhen Var Canyon",
            tag="koq200",
        ),
        ModuleEntryPoint(area_resref="koq200", position=(3.0, -4.0, 1.5), facing=0.0),
        area=AuthoredAreaMetadata(name="Rhen Var Canyon", tag="koq200", sun_fog_on=True),
        time=AuthoredModuleTimeMetadata(dawn_hour=8, dusk_hour=18, minutes_per_hour=4),
    )
    module_path = tmp_path / "metadata.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200", "are", compiled.are_bytes, source="fixture"),
                ModuleArchiveEntry("module", "ifo", compiled.ifo_bytes, source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    resources = {item.label: item for item in read_module_archive_resources(module_path)}

    area_inventory = inspect_module_metadata(module_path, resources["koq200.are"])
    module_inventory = inspect_module_metadata(module_path, resources["module.ifo"])

    assert area_inventory.ok is True
    assert area_inventory.editable_scope == "area_metadata"
    area_fields = {field.label: field.value for field in area_inventory.fields}
    assert area_fields["Area name"] == "Rhen Var Canyon"
    assert area_fields["Area tag"] == "koq200"
    assert "Raw GFF fields" in area_fields
    area_editable = {field.key: field for field in area_inventory.fields if field.editable}
    assert area_editable["Name"].value == "Rhen Var Canyon"
    assert area_editable["SunFogNear"].value == "99.0"

    assert module_inventory.ok is True
    assert module_inventory.editable_scope == "module_metadata"
    module_fields = {field.label: field.value for field in module_inventory.fields}
    assert module_fields["Module name"] == "Rhen Var Canyon"
    assert module_fields["Entry area"] == "koq200"
    assert module_fields["Entry position"] == "3.00, -4.00, 1.50"
    assert module_fields["Dawn hour"] == "8"
    assert module_fields["Dusk hour"] == "18"
    module_editable = {field.key: field for field in module_inventory.fields if field.editable}
    assert module_editable["Mod_Name"].value == "Rhen Var Canyon"
    assert module_editable["Mod_DawnHour"].value == "8"

    area_draft = create_metadata_field_edit_draft(
        module_path,
        resources["koq200.are"],
        field_key="SunFogNear",
        value="42.5",
    )
    assert area_draft.ready is True
    assert area_draft.old_value == "99.0"
    assert area_draft.new_value == "42.5"

    module_draft = create_metadata_field_edit_draft(
        module_path,
        resources["module.ifo"],
        field_key="Mod_Name",
        value="Rhen Var Canyon Elite",
    )
    assert module_draft.ready is True
    assert module_draft.old_value == "Rhen Var Canyon"
    assert module_draft.new_value == "Rhen Var Canyon Elite"
    output_path = tmp_path / "metadata_metadata_patch.mod"
    result = write_metadata_field_patch_export_copy(module_path, output_path, module_draft)
    assert result.ok is True
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == "ghostrigger.stock_module_metadata_patch_plan.v1"
    assert manifest["patched_resources"] == ["module.ifo"]
    assert manifest["draft"]["field_key"] == "Mod_Name"
    assert manifest["draft"]["old_value"] == "Rhen Var Canyon"
    assert manifest["draft"]["new_value"] == "Rhen Var Canyon Elite"
    patched_resources = {item.label: item for item in read_module_archive_resources(output_path)}
    patched_module = inspect_module_metadata(output_path, patched_resources["module.ifo"])
    patched_module_fields = {field.label: field.value for field in patched_module.fields}
    assert patched_module_fields["Module name"] == "Rhen Var Canyon Elite"

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(module_path)
        window.content_type_combo.setCurrentText("Module")
        window.content_search.setText("koq200.are")
        window._populate_content_browser()
        area_item = window.content_browser.item(0)
        assert area_item is not None
        window.content_browser.setCurrentItem(area_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["ARE parse"] == "ok"
        assert detail_rows["Metadata workflow"] == "area/module metadata inspection and override target"
        assert detail_rows["Editable scope"] == "area_metadata"
        assert detail_rows["Area name"] == "Rhen Var Canyon"
        assert area_item.data(QtCore.Qt.UserRole).label == "koq200.are"
        assert window.metadata_field_combo.isEnabled() is True
        assert window.metadata_value_edit.isEnabled() is True
        assert window.metadata_preview_button.isEnabled() is True
        assert {
            window.metadata_field_combo.itemData(index).key
            for index in range(window.metadata_field_combo.count())
        } >= {"Name", "SunFogNear"}

        window.content_search.setText("module.ifo")
        window._populate_content_browser()
        module_item = window.content_browser.item(0)
        assert module_item is not None
        window.content_browser.setCurrentItem(module_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["IFO parse"] == "ok"
        assert detail_rows["Editable scope"] == "module_metadata"
        assert detail_rows["Module name"] == "Rhen Var Canyon"
        assert detail_rows["Entry area"] == "koq200"
        assert detail_rows["Dawn hour"] == "8"
        assert module_item.data(QtCore.Qt.UserRole).label == "module.ifo"
        assert window.metadata_field_combo.isEnabled() is True
        assert {
            window.metadata_field_combo.itemData(index).key
            for index in range(window.metadata_field_combo.count())
        } >= {"Mod_Name", "Mod_Entry_Area", "Mod_DawnHour"}
        module_name_row = -1
        for row_index in range(window.details.rowCount()):
            if window.details.item(row_index, 0).text() == "Module name":
                module_name_row = row_index
                break
        assert module_name_row >= 0
        assert "edit metadata field Module name" in window.details.item(module_name_row, 0).toolTip()
        window.details.selectRow(module_name_row)
        window._sync_selection_from_details()
        assert window.metadata_field_combo.currentData().key == "Mod_Name"
        assert window.metadata_value_edit.text() == "Rhen Var Canyon"
        window.metadata_value_edit.setText("Rhen Var Canyon Elite")
        window._preview_metadata_field_edit()
        assert window._pending_metadata_field_edit is not None
        assert window._pending_metadata_field_edit.ready is True
        assert window.save_copy_action.isEnabled() is True
        edit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert edit_rows["Pending metadata edit"] == "module.ifo Mod_Name: Rhen Var Canyon -> Rhen Var Canyon Elite"
        assert edit_rows["Export state"] == "ready for copied module export"
    finally:
        window.close()


def test_stock_module_logic_inventory_summarizes_path_dialogue_and_scripts_runtime(tmp_path: Path) -> None:
    """Stock Module Editor inspects logic resources and safely patches DLG top-level fields."""

    _configure_native_python_roots()

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_export_queue import (
        summarize_queued_module_patch_preflight,
        write_queued_module_patch_export_copy,
    )
    from src.core.stock_modules.stock_module_logic import (
        create_logic_field_edit_draft,
        inspect_module_logic,
        write_logic_field_patch_export_copy,
    )

    nss_text = (
        "void main() {\n"
        "    ActionStartConversation(GetFirstPC(), \"snowtalk\");\n"
        "    ExecuteScript(\"missing_spawn\", OBJECT_SELF);\n"
        "}\n"
    )
    module_path = tmp_path / "logic.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry(
                    "snowtalk",
                    "dlg",
                    _template_gff(
                        "DLG ",
                        {
                            "EndConversation": ("resref", "snow_end"),
                            "EntryList": ("list", [{"Text": ("locstring", "Welcome to the canyon.")}]),
                            "ReplyList": ("list", [{"Text": ("locstring", "I need supplies.")}]),
                            "StartingList": ("list", [{"Index": ("uint32", 0)}]),
                        },
                    ),
                    source="fixture",
                ),
                ModuleArchiveEntry("snowspawn", "nss", nss_text.encode("latin-1"), source="fixture"),
                ModuleArchiveEntry("snowspawn", "ncs", b"NCS V1.0\x00\x01\x02\x03", source="fixture"),
                ModuleArchiveEntry("koq200", "pth", b"\x00\x01PTH\x00\xff\x10\x00", source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    resources = {item.label: item for item in read_module_archive_resources(module_path)}

    archive_resources = list(resources.values())
    dialogue = inspect_module_logic(module_path, resources["snowtalk.dlg"], archive_resources)
    source_script = inspect_module_logic(module_path, resources["snowspawn.nss"], archive_resources)
    compiled_script = inspect_module_logic(module_path, resources["snowspawn.ncs"], archive_resources)
    path_data = inspect_module_logic(module_path, resources["koq200.pth"], archive_resources)

    assert dialogue.ok is True
    assert dialogue.parse_status == "ok"
    assert dialogue.resource_kind == "Dialogue tree"
    assert dialogue.editable_scope == "dlg_top_level_fields"
    assert {item.label: item.count for item in dialogue.list_summaries}["Entry List"] == 1
    assert {item.label: item.count for item in dialogue.list_summaries}["Reply List"] == 1
    dialogue_fields = {field.label: field.value for field in dialogue.fields}
    assert dialogue_fields["End Conversation"] == "snow_end"
    dialogue_editable = {field.key: field.editable for field in dialogue.fields}
    assert dialogue_editable["EndConversation"] is True
    assert dialogue.missing_reference_count == 1
    assert {reference.resref: reference.status for reference in dialogue.references}["snow_end"] == "missing"

    logic_draft = create_logic_field_edit_draft(
        module_path,
        resources["snowtalk.dlg"],
        field_key="EndConversation",
        value="snowtalk",
    )
    assert logic_draft.ready is True
    assert logic_draft.summary == "snowtalk.dlg EndConversation: snow_end -> snowtalk"
    patched_path = tmp_path / "logic_dlg_patch.mod"
    patch_result = write_logic_field_patch_export_copy(module_path, patched_path, logic_draft)
    assert patch_result.ok is True
    manifest = json.loads(Path(patch_result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == "ghostrigger.stock_module_logic_patch_plan.v1"
    assert manifest["patched_resources"] == ["snowtalk.dlg"]
    patched_resources = {item.label: item for item in read_module_archive_resources(patched_path)}
    patched_dialogue = inspect_module_logic(patched_path, patched_resources["snowtalk.dlg"], list(patched_resources.values()))
    assert {field.label: field.value for field in patched_dialogue.fields}["End Conversation"] == "snowtalk"
    assert patched_dialogue.missing_reference_count == 0

    queued_path = tmp_path / "logic_dlg_queued_patch.mod"
    queued_result = write_queued_module_patch_export_copy(module_path, queued_path, (logic_draft,))
    assert queued_result.ok is True
    queued_manifest = json.loads(Path(queued_result.manifest_path).read_text(encoding="utf-8"))
    assert queued_manifest["edits"][0]["kind"] == "logic"
    assert queued_manifest["patched_resources"] == ["snowtalk.dlg"]

    assert source_script.parse_status == "text"
    assert source_script.line_count == 4
    assert "ActionStartConversation" in source_script.text_preview
    assert source_script.editable_scope == "script_source_list_only"
    script_refs = {reference.resref: reference.status for reference in source_script.references}
    assert script_refs["snowtalk"] == "resolved"
    assert script_refs["missing_spawn"] == "missing"
    assert source_script.missing_reference_count == 1

    assert compiled_script.parse_status == "compiled_binary"
    assert compiled_script.editable_scope == "compiled_script_list_only"
    assert {field.label: field.value for field in compiled_script.fields}["Signature"] == "NCS "
    assert {reference.label: reference.status for reference in compiled_script.references}["matching source: snowspawn (nss)"] == "resolved"

    assert path_data.parse_status == "binary_list_only"
    assert path_data.resource_kind == "Path data"
    assert path_data.editable_scope == "pth_list_only"

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(module_path)
        window.content_type_combo.setCurrentText("Logic")
        window.content_search.setText("snowtalk")
        window._populate_content_browser()
        dlg_item = window.content_browser.item(0)
        assert dlg_item is not None
        window.content_browser.setCurrentItem(dlg_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["DLG parse"] == "ok"
        assert detail_rows["Logic workflow"] == "path/dialogue/script inspection, DLG top-level edits, dependency checks, and list-preserving export target"
        assert detail_rows["Editable scope"] == "dlg_top_level_fields"
        assert detail_rows["Resource kind"] == "Dialogue tree"
        assert detail_rows["Entry List list"] == "1"
        assert detail_rows["References"] == "1"
        assert detail_rows["Missing references"] == "1"
        assert detail_rows["Reference missing"] == "EndConversation: snow_end (dlg)"
        assert dlg_item.data(QtCore.Qt.UserRole).label == "snowtalk.dlg"
        assert window.logic_field_combo.isEnabled() is True
        end_conversation_row = -1
        for row_index in range(window.details.rowCount()):
            if window.details.item(row_index, 0).text() == "End Conversation":
                end_conversation_row = row_index
                break
        assert end_conversation_row >= 0
        assert "edit logic field End Conversation" in window.details.item(end_conversation_row, 0).toolTip()
        window.details.selectRow(end_conversation_row)
        window._sync_selection_from_details()
        assert window.logic_field_combo.currentData().key == "EndConversation"
        assert window.logic_value_edit.text() == "snow_end"
        window.logic_value_edit.setText("snowtalk")
        window._preview_logic_field_edit()
        assert window.stage_edit_action.isEnabled() is True
        assert window._pending_logic_field_edit is not None
        assert window._pending_logic_field_edit.ready is True
        edit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert edit_rows["Pending logic edit"] == "snowtalk.dlg EndConversation: snow_end -> snowtalk"
        assert edit_rows["Export state"] == "ready for copied module export"
        window._stage_current_edit()
        assert len(window._staged_edits) == 1
        assert "EndConversation" in window.edit_queue.item(0).text()

        window.content_search.setText("snowspawn.nss")
        window._populate_content_browser()
        nss_item = window.content_browser.item(0)
        assert nss_item is not None
        window.content_browser.setCurrentItem(nss_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["NSS parse"] == "text"
        assert detail_rows["Editable scope"] == "script_source_list_only"
        assert detail_rows["Lines"] == "4"
        assert detail_rows["References"] == "2"
        assert detail_rows["Missing references"] == "1"
        assert "ActionStartConversation" in detail_rows["Preview"]
        assert nss_item.data(QtCore.Qt.UserRole).label == "snowspawn.nss"

        window.content_search.setText("koq200.pth")
        window._populate_content_browser()
        pth_item = window.content_browser.item(0)
        assert pth_item is not None
        window.content_browser.setCurrentItem(pth_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["PTH parse"] == "binary_list_only"
        assert detail_rows["Resource kind"] == "Path data"
        assert detail_rows["Editable scope"] == "pth_list_only"
    finally:
        window.close()


def test_stock_module_template_inventory_summarizes_gameplay_forms_runtime(tmp_path: Path) -> None:
    """Stock Module Editor gameplay template inspection exposes form fields before editing."""

    _configure_native_python_roots()

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources
    from src.core.stock_modules.stock_module_templates import (
        create_template_field_edit_draft,
        inspect_module_template,
        write_template_field_patch_export_copy,
    )

    module_path = tmp_path / "templates.mod"
    module_path.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry(
                    "g_snowtroop",
                    "utc",
                    _template_gff(
                        "UTC ",
                        {
                            "TemplateResRef": ("resref", "g_snowtroop"),
                            "Tag": ("string", "SnowTrooper"),
                            "FirstName": ("locstring", "Snow Trooper"),
                            "Conversation": ("resref", "snow_talk"),
                            "ScriptSpawn": ("resref", "snow_spawn"),
                            "Appearance_Type": ("uint32", 51),
                            "ChallengeRating": ("float", 2.5),
                        },
                    ),
                    source="fixture",
                ),
                ModuleArchiveEntry(
                    "plc_crate",
                    "utp",
                    _template_gff(
                        "UTP ",
                        {
                            "TemplateResRef": ("resref", "plc_crate"),
                            "Tag": ("string", "SupplyCrate"),
                            "LocalizedName": ("locstring", "Supply Crate"),
                            "OnUsed": ("resref", "crate_used"),
                            "Static": ("uint32", 0),
                            "Useable": ("uint32", 1),
                        },
                    ),
                    source="fixture",
                ),
                ModuleArchiveEntry(
                    "st_snow",
                    "utm",
                    _template_gff(
                        "UTM ",
                        {
                            "TemplateResRef": ("resref", "st_snow"),
                            "Tag": ("string", "SnowMerchant"),
                            "StoreName": ("locstring", "Snow Merchant"),
                            "MarkUp": ("uint32", 125),
                            "MarkDown": ("uint32", 80),
                            "ItemList": ("list", [{"InventoryRes": ("resref", "g_w_blstrpstl001")}]),
                        },
                    ),
                    source="fixture",
                ),
                ModuleArchiveEntry(
                    "g_w_snow",
                    "uti",
                    _template_gff(
                        "UTI ",
                        {
                            "TemplateResRef": ("resref", "g_w_snow"),
                            "Tag": ("string", "SnowRifle"),
                            "LocalizedName": ("locstring", "Snow Rifle"),
                            "PaletteID": ("uint32", 42),
                        },
                    ),
                    source="fixture",
                ),
            ],
            archive_type="MOD",
        )
    )
    resources = {item.label: item for item in read_module_archive_resources(module_path)}

    creature = inspect_module_template(module_path, resources["g_snowtroop.utc"])
    placeable = inspect_module_template(module_path, resources["plc_crate.utp"])
    store = inspect_module_template(module_path, resources["st_snow.utm"])

    assert creature.ok is True
    assert creature.template_kind == "Creature/NPC"
    assert creature.editable_scope == "utc_template_form"
    creature_fields = {field.label: field.value for field in creature.fields}
    assert creature_fields["Template resref"] == "g_snowtroop"
    assert creature_fields["Tag"] == "SnowTrooper"
    assert creature_fields["First name"] == "Snow Trooper"
    assert creature_fields["Conversation"] == "snow_talk"
    assert creature_fields["On spawn"] == "snow_spawn"
    assert creature_fields["Challenge rating"] == "2.5"

    assert placeable.template_kind == "Placeable"
    placeable_fields = {field.label: field.value for field in placeable.fields}
    assert placeable_fields["Name"] == "Supply Crate"
    assert placeable_fields["On used"] == "crate_used"

    assert store.template_kind == "Store/Merchant"
    store_fields = {field.label: field.value for field in store.fields}
    assert store_fields["Store name"] == "Snow Merchant"
    assert {item.label: item.count for item in store.list_summaries}["Item List"] == 1
    store_editable = {field.key: field for field in store.fields if field.editable}
    assert store_editable["StoreName"].value == "Snow Merchant"
    assert store_editable["MarkUp"].value == "125"

    script_draft = create_template_field_edit_draft(
        module_path,
        resources["g_snowtroop.utc"],
        field_key="ScriptSpawn",
        value="elite_spawn",
    )
    assert script_draft.ready is True
    assert script_draft.old_value == "snow_spawn"
    assert script_draft.new_value == "elite_spawn"

    store_draft = create_template_field_edit_draft(
        module_path,
        resources["st_snow.utm"],
        field_key="StoreName",
        value="Snow Merchant Elite",
    )
    assert store_draft.ready is True
    assert store_draft.old_value == "Snow Merchant"
    assert store_draft.new_value == "Snow Merchant Elite"
    output_path = tmp_path / "templates_template_patch.mod"
    result = write_template_field_patch_export_copy(module_path, output_path, store_draft)
    assert result.ok is True
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == "ghostrigger.stock_module_template_patch_plan.v1"
    assert manifest["patched_resources"] == ["st_snow.utm"]
    assert manifest["draft"]["field_key"] == "StoreName"
    assert manifest["draft"]["old_value"] == "Snow Merchant"
    assert manifest["draft"]["new_value"] == "Snow Merchant Elite"
    patched_resources = {item.label: item for item in read_module_archive_resources(output_path)}
    patched_store = inspect_module_template(output_path, patched_resources["st_snow.utm"])
    patched_store_fields = {field.label: field.value for field in patched_store.fields}
    assert patched_store_fields["Store name"] == "Snow Merchant Elite"

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(module_path)
        window.content_type_combo.setCurrentText("Gameplay")
        window.content_search.setText("st_snow")
        window._populate_content_browser()
        store_item = window.content_browser.item(0)
        assert store_item is not None
        window.content_browser.setCurrentItem(store_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["UTM parse"] == "ok"
        assert detail_rows["Gameplay workflow"] == "template form inspection and override target"
        assert detail_rows["Editable scope"] == "utm_template_form"
        assert detail_rows["Template kind"] == "Store/Merchant"
        assert detail_rows["Store name"] == "Snow Merchant"
        assert detail_rows["Item List list"] == "1"
        assert store_item.data(QtCore.Qt.UserRole).label == "st_snow.utm"
        assert window.template_field_combo.isEnabled() is True
        assert window.template_value_edit.isEnabled() is True
        assert window.template_preview_button.isEnabled() is True
        assert {
            window.template_field_combo.itemData(index).key
            for index in range(window.template_field_combo.count())
        } >= {"TemplateResRef", "Tag", "StoreName", "MarkUp"}
        store_name_row = -1
        for row_index in range(window.details.rowCount()):
            if window.details.item(row_index, 0).text() == "Store name":
                store_name_row = row_index
                break
        assert store_name_row >= 0
        assert "edit template field Store name" in window.details.item(store_name_row, 0).toolTip()
        window.details.selectRow(store_name_row)
        window._sync_selection_from_details()
        assert window.template_field_combo.currentData().key == "StoreName"
        assert window.template_value_edit.text() == "Snow Merchant"
        window.template_value_edit.setText("Snow Merchant Elite")
        window._preview_template_field_edit()
        assert window._pending_template_field_edit is not None
        assert window._pending_template_field_edit.ready is True
        assert window.save_copy_action.isEnabled() is True
        edit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert edit_rows["Pending template edit"] == "st_snow.utm StoreName: Snow Merchant -> Snow Merchant Elite"
        assert edit_rows["Export state"] == "ready for copied module export"

        window.content_search.setText("g_snowtroop")
        window._populate_content_browser()
        creature_item = window.content_browser.item(0)
        assert creature_item is not None
        window.content_browser.setCurrentItem(creature_item)
        window._sync_selection_from_content_browser()
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["UTC parse"] == "ok"
        assert detail_rows["Template kind"] == "Creature/NPC"
        assert detail_rows["First name"] == "Snow Trooper"
        assert detail_rows["On spawn"] == "snow_spawn"
        assert creature_item.data(QtCore.Qt.UserRole).label == "g_snowtroop.utc"
    finally:
        window.close()


def test_stock_module_editor_queued_export_combines_texture_and_template_runtime(tmp_path: Path) -> None:
    """Queued Module Editor export combines staged texture and GFF edits into one copied module."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes
    from src.core.stock_modules.stock_module_export_queue import (
        summarize_queued_module_patch_preflight,
        write_queued_module_patch_export_copy,
    )
    from src.core.stock_modules.stock_module_materials import (
        ModuleRoomMaterialInventory,
        ModuleRoomTextureSlot,
        create_texture_replacement_draft,
    )
    from src.core.stock_modules.stock_module_mdl_patch import iter_mdl_texture_fields
    from src.core.stock_modules.stock_module_templates import (
        create_template_field_edit_draft,
        inspect_module_template,
    )
    from src.core.stock_modules.stock_module_textures import ModuleTextureFileResource
    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    source = tmp_path / "queued_source.mod"
    output = tmp_path / "queued_source_patch.mod"
    imported_tga = tmp_path / "snow_wall.tga"
    imported_tga.write_bytes(_tiny_tga_bytes())
    source.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200_01a", "mdl", _minimal_room_mdl("snow_target", "lko_wal02"), source="fixture"),
                ModuleArchiveEntry(
                    "st_snow",
                    "utm",
                    _template_gff(
                        "UTM ",
                        {
                            "TemplateResRef": ("resref", "st_snow"),
                            "Tag": ("string", "SnowMerchant"),
                            "StoreName": ("locstring", "Snow Merchant"),
                            "MarkUp": ("uint32", 125),
                        },
                    ),
                    source="fixture",
                ),
            ],
            archive_type="MOD",
        )
    )
    resources = {item.label: item for item in read_module_archive_resources(source)}
    slot = ModuleRoomTextureSlot(
        room_resref="koq200_01a",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )
    texture_resource = ModuleTextureFileResource(
        resref="snow_wall",
        restype="tga",
        restype_id=3,
        path=str(imported_tga),
        size=imported_tga.stat().st_size,
    )
    texture_draft = create_texture_replacement_draft(slot, texture_resource)
    template_draft = create_template_field_edit_draft(
        source,
        resources["st_snow.utm"],
        field_key="StoreName",
        value="Snow Merchant Elite",
    )
    assert texture_draft.status == "preview_only"
    assert template_draft.ready is True
    preflight = summarize_queued_module_patch_preflight(
        (texture_draft, template_draft),
        existing_resources=resources.values(),
    )
    assert preflight.ready is True
    assert preflight.source_summary == "source module preserved; copied export receives staged edits"
    assert preflight.patched_resources == ("koq200_01a.mdl", "st_snow.utm")
    assert preflight.bundled_resources == ("snow_wall.tga",)
    assert preflight.preserved_resources == ()
    assert preflight.preserve_summary == "(none)"
    assert preflight.summary == "2 edit(s); patches koq200_01a.mdl, st_snow.utm; bundles snow_wall.tga; source preserved"

    result = write_queued_module_patch_export_copy(source, output, (texture_draft, template_draft))

    assert result.ok is True
    assert result.edit_count == 2
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == "ghostrigger.stock_module_queued_patch_plan.v1"
    assert manifest["edit_count"] == 2
    assert manifest["patched_resources"] == ["koq200_01a.mdl", "st_snow.utm"]
    assert manifest["bundled_resources"] == ["snow_wall.tga"]
    assert manifest["preserved_resources"] == []
    assert {edit["kind"] for edit in manifest["edits"]} == {"texture", "template"}
    output_resources = {item.label: item for item in read_module_archive_resources(output)}
    patched_mdl = read_module_resource_bytes(output, output_resources["koq200_01a.mdl"])
    assert iter_mdl_texture_fields(patched_mdl)[0].texture_resref == "snow_wall"
    assert read_module_resource_bytes(output, output_resources["snow_wall.tga"]) == _tiny_tga_bytes()
    patched_template = inspect_module_template(output, output_resources["st_snow.utm"])
    assert {field.label: field.value for field in patched_template.fields}["Store name"] == "Snow Merchant Elite"

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(source)
        test_inventory = ModuleRoomMaterialInventory("koq200_01a", (slot,))
        window._material_inventory_cache["koq200_01a.mdl"] = test_inventory
        window._populate_material_picker(test_inventory)
        window._populate_material_pick_panel(test_inventory)
        window.material_pick_panel.setCurrentItem(window.material_pick_panel.item(0))
        window._sync_selection_from_material_pick_panel()
        imported_resource = window.import_texture(imported_tga)
        assert imported_resource.label == "snow_wall.tga"
        assert window.stage_edit_action.isEnabled() is True
        assert "lko_wal02 -> snow_wall [preview]" in window.material_picker.item(0).text()
        assert "lko_wal02 -> snow_wall" in window.material_pick_panel.item(0).text()
        preview_rows = {
            window.material_preview.item(row, 0).text(): window.material_preview.item(row, 1).text()
            for row in range(window.material_preview.rowCount())
        }
        assert preview_rows["Session preview texture"] == "snow_wall"
        assert preview_rows["Session preview state"] == "preview"
        window._stage_current_edit()
        assert len(window._staged_edits) == 1
        assert window.edit_queue.count() == 1
        assert "snow_target diffuse" in window.edit_queue.item(0).text()
        assert "lko_wal02 -> snow_wall [staged]" in window.material_picker.item(0).text()
        staged_preview_rows = {
            window.material_preview.item(row, 0).text(): window.material_preview.item(row, 1).text()
            for row in range(window.material_preview.rowCount())
        }
        assert staged_preview_rows["Session preview state"] == "staged"
        assert "1 edit(s)" in window.edit_queue_preflight_label.text()
        assert "koq200_01a.mdl" in window.edit_queue_preflight_label.text()
        assert "snow_wall.tga" in window.edit_queue_preflight_label.text()
        window.content_type_combo.setCurrentText("Rooms")
        window.content_search.setText("koq200_01a.mdl")
        window._populate_content_browser()
        room_item = window.content_browser.item(0)
        assert room_item is not None
        window.content_browser.setCurrentItem(room_item)
        window._sync_selection_from_content_browser()
        room_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert room_rows["Texture dependencies"] == "0 resolved, 1 missing"
        assert "source missing" in room_rows["Dependency lko_wal02"]
        assert "1/1 slot(s) use snow_wall (staged)" in room_rows["Dependency lko_wal02"]
        assert room_rows["Effective lko_wal02"] == "snow_wall from session snow_wall.tga"

        window.content_type_combo.setCurrentText("Gameplay")
        window.content_search.setText("st_snow")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        window.content_browser.setCurrentItem(item)
        window._sync_selection_from_content_browser()
        assert item.data(QtCore.Qt.UserRole).label == "st_snow.utm"
        for index in range(window.template_field_combo.count()):
            if window.template_field_combo.itemData(index).key == "StoreName":
                window.template_field_combo.setCurrentIndex(index)
                break
        window.template_value_edit.setText("Snow Merchant Elite")
        window._preview_template_field_edit()
        assert window.stage_edit_action.isEnabled() is True
        window._stage_current_edit()
        assert len(window._staged_edits) == 2
        assert window.edit_queue.count() == 2
        assert window.clear_staged_edits_action.isEnabled() is True
        assert window.save_copy_action.isEnabled() is True
        assert "Snow Merchant Elite" in window.edit_queue.item(1).text()
        assert "2 edit(s)" in window.edit_queue_preflight_label.text()
        assert "koq200_01a.mdl, st_snow.utm" in window.edit_queue_preflight_label.text()
        assert "bundles snow_wall.tga" in window.edit_queue_preflight_label.text()
        assert "source preserved" in window.edit_queue_preflight_label.text()
        assert "Patched resources: koq200_01a.mdl, st_snow.utm" in window.edit_queue.toolTip()
        assert "Preserved source resources: (none)" in window.edit_queue.toolTip()
    finally:
        window.close()


def test_stock_module_editor_stages_matching_texture_uses_runtime(tmp_path: Path) -> None:
    """A previewed texture replacement can stage every matching room material slot."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes
    from src.core.stock_modules.stock_module_export_queue import write_queued_module_patch_export_copy
    from src.core.stock_modules.stock_module_materials import ModuleRoomMaterialInventory, ModuleRoomTextureSlot
    from src.core.stock_modules.stock_module_mdl_patch import iter_mdl_texture_fields
    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    source = tmp_path / "batch_texture_source.mod"
    output = tmp_path / "batch_texture_patch.mod"
    imported_tga = tmp_path / "snow_wall.tga"
    imported_tga.write_bytes(_tiny_tga_bytes())
    source.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200_01a", "mdl", _minimal_room_mdl("snow_target", "lko_wal02"), source="fixture"),
                ModuleArchiveEntry("koq200_01b", "mdl", _minimal_room_mdl("snow_target", "lko_wal02"), source="fixture"),
                ModuleArchiveEntry("koq200_01c", "mdl", b"not a valid mdl payload", source="fixture"),
                ModuleArchiveEntry("lko_wal02", "tga", _tiny_tga_bytes(), source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    slot_a = ModuleRoomTextureSlot(
        room_resref="koq200_01a",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )
    slot_b = ModuleRoomTextureSlot(
        room_resref="koq200_01b",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )
    slot_c = ModuleRoomTextureSlot(
        room_resref="koq200_01c",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )
    room_b_extra_slots = tuple(
        ModuleRoomTextureSlot(
            room_resref="koq200_01b",
            node_name=f"mesh_{index:02d}",
            slot_kind="diffuse",
            texture_resref=f"lko_extra{index:02d}",
            face_count=index,
            vertex_count=index + 4,
        )
        for index in range(1, 14)
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(source)
        window._material_inventory_cache["koq200_01a.mdl"] = ModuleRoomMaterialInventory("koq200_01a", (slot_a,))
        window._material_inventory_cache["koq200_01b.mdl"] = ModuleRoomMaterialInventory("koq200_01b", room_b_extra_slots + (slot_b,))
        window._material_inventory_cache["koq200_01c.mdl"] = ModuleRoomMaterialInventory("koq200_01c", (slot_c,))
        window.content_type_combo.setCurrentText("Rooms")
        window.content_search.setText("koq200_01a.mdl")
        window._populate_content_browser()
        room_item = window.content_browser.item(0)
        assert room_item is not None
        window.content_browser.setCurrentItem(room_item)
        window._sync_selection_from_content_browser()
        room_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert room_rows["Texture lko_wal02"] == "1 diffuse slot(s); 4 faces, 8 verts"

        window._populate_material_picker(type("Inventory", (), {"slots": (slot_a,), "room_resref": "koq200_01a"})())
        window._populate_material_pick_panel(type("Inventory", (), {"slots": (slot_a,), "room_resref": "koq200_01a"})())
        window.material_pick_panel.setCurrentItem(window.material_pick_panel.item(0))
        window._sync_selection_from_material_pick_panel()
        window.content_type_combo.setCurrentText("Textures")
        window.content_search.setText("lko_wal02")
        window._populate_content_browser()
        source_texture_item = window.content_browser.item(0)
        assert source_texture_item is not None
        window.content_browser.setCurrentItem(source_texture_item)
        window._sync_selection_from_content_browser()
        assert source_texture_item.data(QtCore.Qt.UserRole).label == "lko_wal02.tga"
        usage_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert usage_rows["Material uses"] == "3 slot(s) reference lko_wal02"
        assert usage_rows["Used by koq200_01a.snow_target"] == "diffuse; 4 faces, 8 verts"
        usage_row_index = next(
            row
            for row in range(window.details.rowCount())
            if window.details.item(row, 0).text() == "Used by koq200_01b.snow_target"
        )
        assert "room material board" in window.details.item(usage_row_index, 0).toolTip()
        window.details.selectRow(usage_row_index)
        window._sync_selection_from_details()
        assert window._selected_material_slot == slot_b
        assert "13-14 of 14" in window.material_board_page_label.text()
        assert len(window._room_board_hit_slots) == 2

        imported_resource = window.import_texture(imported_tga)

        assert imported_resource.label == "snow_wall.tga"
        assert window._pending_texture_replacement is not None
        assert window.stage_matching_textures_action.isEnabled() is True
        detail_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert detail_rows["Matching texture uses"] == "3 diffuse slot(s) can be staged together"
        assert detail_rows["Patch preflight"] == "source module preserved; copied export receives changes"
        assert detail_rows["Patched resources"] == "koq200_01b.mdl"
        assert detail_rows["Bundled resources"] == "snow_wall.tga"

        window._stage_matching_texture_replacements()

        assert len(window._staged_edits) == 2
        assert window.edit_queue.count() == 2
        assert all("lko_wal02 -> snow_wall" in window.edit_queue.item(index).text() for index in range(2))
        assert "skipped 1 blocked target" in window.statusBar().currentMessage()
        staging_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert staging_rows["Matching texture staging"] == "2 staged, 1 blocked, 0 already staged"
        assert staging_rows["Patch validation"] == "partial"
        assert "koq200_01c.snow_target" in staging_rows["Blocked target 1"]

        result = write_queued_module_patch_export_copy(source, output, tuple(window._staged_edits))

        assert result.ok is True
        assert result.patched_resources == ("koq200_01a.mdl", "koq200_01b.mdl")
        assert result.bundled_resources == ("snow_wall.tga",)
        output_resources = {item.label: item for item in read_module_archive_resources(output)}
        assert read_module_resource_bytes(output, output_resources["snow_wall.tga"]) == _tiny_tga_bytes()
        assert iter_mdl_texture_fields(read_module_resource_bytes(output, output_resources["koq200_01a.mdl"]))[0].texture_resref == "snow_wall"
        assert iter_mdl_texture_fields(read_module_resource_bytes(output, output_resources["koq200_01b.mdl"]))[0].texture_resref == "snow_wall"
    finally:
        window.close()


def test_stock_module_editor_accepts_game_library_textures_runtime() -> None:
    """Game-library texture refs appear in the browser and can drive replacement drafts."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets

    from src.core.stock_modules.stock_module_materials import ModuleRoomMaterialInventory, ModuleRoomTextureSlot
    from src.core.stock_modules.stock_module_textures import ModuleTextureLibraryResource, ModuleTextureMemoryResource
    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    class FakeGameLibrary:
        def list_textures(
            self,
            game: str = "K2",
            *,
            include_modules: bool = True,
        ) -> list[tuple[str, str]]:
            assert game == "K2"
            assert include_modules is False
            return [("snow_wall", "K2")]

        def get_texture(self, resref: str, game: str = "K2") -> bytes:
            assert resref == "snow_wall"
            assert game == "K2"
            return _tiny_tga_bytes()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow(game_library=FakeGameLibrary())
    try:
        assert window._game_texture_resources == []
        window._load_game_library_textures()
        deadline = time.monotonic() + 2.0
        while window._game_texture_load_is_running() and time.monotonic() < deadline:
            app.processEvents()
        app.processEvents()
        assert window.content_browser.count() == 1
        assert "Search 1 installed texture" in window.content_browser.item(0).text()

        current_texture = ModuleTextureMemoryResource(
            resref="lko_wal02",
            restype="tga",
            restype_id=3,
            payload=_tiny_tga_bytes(),
            source_label="fixture current material texture",
        )
        window._imported_texture_resources.append(current_texture)
        assert any(isinstance(item, ModuleTextureLibraryResource) for item in window._game_texture_resources)
        window.content_type_combo.setCurrentText("Textures")
        window.content_search.setText("snow")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        resource = item.data(QtCore.Qt.UserRole)
        assert isinstance(resource, ModuleTextureLibraryResource)
        assert resource.label == "snow_wall.tpc"
        preview = window._texture_preview(resource, max_size=32)
        assert preview is not None
        assert preview.width == 2
        inventory = ModuleRoomMaterialInventory(
            "koq200_01a",
            tuple(
                [
                    ModuleRoomTextureSlot(
                        room_resref="koq200_01a",
                        node_name="mesh_a",
                        slot_kind="diffuse",
                        texture_resref="lko_wal02",
                        face_count=12,
                        vertex_count=18,
                    ),
                    ModuleRoomTextureSlot(
                        room_resref="koq200_01a",
                        node_name="mesh_b",
                        slot_kind="diffuse",
                        texture_resref="lko_floor01",
                        face_count=8,
                        vertex_count=12,
                    ),
                ]
                + [
                    ModuleRoomTextureSlot(
                        room_resref="koq200_01a",
                        node_name=f"mesh_{index:02d}",
                        slot_kind="diffuse",
                        texture_resref=f"lko_extra{index:02d}",
                        face_count=index,
                        vertex_count=index + 4,
                    )
                    for index in range(3, 15)
                ]
            ),
        )
        window._material_inventory_cache["koq200_01a.mdl"] = inventory
        window._populate_material_picker(inventory)
        window._populate_material_pick_panel(inventory)
        window._show_room_material_board(inventory)
        board_pixmap = window.preview_label.pixmap()
        assert board_pixmap is not None
        assert board_pixmap.isNull() is False
        assert "material slots" in window.preview_label.toolTip()
        assert len(window._room_board_hit_slots) == 12
        assert "1-12 of 14" in window.material_board_page_label.text()
        assert window.material_board_prev_button.isEnabled() is False
        assert window.material_board_next_button.isEnabled() is True
        window.material_filter_edit.setText("mesh_14")
        assert window.material_picker.count() == 1
        assert window.material_pick_panel.count() == 1
        assert len(window._room_board_hit_slots) == 1
        assert "1-1 of 1" in window.material_board_page_label.text()
        assert window._select_room_board_slot_at(window._room_board_hit_slots[0][0].center()) is True
        assert window._selected_material_slot is not None
        assert window._selected_material_slot.node_name == "mesh_14"
        window.material_filter_edit.clear()
        assert window.material_picker.count() == 14
        assert window.material_pick_panel.count() == 14
        assert "1-12 of 14" in window.material_board_page_label.text()
        window._next_room_board_page()
        assert len(window._room_board_hit_slots) == 2
        assert "13-14 of 14" in window.material_board_page_label.text()
        assert window.material_board_prev_button.isEnabled() is True
        assert window.material_board_next_button.isEnabled() is False
        assert window._select_room_board_slot_at(window._room_board_hit_slots[1][0].center()) is True
        assert window._selected_material_slot is not None
        assert window._selected_material_slot.node_name == "mesh_14"
        assert window.material_pick_panel.count() == 14
        assert window.material_picker.count() == 14
        pick_item = window.material_pick_panel.item(0)
        window.material_pick_panel.setCurrentItem(pick_item)
        window._sync_selection_from_material_pick_panel()
        assert window._selected_material_slot == pick_item.data(QtCore.Qt.UserRole)
        assert window.material_picker.currentItem().data(QtCore.Qt.UserRole) == window._selected_material_slot
        assert window.content_type_combo.currentText() == "Textures"
        assert window.content_search.text() == ""
        assert window._pending_texture_replacement is None
        assert window.content_browser.count() == 2
        assert window.content_browser.currentItem() is not None
        assert window.content_browser.currentItem().data(QtCore.Qt.UserRole) == current_texture
        assert "Current texture for koq200_01a.mesh_a diffuse" in window.content_browser.currentItem().toolTip()
        assert "leaves the replacement unchanged" in window.content_browser.currentItem().toolTip()
        assert "Choose a TGA/TPC texture to preview replacing koq200_01a.mesh_a diffuse" in window.content_browser.toolTip()
        window.content_browser.setCurrentItem(window.content_browser.currentItem())
        window._sync_selection_from_content_browser()
        assert window._pending_texture_replacement is None
        assert window.save_copy_action.isEnabled() is False
        assert "already assigned" in window.statusBar().currentMessage()
        picked_rows = {
            window.material_preview.item(row, 0).text(): window.material_preview.item(row, 1).text()
            for row in range(window.material_preview.rowCount())
        }
        assert picked_rows["Mesh node"] == "mesh_a"
        assert picked_rows["Current texture"] == "lko_wal02"
        assert picked_rows["Replacement"] == "choose a TGA/TPC texture"
        picked_board_pixmap = window.preview_label.pixmap()
        assert picked_board_pixmap is not None
        assert picked_board_pixmap.isNull() is False
        window.content_search.setText("snow")
        replacement_item = next(
            window.content_browser.item(index)
            for index in range(window.content_browser.count())
            if window.content_browser.item(index).data(QtCore.Qt.UserRole) == resource
        )
        assert replacement_item is not None
        assert replacement_item.data(QtCore.Qt.UserRole) == resource
        assert "Click to preview replacing koq200_01a.mesh_a diffuse" in replacement_item.toolTip()
        assert "lko_wal02 -> snow_wall" in replacement_item.toolTip()
        window.content_browser.setCurrentItem(replacement_item)
        window._sync_selection_from_content_browser()
        assert window._pending_texture_replacement is not None
        assert window._pending_texture_replacement.replacement_texture_resref == "snow_wall"
        assert window._pending_texture_replacement.replacement_payload == _tiny_tga_bytes()
        preview_rows = {
            window.material_preview.item(row, 0).text(): window.material_preview.item(row, 1).text()
            for row in range(window.material_preview.rowCount())
        }
        assert preview_rows["Room"] == "koq200_01a"
        assert preview_rows["Mesh node"] == "mesh_a"
        assert preview_rows["Current texture"] == "lko_wal02"
        assert preview_rows["Replacement"] == "snow_wall"
        assert preview_rows["Patch validation"] == "blocked"
        assert preview_rows["Export state"] == "blocked by validation"
        current_pixmap = window.current_texture_preview.pixmap()
        assert current_pixmap is not None
        assert current_pixmap.isNull() is False
        assert "lko_wal02.tga" in window.current_texture_preview.toolTip()
        replacement_board_pixmap = window.preview_label.pixmap()
        assert replacement_board_pixmap is not None
        assert replacement_board_pixmap.isNull() is False
        assert len(window._room_board_hit_slots) == 12
        assert "1-12 of 14" in window.material_board_page_label.text()
        assert "material slots" in window.preview_label.toolTip()
        replacement_pixmap = window.replacement_texture_preview.pixmap()
        assert replacement_pixmap is not None
        assert replacement_pixmap.isNull() is False
        assert "snow_wall.tpc" in window.replacement_texture_preview.toolTip()
        assert window.save_copy_action.isEnabled() is False

        invalid_texture = ModuleTextureMemoryResource(
            resref="snow_wall_texture_too_long",
            restype="tga",
            restype_id=3,
            payload=_tiny_tga_bytes(),
            source_label="fixture invalid material texture",
        )
        window._imported_texture_resources.append(invalid_texture)
        window._populate_content_browser()
        invalid_item = next(
            window.content_browser.item(index)
            for index in range(window.content_browser.count())
            if window.content_browser.item(index).data(QtCore.Qt.UserRole) == invalid_texture
        )
        window.content_browser.setCurrentItem(invalid_item)
        window._sync_selection_from_content_browser()
        assert window._pending_texture_replacement is None
        assert window.save_copy_action.isEnabled() is False
        assert "exceeds 16 characters" in window.statusBar().currentMessage()
        blocked_rows = {
            window.material_preview.item(row, 0).text(): window.material_preview.item(row, 1).text()
            for row in range(window.material_preview.rowCount())
        }
        assert blocked_rows["Current texture"] == "lko_wal02"
        assert blocked_rows["Replacement"] == "choose a TGA/TPC texture"
    finally:
        window.close()


def test_stock_module_editor_imported_texture_replacement_runtime(tmp_path: Path) -> None:
    """Local edited TGAs can be previewed, selected, and bundled into a copied module export."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes
    from src.core.stock_modules.stock_module_materials import ModuleRoomMaterialInventory, ModuleRoomTextureSlot
    from src.core.stock_modules.stock_module_mdl_patch import iter_mdl_texture_fields
    from src.core.stock_modules.stock_module_patch_plan import write_texture_patch_export_copy
    from src.core.stock_modules.stock_module_textures import ModuleTextureFileResource
    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    source = tmp_path / "source.mod"
    output = tmp_path / "source_texture_patch.mod"
    imported_tga = tmp_path / "snow_wall.tga"
    imported_txi = tmp_path / "snow_wall.txi"
    imported_tga.write_bytes(_tiny_tga_bytes())
    imported_txi.write_text("envmaptexture CM_Baremetal\nblending additive\n", encoding="ascii")
    source.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200_01a", "mdl", _minimal_room_mdl("snow_target", "lko_wal02"), source="fixture"),
                ModuleArchiveEntry("lko_wal02", "txi", b"proceduretype snow\n", source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    slot = ModuleRoomTextureSlot(
        room_resref="koq200_01a",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(source)
        inventory = ModuleRoomMaterialInventory("koq200_01a", (slot,))
        window._populate_material_picker(inventory)
        window._populate_material_pick_panel(inventory)
        window.material_pick_panel.setCurrentItem(window.material_pick_panel.item(0))
        window._sync_selection_from_material_pick_panel()

        resource = window.import_texture(imported_tga)

        assert isinstance(resource, ModuleTextureFileResource)
        assert resource.label == "snow_wall.tga"
        assert resource in window._imported_texture_resources
        assert window.content_type_combo.currentText() == "Textures"
        selected = window.content_browser.currentItem()
        assert selected is not None
        assert selected.data(QtCore.Qt.UserRole) == resource
        assert "imported texture:" in selected.toolTip()
        assert window._pending_texture_replacement is not None
        assert window._pending_texture_replacement.replacement_texture_resref == "snow_wall"
        assert window._pending_texture_replacement.replacement_payload == _tiny_tga_bytes()
        assert window._pending_texture_replacement.replacement_sidecars == ()

        txi_resource = window.import_texture(imported_txi)

        assert isinstance(txi_resource, ModuleTextureFileResource)
        assert txi_resource.label == "snow_wall.txi"
        assert window._pending_texture_replacement is not None
        assert [sidecar.label for sidecar in window._pending_texture_replacement.replacement_sidecars] == ["snow_wall.txi"]
        assert window._pending_texture_replacement.replacement_sidecars[0].payload == imported_txi.read_bytes()
        rows = {
            window.material_preview.item(row, 0).text(): window.material_preview.item(row, 1).text()
            for row in range(window.material_preview.rowCount())
        }
        assert rows["Current texture"] == "lko_wal02"
        assert rows["Current TXI"] == "lko_wal02.txi (module archive)"
        assert rows["Replacement"] == "snow_wall"
        assert rows["Replacement TXI"] == "snow_wall.txi (bundled sidecar)"
        assert rows["Replacement sidecars"] == "snow_wall.txi"
        assert rows["Patch preflight"] == "source module preserved; copied export receives changes"
        assert rows["Patched resources"] == "koq200_01a.mdl"
        assert rows["Bundled resources"] == "snow_wall.tga, snow_wall.txi"
        assert rows["Export state"] == "ready for copied module export"
        replacement_pixmap = window.replacement_texture_preview.pixmap()
        assert replacement_pixmap is not None
        assert replacement_pixmap.isNull() is False

        result = write_texture_patch_export_copy(source, output, (window._pending_texture_replacement,))

        assert result.ok is True
        manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
        assert manifest["bundled_resources"] == ["snow_wall.tga", "snow_wall.txi"]
        assert manifest["drafts"][0]["replacement_payload_bundled"] is True
        assert manifest["drafts"][0]["replacement_sidecars"][0]["resource"] == "snow_wall.txi"
        assert manifest["drafts"][0]["replacement_sidecars"][0]["payload_size"] == imported_txi.stat().st_size
        output_resources = read_module_archive_resources(output)
        labels = {item.label for item in output_resources}
        assert "snow_wall.tga" in labels
        assert "snow_wall.txi" in labels
        bundled = next(item for item in output_resources if item.label == "snow_wall.tga")
        assert read_module_resource_bytes(output, bundled) == _tiny_tga_bytes()
        bundled_txi = next(item for item in output_resources if item.label == "snow_wall.txi")
        assert read_module_resource_bytes(output, bundled_txi) == imported_txi.read_bytes()
        patched_mdl = read_module_resource_bytes(output, next(item for item in output_resources if item.label == "koq200_01a.mdl"))
        assert iter_mdl_texture_fields(patched_mdl)[0].texture_resref == "snow_wall"
    finally:
        window.close()


def test_stock_module_texture_patch_export_copy_rebuilds_archive_runtime(tmp_path: Path) -> None:
    """Texture export rebuilds a new archive with only the target MDL patched."""

    _configure_native_python_roots()

    import struct

    from src.core.stock_modules.stock_module_archive import (
        ModuleArchiveResource,
        read_module_archive_resources,
        read_module_resource_bytes,
    )
    from src.core.stock_modules.stock_module_materials import (
        ModuleRoomTextureSlot,
        create_texture_replacement_draft,
    )
    from src.core.stock_modules.stock_module_mdl_patch import iter_mdl_texture_fields
    from src.core.stock_modules.stock_module_patch_plan import (
        build_texture_patch_plan,
        summarize_texture_patch_preflight,
        write_texture_patch_export_copy,
    )
    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, RESTYPE_IDS, build_erf_v1_archive

    source = tmp_path / "source.mod"
    output = tmp_path / "source_texture_patch.mod"
    mdl_bytes = _minimal_room_mdl("snow_target", "lko_wal02")
    source.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200_01a", "mdl", mdl_bytes, source="fixture"),
                ModuleArchiveEntry("koq_dmblend", "tga", b"fake-tga", source="fixture"),
                ModuleArchiveEntry("koq_dmblend", "tpc", b"fake-tpc", source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    slot = ModuleRoomTextureSlot(
        room_resref="koq200_01a",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )
    draft = create_texture_replacement_draft(
        slot,
        ModuleArchiveResource(resref="snow_wall", restype_id=3, restype="tga", offset=0, size=128),
    )

    plan = build_texture_patch_plan(source, output, (draft,))
    assert plan.ready is True
    assert plan.archive_bytes_modified is True
    assert plan.patched_resources == ("koq200_01a.mdl",)
    assert plan.bundled_resources == ()
    preflight = summarize_texture_patch_preflight((draft,), existing_resources=read_module_archive_resources(source))
    assert preflight.source_preserved is True
    assert preflight.patch_summary == "koq200_01a.mdl"
    assert preflight.bundle_summary == "(none)"

    result = write_texture_patch_export_copy(source, output, (draft,))

    assert result.ok is True
    assert output.read_bytes() != source.read_bytes()
    assert result.patch_results[0].replacement_texture_resref == "snow_wall"
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["schema"] == "ghostrigger.stock_module_texture_patch_plan.v1"
    assert manifest["archive_bytes_modified"] is True
    assert manifest["patched_resources"] == ["koq200_01a.mdl"]
    assert manifest["drafts"][0]["replacement_texture_resref"] == "snow_wall"
    assert manifest["drafts"][0]["original_texture_resref"] == "lko_wal02"
    assert "MDL texture-reference fields patched" in manifest["note"]
    assert RESTYPE_IDS["tpc"] == 3007

    output_resources = read_module_archive_resources(output)
    output_mdl = next(item for item in output_resources if item.label == "koq200_01a.mdl")
    patched_mdl = read_module_resource_bytes(output, output_mdl)
    field = iter_mdl_texture_fields(patched_mdl)[0]
    assert field.node_name == "snow_target"
    assert field.texture_resref == "snow_wall"
    assert b"fake-tga" in [read_module_resource_bytes(output, item) for item in output_resources if item.label == "koq_dmblend.tga"]

    blocked = build_texture_patch_plan(source, source, (draft,))
    assert blocked.has_errors is True
    assert any(issue.code == "source_overwrite_refused" for issue in blocked.issues)

    missing_room_slot = ModuleRoomTextureSlot(
        room_resref="missing_room",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )
    missing_room_draft = create_texture_replacement_draft(
        missing_room_slot,
        ModuleArchiveResource(resref="snow_wall", restype_id=3, restype="tga", offset=0, size=128),
    )
    missing_room_plan = build_texture_patch_plan(source, output, (missing_room_draft,))
    assert missing_room_plan.ready is False
    assert any(issue.code == "target_room_missing" for issue in missing_room_plan.issues)


def test_stock_module_texture_patch_export_bundles_game_library_texture_runtime(tmp_path: Path) -> None:
    """Texture export can bundle a selected game-library texture into the rebuilt archive."""

    _configure_native_python_roots()

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes
    from src.core.stock_modules.stock_module_materials import (
        ModuleRoomTextureSlot,
        create_texture_replacement_draft,
    )
    from src.core.stock_modules.stock_module_mdl_patch import iter_mdl_texture_fields
    from src.core.stock_modules.stock_module_patch_plan import write_texture_patch_export_copy
    from src.core.stock_modules.stock_module_textures import ModuleTextureLibraryResource

    source = tmp_path / "source.mod"
    output = tmp_path / "source_texture_patch.mod"
    source.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200_01a", "mdl", _minimal_room_mdl("snow_target", "lko_wal02"), source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    slot = ModuleRoomTextureSlot(
        room_resref="koq200_01a",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )
    texture = ModuleTextureLibraryResource(
        resref="snow_wall",
        restype="tga",
        restype_id=3,
        source="game library",
        game="K2",
        data_loader=_tiny_tga_bytes,
    )
    draft = create_texture_replacement_draft(slot, texture)

    assert draft.replacement_payload == _tiny_tga_bytes()

    result = write_texture_patch_export_copy(source, output, (draft,))

    assert result.ok is True
    manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["patched_resources"] == ["koq200_01a.mdl"]
    assert manifest["bundled_resources"] == ["snow_wall.tga"]
    assert manifest["drafts"][0]["replacement_payload_bundled"] is True
    assert manifest["drafts"][0]["replacement_payload_size"] == len(_tiny_tga_bytes())
    output_resources = read_module_archive_resources(output)
    labels = {item.label for item in output_resources}
    assert "snow_wall.tga" in labels
    bundled = next(item for item in output_resources if item.label == "snow_wall.tga")
    assert read_module_resource_bytes(output, bundled) == _tiny_tga_bytes()
    patched_mdl = read_module_resource_bytes(output, next(item for item in output_resources if item.label == "koq200_01a.mdl"))
    assert iter_mdl_texture_fields(patched_mdl)[0].texture_resref == "snow_wall"


def _template_gff(file_type: str, fields: dict[str, tuple[str, object]]) -> bytes:
    from src.formats.gff_types import GffFieldType, GffFile, GffStruct, LocString, ResRef
    from src.formats.gff_writer import GffWriter

    def build_struct(values: dict[str, tuple[str, object]]) -> GffStruct:
        struct = GffStruct()
        for label, (kind, value) in values.items():
            if kind == "resref":
                struct.set(label, GffFieldType.RESREF, ResRef(str(value)))
            elif kind == "string":
                struct.set(label, GffFieldType.CEXOSTRING, str(value))
            elif kind == "locstring":
                loc = LocString()
                loc.english = str(value)
                struct.set(label, GffFieldType.CEXOLOCSTRING, loc)
            elif kind == "uint32":
                struct.set(label, GffFieldType.UINT32, int(value))
            elif kind == "float":
                struct.set(label, GffFieldType.FLOAT, float(value))
            elif kind == "list":
                items = [build_struct(dict(item)) for item in value]  # type: ignore[arg-type]
                struct.set(label, GffFieldType.LIST, items)
            else:
                raise AssertionError(f"Unsupported template GFF kind: {kind}")
        return struct

    return GffWriter(GffFile(file_type=file_type, root=build_struct(fields))).serialize()


def _minimal_room_mdl(node_name: str, texture: str) -> bytes:
    import struct

    base = 12
    data = bytearray(520)
    data[:8] = b"\x00" * 8
    struct.pack_into("<I", data, 8, 0)
    name_table_rel = 196
    name_string_rel = 200
    root_rel = 224
    root_abs = base + root_rel
    mesh_abs = root_abs + 80
    struct.pack_into("<I", data, base + 40, root_rel)
    struct.pack_into("<I", data, base + 80 + 104, name_table_rel)
    struct.pack_into("<I", data, base + 80 + 108, 1)
    struct.pack_into("<I", data, base + 80 + 112, 1)
    struct.pack_into("<I", data, base + name_table_rel, name_string_rel)
    data[base + name_string_rel:base + name_string_rel + len(node_name) + 1] = node_name.encode("ascii") + b"\x00"
    struct.pack_into("<H", data, root_abs, 32)
    struct.pack_into("<H", data, root_abs + 4, 0)
    data[mesh_abs + 88:mesh_abs + 120] = texture.encode("ascii").ljust(32, b"\x00")
    return bytes(data)


def _tiny_tga_bytes() -> bytes:
    header = bytes(
        [
            0,
            0,
            2,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            2,
            0,
            2,
            0,
            32,
            8,
        ]
    )
    pixels_bgra = bytes(
        [
            0,
            0,
            255,
            255,
            0,
            255,
            0,
            255,
            255,
            0,
            0,
            255,
            255,
            255,
            255,
            255,
        ]
    )
    return header + pixels_bgra


def test_stock_module_texture_preview_decodes_tga_bytes_runtime() -> None:
    """Module Editor thumbnails decode real TGA payloads into RGBA preview bytes."""

    _configure_native_python_roots()

    from src.core.stock_modules.stock_module_textures import decode_module_texture_preview

    preview = decode_module_texture_preview(
        _tiny_tga_bytes(),
        restype="tga",
        label="sample.tga",
    )

    assert preview is not None
    assert preview.label == "sample.tga"
    assert preview.source_format == "tga"
    assert (preview.width, preview.height) == (2, 2)
    assert (preview.preview_width, preview.preview_height) == (2, 2)
    assert len(preview.rgba) == 16


def test_stock_module_tga_editor_creates_session_replacement_runtime(tmp_path: Path) -> None:
    """Module Editor TGA edits stay in memory and can drive safe texture replacement export."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets

    from src.core.modules.module_save_pipeline import ModuleArchiveEntry, build_erf_v1_archive
    from src.core.stock_modules.stock_module_archive import read_module_archive_resources, read_module_resource_bytes
    from src.core.stock_modules.stock_module_materials import ModuleRoomTextureSlot
    from src.core.stock_modules.stock_module_mdl_patch import iter_mdl_texture_fields
    from src.core.stock_modules.stock_module_patch_plan import write_texture_patch_export_copy
    from src.core.stock_modules.stock_module_tga_editor import create_tga_adjustment_draft
    from src.core.stock_modules.stock_module_textures import decode_module_texture_preview
    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    core_draft = create_tga_adjustment_draft(
        _tiny_tga_bytes(),
        source_resref="lko_wal02",
        source_label="lko_wal02.tga",
        output_resref="snow_wall",
        brightness=12,
        contrast=-8,
        snow=70,
    )
    assert core_draft.ready is True
    assert core_draft.output_payload != _tiny_tga_bytes()
    assert decode_module_texture_preview(core_draft.output_payload, restype="tga", label=core_draft.label) is not None

    source = tmp_path / "tga_editor_source.mod"
    output = tmp_path / "tga_editor_patch.mod"
    source.write_bytes(
        build_erf_v1_archive(
            [
                ModuleArchiveEntry("koq200_01a", "mdl", _minimal_room_mdl("snow_target", "lko_wal02"), source="fixture"),
                ModuleArchiveEntry("lko_wal02", "tga", _tiny_tga_bytes(), source="fixture"),
            ],
            archive_type="MOD",
        )
    )
    slot = ModuleRoomTextureSlot(
        room_resref="koq200_01a",
        node_name="snow_target",
        slot_kind="diffuse",
        texture_resref="lko_wal02",
        face_count=4,
        vertex_count=8,
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = StockModuleEditorWindow()
    try:
        window.open_module(source)
        window._populate_material_picker(type("Inventory", (), {"slots": (slot,), "room_resref": "koq200_01a"})())
        window._populate_material_pick_panel(type("Inventory", (), {"slots": (slot,), "room_resref": "koq200_01a"})())
        window.material_pick_panel.setCurrentItem(window.material_pick_panel.item(0))
        window._sync_selection_from_material_pick_panel()

        window.content_type_combo.setCurrentText("Textures")
        window.content_search.setText("lko_wal02")
        window._populate_content_browser()
        item = window.content_browser.item(0)
        assert item is not None
        window.content_browser.setCurrentItem(item)
        window._sync_selection_from_content_browser()
        assert item.data(QtCore.Qt.UserRole).label == "lko_wal02.tga"
        assert window.tga_preview_button.isEnabled() is True

        window.tga_output_resref_edit.setText("snow_wall")
        window.tga_brightness_spin.setValue(12)
        window.tga_contrast_spin.setValue(-8)
        window.tga_snow_spin.setValue(70)
        window._preview_tga_edit()

        assert window._pending_tga_edit is not None
        assert window._pending_tga_edit.ready is True
        assert window._pending_texture_replacement is not None
        assert window._pending_texture_replacement.replacement_texture_resref == "snow_wall"
        assert window._pending_texture_replacement.replacement_payload == window._pending_tga_edit.output_payload
        assert any(resource.label == "snow_wall.tga" for resource in window._imported_texture_resources)
        edit_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert edit_rows["Pending TGA edit"].startswith("lko_wal02.tga -> snow_wall.tga")
        assert edit_rows["Texture state"] == "available as session replacement texture"
        assert window.replacement_texture_preview.pixmap() is not None

        window.txi_output_resref_edit.setText("snow_wall")
        window.txi_text_edit.setPlainText("envmaptexture CM_Baremetal\nblending additive\n")
        window._preview_txi_edit()

        assert window._pending_txi_edit is not None
        assert window._pending_txi_edit.ready is True
        assert any(resource.label == "snow_wall.txi" for resource in window._imported_texture_resources)
        assert window._pending_texture_replacement is not None
        assert [sidecar.label for sidecar in window._pending_texture_replacement.replacement_sidecars] == ["snow_wall.txi"]
        assert window._pending_texture_replacement.replacement_sidecars[0].payload == b"envmaptexture CM_Baremetal\nblending additive\n"
        txi_rows = {
            window.details.item(row, 0).text(): window.details.item(row, 1).text()
            for row in range(window.details.rowCount())
        }
        assert txi_rows["Pending TXI sidecar"].startswith("lko_wal02.tga -> snow_wall.txi")
        assert txi_rows["Sidecar state"] == "available as session TXI sidecar"

        result = write_texture_patch_export_copy(source, output, (window._pending_texture_replacement,))

        assert result.ok is True
        manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
        assert manifest["bundled_resources"] == ["snow_wall.tga", "snow_wall.txi"]
        assert manifest["drafts"][0]["replacement_payload_bundled"] is True
        assert manifest["drafts"][0]["replacement_sidecars"][0]["resource"] == "snow_wall.txi"
        output_resources = read_module_archive_resources(output)
        bundled = next(item for item in output_resources if item.label == "snow_wall.tga")
        assert read_module_resource_bytes(output, bundled) == window._pending_tga_edit.output_payload
        bundled_txi = next(item for item in output_resources if item.label == "snow_wall.txi")
        assert read_module_resource_bytes(output, bundled_txi) == window._pending_txi_edit.output_payload
        patched_mdl = read_module_resource_bytes(output, next(item for item in output_resources if item.label == "koq200_01a.mdl"))
        assert iter_mdl_texture_fields(patched_mdl)[0].texture_resref == "snow_wall"
    finally:
        window.close()


def test_t2600_level_editor_window_is_branded_as_map_studio_without_new_surface() -> None:
    """Map Studio remains the existing Level Editor window and KMAP workflow."""

    window_source = _read(
        "native/GhostRigger.Core.Tools/Python/src/gui/windows/"
        "module_editor_window.py"
    )

    assert "class ModuleEditorWindow(QtWidgets.QMainWindow)" in window_source
    assert 'self.setWindowTitle("GhostRigger Map Studio - Level Editor")' in window_source
    assert "GhostRigger Map Studio - Level Editor - {self.project.name}" in window_source
    assert "Map Studio is GhostRigger's Level Editor opened from the Module Editor icon" in window_source
    assert "mapStudioLevelEditorScopeLabel" in window_source
    assert "KMAP terrain, rooms, walkmesh, placements, validation, staged export, install handoff, and game proof" in window_source
    assert "Map Studio Level Editor ready." in window_source
    assert "self.controller = ModuleEditorController()" in window_source
    assert "def focus_map_studio_modeling_workspace" in window_source
    assert "def select_map_studio_authored_context" in window_source
    assert "self.controller.set_map_studio_active_selection" in window_source
    assert "def move_map_studio_authored_primitive_selection" in window_source
    assert "self.controller.move_authored_room_primitive" in window_source
    assert "edit Move X/Y/Z, then click Move again" in window_source
    assert "def delete_map_studio_authored_primitive_selection" in window_source
    assert "self.controller.remove_authored_room_primitive" in window_source
    assert "direct_command_actions" in window_source
    for action_key in (
        "select",
        "move",
        "duplicate_selected",
        "delete_selected",
        "object_grid_snap",
        "object_vertex_snap",
        "center_pivot",
        "freeze_transform",
        "texture_paint",
        "paint_material",
        "paint_wok",
    ):
        assert f'"{action_key}"' in window_source


def test_t2600_main_screen_map_studio_action_opens_window_and_tool_belt_runtime() -> None:
    """The visible Module/Map Studio action opens the real window with usable modeling tools."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtGui, QtWidgets
    from src.gui.windows.application_core.shared.resource_panels import ResourcePanelsMixin
    from src.gui.windows.application_core.shared.window_chrome import WindowChromeMixin

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    class Host(QtWidgets.QMainWindow, WindowChromeMixin, ResourcePanelsMixin):
        def __init__(self) -> None:
            super().__init__()
            self.settings_data = {}
            self._library_rows = []
            self._resource_manager = None
            self.theme_manager = None
            self.layout_manager = None
            self.module_editor_window = None

        def _icon(self, *_args):
            return QtGui.QIcon()

        def _configure_dock_toggle_action(self, *_args, **_kwargs) -> None:
            return None

        def _get_resource_manager(self):
            return None

        def _log(self, *_args, **_kwargs) -> None:
            return None

        def __getattr__(self, name: str):
            if name.startswith("_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

    host = Host()
    try:
        host._build_actions()
        host.modules_action.trigger()
        app.processEvents()

        window = host.module_editor_window
        assert window is not None
        assert window.isVisible()
        assert "Map Studio" in window.windowTitle()
        assert window.minimumWidth() <= 1400
        assert window.minimumHeight() <= 800
        assert window.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioTopToolbarScrollArea") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioToolBeltScrollArea") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioCustomToolBeltScrollArea") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioWorkflowTabsScrollArea") is not None
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioViewportPanelScrollArea") is None
        embedded_viewport = window.findChild(QtWidgets.QWidget, "MapStudioViewportWidget")
        assert embedded_viewport is not None
        assert embedded_viewport.property("_gr_suppress_renderer_diagnostics") is True
        assert embedded_viewport.property("_gr_map_studio_clean_viewport") is True
        presentation = getattr(embedded_viewport, "_map_studio_viewport_presentation", {})
        assert presentation.get("clean_display") is True
        assert presentation.get("subtle_room_outlines") is True
        assert presentation.get("show_room_guides") is False
        assert presentation.get("show_transform_dimensions") is False
        assert embedded_viewport.minimumHeight() >= 320
        assert window.findChild(QtWidgets.QScrollArea, "mapStudioRightTabsScrollArea") is not None
        assert window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget") is not None
        for action_key in ("floor", "wall", "cube", "ramp", "stairs", "door_frame", "arch", "terrain_patch"):
            assert window.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}") is not None
        for action_key in ("select", "move", "duplicate_selected", "delete_selected", "texture_paint", "paint_wok"):
            assert window.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}") is not None
    finally:
        window = getattr(host, "module_editor_window", None)
        if window is not None:
            window.close()
        host.close()


def test_t2600_map_studio_workflow_selector_keeps_narrow_rail_reachable_runtime() -> None:
    """Every workflow stays named, synchronized, and inside the 300px rail."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.show()
        window.main_splitter.setSizes([300, 900, 300])
        app.processEvents()
        app.processEvents()

        expected_labels = ["Rooms", "Place", "WOK", "Paint", "Environment", "Porter", "Build", "Data"]
        assert window.workflow_selector.objectName() == "mapStudioWorkflowSelector"
        assert window.workflow_selector.accessibleName() == "Map Studio workflow"
        assert [window.workflow_selector.itemText(index) for index in range(window.workflow_selector.count())] == expected_labels
        assert window.workflow_tabs.count() == len(expected_labels)
        assert window.workflow_tabs_scroll.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAlwaysOff

        for index, label in enumerate(expected_labels):
            window.workflow_selector.setCurrentIndex(index)
            app.processEvents()
            app.processEvents()

            page = window.workflow_tabs.currentWidget()
            assert page is window.workflow_tabs.widget(index)
            assert window.workflow_tabs.tabText(index) == label
            assert window.workflow_tabs.width() == window.workflow_tabs_scroll.viewport().width()
            assert page.width() == window.workflow_tabs.width()
            assert window.workflow_tabs_scroll.horizontalScrollBar().maximum() == 0
            expected_page_height = max(page.minimumSizeHint().height(), page.sizeHint().height())
            if page.hasHeightForWidth():
                expected_page_height = max(
                    expected_page_height,
                    page.heightForWidth(max(1, window.workflow_tabs.width())),
                )
            assert window.workflow_tabs.height() <= expected_page_height + 1
            assert window.workflow_tabs_scroll.verticalScrollBar().maximum() <= max(
                0,
                expected_page_height - window.workflow_tabs_scroll.viewport().height() + 1,
            )
            for control in page.findChildren(QtWidgets.QAbstractButton):
                if not control.isVisibleTo(page):
                    continue
                left = control.mapTo(page, QtCore.QPoint(0, 0)).x()
                assert left >= 0
                assert left + control.width() <= page.width() + 1
                full_text = str(control.property("_gr_workflow_full_text") or "")
                if full_text and str(control.text()) != full_text:
                    assert control.toolTip() or control.accessibleName() == full_text.replace("&", "")

        window.workflow_tabs.setCurrentWidget(window.texture_paint_tab)
        app.processEvents()
        collapsed_height = window.workflow_tabs.height()
        window.texture_paint_tab.advanced_button.setChecked(True)
        app.processEvents()
        app.processEvents()
        assert window.workflow_tabs.height() > collapsed_height
        window.texture_paint_tab.advanced_button.setChecked(False)
        app.processEvents()
        app.processEvents()
        assert window.workflow_tabs.height() == collapsed_height

        window.workflow_tabs.setCurrentWidget(window.environment_tab)
        app.processEvents()
        assert window.workflow_selector.currentText() == "Environment"
    finally:
        window.controller.project.dirty = False
        window.close()


def test_stock_module_editor_attaches_installed_textures_without_eager_scan() -> None:
    """Opening the editor must not enumerate the optional installed texture catalog."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.stock_module_editor_window import StockModuleEditorWindow

    class SlowTextureLibrary:
        def __init__(self) -> None:
            self.list_calls = 0

        def list_textures(self, _game: str = "K2") -> list[str]:
            self.list_calls += 1
            return ["test_texture"]

        @staticmethod
        def get_texture_data(_resref: str, _game: str = "K2") -> bytes:
            return b""

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    library = SlowTextureLibrary()
    window = StockModuleEditorWindow()
    try:
        window.set_game_library(library, game="K2")
        app.processEvents()

        assert library.list_calls == 0
        assert window.load_game_textures_action.isEnabled()
        assert not window.onboarding_frame.isHidden()
        assert "available on request" in window.statusBar().currentMessage()
    finally:
        window.close()


def test_t2904_map_studio_viewport_can_fill_window_and_restore_panels() -> None:
    """The center editor is no longer capped by rigid side-rail minimums."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.resize(1500, 900)
        window.show()
        window.main_splitter.setSizes([300, 900, 300])
        app.processEvents()
        normal_sizes = window.main_splitter.sizes()
        normal_viewport_width = window.viewport_host.width()

        assert window.left_authoring_rail.minimumWidth() <= 240
        assert window.right_inspector_rail.minimumWidth() <= 260
        assert window.main_splitter.isCollapsible(0)
        assert window.main_splitter.isCollapsible(2)
        assert window.focus_viewport_action.shortcut().toString() == "Ctrl+Space"

        window.focus_viewport_action.setChecked(True)
        app.processEvents()

        assert window.left_authoring_rail.isHidden()
        assert window.right_inspector_rail.isHidden()
        assert window.toolbar_scroll.isHidden()
        assert window.map_studio_tool_belt_tabs.isHidden()
        assert window.main_splitter.sizes()[0] == 0
        assert window.main_splitter.sizes()[2] == 0
        assert window.viewport_host.width() > normal_viewport_width

        window.focus_viewport_action.setChecked(False)
        app.processEvents()

        assert not window.left_authoring_rail.isHidden()
        assert not window.right_inspector_rail.isHidden()
        restored_sizes = window.main_splitter.sizes()
        assert restored_sizes[0] > 0
        assert restored_sizes[2] > 0
        assert abs(restored_sizes[0] - normal_sizes[0]) <= 2
        assert abs(restored_sizes[2] - normal_sizes[2]) <= 2
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_modeling_tabs_exist_only_after_the_main_window_opens_map_studio() -> None:
    """The main scene stays clean while the opened Map Studio owns its authoring belt."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})
    try:
        window.show()
        app.processEvents()

        icon_only_controls = [
            button
            for button in (
                *window.findChildren(QtWidgets.QToolButton),
                *window.findChildren(QtWidgets.QPushButton),
            )
            if button.property("_gr_ignore_layout_button_mode") is True
            and not str(button.text() or "").strip()
            and button.iconSize().width() > 0
        ]
        assert icon_only_controls
        blank_controls = [
            button.objectName() or str(button.toolTip() or button.property("_gr_full_text") or "<unnamed>")
            for button in icon_only_controls
            if button.icon().isNull()
        ]
        assert blank_controls == []

        command_icon = window.findChild(QtWidgets.QToolButton, "CommandLauncherButton")
        assert command_icon is not None
        assert command_icon.text() == "Studios and Tools"
        assert command_icon.accessibleName() == "Open Studios and Tools"
        assert window.findChild(QtWidgets.QToolButton, "ViewportToolbarMapStudioModelingButton") is None
        top_toolbar = window.findChild(QtWidgets.QToolBar, "ReservedTopToolbar")
        assert top_toolbar is not None
        modeling_tabs = window.findChild(QtWidgets.QTabWidget, "ViewportToolbarMapStudioModelingTabs")
        assert modeling_tabs is None
        default_row = window.findChild(QtWidgets.QWidget, "ViewportToolbarDefaultRow")
        assert default_row is not None
        toolbar_band = window.findChild(QtWidgets.QFrame, "ViewportToolbarBand")
        assert toolbar_band is not None
        assert toolbar_band.height() == default_row.height()
        assert top_toolbar.minimumHeight() >= toolbar_band.height()
        assert top_toolbar.maximumHeight() >= toolbar_band.height()

        command_icon.click()
        app.processEvents()
        command_dialog = getattr(window, "_command_launcher_dialog", None)
        assert command_dialog is not None
        command_dialog.search_edit.setText("Map Studio")
        app.processEvents()
        assert command_dialog.command_tree.currentItem().text(0).startswith("Open Map Studio")
        command_dialog._activate_current()
        app.processEvents()

        module_window = getattr(window, "module_editor_window", None)
        assert module_window is not None
        assert module_window.isVisible()
        assert module_window.minimumWidth() <= 1400
        assert module_window.minimumHeight() <= 800
        assert module_window.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioTopToolbarScrollArea") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioToolBeltScrollArea") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioCustomToolBeltScrollArea") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioWorkflowTabsScrollArea") is not None
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioViewportPanelScrollArea") is None
        embedded_viewport = module_window.findChild(QtWidgets.QWidget, "MapStudioViewportWidget")
        assert embedded_viewport is not None
        assert embedded_viewport.map_studio_authoring_chrome_enabled is True
        modeling_tabs = module_window.findChild(QtWidgets.QTabWidget, "ViewportToolbarMapStudioModelingTabs")
        assert modeling_tabs is not None
        assert modeling_tabs.isVisible()
        assert [modeling_tabs.tabText(index) for index in range(modeling_tabs.count())] == [
            "Modeling",
            "Blockout",
        ]
        for mode_key in ("object", "vertex", "edge", "face", "terrain", "walkmesh"):
            assert module_window.findChild(
                QtWidgets.QToolButton,
                f"ViewportToolbarMapStudioModeButton_{mode_key}",
            ) is not None
        for action_key in ("blockout_room", "floor", "wall", "cube", "ramp", "stairs", "door_frame", "arch", "terrain_patch"):
            assert module_window.findChild(
                QtWidgets.QToolButton,
                f"ViewportToolbarMapStudioBlockoutButton_{action_key}",
            ) is not None
        mode_requests: list[str] = []
        command_requests: list[str] = []
        module_window._open_map_studio_mode_from_viewport = mode_requests.append
        module_window._run_map_studio_viewport_modeling_command = command_requests.append
        module_window.findChild(
            QtWidgets.QToolButton,
            "ViewportToolbarMapStudioModeButton_vertex",
        ).click()
        module_window.findChild(
            QtWidgets.QToolButton,
            "ViewportToolbarMapStudioBlockoutButton_floor",
        ).click()
        app.processEvents()
        assert mode_requests == ["Vertex"]
        assert command_requests == ["floor"]
        assert embedded_viewport.property("_gr_suppress_renderer_diagnostics") is True
        assert embedded_viewport.property("_gr_map_studio_clean_viewport") is True
        presentation = getattr(embedded_viewport, "_map_studio_viewport_presentation", {})
        assert presentation.get("clean_display") is True
        assert presentation.get("subtle_room_outlines") is True
        assert presentation.get("show_room_guides") is False
        assert presentation.get("show_transform_dimensions") is False
        assert module_window.findChild(QtWidgets.QScrollArea, "mapStudioRightTabsScrollArea") is not None
        for action_key in (
            "object",
            "vertex",
            "edge",
            "face",
            "select",
            "move",
            "duplicate_selected",
            "delete_selected",
            "object_grid_snap",
            "object_vertex_snap",
            "vertex_snap",
            "grid_snap",
            "weld",
            "cut",
            "bridge",
            "extrude",
            "bevel",
            "inset",
            "flatten",
            "cleanup",
            "triangulate",
            "center_pivot",
            "freeze_transform",
            "terrain_patch",
            "texture_paint",
            "paint_material",
            "paint_wok",
            "validate",
        ):
            assert module_window.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}") is not None
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            module_window.controller.project.dirty = False
            module_window.close()
        window.close()


def test_t2600_map_studio_icon_reopens_after_close_or_deleted_reference_runtime() -> None:
    """The main toolbar/menu action keeps opening Map Studio across real window lifetimes."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})
    try:
        window.show()
        app.processEvents()

        window.modules_action.trigger()
        app.processEvents()
        first = getattr(window, "module_editor_window", None)
        assert first is not None
        assert first.isVisible()
        assert first.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None

        first.controller.project.dirty = False
        first.close()
        app.processEvents()
        assert not first.isVisible()

        window.modules_action.trigger()
        app.processEvents()
        reopened = getattr(window, "module_editor_window", None)
        assert reopened is first
        assert reopened.isVisible()
        assert reopened.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None

        reopened.controller.project.dirty = False
        reopened.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()

        window.modules_action.trigger()
        app.processEvents()
        recreated = getattr(window, "module_editor_window", None)
        assert recreated is not None
        assert recreated is not reopened
        assert recreated.isVisible()
        assert recreated.findChild(QtWidgets.QTabWidget, "mapStudioToolBeltTabs") is not None
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            try:
                module_window.controller.project.dirty = False
                module_window.close()
            except RuntimeError:
                pass
        window.close()


def test_t2600_map_studio_load_lyt_uses_indexed_resource_picker_runtime(monkeypatch) -> None:
    """Load LYT uses an in-app indexed game-resource chooser instead of raw Explorer browsing."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.core.assets.resource_manager import RES_LYT
    from src.gui.windows.module_editor_window import ModuleEditorWindow, _MapStudioLytResourceDialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    lyt_text = "\n".join(
        [
            "#MAXLAYOUT ASCII",
            "filedependancy layout.max",
            "beginlayout",
            "roomcount 2",
            "  m12aa_01  0.0  0.0  0.0",
            "  m12aa_02  10.0  0.0  0.0",
            "doorhookcount 1",
            "  m12aa_door  5.0  0.0  0.0",
            "donelayout",
        ]
    ).encode("latin-1")

    class FakeInstall:
        def __init__(self, game_dir: str, resrefs: tuple[str, ...]) -> None:
            self.game_dir = game_dir
            self._resrefs = resrefs

        def list_resrefs(self, restype: int):
            assert restype == RES_LYT
            return self._resrefs

    class FakeResourceManager:
        def __init__(self) -> None:
            self._installs = {
                "K1": FakeInstall("C:/Games/KOTOR", ("m12aa",)),
                "K2": FakeInstall("C:/Games/KOTOR2", ("003ebo",)),
            }

        def get_k1(self):
            return self._installs["K1"]

        def get_k2(self):
            return self._installs["K2"]

        def get(self, resref: str, restype: int, game: str = "K1"):
            assert restype == RES_LYT
            return lyt_text

    def fail_file_dialog(*_args, **_kwargs):
        raise AssertionError("Load LYT should use the indexed in-app picker, not QFileDialog.")

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", fail_file_dialog)
    window = ModuleEditorWindow()
    window.resource_manager = FakeResourceManager()
    try:
        rows = window._indexed_lyt_resource_rows()
        assert [row["resref"] for row in rows] == ["m12aa", "003ebo"]
        assert rows[0]["room_count"] == 2
        assert rows[0]["doorhook_count"] == 1

        dialog = _MapStudioLytResourceDialog(window, rows=rows)
        try:
            assert dialog.findChild(QtWidgets.QLineEdit, "mapStudioLytResourceSearchLineEdit") is not None
            assert dialog.findChild(QtWidgets.QComboBox, "mapStudioLytResourceGameComboBox") is not None
            assert dialog.findChild(QtWidgets.QListWidget, "mapStudioLytResourceListWidget").count() == 2
        finally:
            dialog.close()

        window._choose_indexed_lyt_resource = lambda indexed_rows: indexed_rows[0]
        window._handle_tab_action("Load LYT")
        app.processEvents()

        assert [room.model_resref for room in window.project.rooms] == ["m12aa_01", "m12aa_02"]
        assert "K1:m12aa.lyt" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_map_studio_viewport_mode_buttons_route_owning_workspaces_runtime() -> None:
    """Map Studio's viewport mode buttons focus workflows inside the owning editor."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})

    expected = {
        "object": ("blockout", "geometry", "object", "primitive_room", "builder_tab"),
        "vertex": ("component", "geometry", "vertex", "weld_vertices", "builder_tab"),
        "edge": ("component", "geometry", "edge", "bridge", "builder_tab"),
        "face": ("component", "geometry", "face", "fill_face", "builder_tab"),
        "terrain": ("terrain", "terrain", "terrain", "terrain_sculpt", "builder_tab"),
        "walkmesh": ("component", "walkmesh", "walkmesh", "paint_wok", "walkmesh_tab"),
    }

    try:
        window.show()
        app.processEvents()
        assert window.findChild(
            QtWidgets.QToolButton,
            "ViewportToolbarMapStudioModeButton_object",
        ) is None
        command = window.findChild(QtWidgets.QToolButton, "CommandLauncherButton")
        assert command is not None
        command.click()
        app.processEvents()
        command_dialog = getattr(window, "_command_launcher_dialog", None)
        assert command_dialog is not None
        command_dialog.search_edit.setText("Map Studio")
        app.processEvents()
        command_dialog._activate_current()
        app.processEvents()
        module_window = getattr(window, "module_editor_window", None)
        assert module_window is not None
        assert module_window.isVisible()

        for mode_key, (preset_key, workspace_key, component_key, tool_key, tab_name) in expected.items():
            button = module_window.findChild(QtWidgets.QToolButton, f"ViewportToolbarMapStudioModeButton_{mode_key}")
            assert button is not None
            assert button.isEnabled()
            button.click()
            app.processEvents()

            assert module_window.map_studio_tool_belt_preset_combo.currentData() == preset_key
            assert module_window.map_studio_workspace_combo.currentData() == workspace_key
            assert module_window.builder_tab.componentModeComboBox.currentData()["key"] == component_key
            assert module_window.builder_tab.modelingToolComboBox.currentData()["key"] == tool_key
            expected_tab = module_window.walkmesh_tab if tab_name == "walkmesh_tab" else module_window.builder_tab
            assert module_window.workflow_tabs.currentWidget() is expected_tab
            assert f"{component_key.capitalize()} mode" in module_window.statusBar().currentMessage()
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            module_window.controller.project.dirty = False
            module_window.close()
        window.close()


def test_t2600_map_studio_marking_menus_route_modes_and_tools_runtime() -> None:
    """Viewport marking menus expose Maya-like mode and tool choices through Map Studio actions."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def collect_actions(menu: QtWidgets.QMenu) -> list[QtGui.QAction]:
        actions: list[QtGui.QAction] = []
        for action in menu.actions():
            actions.append(action)
            child_menu = action.menu()
            if child_menu is not None:
                actions.extend(collect_actions(child_menu))
        return actions

    try:
        mode_menu = window._build_map_studio_mode_marking_menu(window)
        assert mode_menu.objectName() == "mapStudioModeMarkingMenu"
        # 2026-07-07 redesign: GModeler picks faces/edges/vertices by hover,
        # so the menu offers Edit Mode + Object Mode (+ Terrain/Placement)
        # instead of per-component modes.
        for key in ("edit", "object", "terrain", "placement"):
            assert mode_menu.findChild(QtWidgets.QToolButton, f"mapStudioModeMarkingButton_{key}") is not None
            assert mode_menu.findChild(QtGui.QAction, f"mapStudioModeMarkingAction_{key}") is not None

        edit_action = mode_menu.findChild(QtGui.QAction, "mapStudioModeMarkingAction_edit")
        assert edit_action is not None
        edit_action.trigger()
        app.processEvents()
        assert window.toolbar.selection_mode.currentText() == "Multi-Component"
        panel = window.viewport_panel
        assert panel._hover_probe_enabled is True
        assert panel._hover_component_mode == ""  # all components at once

        tool_menu = window._build_map_studio_tool_marking_menu(window)
        assert tool_menu.objectName() == "mapStudioToolMarkingMenu"
        for key in ("extrude", "bridge", "cut", "weld", "fill_hole", "bevel"):
            button = tool_menu.findChild(QtWidgets.QToolButton, f"mapStudioToolMarkingQuickButton_{key}")
            assert button is not None
            assert button.defaultAction() is not None
        names = {action.objectName(): action for action in collect_actions(tool_menu)}
        for key in (
            "insert_edge_loop",
            "cut_slice_insert_edges",
            "triangulate",
            "cleanup",
            "soften_edges",
            "harden_edges",
            "reverse_normals",
            "mirror",
            "separate",
            "combine",
            "texture_paint",
            "paint_material",
            "paint_wok",
            "validate",
            "sculpt_raise",
            "sculpt_smooth",
            "sculpt_flatten",
        ):
            assert f"mapStudioToolMarkingAction_{key}" in names
        assert tool_menu.findChild(QtWidgets.QMenu, "mapStudioToolMarkingTerrainBrushesMenu") is not None
        assert tool_menu.findChild(QtWidgets.QMenu, "mapStudioToolMarkingUvMappingMenu") is not None
        # "Planned / Missing" menu removed in the 2026-07-07 UI cleanup:
        # roadmap items live in the audit brief and dimmed GModeler actions.
        assert tool_menu.findChild(QtWidgets.QMenu, "mapStudioToolMarkingPlannedMenu") is None
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_viewport_right_click_marking_menu_requests_split_by_shift_runtime() -> None:
    """Plain RMB requests the mode marking menu; Shift+RMB requests the tool marking menu."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    mode_positions: list[QtCore.QPoint] = []
    tool_positions: list[QtCore.QPoint] = []
    panel.modeMarkingMenuRequested.connect(mode_positions.append)
    panel.toolMarkingMenuRequested.connect(tool_positions.append)

    def mouse_event(modifiers=QtCore.Qt.NoModifier):
        return QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress,
            QtCore.QPointF(42, 42),
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            modifiers,
        )

    try:
        canvas = panel.viewport.canvas
        assert panel.eventFilter(canvas, mouse_event()) is True
        assert len(mode_positions) == 1
        assert len(tool_positions) == 0

        assert panel.eventFilter(canvas, mouse_event(QtCore.Qt.ShiftModifier)) is True
        assert len(mode_positions) == 1
        assert len(tool_positions) == 1

        panel.viewport.canvas.install_input_bridge(panel.viewport)
        panel.viewport._show_mesh_context_menu = lambda _event: (_ for _ in ()).throw(
            AssertionError("Map Studio RMB should not fall through to the generic mesh context menu.")
        )
        surface = panel.viewport.canvas.current_surface() or canvas
        assert panel.viewport.eventFilter(surface, mouse_event()) is True
        assert len(mode_positions) == 2
        assert len(tool_positions) == 1

        assert panel.viewport.eventFilter(surface, mouse_event(QtCore.Qt.ShiftModifier)) is True
        assert len(mode_positions) == 2
        assert len(tool_positions) == 2
    finally:
        panel.close()


def test_t3008_pie_start_cancels_authoring_selection_marquees_runtime() -> None:
    """PIE must never retain either Map Studio or shared-viewport rubber bands."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.panels.module_editor.module_editor_viewport_panel import ModuleEditorViewportPanel

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = ModuleEditorViewportPanel()
    try:
        panel.show()
        app.processEvents()
        canvas = panel.viewport.canvas
        map_band = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, canvas)
        map_band.setGeometry(QtCore.QRect(20, 20, 160, 90))
        map_band.show()
        panel._map_studio_marquee = {
            "origin": QtCore.QPoint(20, 20),
            "band": map_band,
            "widget": canvas,
        }
        shared_band = panel.viewport._selection_rubber_band
        shared_band.setGeometry(QtCore.QRect(40, 40, 120, 70))
        shared_band.show()
        panel.viewport._mesh_box_start = QtCore.QPoint(40, 40)
        panel.viewport._mesh_box_selecting = True
        panel.viewport._is_dragging = True
        app.processEvents()

        assert not map_band.isHidden()
        assert not shared_band.isHidden()
        panel.set_map_studio_pie_active(True)
        app.processEvents()

        assert panel._map_studio_marquee is None
        assert map_band.isHidden()
        assert shared_band.isHidden()
        assert panel.viewport._mesh_box_start is None
        assert panel.viewport._mesh_box_selecting is False
        assert panel.viewport._is_dragging is False
    finally:
        panel.set_map_studio_pie_active(False)
        panel.close()


def test_t2600_map_studio_gimbal_modes_and_undo_redo_shortcuts_runtime() -> None:
    """Selected primitives show a manipulator, W/E/R changes modes, and Ctrl+Z/Ctrl+R route to KMAP undo/redo."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def key_event(key, modifiers=QtCore.Qt.NoModifier):
        return QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifiers)

    def primitive_names() -> set[str]:
        return {
            str(getattr(row, "primitive_name", "") or "")
            for row in window.controller.authored_room_primitive_transforms()
        }

    try:
        window.show()
        app.processEvents()
        click_tool("cube")

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        primitive_name = str(selected["primitive_name"])
        overlay = getattr(window.viewport_panel.viewport, "_map_studio_universal_transform_overlay", None)
        assert overlay is not None
        assert getattr(overlay, "primitive_name", "") == primitive_name

        translate_button = window.findChild(QtWidgets.QToolButton, "mapStudioViewportTranslateGizmoButton")
        rotate_button = window.findChild(QtWidgets.QToolButton, "mapStudioViewportRotateGizmoButton")
        scale_button = window.findChild(QtWidgets.QToolButton, "mapStudioViewportScaleGizmoButton")
        assert translate_button is not None and translate_button.isChecked()
        assert rotate_button is not None
        assert scale_button is not None

        surface = window.viewport_panel.viewport.canvas.current_surface() or window.viewport_panel.viewport.canvas
        assert window.viewport_panel.viewport.eventFilter(surface, key_event(QtCore.Qt.Key_E)) is True
        assert window.viewport_panel.transform_gizmo_mode() == "rotate"
        assert getattr(window.viewport_panel.viewport, "_map_studio_transform_gizmo_mode") == "rotate"
        assert rotate_button.isChecked()

        assert window.viewport_panel.viewport.eventFilter(surface, key_event(QtCore.Qt.Key_R)) is True
        assert window.viewport_panel.transform_gizmo_mode() == "scale"
        assert scale_button.isChecked()

        assert window.viewport_panel.viewport.eventFilter(surface, key_event(QtCore.Qt.Key_W)) is True
        assert window.viewport_panel.transform_gizmo_mode() == "translate"
        assert translate_button.isChecked()

        assert primitive_name in primitive_names()
        assert window.viewport_panel.viewport.eventFilter(
            surface,
            key_event(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier),
        ) is True
        app.processEvents()
        assert primitive_name not in primitive_names()

        assert window.viewport_panel.viewport.eventFilter(
            surface,
            key_event(QtCore.Qt.Key_R, QtCore.Qt.ControlModifier),
        ) is True
        app.processEvents()
        assert primitive_name in primitive_names()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_map_studio_delete_key_removes_selected_authored_primitive_runtime() -> None:
    """The viewport Delete key removes the selected authored primitive through KMAP history."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_names() -> set[str]:
        return {
            str(getattr(row, "primitive_name", "") or "")
            for row in window.controller.authored_room_primitive_transforms()
        }

    try:
        window.show()
        app.processEvents()
        click_tool("cube")

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        primitive_name = str(selected["primitive_name"])
        assert primitive_name in primitive_names()

        surface = window.viewport_panel.viewport.canvas.current_surface() or window.viewport_panel.viewport.canvas
        delete_event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Delete, QtCore.Qt.NoModifier)
        assert window.viewport_panel.viewport.eventFilter(surface, delete_event) is True
        app.processEvents()

        assert primitive_name not in primitive_names()
        assert window.controller.command_history.undo_label == f"Remove primitive {primitive_name}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        window.undo_map_studio_command()
        app.processEvents()
        assert primitive_name in primitive_names()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_map_studio_outliner_selects_renames_and_deletes_primitives_runtime() -> None:
    """Map Studio outliner rows behave like Maya scene objects for authored primitives."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    def outliner_item(item_id: str):
        for item in window.outliner.findItems("*", QtCore.Qt.MatchWildcard | QtCore.Qt.MatchRecursive):
            if str(item.data(0, QtCore.Qt.UserRole) or "") == item_id:
                return item
        raise AssertionError(f"Missing outliner item {item_id!r}")

    try:
        window.show()
        app.processEvents()
        click_tool("cube")

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        room_resref = str(selected["room_resref"])
        primitive_name = str(selected["primitive_name"])
        item_id = f"authored_primitive:{room_resref}:{primitive_name}"
        item = outliner_item(item_id)
        assert item.text(0) == primitive_name
        assert item.text(1) == "cube"

        window.outliner.setCurrentItem(item)
        app.processEvents()
        selected_after_click = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected_after_click, dict)
        assert selected_after_click.get("primitive_name") == primitive_name
        overlay = getattr(window.viewport_panel.viewport, "_map_studio_universal_transform_overlay", None)
        assert overlay is not None
        assert getattr(overlay, "primitive_name", "") == primitive_name

        renamed = "renamed_outliner_cube"
        item.setText(0, renamed)
        app.processEvents()
        assert renamed in primitive_rows()
        assert primitive_name not in primitive_rows()
        assert window.controller.command_history.undo_label == f"Rename primitive {primitive_name}"

        renamed_id = f"authored_primitive:{room_resref}:{renamed}"
        renamed_item = outliner_item(renamed_id)
        window._outliner_action("delete", renamed_id)
        app.processEvents()
        assert renamed not in primitive_rows()
        assert window.controller.command_history.undo_label == f"Remove primitive {renamed}"

        window.undo_map_studio_command()
        app.processEvents()
        assert renamed in primitive_rows()
        assert outliner_item(renamed_id).text(0) == renamed
        assert renamed_item is not None
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_map_studio_gimbal_rotate_and_scale_commit_authored_kmap_runtime() -> None:
    """Rotate and scale gimbal modes commit through authored KMAP transform commands."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_row(name: str):
        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }
        return rows[name]

    try:
        window.show()
        app.processEvents()
        click_tool("cube")

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        room_resref = str(selected["room_resref"])
        primitive_name = str(selected["primitive_name"])

        window.viewport_panel.set_transform_gizmo_mode("rotate")
        window._rotate_authored_room_primitive(room_resref, primitive_name, 22.5)
        app.processEvents()
        assert round(float(getattr(primitive_row(primitive_name), "rotation_degrees_z")), 1) == 22.5
        assert window.controller.command_history.undo_label == f"Transform primitive {primitive_name}"

        window.viewport_panel.set_transform_gizmo_mode("scale")
        window._scale_authored_room_primitive(room_resref, primitive_name, (1.5, 1.5, 1.5))
        app.processEvents()
        assert tuple(round(float(value), 3) for value in getattr(primitive_row(primitive_name), "scale")) == (
            1.5,
            1.5,
            1.5,
        )
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2907_object_drag_commit_promotes_resident_preview_without_level_rebuild() -> None:
    """A finished Maya-style object drag lands the visible result in place."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    try:
        window.show()
        app.processEvents()
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        cube = belt.findChild(QtWidgets.QToolButton, "mapStudioToolBeltButton_cube")
        assert cube is not None
        cube.click()
        app.processEvents()

        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        identity = (str(selected["room_resref"]), str(selected["primitive_name"]))
        selection = (identity,)
        baselines, pivot = window.viewport_panel._capture_room_primitive_drag_preview(selection)
        assert len(baselines) == 1
        node = baselines[0]["node"]
        model = window.viewport_panel._room_preview_model
        drag = {
            "selection": selection,
            "mode": "translate",
            "group_pivot": pivot,
            "preview_baselines": baselines,
            "pending_delta": (0.75, -0.25, 0.0),
            "pending_rotation_delta_degrees": 0.0,
            "pending_scale_multiplier": (1.0, 1.0, 1.0),
            "active": True,
        }
        window.viewport_panel._apply_room_primitive_drag_preview(drag)
        visible_vertices = tuple(node.vertices)
        window.viewport_panel._pending_room_primitive_commit_preview = drag

        window._move_authored_room_primitive(identity[0], identity[1], (0.75, -0.25, 0.0))
        app.processEvents()

        assert window.viewport_panel._room_preview_model is model
        assert baselines[0]["node"] is node
        assert tuple(node.vertices) == visible_vertices
        assert window.viewport_panel._pending_room_primitive_commit_preview is None
        row = next(
            item
            for item in window.controller.authored_room_primitive_transforms()
            if str(getattr(item, "primitive_name", "")) == identity[1]
        )
        assert tuple(round(float(value), 3) for value in row.translation) == (0.75, -0.25, 0.0)
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_file_actions_save_open_kmap_and_keep_tool_belt_usable_runtime(tmp_path: Path, monkeypatch) -> None:
    """Visible File actions save/open authored KMAP state and leave modeling tools usable."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    kmap_path = tmp_path / "visible_file_actions.kmap"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )

    def click_tool(window: ModuleEditorWindow, action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    writer = ModuleEditorWindow()
    try:
        writer.show()
        app.processEvents()

        click_tool(writer, "floor")
        click_tool(writer, "paint_wok")
        click_tool(writer, "select")
        selection = writer.controller.map_studio_active_selection()
        assert selection["room_resref"] == "new_level_room01"
        assert selection["primitive_name"] == "new_level_room01_floor"
        assert selection["tool_key"] == "select"
        assert writer.controller.command_history.undo_label == "Select new_level_room01_floor"
        assert writer.controller.command_history.undo_stack[-1].stale_outputs == ()
        writer.save_as_action.trigger()
        app.processEvents()

        assert kmap_path.is_file()
        assert Path(writer.project.path) == kmap_path
        assert writer.project.dirty is False

        click_tool(writer, "cube")
        assert writer.project.dirty is True
        writer.save_action.trigger()
        app.processEvents()
        assert writer.project.dirty is False
    finally:
        writer.controller.project.dirty = False
        writer.close()

    reader = ModuleEditorWindow()
    try:
        reader.show()
        app.processEvents()

        reader.open_action.trigger()
        app.processEvents()

        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in reader.controller.authored_room_primitive_transforms()
        }
        assert "new_level_room01_floor" in rows
        assert rows["new_level_room01_floor"].primitive_type == "plane"
        assert str(getattr(rows["new_level_room01_floor"], "surface_id")) == "4"
        assert any(row.primitive_type == "cube" for row in rows.values())
        reopened_selection = reader.controller.map_studio_active_selection()
        assert reopened_selection["room_resref"] == "new_level_room01"
        assert reopened_selection["primitive_name"] == "new_level_room01_floor"
        assert reopened_selection["tool_key"] == "select"
        assert Path(reader.project.path) == kmap_path
        assert reader.project.dirty is False

        click_tool(reader, "validate")
        assert reader.statusBar().currentMessage().startswith("Validation complete:")
        assert reader.findChild(QtWidgets.QToolButton, "mapStudioToolBeltButton_floor") is not None
        assert reader.findChild(QtWidgets.QToolButton, "mapStudioToolBeltButton_paint_wok") is not None
    finally:
        reader.controller.project.dirty = False
        reader.close()


def test_t2600_visible_walkmesh_tab_assigns_room_wok_surface_and_persists_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    """Visible Walkmesh controls assign WOK surface intent into durable KMAP state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    kmap_path = tmp_path / "visible_walkmesh_surface.kmap"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )

    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def choose_surface(combo: QtWidgets.QComboBox, surface_id: str) -> None:
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("surface_id") or "") == surface_id:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing visible Walkmesh surface {surface_id}")

    def accept_package_wizard(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioPackageWizardDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_package_wizard(attempt + 1))
            return
        output = dialog.findChild(QtWidgets.QLineEdit, "mapStudioPackageWizardOutputDirLineEdit")
        assert output is not None
        output.setText(str(tmp_path))
        dry_run = dialog.findChild(QtWidgets.QCheckBox, "mapStudioPackageWizardDryRunCheckBox")
        assert dry_run is not None
        dry_run.setChecked(True)
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioPackageWizardButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        click_tool("validate")
        QtCore.QTimer.singleShot(20, accept_package_wizard)
        select_preset("export")
        click_tool("stage_module")
        assert window.controller.authored_module_readiness().readiness.capability_stage == "export_candidate"

        open_walkmesh = window.findChild(QtWidgets.QPushButton, "mapStudioWorkflowWalkmeshToolsButton")
        assert open_walkmesh is not None
        assert open_walkmesh.isEnabled()
        open_walkmesh.click()
        app.processEvents()
        assert window.workflow_tabs.currentWidget() is window.walkmesh_tab

        room_combo = window.findChild(QtWidgets.QComboBox, "mapStudioWalkmeshRoomComboBox")
        surface_combo = window.findChild(QtWidgets.QComboBox, "mapStudioWalkmeshSurfaceComboBox")
        apply_button = window.findChild(QtWidgets.QPushButton, "mapStudioWalkmeshApplySurfaceButton")
        status_label = window.findChild(QtWidgets.QLabel, "mapStudioWalkmeshStatusLabel")
        assert room_combo is not None and room_combo.isEnabled()
        assert surface_combo is not None and surface_combo.isEnabled()
        assert apply_button is not None and apply_button.isEnabled()
        assert status_label is not None
        assert "new_level_room01" in room_combo.currentText()

        choose_surface(surface_combo, "6")
        apply_button.click()
        app.processEvents()

        choices = window.controller.authored_walkmesh_room_surface_choices()
        assert len(choices) == 1
        assert choices[0].room_resref == "new_level_room01"
        assert choices[0].floor_surface_id == 6
        assert choices[0].floor_surface_name == "WATER"
        assert choices[0].walkable is False
        assert window.controller.command_history.undo_label == "Style new_level_room01"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        payload = window.controller.project.extra_sections["authored_module"]
        invalidation = payload["export_proof_invalidation"]
        assert invalidation["latest_summary"] == "Style new_level_room01"
        assert invalidation["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
        assert "Regenerate the authored module package" in invalidation["next_action"]
        assert "Applied WOK surface 6 to room new_level_room01" in window.statusBar().currentMessage()

        window.save_as_action.trigger()
        app.processEvents()
        assert kmap_path.is_file()
    finally:
        window.controller.project.dirty = False
        window.close()

    reader = ModuleEditorWindow()
    try:
        reader.show()
        app.processEvents()

        reader.open_action.trigger()
        app.processEvents()

        reopened_choices = reader.controller.authored_walkmesh_room_surface_choices()
        assert len(reopened_choices) == 1
        assert reopened_choices[0].room_resref == "new_level_room01"
        assert reopened_choices[0].floor_surface_id == 6
        assert reopened_choices[0].floor_surface_name == "WATER"
        assert reopened_choices[0].walkable is False
        reopened_payload = reader.controller.project.extra_sections["authored_module"]
        assert reopened_payload["export_proof_invalidation"]["latest_summary"] == "Style new_level_room01"

        open_walkmesh = reader.findChild(QtWidgets.QPushButton, "mapStudioWorkflowWalkmeshToolsButton")
        assert open_walkmesh is not None
        open_walkmesh.click()
        app.processEvents()
        reopened_surface_combo = reader.findChild(QtWidgets.QComboBox, "mapStudioWalkmeshSurfaceComboBox")
        assert reopened_surface_combo is not None
        current_data = reopened_surface_combo.currentData()
        assert isinstance(current_data, dict)
        assert str(current_data.get("surface_id") or "") == "6"
    finally:
        reader.controller.project.dirty = False
        reader.close()


def test_t2600_main_viewport_floor_blockout_button_creates_authored_kmap_state_runtime() -> None:
    """Clicking Floor from the main viewport creates durable KMAP room/floor state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})
    try:
        window.show()
        app.processEvents()

        floor_button = window.findChild(QtWidgets.QToolButton, "ViewportToolbarMapStudioBlockoutButton_floor")
        assert floor_button is not None
        assert floor_button.text() == "Floor"

        floor_button.click()
        app.processEvents()

        module_window = getattr(window, "module_editor_window", None)
        assert module_window is not None
        assert module_window.isVisible()
        rows = module_window.controller.authored_room_primitive_transforms()
        floor_rows = [row for row in rows if row.primitive_type == "plane" and row.supports_walkmesh_surface]
        assert floor_rows
        assert module_window.controller.project.dirty is True
        assert module_window.controller.command_history.undo_label == "Add floor primitive"
        assert module_window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            module_window.controller.project.dirty = False
            module_window.close()
        window.close()


def test_t2600_map_studio_visible_tool_belt_buttons_mutate_kmap_state_runtime() -> None:
    """Visible Map Studio modeling buttons create, style, duplicate, and delete KMAP primitives."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        rows = primitive_rows()
        floor = rows["new_level_room01_floor"]
        assert getattr(floor, "primitive_type") == "plane"
        assert getattr(floor, "supports_walkmesh_surface") is True
        assert window.controller.project.dirty is True
        assert window.controller.command_history.undo_label == "Add floor primitive"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        click_tool("paint_material")
        assert window.controller.command_history.undo_label == "Style primitive new_level_room01_floor"
        assert getattr(primitive_rows()["new_level_room01_floor"], "texture") == "ruler01"

        click_tool("paint_wok")
        assert window.controller.command_history.undo_label == "Style primitive new_level_room01_floor"
        styled_floor = primitive_rows()["new_level_room01_floor"]
        assert str(getattr(styled_floor, "surface_id")) == "4"
        assert str(getattr(styled_floor, "surface_name")).upper() == "STONE"

        window.builder_tab.primitiveTranslateXSpinBox.setValue(0.13)
        window.builder_tab.primitiveTranslateYSpinBox.setValue(0.27)
        window.builder_tab.primitiveTranslateZSpinBox.setValue(0.0)
        click_tool("move")
        moved_floor = primitive_rows()["new_level_room01_floor"]
        assert tuple(round(float(value), 2) for value in getattr(moved_floor, "translation")) == (0.13, 0.27, 0.0)
        assert window.controller.command_history.undo_label == "Move primitive new_level_room01_floor"
        moved_payload = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert moved_payload["floor"]["transform"]["translation"] == [0.13, 0.27, 0.0]

        click_tool("object_grid_snap")
        snapped_floor = primitive_rows()["new_level_room01_floor"]
        assert tuple(round(float(value), 2) for value in getattr(snapped_floor, "translation")) == (0.1, 0.3, 0.0)
        assert window.controller.command_history.undo_label == "Object grid snap new_level_room01_floor"
        snapped_payload = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert [round(float(value), 2) for value in snapped_payload["floor"]["transform"]["translation"]] == [
            0.1,
            0.3,
            0.0,
        ]

        click_tool("duplicate_selected")
        rows = primitive_rows()
        duplicate_names = [name for name in rows if name.startswith("new_level_room01_floor_dup")]
        assert duplicate_names
        duplicate_name = duplicate_names[-1]
        assert window.controller.command_history.undo_label == "Duplicate primitive new_level_room01_floor"
        selected = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(selected, dict)
        assert selected.get("primitive_name") == duplicate_name

        click_tool("delete_selected")
        assert duplicate_name not in primitive_rows()
        assert "new_level_room01_floor" in primitive_rows()
        assert window.controller.command_history.undo_label == f"Remove primitive {duplicate_name}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_undo_redo_actions_restore_authored_kmap_state_runtime() -> None:
    """Visible Undo/Redo actions restore authored Map Studio KMAP mutations."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_names() -> set[str]:
        return {
            str(getattr(row, "primitive_name", "") or "")
            for row in window.controller.authored_room_primitive_transforms()
        }

    try:
        window.show()
        app.processEvents()

        assert window.undo_action.isEnabled() is False
        assert window.redo_action.isEnabled() is False

        click_tool("floor")

        assert "new_level_room01_floor" in primitive_names()
        assert window.undo_action.isEnabled() is True
        assert window.undo_action.text() == "Undo Add floor primitive"
        assert window.redo_action.isEnabled() is False

        window.undo_action.trigger()
        app.processEvents()

        assert "new_level_room01_floor" not in primitive_names()
        assert window.undo_action.isEnabled() is False
        assert window.redo_action.isEnabled() is True
        assert window.redo_action.text() == "Redo Add floor primitive"
        assert "Undid Add floor primitive" in window.statusBar().currentMessage()

        window.redo_action.trigger()
        app.processEvents()

        assert "new_level_room01_floor" in primitive_names()
        assert window.undo_action.isEnabled() is True
        assert window.redo_action.isEnabled() is False
        assert "Redid Add floor primitive" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_component_modeling_buttons_mutate_floor_plan_kmap_state_runtime() -> None:
    """Visible component modeling buttons commit KMAP edits instead of only focusing panels."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def reset_room() -> None:
        click_tool("create_room")
        assert window.controller.command_history.undo_label == "Create authored module grdev01"

    try:
        window.show()
        app.processEvents()

        reset_room()
        click_tool("flatten")
        flattened = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert flattened["metadata"]["last_operation"] == "flatten_floor_plan_vertices"
        assert flattened["metadata"]["flattened_vertices"] == [0, 2]
        assert flattened["metadata"]["flatten_axis"] == "x"
        assert window.controller.command_history.undo_label == "Flatten grdev01_room01 vertices on x"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        reset_room()
        click_tool("cleanup")
        cleaned = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert cleaned["metadata"]["last_operation"] == "cleanup_floor_plan_vertices"
        assert window.controller.command_history.undo_label == "Clean grdev01_room01 floor-plan vertices"

        reset_room()
        click_tool("triangulate")
        triangulated = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert triangulated["metadata"]["last_operation"] == "triangulate_floor_plan_face"
        assert triangulated["metadata"]["triangulated_faces"] == [[0, 1, 2], [0, 2, 3]]
        assert window.controller.command_history.undo_label == "Triangulate grdev01_room01 floor-plan face"

        reset_room()
        click_tool("extrude")
        extruded = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert len(extruded["points"]) == 6
        assert extruded["metadata"]["operation"] == "edge_extrude"
        assert window.controller.command_history.undo_label == "Extrude edge 0 on grdev01_room01"

        reset_room()
        click_tool("bevel")
        beveled = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
        assert len(beveled["points"]) == 8
        assert beveled["metadata"]["operation"] == "bevel"
        assert window.controller.command_history.undo_label == "Bevel grdev01_room01"

        reset_room()
        click_tool("split")
        explicit_split_payload = window.controller.project.extra_sections["authored_module"]
        assert len(explicit_split_payload["rooms"]) == 2
        assert {room["room_resref"] for room in explicit_split_payload["rooms"]} == {
            "grdev01_room0_l1",
            "grdev01_room0_r2",
        }
        assert window.controller.command_history.undo_label == "Axis split grdev01_room01 on x"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        reset_room()
        click_tool("cut")
        split_payload = window.controller.project.extra_sections["authored_module"]
        assert len(split_payload["rooms"]) == 2
        assert {room["room_resref"] for room in split_payload["rooms"]} == {
            "grdev01_room0_l1",
            "grdev01_room0_r2",
        }
        assert window.controller.command_history.undo_label == "Axis split grdev01_room01 on x"
        assert int(window.builder_tab.floorPlanBridgeFirstEdgeSpinBox.value()) == 0
        assert int(window.builder_tab.floorPlanBridgeSecondEdgeSpinBox.value()) == 1

        click_tool("bridge")
        bridged_payload = window.controller.project.extra_sections["authored_module"]
        assert len(bridged_payload["rooms"]) == 3
        bridge_room = bridged_payload["rooms"][-1]
        bridge_metadata = bridge_room["primitive"]["metadata"]
        assert bridge_metadata["operation"] == "bridge_edges"
        assert bridge_metadata["first_room_resref"] == "grdev01_room0_l1"
        assert bridge_metadata["first_edge_index"] == 0
        assert bridge_metadata["second_room_resref"] == "grdev01_room0_r2"
        assert bridge_metadata["second_edge_index"] == 1
        assert bridge_metadata["last_component_edit_audit"]["walkmesh_review_required"] is True
        assert window.controller.command_history.undo_label == "Bridge grdev01_room0_l1:0 to grdev01_room0_r2:1"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_snap_and_weld_buttons_persist_floor_plan_kmap_state_runtime(tmp_path: Path) -> None:
    """Visible snap and weld controls author durable KMAP floor-plan edits."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def room_payload(room_resref: str) -> dict:
        payload = window.controller.project.extra_sections["authored_module"]
        for room in payload["rooms"]:
            if room["room_resref"] == room_resref:
                return room
        raise AssertionError(f"Missing authored room {room_resref!r}")

    def select_room_combo(combo_name: str, room_resref: str) -> None:
        combo = getattr(window.builder_tab, combo_name)
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("room_resref") == room_resref:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing room {room_resref!r} in {combo_name}")

    def save_and_reload(path: Path, room_resref: str) -> dict:
        window.controller.save_project(path)
        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(path)
            payload = reloaded.controller.project.extra_sections["authored_module"]
            for room in payload["rooms"]:
                if room["room_resref"] == room_resref:
                    return dict(room)
            raise AssertionError(f"Missing reloaded room {room_resref!r}")
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()

    def assert_stale_walkmesh_edit(metadata: dict, *, topology_changed: bool) -> None:
        audit = metadata["last_component_edit_audit"]
        assert audit["walkmesh_review_required"] is True
        assert audit["export_candidate_stale"] is True
        assert audit["game_proof_stale"] is True
        assert audit["topology_changed"] is topology_changed
        assert audit["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        click_tool("cut")
        source_room = "grdev01_room0_l1"
        target_room = "grdev01_room0_r2"
        select_room_combo("floorPlanVertexRoomComboBox", source_room)
        select_room_combo("floorPlanVertexTargetRoomComboBox", target_room)
        window.builder_tab.floorPlanSourcePointSpinBox.setValue(1)
        window.builder_tab.floorPlanTargetPointSpinBox.setValue(0)
        app.processEvents()

        click_tool("vertex_snap")

        snapped = room_payload(source_room)
        snapped_metadata = snapped["primitive"]["metadata"]
        assert snapped_metadata["last_operation"] == "snap_floor_plan_vertex"
        assert snapped_metadata["last_vertex_edit"] == 1
        assert snapped_metadata["snap_target_room"] == target_room
        assert snapped_metadata["snap_target_index"] == 0
        assert snapped["primitive"]["points"][1] == room_payload(target_room)["primitive"]["points"][0]
        assert window.controller.command_history.undo_label == f"Snap {source_room} point 1"
        assert_stale_walkmesh_edit(snapped_metadata, topology_changed=False)
        reloaded_snap = save_and_reload(tmp_path / "vertex_snap.kmap", source_room)
        assert reloaded_snap["primitive"]["metadata"]["last_operation"] == "snap_floor_plan_vertex"

        click_tool("create_room")
        window.builder_tab.floorPlanSelectedPointsLineEdit.setText("0,2")
        app.processEvents()
        click_tool("grid_snap")

        gridded = room_payload("grdev01_room01")
        grid_metadata = gridded["primitive"]["metadata"]
        assert grid_metadata["last_operation"] == "grid_snap_floor_plan_vertices"
        assert grid_metadata["grid_snap_vertices"] == [0, 2]
        assert grid_metadata["grid_snap_size"] == 0.1
        assert grid_metadata["grid_snap_axes"] == ["x", "y"]
        assert window.controller.command_history.undo_label == "Grid snap grdev01_room01 vertices"
        assert_stale_walkmesh_edit(grid_metadata, topology_changed=False)
        reloaded_grid = save_and_reload(tmp_path / "grid_snap.kmap", "grdev01_room01")
        assert reloaded_grid["primitive"]["metadata"]["last_operation"] == "grid_snap_floor_plan_vertices"

        click_tool("create_room")
        window.builder_tab.floorPlanSelectedPointsLineEdit.setText("1,2")
        window.builder_tab.floorPlanTargetPointSpinBox.setValue(1)
        app.processEvents()
        click_tool("transform_snap_level")

        level_snapped = room_payload("grdev01_room01")
        level_metadata = level_snapped["primitive"]["metadata"]
        assert level_metadata["last_operation"] == "transform_snap_floor_plan_vertices"
        assert level_metadata["transform_snap_vertices"] == [1, 2]
        assert level_metadata["transform_snap_axis"] == "x"
        assert level_metadata["transform_snap_policy"] == "target"
        assert level_metadata["transform_snap_target_index"] == 1
        assert level_metadata["source"] == "map_studio:floor_plan_transform_level_snap"
        assert window.controller.command_history.undo_label == "Transform snap grdev01_room01 vertices on x"
        assert_stale_walkmesh_edit(level_metadata, topology_changed=False)
        reloaded_level = save_and_reload(tmp_path / "transform_snap_level.kmap", "grdev01_room01")
        assert reloaded_level["primitive"]["metadata"]["last_operation"] == "transform_snap_floor_plan_vertices"

        click_tool("create_room")
        window.builder_tab.floorPlanSelectedPointsLineEdit.setText("0,2")
        window.builder_tab.floorPlanTargetPointSpinBox.setValue(0)
        app.processEvents()
        click_tool("weld")

        welded = room_payload("grdev01_room01")
        weld_metadata = welded["primitive"]["metadata"]
        assert weld_metadata["last_operation"] == "weld_floor_plan_vertices"
        assert weld_metadata["welded_vertices"] == [0, 2]
        assert weld_metadata["weld_policy"] == "target"
        assert len(welded["primitive"]["points"]) == 3
        assert window.controller.command_history.undo_label == "Weld grdev01_room01 vertices"
        assert_stale_walkmesh_edit(weld_metadata, topology_changed=True)
        reloaded_weld = save_and_reload(tmp_path / "weld.kmap", "grdev01_room01")
        assert reloaded_weld["primitive"]["metadata"]["last_operation"] == "weld_floor_plan_vertices"
        assert len(reloaded_weld["primitive"]["points"]) == 3

        click_tool("create_room")
        window.builder_tab.floorPlanSelectedPointsLineEdit.setText("0,2")
        window.builder_tab.floorPlanTargetPointSpinBox.setValue(0)
        app.processEvents()
        click_tool("merge_components")

        merged = room_payload("grdev01_room01")
        merge_metadata = merged["primitive"]["metadata"]
        assert merge_metadata["last_operation"] == "weld_floor_plan_vertices"
        assert merge_metadata["welded_vertices"] == [0, 2]
        assert len(merged["primitive"]["points"]) == 3
        assert window.controller.command_history.undo_label == "Weld grdev01_room01 vertices"
        assert_stale_walkmesh_edit(merge_metadata, topology_changed=True)
        reloaded_merge = save_and_reload(tmp_path / "merge_components.kmap", "grdev01_room01")
        assert reloaded_merge["primitive"]["metadata"]["last_operation"] == "weld_floor_plan_vertices"
        assert len(reloaded_merge["primitive"]["points"]) == 3
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_object_vertex_snap_moves_primitive_and_persists_kmap_runtime(tmp_path: Path) -> None:
    """Visible Object Vertex Snap moves a primitive pivot to another primitive vertex in KMAP state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    def select_primitive(name: str) -> None:
        combo = window.builder_tab.roomPrimitiveTransformComboBox
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("primitive_name") == name:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing visible primitive row {name!r}")

    try:
        window.show()
        app.processEvents()

        click_tool("cube")
        click_tool("cube")
        cubes = [
            row
            for row in primitive_rows().values()
            if str(getattr(row, "primitive_type", "") or "") == "cube"
        ]
        assert len(cubes) >= 2
        source = cubes[0]
        target = cubes[1]

        select_primitive(str(getattr(target, "primitive_name")))
        window.builder_tab.primitiveTranslateXSpinBox.setValue(1.0)
        window.builder_tab.primitiveTranslateYSpinBox.setValue(0.0)
        window.builder_tab.primitiveTranslateZSpinBox.setValue(0.0)
        window.builder_tab.applyPrimitiveTransformButton.click()
        app.processEvents()

        select_primitive(str(getattr(source, "primitive_name")))
        click_tool("object_vertex_snap")

        source_name = str(getattr(source, "primitive_name"))
        target_name = str(getattr(target, "primitive_name"))
        snapped = primitive_rows()[source_name]
        assert tuple(round(float(value), 6) for value in getattr(snapped, "translation")) == (0.5, -0.5, 0.0)
        payload = window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        assert metadata["last_operation"] == "object_vertex_snap_primitive"
        assert metadata["last_vertex_snapped_primitive"] == source_name
        assert metadata["object_vertex_snap_coordinate_space"] == "authored_room_composition_mesh_space"
        assert metadata["target_primitive"] == target_name
        assert metadata["target_vertex_index"] == 0
        assert metadata["target_vertex"] == [0.5, -0.5, 0.0]
        assert metadata["old_translation"] == [0.0, 0.0, 0.0]
        assert metadata["new_translation"] == [0.5, -0.5, 0.0]
        assert window.controller.command_history.undo_label == f"Object vertex snap {source_name}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        path = tmp_path / "object_vertex_snap.kmap"
        window.controller.save_project(path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(path)
            reloaded_rows = {
                str(getattr(row, "primitive_name", "") or ""): row
                for row in reloaded.controller.authored_room_primitive_transforms()
            }
            assert tuple(round(float(value), 6) for value in getattr(reloaded_rows[source_name], "translation")) == (
                0.5,
                -0.5,
                0.0,
            )
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_metadata = reloaded_payload["rooms"][0]["primitive"]["metadata"]
            assert reloaded_metadata["last_operation"] == "object_vertex_snap_primitive"
            assert reloaded_metadata["target_primitive"] == target_name
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_combine_and_separate_buttons_persist_kmap_boundaries_runtime(tmp_path: Path) -> None:
    """Visible Combine and Separate controls author durable KMAP room/object boundaries."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def click_tool(window: ModuleEditorWindow, action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_room_combo(window: ModuleEditorWindow, combo_name: str, room_resref: str) -> None:
        combo = getattr(window.builder_tab, combo_name)
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("room_resref") == room_resref:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing room {room_resref!r} in {combo_name}")

    def select_first_non_floor_primitive(window: ModuleEditorWindow) -> dict:
        combo = window.builder_tab.roomPrimitiveTransformComboBox
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("primitive_type") != "plane":
                combo.setCurrentIndex(index)
                app.processEvents()
                return dict(data)
        raise AssertionError("Missing a non-floor primitive row for visible Separate.")

    def reload_payload(path: Path) -> dict:
        reader = ModuleEditorWindow()
        try:
            reader.controller.open_project(path)
            return dict(reader.controller.project.extra_sections["authored_module"])
        finally:
            reader.controller.project.dirty = False
            reader.close()

    combine_window = ModuleEditorWindow()
    try:
        combine_window.show()
        app.processEvents()

        click_tool(combine_window, "create_room")
        click_tool(combine_window, "cut")
        select_room_combo(combine_window, "floorPlanUnionFirstRoomComboBox", "grdev01_room0_l1")
        select_room_combo(combine_window, "floorPlanUnionSecondRoomComboBox", "grdev01_room0_r2")
        combine_window.builder_tab.floorPlanUnionResultRoomLineEdit.setText("grvisible_union")
        app.processEvents()
        click_tool(combine_window, "combine")

        combined_payload = combine_window.controller.project.extra_sections["authored_module"]
        assert [room["room_resref"] for room in combined_payload["rooms"]] == ["grvisible_union"]
        combined_room = combined_payload["rooms"][0]
        assert combined_room["primitive"]["metadata"]["operation"] == "rectangular_union"
        assert combined_room["primitive"]["metadata"]["source_room_resrefs"] == [
            "grdev01_room0_l1",
            "grdev01_room0_r2",
        ]
        assert combine_window.controller.command_history.undo_label == "Merge grdev01_room0_l1 and grdev01_room0_r2"
        assert combine_window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        combine_path = tmp_path / "visible_combine.kmap"
        combine_window.controller.save_project(combine_path)
        reloaded_combine = reload_payload(combine_path)
        assert [room["room_resref"] for room in reloaded_combine["rooms"]] == ["grvisible_union"]
        assert reloaded_combine["rooms"][0]["primitive"]["metadata"]["operation"] == "rectangular_union"
    finally:
        combine_window.controller.project.dirty = False
        combine_window.close()

    separate_window = ModuleEditorWindow()
    try:
        separate_window.show()
        app.processEvents()

        click_tool(separate_window, "blockout_room")
        selected = select_first_non_floor_primitive(separate_window)
        separate_window.builder_tab.roomPrimitiveSeparateResultLineEdit.setText("grvisible_sep")
        app.processEvents()
        click_tool(separate_window, "separate")

        separated_payload = separate_window.controller.project.extra_sections["authored_module"]
        assert [room["room_resref"] for room in separated_payload["rooms"]] == [
            "grdev01_room01",
            "grvisible_sep",
        ]
        assert separated_payload["rooms"][0]["metadata"]["last_operation"] == "separate_composition_primitive"
        assert separated_payload["rooms"][0]["metadata"]["last_separated_primitive"] == selected["primitive_name"]
        separated_room = separated_payload["rooms"][1]
        assert separated_room["metadata"]["last_operation"] == "separate_composition_primitive"
        assert separated_room["metadata"]["separated_from_room"] == selected["room_resref"]
        assert separated_room["metadata"]["separated_primitive"] == selected["primitive_name"]
        assert separate_window.controller.command_history.undo_label == f"Separate primitive {selected['primitive_name']}"
        assert separate_window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in separate_window.controller.authored_room_primitive_transforms()
        }
        assert selected["primitive_name"] in rows
        assert getattr(rows[selected["primitive_name"]], "room_resref") == "grvisible_sep"

        separate_path = tmp_path / "visible_separate.kmap"
        separate_window.controller.save_project(separate_path)
        reloaded_separate = reload_payload(separate_path)
        assert [room["room_resref"] for room in reloaded_separate["rooms"]] == [
            "grdev01_room01",
            "grvisible_sep",
        ]
        assert reloaded_separate["rooms"][1]["metadata"]["separated_primitive"] == selected["primitive_name"]
    finally:
        separate_window.controller.project.dirty = False
        separate_window.close()


def test_t2600_visible_opening_and_transition_marker_persist_kmap_and_validate_runtime(tmp_path: Path) -> None:
    """Visible doorway controls persist KMAP opening/transition intent and validation blockers."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        window.builder_tab.floorPlanOpeningNameLineEdit.setText("south_door")
        window.builder_tab.floorPlanOpeningEdgeSpinBox.setValue(0)
        window.builder_tab.floorPlanOpeningCenterSpinBox.setValue(0.5)
        window.builder_tab.floorPlanOpeningWidthSpinBox.setValue(1.5)
        window.builder_tab.floorPlanOpeningHeightSpinBox.setValue(2.0)
        window.builder_tab.floorPlanOpeningBottomSpinBox.setValue(0.0)
        app.processEvents()

        click_tool("opening")

        payload = window.controller.project.extra_sections["authored_module"]
        primitive = payload["rooms"][0]["primitive"]
        opening = primitive["openings"][-1]
        assert opening == {
            "name": "south_door",
            "edge_index": 0,
            "center_fraction": 0.5,
            "width": 1.5,
            "height": 2.0,
            "bottom": 0.0,
            "metadata": {"source": "map_studio:wall_opening", "operation": "set_wall_opening"},
        }
        assert primitive["metadata"]["last_operation"] == "set_wall_opening"
        assert primitive["metadata"]["last_opening_name"] == "south_door"
        assert window.controller.command_history.undo_label == "Set wall opening south_door"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        trigger_index = window.builder_tab.floorPlanOpeningMarkerKindComboBox.findData("trigger")
        assert trigger_index >= 0
        window.builder_tab.floorPlanOpeningMarkerKindComboBox.setCurrentIndex(trigger_index)
        window.builder_tab.floorPlanOpeningMarkerTemplateLineEdit.setText("trg_exit")
        window.builder_tab.floorPlanOpeningMarkerTagLineEdit.setText("south_exit_trigger")
        window.builder_tab.floorPlanOpeningMarkerLinkedToLineEdit.setText("wp_dest")
        window.builder_tab.floorPlanOpeningMarkerLinkedModuleLineEdit.setText("grnext01")
        target_index = window.builder_tab.floorPlanOpeningMarkerTargetTypeComboBox.findData(2)
        assert target_index >= 0
        window.builder_tab.floorPlanOpeningMarkerTargetTypeComboBox.setCurrentIndex(target_index)
        window.builder_tab.floorPlanOpeningMarkerTransitionDestSpinBox.setValue(2)
        app.processEvents()

        click_tool("opening_marker")

        marker_payload = window.controller.project.extra_sections["authored_module"]
        trigger = marker_payload["placements"]["triggers"][-1]
        marker_metadata = marker_payload["extra"]["last_opening_transition_marker"]
        assert trigger["template_resref"] == "trg_exit"
        assert trigger["tag"] == "south_exit_trigger"
        assert trigger["linked_to"] == "wp_dest"
        assert trigger["linked_to_module"] == "grnext01"
        assert trigger["linked_to_flags"] == 2
        assert trigger["transition_destination"] == 2
        assert marker_metadata["room_resref"] == "grdev01_room01"
        assert marker_metadata["opening_name"] == "south_door"
        assert marker_metadata["marker_kind"] == "trigger"
        assert marker_metadata["linked_to_flags"] == 2
        assert marker_metadata["transition_destination"] == 2
        assert window.controller.command_history.undo_label == "Add opening marker south_exit_trigger"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        issues = window.controller.validate()
        assert any(
            getattr(issue, "code", "") == "MAP_STUDIO_TRANSITION_WOK_SURFACE_WARNING"
            and "no WOK DOOR/transition surface" in getattr(issue, "message", "")
            for issue in issues
        )

        kmap_path = tmp_path / "opening_transition_marker.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_opening = reloaded_payload["rooms"][0]["primitive"]["openings"][-1]
            reloaded_trigger = reloaded_payload["placements"]["triggers"][-1]
            assert reloaded_opening["name"] == "south_door"
            assert reloaded_trigger["tag"] == "south_exit_trigger"
            assert reloaded_trigger["linked_to_module"] == "grnext01"
            assert reloaded_trigger["linked_to_flags"] == 2
            assert reloaded_payload["extra"]["last_opening_transition_marker"]["opening_name"] == "south_door"
            reloaded_issues = reloaded.controller.validate()
            assert any(
                getattr(issue, "code", "") == "MAP_STUDIO_TRANSITION_WOK_SURFACE_WARNING"
                for issue in reloaded_issues
            )
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_validate_reports_unwalkable_player_start_runtime(tmp_path: Path) -> None:
    """Visible entry point and Validate controls report a player start off generated WOK."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        index = combo.findData(preset_key)
        assert index >= 0
        combo.setCurrentIndex(index)
        app.processEvents()

    def player_start_validation_rows() -> list[int]:
        rows: list[int] = []
        for row in range(window.validation_panel.rowCount()):
            item_id = window.validation_panel.item(row, 2)
            message = window.validation_panel.item(row, 1)
            if item_id is None or message is None:
                continue
            if item_id.text().startswith("authored_entry_point:walkable:") or "player start" in message.text().lower():
                rows.append(row)
        return rows

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        select_preset("gameplay")
        window.builder_tab.entryPointAreaLineEdit.setText("grdev01")
        window.builder_tab.entryPointPosXSpinBox.setValue(99.0)
        window.builder_tab.entryPointPosYSpinBox.setValue(99.0)
        window.builder_tab.entryPointPosZSpinBox.setValue(0.0)
        window.builder_tab.entryPointFacingSpinBox.setValue(180.0)
        app.processEvents()

        click_tool("entry_point")

        payload = window.controller.project.extra_sections["authored_module"]
        assert payload["placements"]["entry_point"] == {
            "area_resref": "grdev01",
            "position": [99.0, 99.0, 0.0],
            "facing": math.pi,
        }
        assert window.controller.command_history.undo_label == "Set entry point grdev01"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        select_preset("export")
        click_tool("validate")

        assert window.statusBar().currentMessage().startswith("Validation complete:")
        issues = window.controller.validate()
        assert any(getattr(issue, "code", "") == "MAP_STUDIO_PLAYER_START_NOT_WALKABLE" for issue in issues)
        rows = player_start_validation_rows()
        assert rows
        row = rows[0]
        assert window.validation_panel.item(row, 0).text() == "Error"
        assert "player start" in window.validation_panel.item(row, 1).text().lower()
        assert "move the player start" in window.validation_panel.item(row, 3).text().lower()

        kmap_path = tmp_path / "player_start_not_walkable.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            assert reloaded_payload["placements"]["entry_point"]["position"] == [99.0, 99.0, 0.0]
            reloaded_issues = reloaded.controller.validate()
            assert any(getattr(issue, "code", "") == "MAP_STUDIO_PLAYER_START_NOT_WALKABLE" for issue in reloaded_issues)
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_normals_tools_report_and_repair_bad_winding_runtime(tmp_path: Path) -> None:
    """Visible normal cleanup tools persist winding intent and validation feedback."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_metadata() -> dict:
        return window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]["metadata"]

    def room_metadata() -> dict:
        return window.controller.project.extra_sections["authored_module"]["rooms"][0]["metadata"]

    def issue_codes() -> set[str]:
        return {str(getattr(issue, "code", "") or "") for issue in window.controller.validate()}

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        click_tool("reverse_normals")

        reversed_metadata = primitive_metadata()
        assert reversed_metadata["last_operation"] == "cleanup_floor_plan_normals"
        assert reversed_metadata["normal_cleanup_positive_z"] is False
        assert reversed_metadata["normal_cleanup_flipped_faces"] == 1
        assert room_metadata()["normal_cleanup_positive_z"] is False
        assert window.controller.command_history.undo_label == "Clean grdev01_room01 floor-plan normals"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        audit = reversed_metadata["last_component_edit_audit"]
        assert audit["walkmesh_review_required"] is True
        assert audit["export_candidate_stale"] is True
        assert audit["game_proof_stale"] is True
        assert "MAP_STUDIO_FLOOR_PLAN_BAD_WINDING" in issue_codes()

        click_tool("normals")

        repaired_metadata = primitive_metadata()
        assert repaired_metadata["last_operation"] == "cleanup_floor_plan_normals"
        assert repaired_metadata["normal_cleanup_positive_z"] is True
        assert repaired_metadata["normal_cleanup_flipped_faces"] == 1
        assert room_metadata()["normal_cleanup_positive_z"] is True
        assert "MAP_STUDIO_FLOOR_PLAN_BAD_WINDING" not in issue_codes()

        kmap_path = tmp_path / "normal_cleanup.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_metadata = reloaded_payload["rooms"][0]["primitive"]["metadata"]
            assert reloaded_metadata["last_operation"] == "cleanup_floor_plan_normals"
            assert reloaded_metadata["normal_cleanup_positive_z"] is True
            reloaded_codes = {str(getattr(issue, "code", "") or "") for issue in reloaded.controller.validate()}
            assert "MAP_STUDIO_FLOOR_PLAN_BAD_WINDING" not in reloaded_codes
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_map_studio_controls_stage_export_candidate_runtime(tmp_path: Path, monkeypatch) -> None:
    """Visible Floor/Validate/Stage controls write durable package evidence back into KMAP."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    kmap_path = tmp_path / "visible_stage_export_candidate.kmap"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def accept_package_wizard(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioPackageWizardDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_package_wizard(attempt + 1))
            return
        output = dialog.findChild(QtWidgets.QLineEdit, "mapStudioPackageWizardOutputDirLineEdit")
        assert output is not None
        output.setText(str(tmp_path))
        dry_run = dialog.findChild(QtWidgets.QCheckBox, "mapStudioPackageWizardDryRunCheckBox")
        assert dry_run is not None
        dry_run.setChecked(True)
        resource_table = dialog.findChild(QtWidgets.QTableWidget, "mapStudioPackageWizardResourceReviewTable")
        proof_table = dialog.findChild(QtWidgets.QTableWidget, "mapStudioPackageWizardProofGateTable")
        assert resource_table is not None and resource_table.rowCount() > 0
        assert proof_table is not None and proof_table.rowCount() > 0
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioPackageWizardButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        click_tool("paint_wok")
        click_tool("paint_material")
        click_tool("validate")
        assert window.statusBar().currentMessage().startswith("Validation complete:")
        assert not [
            issue
            for issue in window.controller.validate()
            if str(getattr(issue, "severity", "")).lower() == "error"
        ]

        select_preset("export")
        QtCore.QTimer.singleShot(20, accept_package_wizard)
        click_tool("stage_module")

        payload = window.controller.project.extra_sections["authored_module"]
        assert Path(payload["pack_manifest_path"]).is_file()
        assert Path(payload["proof_manifest_path"]).is_file()
        inventory = payload["package_resource_inventory"]
        assert inventory["readback_ok"] is True
        assert inventory["all_required_runtime_resources_present"] is True
        assert {"new_level.lyt", "new_level.vis", "new_level.pth", "new_level_room01.wok"} <= set(
            payload["runtime_resources"]
        )
        readiness = window.controller.authored_module_readiness().readiness
        assert readiness.capability_stage == "export_candidate"
        assert readiness.can_export_candidate is True
        manifest = json.loads(Path(payload["pack_manifest_path"]).read_text(encoding="utf-8"))
        authored_manifest = manifest["map_studio_authored_module"]
        material_uv = authored_manifest["material_uv"]
        assert material_uv[0]["room_resref"] == "new_level_room01"
        assert material_uv[0]["texture"] == "ruler01"
        assert material_uv[0]["floor_surface_id"] == 4
        assert material_uv[0]["floor_surface_name"] == "STONE"
        assert material_uv[0]["all_mesh_uvs_complete"] is True
        assert material_uv[0]["meshes"][0]["role"] == "room_mesh"
        assert material_uv[0]["meshes"][0]["uv_coordinate_space"] == "mesh_uv0"
        assert material_uv[0]["meshes"][0]["uv_count"] == material_uv[0]["meshes"][0]["vertex_count"]
        assert material_uv[0]["meshes"][0]["face_count"] > 0
        assert window.controller.command_history.undo_label == "Stage authored module new_level"
        assert "Authored module staged" in window.statusBar().currentMessage()

        window.save_as_action.trigger()
        app.processEvents()
        assert kmap_path.is_file()
        assert window.project.dirty is False
    finally:
        window.controller.project.dirty = False
        window.close()

    reader = ModuleEditorWindow()
    try:
        reader.show()
        app.processEvents()

        reader.open_action.trigger()
        app.processEvents()

        reopened_payload = reader.controller.project.extra_sections["authored_module"]
        assert Path(reopened_payload["pack_manifest_path"]).is_file()
        assert Path(reopened_payload["proof_manifest_path"]).is_file()
        assert reopened_payload["package_resource_inventory"]["readback_ok"] is True
        assert reopened_payload["package_resource_inventory"]["all_required_runtime_resources_present"] is True
        assert {"new_level.lyt", "new_level.vis", "new_level.pth", "new_level_room01.wok"} <= set(
            reopened_payload["runtime_resources"]
        )
        reopened_readiness = reader.controller.authored_module_readiness().readiness
        assert reopened_readiness.capability_stage == "export_candidate"
        assert reopened_readiness.can_export_candidate is True
        reopened_manifest = json.loads(Path(reopened_payload["pack_manifest_path"]).read_text(encoding="utf-8"))
        reopened_material_uv = reopened_manifest["map_studio_authored_module"]["material_uv"]
        assert reopened_material_uv[0]["texture"] == "ruler01"
        assert reopened_material_uv[0]["all_mesh_uvs_complete"] is True
        assert reopened_material_uv[0]["meshes"][0]["uv_coordinate_space"] == "mesh_uv0"
        assert reader.findChild(QtWidgets.QToolButton, "mapStudioToolBeltButton_stage_module") is not None
        assert reader.project.dirty is False
    finally:
        reader.controller.project.dirty = False
        reader.close()


def test_t2600_visible_record_proof_dialog_updates_kmap_game_test_state_runtime(tmp_path: Path) -> None:
    """Visible Stage and Record Proof controls write game-test proof metadata into KMAP."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()
    evidence_path = tmp_path / "new_level_warp_proof.png"
    evidence_path.write_bytes(b"visible proof screenshot bytes")

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def accept_package_wizard(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioPackageWizardDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_package_wizard(attempt + 1))
            return
        output = dialog.findChild(QtWidgets.QLineEdit, "mapStudioPackageWizardOutputDirLineEdit")
        assert output is not None
        output.setText(str(tmp_path))
        dry_run = dialog.findChild(QtWidgets.QCheckBox, "mapStudioPackageWizardDryRunCheckBox")
        assert dry_run is not None
        dry_run.setChecked(True)
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioPackageWizardButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    def accept_proof_dialog(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioGameProofDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_proof_dialog(attempt + 1))
            return
        manifest_edit = dialog.findChild(QtWidgets.QLineEdit, "mapStudioProofManifestLineEdit")
        evidence_edit = dialog.findChild(QtWidgets.QLineEdit, "mapStudioProofEvidenceLineEdit")
        tester_edit = dialog.findChild(QtWidgets.QLineEdit, "mapStudioProofTesterLineEdit")
        summary_label = dialog.findChild(QtWidgets.QLabel, "mapStudioProofPackageResourceSummaryLabel")
        assert manifest_edit is not None and Path(manifest_edit.text()).is_file()
        assert evidence_edit is not None
        assert tester_edit is not None
        assert summary_label is not None and "0 missing" in summary_label.text()
        evidence_edit.setText(str(evidence_path))
        tester_edit.setText("visible-runtime")
        for object_name in (
            "mapStudioProofModuleLoadsCheckBox",
            "mapStudioProofModuleIdentityCheckBox",
            "mapStudioProofPlayerFloorCheckBox",
            "mapStudioProofPlaceableVisibleCheckBox",
            "mapStudioProofWalkableFloorCheckBox",
            "mapStudioProofTransitionPathingCheckBox",
            "mapStudioProofNoInheritedContentCheckBox",
        ):
            checkbox = dialog.findChild(QtWidgets.QCheckBox, object_name)
            assert checkbox is not None
            checkbox.setChecked(True)
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioProofButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        click_tool("paint_wok")
        click_tool("paint_material")
        click_tool("validate")

        select_preset("export")
        QtCore.QTimer.singleShot(20, accept_package_wizard)
        click_tool("stage_module")

        payload = window.controller.project.extra_sections["authored_module"]
        assert Path(payload["proof_manifest_path"]).is_file()
        assert window.workflow_panel.proof_button.isEnabled()

        QtCore.QTimer.singleShot(20, accept_proof_dialog)
        window.workflow_panel.proof_button.click()
        app.processEvents()

        payload = window.controller.project.extra_sections["authored_module"]
        readiness = window.controller.authored_module_readiness().readiness
        proof = json.loads(Path(payload["proof_manifest_path"]).read_text(encoding="utf-8"))
        assert payload["game_tested"] is True
        assert payload["in_game_proof_evidence_path"] == str(evidence_path)
        assert payload["in_game_proof"]["tester"] == "visible-runtime"
        assert payload["in_game_proof"]["accepted_checks"] == proof["acceptance_checks"]
        assert readiness is not None
        assert readiness.capability_stage == "game_tested"
        assert readiness.game_tested is True
        assert proof["game_tested"] is True
        assert proof["game_test"]["tester"] == "visible-runtime"
        assert "Map Studio game proof updated" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_terrain_patch_and_sculpt_buttons_mutate_kmap_state_runtime() -> None:
    """Visible terrain patch and sculpt buttons commit heightfield KMAP edits."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    try:
        window.show()
        app.processEvents()

        select_preset("terrain")
        click_tool("terrain_patch")

        terrain_payload = window.controller.project.extra_sections["authored_module"]
        terrain_primitive = terrain_payload["rooms"][0]["primitive"]
        assert terrain_primitive["type"] == "terrain_heightfield"
        assert terrain_primitive["floor_surface_id"] == "grass"
        assert terrain_primitive["metadata"]["supports_terrain_authoring"] is True
        assert terrain_primitive["metadata"]["supports_slope_walkability"] is True
        before_height = float(terrain_primitive["heights"][0][0])
        assert window.controller.command_history.undo_label == "Create authored module grdev01"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        context = window.builder_tab.current_terrain_brush_context()
        assert context["enabled"] is True
        assert context["room_resref"] == "grdev01_room01"
        assert context["brush"] == "raise"

        click_tool("sculpt_raise")

        sculpted_payload = window.controller.project.extra_sections["authored_module"]
        sculpted = sculpted_payload["rooms"][0]["primitive"]
        metadata = sculpted["metadata"]
        assert float(sculpted["heights"][0][0]) == before_height + 0.1
        assert metadata["last_operation"] == "terrain_brush_stroke"
        assert metadata["last_brush"] == "raise"
        assert metadata["last_dirty_region"] == {
            "min_row": 0,
            "max_row": 0,
            "min_column": 0,
            "max_column": 0,
            "changed_sample_count": 1,
        }
        assert metadata["last_brush_slope_report"]["walkable_triangle_count"] == 32
        assert metadata["last_brush_slope_report"]["non_walk_triangle_count"] == 0
        assert metadata["last_brush_performance"]["within_budget"] is True
        assert window.controller.command_history.undo_label == "Apply terrain brush raise"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        status = window.controller.authored_terrain_status()
        assert status["ready"] is True
        assert status["terrain_room_count"] == 1
        assert status["walkable_triangle_count"] == 32
        assert status["non_walk_triangle_count"] == 0
        assert "max slope" in status["summary"]
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_viewport_terrain_brush_drag_paints_instead_of_marquee_runtime() -> None:
    """Left-drag in active Terrain Brush mode paints dirty terrain samples, not a selection box."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = QtGhostRiggerMainWindow(app_root=ROOT, startup_input={"skip_prelaunch": True})

    def click_tool(module_window, action_key: str) -> None:
        belt = module_window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(module_window, preset_key: str) -> None:
        combo = module_window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def mouse_event(kind, x: float, y: float, button, buttons, modifiers=QtCore.Qt.NoModifier):
        return QtGui.QMouseEvent(kind, QtCore.QPointF(x, y), button, buttons, modifiers)

    try:
        window.show()
        app.processEvents()
        window.modules_action.trigger()
        app.processEvents()
        module_window = window.module_editor_window
        assert module_window is not None

        select_preset(module_window, "terrain")
        click_tool(module_window, "terrain_patch")
        module_window._sync_map_studio_terrain_brush_context(force_enabled=True)

        panel = module_window.viewport_panel
        canvas = panel.viewport.canvas
        samples = [(1, 1, 1.0), (1, 2, 1.0), (2, 2, 1.0)]
        panel._terrain_sample_at_event = lambda _event: samples.pop(0) if samples else (2, 2, 1.0)

        press = mouse_event(QtCore.QEvent.MouseButtonPress, 80, 80, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton)
        move = mouse_event(QtCore.QEvent.MouseMove, 120, 96, QtCore.Qt.NoButton, QtCore.Qt.LeftButton)
        release = mouse_event(QtCore.QEvent.MouseButtonRelease, 120, 96, QtCore.Qt.LeftButton, QtCore.Qt.NoButton)

        assert panel.eventFilter(canvas, press) is True
        assert not panel.viewport._selection_rubber_band.isVisible()
        assert panel.eventFilter(canvas, move) is True
        assert not panel.viewport._selection_rubber_band.isVisible()
        assert panel.eventFilter(canvas, release) is True
        assert not panel.viewport._selection_rubber_band.isVisible()

        # The shared viewport must fail closed while Sculpt Mode owns the
        # pointer.  Even if the Map Studio handler misses an Alt+LMB event, the
        # Maya navigation profile may not start orbiting the camera.
        viewport = panel.viewport
        original_handler = viewport._gr_map_studio_viewport_input_handler
        original_profile = viewport._navigation_profile
        viewport._gr_map_studio_viewport_input_handler = lambda *_args: False
        viewport._navigation_profile = "maya"
        camera_before = (float(viewport.camera.azimuth), float(viewport.camera.elevation))
        blocked_press = mouse_event(
            QtCore.QEvent.MouseButtonPress,
            96,
            96,
            QtCore.Qt.LeftButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.AltModifier,
        )
        blocked_move = mouse_event(
            QtCore.QEvent.MouseMove,
            140,
            120,
            QtCore.Qt.NoButton,
            QtCore.Qt.LeftButton,
            QtCore.Qt.AltModifier,
        )
        assert viewport.eventFilter(canvas, blocked_press) is True
        assert viewport.eventFilter(canvas, blocked_move) is True
        assert viewport._nav_dragging == ""
        assert (float(viewport.camera.azimuth), float(viewport.camera.elevation)) == camera_before
        viewport._navigation_profile = original_profile
        viewport._gr_map_studio_viewport_input_handler = original_handler

        payload = module_window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        assert metadata["last_operation"] == "terrain_brush_stroke"
        assert metadata["last_brush"] == "raise"
        assert metadata["dirty_region_only"] is True
        room_resref = module_window.builder_tab.current_terrain_brush_context()["room_resref"]
        assert module_window.controller.command_history.undo_label == f"Sculpt terrain raise on {room_resref}"
    finally:
        module_window = getattr(window, "module_editor_window", None)
        if module_window is not None:
            module_window.controller.project.dirty = False
            module_window.close()
        window.close()


def test_t2600_viewport_terrain_brush_alt_right_drag_changes_size_and_hardness_runtime() -> None:
    """Alt+right-drag edits Photoshop-style terrain brush size and hardness controls."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def mouse_event(kind, x: float, y: float, button, buttons, modifiers=QtCore.Qt.NoModifier):
        position = QtCore.QPointF(x, y)
        return QtGui.QMouseEvent(kind, position, position, position, button, buttons, modifiers)

    try:
        window.show()
        app.processEvents()
        window.create_map_studio_starter_terrain()
        window.builder_tab.terrainRadiusSpinBox.setValue(1)
        window.builder_tab.terrainSmoothStrengthSpinBox.setValue(0.5)
        window._sync_map_studio_terrain_brush_context(force_enabled=True)

        panel = window.viewport_panel
        canvas = panel.viewport.canvas
        press = mouse_event(
            QtCore.QEvent.MouseButtonPress,
            100,
            100,
            QtCore.Qt.RightButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.AltModifier,
        )
        move = mouse_event(
            QtCore.QEvent.MouseMove,
            148,
            64,
            QtCore.Qt.NoButton,
            QtCore.Qt.RightButton,
            QtCore.Qt.AltModifier,
        )
        release = mouse_event(
            QtCore.QEvent.MouseButtonRelease,
            148,
            64,
            QtCore.Qt.RightButton,
            QtCore.Qt.NoButton,
            QtCore.Qt.AltModifier,
        )

        assert panel.eventFilter(canvas, press) is True
        assert panel.eventFilter(canvas, move) is True
        assert panel.eventFilter(canvas, release) is True

        assert window.builder_tab.terrainRadiusSpinBox.value() == 4
        assert round(float(window.builder_tab.terrainHardnessSpinBox.value()), 2) == 0.70
        context = window.builder_tab.current_terrain_brush_context()
        assert context["radius"] == 4
        assert round(float(context["hardness"]), 2) == 0.70
        assert panel._terrain_brush_context["radius"] == 4
        assert round(float(panel._terrain_brush_context["hardness"]), 2) == 0.70
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_viewport_terrain_sculpt_alt_middle_drag_pans_without_painting_runtime() -> None:
    """Alt+MMB deliberately pans the sculpt camera while bare LMB remains paint-only."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtGui, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def mouse_event(kind, x: float, y: float, button, buttons):
        position = QtCore.QPointF(x, y)
        return QtGui.QMouseEvent(
            kind,
            position,
            position,
            position,
            button,
            buttons,
            QtCore.Qt.AltModifier,
        )

    try:
        window.show()
        app.processEvents()
        window.create_map_studio_starter_terrain()
        window._sync_map_studio_terrain_brush_context(force_enabled=True)

        panel = window.viewport_panel
        canvas = panel.viewport.canvas
        camera = panel.viewport.camera
        target_before = tuple(float(value) for value in camera.target)
        angles_before = (float(camera.azimuth), float(camera.elevation))
        press = mouse_event(
            QtCore.QEvent.MouseButtonPress,
            100,
            100,
            QtCore.Qt.MiddleButton,
            QtCore.Qt.MiddleButton,
        )
        move = mouse_event(
            QtCore.QEvent.MouseMove,
            136,
            118,
            QtCore.Qt.NoButton,
            QtCore.Qt.MiddleButton,
        )
        release = mouse_event(
            QtCore.QEvent.MouseButtonRelease,
            136,
            118,
            QtCore.Qt.MiddleButton,
            QtCore.Qt.NoButton,
        )

        assert panel.eventFilter(canvas, press) is True
        assert panel.eventFilter(canvas, move) is True
        assert panel.eventFilter(canvas, release) is True
        assert tuple(float(value) for value in camera.target) != target_before
        assert (float(camera.azimuth), float(camera.elevation)) == angles_before
        assert panel._terrain_brush_drag is None
        assert panel._terrain_camera_drag is None
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_terrain_brush_shelf_persists_kmap_metadata_runtime(tmp_path: Path) -> None:
    """Visible terrain shelf brushes all record durable dirty-region KMAP state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        index = combo.findData(preset_key)
        assert index >= 0
        combo.setCurrentIndex(index)
        app.processEvents()

    def terrain_primitive() -> dict:
        return window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]

    brush_actions = (
        ("sculpt_noise", "noise"),
        ("sculpt_terrace", "terrace"),
        ("sculpt_plateau", "plateau"),
        ("sculpt_flatten", "flatten"),
        ("sculpt_lower", "lower"),
        ("sculpt_smooth", "smooth"),
        ("sculpt_erode", "erode"),
        ("sculpt_ramp", "ramp"),
        ("sculpt_slope", "slope"),
        ("sculpt_pinch", "pinch"),
        ("sculpt_erase", "erase"),
    )

    try:
        window.show()
        app.processEvents()

        select_preset("terrain")
        click_tool("terrain_patch")
        window.builder_tab.terrainRowSpinBox.setValue(2)
        window.builder_tab.terrainColumnSpinBox.setValue(2)
        window.builder_tab.terrainRadiusSpinBox.setValue(1)
        window.builder_tab.terrainDeltaSpinBox.setValue(0.25)
        window.builder_tab.terrainHeightSpinBox.setValue(0.35)
        window.builder_tab.terrainSmoothIterationsSpinBox.setValue(2)
        window.builder_tab.terrainSmoothStrengthSpinBox.setValue(0.75)
        app.processEvents()

        first_heights = [list(row) for row in terrain_primitive()["heights"]]
        seen_brushes: list[str] = []
        for action_key, brush in brush_actions:
            click_tool(action_key)

            primitive = terrain_primitive()
            metadata = primitive["metadata"]
            seen_brushes.append(brush)
            assert metadata["last_operation"] == "terrain_brush_stroke"
            assert metadata["last_brush"] == brush
            assert metadata["source"] == "map_studio:terrain_brush_stroke"
            assert metadata["dirty_region_only"] is True
            assert metadata["last_dirty_region"]["changed_sample_count"] >= 0
            assert metadata["last_brush_radius"] == 1
            assert metadata["last_brush_delta"] == 0.25
            assert metadata["last_brush_height"] == 0.35
            assert metadata["last_brush_performance"]["within_budget"] is True
            assert "last_brush_slope_report" in metadata
            assert window.controller.command_history.undo_label == f"Apply terrain brush {brush}"
            assert window.controller.command_history.undo_stack[-1].stale_outputs == (
                "MDL",
                "MDX",
                "WOK",
                "LYT",
                "VIS",
                "PTH",
                ".mod",
            )
            assert window.statusBar().currentMessage().startswith(f"Applied terrain brush {brush};")

        final_primitive = terrain_primitive()
        assert final_primitive["heights"] != first_heights
        assert seen_brushes == [brush for _action, brush in brush_actions]

        boundary = window.controller.map_studio_export_object_boundaries()[0]
        boundary_metadata = boundary.to_metadata()
        assert boundary.terrain_authoring_status == "dirty_region_sculpted"
        assert boundary.terrain_last_operation == "terrain_brush_stroke"
        assert boundary.terrain_last_brush == "erase"
        assert boundary_metadata["terrain_last_brush"] == "erase"
        readiness_boundary = window.controller.authored_module_readiness().readiness.metadata["export_object_boundaries"][0]
        assert readiness_boundary["terrain_last_brush"] == "erase"

        kmap_path = tmp_path / "visible_terrain_brush_shelf.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_primitive = reloaded_payload["rooms"][0]["primitive"]
            reloaded_metadata = reloaded_primitive["metadata"]
            assert reloaded_primitive["heights"] == final_primitive["heights"]
            assert reloaded_metadata["last_operation"] == "terrain_brush_stroke"
            assert reloaded_metadata["last_brush"] == "erase"
            assert reloaded_metadata["last_brush_performance"]["within_budget"] is True
            assert reloaded_metadata["last_brush_slope_report"]["walkable_triangle_count"] >= 0
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_validate_reports_steep_terrain_slope_warning_runtime(tmp_path: Path) -> None:
    """Visible terrain sculpting reports steep slope readiness warnings before export."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        index = combo.findData(preset_key)
        assert index >= 0
        combo.setCurrentIndex(index)
        app.processEvents()

    def slope_warning_rows() -> list[int]:
        rows: list[int] = []
        for row in range(window.validation_panel.rowCount()):
            message = window.validation_panel.item(row, 1)
            if message is not None and "steeper than" in message.text() and "non-walk" in message.text():
                rows.append(row)
        return rows

    try:
        window.show()
        app.processEvents()

        select_preset("terrain")
        click_tool("terrain_patch")
        window.builder_tab.terrainDeltaSpinBox.setValue(5.0)
        app.processEvents()
        click_tool("sculpt_raise")

        payload = window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        slope_report = metadata["last_brush_slope_report"]
        assert slope_report["max_slope_degrees"] > 35.0
        assert slope_report["non_walk_triangle_count"] == 2
        assert "steeper than 35.0 degrees" in slope_report["warnings"][0]
        assert window.controller.command_history.undo_label == "Apply terrain brush raise"

        select_preset("export")
        click_tool("validate")

        assert window.statusBar().currentMessage().startswith("Validation complete:")
        rows = slope_warning_rows()
        assert rows
        row = rows[0]
        assert window.validation_panel.item(row, 0).text() == "Warning"
        assert "steeper than 35.0 degrees" in window.validation_panel.item(row, 1).text()
        assert "non-walk" in window.validation_panel.item(row, 1).text()

        kmap_path = tmp_path / "steep_terrain_slope.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_report = reloaded_payload["rooms"][0]["primitive"]["metadata"]["last_brush_slope_report"]
            assert reloaded_report["non_walk_triangle_count"] == 2
            reloaded_issues = reloaded.controller.validate()
            assert any("steeper than 35.0 degrees" in getattr(issue, "message", "") for issue in reloaded_issues)
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_validate_table_reports_wok_topology_blockers_runtime(monkeypatch) -> None:
    """Visible Validate table displays invalid, degenerate, non-manifold, and open WOK topology rows."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from types import SimpleNamespace

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        index = combo.findData(preset_key)
        assert index >= 0
        combo.setCurrentIndex(index)
        app.processEvents()

    def row_for_item_prefix(prefix: str) -> int:
        for row in range(window.validation_panel.rowCount()):
            item = window.validation_panel.item(row, 2)
            if item is not None and item.text().startswith(prefix):
                return row
        raise AssertionError(f"Missing validation-table row for {prefix!r}")

    readiness = SimpleNamespace(
        metadata={
            "invalid_wok_face_count": 1,
            "degenerate_wok_face_count": 2,
            "non_manifold_wok_edge_count": 3,
            "open_wok_edge_count": 4,
        },
        inputs=(),
        blocking_messages=(
            "Room grbad generated WOK has 1 face(s) with invalid vertex indices.",
            "Room grbad generated WOK has 2 degenerate face(s).",
            "Room grbad generated WOK has 3 non-manifold walkable edge(s).",
        ),
        missing_runtime_resources=(),
        toolchain=(),
        warnings=("Room grbad generated WOK has 4 open/boundary walkable edge(s).",),
        can_preview=False,
        ready_for_game_test=False,
        game_tested=False,
    )
    readiness_result = SimpleNamespace(readiness=readiness, warnings=(), blocking_messages=())

    try:
        window.show()
        app.processEvents()
        monkeypatch.setattr(window.controller, "authored_module_readiness", lambda: readiness_result)

        select_preset("export")
        click_tool("validate")

        issues = window.controller.validate()
        assert {
            "MAP_STUDIO_WOK_INVALID_TRIANGLE",
            "MAP_STUDIO_WOK_DEGENERATE_TRIANGLE",
            "MAP_STUDIO_WOK_NON_MANIFOLD_EDGE",
            "MAP_STUDIO_WOK_OPEN_EDGE_WARNING",
        } <= {
            str(getattr(issue, "code", "") or "") for issue in issues
        }

        invalid_row = row_for_item_prefix("authored_wok_invalid_triangle:blocker")
        assert window.validation_panel.item(invalid_row, 0).text() == "Error"
        assert "invalid vertex indices" in window.validation_panel.item(invalid_row, 1).text()
        assert "valid vertices" in window.validation_panel.item(invalid_row, 3).text()

        degenerate_row = row_for_item_prefix("authored_wok_degenerate_triangle:blocker")
        assert window.validation_panel.item(degenerate_row, 0).text() == "Error"
        assert "degenerate" in window.validation_panel.item(degenerate_row, 1).text()
        assert "zero-area WOK triangles" in window.validation_panel.item(degenerate_row, 3).text()

        non_manifold_row = row_for_item_prefix("authored_wok_non_manifold_edge:blocker")
        assert window.validation_panel.item(non_manifold_row, 0).text() == "Error"
        assert "non-manifold walkable edge" in window.validation_panel.item(non_manifold_row, 1).text()
        assert "valid ownership" in window.validation_panel.item(non_manifold_row, 3).text()

        open_edge_row = row_for_item_prefix("authored_wok_open_edge:warning")
        assert window.validation_panel.item(open_edge_row, 0).text() == "Warning"
        assert "open/boundary walkable edge" in window.validation_panel.item(open_edge_row, 1).text()
        assert "intentional room perimeter" in window.validation_panel.item(open_edge_row, 3).text()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_validate_reports_stale_package_after_modeling_edit_runtime(tmp_path: Path) -> None:
    """Visible Validate reports stale package/proof state after staged output is edited."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtCore, QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_preset(preset_key: str) -> None:
        combo = window.map_studio_tool_belt_preset_combo
        for index in range(combo.count()):
            if combo.itemData(index) == preset_key:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing Map Studio tool-belt preset {preset_key!r}")

    def accept_package_wizard(attempt: int = 0) -> None:
        dialog = app.activeModalWidget()
        if dialog is None or dialog.objectName() != "mapStudioPackageWizardDialog":
            if attempt < 25:
                QtCore.QTimer.singleShot(20, lambda: accept_package_wizard(attempt + 1))
            return
        output = dialog.findChild(QtWidgets.QLineEdit, "mapStudioPackageWizardOutputDirLineEdit")
        assert output is not None
        output.setText(str(tmp_path))
        dry_run = dialog.findChild(QtWidgets.QCheckBox, "mapStudioPackageWizardDryRunCheckBox")
        assert dry_run is not None
        dry_run.setChecked(True)
        buttons = dialog.findChild(QtWidgets.QDialogButtonBox, "mapStudioPackageWizardButtons")
        assert buttons is not None
        buttons.button(QtWidgets.QDialogButtonBox.Ok).click()

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        click_tool("paint_wok")
        click_tool("paint_material")
        select_preset("export")
        QtCore.QTimer.singleShot(20, accept_package_wizard)
        click_tool("stage_module")

        staged_payload = window.controller.project.extra_sections["authored_module"]
        assert Path(staged_payload["pack_manifest_path"]).is_file()
        assert Path(staged_payload["proof_manifest_path"]).is_file()

        select_preset("component")
        window.builder_tab.primitiveTranslateXSpinBox.setValue(0.25)
        click_tool("move")

        edited_payload = window.controller.project.extra_sections["authored_module"]
        invalidation = edited_payload["export_proof_invalidation"]
        assert edited_payload["proof_manifest_path"] == staged_payload["proof_manifest_path"]
        assert invalidation["invalidates_previous_export"] is True
        assert invalidation["invalidates_game_proof"] is True
        assert invalidation["latest_summary"] == "Move primitive new_level_room01_floor"
        assert invalidation["stale_outputs"] == ["MDL", "MDX", "WOK", "LYT", "VIS", "PTH", ".mod"]

        click_tool("validate")

        stale_rows = []
        for row in range(window.validation_panel.rowCount()):
            item_id = window.validation_panel.item(row, 2)
            if item_id is not None and item_id.text() == "authored_module:export_proof_stale":
                stale_rows.append(row)
        assert stale_rows
        row = stale_rows[0]
        assert window.validation_panel.item(row, 0).text() == "Warning"
        assert "Stale outputs: MDL, MDX, WOK, LYT, VIS, PTH, .mod" in window.validation_panel.item(row, 1).text()
        assert "record fresh in-game proof" in window.validation_panel.item(row, 3).text()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_required_blockout_buttons_create_distinct_kmap_primitives_runtime(tmp_path: Path) -> None:
    """Visible blockout buttons create the required KOTOR-authored primitive types."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    expected_blockout = {
        "wall": ("wall", False),
        "cube": ("cube", False),
        "ramp": ("ramp", True),
        "stairs": ("stairs", True),
        "door_frame": ("door_frame", False),
        "arch": ("arch", False),
    }

    try:
        window.show()
        app.processEvents()

        click_tool("floor")
        rows = primitive_rows()
        floor = rows["new_level_room01_floor"]
        assert getattr(floor, "primitive_type") == "plane"
        assert getattr(floor, "supports_walkmesh_surface") is True
        assert window.controller.command_history.undo_label == "Add floor primitive"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        created_names: dict[str, str] = {}
        for action_key, (primitive_type, supports_wok) in expected_blockout.items():
            before_names = set(primitive_rows())
            click_tool(action_key)
            after_rows = primitive_rows()
            new_names = sorted(set(after_rows) - before_names)
            assert len(new_names) == 1
            created = after_rows[new_names[0]]
            created_names[action_key] = new_names[0]
            assert getattr(created, "primitive_type") == primitive_type
            assert getattr(created, "supports_walkmesh_surface") is supports_wok
            assert window.controller.command_history.undo_label == f"Add {action_key} primitive"
            assert window.controller.command_history.undo_stack[-1].metadata["primitive_kind"] == action_key
            assert window.controller.command_history.undo_stack[-1].stale_outputs == (
                "MDL",
                "MDX",
                "WOK",
                "LYT",
                "VIS",
                "PTH",
                ".mod",
            )

        payload = window.controller.project.extra_sections["authored_module"]
        composition = payload["rooms"][0]["primitive"]
        authored_types = {
            str(item.get("name") or ""): str(item.get("type") or "")
            for item in composition.get("primitives", ())
        }
        for action_key, (primitive_type, _supports_wok) in expected_blockout.items():
            assert authored_types[created_names[action_key]] == primitive_type
        assert composition["metadata"]["last_added_primitive_kind"] == "arch"

        kmap_path = tmp_path / "blockout_primitives.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_rows = {
                str(getattr(row, "primitive_name", "") or ""): row
                for row in reloaded.controller.authored_room_primitive_transforms()
            }
            assert reloaded_rows["new_level_room01_floor"].primitive_type == "plane"
            for action_key, (primitive_type, supports_wok) in expected_blockout.items():
                row = reloaded_rows[created_names[action_key]]
                assert row.primitive_type == primitive_type
                assert row.supports_walkmesh_surface is supports_wok
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_center_pivot_and_freeze_update_kmap_without_moving_bounds_runtime(tmp_path: Path) -> None:
    """Visible Pivot and Freeze commands update authored KMAP transforms without moving geometry."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def current_primitive() -> dict:
        data = window.builder_tab.roomPrimitiveTransformComboBox.currentData()
        assert isinstance(data, dict)
        return dict(data)

    def set_visible_transform(
        *,
        translation: tuple[float, float, float],
        scale: tuple[float, float, float],
        pivot: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        window.builder_tab.primitiveTranslateXSpinBox.setValue(translation[0])
        window.builder_tab.primitiveTranslateYSpinBox.setValue(translation[1])
        window.builder_tab.primitiveTranslateZSpinBox.setValue(translation[2])
        window.builder_tab.primitiveRotateZSpinBox.setValue(0.0)
        window.builder_tab.primitiveScaleXSpinBox.setValue(scale[0])
        window.builder_tab.primitiveScaleYSpinBox.setValue(scale[1])
        window.builder_tab.primitiveScaleZSpinBox.setValue(scale[2])
        window.builder_tab.primitivePivotXSpinBox.setValue(pivot[0])
        window.builder_tab.primitivePivotYSpinBox.setValue(pivot[1])
        window.builder_tab.primitivePivotZSpinBox.setValue(pivot[2])
        window.builder_tab.applyPrimitiveTransformButton.click()
        app.processEvents()

    def overlay_for(selection: dict):
        return window.controller.map_studio_universal_transform_overlay(
            room_resref=str(selection["room_resref"]),
            primitive_name=str(selection["primitive_name"]),
        )

    def rounded_triplet(values: object) -> tuple[float, float, float]:
        return tuple(round(float(value), 6) for value in tuple(values))  # type: ignore[arg-type]

    def primitive_row(name: str) -> object:
        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }
        return rows[name]

    try:
        window.show()
        app.processEvents()

        click_tool("cube")
        pivot_selection = current_primitive()
        assert pivot_selection["primitive_type"] == "cube"
        set_visible_transform(translation=(1.0, 2.0, 0.0), scale=(2.0, 1.0, 2.0))
        pivot_selection = current_primitive()
        pivot_before = overlay_for(pivot_selection)

        click_tool("center_pivot")

        pivot_after = overlay_for(pivot_selection)
        assert rounded_triplet(pivot_after.bounds_min) == rounded_triplet(pivot_before.bounds_min)
        assert rounded_triplet(pivot_after.bounds_max) == rounded_triplet(pivot_before.bounds_max)
        assert rounded_triplet(pivot_after.center) == rounded_triplet(pivot_before.center)
        centered = primitive_row(str(pivot_selection["primitive_name"]))
        assert tuple(round(float(value), 6) for value in getattr(centered, "pivot")) == (0.0, 0.0, 0.5)
        assert tuple(round(float(value), 6) for value in getattr(centered, "translation")) == (1.0, 2.0, 0.5)
        assert window.controller.command_history.undo_label == f"Center pivot {pivot_selection['primitive_name']}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        click_tool("cube")
        freeze_selection = current_primitive()
        assert freeze_selection["primitive_type"] == "cube"
        assert freeze_selection["primitive_name"] != pivot_selection["primitive_name"]
        set_visible_transform(translation=(1.0, 2.0, 3.0), scale=(2.0, 3.0, 4.0))
        freeze_selection = current_primitive()
        freeze_before = overlay_for(freeze_selection)

        click_tool("freeze_transform")

        freeze_after = overlay_for(freeze_selection)
        assert rounded_triplet(freeze_after.bounds_min) == rounded_triplet(freeze_before.bounds_min)
        assert rounded_triplet(freeze_after.bounds_max) == rounded_triplet(freeze_before.bounds_max)
        assert rounded_triplet(freeze_after.center) == rounded_triplet(freeze_before.center)
        frozen = primitive_row(str(freeze_selection["primitive_name"]))
        assert tuple(round(float(value), 6) for value in getattr(frozen, "translation")) == (0.0, 0.0, 0.0)
        assert tuple(round(float(value), 6) for value in getattr(frozen, "scale")) == (1.0, 1.0, 1.0)
        assert window.controller.command_history.undo_label == f"Freeze transform {freeze_selection['primitive_name']}"

        payload = window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        assert metadata["last_operation"] == "freeze_primitive_transform"
        assert metadata["center_pivot_space"] == "primitive_local_preserve_world_geometry"
        assert metadata["freeze_transform_space"] == "primitive_local_parametric_unrotated"
        frozen_payload = next(
            item
            for item in payload["rooms"][0]["primitive"]["primitives"]
            if item.get("instance_name") == freeze_selection["primitive_name"]
        )
        assert frozen_payload["size"] == [2.0, 3.0, 4.0]
        assert frozen_payload["center"] == [1.0, 2.0, 5.0]
        assert frozen_payload["transform"] == {
            "translation": [0.0, 0.0, 0.0],
            "rotation_degrees_z": 0.0,
            "scale": [1.0, 1.0, 1.0],
            "pivot": [0.0, 0.0, 0.0],
        }

        kmap_path = tmp_path / "pivot_freeze.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_rows = {
                str(getattr(row, "primitive_name", "") or ""): row
                for row in reloaded.controller.authored_room_primitive_transforms()
            }
            reloaded_centered = reloaded_rows[str(pivot_selection["primitive_name"])]
            assert tuple(round(float(value), 6) for value in getattr(reloaded_centered, "pivot")) == (0.0, 0.0, 0.5)
            reloaded_frozen = reloaded_rows[str(freeze_selection["primitive_name"])]
            assert tuple(round(float(value), 6) for value in getattr(reloaded_frozen, "translation")) == (0.0, 0.0, 0.0)
            assert tuple(round(float(value), 6) for value in getattr(reloaded_frozen, "scale")) == (1.0, 1.0, 1.0)
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_duplicate_special_and_edge_normals_persist_kmap_metadata_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    """Visible Duplicate Special and edge normal tools write durable KMAP metadata."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    kmap_path = tmp_path / "visible_duplicate_special_normals.kmap"

    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(kmap_path), "GhostRigger KMAP (*.kmap)"),
    )

    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def primitive_rows() -> dict[str, object]:
        return {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }

    def select_primitive(primitive_name: str) -> None:
        combo = window.findChild(QtWidgets.QComboBox, "mapStudioRoomPrimitiveTransformComboBox")
        assert combo is not None
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and data.get("primitive_name") == primitive_name:
                combo.setCurrentIndex(index)
                app.processEvents()
                return
        raise AssertionError(f"Missing visible primitive selection row {primitive_name!r}")

    try:
        window.show()
        app.processEvents()

        click_tool("cube")
        cube = next(row for row in primitive_rows().values() if getattr(row, "primitive_type", "") == "cube")
        select_primitive(cube.primitive_name)

        count_spin = window.findChild(QtWidgets.QSpinBox, "mapStudioDuplicateSpecialCountSpinBox")
        offset_x = window.findChild(QtWidgets.QDoubleSpinBox, "mapStudioDuplicateSpecialOffsetXSpinBox")
        assert count_spin is not None
        assert offset_x is not None
        count_spin.setValue(2)
        offset_x.setValue(0.5)
        app.processEvents()

        count_before = len(primitive_rows())
        click_tool("duplicate_special")

        duplicated = primitive_rows()
        first_duplicate = f"{cube.primitive_name}_dup_01"[:32]
        second_duplicate = f"{cube.primitive_name}_dup_02"[:32]
        assert len(duplicated) == count_before + 2
        assert first_duplicate in duplicated
        assert second_duplicate in duplicated
        assert duplicated[first_duplicate].translation[0] == cube.translation[0] + 0.5
        assert duplicated[second_duplicate].translation[0] == cube.translation[0] + 1.0
        payload = window.controller.project.extra_sections["authored_module"]
        metadata = payload["rooms"][0]["primitive"]["metadata"]
        duplicate_batch = metadata["duplicate_special_batches"][0]
        assert metadata["last_operation"] == "duplicate_special"
        assert metadata["last_duplicated_primitive"] == cube.primitive_name
        assert metadata["last_duplicate_special_names"] == [first_duplicate, second_duplicate]
        assert duplicate_batch["source_primitive"] == cube.primitive_name
        assert duplicate_batch["generated_primitive_names"] == [first_duplicate, second_duplicate]
        assert duplicate_batch["translation_offset"] == [0.5, 0.0, 0.0]
        assert window.controller.command_history.undo_label == f"Duplicate primitive {cube.primitive_name}"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )

        select_primitive(cube.primitive_name)
        click_tool("soften_edges")
        payload = window.controller.project.extra_sections["authored_module"]
        edge_policy = payload["rooms"][0]["primitive"]["metadata"]["edge_normal_policy_by_target"][cube.primitive_name]
        assert edge_policy["edge_normal_policy"] == "soft"
        assert edge_policy["edge_normal_policy_operation"] == "soften_edges"
        assert edge_policy["edge_normal_policy_coordinate_space"] == "authored_room_composition_primitive_edges"
        assert window.controller.command_history.undo_label == "Soften edges"
        boundary = window.controller.map_studio_export_object_boundaries()[0]
        assert boundary.normal_policy_status == "authored_visual_normal_policy"
        assert cube.primitive_name in boundary.normal_policy_summary

        click_tool("harden_edges")
        payload = window.controller.project.extra_sections["authored_module"]
        hard_policy = payload["rooms"][0]["primitive"]["metadata"]["edge_normal_policy_by_target"][cube.primitive_name]
        assert hard_policy["edge_normal_policy"] == "hard"
        assert hard_policy["edge_normal_policy_operation"] == "harden_edges"
        assert window.controller.command_history.undo_label == "Harden edges"

        window.save_as_action.trigger()
        app.processEvents()
        assert kmap_path.is_file()
    finally:
        window.controller.project.dirty = False
        window.close()

    reader = ModuleEditorWindow()
    try:
        reader.show()
        app.processEvents()

        reader.open_action.trigger()
        app.processEvents()

        reopened = reader.controller.project.extra_sections["authored_module"]
        reopened_metadata = reopened["rooms"][0]["primitive"]["metadata"]
        assert reopened_metadata["last_operation"] == "harden_edges"
        assert reopened_metadata["last_duplicate_special_names"] == [first_duplicate, second_duplicate]
        assert reopened_metadata["duplicate_special_batches"][0]["generated_primitive_names"] == [
            first_duplicate,
            second_duplicate,
        ]
        assert reopened_metadata["edge_normal_policy_by_target"][cube.primitive_name]["edge_normal_policy"] == "hard"
        reopened_rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in reader.controller.authored_room_primitive_transforms()
        }
        assert first_duplicate in reopened_rows
        assert second_duplicate in reopened_rows
    finally:
        reader.controller.project.dirty = False
        reader.close()


def test_t2911_visible_wok_surface_combo_paints_required_kotor_intent_runtime(tmp_path: Path) -> None:
    """Visible WOK surface choices round-trip required KOTOR intent into saved KMAP state."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    required_surfaces = {
        "walkable": ("4", "STONE", True),
        "non_walk": ("7", "NON_WALK", False),
        "door_transition": ("18", "DOOR", True),
        "water": ("6", "WATER", True),
        "grass": ("3", "GRASS", True),
        "metal": ("10", "METAL", True),
        "visual_only": ("8", "TRANSPARENT", False),
    }

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    def select_surface(surface_id: str) -> dict:
        combo = window.builder_tab.primitiveSurfaceComboBox
        assert combo.isEnabled()
        for index in range(combo.count()):
            data = combo.itemData(index)
            if isinstance(data, dict) and str(data.get("surface_id") or "") == surface_id:
                combo.setCurrentIndex(index)
                app.processEvents()
                return dict(data)
        raise AssertionError(f"Missing visible WOK surface choice {surface_id}")

    def floor_row() -> object:
        rows = {
            str(getattr(row, "primitive_name", "") or ""): row
            for row in window.controller.authored_room_primitive_transforms()
        }
        return rows["new_level_room01_floor"]

    try:
        window.show()
        app.processEvents()

        click_tool("floor")

        for semantic, (surface_id, surface_name, walkable) in required_surfaces.items():
            combo_data = select_surface(surface_id)
            assert str(combo_data.get("name") or "").upper() == surface_name
            assert bool(combo_data.get("walkable")) is walkable

            click_tool("paint_wok")

            styled_floor = floor_row()
            assert str(getattr(styled_floor, "surface_id")) == surface_id
            assert str(getattr(styled_floor, "surface_name")).upper() == surface_name
            assert window.controller.command_history.undo_label == "Style primitive new_level_room01_floor"
            assert window.controller.command_history.undo_stack[-1].stale_outputs == (
                "MDL",
                "MDX",
                "WOK",
                "LYT",
                "VIS",
                "PTH",
                ".mod",
            )

            primitive = window.controller.project.extra_sections["authored_module"]["rooms"][0]["primitive"]
            floor_payload = primitive["floor"]
            metadata = floor_payload["material"]["metadata"]
            assert str(floor_payload["surface_id"]) == surface_id
            assert str(metadata["surface_id"]) == surface_id
            assert str(metadata["surface_name"]).upper() == surface_name
            assert primitive["metadata"]["last_style_edit"] == "new_level_room01_floor"

        kmap_path = tmp_path / "surface_intent.kmap"
        window.controller.save_project(kmap_path)

        reloaded = ModuleEditorWindow()
        try:
            reloaded.controller.open_project(kmap_path)
            reloaded_payload = reloaded.controller.project.extra_sections["authored_module"]
            reloaded_floor = reloaded_payload["rooms"][0]["primitive"]["floor"]
            assert str(reloaded_floor["surface_id"]) == required_surfaces["visual_only"][0]
            assert str(reloaded_floor["material"]["metadata"]["surface_name"]).upper() == required_surfaces["visual_only"][1]
        finally:
            reloaded.controller.project.dirty = False
            reloaded.close()
    finally:
        window.controller.project.dirty = False
        window.close()


def test_t2600_visible_inset_button_edits_floor_plan_kmap_state_runtime() -> None:
    """The visible Inset component tool routes through the authored KMAP command path."""

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _configure_native_python_roots()

    from PySide6 import QtWidgets
    from src.gui.windows.module_editor_window import ModuleEditorWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ModuleEditorWindow()

    def click_tool(action_key: str) -> None:
        belt = window.findChild(QtWidgets.QWidget, "mapStudioToolBeltWidget")
        assert belt is not None
        button = belt.findChild(QtWidgets.QToolButton, f"mapStudioToolBeltButton_{action_key}")
        assert button is not None
        assert button.isEnabled()
        button.click()
        app.processEvents()

    try:
        window.show()
        app.processEvents()

        click_tool("create_room")
        before = window.controller.project.extra_sections["authored_module"]

        click_tool("inset")

        after = window.controller.project.extra_sections["authored_module"]
        assert before != after
        assert window.controller.command_history.undo_label == "Inset grdev01_room01"
        assert window.controller.command_history.undo_stack[-1].stale_outputs == (
            "MDL",
            "MDX",
            "WOK",
            "LYT",
            "VIS",
            "PTH",
            ".mod",
        )
        assert "Inset the selected authored floor plan" in window.statusBar().currentMessage()
    finally:
        window.controller.project.dirty = False
        window.close()
