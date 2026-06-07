#pragma once

#include <cstddef>

namespace ghostrigger::game {

#ifndef GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GAME_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& read_mesh_safe_vec3_list_line_776_3a830960_native();
const NativeFunctionImplementation& read_mesh_safe_vec2_list_line_784_a5cd70ac_native();
const NativeFunctionImplementation& read_mesh_safe_float_line_809_85bd8cf1_native();
const NativeFunctionImplementation& read_mesh_safe_uv_line_815_aa513aa1_native();
const NativeFunctionImplementation& ghostrigger_trimesh_read_read_i32_as_u32_line_367_d948baad_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::game
