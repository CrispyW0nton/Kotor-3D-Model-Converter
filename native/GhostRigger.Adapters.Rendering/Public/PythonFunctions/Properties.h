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

const NativeFunctionImplementation& gpurenderer_is_gpu_line_2716_996d44b7_native();
const NativeFunctionImplementation& fallbackviewportrenderer_name_line_127_fde2575f_native();
const NativeFunctionImplementation& fallbackviewportrenderer_backend_id_line_132_2bc3f975_native();
const NativeFunctionImplementation& fallbackviewportrenderer_active_renderer_line_196_3eb56d6b_native();
const NativeFunctionImplementation& fallbackviewportrenderer_active_backend_line_200_710bb50c_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::adapters::rendering
