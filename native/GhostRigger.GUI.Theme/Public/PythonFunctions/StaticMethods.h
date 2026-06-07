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

const char* src_gui_libtheme_collapsible_group_collapsiblegroupbox_set_layout_visible_line_90_85f101db_descriptor_json();
const char* src_gui_libtheme_layout_validator_layoutvalidator_check_int_line_99_263b6341_descriptor_json();
const char* src_gui_libtheme_qt_stylesheet_builder_qtstylesheetbuilder_is_light_hex_line_15_3f4aad3a_descriptor_json();
const char* src_gui_libtheme_theme_applier_themeapplier_pump_ui_events_line_226_85a620cf_descriptor_json();
const char* src_gui_libtheme_theme_applier_themeapplier_clear_widget_styles_line_337_86ecc521_descriptor_json();
const char* src_gui_libtheme_theme_applier_themeapplier_theme_cache_key_line_343_24d23027_descriptor_json();
const char* src_gui_libtheme_theme_applier_themeapplier_palette_line_359_b00cdd45_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_matrixbarimagepreview_normalize_crop_line_267_40de9110_descriptor_json();
const char* src_gui_libtheme_theme_editor_window_themeeditorwindow_contrast_text_line_1377_8d589e73_descriptor_json();
const char* src_gui_libtheme_theme_loader_themeloader_derive_missing_colors_line_126_dcf96fb7_descriptor_json();
const char* src_gui_libtheme_theme_loader_themeloader_derive_native_colors_line_195_74237dfd_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_gui_theme
