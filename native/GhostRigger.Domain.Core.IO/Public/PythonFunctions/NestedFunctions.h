#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::io {

#ifndef GHOSTRIGGER_IO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_IO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_IO_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& fbx_mesh_to_gr_mesh_add_poly_vertex_line_172_858003db_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::io
