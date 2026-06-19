#pragma once

#include <cstddef>

namespace ghostrigger::core::meshtools {

#ifndef GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_MESHTOOLS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& cluster_vertices_find_line_60_b7051c5a_native();
const NativeFunctionImplementation& cluster_vertices_union_line_66_9b38cc0d_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::meshtools
