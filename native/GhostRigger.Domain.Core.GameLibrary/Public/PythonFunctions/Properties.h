#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::gamelibrary {

#ifndef GHOSTRIGGER_GAMELIBRARY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GAMELIBRARY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GAMELIBRARY_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& resourceentry_is_model_line_148_43c8a66b_native();
const NativeFunctionImplementation& resourceentry_is_texture_line_158_fe34306f_native();
const NativeFunctionImplementation& resourceentry_ext_line_176_0604481f_native();
const NativeFunctionImplementation& resourceentry_filename_line_183_c3d15313_native();
const NativeFunctionImplementation& modellibraryentry_display_label_line_564_bd018b8d_native();
const NativeFunctionImplementation& modellibraryentry_display_label_rich_line_572_ec474d1b_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::gamelibrary
