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

const NativeFunctionImplementation& button_mode_to_toolbutton_style_line_24_bb380d27_native();
const NativeFunctionImplementation& bool_line_13_fecc1a68_native();
const NativeFunctionImplementation& int_line_19_8b8a01b4_native();
const NativeFunctionImplementation& color_alias_view_line_325_52f9db75_native();
const NativeFunctionImplementation& lighten_hex_line_67_a1782f21_native();
const NativeFunctionImplementation& darken_hex_line_74_85a0ded9_native();
const NativeFunctionImplementation& surface_fill_line_81_f8579bb2_native();
const NativeFunctionImplementation& palette_hex_line_96_f8eaa291_native();
const NativeFunctionImplementation& live_native_palette_colors_line_101_eec51d09_native();
const NativeFunctionImplementation& register_bundled_matrix_font_line_207_d17c4cd3_native();
const NativeFunctionImplementation& metric_unit_line_224_c3f1382e_native();
const NativeFunctionImplementation& user_config_root_line_54_179acef8_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::boundary::theme
