#pragma once

#include <cstddef>

namespace ghostrigger::systems::feature::bas {

#ifndef GHOSTRIGGER_SYSTEMS_BAS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SYSTEMS_BAS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_SYSTEMS_BAS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& normalize_bas_transform_values_line_38_bdcb89bd_native();
const NativeFunctionImplementation& normalize_bas_layer_transform_values_line_162_3ef7d12a_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::systems::feature::bas
