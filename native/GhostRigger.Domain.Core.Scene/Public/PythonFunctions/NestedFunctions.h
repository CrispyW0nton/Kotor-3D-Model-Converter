#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::scene {

#ifndef GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_SCENE_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& frustum_update_from_matrix_plane_line_139_e5dad599_native();
const NativeFunctionImplementation& frustum_update_from_camera_plane_through_pos_line_198_93dc44e6_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::scene
