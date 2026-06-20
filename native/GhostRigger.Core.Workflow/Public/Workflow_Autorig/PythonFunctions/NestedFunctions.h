#pragma once

#include <cstddef>

namespace ghostrigger::core::autorig {

#ifndef GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_AUTORIG_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& guideplacer_place_guides_clamp_line_327_5bc55e06_native();
const NativeFunctionImplementation& rigextractor_extract_index_line_335_1c027174_native();
const NativeFunctionImplementation& rigextractor_extract_add_bone_line_360_fa66f26c_native();
const NativeFunctionImplementation& rigextractor_extract_walk_dummies_line_382_b4c5b65c_native();
const NativeFunctionImplementation& autorigger_bind_pose_from_fbx_bones_norm_line_872_52f30d34_native();
const NativeFunctionImplementation& meshscaler_apply_scale_node_line_493_fdfe78ca_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::autorig
