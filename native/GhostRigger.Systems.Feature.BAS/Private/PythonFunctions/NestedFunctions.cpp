#include "PythonFunctions/NestedFunctions.h"

namespace ghostrigger::systems::feature::bas {

const NativeFunctionImplementation& normalize_bas_transform_values_line_38_bdcb89bd_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Systems.Feature.BAS",
        "ghostrigger::systems::feature::bas::attachment_alignment",
        "src/systems/bas/attachment_alignment.py",
        "normalize_bas_transform.values",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Systems.Feature.BAS","namespace":"ghostrigger::systems::feature::bas::attachment_alignment","python_file":"src/systems/bas/attachment_alignment.py","qualname":"normalize_bas_transform.values","name":"values","callable_type":"nested_functions","line":38,"end_line":46,"signature":{"args":["key","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& normalize_bas_layer_transform_values_line_162_3ef7d12a_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Systems.Feature.BAS",
        "ghostrigger::systems::feature::bas::model_recipe",
        "src/systems/bas/model_recipe.py",
        "normalize_bas_layer_transform.values",
        "nested_functions",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Systems.Feature.BAS","namespace":"ghostrigger::systems::feature::bas::model_recipe","python_file":"src/systems/bas/model_recipe.py","qualname":"normalize_bas_layer_transform.values","name":"values","callable_type":"nested_functions","line":162,"end_line":170,"signature":{"args":["key","fallback"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* nestedfunctions_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        normalize_bas_transform_values_line_38_bdcb89bd_native(),
        normalize_bas_layer_transform_values_line_162_3ef7d12a_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::systems::feature::bas
