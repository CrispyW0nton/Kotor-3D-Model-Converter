#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::assets {

#ifndef GHOSTRIGGER_ASSETS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ASSETS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ASSETS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& overridelayer_game_dir_line_112_49db4eaa_native();
const NativeFunctionImplementation& overridelayer_override_dir_line_116_d702c23f_native();
const NativeFunctionImplementation& overridelayer_is_available_line_120_4fde95ac_native();
const NativeFunctionImplementation& overridelayer_entry_count_line_125_b6182ba0_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::assets
