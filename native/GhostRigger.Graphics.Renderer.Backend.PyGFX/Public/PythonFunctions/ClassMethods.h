#pragma once

#include <cstddef>

namespace ghostrigger::graphics::renderer::backend::pygfx {

#ifndef GHOSTRIGGER_RENDERER_PYGFX_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RENDERER_PYGFX_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_RENDERER_PYGFX_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& pygfxviewportrenderer_probe_availability_line_87_bda39575_native();
const NativeFunctionImplementation& pygfxscenebridge_polyline_to_segments_line_524_5d05e78c_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::graphics::renderer::backend::pygfx
