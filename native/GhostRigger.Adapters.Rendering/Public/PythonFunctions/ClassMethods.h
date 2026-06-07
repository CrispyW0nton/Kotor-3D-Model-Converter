#pragma once

#include <cstddef>

namespace ghostrigger::adapters::rendering {

#ifndef GHOSTRIGGER_ADAPTERS_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ADAPTERS_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ADAPTERS_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& gpurenderer_is_sprite_hilt_line_2650_5adc72a0_native();
const NativeFunctionImplementation& gpurenderer_sprite_alpha_source_line_2665_2b8129c9_native();
const NativeFunctionImplementation& gpurenderer_sprite_glow_line_2677_fe0a0901_native();
const NativeFunctionImplementation& nativeruntimebinding_load_line_703_925af164_native();
const NativeFunctionImplementation& pygfxviewportrenderer_probe_availability_line_87_bda39575_native();
const NativeFunctionImplementation& pygfxscenebridge_polyline_to_segments_line_524_5d05e78c_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::adapters::rendering
