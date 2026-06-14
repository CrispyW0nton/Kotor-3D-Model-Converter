#pragma once

#include <cstddef>

namespace ghostrigger::domain::core::kotormcp {

#ifndef GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_KOTORMCP_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& filesystemmodellocator_load_mdx_line_401_1325659a_native();
const NativeFunctionImplementation& modelanalyzer_all_nodes_line_571_84d72b05_native();
const NativeFunctionImplementation& modelanalyzer_mesh_nodes_line_579_15aa35bb_native();
const NativeFunctionImplementation& modelanalyzer_bone_nodes_line_604_bf59a565_native();
const NativeFunctionImplementation& modelanalyzer_bbox_line_611_69879d13_native();
const NativeFunctionImplementation& modelanalyzer_node_count_line_617_de9db12b_native();

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count);

} // namespace ghostrigger::domain::core::kotormcp
