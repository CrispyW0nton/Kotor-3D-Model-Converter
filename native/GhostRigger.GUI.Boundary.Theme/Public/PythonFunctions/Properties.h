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

const NativeFunctionImplementation& layoutmanager_packaged_layout_dir_line_35_1ddb6334_native();
const NativeFunctionImplementation& layoutmanager_user_layout_dir_line_39_752bcb64_native();
const NativeFunctionImplementation& thememanager_packaged_theme_dir_line_47_189b0632_native();
const NativeFunctionImplementation& thememanager_user_theme_dir_line_51_07b14327_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::boundary::theme
