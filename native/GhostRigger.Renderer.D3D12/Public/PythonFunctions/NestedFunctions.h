#pragma once

#include <cstddef>

namespace ghostrigger::renderer::d3d12 {

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

const NativeFunctionImplementation& texture_content_stats_sample_line_180_6862de25_native();
const NativeFunctionImplementation& skin_3g_candidate_records_norm_pos_line_1096_04f54701_native();
const NativeFunctionImplementation& skin_3g_candidate_records_delta_to_production_line_1109_482a84f4_native();
const NativeFunctionImplementation& compositemodel_construct_bb_line_204_ce6728e6_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::renderer::d3d12
