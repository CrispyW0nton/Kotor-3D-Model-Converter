#pragma once

#include <cstddef>

namespace ghostrigger::walkmesh {

#ifndef GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WALKMESH_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& walkmeshwriter_roundtrip_line_568_cd29482e_native();
const NativeFunctionImplementation& walkmeshwriter_compute_adjacency_line_631_816fefe7_native();
const NativeFunctionImplementation& walkmeshwriter_pack_line_665_044477c6_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::walkmesh
