#pragma once

#include <cstddef>

namespace ghostrigger::core::modules {

#ifndef GHOSTRIGGER_MODULES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MODULES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_MODULES_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& moduleeditorcontroller_blueprint_type_for_library_asset_line_165_6428786f_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::modules
