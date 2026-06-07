#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_integration {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_assets_qt_icon_manager_get_line_183_d0d05160_descriptor_json();
const char* src_gui_assets_qt_icon_manager_pixmap_line_200_1195c61b_descriptor_json();
const char* src_gui_assets_qt_icon_manager_icon_for_label_line_204_6228b29f_descriptor_json();
const char* src_gui_assets_qt_icon_manager_action_icon_kwargs_line_223_fa65a2f7_descriptor_json();
const char* src_gui_assets_qt_matrix_background_aurebesh_font_family_line_23_a385f325_descriptor_json();
const char* src_gui_assets_qt_theme_icon_line_154_62eb5d14_descriptor_json();
const char* src_gui_assets_qt_theme_make_scrollable_panel_line_166_f755594c_descriptor_json();
const char* src_gui_assets_qt_theme_make_horizontal_overflow_area_line_184_3547d9dd_descriptor_json();
const char* src_gui_assets_qt_theme_update_legacy_palette_line_209_9a6b8acf_descriptor_json();
const char* src_gui_assets_qt_theme_apply_theme_line_216_a8dea542_descriptor_json();
const char* src_gui_assets_qt_theme_heading_line_228_11c007cd_descriptor_json();
const char* src_gui_integration_editor_services_safe_call_line_21_1b3760a4_descriptor_json();
const char* src_gui_integration_tool_integration_registry_build_default_tool_integration_registry_line_62_b419589d_descriptor_json();
const char* src_gui_qt_lib_make_package_line_279_4cec85ac_descriptor_json();
const char* src_gui_qt_lib_register_alias_line_286_8b16ed55_descriptor_json();
const char* src_gui_qt_lib_register_group_line_296_d29881e9_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_integration
