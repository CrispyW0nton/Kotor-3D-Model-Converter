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

const NativeFunctionImplementation& direct3drenderer_construct_line_15_63a3b021_native();
const NativeFunctionImplementation& direct3drenderer_is_available_line_21_ad1b3dd8_native();
const NativeFunctionImplementation& direct3drenderer_reason_line_24_642745d0_native();
const NativeFunctionImplementation& direct3drenderer_get_capabilities_line_29_8ae24155_native();
const NativeFunctionImplementation& direct3drenderer_get_diagnostics_line_45_b8fcb653_native();
const NativeFunctionImplementation& compositemodel_construct_line_200_c12006dd_native();
const NativeFunctionImplementation& compositemodel_getattr_line_261_4ff9158e_native();
const NativeFunctionImplementation& compositemodel_all_nodes_line_264_09c0cd80_native();
const NativeFunctionImplementation& hardwarediagnostics_to_dict_line_41_dc705848_native();
const NativeFunctionImplementation& hardwarediagnostics_lines_line_73_82d8df33_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::renderer::backend::d3d12
