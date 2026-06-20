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

const NativeFunctionImplementation& bone_colour_line_122_56b926ee_native();
const NativeFunctionImplementation& build_skeleton_line_131_e387f022_native();
const NativeFunctionImplementation& normalize_skeleton_to_kotor_line_892_8276a0b5_native();
const NativeFunctionImplementation& get_bone_colour_map_line_902_0a076be0_native();
const NativeFunctionImplementation& model_data_line_76_db8ee615_native();
const NativeFunctionImplementation& run_cloth_preset_dialog_line_811_8343f8b1_native();
const NativeFunctionImplementation& confirm_cloth_action_line_823_871d4649_native();
const NativeFunctionImplementation& export_as_mdl_line_1396_38ae9fad_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::autorig
