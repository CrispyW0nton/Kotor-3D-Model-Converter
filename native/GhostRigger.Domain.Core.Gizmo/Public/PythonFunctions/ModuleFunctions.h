#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::gizmo {

#ifndef GHOSTRIGGER_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GIZMO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& rgba255_to_float_line_38_22b0952d_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::gizmo
