#include "PythonFunctions/Properties.h"

namespace ghostrigger::domain::core::export_ {

const NativeFunctionImplementation& exportjobresult_succeeded_line_104_a5b01fae_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Domain.Core.Export",
        "ghostrigger::domain::core::export_::core::export_::export_job",
        "src/core/export/export_job.py",
        "ExportJobResult.succeeded",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Domain.Core.Export","namespace":"ghostrigger::domain::core::export_::core::export_::export_job","python_file":"src/core/export/export_job.py","qualname":"ExportJobResult.succeeded","name":"succeeded","callable_type":"properties","line":104,"end_line":105,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        exportjobresult_succeeded_line_104_a5b01fae_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::domain::core::export_
