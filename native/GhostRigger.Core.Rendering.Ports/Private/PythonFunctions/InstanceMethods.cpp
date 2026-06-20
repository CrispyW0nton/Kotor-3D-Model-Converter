#include "PythonFunctions/InstanceMethods.h"

namespace ghostrigger::core::ports {

const NativeFunctionImplementation& filewriterport_write_bytes_line_13_386e4596_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Ports",
        "ghostrigger::core::ports::core::ports::files",
        "src/core/ports/files.py",
        "FileWriterPort.write_bytes",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Ports","namespace":"ghostrigger::core::ports::core::ports::files","python_file":"src/core/ports/files.py","qualname":"FileWriterPort.write_bytes","name":"write_bytes","callable_type":"instance_methods","line":13,"end_line":14,"signature":{"args":["self","path","data"],"positional_count":3,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& filewriterport_write_text_line_16_f4a4863f_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Ports",
        "ghostrigger::core::ports::core::ports::files",
        "src/core/ports/files.py",
        "FileWriterPort.write_text",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Ports","namespace":"ghostrigger::core::ports::core::ports::files","python_file":"src/core/ports/files.py","qualname":"FileWriterPort.write_text","name":"write_text","callable_type":"instance_methods","line":16,"end_line":17,"signature":{"args":["self","path","text","encoding"],"positional_count":3,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& scriptcompilerport_compile_script_line_27_6df94b86_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Ports",
        "ghostrigger::core::ports::core::ports::scripts",
        "src/core/ports/scripts.py",
        "ScriptCompilerPort.compile_script",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Ports","namespace":"ghostrigger::core::ports::core::ports::scripts","python_file":"src/core/ports/scripts.py","qualname":"ScriptCompilerPort.compile_script","name":"compile_script","callable_type":"instance_methods","line":27,"end_line":28,"signature":{"args":["self","source","game"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& texturedecoder_decode_texture_line_27_e83bd02c_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Rendering.Ports",
        "ghostrigger::core::ports::core::ports::textures",
        "src/core/ports/textures.py",
        "TextureDecoder.decode_texture",
        "instance_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Rendering.Ports","namespace":"ghostrigger::core::ports::core::ports::textures","python_file":"src/core/ports/textures.py","qualname":"TextureDecoder.decode_texture","name":"decode_texture","callable_type":"instance_methods","line":27,"end_line":34,"signature":{"args":["self","data","name","source"],"positional_count":2,"keyword_only_count":2,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        filewriterport_write_bytes_line_13_386e4596_native(),
        filewriterport_write_text_line_16_f4a4863f_native(),
        scriptcompilerport_compile_script_line_27_6df94b86_native(),
        texturedecoder_decode_texture_line_27_e83bd02c_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::ports
