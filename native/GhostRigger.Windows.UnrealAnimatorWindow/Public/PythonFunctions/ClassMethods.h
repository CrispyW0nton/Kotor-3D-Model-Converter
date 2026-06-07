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

const NativeFunctionImplementation& qtunrealanimatorwindow_should_synthesize_quinn_bridge_bone_line_690_77764356_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_nearest_mapped_target_ancestor_line_698_37c74f8e_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_target_chain_between_line_712_6896e5a8_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_can_thread_bridge_between_source_nodes_line_729_d788a09f_native();
const NativeFunctionImplementation& qtunrealanimatorwindow_can_thread_source_spine_line_857_a205a42a_native();

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::windows::unrealanimatorwindow
