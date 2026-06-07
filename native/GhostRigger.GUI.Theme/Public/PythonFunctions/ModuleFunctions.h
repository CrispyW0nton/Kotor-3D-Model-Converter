#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_gui_theme {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_gui_libtheme_layout_applier_button_mode_to_toolbutton_style_line_24_bb380d27_descriptor_json();
const char* src_gui_libtheme_layout_loader_bool_line_13_fecc1a68_descriptor_json();
const char* src_gui_libtheme_layout_loader_int_line_19_8b8a01b4_descriptor_json();
const char* src_gui_libtheme_style_tokens_color_alias_view_line_325_52f9db75_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_lighten_hex_line_67_a1782f21_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_darken_hex_line_74_85a0ded9_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_surface_fill_line_81_f8579bb2_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_palette_hex_line_96_f8eaa291_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_live_native_palette_colors_line_101_eec51d09_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_register_bundled_matrix_font_line_207_d17c4cd3_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_metric_unit_line_224_c3f1382e_descriptor_json();
const char* src_gui_libtheme_theme_settings_user_config_root_line_54_179acef8_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_theme
