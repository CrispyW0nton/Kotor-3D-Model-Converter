#pragma once

#include <cstddef>

namespace ghostrigger::graphics::renderer::backend::d3d12 {

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

const NativeFunctionImplementation& compositemodel_nodes_line_292_c770f0f1_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::graphics::renderer::backend::d3d12
