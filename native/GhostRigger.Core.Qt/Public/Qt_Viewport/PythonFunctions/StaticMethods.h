#pragma once

#include <cstddef>

namespace ghostrigger::core::qt::viewport {

#ifndef GHOSTRIGGER_CORE_QT_VIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_CORE_QT_VIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_CORE_QT_VIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& cameragizmorenderer_hex_to_rgba_line_18_cf0993c0_native();
const NativeFunctionImplementation& cameragizmorenderer_blend_line_32_f09bef2b_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::qt::viewport
