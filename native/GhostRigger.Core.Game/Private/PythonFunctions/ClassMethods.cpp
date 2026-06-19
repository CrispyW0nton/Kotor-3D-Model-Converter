#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::core::game {

const NativeFunctionImplementation& gffreader_from_bytes_line_256_55910253_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Game",
        "ghostrigger::core::game::core::game::game_library_ext",
        "src/core/game/game_library_ext.py",
        "GFFReader.from_bytes",
        "class_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Game","namespace":"ghostrigger::core::game::core::game::game_library_ext","python_file":"src/core/game/game_library_ext.py","qualname":"GFFReader.from_bytes","name":"from_bytes","callable_type":"class_methods","line":256,"end_line":266,"signature":{"args":["cls","data"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* classmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gffreader_from_bytes_line_256_55910253_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::game
