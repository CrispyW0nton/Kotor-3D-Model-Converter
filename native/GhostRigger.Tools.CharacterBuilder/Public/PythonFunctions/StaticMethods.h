#pragma once

#include <cstddef>

namespace ghostrigger::tools::characterbuilder {

#ifndef GHOSTRIGGER_TOOLS_CHARACTERBUILDER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_CHARACTERBUILDER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_CHARACTERBUILDER_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& qtcharacterbuilderwindow_character_builder_theme_stylesheet_line_551_081c8327_native();
const NativeFunctionImplementation& qtcharacterbuilderwindow_option_field_line_1975_4be3154b_native();
const NativeFunctionImplementation& qtcharacterbuilderwindow_settings_line_4222_ff8074da_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::tools::characterbuilder
