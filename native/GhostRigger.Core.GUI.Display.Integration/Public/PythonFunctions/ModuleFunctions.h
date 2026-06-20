#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::integration {

#ifndef GHOSTRIGGER_GUI_INTEGRATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_INTEGRATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_INTEGRATION_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& get_line_183_d0d05160_native();
const NativeFunctionImplementation& pixmap_line_200_1195c61b_native();
const NativeFunctionImplementation& icon_for_label_line_204_6228b29f_native();
const NativeFunctionImplementation& action_icon_kwargs_line_223_fa65a2f7_native();
const NativeFunctionImplementation& aurebesh_font_family_line_23_a385f325_native();
const NativeFunctionImplementation& icon_line_154_62eb5d14_native();
const NativeFunctionImplementation& make_scrollable_panel_line_166_f755594c_native();
const NativeFunctionImplementation& make_horizontal_overflow_area_line_184_3547d9dd_native();
const NativeFunctionImplementation& update_legacy_palette_line_209_9a6b8acf_native();
const NativeFunctionImplementation& apply_theme_line_216_a8dea542_native();
const NativeFunctionImplementation& heading_line_228_11c007cd_native();
const NativeFunctionImplementation& safe_call_line_21_1b3760a4_native();
const NativeFunctionImplementation& build_default_tool_integration_registry_line_62_b419589d_native();
const NativeFunctionImplementation& make_package_line_279_4cec85ac_native();
const NativeFunctionImplementation& register_alias_line_286_8b16ed55_native();
const NativeFunctionImplementation& register_group_line_296_d29881e9_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::integration
