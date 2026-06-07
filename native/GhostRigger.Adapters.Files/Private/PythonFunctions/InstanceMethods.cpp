#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::adapters::files {

const NativeFunctionImplementation& localfilewriter_write_bytes_line_15_ad2c205d_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.Files",
        "ghostrigger::adapters::files::local_file_writer",
        "src/adapters/files/local_file_writer.py",
        "LocalFileWriter.write_bytes",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.Files","namespace":"ghostrigger::adapters::files::local_file_writer","python_file":"src/adapters/files/local_file_writer.py","qualname":"LocalFileWriter.write_bytes","name":"write_bytes","callable_type":"instance_methods","line":15,"end_line":18,"signature":{"args":["self","path","data"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& localfilewriter_write_text_line_20_ec441b06_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Adapters.Files",
        "ghostrigger::adapters::files::local_file_writer",
        "src/adapters/files/local_file_writer.py",
        "LocalFileWriter.write_text",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Adapters.Files","namespace":"ghostrigger::adapters::files::local_file_writer","python_file":"src/adapters/files/local_file_writer.py","qualname":"LocalFileWriter.write_text","name":"write_text","callable_type":"instance_methods","line":20,"end_line":23,"signature":{"args":["self","path","text","encoding"],"positional_count":3,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        localfilewriter_write_bytes_line_15_ad2c205d_native(),
        localfilewriter_write_text_line_20_ec441b06_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::adapters::files
