#pragma once

#include <cstddef>

namespace ghostrigger::core::camera {

#ifndef GHOSTRIGGER_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_CAMERA_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& cameramanager_install_all_nodes_wrapper_all_nodes_with_generated_line_258_a1a103ec_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::camera
