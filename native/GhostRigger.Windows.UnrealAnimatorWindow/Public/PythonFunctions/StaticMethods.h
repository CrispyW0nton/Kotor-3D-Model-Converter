#pragma once

#include <cstddef>

namespace ghostrigger::windows::unrealanimatorwindow {

#ifndef GHOSTRIGGER_WINDOWS_UNREALANIMATORWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_WINDOWS_UNREALANIMATORWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_WINDOWS_UNREALANIMATORWINDOW_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& qtunrealanimatorwindow_node_name_key_line_785_481bc949_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_is_descendant_line_843_54428b4d_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_is_source_null_helper_node_line_869_a373cec2_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_is_source_null_helper_name_line_874_39a297a0_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_node_world_position_line_879_82e27047_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_set_viewport_gpu_enabled_line_1046_75731430_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_source_bone_role_line_1392_11e13bdc_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::windows::unrealanimatorwindow
