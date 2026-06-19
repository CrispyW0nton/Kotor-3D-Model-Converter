#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::kotormcp {

const NativeFunctionImplementation& basemodel_model_validate_line_23_d78d3b93_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.KotorMCP",
        "ghostrigger::core::kotormcp::schemas::init",
        "src/kotormcp/schemas/__init__.py",
        "BaseModel.model_validate",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.KotorMCP","namespace":"ghostrigger::core::kotormcp::schemas::init","python_file":"src/kotormcp/schemas/__init__.py","qualname":"BaseModel.model_validate","name":"model_validate","callable_type":"class_methods","line":23,"end_line":31,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        basemodel_model_validate_line_23_d78d3b93_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::kotormcp
