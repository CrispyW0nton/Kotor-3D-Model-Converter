#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_runtime_shared_resources {

const char* src_resources_game_library_gamelibrary_detect_game_tag_line_815_80fc5b7b_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Runtime.Shared.Resources","python_module":"src.resources.game_library","python_file":"src/resources/game_library.py","qualname":"GameLibrary._detect_game_tag","name":"_detect_game_tag","kind":"static_methods","line":815,"end_line":859,"signature":{"args":["game_dir"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/resources/game_library.py", "GameLibrary._detect_game_tag", "static_methods", &src_resources_game_library_gamelibrary_detect_game_tag_line_815_80fc5b7b_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_runtime_shared_resources
