#pragma once

#include <cstddef>

namespace ghostrigger::renderer::backend::d3d12 {

#ifndef GHOSTRIGGER_RENDERER_D3D12_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RENDERER_D3D12_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RENDERER_D3D12_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& hardwarediagnostics_from_dict_line_56_a66bccdf_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::renderer::backend::d3d12
