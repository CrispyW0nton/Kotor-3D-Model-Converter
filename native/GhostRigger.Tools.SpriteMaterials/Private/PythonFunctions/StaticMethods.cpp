#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::tools::spritematerials {

const NativeFunctionImplementation& texarraycache_convert_line_120_742e16bf_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.SpriteMaterials",
        "ghostrigger::tools::spritematerials::core::graphics::tex_atlas",
        "src/core/graphics/tex_atlas.py",
        "TexArrayCache._convert",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.SpriteMaterials","namespace":"ghostrigger::tools::spritematerials::core::graphics::tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"TexArrayCache._convert","name":"_convert","callable_type":"static_methods","line":120,"end_line":129,"signature":{"args":["img"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation& miparraycache_convert_mip1_line_173_22a0ae15_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Tools.SpriteMaterials",
        "ghostrigger::tools::spritematerials::core::graphics::tex_atlas",
        "src/core/graphics/tex_atlas.py",
        "MipArrayCache._convert_mip1",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Tools.SpriteMaterials","namespace":"ghostrigger::tools::spritematerials::core::graphics::tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"MipArrayCache._convert_mip1","name":"_convert_mip1","callable_type":"static_methods","line":173,"end_line":186,"signature":{"args":["img"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        texarraycache_convert_line_120_742e16bf_native(),
        miparraycache_convert_mip1_line_173_22a0ae15_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::tools::spritematerials
