#include "PythonFunctions/Properties.h"

namespace ghostrigger::core::tools::spritematerials {

const NativeFunctionImplementation& texarraycache_hit_rate_line_113_9ddcc050_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Tools.SpriteMaterials",
        "ghostrigger::core::tools::spritematerials::core::graphics::tex_atlas",
        "src/core/graphics/tex_atlas.py",
        "TexArrayCache.hit_rate",
        "properties",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Tools.SpriteMaterials","namespace":"ghostrigger::core::tools::spritematerials::core::graphics::tex_atlas","python_file":"src/core/graphics/tex_atlas.py","qualname":"TexArrayCache.hit_rate","name":"hit_rate","callable_type":"properties","line":113,"end_line":115,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* properties_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        texarraycache_hit_rate_line_113_9ddcc050_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::tools::spritematerials
