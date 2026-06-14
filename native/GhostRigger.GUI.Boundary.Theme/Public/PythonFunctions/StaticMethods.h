#pragma once

#include <cstddef>

namespace ghostrigger::gui::boundary::theme {

#ifndef GHOSTRIGGER_GUI_THEME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_THEME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_GUI_THEME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& collapsiblegroupbox_set_layout_visible_line_90_85f101db_native();
const NativeFunctionImplementation& layoutvalidator_check_int_line_99_263b6341_native();
const NativeFunctionImplementation& qtstylesheetbuilder_is_light_hex_line_15_3f4aad3a_native();
const NativeFunctionImplementation& themeapplier_pump_ui_events_line_226_85a620cf_native();
const NativeFunctionImplementation& themeapplier_clear_widget_styles_line_337_86ecc521_native();
const NativeFunctionImplementation& themeapplier_theme_cache_key_line_343_24d23027_native();
const NativeFunctionImplementation& themeapplier_palette_line_359_b00cdd45_native();
const NativeFunctionImplementation& matrixbarimagepreview_normalize_crop_line_267_40de9110_native();
const NativeFunctionImplementation& themeeditorwindow_contrast_text_line_1377_8d589e73_native();
const NativeFunctionImplementation& themeloader_derive_missing_colors_line_126_dcf96fb7_native();
const NativeFunctionImplementation& themeloader_derive_native_colors_line_195_74237dfd_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::boundary::theme
