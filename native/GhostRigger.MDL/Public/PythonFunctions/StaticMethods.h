#pragma once

#include <cstddef>

namespace ghostrigger::mdl {

#ifndef GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_MDL_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& mdlbinaryparser_apply_bind_pose_controllers_line_315_3f0185ac_native();
const NativeFunctionImplementation& mdlbinaryparser_generate_missing_normals_line_329_7f0e1ae8_native();
const NativeFunctionImplementation& mdlbinarywriter_validate_animation_export_tree_line_1294_b52fe53c_native();
const NativeFunctionImplementation& mdlbinarywriter_read_animation_offsets_line_401_2e75a594_native();
const NativeFunctionImplementation& mdlbinarywriter_read_animation_name_line_418_a543d9e8_native();
const NativeFunctionImplementation& mdlbinarywriter_read_name_table_line_426_679d4a28_native();
const NativeFunctionImplementation& mdlbinarywriter_animation_export_key_times_line_1692_dd1e2011_native();
const NativeFunctionImplementation& mdlbinarywriter_normalized_xyzw_line_1712_249fd32e_native();
const NativeFunctionImplementation& mdlbinarywriter_validate_animation_export_tree_line_1739_9c16ae75_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::mdl
