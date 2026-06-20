#pragma once

#include <cstddef>

namespace ghostrigger::core::tools::bas {

#ifndef GHOSTRIGGER_TOOLS_BODYATTACHMENTSYSTEM_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_TOOLS_BODYATTACHMENTSYSTEM_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_TOOLS_BODYATTACHMENTSYSTEM_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& ground_snapped_target_origin_mapped_line_2011_8a0fe80f_native();
const NativeFunctionImplementation& apply_external_model_fit_adjustment_transform_point_line_2309_3b6f063d_native();
const NativeFunctionImplementation& normalize_external_model_for_kotor_transform_point_line_2575_98ab7fce_native();
const NativeFunctionImplementation& normalize_external_model_for_kotor_transform_direction_line_2579_9f227abd_native();
const NativeFunctionImplementation& normalize_external_model_for_kotor_transform_node_position_line_2583_bf5207e2_native();
const NativeFunctionImplementation& normalize_external_model_for_kotor_transform_point_line_2692_be866f18_native();
const NativeFunctionImplementation& normalize_external_model_for_kotor_transform_direction_line_2700_d3af9a5d_native();
const NativeFunctionImplementation& normalize_external_model_for_kotor_transform_node_position_line_2706_3aa6f982_native();
const NativeFunctionImplementation& with_supermodel_resource_manager_resolvercontext_construct_line_5113_fc886da7_native();
const NativeFunctionImplementation& with_supermodel_resource_manager_resolvercontext_enter_line_5118_e5652f36_native();
const NativeFunctionImplementation& with_supermodel_resource_manager_resolvercontext_exit_line_5131_fed9154f_native();
const NativeFunctionImplementation& model_nodes_walk_line_5184_c22f7bba_native();
const NativeFunctionImplementation& export_single_format_reload_exported_line_5841_aa70b842_native();
const NativeFunctionImplementation& normalize_bas_transform_values_line_38_bdcb89bd_native();
const NativeFunctionImplementation& normalize_bas_layer_transform_values_line_162_3ef7d12a_native();

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::core::tools::bas
