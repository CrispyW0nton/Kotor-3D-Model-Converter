#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::core::resources::gamelibrary {

const NativeFunctionImplementation& gamelibrary_detect_game_tag_line_815_80fc5b7b_native() {
    static const NativeFunctionImplementation implementation = {
        "GhostRigger.Core.Resources.GameLibrary",
        "ghostrigger::core::resources::gamelibrary::resources::game_library",
        "src/resources/game_library.py",
        "GameLibrary._detect_game_tag",
        "static_methods",
        "native_contract_pending_semantic_port",
        true,
        false,
        true,
        R"grjson({"schema":"ghostrigger.native.cpp_function.v1","project":"GhostRigger.Core.Resources.GameLibrary","namespace":"ghostrigger::core::resources::gamelibrary::resources::game_library","python_file":"src/resources/game_library.py","qualname":"GameLibrary._detect_game_tag","name":"_detect_game_tag","callable_type":"static_methods","line":815,"end_line":859,"signature":{"args":["game_dir"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_language":"C++","native_status":"native_contract_pending_semantic_port","native_first":true,"python_runtime_required":false,"python_fallback_allowed":true,"semantic_port_required":true})grjson"
    };
    return implementation;
}

const NativeFunctionImplementation* staticmethods_native_functions(std::size_t& count) {
    static const NativeFunctionImplementation entries[] = {
        gamelibrary_detect_game_tag_line_815_80fc5b7b_native(),
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::core::resources::gamelibrary
