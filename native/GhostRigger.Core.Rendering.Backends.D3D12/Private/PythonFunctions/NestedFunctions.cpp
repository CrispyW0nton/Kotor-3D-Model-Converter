#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::core::rendering::backends::d3d12 {

const NativeFunctionImplementation& texture_content_stats_sample_line_180_6862de25_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Backends.D3D12",
        "ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_texture_content_stats._sample",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Backends.D3D12","namespace":"ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_texture_content_stats._sample","name":"_sample","callable_type":"nested_functions","line":180,"end_line":187,"signature":{"args":["x0","y0"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_3g_candidate_records_norm_pos_line_1096_04f54701_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Backends.D3D12",
        "ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_skin_3g_candidate_records._norm_pos",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Backends.D3D12","namespace":"ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_3g_candidate_records._norm_pos","name":"_norm_pos","callable_type":"nested_functions","line":1096,"end_line":1103,"signature":{"args":["acc"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& skin_3g_candidate_records_delta_to_production_line_1109_482a84f4_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Backends.D3D12",
        "ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_diagnostics_records",
        "src/core/rendering/gpu_diagnostics_records.py",
        "_skin_3g_candidate_records._delta_to_production",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Backends.D3D12","namespace":"ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_diagnostics_records","python_file":"src/core/rendering/gpu_diagnostics_records.py","qualname":"_skin_3g_candidate_records._delta_to_production","name":"_delta_to_production","callable_type":"nested_functions","line":1109,"end_line":1115,"signature":{"args":["pos"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& compositemodel_construct_bb_line_204_ce6728e6_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Backends.D3D12",
        "ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_scene_helpers",
        "src/core/rendering/gpu_scene_helpers.py",
        "_CompositeModel.__init__._bb",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Backends.D3D12","namespace":"ghostrigger::core::rendering::backends::d3d12::core::rendering::gpu_scene_helpers","python_file":"src/core/rendering/gpu_scene_helpers.py","qualname":"_CompositeModel.__init__._bb","name":"_bb","callable_type":"nested_functions","line":204,"end_line":206,"signature":{"args":["m","attr","default"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        texture_content_stats_sample_line_180_6862de25_native(),
        skin_3g_candidate_records_norm_pos_line_1096_04f54701_native(),
        skin_3g_candidate_records_delta_to_production_line_1109_482a84f4_native(),
        compositemodel_construct_bb_line_204_ce6728e6_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::rendering::backends::d3d12
