#pragma once

#include <cstddef>

namespace ghostrigger::core::lighting {

#ifndef GHOSTRIGGER_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_LIGHTING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& auroralightadapter_is_aurora_light_line_32_72871b3e_native();
const NativeFunctionImplementation& lightingrigpresets_create_line_10_24da2ddb_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::lighting
