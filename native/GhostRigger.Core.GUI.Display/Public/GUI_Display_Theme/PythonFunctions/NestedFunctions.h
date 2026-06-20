#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::theme {

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

const NativeFunctionImplementation& themeloader_derive_missing_colors_fill_line_128_25656650_native();
const NativeFunctionImplementation& themelayoutwatcher_start_handler_on_modified_line_32_1956a09d_native();
const NativeFunctionImplementation& themelayoutwatcher_start_handler_on_created_line_36_31753562_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::theme
