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

const NativeFunctionImplementation& themeapplier_precache_stylesheets_line_77_c29937da_native();
const NativeFunctionImplementation& themelayoutsettings_from_settings_line_29_0c63c89b_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::boundary::theme
