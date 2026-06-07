#pragma once

#include <cstddef>

namespace ghostrigger::adapters::qtviewport {

#ifndef GHOSTRIGGER_ADAPTERS_QTVIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_ADAPTERS_QTVIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_ADAPTERS_QTVIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& create_viewport_frame_renderer_line_6_3db885a3_native();
const NativeFunctionImplementation& create_validation_frame_renderer_line_13_70d85031_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::adapters::qtviewport
